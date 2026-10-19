"""Build data/eval_set.jsonl from UTRefactor's inputs on the pinned project checkouts.

  python3 -m testdebt.eval.build_eval_set                # all projects in data/pins.json
  python3 -m testdebt.eval.build_eval_set --subset 150 --seed 1 --out data/eval_subset150.jsonl

One row per smelly test: project, file, module_dir, class_name, method, smells (tsDetect labels from [1]),
matched (original text found verbatim at the pinned commit), multi_smell.
Stratified subset: proportional by (project, single vs multi smell), seeded, so every system gets the same tests.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from ..java_utils import find_method, module_dir
from .utr_dataset import UTR_NAMES, norm, read_reports


def build(utr_dir: str, projects_dir: str, utr_projects: list[str]) -> list[dict]:
    rows = []
    for p in utr_projects:
        repo = Path(projects_dir, UTR_NAMES.get(p, p))
        files = {f.stem: f for f in repo.rglob("*.java") if "/test/" in f.as_posix()}
        for it in read_reports(utr_dir, p):
            f = files.get(it["class_name"])
            row = {"project": UTR_NAMES.get(p, p), "class_name": it["class_name"], "method": it["method"],
                   "smells": it["smells"], "utr_smells": it["utr_smells"], "multi_smell": len(it["smells"]) > 1,
                   "file": str(f) if f else "", "module_dir": str(module_dir(f)) if f else "", "matched": False,
                   "utr_refactored": it["utr_refactored"]}
            if f:
                src = f.read_text(encoding="utf-8", errors="replace")
                row["matched"] = find_method(src, it["method"]) is not None and norm(it["original"]) in norm(src)
            rows.append(row)
    return rows


def stratified(rows: list[dict], n: int, seed: int) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["project"], r["multi_smell"])].append(r)
    rng, total, out = random.Random(seed), len(rows), []
    for k in sorted(groups):
        g = sorted(groups[k], key=lambda r: (r["class_name"], r["method"]))
        rng.shuffle(g)
        out += g[:max(1, round(n * len(g) / total))]
    return out[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--utr", default="data/utrefactor")
    ap.add_argument("--projects-dir", default="data/projects")
    ap.add_argument("--projects", default="cli,gson,jsoup")
    ap.add_argument("--subset", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="data/eval_set.jsonl")
    a = ap.parse_args()
    rows = [r for r in build(a.utr, a.projects_dir, a.projects.split(",")) if r["matched"]]
    if a.subset:
        rows = stratified(rows, a.subset, a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    by = defaultdict(int)
    for r in rows:
        by[r["project"]] += 1
    print(f"wrote {len(rows)} tests to {a.out}: {dict(by)}  (smells: {sum(len(r['smells']) for r in rows)})")


if __name__ == "__main__":
    main()
