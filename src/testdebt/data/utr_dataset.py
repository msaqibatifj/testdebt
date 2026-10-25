"""Read UTRefactor's published inputs and pin each project to the commit those inputs came from.

The replication package (datasets/refactoring/exp/result/<project>/*_refactoring_report.txt) lists, for every
refactored test, the ORIGINAL method text and the smell list tsDetect gave it. The paper does not say which
commit of each project it used, and the current HEADs differ (e.g. Commons-cli later dropped `public` from
its JUnit 5 tests, which tsDetect then ignores). So we scan the project history and pick the commit whose
test files contain the largest share of those original methods verbatim (whitespace-insensitive).

  python3 -m testdebt.data.utr_dataset pin --utr data/utrefactor --project cli --repo data/projects/commons-cli
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from ..tools.tsdetect import UTR_TO_SMELL

UTR_NAMES = {"cli": "commons-cli", "gson": "gson", "jsoup": "jsoup", "math": "commons-math",
             "compress": "commons-compress", "jfreechart": "jfreechart"}
_INPUT = re.compile(r"Input#(\d+)[ \t]*\n((?:(?!Input#|Refactor#).)*?)Smell List:\s*(\[.*?\])", re.S)
_REFACTOR = re.compile(r"Refactor#(\d+)[ \t]*\n(.*?)(?=\n[ \t]*(?:Input#|File#)|\Z)", re.S)
_VOID = re.compile(r"\bvoid\s+(\w+)\s*\(")


def norm(code: str) -> str:
    return re.sub(r"\s+", "", code)


def read_reports(utr_dir: str | Path, project: str) -> list[dict]:
    """[{utr_project, class_name, method, original, utr_smells, smells, utr_refactored}] from the result reports
    (utr_refactored = UTRefactor's PUBLISHED refactoring of that test, used by the b0-replay system)."""
    items = []
    for f in sorted(Path(utr_dir, "datasets/refactoring/exp/result", project).glob("*_refactoring_report.txt")):
        cls = re.sub(r"^\d+(?:-\d+)?_|_refactoring_report$", "", f.stem)
        text = f.read_text(encoding="utf-8", errors="replace")
        refactored = {int(r.group(1)): r.group(2).strip() for r in _REFACTOR.finditer(text)}
        for m in _INPUT.finditer(text):
            code = m.group(2).strip()
            name = _VOID.search(code)
            try:
                labels = ast.literal_eval(m.group(3))
            except (ValueError, SyntaxError):
                labels = []
            if name:
                items.append({"utr_project": project, "class_name": cls, "method": name.group(1),
                              "original": code, "utr_smells": labels,
                              "utr_refactored": refactored.get(int(m.group(1)), ""),
                              "smells": sorted({UTR_TO_SMELL.get(s, s) for s in labels})})
    return items


def _git(repo: str | Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def match_rate(repo: str | Path, commit: str, items: list[dict]) -> tuple[float, dict[str, str]]:
    """Share of items whose original text occurs in their class file at `commit`; also returns class->path."""
    files = [p for p in _git(repo, "ls-tree", "-r", "--name-only", commit).splitlines()
             if p.endswith(".java") and "/test/" in p]
    by_class: dict[str, str] = {}
    for p in files:
        by_class.setdefault(Path(p).stem, p)
    cache: dict[str, str] = {}
    hits = 0
    for it in items:
        path = by_class.get(it["class_name"])
        if not path:
            continue
        if path not in cache:
            cache[path] = norm(_git(repo, "show", f"{commit}:{path}"))
        hits += norm(it["original"]) in cache[path]
    return (hits / len(items) if items else 0.0), by_class


def pin(repo: str | Path, items: list[dict], since: str = "2022-01-01", until: str = "2024-12-31",
        every: int = 10) -> dict:
    """Coarse scan (every Nth commit), then fine scan around the best one."""
    log = _git(repo, "log", f"--since={since}", f"--until={until}", "--format=%H %ad", "--date=short").split("\n")
    commits = [l.split() for l in log if l.strip()]
    if not commits:
        raise RuntimeError("no commits in range; clone with full history (setup script does this)")
    scores = {}
    for i in range(0, len(commits), every):
        scores[i] = match_rate(repo, commits[i][0], items)[0]
    best = max(scores, key=scores.get)
    for i in range(max(0, best - every), min(len(commits), best + every)):
        if i not in scores:
            scores[i] = match_rate(repo, commits[i][0], items)[0]
    best = max(scores, key=lambda i: (scores[i], -i))      # ties -> most recent
    return {"commit": commits[best][0], "date": commits[best][1], "match_rate": round(scores[best], 3),
            "checked": len(scores)}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pin")
    p.add_argument("--utr", default="data/utrefactor")
    p.add_argument("--project", required=True, help="cli | gson | jsoup | ...")
    p.add_argument("--repo", required=True)
    p.add_argument("--out", default="data/pins.json")
    a = ap.parse_args()
    items = read_reports(a.utr, a.project)
    res = pin(a.repo, items)
    res.update(project=UTR_NAMES.get(a.project, a.project), utr_tests=len(items))
    out = Path(a.out)
    pins = json.loads(out.read_text()) if out.exists() else {}
    pins[res["project"]] = res
    out.write_text(json.dumps(pins, indent=2))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
