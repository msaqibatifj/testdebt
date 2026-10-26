"""Gap-resolution table (guidelines 4.4) from results/ only, so the README and the paper print the same numbers.

  python3 -m testdebt.team.hasan.gap_table [--readme README.md]
      -> results/gap_table.md, results/gap_table.tex; with --readme, the block between
         <!-- gap-table --> and <!-- /gap-table --> in that file is replaced by gap_table.md

Numbers are mean +- sd over seeds from results/E2, E3 summary.json. "Base paper" cells say where the number comes
from: reproduced by us (b0 = UTRefactor's method run by us, b0replay = its published outputs through our verifier)
or reported in [1]. The Addressed? column is a judgement, written by hand in results/gap_verdicts.json
({"G1": "Partially", ...}); it is never computed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ...eval.metrics import PAPER_REDUCTION

GAPS = [  # gap, component, metric label, summary key, lower is better
    ("G1", "Kill-set gate (`killset_gate.py`)", "Accepted outputs losing a mutant (%)", "accepted_losing_mutants_rate"),
    ("G2", "Consensus detector, tsDetect + JNose (`consensus.py`)", "Smell reduction, rule ii (%)", "smell_reduction_strict"),
    ("G6", "Adaptive Supervisor + memory (`agents/supervisor.py`)", "Accepted and safe (%)", "accepted_safe_rate"),
]


def _load(results: Path, exp: str) -> dict:
    f = results / exp / "summary.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _cell(summary: dict, config: str, key: str) -> str | None:
    v = summary.get(config, {}).get(key)
    if not v or v[0] is None:
        return None
    return f"{v[0]:g} ± {v[1]:g}" if v[1] else f"{v[0]:g}"


def rows(results: str | Path = "results") -> list[list[str]]:
    results = Path(results)
    e2, e3 = _load(results, "E2"), _load(results, "E3")
    verdicts_f = results / "gap_verdicts.json"
    verdicts = json.loads(verdicts_f.read_text()) if verdicts_f.exists() else {}
    out = []
    for gap, comp, label, key in GAPS:
        base = [f"{c} ({src})" for c, src in ((_cell(e2, "b0", key), "b0, reproduced"),
                                               (_cell(e2, "b0replay", key), "b0replay, reproduced")) if c]
        if gap == "G2":   # [1] reports rule i only; quoted so the reader sees it is not our measurement
            base.append("rule i: " + " / ".join(f"{v:g}" for v in PAPER_REDUCTION.values()) + " (reported in [1])")
        out.append([gap, comp, label, "; ".join(base) or "pending", _cell(e3, "s3", key) or "pending",
                    verdicts.get(gap, "TBD")])
    return out


HEAD = ["Gap", "Method / component", "Metric", "Base paper result", "Our result (S3)", "Addressed?"]


def markdown(rs: list[list[str]]) -> str:
    lines = ["| " + " | ".join(HEAD) + " |", "|" + "---|" * len(HEAD)]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rs]) + "\n"


def latex(rs: list[list[str]]) -> str:
    esc = lambda s: re.sub(r"`([^`]*)`", r"\\texttt{\1}", s).replace("%", "\\%").replace("±", "$\\pm$").replace("_", "\\_")
    body = [" & ".join(esc(c) for c in r) + " \\\\" for r in rs]
    return "\n".join(["\\begin{tabular}{p{0.6cm}p{2.6cm}p{2.2cm}p{3.2cm}p{1.6cm}p{1.4cm}}", "\\toprule",
                      " & ".join(HEAD) + " \\\\", "\\midrule", *body, "\\bottomrule", "\\end{tabular}"]) + "\n"


def replace_block(text: str, table: str) -> str:
    start, end = "<!-- gap-table -->", "<!-- /gap-table -->"
    if start not in text or end not in text:
        raise SystemExit(f"README has no {start} ... {end} block to fill")
    return text[:text.index(start) + len(start)] + "\n" + table + text[text.index(end):]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--readme", default="")
    a = ap.parse_args()
    rs = rows(a.results)
    md = markdown(rs)
    Path(a.results, "gap_table.md").write_text(md, encoding="utf-8")
    Path(a.results, "gap_table.tex").write_text(latex(rs), encoding="utf-8")
    if a.readme:
        p = Path(a.readme)
        p.write_text(replace_block(p.read_text(encoding="utf-8"), md), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
