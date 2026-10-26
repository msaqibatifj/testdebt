"""E4-G2, no LLM: how far do tsDetect and JNose agree on the ORIGINAL test methods, and do they confirm [1]'s labels?

  python3 -m testdebt.team.hasan.agreement --split all          # -> results/E4/g2_agreement.{csv,json}

Per smell type: tests flagged by tsDetect, by JNose, by both, Cohen's kappa (present/absent per test), and the
share of [1]'s labels each detector confirms. Same method isolation for both detectors (tools/tsdetect.keep_only).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from ...data import splits
from ...tools.tsdetect import COLUMN_TO_SMELL, TsDetect, focal_class_file, keep_only
from .jnose import JNose
from .stats import cohen_kappa


def detect_all(rows: list[dict], tsd: TsDetect, jn: JNose) -> dict[str, tuple[set, set]]:
    units = []
    for r in rows:
        src = Path(r["file"]).read_text(encoding="utf-8", errors="replace")
        units.append({"key": splits.test_id(r), "source": keep_only(src, {r["method"]}), "class_name": r["class_name"],
                      "production_file": focal_class_file(r["file"])})
    ts, js = tsd.detect_units(units), jn.detect_units(units)
    return {k: (ts[k], js[k]) for k in ts}


def table(rows: list[dict], found: dict[str, tuple[set, set]]) -> list[dict]:
    out = []
    for smell in sorted(set(COLUMN_TO_SMELL.values())):
        a = [smell in found[splits.test_id(r)][0] for r in rows]
        b = [smell in found[splits.test_id(r)][1] for r in rows]
        lab = [r for r in rows if smell in r["smells"]]
        if not (any(a) or any(b) or lab):
            continue
        out.append({"smell": smell, "tests": len(rows), "tsdetect": sum(a), "jnose": sum(b),
                    "both": sum(x and y for x, y in zip(a, b)), "kappa": cohen_kappa(a, b),
                    "labelled_by_utr": len(lab),
                    "labels_confirmed_tsdetect": sum(smell in found[splits.test_id(r)][0] for r in lab),
                    "labels_confirmed_jnose": sum(smell in found[splits.test_id(r)][1] for r in lab),
                    "labels_confirmed_both": sum(smell in found[splits.test_id(r)][0] & found[splits.test_id(r)][1]
                                                 for r in lab)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default="data/eval_set.jsonl")
    ap.add_argument("--split", default="all")
    ap.add_argument("--out", default="results/E4")
    a = ap.parse_args()
    ids = set(splits.load(a.split))
    rows = [r for r in map(json.loads, Path(a.eval).read_text().splitlines()) if splits.test_id(r) in ids]
    tsd, jn = TsDetect("data/utrefactor/detection/v3/TestSmellDetector.jar"), JNose()
    if not (tsd.available() and jn.available()):
        raise SystemExit("needs the tsDetect jar (setup_projects.sh) and JNose (team/hasan/get_jnose.sh)")
    by_proj = defaultdict(list)
    for r in rows:
        by_proj[r["project"]].append(r)
    found = {}
    for p, rs in sorted(by_proj.items()):
        found.update(detect_all(rs, tsd, jn))
    t = table(rows, found)
    lab = sum(x["labelled_by_utr"] for x in t)
    overall = {"split": a.split, "tests": len(rows), "labelled_smells": lab,
               **{f"labels_confirmed_{d}_pct": round(100 * sum(x[f"labels_confirmed_{d}"] for x in t) / lab, 1)
                  for d in ("tsdetect", "jnose", "both")}}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    with open(Path(a.out, "g2_agreement.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(t[0]))
        w.writeheader()
        w.writerows(t)
    Path(a.out, "g2_agreement.json").write_text(json.dumps({"overall": overall, "by_smell": t}, indent=1))
    Path(a.out, "g2_detections.json").write_text(json.dumps({k: [sorted(v[0]), sorted(v[1])] for k, v in found.items()}))
    print(json.dumps(overall, indent=1))
    for x in t:
        print(f"{x['smell']:<26} ts={x['tsdetect']:<4} jn={x['jnose']:<4} both={x['both']:<4} kappa={x['kappa']}")


if __name__ == "__main__":
    main()
