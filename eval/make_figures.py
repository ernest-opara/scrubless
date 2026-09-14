"""Render the report figures from eval/results/summary.json.

    .venv/bin/python eval/make_figures.py   ->  docs/assets/eval_*.pdf
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "docs" / "assets"
OUT.mkdir(exist_ok=True)
S = json.loads((HERE / "results" / "summary.json").read_text())

BLUE, ORANGE = "#2a78d6", "#eb6834"  # categorical slots 1 and 2
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d3"
plt.rcParams.update({
    "font.family": "Helvetica Neue", "font.size": 9, "axes.edgecolor": GRID,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
})

CONDS = [  # (key, label) in display order, bottom-to-top
    ("visual_5s", "Visual only (shipped)"),
    ("transcript_bm25_5s", "Transcript only (BM25)"),
    ("hybrid_rrf_5s", "Hybrid: RRF"),
    ("hybrid_combsum_5s", "Hybrid: CombSUM, max-norm"),
    ("hybrid_coverage_5s", "Hybrid: CombSUM, coverage-norm"),
    ("hybrid_coverage_5s_noblank", "  + blank-frame suppression"),
]


def fig_conditions():
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=True)
    panels = [("visual", "Visual queries (n=39)"), ("spoken", "Spoken queries (n=26)"), ("all", "All queries (n=65)")]
    for ax, (key, title) in zip(axes, panels):
        block = S["by_type"][key] if key != "all" else S["all"]
        vals = [block[c]["r1"] for c, _ in CONDS]
        y = range(len(CONDS))
        ax.barh(y, vals, height=0.55, color=BLUE, zorder=3)
        for yi, v in zip(y, vals):
            ax.text(v + 0.02, yi, "%.2f" % v, va="center", ha="left", color=INK, fontsize=8)
        ax.set_xlim(0, 1.12)
        ax.set_xticks([0, 0.5, 1.0])
        ax.xaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.tick_params(length=0)
        ax.spines["left"].set_visible(False)
    axes[0].set_yticks(range(len(CONDS)))
    axes[0].set_yticklabels([l for _, l in CONDS], color=INK)
    axes[1].set_xlabel("Recall@1 (5 s frame index)")
    fig.tight_layout()
    fig.savefig(OUT / "eval_conditions.pdf")


def fig_alpha():
    sweep = S["alpha_sweep_combsum_5s"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.4), sharey=True)
    for ax, name, title in ((axes[0], "combsum", "Max-normalised BM25"),
                            (axes[1], "coverage", "Coverage-normalised BM25")):
        alphas = sorted(float(k.split("=")[1]) for k in sweep if k.startswith(name))
        for series, color, label in (("visual", BLUE, "visual queries"), ("spoken", ORANGE, "spoken queries")):
            ys = [sweep["%s a=%s" % (name, a)][series]["r1"] for a in alphas]
            ax.plot(alphas, ys, color=color, linewidth=2, marker="o", markersize=4,
                    markerfacecolor="white", markeredgewidth=1.5, label=label, zorder=3)
            ax.text(alphas[-1] + 0.02, ys[-1], label, color=INK2, va="center", fontsize=8)
        ax.axvline(0.5, color=GRID, linewidth=0.8, linestyle="--", zorder=1)
        ax.set_xlim(0.25, 0.95)
        ax.set_ylim(0, 1.02)
        ax.set_xticks(alphas)
        ax.set_xlabel("α (weight on visual channel)")
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
        ax.tick_params(length=0)
    axes[0].set_ylabel("Recall@1")
    axes[0].legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / "eval_alpha.pdf")


if __name__ == "__main__":
    fig_conditions()
    fig_alpha()
    print("wrote", OUT / "eval_conditions.pdf", OUT / "eval_alpha.pdf")
