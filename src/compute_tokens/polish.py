"""Alternative report artwork; frozen analysis and original figures are untouched.

Run: python -m compute_tokens.polish
All figures are rebuilt from numeric inputs, never from reference images.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LogNorm, LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, NullLocator
import numpy as np
import pandas as pd

from . import benchmark_figures as b, distributions as d
from .paths import ROOT, DATA, REFERENCE

INK = "#203448"
MUTED = "#566774"
TEAL = "#177782"
PURPLE = "#7160A0"
ROSE = "#AD456E"
PALE = "#DCE9ED"
LABELS = dict(b.LABELS, **{"glm5.2": "GLM-5.2"})
MARKERS = ["o", "s", "^", "v", "D", "P", "X", "<", ">"]
FILES = {
    "1": "figure_1_p90_frontiers", "2": "figure_2_capacity_matrix",
    "3": "figure_3_session_costs_retained", "4": "figure_4_token_distributions_retained",
    "5": "figure_5_capacity_envelope", "6": "figure_6_cost_sensitivity",
    "7": "figure_7_deepseek_sensitivity", "A1": "figure_a1_median_frontiers",
    "A2": "figure_a2_200tps",
}
SOURCES = {
    "benchmark": ("InferenceX, September 15, 2026 snapshot", "https://inferencex.semianalysis.com/"),
    "tracelab": ("TraceLab v0.0.2", "https://github.com/uw-syfi/TraceLab/releases/tag/v0.0.2"),
    "weka": ("SemiAnalysis WEKA source dataset", "https://huggingface.co/datasets/semianalysisai/cc-traces-weka-062126/tree/23f152f6f0f9399a85901b89a6458def0ef16729"),
}
BENCH_NOTE = (
    "Configured AgentX clients are root session trees, including subagents and waiting, not simultaneous "
    "decode requests. Physical GPU counts include both pools in disaggregated deployments. Streaming "
    "speed excludes time to first token; P90 is the published speed statistic, not a latency guarantee. "
    "The September 15, 2026 snapshot is frozen; GLM 5.1 and VR200 are excluded. Models are not assumed "
    "to have equal capabilities."
)
CAP_NOTE = (
    "Eligible memory shipments accumulate from 2025 through the indicated year. These are potential "
    "capacities once that memory is deployed and fully allocated to these workloads, not forecasts of "
    "agents online at year-end. Uplift means HBM4 concurrency relative to HBM3E. Ranges are scenario "
    "envelopes, not confidence intervals. The original supply and serving assumptions are unchanged."
)
SHORT_CAPTIONS = {
    "1": "Published P90 streaming-speed/concurrency frontiers by model and hardware. Concurrency counts configured AgentX session trees per physical GPU, including subagents and waiting. Speed excludes time to first token; frontier segments may connect different serving deployments.",
    "A1": "Median streaming-speed/concurrency frontiers, using the same models, axes, and hardware encodings as Figure 1. Concurrency counts configured session trees, not simultaneous decode requests. Speed excludes time to first token.",
    "2": "Configured agent sessions per physical GPU at P90 streaming-speed targets of 50 and 100 tokens/s/user. Values interpolate published frontiers in original units without extrapolation. Asterisks indicate measured sweeps that remain above the target; dashes mean no qualifying coverage, not zero capacity.",
    "A2": "Configured agent sessions per physical GPU at a P90 streaming-speed target of 200 tokens/s/user. Columns and color scale match Figure 2. Dashes indicate no qualifying coverage, not zero capacity; models are not assumed to have equal capabilities.",
    "3": "API-equivalent hourly costs in TraceLab under the retained-cache scenario and five-minute gap cap. Boxes show the middle 50% of eligible group rates; pooled rates equal total spending divided by total adjusted hours, including short groups. Long-context rows are overlapping whole-session subsets, not just periods above 500,000 tokens.",
    "4": "Hourly token-use distributions for seven Claude models shared by TraceLab and the WEKA source corpus used by AgentX, without reweighting model shares. Both analyses cap uncovered gaps at five minutes, but session and cache reconstruction differ. This is a source-trace comparison, not a comparison of replayed hardware workloads.",
    "5": "Potential concurrent agent capacity from eligible memory shipped since 2025, once deployed and fully allocated to these workloads. Dark ranges assume 2× HBM4 concurrency uplift; pale ranges allow 1–4×. Both use a revenue/serving-cost ratio of 5–10×. These are scenario ranges, not confidence intervals or year-end activity forecasts.",
    "6": "Sensitivity to API-equivalent hourly workload cost at a fixed revenue/serving-cost ratio of 5–10×. Dark bands assume 2× HBM4 concurrency uplift; pale bands allow 1–4×. A pure API price change also changes the revenue/cost ratio, so this is not the physical effect of repricing alone.",
    "7": "Potential agent capacity using DeepSeek V4 Pro GB300 benchmarks and cumulative memory shipments since 2025. Lines span 1–4× HBM4 concurrency uplift; circles mark 2×. The two speed targets are alternative uses of the same hardware pool and must not be added. Model capabilities are not assumed equivalent.",
}


def cell_color(rgba):
    """Choose black or white by WCAG relative-luminance contrast."""
    rgb = np.asarray(rgba[:3])
    linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
    luminance = float(linear @ np.array([.2126, .7152, .0722]))
    return "white" if 1.05 / (luminance + .05) >= (luminance + .05) / .05 else "black"


def theme():
    plt.rcdefaults()
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11, "axes.labelsize": 11,
        "axes.titlesize": 13, "axes.titleweight": "bold", "text.color": INK,
        "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#BBC7CD", "svg.fonttype": "none", "text.parse_math": False,
        "pdf.fonttype": 42, "savefig.facecolor": "white",
    })


def header(fig, title, subtitle):
    fig.text(.035, .967, title, fontsize=21, fontweight="bold", va="top", gid="figure-title")
    fig.text(.035, .911, subtitle, fontsize=11.5, color=MUTED, va="top", gid="figure-subtitle")


def foot(fig, text):
    fig.text(.035, .023, text, fontsize=10, color=MUTED, va="bottom", gid="figure-footnote")


def clean(ax, axis="x"):
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis=axis, color="#E1E7EA", lw=.7)
    ax.tick_params(axis="y", length=0)


class Gallery:
    def __init__(self, output):
        self.out = output
        for directory in (output, output / "figures", output / "measurements"):
            directory.mkdir(parents=True, exist_ok=True)
        self.entries = []
        self.bounds = []
        self.pdf = PdfPages(output / "all_figures.pdf", metadata={"Title": "Compute to tokens — polished figures", "CreationDate": None, "ModDate": None})

    def save(self, fig, number, title, caption, alt, sources):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        # Catch figure-level text overflowing the canvas (not just inspect the PNG).
        for text in fig.texts:
            box = text.get_window_extent(renderer).transformed(fig.transFigure.inverted())
            if box.x0 < -.001 or box.x1 > 1.001 or box.y0 < -.001 or box.y1 > 1.001:
                raise AssertionError(f"Figure {number}: out-of-canvas text: {text.get_text()}")
        self.bounds.append({"figure": number, "figure_text_inside_canvas": True})
        stem = FILES[number]
        for ext in ("png", "svg", "pdf"):
            metadata = {"Date": None} if ext == "svg" else ({"CreationDate": None, "ModDate": None} if ext == "pdf" else None)
            fig.savefig(self.out / "figures" / f"{stem}.{ext}", dpi=240, metadata=metadata)
        self.pdf.savefig(fig)
        plt.close(fig)
        self.entries.append(dict(number=number, stem=stem, title=title, caption=SHORT_CAPTIONS[number], method_notes=caption, alt=alt, sources=sources))

    def finish(self, checks):
        self.pdf.close()
        self.entries.sort(key=lambda e: list(FILES).index(e["number"]))
        (self.out / "captions.json").write_text(json.dumps(self.entries, indent=2) + "\n")
        md = "# Polished figure captions\n\nDraft 2 terminology; reviewed September 17, 2026. Figure numbering unchanged. Numerical assumptions unchanged.\n\n"
        sections = []
        for e in self.entries:
            source_links = "; ".join(f"[{SOURCES[k][0]}]({SOURCES[k][1]})" for k in e["sources"])
            md += f"## Figure {e['number']}. {e['title']}\n\n{e['caption']}\n\nSources: {source_links or 'Frozen report assumptions; see the methodology and provenance files.'}\n\n### Detailed methodological notes\n\n{e['method_notes']}\n\nAlt text: {e['alt']}\n\n"
            links = " · ".join(f'<a href="figures/{e["stem"]}.{x}">{x.upper()}</a>' for x in ("png", "svg", "pdf"))
            source_html = "; ".join(f'<a href="{SOURCES[k][1]}">{html.escape(SOURCES[k][0])}</a>' for k in e["sources"])
            sections.append(f'''<section id="figure-{e['number']}"><h2>Figure {e['number']}</h2>
<img src="figures/{e['stem']}.svg" alt="{html.escape(e['alt'], quote=True)}" loading="lazy">
<p>{html.escape(e['caption'])}</p><p class="muted">{source_html}</p><p>{links}</p>
<details><summary>Methodological notes and exclusions</summary><p>{html.escape(e['method_notes'])}</p></details>
<details><summary>Compare with the existing report figure</summary><img src="../reference/figures/{e['stem']}.png" alt="Existing Figure {e['number']}"></details></section>''')
        (self.out / "captions.md").write_text(md)
        nav = " · ".join(f'<a href="#figure-{n}">{n}</a>' for n in FILES)
        (self.out / "index.html").write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Polished report figures</title>
<style>body{{max-width:1120px;margin:40px auto;padding:0 22px;font:17px/1.6 system-ui;color:{INK};background:#f5f7f8}}
h1,h2{{line-height:1.2}}a{{color:#096c79}}nav{{position:sticky;top:0;background:#f5f7f8;padding:12px 0;z-index:1}}
section{{background:white;border:1px solid #d9e1e5;border-radius:8px;padding:20px;margin:25px 0;scroll-margin-top:65px}}
img{{width:100%;height:auto}}.muted{{color:{MUTED};font-size:14px}}details{{border-top:1px solid #dde4e7;padding-top:10px}}
@media print{{nav,details{{display:none}}section{{break-before:page;border:0}}}}</style>
<h1>Polished report figures</h1><p>Draft 2 terminology · September 17, 2026 · all nine figures, rebuilt from the frozen data.</p>
<p>Revised wording and layouts, unchanged calculations. No document edits. The original figures are available below each chart.</p>
<nav>Figures: {nav}</nav><p><a href="all_figures.pdf">All figures (PDF)</a> · <a href="captions.md">Captions</a> · <a href="measurements/summary.json">Numerical summaries</a> · <a href="README.md">Methods and design notes</a></p>
{''.join(sections)}</html>''')
        (self.out / "validation.json").write_text(json.dumps(dict(checks=checks, text_bounds=self.bounds), indent=2) + "\n")
        paths = [DATA / n for n in ("cost_groups.json", "token_groups.json", "prices.json", "assumptions.json", "figure_config.json", "inferencex_2026-09-15.csv.gz")]
        paths.append(Path(__file__))
        inputs = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        outputs = {str(p.relative_to(self.out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.out.rglob("*")) if p.is_file() and p.name != "manifest.json"}
        (self.out / "manifest.json").write_text(json.dumps(dict(prepared="2026-09-17", inputs=inputs, outputs=outputs), indent=2) + "\n")


def frontiers(gallery, df, metric):
    number = "1" if metric == "p90" else "A1"
    stat = "P90" if metric == "p90" else "Median"
    title = "Faster responses trade off against concurrent agents"
    fig, axes = plt.subplots(4, 2, figsize=(12.4, 13.8), sharex=True, sharey=True)
    header(fig, title, f"Published configuration frontiers · {stat.lower() if stat == 'Median' else stat} streaming speed · logarithmic axes")
    x = f"metrics.{metric}_intvty"
    for ax, model in zip(axes.flat, b.MODELS):
        for h, marker in zip(b.HARDWARE, MARKERS):
            group = df[(df.model == model) & (df.hardware == h)]
            if group.empty:
                continue
            c = b.CONFIG["hardware_colors"][h]
            frontier = b.r.pareto_frontier(group, x)
            ax.scatter(group[x], group.concurrency_per_gpu, s=10, alpha=.13, color=c, marker=marker)
            ax.plot(frontier[x], frontier.concurrency_per_gpu, color=c, lw=2, marker=marker, ms=4)
        ax.set_title(LABELS[model], loc="left", pad=9)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlim(1, 1000); ax.set_ylim(.025, 100)
        ax.set_xticks([1, 10, 100, 1000], ["1", "10", "100", "1,000"])
        ax.set_yticks([.1, 1, 10, 100], ["0.1", "1", "10", "100"])
        ax.minorticks_off(); clean(ax, "both")
        for cut in (50, 100):
            ax.axvline(cut, ls=":", lw=.9, color="#8C9BA4", zorder=0)
        ax.tick_params(labelbottom=True, labelleft=True)
    axes[-1, -1].axis("off")
    handles = [Line2D([], [], color=b.CONFIG["hardware_colors"][h], marker=m, lw=2, ms=5, label=h.upper()) for h, m in zip(b.HARDWARE, MARKERS)]
    axes[-1, -1].legend(handles=handles, loc="upper left", ncol=3, frameon=False, columnspacing=1, handlelength=1.5, fontsize=10)
    axes[-1, -1].text(.02, .50, "Faint points: measured configurations\nLines: best observed trade-offs\nDotted guides: 50 and 100 tokens/s/user", transform=axes[-1, -1].transAxes, va="top", color=MUTED, fontsize=11, linespacing=1.7)
    fig.text(.02, .52, "Configured agent sessions per GPU", rotation=90, va="center", fontsize=12)
    fig.text(.52, .065, f"{stat} streaming speed (tokens/s/user)", ha="center", fontsize=12)
    foot(fig, "Speed excludes time to first token. Frontiers can connect different serving deployments.")
    fig.subplots_adjust(left=.10, right=.965, top=.858, bottom=.115, hspace=.53, wspace=.24)
    gallery.save(fig, number, title, "Speed/concurrency frontiers share the same axes across models and across Figures 1 and A1. Lines show Pareto envelopes of measured configurations, not a controlled sweep of one deployment. " + BENCH_NOTE,
                 f"Seven model panels compare {stat} streaming speed with configured session trees per physical GPU; higher concurrency generally reduces per-user speed.", ["benchmark"])


def matrix(gallery, estimates, cutoffs):
    number = "2" if len(cutoffs) == 2 else "A2"
    title = "Concurrent agents per GPU at a target response speed"
    sel = estimates[estimates.metric == "p90"]
    # Identical columns and color mapping at all three speed targets.
    hardware = [h for h in b.HARDWARE if sel[(sel.hardware == h) & sel.model.isin(b.MODELS)].estimate.notna().any()]
    fig, axes = plt.subplots(len(cutoffs), 1, figsize=(12.4, 10.5 if len(cutoffs) == 2 else 7.3), squeeze=False)
    header(fig, title, "Configured agent sessions · root trees including subagents · per physical GPU")
    cmap = LinearSegmentedColormap.from_list("teal", ["#F1F7F8", "#91BDC5", "#176B79", "#133747"])
    cmap.set_bad("#F0F2F4")
    norm = LogNorm(.05, 40)
    for ax, cut in zip(axes[:, 0], cutoffs):
        mat = np.full((len(b.MODELS), len(hardware)), np.nan)
        marks = {}
        for i, m in enumerate(b.MODELS):
            for j, h in enumerate(hardware):
                row = sel[(sel.model == m) & (sel.hardware == h) & (sel.cutoff == cut)]
                if not row.empty:
                    mat[i, j] = row.iloc[0].estimate
                    marks[i, j] = "*" if row.iloc[0]["method"] == "maximum_measured_frontier_starts_above_cutoff" else ""
        im = ax.imshow(mat, cmap=cmap, norm=norm, aspect="auto")
        for (i, j), value in np.ndenumerate(mat):
            ax.text(j, i, f"{value:.3g}{marks.get((i,j), '')}" if np.isfinite(value) else "—", ha="center", va="center", fontsize=12, color=cell_color(cmap(norm(value))) if np.isfinite(value) else INK)
        ax.set_xticks(range(len(hardware)), [h.upper() for h in hardware])
        ax.set_yticks(range(len(b.MODELS)), [LABELS[m] for m in b.MODELS])
        ax.set_title(f"P90 streaming speed ≥ {cut} tokens/s/user", loc="left", pad=14)
        ax.spines[:].set_visible(False); ax.tick_params(length=0)
        ax.set_xticks(np.arange(-.5, len(hardware)), minor=True)
        ax.set_yticks(np.arange(-.5, len(b.MODELS)), minor=True)
        ax.grid(which="minor", color="white", lw=2); ax.tick_params(which="minor", length=0)
    cbax = fig.add_axes([.32, .115 if len(cutoffs) == 2 else .145, .55, .015])
    cb = fig.colorbar(im, cax=cbax, orientation="horizontal", ticks=[.05, .1, 1, 10, 40])
    cb.ax.set_xticklabels(["0.05", "0.1", "1", "10", "40"]); cb.ax.minorticks_off()
    cb.set_label("Agent sessions per GPU · logarithmic color scale", fontsize=10)
    foot(fig, "* Highest measured concurrency remains above the target.   — No qualifying measurement or no coverage.")
    fig.subplots_adjust(left=.255, right=.97, top=.805 if len(cutoffs) == 2 else .755, bottom=.225, hspace=.40)
    gallery.save(fig, number, title, "Linear interpolation uses original speed and concurrency units; no extrapolation. An asterisk marks the highest measured concurrency when its speed already exceeds the target. A dash is missing qualifying coverage, not zero capacity. All three target-speed matrices use identical hardware columns and color scales. " + BENCH_NOTE,
                 "Numeric heatmap of configured agent sessions per GPU for seven models across hardware, with separate panels for " + " and ".join(map(str, cutoffs)) + " tokens/s/user targets. Missing coverage is shown explicitly.", ["benchmark"])


def costs(gallery, records):
    selected = d.figure6_records(records, "retained")
    title = "The cost of an agent-hour varies across agent sessions"
    fig = plt.figure(figsize=(12.4, 7.6))
    header(fig, title, "TraceLab · five-minute gap cap · retained-cache scenario · frozen September 2026 prices")
    gs = fig.add_gridspec(1, 3, width_ratios=[2.6, 5.4, 1.9], left=.035, right=.975, top=.79, bottom=.225, wspace=.06)
    labels, ax, nums = [fig.add_subplot(gs[0, i]) for i in range(3)]
    positions = [0, 1, 2, 3, 4.8, 5.8]
    for panel in (labels, ax, nums):
        panel.set_ylim(6.5, -.75)
    labels.axis("off"); nums.axis("off")
    xmax = np.ceil(max(max(r["values"] + [r["pooled"]]) for r in selected) / 50) * 50
    ax.set_xlim(0, xmax); ax.set_xticks(np.arange(0, xmax+1, 50))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.set_yticks([]); ax.set_xlabel("API-equivalent cost per agent-hour (US$)", labelpad=12)
    clean(ax)
    for y, row in zip(positions, selected):
        model = {"gpt-5.5": "GPT-5.5", "gpt-5.6-sol": "GPT-5.6 Sol", "claude-opus-4-8": "Claude Opus 4.8", "claude-fable-5": "Claude Fable 5"}[row["model"]]
        harness = "Codex" if row["model"].startswith("gpt") else "Claude Code"
        color = TEAL if harness == "Codex" else PURPLE
        labels.text(0, y-.16, model, weight="bold", fontsize=12, va="center")
        labels.text(0, y+.20, f"{harness} · n = {row['eligible_groups']:,}" + (" (small sample)" if row["eligible_groups"] < 20 else ""), color=MUTED, fontsize=10, va="center")
        ax.plot([row["p0"], row["p100"]], [y,y], color="#AEBFC8", lw=1)
        ax.plot([row["p10"], row["p90"]], [y,y], color=color, lw=2)
        ax.plot([row["p10"], row["p90"]], [y,y], "|", color=color, ms=9)
        ax.barh(y, row["p75"]-row["p25"], left=row["p25"], height=.4, color=color, alpha=.85)
        ax.plot([row["p50"]]*2, [y-.26,y+.26], color=INK, lw=2.2)
        nums.text(.38, y, f"${row['p50']:.1f}", ha="right", va="center", weight="bold", fontsize=12)
        nums.text(.98, y, f"${row['pooled']:.1f}", ha="right", va="center", fontsize=12)
    nums.text(.38, -.65, "Median", ha="right", color=MUTED, fontsize=10)
    nums.text(.98, -.65, "Pooled", ha="right", color=MUTED, fontsize=10)
    for panel in (labels, ax, nums):
        panel.axhline(3.75, lw=.9, color="#D3DDE2")
    labels.text(0, 4.22, "Subsets: peak context >500k", fontsize=10, weight="bold", color=MUTED)
    ax.text(0, 4.22, "Whole agent sessions; overlap the rows above", fontsize=10, color=MUTED)
    fig.text(.035, .12, "Box: middle 50% · thick whiskers: middle 80% · dark tick: median · faint line: full range", fontsize=11, color=MUTED)
    foot(fig, "Pooled = total spending ÷ total adjusted hours, including short groups.\nn = plotted groups with at least five primary active minutes; see caption for group definitions.")
    caption = (
        "TraceLab session/model groups, using the report's retained-cache counterfactual and 300-second cap on uncovered within-run gaps; known model/tool work is not capped. "
        "Boxes span P25–P75, whiskers P10–P90, and faint lines the full eligible range. Percentiles weight eligible groups equally. Pooled rates divide all included spending by all adjusted hours, including short groups. "
        "The >500k rows include whole groups with at least one request exceeding 500,000 input-context tokens; they overlap the main rows and are not full-1M-only periods. "
        "Runs are assigned to their first priceable model; mixed-model calls keep their own prices. Groups are not always complete parent/subagent trees, and counts are not additive across model rows. "
        "Included activity spans April 23–July 24, 2026 UTC. Claude tariffs were collected August 21; the saved overlay is September 8 and Codex prices were checked September 14. "
        "GPT-5.6 non-read inputs are assumed written. Source response times are unchanged, and the retained-cache scenario is not observed billing."
    )
    gallery.save(fig, "3", title, caption, "Horizontal cost distributions for GPT-5.5, GPT-5.6 Sol, Claude Opus 4.8, and Claude Fable 5, plus overlapping long-context Claude subsets. Pooled costs are $18.2, $15.5, $24.3, $50.2, $39.0, and $104.8 per adjusted hour, respectively.", ["tracelab"])
    return [{k:v for k,v in r.items() if k != "values"} for r in selected]


def tokens(gallery, records):
    selected = [r for r in records if r["kind"] == "tokens" and r["scenario"] == "retained" and r["clock"] == "cap300" and r["cohort"] == "shared_pool"]
    title = "Hourly token use in AgentX source traces and TraceLab"
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 7.4))
    header(fig, title, "Pooled Claude workloads · five-minute gap cap · retained-cache comparison")
    colors = {"TraceLab": TEAL, "WEKA": ROSE}
    for i, (metric, label, scale, unit, ticks) in enumerate(d.TOKEN_METRICS):
        ax = axes[i]; clean(ax, "both")
        rows = [r for r in selected if r["metric"] == metric]
        xmax = max(max(r["values"]) for r in rows) / scale * 1.1
        pivot = {"cached_input": 1, "nonread_input": 100, "output": 20}[metric]
        ax.set_xscale("function", functions=(lambda x,p=pivot: np.log10(1+np.asarray(x)/p), lambda x,p=pivot:p*(10**np.asarray(x)-1)))
        ax.set_xlim(0, xmax); ax.set_xticks([v for v in ticks if v <= xmax])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}")); ax.xaxis.set_minor_locator(NullLocator())
        for row in rows:
            values = np.array(row["values"]) / scale
            percentages = np.arange(1, len(values)+1) / len(values) * 100
            ax.step(np.r_[0,values,xmax], np.r_[0,percentages,100], where="post", color=colors[row["dataset"]], lw=2.3, ls="-" if row["dataset"] == "TraceLab" else "--")
            ax.plot(row["p50"]/scale, 50, "o", color=colors[row["dataset"]], mfc="white", ms=6, mew=1.5)
        ax.axhline(50, color="#8E9CA6", ls=":", lw=1)
        ax.set_ylim(0, 102); ax.set_yticks([0,25,50,75,100], [f"{p}%" for p in (0,25,50,75,100)] if i == 0 else [])
        ax.set_title(label, loc="left", pad=12)
        ax.set_xlabel(("Million" if scale == 1e6 else "Thousand") + " tokens per agent-hour", labelpad=10, fontsize=10)
        if i == 0: ax.set_ylabel("Share of agent sessions at or below the rate", labelpad=10)
        ax.text(0, -.30, "Dataset", transform=ax.transAxes, fontsize=9.5, color=MUTED)
        ax.text(.68, -.30, "Median", transform=ax.transAxes, fontsize=9.5, color=MUTED, ha="right")
        ax.text(1, -.30, "Pooled", transform=ax.transAxes, fontsize=9.5, color=MUTED, ha="right")
        for j, dataset in enumerate(("TraceLab", "WEKA")):
            row = next(r for r in rows if r["dataset"] == dataset)
            y = -.41-j*.11
            ax.text(0, y, "TraceLab" if dataset == "TraceLab" else "AgentX (WEKA)", transform=ax.transAxes, color=colors[dataset], fontsize=10)
            for x, key in ((.68,"p50"),(1,"pooled")):
                ax.text(x, y, f"{row[key]/scale:,.1f}", ha="right", transform=ax.transAxes, color=colors[dataset], fontsize=10)
    handles = [Line2D([], [], color=colors[ds], lw=2.3, ls="-" if ds == "TraceLab" else "--", label=("TraceLab" if ds == "TraceLab" else "AgentX source traces (WEKA)") + f" · n = {next(r['eligible_groups'] for r in selected if r['dataset']==ds):,}") for ds in colors]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.025,.862), frameon=False, ncol=2, fontsize=11)
    foot(fig, "Circles mark medians. Nonlinear x axes show zero and the full tails; scales differ by token type.\nSource-trace accounting, not benchmark replay. Session and cache methods differ between datasets.")
    fig.subplots_adjust(left=.09, right=.97, top=.735, bottom=.365, wspace=.21)
    caption = (
        "Cumulative distributions of token consumption per adjusted hour, pooling the seven shared Claude model labels without reweighting their shares. "
        "The same eligible groups and full tails as the report are shown; curves weight eligible groups equally, while pooled rates divide all tokens by all adjusted hours, including short groups. "
        "TraceLab has 5,079 session/model groups; WEKA has 393 root trees, with both parent and child calls. TraceLab parent/child linkage is incomplete. "
        "Both source clocks use a five-minute gap cap, but TraceLab preserves identified tool/model work and removes identified human waits; WEKA caps uncovered gaps between unioned response intervals without those labels. "
        "These offline adjustments are not the AgentX runtime idle watchdog. TraceLab retained-cache accounting is heuristic; WEKA ideal reuse matches previously completed same-model prefixes without expiry. "
        "Non-read input includes cache writes and misses, not just novel text. WEKA input counts are derived from 64-token blocks and are not exact tokenization. "
        "The comparison is conditional on these methods, not evidence of identical tasks, model mix, or replay intensity. "
        "Each x axis uses log10(1 + rate/pivot), with pivots 1 million cached-input, 100,000 non-read-input, and 20,000 output tokens/hour. "
        "TraceLab v0.0.2 and the pinned WEKA dataset built June 21, 2026 are unchanged."
    )
    gallery.save(fig, "4", title, caption, "Three cumulative-distribution panels compare cached input, non-read input, and output tokens per adjusted hour for TraceLab and WEKA. Both medians and pooled rates are printed separately; the datasets' distributions overlap but their methods differ.", ["tracelab", "weka"])
    return [{k:v for k,v in r.items() if k != "values"} for r in selected]


def projections(gallery, estimates):
    cap = b.capacity
    title = "Potential agent capacity grows with cumulative memory supply"
    fig, ax = plt.subplots(figsize=(12.4, 6.3))
    header(fig, title, "$30 per agent-hour · revenue/cost ratio of 5–10× · $5 per GB300-hour · full allocation")
    closed = []
    for pos, year in enumerate((2026, 2027)):
        lo, hi, central_lo, central_hi = cap(year,u=1), cap(year,K=10,u=4), cap(year), cap(year,K=10)
        ax.plot([lo,hi], [pos,pos], lw=23, color=PALE, solid_capstyle="butt")
        ax.plot([central_lo,central_hi], [pos,pos], lw=12, color=TEAL, solid_capstyle="butt")
        ax.text((central_lo+central_hi)/2, pos-.24, f"{central_lo:.0f}–{central_hi:.0f} million", ha="center", color=TEAL, weight="bold", fontsize=13)
        ax.text(hi+4, pos, f"{lo:.0f}–{hi:.0f}", va="center", color=MUTED, fontsize=12)
        closed.append(dict(year=year, low_millions=lo, central_low_millions=central_lo, central_high_millions=central_hi, high_millions=hi))
    clean(ax); ax.set_yticks([0,1], ["2025–26 shipments", "2025–27 shipments"])
    ax.set_ylim(1.52,-.60); ax.set_xlim(0,205)
    ax.set_xlabel("Potential concurrent agents (millions)", labelpad=12)
    fig.legend([Line2D([],[],color=TEAL,lw=9),Line2D([],[],color=PALE,lw=13)], ["2× HBM4 concurrency uplift", "1–4× HBM4 concurrency uplift"], loc="lower left", bbox_to_anchor=(.19,.105), ncol=2, frameon=False, fontsize=11)
    foot(fig, "Scenario ranges, not confidence intervals. Capacity once deployed, not agents online at year-end.")
    fig.subplots_adjust(left=.20,right=.97,top=.77,bottom=.29)
    gallery.save(fig,"5",title,"At $30 of API-equivalent spending per adjusted agent-hour and $5 per GB300-hour, a revenue/serving-cost ratio of 5–10× implies 0.833–1.667 agent sessions per GB300 equivalent. Dark bars use 2× HBM4 uplift; pale bars vary uplift from 1× to 4×, keeping the same revenue/cost range. " + CAP_NOTE,
                 "Through-2026 shipments support a central scenario of 20–40 million concurrent agents, rising to 50–101 million through 2027. Wider uplift scenarios broaden both ranges.", [])
    title = "The capacity estimate depends on hourly workload cost"
    fig, axes = plt.subplots(1,2,figsize=(12.4,6.5),sharey=True)
    header(fig,title,"Revenue/cost ratio held at 5–10× · $5 per GB300-hour · full allocation")
    s = np.linspace(10,100,181)
    sensitivity = []
    for ax, year in zip(axes,(2026,2027)):
        ax.fill_between(s,cap(year,s,u=1),cap(year,s,K=10,u=4),color=PALE)
        ax.fill_between(s,cap(year,s),cap(year,s,K=10),color=TEAL,alpha=.88)
        ax.axvline(30,ls="--",color=INK,lw=1.2)
        ax.text(32,380,"$30 reference",fontsize=10)
        ax.set_title(f"2025–{str(year)[-2:]} shipments",loc="left",pad=12)
        ax.set_yscale("log"); ax.set_ylim(4,600); ax.set_xlim(10,100)
        ax.set_xticks([10,30,50,75,100], ["$10","$30","$50","$75","$100"])
        ax.set_yticks([5,10,25,50,100,250,500],["5","10","25","50","100","250","500"])
        ax.minorticks_off(); clean(ax,"y")
        ax.set_xlabel("API-equivalent cost per agent-hour (US$)",labelpad=12)
        sensitivity.extend(dict(year=year,hourly_cost=float(v),outer_low=cap(year,v,u=1),outer_high=cap(year,v,K=10,u=4),central_low=cap(year,v),central_high=cap(year,v,K=10)) for v in s)
    axes[0].set_ylabel("Potential concurrent agents (millions)\nLogarithmic scale",labelpad=10)
    fig.legend([Line2D([],[],color=TEAL,lw=8),Line2D([],[],color=PALE,lw=11)], ["2× HBM4 concurrency uplift","1–4× HBM4 concurrency uplift"],loc="lower left",bbox_to_anchor=(.13,.08),ncol=2,frameon=False)
    foot(fig,"Not the effect of API repricing alone: a price change affects both spending and the revenue/cost ratio.")
    fig.subplots_adjust(left=.11,right=.97,top=.765,bottom=.26,wspace=.16)
    gallery.save(fig,"6",title,"The workload-cost sensitivity varies API-equivalent spending from $10 to $100 per adjusted agent-hour while holding the revenue/serving-cost ratio at 5–10×. Dark ranges use 2× HBM4 concurrency uplift and pale ranges use 1–4×. A pure API price change would also change the revenue/cost ratio, and does not itself change physical capacity. " + CAP_NOTE,
                 "Two panels show falling capacity as assumed workload cost increases, with a $30 reference and the same logarithmic capacity scale for both shipment horizons.",[])
    title = "Potential capacity under DeepSeek V4 Pro benchmarks"
    fig, axes = plt.subplots(1,2,figsize=(12.4,6.2),sharex=True,sharey=True)
    header(fig,title,"GB300 measurements · agents counted as root session trees · alternative P90 speed targets")
    group = estimates[(estimates.model=="dsv4")&(estimates.hardware=="gb300")&(estimates.metric=="p90")].set_index("cutoff")
    opened=[]
    for ax,year in zip(axes,(2026,2027)):
        for pos,cut in enumerate((50,100)):
            concurrency=group.loc[cut,"estimate"]
            lo,hi,central=cap(year,u=1,c=concurrency),cap(year,u=4,c=concurrency),cap(year,u=2,c=concurrency)
            ax.plot([lo/1000,hi/1000],[pos,pos],lw=9,color=TEAL,solid_capstyle="butt")
            ax.plot(central/1000,pos,"o",mfc="white",mec=TEAL,ms=9,mew=2)
            ax.text((lo+hi)/2000,pos-.22,f"{lo/1000:.2f}–{hi/1000:.2f} billion",ha="center",fontsize=12)
            opened.append(dict(year=year,cutoff=cut,c=concurrency,low_millions=lo,central_millions=central,high_millions=hi))
        ax.set_title(f"2025–{str(year)[-2:]} shipments",loc="left",pad=14)
        ax.set_xlim(0,3.5);ax.set_ylim(1.6,-.7)
        ax.set_yticks([0,1],["50 tokens/s/user","100 tokens/s/user"])
        ax.set_xlabel("Potential concurrent agents (billions)",labelpad=12);clean(ax)
    fig.legend([Line2D([],[],color=TEAL,lw=7),Line2D([],[],color=TEAL,marker="o",mfc="white",lw=0,ms=8)], ["1–4× HBM4 concurrency uplift","2× HBM4 concurrency uplift"],loc="lower left",bbox_to_anchor=(.15,.085),ncol=2,frameon=False)
    foot(fig,"The two speed targets use the same hardware pool; do not add them. No claim of equal model capability.")
    fig.subplots_adjust(left=.165,right=.97,top=.745,bottom=.285,wspace=.16)
    gallery.save(fig,"7",title,"The DeepSeek V4 Pro GB300 frontier yields 31.425 and 14.422 configured agent sessions per GPU at P90 streaming-speed targets of 50 and 100 tokens/s/user, respectively. These are separate uses of the same memory pool, not additive capacities. Lines vary HBM4 concurrency uplift from 1× to 4×; open circles show 2×. This direct benchmark projection does not use the closed-model revenue/cost ratio. " + CAP_NOTE + " " + BENCH_NOTE,
                 "Alternative 50- and 100-token/s/user targets give different potential agent capacities, shown in billions, for cumulative shipments through 2026 and 2027.",["benchmark"])
    return closed,sensitivity,opened


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"polished_figures")
    args=parser.parse_args()
    gallery=Gallery(args.output)
    theme()
    prepared=args.output/"measurements"/"inferencex_prepared.csv"
    subprocess.run([sys.executable,"-m","compute_tokens.prepare","--input",str(DATA/"inferencex_2026-09-15.csv.gz"),"--output",str(prepared),"--snapshot-date","2026-09-15"],check=True)
    df=pd.read_csv(prepared)
    ref=pd.read_csv(REFERENCE/"inferencex_prepared.csv")
    pd.testing.assert_frame_equal(df,ref,check_dtype=False,check_like=True,rtol=1e-10,atol=1e-8)
    tokens_raw=json.loads((DATA/"token_groups.json").read_text())
    costs_raw=[dict(row,dataset="TraceLab",hours_primary=row["hours_uncapped"]) for row in json.loads((DATA/"cost_groups.json").read_text())]
    records=d.build_records(costs_raw+d.choose(tokens_raw,"WEKA"),tokens_raw)
    d.validate(costs_raw+d.choose(tokens_raw,"WEKA"),tokens_raw,records)
    estimates=b.r.estimates(df,"latest")
    estimates.to_csv(args.output/"measurements"/"all_cutoff_estimates.csv",index=False)
    # Preserve complete ECDF data, not just exported summary quantiles.
    (args.output/"measurements"/"distributions.json").write_text(json.dumps(records,indent=2)+"\n")
    frontiers(gallery,df,"p90");matrix(gallery,estimates,[50,100])
    cost_summary=costs(gallery,records);token_summary=tokens(gallery,records)
    closed,sensitivity,opened=projections(gallery,estimates)
    frontiers(gallery,df,"median");matrix(gallery,estimates,[200])
    for name,rows in (("session_costs",cost_summary),("token_rates",token_summary),("capacity_scenarios",closed),("cost_sensitivity",sensitivity),("deepseek_capacity",opened)):
        pd.DataFrame(rows).to_csv(args.output/"measurements"/f"{name}.csv",index=False)
    summary=dict(cost=cost_summary,tokens=token_summary,capacity=closed,deepseek=opened)
    (args.output/"measurements"/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    sealed=json.loads((ROOT/"release_manifest.json").read_text())["files"]
    protected=[name for name in sealed if name.startswith(("data/","reference/")) or name in ("src/compute_tokens/benchmark_figures.py","src/compute_tokens/distributions.py")]
    for name in protected:
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sealed[name]["sha256"], f"Frozen baseline changed: {name}"
    gallery.finish({"prepared_benchmarks_match_reference":True,"cost_and_token_regressions_passed":True,"figures":len(gallery.entries),"frozen_files_checked":len(protected),"baseline_renderers_unchanged":True})
    print(f"Created {len(gallery.entries)} figures: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
