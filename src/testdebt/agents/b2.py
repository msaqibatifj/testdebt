"""B2: a single tool-using agent (the comparison that isolates G6).

One LLM loop decides for itself which tool to call next. Same model, KB prompt, Verifier, caps and tests as S3;
what is missing is the Supervisor's policy (no planner, no strategy switch, no narrowing, no memory, no escalation).
Each reply names ONE action and carries the code it applies to; we parse it (no provider tool-calling API, so
malformed calls cannot depend on the provider, and Java never has to be escaped inside JSON):

  ACTION: detect | compile_and_run | pit | submit
  ```java
  <refactored test method(s), as in the output rules>
  ```
detect           static checks + smells left (no build)
compile_and_run  patch, compile, run the class (no mutation testing)
pit              the full check, including the kill-set when PIT is on
submit           the full check; accepted if every gate passes and no targeted smell is left, else rejected. Ends.
The loop also ends at Config.max_steps replies or the token cap (decision 'rejected').
"""
from __future__ import annotations

import re
import time
from dataclasses import asdict
from pathlib import Path

from ..contracts import DebtFinding, RefactorProposal, RunState, TestRef, VerificationReport
from ..java_utils import find_method
from ..prompts import SYSTEM, build_context, parse_reply, utr_prompt
from ..smells import analyze_code
from ..tools.tsdetect import focal_class_file
from ..verify import patch_source, static_checks
from .supervisor import Supervisor

TOOLS = """You can use tools before you answer. Every reply must start with one line naming ONE action, followed by
one ```java block with the code it applies to (what the java block would hold under the output rules above):

ACTION: detect            -> static checks and the test smells still present in your code (no build)
ACTION: compile_and_run   -> puts your code into the test class, compiles it and runs the class
ACTION: pit               -> the full check, including mutation testing: does your code still kill every mutant the
                             original test killed?{pit_note}
ACTION: submit            -> your final answer; it gets the full check and ends the task

You have at most {steps} replies in total, so submit before you run out."""


def parse_action(reply: str) -> tuple[str | None, str]:
    m = re.search(r"ACTION:\s*(detect|compile_and_run|pit|submit)\b", reply, re.I)
    return (m.group(1).lower() if m else None), reply


def summarize(rep: VerificationReport, targets: list[str], with_pit: bool) -> str:
    """Tool result text for the agent: what failed and why, like the retry prompts of B1/S3."""
    if not rep.sane:
        return f"static check failed: {rep.problem}"
    lines = [f"smells still present among the targeted ones: {sorted(set(targets) & set(rep.smells_after)) or 'none'}"]
    if rep.compiled is None:
        lines.append("not compiled (no build in this run)")
    elif not rep.compiled or not rep.passed:
        lines.append(rep.problem[-1500:])
    else:
        lines.append("compiles and all tests of the class pass")
    if with_pit and rep.compiled and rep.passed:
        lines.append(rep.problem[-800:] if rep.killset_preserved is False else
                     "kill-set preserved" if rep.killset_preserved else "kill-set unknown (original kills no mutant)")
    return "\n".join(lines)


class B2Agent(Supervisor):
    SYSTEM_NAME = "b2"
    EVENT = {**Supervisor.EVENT, "agent": "decision"}

    def _detect(self, test: TestRef, original: str, block: str, src: str) -> VerificationReport:
        sane, problem, info = static_checks(original, block)
        rep = VerificationReport(sane=sane, problem=problem, assertions_before=info["assertions_before"],
                                 assertions_after=info["assertions_after"])
        if sane:
            patched = patch_source(src, test.method, block, [])
            tsd = self.verifier.tsdetect
            rep.smells_after = sorted(
                tsd.detect_source(patched, test.class_name, set(info["new_tests"]), focal_class_file(test.file))
                if tsd and tsd.available() and patched else analyze_code(block))
        return rep

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

        original, targets, with_pit = m["text"], list(finding.smells), self.verifier.pit is not None
        task = utr_prompt(self.planner.kb, original, build_context(src, test.class_name), targets) + "\n\n" + \
            TOOLS.format(steps=self.cfg.max_steps, pit_note="" if with_pit else " (NOT enabled in this run)")
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
        st.decision, st.reason = "rejected", f"no submit within {self.cfg.max_steps} replies"
        for n in range(self.cfg.max_steps):
            r = self.refactor.llm.chat(messages, temperature=self.cfg.temperature,
                                       max_tokens=self.cfg.max_tokens_per_call, tag=f"b2:{test.id}:{n}",
                                       seed=self.cfg.seed)
            self.tr.llm("refactor", messages[-1]["content"], r)
            u = r.get("usage", {})
            action, reply = parse_action(r["text"])
            block, imports = parse_reply(reply.split("\n", 1)[1] if action and "\n" in reply else reply)
            st.proposals.append(RefactorProposal(test, original, block, n, u.get("total_tokens", 0),
                                                 (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                                                 r.get("latency_s", 0.0), r.get("cached", False)))
            messages.append({"role": "assistant", "content": r["text"]})
            if action is None:
                result = "No action found. Start your reply with one line 'ACTION: <detect|compile_and_run|pit|submit>'."
                self._log(st, "agent", "invalid-action", r["text"][:200])
            else:
                tv = time.monotonic()
                rep = (self._detect(test, original, block, src) if action == "detect" else
                       self.verifier.verify(test, original, block, imports, finding.smells, pit=action != "compile_and_run"))
                st.reports.append(rep)
                self._log(st, "verifier", action, f"sane={rep.sane} compiled={rep.compiled} passed={rep.passed} "
                                                  f"killset={rep.killset_preserved} smells_after={rep.smells_after}",
                          tool=action, output=asdict(rep), latency_s=round(time.monotonic() - tv, 3))
                result = summarize(rep, targets, with_pit and action != "compile_and_run")
                if action == "submit":
                    left = sorted(set(targets) & set(rep.smells_after))
                    if rep.ok and not left:
                        st.decision, st.reason = "accepted", f"submitted and passed all checks on reply {n + 1}"
                    else:
                        st.reason = "submitted but rejected: " + (rep.problem or f"targeted smells still present: {left}")[:300]
                    self._log(st, "agent", "submit", st.decision)
                    break
            if sum(p.tokens for p in st.proposals) >= self.cfg.token_cap_per_test:
                st.reason = "token cap reached before submit"
                self._log(st, "agent", "stop", "token cap")
                break
            messages.append({"role": "user", "content": f"Tool result ({action or 'none'}):\n{result}"})
        return self._save(st, t0)
