"""Run one system over an evaluation set and write runs/<run_id>/{config.json,state.jsonl,report.json,report.md}.

  python3 -m testdebt.cli --system b0replay --eval data/eval_set.jsonl      # no LLM: paper's own outputs
  python3 -m testdebt.cli --system b0 --eval data/eval_set.jsonl --limit 10
  python3 -m testdebt.cli --system b1 --eval data/eval_subset150.jsonl --seed 2 --pit
  python3 -m testdebt.cli --system b0 --eval data/eval_set.jsonl --limit 20 --skip-verify   # LLM-only pilot
  python3 -m testdebt.cli --system s3 --eval data/eval_set.jsonl --project commons-cli --limit 10
  python3 -m testdebt.cli --report runs/<run_id>                                             # metrics only
  python3 -m testdebt.cli --system b1 --split dev --seed 1                                   # tuning: dev split only
  python3 -m testdebt.cli --system s3 --split test --frozen --seed 1                          # reported runs: clean tree

A run is resumable: re-running with the same --run-id skips tests already in state.jsonl.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from .contracts import DebtFinding, TestRef
from .pipeline import Config, Pipeline
from .prompts import KnowledgeBase
from .tools.fastrun import FastRunner
from .tools.maven import MavenRunner
from .tools.pit import PitRunner
from .tools.tsdetect import TsDetect
from .verify import Verifier
from .data import splits
from .eval import metrics


def load_config(path: str | None) -> dict:
    return json.loads(Path(path).read_text()) if path and Path(path).exists() else {}


def write_report(run_dir: Path) -> dict:
    recs = metrics.load(run_dir / "state.jsonl")
    rep = metrics.report(recs)
    (run_dir / "report.json").write_text(json.dumps(rep, indent=2))
    (run_dir / "report.md").write_text(metrics.markdown(rep, f"Run {run_dir.name}"))
    decisions = [{"test": r["test_id"], "decision": r["decision"], "reason": r["reason"], "retries": r["retries"],
                  "tokens": r["tokens"], "smells_before": r["finding"]["smells"],
                  "smells_after": (r["reports"][-1]["smells_after"] if r["reports"] else None)} for r in recs]
    (run_dir / "decisions.json").write_text(json.dumps(decisions, indent=2))
    return rep


def git_state() -> tuple[str, bool]:
    """(HEAD commit, tracked files modified): recorded in config.json so every number names the code it came from."""
    git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return git("rev-parse", "HEAD"), bool(git("status", "--porcelain", "--untracked-files=no"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.json")
    ap.add_argument("--system", choices=["single", "b0replay", "b0", "b1", "b2", "s3"])
    ap.add_argument("--eval", default="data/eval_set.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--project", default="", help="only tests of this project, e.g. commons-cli")
    ap.add_argument("--split", choices=["dev", "test", "rest", "all"], help="only tests in data/splits/<split>.jsonl")
    ap.add_argument("--frozen", action="store_true", help="required for --split test: clean tree, results count")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--run-id", default="")
    ap.add_argument("--skip-verify", action="store_true", help="no Maven: static checks + smells only")
    ap.add_argument("--pit", action="store_true", help="kill-set gate/measurement with PIT (slow)")
    ap.add_argument("--runner", choices=["fast", "maven"], default="fast",
                    help="fast: Maven once per module, then javac + JUnit launcher per test (default)")
    ap.add_argument("--policy", choices=["adaptive", "fixed"], help="s3: fixed = B1's retry script (-G6 ablation)")
    ap.add_argument("--memory", choices=["on", "off"], help="s3: off = no memory of failed approaches (ablation)")
    ap.add_argument("--report", default="", help="only (re)compute metrics for an existing run dir")
    a = ap.parse_args()

    if a.report:
        print(json.dumps(write_report(Path(a.report))["overall"], indent=2))
        return

    commit, dirty = git_state()
    if a.split == "test" and not a.frozen:
        ap.error("--split test is for final runs only: pass --frozen (tune on --split dev)")
    if a.frozen and dirty:
        ap.error("--frozen needs a clean tree (commit first) so config.json names the code that ran")

    c = load_config(a.config)
    cfg = Config(**{k: v for k, v in c.get("pipeline", {}).items() if k in Config.__dataclass_fields__})
    if a.system:
        cfg.system = a.system
    if a.seed is not None:
        cfg.seed = a.seed
    if a.policy:
        cfg.policy = a.policy
    if a.memory:
        cfg.memory = a.memory == "on"
    paths = c.get("paths", {})
    run_id = a.run_id or f"{cfg.system}_s{cfg.seed}_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = Path("runs", run_id)

    from .llm_client import LLMClient   # imported late so --report works without requests/keys
    llm = LLMClient(max_requests_per_min=c.get("llm", {}).get("max_requests_per_min", 5))
    tsd = TsDetect(paths.get("tsdetect_jar", "data/utrefactor/detection/v3/TestSmellDetector.jar"))
    if not tsd.available():
        print("WARNING: tsDetect jar not found -> smells-after uses the rules approximation (not comparable to [1])")
    pins = json.loads(Path(paths.get("pins", "data/pins.json")).read_text()) if Path(paths.get("pins", "data/pins.json")).exists() else {}
    java_homes = {p: v["java_home"] for p, v in pins.items() if v.get("java_home")}
    runner_cls = MavenRunner if a.runner == "maven" else FastRunner
    maven = None if a.skip_verify else runner_cls(mvn=paths.get("mvn", "mvn"), java_homes=java_homes)
    pit = PitRunner(mvn=paths.get("mvn", "mvn"), env=maven.env) if a.pit and maven else None
    verifier = Verifier(maven, tsd, pit, run_tests=not a.skip_verify)
    kb = KnowledgeBase(paths.get("utrefactor", "data/utrefactor"))
    if cfg.system == "s3":
        from .agents import Supervisor
        pipe = Supervisor(llm, verifier, kb, cfg, run_dir, max_attempts=1 + cfg.max_retries)
    elif cfg.system == "b2":
        from .agents import B2Agent
        pipe = B2Agent(llm, verifier, kb, cfg, run_dir)
    else:
        pipe = Pipeline(llm, verifier, kb, cfg, run_dir)
    (run_dir / "config.json").write_text(json.dumps({"config": asdict(cfg), "model": llm.model, "eval": a.eval,
                                                     "skip_verify": a.skip_verify, "pit": a.pit, "split": a.split,
                                                     "frozen": a.frozen, "git_commit": commit, "git_dirty": dirty},
                                                    indent=2))

    rows = [json.loads(l) for l in Path(a.eval).read_text().splitlines() if l.strip()]
    if a.split:
        ids = splits.load(a.split)
        by_id = {splits.test_id(r): r for r in rows}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise SystemExit(f"{len(missing)} test(s) of split '{a.split}' are not in {a.eval} (e.g. {missing[0]}): "
                             "the eval set was built differently from the one the splits came from")
        rows = [by_id[i] for i in ids]
    if a.project:
        rows = [r for r in rows if r["project"] == a.project]
    rows = rows[:a.limit] if a.limit else rows
    done = pipe.done_ids()
    for i, r in enumerate(rows, 1):
        test = TestRef(r["project"], r["module_dir"], r["file"], r["class_name"], r["method"])
        if test.id in done:
            continue
        st = pipe.process(test, DebtFinding(test, r["smells"], detector="tsdetect[1]", all_smells=r["smells"]),
                          replay=r.get("utr_refactored"))
        print(f"[{i}/{len(rows)}] {test.id}: {st.decision} ({len(st.proposals)} attempt(s), "
              f"{sum(p.tokens for p in st.proposals) + st.plan_tokens} tok) {st.reason[:120]}")
    rep = write_report(run_dir)
    print(json.dumps(rep["overall"], indent=2))
    print(f"saved {run_dir}/report.md")


if __name__ == "__main__":
    main()
