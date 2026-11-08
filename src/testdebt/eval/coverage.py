"""Post-hoc JaCoCo check: does each ACCEPTED refactoring keep the main-code lines the original test covered?

Not part of the agent loop (the kill-set gate is the safety check); a second, weaker oracle measured afterwards
on stored runs. The accepted code is rebuilt from logs/<run>/ exactly as the verifier patched it.

  python3 -m testdebt.eval.coverage logs/E3_s3_s1 [--limit N]
      -> results/coverage/<run>.jsonl (one line per accepted test, resumable) and <run>.json (summary)
"""
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

from ..tools.fastrun import FastRunner
from ..tools.jacoco import JacocoRunner, compare
from ..java_utils import extract_test_methods
from ..verify import missing_assert_imports, missing_param_imports, patch_source

OUT = Path("results/coverage")


def accepted_records(log_dir: Path) -> list[dict]:
    return [r for r in map(json.loads, (log_dir / "state.jsonl").read_text().splitlines()) if r["decision"] == "accepted"]


def last_imports(log_dir: Path, rec: dict) -> list[str]:
    """Imports of the accepted attempt: the last `verify` tool call in the test's trajectory."""
    t = rec["test"]
    with tarfile.open(log_dir / "trajectories.tar.gz") as tar:
        names = [n for n in tar.getnames() if n.endswith(f"{t['project']}_{t['class_name']}_{t['method']}.jsonl")]
        if not names:
            return []
        imports: list[str] = []
        for line in tar.extractfile(names[0]).read().decode().splitlines():
            e = json.loads(line)
            if e.get("tool") == "verify" and e.get("event") == "tool_call":
                inp = e.get("input") or {}
                inp = json.loads(inp) if isinstance(inp, str) else inp     # traces store tool input as JSON text
                imports = inp.get("imports", []) or []
        return imports


def check(jac: JacocoRunner, log_dir: Path, rec: dict) -> dict:
    t = rec["test"]
    src = Path(t["file"]).read_text(encoding="utf-8")
    block = rec["proposals"][-1]["refactored"]
    imports = last_imports(log_dir, rec)
    patched = patch_source(src, t["method"], block, imports + missing_assert_imports(src, block)
                           + missing_param_imports(src, block))
    out = {"test_id": rec["test_id"], "project": t["project"]}
    if patched is None:
        return {**out, "status": "unmeasured", "why": "could not patch"}
    new_tests = {m["name"] for m in extract_test_methods(block)}
    before = jac.covered_lines(t["module_dir"], t["project"], t["file"], src, {t["method"]})
    if not before["ok"]:
        return {**out, "status": "unmeasured", "why": "original: " + before["log"][-300:]}
    after = jac.covered_lines(t["module_dir"], t["project"], t["file"], patched, new_tests)
    if not after["ok"]:
        return {**out, "status": "unmeasured", "why": "refactored: " + after["log"][-300:]}
    cmp = compare(before["lines"], after["lines"])
    if not before["lines"]:     # original covers no main code: nothing to keep is not evidence (as PIT's empty kill-set)
        return {**out, "status": "empty", **cmp}
    return {**out, "status": "preserved" if cmp["preserved"] else "lost", **cmp}


def summarize(rows: list[dict]) -> dict:
    measured = [r for r in rows if r["status"] in ("preserved", "lost")]
    kept = [r for r in measured if r["status"] == "preserved"]
    by_proj = {}
    for p in sorted({r["project"] for r in rows}):
        m = [r for r in measured if r["project"] == p]
        by_proj[p] = {"accepted": sum(r["project"] == p for r in rows), "measured": len(m),
                      "preserved": sum(r["status"] == "preserved" for r in m)}
    return {"accepted": len(rows), "measured": len(measured),
            "empty": sum(r["status"] == "empty" for r in rows), "unmeasured": sum(r["status"] == "unmeasured" for r in rows), "preserved": len(kept),
            "preserved_rate": round(100 * len(kept) / len(measured), 1) if measured else None,
            "lines_lost_total": sum(r["lost"] for r in measured),
            "lines_lost_mean_when_lost": round(sum(r["lost"] for r in measured if r["lost"]) /
                                               max(1, len(measured) - len(kept)), 1),
            "by_project": by_proj}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("log_dirs", nargs="+", help="logs/<run id> (state.jsonl + trajectories.tar.gz)")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    cfg = json.loads(Path("configs/default.json").read_text())
    pins = json.loads(Path("data/pins.json").read_text())
    runner = FastRunner(mvn=cfg["paths"].get("mvn", "mvn"),
                        java_homes={p: v["java_home"] for p, v in pins.items() if v.get("java_home")})
    jac = JacocoRunner(runner)
    if not jac.available():
        raise SystemExit("JaCoCo jars missing in data/tools/jacoco (see src/testdebt/tools/jacoco.py)")
    OUT.mkdir(parents=True, exist_ok=True)
    for d in map(Path, a.log_dirs):
        rows_f = OUT / f"{d.name}.jsonl"
        done = {json.loads(l)["test_id"] for l in rows_f.read_text().splitlines()} if rows_f.exists() else set()
        recs = accepted_records(d)
        if a.limit:
            recs = recs[:a.limit]
        for i, rec in enumerate(recs, 1):
            if rec["test_id"] in done:
                continue
            row = check(jac, d, rec)
            print(f"[{d.name} {i}/{len(recs)}] {row['test_id']}: {row['status']}"
                  + (f" (lost {row['lost']} of {row['lines_before']} lines)" if row["status"] == "lost" else ""),
                  flush=True)
            with rows_f.open("a") as f:
                f.write(json.dumps(row) + "\n")
        rows = [json.loads(l) for l in rows_f.read_text().splitlines()]
        s = summarize(rows)
        (OUT / f"{d.name}.json").write_text(json.dumps(s, indent=2))
        print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
