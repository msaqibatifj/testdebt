"""Draw docs/architecture.png: baselines on top, proposed system below, gap badges.  python3 scripts/make_diagram.py"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

INK, MUTED, LINE = "#1f2328", "#57606a", "#8c959f"
FILL = {"tool": "#eaf2fb", "agent": "#fdf1e3", "data": "#eef7ee", "base": "#f4f4f6", "gap": "#c9302c"}


def box(ax, x, y, w, h, text, kind, size=8.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=FILL[kind], ec=LINE, lw=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=INK,
            fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.08, label, fontsize=7, color=MUTED, ha="center")


def badge(ax, x, y, t):
    ax.text(x, y, t, fontsize=7.5, color="white", ha="center", va="center", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc=FILL["gap"], ec="none"))


def main():
    fig, ax = plt.subplots(figsize=(13, 7.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7.6)
    ax.axis("off")
    ax.text(0.2, 7.3, "VeriRefactor: baselines (top) and proposed system S3 (bottom)", fontsize=12, color=INK,
            fontweight="bold")

    # data
    box(ax, 0.2, 5.6, 2.2, 1.1, "Pinned projects\nCommons-cli, Gson, Jsoup\n(data/pins.json)", "data")
    box(ax, 0.2, 4.2, 2.2, 1.1, "UTRefactor package\n484 smelly tests, tsDetect\nlabels, KB (defs, DSL)", "data")

    # baselines lane
    ax.text(2.9, 6.95, "Baselines - same model, KB, tools, caps, tests; only control flow differs", fontsize=8.5, color=MUTED)
    box(ax, 2.9, 5.9, 2.0, 0.85, "B0 (D1)\nUTRefactor prompt\n1 pass, compile+run", "base")
    box(ax, 5.1, 5.9, 2.2, 0.85, "B0-replay\npublished outputs of [1]\nthrough our verifier", "base")
    box(ax, 7.5, 5.9, 2.4, 0.85, "B1 fixed pipeline\nverify -> fixed retry prompt\n(<= 2 retries) -> reject", "base")
    box(ax, 10.1, 5.9, 2.6, 0.85, "B2 single tool-using agent\n(state-machine guard)\n[Phase 2]", "base")

    # proposed system
    ax.text(2.9, 4.95, "S3 (Phase 2): agents share one state record per test", fontsize=8.5, color=MUTED)
    box(ax, 2.9, 3.6, 1.9, 1.0, "Detection agent\ntsDetect + JNose", "agent")
    box(ax, 5.1, 3.6, 1.9, 1.0, "Planner agent\nDSL rule per smell,\nsplit plan", "agent")
    box(ax, 7.3, 3.6, 1.9, 1.0, "Refactor agent\nLLM (gpt-oss-120b)", "agent")
    box(ax, 9.5, 3.6, 1.9, 1.0, "Verifier agent\nevidence only", "agent")
    box(ax, 3.4, 2.2, 5.8, 0.9, "Supervisor: accept | retry with feedback | switch rule | revert | escalate\n"
                                "(<= 3 attempts, token cap, memory of failed (rule, context) pairs)", "agent", size=7.8)
    for x1, x2 in [(4.8, 5.1), (7.0, 7.3), (9.2, 9.5)]:
        arrow(ax, x1, 4.1, x2, 4.1)
    arrow(ax, 10.45, 3.6, 9.0, 3.1, "report")
    arrow(ax, 4.6, 3.1, 5.6, 3.6, "next step")
    arrow(ax, 2.4, 4.75, 2.9, 4.1)
    arrow(ax, 2.4, 6.1, 2.9, 6.3)

    # tools
    ax.text(0.2, 1.75, "Tools (every number comes from a tool, never from the LLM)", fontsize=8.5, color=MUTED)
    tools = [("Maven runner\ncompile + run class", 0.2), ("tsDetect\nmethod-level", 2.35), ("JNose\n2nd detector", 4.5),
             ("PIT full kill matrix\nK(T) subset of union K(t')", 6.65), ("JaCoCo\ncoverage", 8.8), ("Run log\ntokens, time", 10.95)]
    for t, x in tools:
        box(ax, x, 0.7, 2.0, 0.85, t, "tool", size=8)
    arrow(ax, 10.45, 3.6, 9.8, 1.55)

    # outputs
    box(ax, 11.6, 2.2, 1.3, 0.9, "Decision report\n+ escalation\nqueue", "data", size=7.5)
    arrow(ax, 9.2, 2.65, 11.6, 2.65)

    badge(ax, 7.65, 1.65, "G1 kill-set gate")
    badge(ax, 5.5, 1.65, "G2 second detector")
    badge(ax, 11.4, 6.85, "G6 B1/B2 vs S3, paired")

    ax.text(0.2, 0.25, "Legend:  blue = tool   orange = agent   green = data/output   grey = baseline   red = selected gap",
            fontsize=8, color=MUTED)
    out = Path(__file__).resolve().parents[1] / "docs/architecture.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    print("saved", out)


if __name__ == "__main__":
    main()
