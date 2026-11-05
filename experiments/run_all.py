"""Reproduce E1-E6 into results/<E>/ (per-seed json, runs.csv, summary.json = {config: {metric: [mean, sd]}}).

  SPLIT=test bash experiments/run_all.sh        # reported runs (frozen: clean tree)
  SPLIT=dev LIMIT=3 SEEDS="1" bash experiments/run_all.sh   # smoke test

E1 b0replay (UTRefactor's published outputs, no LLM)   E2 baselines: b0replay, b0, b1, single, b2
E3 full system s3 (G1+G2+G6)                            E4 detector agreement (no LLM, Hasan)
E5 ablations of s3: -G1, -G2, -G6                       E6 efficiency/reliability, computed from the E3 runs
A finished (experiment, config, seed) is skipped, so an interrupted run resumes.
"""
from __future__ import annotations

import csv
import json
import os
import statistics as st
import subprocess
import sys
from pathlib import Path

from experiments.run_experiment import run_system

SPLIT = os.environ.get("SPLIT", "test")
LIMIT = int(os.environ.get("LIMIT", "0"))
SEEDS = [int(s) for s in os.environ.get("SEEDS", "1 2 3").split()]
R = Path("results")
FULL = {"gap1", "gap2", "gap6"}
EXPS = {  # experiment -> {config name: (system, gaps, seeds-needed)}
    "E1": {"b0replay": ("b0replay", set(), "once")},
    "E2": {"b0replay": ("b0replay", set(), "once"), "b0": ("b0", set(), "all"), "b1": ("b1", set(), "all"),
           "single": ("single", set(), "all"), "b2": ("b2", {"gap1"}, "all")},
    "E3": {"s3": ("s3", FULL, "all")},
    "E5": {"s3-G1": ("s3", FULL - {"gap1"}, "all"), "s3-G2": ("s3", FULL - {"gap2"}, "all"),
           "s3-G6": ("s3", FULL - {"gap6"}, "all")},
}
E6_KEYS = ["tokens_total", "tokens_per_test", "latency_s_per_test", "tool_calls", "retries", "recovery_rate", "cost_usd"]


def summarize(exp: str, configs: dict) -> None:
    summary, rows = {}, []
    for name, runs in configs.items():
        rows += runs
        keys = [k for k, v in runs[0].items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        summary[name] = {k: [round(st.mean(v), 2), round(st.stdev(v), 2) if len(v) > 1 else 0.0] if v else [None, 0.0]
                         for k in keys for v in [[r[k] for r in runs if r.get(k) is not None]]}
    (R / exp / "summary.json").write_text(json.dumps(summary, indent=2))
    cols = sorted({k for r in rows for k in r})
    with (R / exp / "runs.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    frozen = SPLIT == "test"
    cfg = {"split": SPLIT, "limit": LIMIT, "frozen": frozen}
    done: dict[tuple, dict] = {}
    for exp, configs in EXPS.items():
        (R / exp).mkdir(parents=True, exist_ok=True)
        out = {}
        for name, (system, gaps, need) in configs.items():
            for seed in (SEEDS[:1] if need == "once" else SEEDS):
                f = R / exp / f"{name}_s{seed}.json"
                if (system, tuple(sorted(gaps)), seed) in done:   # same run already made in another experiment
                    m = done[(system, tuple(sorted(gaps)), seed)]
                elif f.exists():
                    m = json.loads(f.read_text())
                else:
                    m = run_system({**cfg, "system": system}, gaps, seed, Path("runs", f"{exp}_{name}_s{seed}"))
                f.write_text(json.dumps(m, indent=2))
                done[(system, tuple(sorted(gaps)), seed)] = m
                out.setdefault(name, []).append(m)
        summarize(exp, out)
        if exp == "E3":
            e6 = {"s3": [{k: r.get(k) for k in E6_KEYS} for r in out["s3"]]}
            (R / "E6").mkdir(exist_ok=True)
            summarize("E6", e6)
    subprocess.run([sys.executable, "-m", "testdebt.team.hasan.agreement", "--split", "all"],
                   check=True)  # E4 is on all 484 tests, no LLM


if __name__ == "__main__":
    main()
