"""Agent trajectories: one JSON event per step, in runs/<run>/trajectories/<test>.jsonl.

  python3 -m testdebt.trace runs/<run_id> 'commons-cli:HelpFormatterTest#testFoo'     # readable timeline

Event fields: t (s since the test started), step, agent (detection | planner | refactor | verifier | supervisor |
pipeline | human), event (llm_call | tool_call | decision | state_change | error), and when relevant: tool, input
(first 2 KB), output (first 4 KB), reasoning, state_after, tokens, latency_s, cached. Longer texts are cut and
stored whole in runs/<run>/blobs/<sha256>.txt, so any decision can be traced to the full output that caused it.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

IN_MAX, OUT_MAX = 2048, 4096


def file_name(test_id: str) -> str:
    return re.sub(r"[^\w.-]", "_", test_id) + ".jsonl"   # ':' and '#' are not valid in Windows paths


class Trace:
    """Trajectory of one test in one run. Starts a fresh file, so a resumed test is not mixed with its old trace."""

    def __init__(self, run_dir: str | Path, test_id: str):
        self.run_dir = Path(run_dir)
        self.path = self.run_dir / "trajectories" / file_name(test_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self.step, self.t0 = 0, time.monotonic()

    def _text(self, value, limit: int) -> str:
        s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        if len(s) <= limit:
            return s
        sha = hashlib.sha256(s.encode()).hexdigest()
        blob = self.run_dir / "blobs" / f"{sha}.txt"
        if not blob.exists():
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_text(s, encoding="utf-8")
        return s[:limit] + f"\n... [{len(s)} chars, full text in blobs/{sha}.txt]"

    def event(self, agent: str, event: str, *, input=None, output=None, **fields) -> dict:
        self.step += 1
        rec = {"t": round(time.monotonic() - self.t0, 3), "step": self.step, "agent": agent, "event": event}
        if input is not None:
            rec["input"] = self._text(input, IN_MAX)
        if output is not None:
            rec["output"] = self._text(output, OUT_MAX)
        rec.update({k: v for k, v in fields.items() if v is not None})
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        return rec

    def llm(self, agent: str, prompt: str, r: dict) -> dict:
        """One LLM call: prompt, reply, the model's reasoning field when the provider returns one, cost."""
        return self.event(agent, "llm_call", input=prompt, output=r.get("text", ""),
                          reasoning=(r.get("response_raw_message") or {}).get("reasoning"),
                          tokens=(r.get("usage") or {}).get("total_tokens"), latency_s=r.get("latency_s"),
                          cached=r.get("cached"))


def timeline(run_dir: str | Path, test_id: str) -> str:
    lines = []
    for l in Path(run_dir, "trajectories", file_name(test_id)).read_text(encoding="utf-8").splitlines():
        e = json.loads(l)
        head = f"{e['step']:>3} {e['t']:>8.2f}s  {e['agent']:<10} {e['event']:<12}"
        extra = " ".join(f"{k}={e[k]}" for k in ("tool", "tokens", "latency_s", "cached") if k in e)
        lines.append(f"{head} {extra}".rstrip())
        for k in ("state_after", "output"):
            if k in e:
                text = e[k] if isinstance(e[k], str) else json.dumps(e[k])
                lines.append(f"{'':27}{k}: {text[:200].replace(chr(10), ' ')}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python3 -m testdebt.trace runs/<run_id> '<project>:<Class>#<method>'")
    print(timeline(sys.argv[1], sys.argv[2]))
