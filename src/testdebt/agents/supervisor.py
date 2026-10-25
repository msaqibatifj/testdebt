"""S3: multi-agent system with a Supervisor (Phase 1 skeleton; see docs/architecture.png).

Same model, KB, tools, caps and tests as the baselines. What differs is the control flow: a Supervisor reads
the Verifier's evidence and picks the next action instead of following a fixed retry script.

  Detection agent  -> which targeted smells are really present (tsDetect when available, else labels of [1])
  Planner agent    -> which smells to target in this attempt, and with which prompt (KB rule / plain)
  Refactor agent   -> one LLM call
  Verifier agent   -> tool evidence only (static checks, compile, run, smells after, kill-set with --pit)
  Supervisor       -> accept | retry with feedback | switch strategy | escalate

Supervisor policy (deterministic, so runs are reproducible and every decision is logged in RunState.trace):
  * accept     all gates pass and no targeted smell is left
  * retry      the attempt failed at a gate for the first time -> feed the error back
  * switch     the same gate failed twice in a row, or the reply repeats a failed proposal
               -> narrow the plan to the smells not yet removed, and change prompt strategy (KB <-> plain)
  * escalate   attempts or tokens exhausted -> decision "escalated" (goes to the human review queue)
Memory: the (strategy, smells, proposal hash) of every failed attempt, so the same proposal is never re-verified.

Phase 2 work (not here): JNose as a second detector inside Detection, LLM-based planning, B2.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ..contracts import DebtFinding, RefactorProposal, RunState, TestRef, VerificationReport
from ..java_utils import find_method
from ..pipeline import Config, _stage
from ..prompts import KnowledgeBase, build_context, parse_reply, retry_prompt
from ..verify import Verifier
from .detection import DetectionAgent
from .planner import PlannerAgent
from .refactor import RefactorAgent


class Supervisor:
    """Owns the per-test loop and the RunState; same run-dir layout and resume behaviour as Pipeline."""

    def __init__(self, llm, verifier: Verifier, kb: KnowledgeBase, cfg: Config, run_dir: str | Path,
                 max_attempts: int = 3):
        self.verifier, self.cfg, self.max_attempts = verifier, cfg, max_attempts
        self.detect, self.planner, self.refactor = DetectionAgent(verifier), PlannerAgent(kb), RefactorAgent(llm, cfg)
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.run_dir / "state.jsonl"

    def done_ids(self) -> set[str]:
        if not self.state_file.exists():
            return set()
        recs = [json.loads(l) for l in self.state_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        return {r["test_id"] for r in recs if r["decision"] != "error"}   # errors are retried on resume

    @staticmethod
    def _log(st: RunState, who: str, action: str, note: str = "") -> None:
        st.trace.append({"agent": who, "action": action, "note": note[:300]})

    def process(self, test: TestRef, finding: DebtFinding, replay: str | None = None) -> RunState:
        """Any exception (LLM, Maven, PIT, detector) is recorded as decision 'error' and the run continues."""
        t0 = time.monotonic()
        st = RunState(run_id=self.run_dir.name, system="s3", seed=self.cfg.seed, test=test, finding=finding)
        try:
            return self._process(st, test, finding, replay, t0)
        except Exception as e:   # keeps the partial state: tokens already spent still count
            st.decision, st.reason = "error", f"{type(e).__name__}: {e}"[:300]
            return self._save(st, t0)

    def _process(self, st: RunState, test: TestRef, finding: DebtFinding, replay: str | None, t0: float) -> RunState:
        src = Path(test.file).read_text(encoding="utf-8", errors="replace")
        m = find_method(src, test.method)
        if m is None:
            st.decision, st.reason = "skipped", "method not found uniquely in the pinned source"
            return self._save(st, t0)
        ok, log = self.verifier.baseline_ok(test)
        if not ok:
            st.decision, st.reason = "skipped", "original test class does not compile/pass in this environment: " + log[-300:]
            return self._save(st, t0)

        original, context = m["text"], build_context(src, test.class_name)
        targets = self.detect.run(test, src, finding)
        self._log(st, "detection", "smells", ",".join(targets))

        strategy, failed, last_stage, tokens = "kb", set(), None, 0
        prompt = self.planner.prompt(strategy, original, context, targets)
        self._log(st, "planner", "plan", f"strategy={strategy} targets={targets}")
        for n in range(self.max_attempts):
            reply, r = self.refactor.run(prompt, tag=f"s3:{test.id}:{n}")
            u = r.get("usage", {})
            tokens += u.get("total_tokens", 0)
            block, imports = parse_reply(reply)
            st.proposals.append(RefactorProposal(test, original, block, n, u.get("total_tokens", 0),
                                                 (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                                                 r.get("latency_s", 0.0), r.get("cached", False)))
            key = hashlib.sha1(block.strip().encode()).hexdigest()
            if key in failed:                                 # memory: do not re-verify a proposal that already failed
                rep = VerificationReport(sane=False, problem="identical to an earlier rejected proposal")
                self._log(st, "supervisor", "memory-hit", "proposal repeats a failed one")
            else:
                rep = self.verifier.verify(test, original, block, imports, finding.smells)
                self._log(st, "verifier", "report", f"sane={rep.sane} compiled={rep.compiled} passed={rep.passed} "
                                                    f"killset={rep.killset_preserved} smells_after={rep.smells_after}")
            st.reports.append(rep)
            left = sorted(set(targets) & set(rep.smells_after))
            if rep.ok and not left:
                st.decision, st.reason = "accepted", f"supervisor accepted on attempt {n + 1}"
                self._log(st, "supervisor", "accept")
                break
            failed.add(key)
            stage = _stage(rep) if not rep.ok else "smell check"
            problem = rep.problem or (f"targeted smells still present after refactoring: {left}" if left else "unknown")
            st.decision, st.reason = "escalated", f"failed at {stage}: {problem[:300]}"
            if tokens >= self.cfg.token_cap_per_test:
                st.reason += " | token cap reached"
                self._log(st, "supervisor", "escalate", "token cap")
                break
            if n == self.max_attempts - 1:
                self._log(st, "supervisor", "escalate", "attempts exhausted")
                break
            if stage == last_stage or rep.problem.startswith("identical"):
                strategy = self.planner.switch(strategy)
                if left:
                    targets = left
                base = self.planner.prompt(strategy, original, context, targets)
                prompt = retry_prompt(base, stage, problem, block)
                self._log(st, "supervisor", "switch", f"strategy={strategy} targets={targets}")
            else:
                prompt = retry_prompt(self.planner.prompt(strategy, original, context, targets), stage, problem, block)
                self._log(st, "supervisor", "retry", stage)
            last_stage = stage
        return self._save(st, t0)

    def _save(self, st: RunState, t0: float) -> RunState:
        st.wall_time_s = round(time.monotonic() - t0, 2)
        with self.state_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(st.to_json(), ensure_ascii=False) + "\n")
        return st
