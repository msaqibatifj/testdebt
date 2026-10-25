"""Metrics over runs/<run>/state.jsonl (one record per test).

Smell reduction (rule i, tsDetect only, as in [1]): targeted smells that are gone after the FINAL attempt,
counted over every test (a test with no usable reply counts as nothing removed).
Rules ii (strict, tsDetect AND JNose) and iii (manual sample) need JNose / labels: reported as null until added.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

PAPER_REDUCTION = {"commons-cli": 86.0, "gson": 89.0, "jsoup": 91.0}   # Table 5 of [1], quoted in the proposal


def load(state_file: str | Path) -> list[dict]:
    """Last record per test: a resumed run appends a new record for each test that ended in 'error'."""
    recs = [json.loads(l) for l in Path(state_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    return list({r["test_id"]: r for r in recs}.values())


def _rate(k: int, n: int) -> float | None:
    return round(100 * k / n, 1) if n else None


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def summarize(recs: list[dict]) -> dict:
    recs = [r for r in recs if r["decision"] != "skipped"]
    n = len(recs)
    final = [r["reports"][-1] if r["reports"] else {} for r in recs]
    compiled = sum(1 for f in final if f.get("compiled") is True)
    passed = sum(1 for f in final if f.get("passed") is True)
    sane = sum(1 for f in final if f.get("sane"))
    accepted = sum(1 for r in recs if r["decision"] == "accepted")
    targeted = removed = 0
    for r, f in zip(recs, final):
        t = set(r["finding"]["smells"])
        targeted += len(t)
        if f.get("sane"):
            removed += len(t - set(f.get("smells_after", [])))
    ks = [f for r, f in zip(recs, final) if r["decision"] == "accepted" and f.get("killset_preserved") is not None]
    lost = sum(1 for f in ks if f["killset_preserved"] is False)
    tokens = sum(r["tokens"] for r in recs)
    safe = sum(1 for r, f in zip(recs, final) if r["decision"] == "accepted" and f.get("killset_preserved") is True
               and not (set(r["finding"]["smells"]) & set(f.get("smells_after", []))))
    # With --skip-verify nothing is compiled or run, so "accepted" only means "passed the static checks".
    # Report it as unverified instead of as an acceptance rate.
    verified = not any(r["decision"] == "accepted" and f.get("compiled") is None for r, f in zip(recs, final))
    return {
        "tests": n, "verified": verified, "errors": sum(1 for r in recs if r["decision"] == "error"),
        "accepted": accepted if verified else None, "accepted_rate": _rate(accepted, n) if verified else None,
        "accepted_unverified": None if verified else accepted,
        "static_ok_rate": _rate(sane, n),
        "compile_rate": _rate(compiled, n) if any(f.get("compiled") is not None for f in final) else None,
        "pass_rate": _rate(passed, n) if any(f.get("passed") is not None for f in final) else None,
        "smell_reduction_tsdetect": _rate(removed, targeted), "smells_targeted": targeted, "smells_removed": removed,
        "smell_reduction_strict": None, "smell_reduction_manual": None,
        "killset_checked": len(ks),
        "killset_unknown": sum(1 for r, f in zip(recs, final) if r["decision"] == "accepted"
                               and f.get("killset_preserved") is None and f.get("mutants_killed_before") == 0),
        "accepted_losing_mutants": lost,
        "accepted_losing_mutants_rate": _rate(lost, len(ks)), "accepted_losing_mutants_ci95": wilson(lost, len(ks)),
        "accepted_safe": safe if ks else None, "accepted_safe_rate": _rate(safe, n) if ks else None,
        "retried": sum(1 for r in recs if r["retries"] > 0),
        "tokens_total": tokens, "tokens_per_test": round(tokens / n) if n else 0,
        "tokens_per_accepted": round(tokens / accepted) if accepted and verified else None,
        "wall_time_s": round(sum(r["wall_time_s"] for r in recs), 1),
        "multi_smell_tests": sum(1 for r in recs if len(r["finding"]["smells"]) > 1),
    }


def per_smell(recs: list[dict]) -> dict:
    """{smell: {targeted, removed, removed_pct}} using the final attempt (rule i)."""
    out: dict = {}
    for r in recs:
        if r["decision"] == "skipped" or not r["reports"] or not r["reports"][-1].get("sane"):
            continue
        after = set(r["reports"][-1].get("smells_after", []))
        for s in r["finding"]["smells"]:
            d = out.setdefault(s, {"targeted": 0, "removed": 0})
            d["targeted"] += 1
            d["removed"] += s not in after
    for d in out.values():
        d["removed_pct"] = _rate(d["removed"], d["targeted"])
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["targeted"]))


def report(recs: list[dict]) -> dict:
    by_proj = defaultdict(list)
    for r in recs:
        by_proj[r["test"]["project"]].append(r)
    out = {"overall": summarize(recs), "by_project": {}, "by_smell": per_smell(recs)}
    for p, rs in sorted(by_proj.items()):
        s = summarize(rs)
        if p in PAPER_REDUCTION and s["smell_reduction_tsdetect"] is not None:
            s["paper_reduction"] = PAPER_REDUCTION[p]
            s["delta_vs_paper"] = round(s["smell_reduction_tsdetect"] - PAPER_REDUCTION[p], 1)
            s["within_5_points"] = abs(s["delta_vs_paper"]) <= 5
        out["by_project"][p] = s
    return out


def markdown(rep: dict, title: str) -> str:
    keys = ["tests", "accepted_rate", "compile_rate", "pass_rate", "smell_reduction_tsdetect",
            "accepted_losing_mutants_rate", "accepted_safe_rate", "tokens_per_test", "wall_time_s"]
    rows = [("overall", rep["overall"])] + list(rep["by_project"].items())
    lines = [f"# {title}", "", "| scope | " + " | ".join(keys) + " |", "|" + "---|" * (len(keys) + 1)]
    for name, s in rows:
        lines.append(f"| {name} | " + " | ".join("-" if s.get(k) is None else str(s.get(k)) for k in keys) + " |")
    for name, s in rep["by_project"].items():
        if "delta_vs_paper" in s:
            lines.append(f"\n{name}: reduction {s['smell_reduction_tsdetect']}% vs paper {s['paper_reduction']}% "
                         f"(delta {s['delta_vs_paper']}, within 5 points: {s['within_5_points']})")
    lines += ["", "| smell | targeted | removed | removed % |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['targeted']} | {v['removed']} | {v['removed_pct']} |" for k, v in rep.get("by_smell", {}).items()]
    return "\n".join(lines) + "\n"
