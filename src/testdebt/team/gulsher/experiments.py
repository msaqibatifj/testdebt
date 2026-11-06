"""E1-E6 from one entry point. Every run is a normal `testdebt.cli` run with a fixed run id, so it is resumable.

  python3 -m testdebt.team.gulsher.experiments run E3 --frozen        # test split, seeds from E3.json
  python3 -m testdebt.team.gulsher.experiments run E3 --dev --limit 5 # dry run on the dev split, seed 1
  python3 -m testdebt.team.gulsher.experiments summarize E3           # results/E3/{runs.csv,summary.json,table.tex}
  python3 -m testdebt.team.gulsher.experiments summarize E4           # gap-wise tests from E1-E3 runs
  python3 -m testdebt.team.gulsher.experiments summarize E6           # cost, latency, calls, reliability

Run ids: <E>_<config>_s<seed> (dev runs: dev_<E>_<config>_s<seed>). E4 and E6 run nothing: they are computed
from the saved E1, E2, E3 (and E5) runs. Each summarize copies report.json and config.json of the runs it used
into results/<E>/runs/, because runs/ is not committed.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from ...eval import metrics
from ..hasan.stats import bootstrap_ci, holm, mcnemar_exact, mean_sd, wilcoxon

CONFIGS = Path(__file__).parent / "experiments"
TABLE = [("accepted_rate", "Accepted %"), ("pass_rate", "Passes %"), ("smell_reduction_tsdetect", "Red. i %"),
         ("smell_reduction_strict", "Red. ii %"), ("accepted_losing_mutants_rate", "Lose mut. %"),
         ("accepted_safe_rate", "Acc.+safe %"), ("tokens_per_test", "Tok/test")]


def load(exp: str) -> dict:
    return json.loads((CONFIGS / f"{exp}.json").read_text())


def run_ids(exp: str, dev: bool = False) -> dict[str, list[str]]:
    """{config name: [run id per seed]}"""
    cfg = load(exp)
    return {r["name"]: [f"{'dev_' if dev else ''}{exp}_{r['name']}_s{s}" for s in ([1] if dev else r["seeds"])]
            for r in cfg["runs"]}


def run(exp: str, dev: bool, frozen: bool, limit: int, only: str, seeds: list[int] | None = None) -> None:
    for r in load(exp)["runs"]:
        if only and r["name"] != only:
            continue
        for seed in ([1] if dev else [s for s in r["seeds"] if not seeds or s in seeds]):
            split = "dev" if dev else r["split"]
            rid = f"{'dev_' if dev else ''}{exp}_{r['name']}_s{seed}"
            cmd = [sys.executable, "-m", "testdebt.cli", "--run-id", rid, "--split", split, "--seed", str(seed), *r["args"]]
            cmd += ["--frozen"] if frozen else []
            lim = limit or r.get("limit", 0)
            cmd += ["--limit", str(lim)] if lim else []
            print("$", " ".join(cmd[1:]), flush=True)
            if subprocess.run(cmd).returncode:
                raise SystemExit(f"{rid} failed; fix and re-run the same command (it resumes)")


def _copy(rid: str, out: Path) -> None:
    """report/config -> results/<E>/runs/<rid>/; state + compressed trajectories -> logs/<rid>/ (runs/ is not committed)."""
    for f in ("report.json", "config.json"):
        if Path("runs", rid, f).exists():
            (out / "runs" / rid).mkdir(parents=True, exist_ok=True)
            shutil.copy(Path("runs", rid, f), out / "runs" / rid / f)
    src, log = Path("runs", rid), Path("logs", rid)
    if (src / "state.jsonl").exists():
        log.mkdir(parents=True, exist_ok=True)
        for f in ("config.json", "report.json", "state.jsonl"):
            if (src / f).exists():
                shutil.copy(src / f, log / f)
        if (src / "trajectories").is_dir():
            shutil.make_archive(str(log / "trajectories"), "gztar", src, "trajectories")


def _tex(path: Path, header: list[str], rows: list[list], caption_note: str = "") -> None:
    """booktabs tabular; cells: None -> --, (mean, sd) -> 'm $\\pm$ sd' (sd omitted when 0), numbers as %g."""
    def cell(v):
        if v is None or (isinstance(v, (tuple, list)) and v[0] is None):
            return "--"
        if isinstance(v, (tuple, list)):
            return f"{v[0]:g} $\\pm$ {v[1]:g}" if v[1] else f"{v[0]:g}"
        return f"{v:g}" if isinstance(v, (int, float)) else str(v).replace("_", "\\_").replace("%", "\\%")
    lines = ["\\begin{tabular}{l" + "r" * (len(header) - 1) + "}", "\\toprule",
             " & ".join(h.replace("%", "\\%") for h in header) + " \\\\", "\\midrule"]
    lines += [" & ".join(cell(c) for c in r) + " \\\\" for r in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines + ["\\bottomrule", "\\end{tabular}"]) + "\n")


def summarize(exp: str, dev: bool) -> dict:
    out = Path("results", ("dev/" if dev else "") + exp)
    rows, summary = [], {}
    for name, rids in run_ids(exp, dev).items():
        reps = []
        for seed, rid in enumerate(rids, 1):
            f = Path("runs", rid, "report.json")
            if not f.exists():
                print(f"missing {rid} (not run yet)")
                continue
            o = json.loads(f.read_text())["overall"]
            reps.append(o)
            rows.append({"config": name, "run": rid, **{k: o.get(k) for k, _ in TABLE},
                         "tests": o["tests"], "errors": o.get("errors"), "smell_reduction_accepted": o.get("smell_reduction_accepted")})
            _copy(rid, out)
        if reps:
            summary[name] = {"seeds": len(reps), **{k: mean_sd([o.get(k) for o in reps]) for k, _ in TABLE}}
    if not rows:
        raise SystemExit(f"no runs of {exp} found")
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    cell = lambda v: "--" if v[0] is None else (f"{v[0]:g} $\\pm$ {v[1]:g}" if v[1] else f"{v[0]:g}")
    tex = ["\\begin{tabular}{l" + "r" * len(TABLE) + "}", "\\toprule",
           "System & " + " & ".join(h.replace("%", "\\%") for _, h in TABLE) + " \\\\", "\\midrule"]
    tex += [f"{n} & " + " & ".join(cell(s[k]) for k, _ in TABLE) + " \\\\" for n, s in summary.items()]
    (out / "table.tex").write_text("\n".join(tex + ["\\bottomrule", "\\end{tabular}"]) + "\n")
    if exp == "E5" and not dev:
        _e5_delta(summary, out)
    if exp == "E2" and not dev:
        _e2_vs_paper(out)
    print(json.dumps(summary, indent=1))
    return summary


def _e5_delta(summary: dict, out: Path) -> None:
    """Change of each ablation from the full system (E3), mean over seeds; positive = higher without the component."""
    f = Path("results/E3/summary.json")
    if not f.exists():
        return
    full = json.loads(f.read_text()).get("s3", {})
    rows, js = [["full (E3)", *[full.get(k) for k, _ in TABLE]]], {}
    for name, s in summary.items():
        d = {k: (round(s[k][0] - full[k][0], 2) if s.get(k) and full.get(k) and s[k][0] is not None
                 and full[k][0] is not None else None) for k, _ in TABLE}
        js[name] = d
        rows.append([f"$\\Delta$ {name}", *[d[k] for k, _ in TABLE]])
    (out / "delta.json").write_text(json.dumps(js, indent=1))
    _tex(out / "delta.tex", ["Config", *[h for _, h in TABLE]], rows)


def _e2_vs_paper(out: Path) -> None:
    """Per-project rule-i smell reduction: paper-reported [1] vs reproduced (b0replay = published outputs through our
    verifier, E1; b0 = [1]'s method with our model, E2). Every row carries its source label."""
    def by_proj(rids):
        vals = defaultdict(list)
        for rid in rids:
            f = Path("runs", rid, "report.json")
            if f.exists():
                for p, s in json.loads(f.read_text())["by_project"].items():
                    vals[p].append(s.get("smell_reduction_tsdetect"))
        return {p: mean_sd(v) for p, v in vals.items()}
    replay = by_proj(run_ids("E1").get("b0replay", []))
    b0 = by_proj(run_ids("E2").get("b0", []))
    rows, js = [], []
    for p, paper in metrics.PAPER_REDUCTION.items():
        r = {"project": p, "paper_reported": paper, "b0replay_reproduced": replay.get(p), "b0_reproduced": b0.get(p)}
        js.append(r)
        rows.append([p, paper, replay.get(p), b0.get(p)])
    (out / "vs_paper.json").write_text(json.dumps({"metric": "smell_reduction_tsdetect (rule i, %)", "rows": js}, indent=1))
    _tex(out / "vs_paper.tex", ["Project", "[1] paper-reported", "b0replay (reproduced)", "b0 (reproduced)"], rows)


# ---- per-test flags (same definitions as eval/metrics.py) ----
def _flags(r: dict) -> dict:
    f = r["reports"][-1] if r["reports"] else {}
    left = set(r["finding"]["smells"]) & metrics._after_strict(f)
    acc = r["decision"] == "accepted"
    return {"accepted": acc, "safe": acc and f.get("killset_preserved") is True and not left,
            "lost": acc and f.get("killset_preserved") is False, "tokens": r["tokens"],
            "all_gone_strict": bool(f.get("sane")) and not left}


def _per_test(rid: str) -> dict[str, dict]:
    p = Path("runs", rid, "state.jsonl")
    return {r["test_id"]: _flags(r) for r in metrics.load(p) if r["decision"] != "skipped"} if p.exists() else {}


def _paired(a_rids: list[str], b_rids: list[str], flag: str) -> dict:
    """Pairs (test, seed) present in both systems; pooled over seeds."""
    xa, xb, ta, tb = [], [], [], []
    for ra, rb in zip(a_rids, b_rids):
        A, B = _per_test(ra), _per_test(rb)
        for t in sorted(set(A) & set(B)):
            xa.append(A[t][flag]); xb.append(B[t][flag]); ta.append(A[t]["tokens"]); tb.append(B[t]["tokens"])
    if not xa:
        return {}
    return {"pairs": len(xa), f"{flag}_a_pct": round(100 * sum(xa) / len(xa), 1),
            f"{flag}_b_pct": round(100 * sum(xb) / len(xb), 1), "mcnemar": mcnemar_exact(xa, xb),
            "diff_ci95_pct": [round(100 * v, 1) for v in bootstrap_ci([x - y for x, y in zip(xa, xb)], n=10000)],
            "tokens_wilcoxon": wilcoxon(ta, tb)}


def summarize_e4() -> dict:
    ids = {**{f"E1/{k}": v for k, v in run_ids("E1").items()}, **{f"E2/{k}": v for k, v in run_ids("E2").items()},
           **{f"E3/{k}": v for k, v in run_ids("E3").items()},
           **{f"E5/{k}": v for k, v in run_ids("E5").items()}}
    out = Path("results/E4")
    out.mkdir(parents=True, exist_ok=True)
    # G1: how often an ACCEPTED refactoring loses a mutant, per system (pooled over seeds, Wilson 95% CI)
    g1 = []
    for name, rids in ids.items():
        recs = [r for rid in rids if Path("runs", rid, "state.jsonl").exists()
                for r in metrics.load(Path("runs", rid, "state.jsonl"))]
        if recs:
            o = metrics.summarize(recs)
            g1.append({"system": name, "accepted": o["accepted"], "killset_checked": o["killset_checked"],
                       "lost": o["accepted_losing_mutants"], "lost_pct": o["accepted_losing_mutants_rate"],
                       "ci95": o["accepted_losing_mutants_ci95"], "unknown": o["killset_unknown"]})
    s3, b1, b0 = ids.get("E3/s3", []), ids.get("E2/b1", []), ids.get("E2/b0", [])
    b2, g1off = ids.get("E2/b2", []), ids.get("E5/s3-G1", [])
    tests = {"G1: s3 vs s3-G1 (accepted and losing a mutant)": _paired(s3, g1off, "lost"),
             "G1: s3 vs b0 (accepted and losing a mutant)": _paired(s3, b0, "lost"),
             "G2: s3 vs b0 (all targeted smells gone, rule ii)": _paired(s3, b0, "all_gone_strict"),
             "G6: s3 vs b1 (accepted and safe)": _paired(s3, b1, "safe"),
             "G6: s3 vs b2 (accepted and safe)": _paired(s3, b2, "safe")}
    have = [k for k, v in tests.items() if v]
    for k, p in zip(have, holm([tests[k]["mcnemar"]["p"] for k in have])):
        tests[k]["p_holm"] = p
    agreement = Path("results/E4/g2_agreement.json")
    res = {"g1_killset_loss": g1, "paired_tests": tests, "subsets": _e4_subsets(ids),
           "g2_detector_agreement": json.loads(agreement.read_text())["overall"] if agreement.exists() else None}
    for name, rows in (("g1.csv", g1),):
        if rows:
            with open(out / name, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
    (out / "summary.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return res


def _states(rids: list[str]) -> list[list[dict]]:
    return [[r for r in metrics.load(Path("runs", rid, "state.jsonl")) if r["decision"] != "skipped"]
            for rid in rids if Path("runs", rid, "state.jsonl").exists()]


def _e4_subsets(ids: dict) -> dict:
    """Hypothesis subsets. H1: tests with a non-empty baseline kill-set (s3 vs s3-G1).
    H2: per smell, rule i vs rule ii removal for s3 (largest gap expected where the detectors disagree).
    H3: multi-smell tests, and 'hard' tests = rejected by the one-pass reproduction b0 (seed 1); s3 vs b1 vs b2."""
    def rate(seeds, keep, flag):
        vals = []
        for recs in seeds:
            sel = [r for r in recs if keep(r)]
            if sel:
                vals.append(100 * sum(_flags(r)[flag] for r in sel) / len(sel))
        n = len([r for r in seeds[0] if keep(r)]) if seeds else 0
        return {"n": n, "pct": mean_sd(vals)}
    s3, g1off = _states(ids.get("E3/s3", [])), _states(ids.get("E5/s3-G1", []))
    known = lambda r: any((p.get("mutants_killed_before") or 0) > 0 or p.get("killset_preserved") is not None
                          for p in r["reports"])   # some attempt reached PIT with a non-empty baseline kill-set
    h1 = {"s3": rate(s3, known, "lost"), "s3-G1": rate(g1off, known, "lost"),
          "s3_accepted": rate(s3, known, "accepted"), "s3-G1_accepted": rate(g1off, known, "accepted")}
    h2 = {}
    for recs in s3[:1]:
        for r in recs:
            f = r["reports"][-1] if r["reports"] else {}
            if not f.get("sane") or f.get("smells_after_jnose") is None:
                continue
            for sm in r["finding"]["smells"]:
                d = h2.setdefault(sm, {"targeted": 0, "gone_i": 0, "gone_ii": 0})
                d["targeted"] += 1
                d["gone_i"] += sm not in set(f.get("smells_after", []))
                d["gone_ii"] += sm not in metrics._after_strict(f)
    for d in h2.values():
        d["rule_i_pct"], d["rule_ii_pct"] = (round(100 * d["gone_i"] / d["targeted"], 1),
                                             round(100 * d["gone_ii"] / d["targeted"], 1))
    b0 = _states(ids.get("E2/b0", [])[:1])
    hard_ids = {r["test_id"] for r in b0[0] if r["decision"] != "accepted"} if b0 else set()
    multi = lambda r: len(r["finding"]["smells"]) > 1
    hard = lambda r: r["test_id"] in hard_ids
    h3 = {}
    for name, key in (("s3", "E3/s3"), ("b1", "E2/b1"), ("b2", "E2/b2")):
        st = _states(ids.get(key, []))
        h3[name] = {"multi_smell": rate(st, multi, "safe"), "hard": rate(st, hard, "safe"),
                    "tokens_per_test": mean_sd([sum(r["tokens"] for r in recs) / max(len(recs), 1) for recs in st])}
    return {"H1_nonempty_killset": h1, "H2_per_smell_rule_i_vs_ii": h2, "H3_subsets_accepted_safe": h3}


def summarize_e6() -> dict:
    """Cost, latency, calls and reliability per configuration (mean +- sd over seeds), from states and trajectories."""
    out, res = Path("results/E6"), {}
    for exp in ("E1", "E2", "E3", "E5"):
        for name, rids in run_ids(exp).items():
            per_seed = []
            for rid in rids:
                d = Path("runs", rid)
                if not (d / "state.jsonl").exists():
                    continue
                recs = [r for r in metrics.load(d / "state.jsonl") if r["decision"] != "skipped"]
                n = len(recs) or 1
                calls, tools, llm_s, ptok, ctok = 0, defaultdict(int), 0.0, 0, 0
                for t in (d / "trajectories").glob("*.jsonl"):
                    for e in map(json.loads, t.read_text().splitlines()):
                        if e["event"] == "llm_call":
                            calls += 1
                            llm_s += e.get("latency_s") or 0
                            ptok += e.get("prompt_tokens") or 0
                            ctok += e.get("completion_tokens") or 0
                        elif e["event"] == "tool_call":
                            tools[e.get("tool", "?")] += 1
                tim = defaultdict(float)
                for r in recs:
                    for rep in r["reports"]:
                        for k, v in (rep.get("timings") or {}).items():
                            tim[k] += v
                acc = sum(r["decision"] == "accepted" for r in recs)
                retried = [r for r in recs if len(r["proposals"]) > 1]
                per_seed.append({"tokens_per_test": sum(r["tokens"] for r in recs) / n,
                                 "prompt_tokens_per_test": ptok / n, "completion_tokens_per_test": ctok / n,
                                 "tokens_per_accepted": sum(r["tokens"] for r in recs) / acc if acc else None,
                                 "llm_calls_per_test": calls / n, "tool_calls_per_test": sum(tools.values()) / n,
                                 "wall_s_per_test": sum(r["wall_time_s"] for r in recs) / n,
                                 "llm_s_per_test": llm_s / n, "compile_run_s_per_test": tim["compile_run"] / n,
                                 "pit_s_per_test": tim["pit"] / n,
                                 "error_pct": 100 * sum(r["decision"] == "error" for r in recs) / n,
                                 "escalated_pct": 100 * sum(r["decision"] == "escalated" for r in recs) / n,
                                 "retried_pct": 100 * len(retried) / n,
                                 "recovery_pct": (100 * sum(r["decision"] == "accepted" for r in retried) / len(retried)
                                                  if retried else None),
                                 "cost_usd": 0.0})   # Cerebras free tier; token counts above are the cost proxy
            if per_seed:
                res[f"{exp}/{name}"] = {"seeds": len(per_seed),
                                        **{k: mean_sd([s[k] for s in per_seed]) for k in per_seed[0]}}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(res, indent=1))
    cols = [("tokens_per_test", "Tok/test"), ("prompt_tokens_per_test", "Prompt"), ("completion_tokens_per_test", "Compl."),
            ("llm_calls_per_test", "LLM calls"), ("tool_calls_per_test", "Tool calls"), ("wall_s_per_test", "s/test"),
            ("pit_s_per_test", "PIT s"), ("retried_pct", "Retried %"), ("recovery_pct", "Recovery %"), ("cost_usd", "Cost \\$")]
    if res:
        _tex(out / "table.tex", ["Config", *[h for _, h in cols]], [[n, *[s.get(k) for k, _ in cols]] for n, s in res.items()])
    print(json.dumps(res, indent=1))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("exp", choices=["E1", "E2", "E3", "E5", "ES"])
    r.add_argument("--dev", action="store_true", help="dev split, seed 1 (for trying the pipeline, not results)")
    r.add_argument("--frozen", action="store_true")
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--only", default="", help="one config name, e.g. b1")
    r.add_argument("--seeds", default="", help="only these of the config's seeds, e.g. 1 or 2,3 (run by priority)")
    s = sub.add_parser("summarize")
    s.add_argument("exp", choices=["E1", "E2", "E3", "E4", "E5", "E6", "ES"])
    s.add_argument("--dev", action="store_true")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.exp, a.dev, a.frozen, a.limit, a.only, [int(s) for s in a.seeds.split(",") if s])
    elif a.exp == "E4":
        summarize_e4()
    elif a.exp == "E6":
        summarize_e6()
    else:
        summarize(a.exp, a.dev)


if __name__ == "__main__":
    main()
