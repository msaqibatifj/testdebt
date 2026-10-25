"""Fixed dev/test/rest splits of the evaluation set (built once, committed, never regenerated).

  python3 -m testdebt.data.splits --seed 1      # writes data/splits/{dev,test,rest}.jsonl

dev  (80):  stratified by project x single/multi smell, seed       -> prompt, threshold and cap tuning
test (150): same strata, seed + 1, drawn from what dev left         -> E1-E6 LLM runs only, no design decisions
rest:       everything else                                         -> no-LLM runs (b0replay, detector agreement)
Files hold test IDs only (project:Class#method), so no UTRefactor code is committed.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .build_eval_set import stratified

SPLITS_DIR = Path("data/splits")
SIZES = {"dev": 80, "test": 150}


def test_id(r: dict) -> str:
    return f"{r['project']}:{r['class_name']}#{r['method']}"


def make(rows: list[dict], seed: int) -> dict[str, list[dict]]:
    dev = stratified(rows, SIZES["dev"], seed)
    used = {test_id(r) for r in dev}
    test = stratified([r for r in rows if test_id(r) not in used], SIZES["test"], seed + 1)
    used |= {test_id(r) for r in test}
    return {"dev": dev, "test": test, "rest": [r for r in rows if test_id(r) not in used]}


def load(split: str, splits_dir: str | Path = SPLITS_DIR) -> list[str]:
    """Test IDs of one split; 'all' is the union."""
    names = ["dev", "test", "rest"] if split == "all" else [split]
    return [json.loads(l)["test_id"] for s in names
            for l in Path(splits_dir, f"{s}.jsonl").read_text().splitlines() if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default="data/eval_set.jsonl")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=str(SPLITS_DIR))
    a = ap.parse_args()
    rows = [json.loads(l) for l in Path(a.eval).read_text().splitlines() if l.strip()]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    for name, rs in make(rows, a.seed).items():
        Path(a.out, f"{name}.jsonl").write_text("".join(json.dumps({"test_id": test_id(r)}) + "\n" for r in rs))
        print(f"{name}: {len(rs)} tests {dict(sorted(Counter(r['project'] for r in rs).items()))}")


if __name__ == "__main__":
    main()
