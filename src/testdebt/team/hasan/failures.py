"""Failure analysis: one category per non-accepted test, from the final report (automatic, then checked by hand).

  python3 -m testdebt.team.hasan.failures runs/<run> [runs/<run> ...] --name E3
      -> results/failures/<name>_categories.csv (run, test, decision, category, stage, message) and counts
  ... --case success1 '<project>:<Class>#<method>' --case failure1 '...'
      -> cases/<name>.md (timeline + final code) and cases/<name>.jsonl (raw trajectory), from the first run

The category order matters: the first rule that matches wins.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from ...eval import metrics
from ...trace import file_name, timeline

# APIs [1]'s and our model's outputs use that the pinned projects do not have (JUnit 5 / Truth in JUnit 4 code)
FOREIGN_API = re.compile(r"assertDoesNotThrow|assertAll|org\.junit\.jupiter|assertWithMessage|ThrowingRunnable"
                         r"|package org\.junit\.jupiter\S* does not exist")
CATEGORIES = ["infrastructure error", "budget exhausted", "malformed reply", "assertion dropped or empty test",
              "compile: API not in the project", "compile: missing symbol or import", "compile: other",
              "fixture clobbered by extracted setup", "semantic change: test now fails",
              "weakened test: kill-set loss", "smell not removed / new smell"]


def classify(r: dict) -> tuple[str, str, str]:
    """-> (category, stage, message) for one state record."""
    rep = r["reports"][-1] if r["reports"] else {}
    msg = (rep.get("problem") or r.get("reason") or "")[:400]
    block = r["proposals"][-1]["refactored"] if r["proposals"] else ""
    if r["decision"] == "error":
        return "infrastructure error", "exception", r["reason"][:400]
    if "token cap" in r.get("reason", ""):
        return "budget exhausted", "supervisor", r["reason"][:400]
    if not rep.get("sane", False):
        if "assertions dropped" in msg:
            return "assertion dropped or empty test", "static check", msg
        return "malformed reply", "static check", msg
    if rep.get("compiled") is False:
        if FOREIGN_API.search(msg):
            return "compile: API not in the project", "compile", msg
        if "cannot find symbol" in msg or "does not exist" in msg:
            return "compile: missing symbol or import", "compile", msg
        return "compile: other", "compile", msg
    if rep.get("passed") is False:
        if re.search(r"@Before(Each)?\b|\bsetUp\s*\(|@BeforeClass|@BeforeAll", block):
            return "fixture clobbered by extracted setup", "test run", msg
        return "semantic change: test now fails", "test run", msg
    if rep.get("killset_preserved") is False:
        return "weakened test: kill-set loss", "kill-set", msg
    return "smell not removed / new smell", "smell check", msg


def export_case(run_dir: str | Path, test_id: str, out_dir: str | Path, name: str) -> Path:
    """One representative case for the paper: cases/<name>.jsonl (the raw trajectory) and cases/<name>.md
    (decision, failure category, timeline, final refactoring)."""
    r = next((r for r in metrics.load(Path(run_dir, "state.jsonl")) if r["test_id"] == test_id), None)
    if r is None:
        raise SystemExit(f"{test_id} is not in {run_dir}/state.jsonl")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(run_dir, "trajectories", file_name(test_id)), out / f"{name}.jsonl")
    cat = "accepted" if r["decision"] == "accepted" else classify(r)[0]
    final = r["proposals"][-1]["refactored"] if r["proposals"] else "(no proposal)"
    md = [f"# {name}: {test_id}", "", f"- run: `{Path(run_dir).name}`", f"- decision: **{r['decision']}** ({cat})",
          f"- reason: {r['reason']}", f"- attempts: {len(r['proposals'])}, tokens: {r['tokens']}", "",
          "## Trajectory", "", "```", timeline(run_dir, test_id), "```", "", "## Final refactoring", "",
          "```java", final, "```", ""]
    (out / f"{name}.md").write_text("\n".join(md), encoding="utf-8")
    return out / f"{name}.md"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", default="results/failures")
    ap.add_argument("--case", nargs=2, action="append", default=[], metavar=("NAME", "TEST_ID"),
                    help="also export this test of the first run to cases/NAME.{md,jsonl} (repeatable)")
    a = ap.parse_args()
    for name, test_id in a.case:
        print("wrote", export_case(a.runs[0], test_id, "cases", name))
    rows = []
    for run in a.runs:
        for r in metrics.load(Path(run, "state.jsonl")):
            if r["decision"] not in ("accepted", "skipped"):
                rows.append({"run": Path(run).name, "test": r["test_id"], "decision": r["decision"],
                             **dict(zip(("category", "stage", "message"), classify(r)))})
    Path(a.out).mkdir(parents=True, exist_ok=True)
    with open(Path(a.out, f"{a.name}_categories.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["run", "test", "decision", "category", "stage", "message"])
        w.writeheader()
        w.writerows(rows)
    counts = Counter(r["category"] for r in rows)
    summary = {"failures": len(rows), "counts": {c: counts[c] for c in CATEGORIES if counts[c]}}
    Path(a.out, f"{a.name}_counts.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
