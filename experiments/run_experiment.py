"""run_system(cfg, gaps, seed, trace_dir) -> flat metrics dict, on top of the existing `testdebt run` pipeline.

cfg:  {"system": "s3", "split": "dev", "limit": 0, "frozen": false, "skip_verify": false, "config": "configs/default.json"}
gaps: set of {"gap1" (PIT kill-set gate), "gap2" (tsDetect+JNose consensus), "gap6" (adaptive supervision + memory)}
trace_dir: runs/<run_id>; its name is the run id, so trajectories land in <trace_dir>/trajectories/.

  python -m experiments.run_experiment --system s3 --split dev --limit 5 --gaps gap1,gap2,gap6 --seed 1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from testdebt import cli


def _argv(cfg: dict, gaps: set, seed: int, run_id: str) -> list[str]:
    a = ["--system", cfg["system"], "--seed", str(seed), "--run-id", run_id,
         "--config", cfg.get("config", "configs/default.json")]
    if cfg.get("split"):
        a += ["--split", cfg["split"]]
    if cfg.get("limit"):
        a += ["--limit", str(cfg["limit"])]
    if cfg.get("frozen"):
        a.append("--frozen")
    if cfg.get("skip_verify"):
        a.append("--skip-verify")
    a += ["--gaps", ",".join(sorted(gaps)) or "none"]
    return a


def run_system(cfg: dict, gaps: set, seed: int, trace_dir: str | Path) -> dict:
    trace_dir = Path(trace_dir)
    if trace_dir.parent.name != "runs":
        raise ValueError("trace_dir must be runs/<run_id>")
    cli.main(_argv(cfg, set(gaps), seed, trace_dir.name))
    recs = [json.loads(l) for l in (trace_dir / "state.jsonl").read_text().splitlines() if l.strip()]
    rep = json.loads((trace_dir / "report.json").read_text())["overall"]
    meta = json.loads((trace_dir / "config.json").read_text())
    retried = [r for r in recs if r["retries"] > 0]
    tool_calls = sum(l.count('"event": "tool_call"') for f in (trace_dir / "trajectories").glob("*.jsonl")
                     for l in f.read_text(encoding="utf-8").splitlines())
    return {**rep, "system": cfg["system"], "gaps": ",".join(sorted(gaps)), "seed": seed,
            "tool_calls": tool_calls, "retries": sum(r["retries"] for r in recs),
            "recovery_rate": round(100 * sum(r["decision"] == "accepted" for r in retried) / len(retried), 1) if retried else None,
            "latency_s_per_test": round(rep["wall_time_s"] / max(rep["tests"], 1), 1),
            "cost_usd": 0.0,  # Cerebras free tier; prompt/completion split is not logged, only totals
            "model": meta["model"], "temperature": meta["config"]["temperature"],
            "prompt_hash": meta.get("prompt_hash"),
            "git_commit": meta["git_commit"], "git_dirty": meta["git_dirty"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", default="s3")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--frozen", action="store_true")
    ap.add_argument("--skip-verify", action="store_true")
    ap.add_argument("--gaps", default="gap1,gap2,gap6")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--run-id", default="")
    ap.add_argument("--out", default="", help="write the metrics dict here (json)")
    a = ap.parse_args()
    gaps = {g for g in a.gaps.split(",") if g}
    rid = a.run_id or f"{a.system}_{a.split}_{'-'.join(sorted(gaps)) or 'nogaps'}_s{a.seed}"
    m = run_system(vars(a), gaps, a.seed, Path("runs", rid))
    print(json.dumps(m, indent=2))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(m, indent=2))
