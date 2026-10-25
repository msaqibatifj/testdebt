"""Human review queue for escalated tests (the human-control part of S3).

  python3 -m testdebt.review runs/<run_id>              # review escalated tests one by one: a / r / n / s / q
  python3 -m testdebt.review runs/<run_id> --list       # what is waiting, no input
  python3 -m testdebt.review runs/<run_id> --summary    # human decisions so far -> escalations_summary.json

Decisions go to runs/<run>/escalations.jsonl (test, decision, note, reviewer, time). They never change state.jsonl or
the automatic metrics: the paper reports them separately ("after human review, k of n escalated tests accepted").
Reviewing again appends; the last decision per test counts.
"""
from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path

from .eval import metrics

CHOICES = {"a": "accepted", "r": "rejected", "n": "note"}


def queue(run_dir: Path) -> list[dict]:
    return [r for r in metrics.load(run_dir / "state.jsonl") if r["decision"] == "escalated"]


def decisions(run_dir: Path) -> dict[str, dict]:
    f = run_dir / "escalations.jsonl"
    recs = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []
    return {d["test_id"]: d for d in recs if d["decision"] != "note"}


def show(r: dict) -> str:
    rep = r["reports"][-1] if r["reports"] else {}
    prop = r["proposals"][-1] if r["proposals"] else {"original": "", "refactored": ""}
    diff = difflib.unified_diff(prop["original"].splitlines(), prop["refactored"].splitlines(), "original",
                                f"attempt {len(r['proposals'])}", lineterm="")
    lines = [f"== {r['test_id']}  ({len(r['proposals'])} attempt(s), {r['tokens']} tokens)",
             f"targeted smells: {r['finding']['smells']}   still present: {rep.get('smells_after')}",
             f"why escalated: {r['reason']}", *diff]
    if rep.get("killset_preserved") is False:
        lines.append(f"kill-set: {rep.get('mutants_killed_before')} -> {rep.get('mutants_killed_after')} mutants; "
                     + (rep.get("problem") or "")[:500])
    return "\n".join(lines)


def reviewer() -> str:
    return subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip() or "unknown"


def review(run_dir: Path, ask=input, say=print, who: str | None = None) -> int:
    """Interactive loop; returns how many decisions were recorded. `ask`/`say` are injectable for tests."""
    who, done, n = who or reviewer(), decisions(run_dir), 0
    todo = [r for r in queue(run_dir) if r["test_id"] not in done]
    say(f"{len(todo)} escalated test(s) waiting ({len(done)} already decided)")
    for r in todo:
        say(show(r))
        while True:
            c = ask("[a]ccept  [r]eject  [n]ote  [s]kip  [q]uit > ").strip().lower()[:1]
            if c in ("s", "q") or c in CHOICES:
                break
        if c == "q":
            break
        if c == "s":
            continue
        note = ask("note (optional) > ").strip()
        with (run_dir / "escalations.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"test_id": r["test_id"], "decision": CHOICES[c], "note": note, "reviewer": who,
                                "t": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")
        n += 1
    return n


def summary(run_dir: Path) -> dict:
    q, d = queue(run_dir), decisions(run_dir)
    c = Counter(d[r["test_id"]]["decision"] for r in q if r["test_id"] in d)
    s = {"escalated": len(q), "reviewed": sum(c.values()), "human_accepted": c["accepted"],
         "human_rejected": c["rejected"], "waiting": len(q) - sum(c.values())}
    (run_dir / "escalations_summary.json").write_text(json.dumps(s, indent=1))
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    run_dir = Path(a.run_dir)
    if a.summary:
        print(json.dumps(summary(run_dir), indent=1))
    elif a.list:
        done = decisions(run_dir)
        for r in queue(run_dir):
            print(f"{done.get(r['test_id'], {}).get('decision', 'waiting'):<9} {r['test_id']}  {r['reason'][:100]}")
    else:
        print(f"recorded {review(run_dir)} decision(s) in {run_dir / 'escalations.jsonl'}")


if __name__ == "__main__":
    main()
