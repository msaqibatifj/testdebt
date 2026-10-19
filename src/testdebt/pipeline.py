"""Control flow of each system. Same model, KB, tools, caps and tests everywhere: only the control flow differs.

  single  plain prompt (no KB), 1 attempt, accepted if it compiles and passes  [the 'direct LLM' reference of [1]]
  b0replay  UTRefactor's PUBLISHED refactorings (from its replication package) pushed through OUR verifier:
          no LLM calls; checks our measurement against the paper and gives G1 numbers for [1] itself
  b0      UTRefactor reproduction: KB prompt (smell definition + DSL rule + checkpoints, chain of thought),
          1 attempt, accepted if it compiles and passes  (as in [1])
  b1      fixed pipeline: KB prompt, verify (compile, run, targeted smells gone, kill-set if PIT is on);
          on failure ONE fixed retry prompt carrying the error text, up to 2 retries, then rejected
  b2, s3  Phase 2 (single tool-using agent; multi-agent with Supervisor) - same interface
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .contracts import DebtFinding, RefactorProposal, RunState, TestRef, VerificationReport
from .java_utils import find_method
from .prompts import SYSTEM, KnowledgeBase, build_context, parse_reply, plain_prompt, retry_prompt, utr_prompt
from .verify import Verifier

SYSTEMS = ("single", "b0replay", "b0", "b1", "b2", "s3")


@dataclass
class Config:
    system: str = "b1"
    max_retries: int = 2             # b1 only
    max_tokens_per_call: int = 8000
    token_cap_per_test: int = 60000
    temperature: float = 0.7
    seed: int = 1
    require_smells_removed: bool = True   # b1 gate


def _stage(rep: VerificationReport) -> str:
    if not rep.sane:
        return "static check"
    if rep.compiled is False:
        return "compile"
    if rep.passed is False:
        return "test run"
    if rep.killset_preserved is False:
        return "kill-set (mutation testing)"
    return "smell check"


class Pipeline:
    def __init__(self, llm, verifier: Verifier, kb: KnowledgeBase, cfg: Config, run_dir: str | Path):
        if cfg.system not in SYSTEMS:
            raise ValueError(f"unknown system {cfg.system}; choose from {SYSTEMS}")
        if cfg.system in ("b2", "s3"):
            raise NotImplementedError(f"{cfg.system} is a Phase 2 deliverable (same interface as b1)")
        if cfg.system in ("b0", "b1") and not kb.available():
            raise RuntimeError("UTRefactor knowledge base not found: run scripts/setup_projects.sh (clones it to data/utrefactor)")
        self.llm, self.verifier, self.kb, self.cfg = llm, verifier, kb, cfg
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.run_dir / "state.jsonl"

    def done_ids(self) -> set[str]:
        """Resume support: tests already recorded in this run."""
        if not self.state_file.exists():
            return set()
        return {json.loads(l)["test_id"] for l in self.state_file.read_text(encoding="utf-8").splitlines() if l.strip()}

    def _call(self, prompt: str, tag: str) -> tuple[str, dict]:
        r = self.llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                          temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens_per_call, tag=tag,
                          seed=self.cfg.seed)
        return r["text"], r

    def process(self, test: TestRef, finding: DebtFinding, replay: str | None = None) -> RunState:
        t0 = time.monotonic()
        st = RunState(run_id=self.run_dir.name, system=self.cfg.system, seed=self.cfg.seed, test=test, finding=finding)
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
        base = (plain_prompt(original, context, finding.smells) if self.cfg.system == "single"
                else utr_prompt(self.kb, original, context, finding.smells))
        attempts = 1 + (self.cfg.max_retries if self.cfg.system == "b1" else 0)
        prompt, tokens = base, 0
        for n in range(attempts):
            if self.cfg.system == "b0replay":
                if not replay:
                    st.decision, st.reason = "skipped", "no published UTRefactor output for this test"
                    return self._save(st, t0)
                reply, r = f"```java\n{replay}\n```", {"usage": {}, "latency_s": 0.0, "cached": True}
            else:
                reply, r = self._call(prompt, tag=f"{self.cfg.system}:{test.id}:{n}")
            u = r.get("usage", {})
            tokens += u.get("total_tokens", 0)
            block, imports = parse_reply(reply)
            st.proposals.append(RefactorProposal(test, original, block, n, u.get("total_tokens", 0),
                                                 (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                                                 r.get("latency_s", 0.0), r.get("cached", False)))
            rep = self.verifier.verify(test, original, block, imports, finding.smells)
            if self.cfg.system == "b1":
                if self.cfg.require_smells_removed and rep.ok:
                    left = sorted(set(finding.smells) & set(rep.smells_after))
                    if left:
                        rep.problem = f"targeted smells still present after refactoring: {left}"
                accepted = rep.ok and not rep.problem
            else:   # single / b0 / b0replay: accepted if it compiles and runs, as in [1]; kill-set is only MEASURED (G1a)
                accepted = rep.sane and rep.compiled is not False and rep.passed is not False
            st.reports.append(rep)
            if accepted:
                st.decision, st.reason = "accepted", f"passed all checks on attempt {n + 1}"
                break
            st.decision, st.reason = "rejected", f"failed at {_stage(rep)}: {rep.problem[:300]}"
            if tokens >= self.cfg.token_cap_per_test:
                st.reason += " | token cap reached"
                break
            prompt = retry_prompt(base, _stage(rep), rep.problem or "unknown", block)
        return self._save(st, t0)

    def _save(self, st: RunState, t0: float) -> RunState:
        st.wall_time_s = round(time.monotonic() - t0, 2)
        with self.state_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(st.to_json(), ensure_ascii=False) + "\n")
        return st
