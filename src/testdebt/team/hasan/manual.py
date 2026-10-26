"""Rule iii (G2): manual labels on a 100-test sample, the reference both detectors are judged against.

  python3 -m testdebt.team.hasan.manual sample runs/<E3 run> --n 100      # -> results/E4/manual/sheet_<run>.csv
      one row per (test, targeted smell): before/after code paths and both detectors' verdicts are NOT shown
      to the labellers; they fill  present_before_<labeller>, present_after_<labeller>  with 1/0
  python3 -m testdebt.team.hasan.manual score results/E4/manual/sheet_<run>.csv   # -> ..._score.json
      kappa labeller vs labeller; adjudicated label = agreement, else the 'adjudicated_after' column;
      kappa of tsDetect and JNose vs adjudicated; rule iii reduction = smells present before and gone after

Calibrate the guide (docs in labelling_guide.md here) on 20 dev tests first; then the sample comes from the test
split (seeded), and nothing is tuned on it.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from ...eval import metrics
from .stats import cohen_kappa

LABELLERS = ("hasan", "gulsher")


def sample(run_dir: str, n: int, seed: int, out_dir: str) -> Path:
    recs = [r for r in metrics.load(Path(run_dir, "state.jsonl")) if r["reports"] and r["reports"][-1].get("sane")]
    recs = sorted(recs, key=lambda r: r["test_id"])
    random.Random(seed).shuffle(recs)
    out = Path(out_dir, f"sheet_{Path(run_dir).name}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    cases = Path(out_dir, "cases", Path(run_dir).name)
    cases.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["test_id", "smell", "case_file", "tsdetect_after", "jnose_after"]
                   + [f"present_{w}_{l}" for l in LABELLERS for w in ("before", "after")]
                   + ["adjudicated_before", "adjudicated_after"])
        for r in recs[:n]:
            rep, prop = r["reports"][-1], r["proposals"][-1]
            case = cases / (r["test_id"].replace(":", "_").replace("#", "_") + ".txt")
            case.write_text(f"// ORIGINAL\n{prop['original']}\n\n// REFACTORED\n{prop['refactored']}\n", encoding="utf-8")
            for s in r["finding"]["smells"]:
                w.writerow([r["test_id"], s, str(case), int(s in rep.get("smells_after", [])),
                            "" if rep.get("smells_after_jnose") is None else int(s in rep["smells_after_jnose"])]
                           + [""] * (2 * len(LABELLERS) + 2))
    return out


def score(sheet: str) -> dict:
    rows = [r for r in csv.DictReader(open(sheet, encoding="utf-8")) if all(
        r[f"present_{w}_{l}"] in ("0", "1") for l in LABELLERS for w in ("before", "after"))]
    if not rows:
        raise SystemExit("no fully labelled rows yet")

    def adj(r, w):
        a, b = (r[f"present_{w}_{l}"] for l in LABELLERS)
        return int(a) if a == b else int(r[f"adjudicated_{w}"] or a)
    after = [adj(r, "after") for r in rows]
    before = [adj(r, "before") for r in rows]
    present = [i for i, b in enumerate(before) if b]
    res = {"rows": len(rows),
           "kappa_labellers_before": cohen_kappa(*[[r[f"present_before_{l}"] for r in rows] for l in LABELLERS]),
           "kappa_labellers_after": cohen_kappa(*[[r[f"present_after_{l}"] for r in rows] for l in LABELLERS]),
           "kappa_tsdetect_vs_human_after": cohen_kappa([int(r["tsdetect_after"]) for r in rows], after),
           "smell_reduction_manual": round(100 * sum(1 for i in present if not after[i]) / len(present), 1)
           if present else None, "smells_present_before": len(present)}
    jn = [(int(r["jnose_after"]), a) for r, a in zip(rows, after) if r["jnose_after"] in ("0", "1")]
    res["kappa_jnose_vs_human_after"] = cohen_kappa([x for x, _ in jn], [y for _, y in jn]) if jn else None
    Path(sheet).with_name(Path(sheet).stem + "_score.json").write_text(json.dumps(res, indent=1))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("run_dir")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--out", default="results/E4/manual")
    c = sub.add_parser("score")
    c.add_argument("sheet")
    a = ap.parse_args()
    print(sample(a.run_dir, a.n, a.seed, a.out) if a.cmd == "sample" else json.dumps(score(a.sheet), indent=1))


if __name__ == "__main__":
    main()
