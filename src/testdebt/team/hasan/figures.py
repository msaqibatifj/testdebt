"""Paper figures from results/ (never from typed numbers): python3 -m testdebt.team.hasan.figures

  fig_systems.pdf    E1-E3: accepted-and-safe % and accepted-but-losing-a-mutant % per system (mean +- sd over seeds)
  fig_ablation.pdf   E3 full vs each E5 ablation: accepted-and-safe %
  fig_cost.pdf       tokens per test vs accepted-and-safe %, one dot per configuration
  fig_failures.pdf   failure categories of the final system (results/failures/E3_counts.json)
A figure whose inputs are missing is skipped with a message. Single-series charts: one hue, no legend.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, INK, INK2, GRID = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42, "font.family": "DejaVu Sans"})


def _read(p: str):
    f = Path(p)
    return json.loads(f.read_text()) if f.exists() else None


def _bars(ax, labels, means, sds, title, unit="%"):
    y = range(len(labels))
    err = [s or 0 for s in sds] if any(sds) else None      # no zero-width whiskers when there is no spread
    ax.barh(list(y), means, xerr=err, color=BLUE, height=0.55,
            error_kw={"ecolor": INK2, "elinewidth": 0.8, "capsize": 2})
    ax.set_yticks(list(y), labels)
    if not ax.yaxis_inverted():                             # panels sharing y would otherwise flip it back
        ax.invert_yaxis()
    ax.set_title(title, loc="right", fontsize=8, color=INK)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    top = max([m + (s or 0) for m, s in zip(means, sds)] + [1])
    ax.set_xlim(0, top * 1.18)
    for i, (m, s) in enumerate(zip(means, sds)):
        ax.text(m + (s or 0) + top * 0.02, i, f"{m:g}{unit}", va="center", fontsize=7, color=INK)


def _systems(out: Path, results: Path) -> str | None:
    rows = []
    for exp in ("E1", "E2", "E3"):
        for name, s in (_read(results / exp / "summary.json") or {}).items():
            if s["accepted_safe_rate"][0] is not None:
                rows.append((f"{name}", s["accepted_safe_rate"], s["accepted_losing_mutants_rate"]))
    if not rows:
        return None
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.8, 0.45 * len(rows) + 0.9), sharey=True)
    _bars(a, [r[0] for r in rows], [r[1][0] for r in rows], [r[1][1] for r in rows], "Accepted and safe (%)")
    _bars(b, [r[0] for r in rows], [r[2][0] or 0 for r in rows], [r[2][1] for r in rows],
          "Accepted but losing a mutant (%)")
    fig.tight_layout()
    fig.savefig(out / "fig_systems.pdf")
    return "fig_systems.pdf"


def _ablation(out: Path, results: Path) -> str | None:
    full, abl = _read(results / "E3/summary.json"), _read(results / "E5/summary.json")
    if not (full and abl):
        return None
    rows = [("s3 (full)", full["s3"]["accepted_safe_rate"])] + [(k, v["accepted_safe_rate"]) for k, v in abl.items()]
    fig, ax = plt.subplots(figsize=(3.4, 0.4 * len(rows) + 0.7))
    _bars(ax, [r[0] for r in rows], [r[1][0] or 0 for r in rows], [r[1][1] for r in rows], "Accepted and safe (%)")
    fig.tight_layout()
    fig.savefig(out / "fig_ablation.pdf")
    return "fig_ablation.pdf"


def _cost(out: Path, results: Path) -> str | None:
    pts = []
    for exp in ("E1", "E2", "E3", "E5"):
        for name, s in (_read(results / exp / "summary.json") or {}).items():
            if s["accepted_safe_rate"][0] is not None and s["tokens_per_test"][0]:
                pts.append((name, s["tokens_per_test"][0], s["accepted_safe_rate"][0]))
    if not pts:
        return None
    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    ax.scatter([p[1] for p in pts], [p[2] for p in pts], s=28, color=BLUE, edgecolor="white", linewidth=1, zorder=3)
    fig.canvas.draw()
    placed = []
    for n, x, y in sorted(pts, key=lambda p: -p[2]):        # first free spot around the dot, so labels never collide
        for dx, dy, ha in ((5, 2, "left"), (5, -9, "left"), (-5, 2, "right"), (-5, -9, "right"), (5, 10, "left")):
            t = ax.annotate(n, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=7, color=INK, ha=ha)
            box = t.get_window_extent(fig.canvas.get_renderer())
            if not any(box.overlaps(b) for b in placed):
                placed.append(box)
                break
            t.remove()
        else:
            ax.annotate(n, (x, y), xytext=(5, 2), textcoords="offset points", fontsize=7, color=INK)
    ax.set_xlabel("Tokens per test (mean over seeds)")
    ax.set_ylabel("Accepted and safe (%)")
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out / "fig_cost.pdf")
    return "fig_cost.pdf"


def _failures(out: Path, results: Path) -> str | None:
    c = _read(results / "failures/E3_counts.json")
    if not (c and c["counts"]):
        return None
    items = sorted(c["counts"].items(), key=lambda kv: -kv[1])
    fig, ax = plt.subplots(figsize=(4.6, 0.32 * len(items) + 0.7))
    _bars(ax, [k for k, _ in items], [v for _, v in items], [0] * len(items),
          f"Failures of the final system (n = {c['failures']})", unit="")
    fig.tight_layout()
    fig.savefig(out / "fig_failures.pdf")
    return "fig_failures.pdf"


def make_all(results: str | Path = "results") -> list[str]:
    results = Path(results)
    out = results / "figures"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for f in (_systems, _ablation, _cost, _failures):
        name = f(out, results)
        print(f"{f.__name__[1:]}: " + (f"wrote {out / name}" if name else "skipped (results not there yet)"))
        made += [name] if name else []
        plt.close("all")
    return made


if __name__ == "__main__":
    make_all()
