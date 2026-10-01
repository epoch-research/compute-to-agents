"""Report figures from audited anonymous aggregates and verified Codex tariffs.

Run with TraceLab/.venv/bin/python from any working directory.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
from pathlib import Path

import numpy as np

from .paths import DATA, REFERENCE
OUT = None
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, NullLocator
SOURCES = {
 "pricing_verification": DATA / "pricing_verification.json",
 "cost_groups": DATA / "cost_groups.json",
 "cost_reference": REFERENCE / "cost_percentiles.json",
 "token_groups": DATA / "token_groups.json",
 "token_reference": REFERENCE / "token_comparison.json",
}
COLORS = {"TraceLab": "#177782", "WEKA": "#B54E76"}
DISPLAY = {"TraceLab": "TraceLab", "WEKA": "AgentX source traces (WEKA)"}
INK = "#233448"
MUTED = "#5A6877"
COHORTS = [
    ("gpt-5.5", False, "GPT-5.5 · Codex"),
    ("gpt-5.6-sol", False, "GPT-5.6 Sol · Codex"),
    ("claude-opus-4-8", False, "Opus 4.8-led"),
    ("claude-fable-5", False, "Fable 5-led"),
    ("claude-opus-4-8", True, "Opus 4.8-led\npeak >500k"),
    ("claude-fable-5", True, "Fable 5-led\npeak >500k"),
]
TOKEN_METRICS = [
    ("cached_input", "Cached input", 1e6, "Million tokens / hour", [0, 1, 10, 100, 1000]),
    ("nonread_input", "Non-read input", 1e3, "Thousand tokens / hour", [0, 100, 1000, 10000]),
    ("output", "Output", 1e3, "Thousand tokens / hour", [0, 10, 100, 1000]),
]
FLAGSHIPS = {"claude-fable-5", "claude-opus-4-7", "claude-opus-4-8"}
METHODS = {"baseline": {"TraceLab": "observed", "WEKA": "recent"},
           "retained": {"TraceLab": "retained", "WEKA": "ideal"}}
PRICE_PROXY = {"cached_input": .5, "nonread_input": 6.25, "output": 25.}
MAIN_CODEX_WRITE_MARKUP = True
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "svg.fonttype": "none", "axes.titleweight": "bold"})


def load(path):
    return json.loads(path.read_text())


def choose(rows, dataset, model=None, high=False):
    return [r for r in rows if r["dataset"] == dataset and
            (model is None or r["model"] == model) and
            (not high or r["max_input"] > 500000)]


def cost(row, scenario, markup=False):
    if row["dataset"] == "WEKA":
        return row["reconstructed_costs"][METHODS[scenario]["WEKA"]]
    field = ("observed_cost" if scenario == "baseline" else "retained_cost") if markup else (
        "no_write_cost" if scenario == "baseline" else "no_write_retained_cost")
    return row[field]


def distribution(rows, numerator, clock="cap300"):
    hours = np.array([r["hours_" + clock] for r in rows])
    totals = np.array([numerator(r) for r in rows])
    eligible = np.array([r["hours_primary"] >= 1/12 and h > 0 for r, h in zip(rows, hours)], dtype=bool)
    values = totals[eligible] / hours[eligible]
    v = np.sort(values)
    return dict(groups=len(rows), eligible_groups=len(v), hours=float(hours.sum()),
                eligible_hours=float(hours[eligible].sum()), numerator=float(totals.sum()),
                pooled=float(totals.sum() / hours.sum()) if hours.sum() else None,
                values=v.tolist(),
                **{f"p{p}": float(np.quantile(v, p/100)) if len(v) else None
                   for p in (0, 5, 10, 25, 50, 75, 90, 95, 99, 100)})


def setup_axis(ax):
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#CBD3DC")
    ax.grid(axis="x", color="#E2E7EC", lw=.65)
    ax.tick_params(axis="y", length=0)


def save(fig, name):
    for ext in ("png", "svg", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=230, facecolor="white")
    plt.close(fig)


def cost_figure(records, scenario):
    fig, ax = plt.subplots(figsize=(8.8, 5.6), facecolor="white")
    selected = figure6_records(records, scenario)
    xmax = max(max(r["values"] + [r["pooled"]]) for r in selected) * 1.07
    ax.set_xlim(0, max(200, np.ceil(xmax / 25) * 25))
    ax.set_ylim(6.45, -.6)
    setup_axis(ax)
    ax.set_xticks(np.arange(0, ax.get_xlim()[1] + 1, 50))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.set_yticks([])
    ax.set_xlabel("API-equivalent $ per adjusted session-hour", labelpad=9, fontsize=10)
    positions = [0, 1, 2, 3, 4.65, 5.65]
    for yy, d in zip(positions, selected):
        c = "#177782" if d["model"].startswith("gpt") else "#5969A6"
        label = d["label"].replace("-led", "").replace("\npeak >500k", "")
        ax.text(-.045, yy-.10, label, transform=ax.get_yaxis_transform(), ha="right",
                va="center", fontsize=10, color=INK, fontweight="medium")
        nlabel = f"n = {d['eligible_groups']:,}" + (" · small sample" if d['eligible_groups'] < 20 else "")
        ax.text(-.045, yy+.24, nlabel, transform=ax.get_yaxis_transform(), ha="right",
                va="center", fontsize=8.5, color=MUTED)
        # No point cloud. Full observed extent stays visible as a faint hairline;
        # summaries have dedicated marks, and numbers live outside the plot.
        ax.plot([d["p0"], d["p100"]], [yy]*2, color="#C3CCD5", lw=.9, zorder=2)
        ax.plot([d["p10"], d["p90"]], [yy]*2, color=c, lw=2.0, zorder=3)
        ax.plot([d["p10"], d["p90"]], [yy]*2, "|", color=c, ms=7, mew=1.2, zorder=3)
        ax.barh(yy, d["p75"]-d["p25"], left=d["p25"], height=.34,
                color=c, alpha=.80, edgecolor="none", zorder=4)
        ax.plot([d["p50"]]*2, [yy-.22, yy+.22], color=INK, lw=2.1, zorder=5)
        for xx, key in [(1.155, "p50"), (1.345, "pooled")]:
            ax.text(xx, yy, f"${d[key]:.1f}", transform=ax.get_yaxis_transform(),
                    ha="right", va="center", color=INK, fontsize=10,
                    fontweight="bold" if key == "p50" else "normal")
    ax.axhline(3.65, color="#CFD7DF", lw=.8)
    ax.text(-.045, 4.03, "SESSION PEAK >500k", transform=ax.get_yaxis_transform(),
            ha="right", va="center", fontsize=8.2, fontweight="bold", color=MUTED)
    ax.text(0, 4.03, "Whole sessions that reached long context", va="center", fontsize=8.2, color=MUTED)
    for xx, label in [(1.155, "Median"), (1.345, "Pooled")]:
        ax.text(xx, -.65, label, transform=ax.get_yaxis_transform(), ha="right", color=MUTED, fontsize=9)
    fig.text(.035, .948, "The cost of an agent-hour is a distribution", fontsize=17, fontweight="bold", color=INK)
    mode = "retained-cache scenario" if scenario == "retained" else "recorded-cache scenario"
    fig.text(.035, .902, "TraceLab sessions · five-minute gap cap · " + mode, fontsize=10, color=MUTED)
    fig.text(.035, .118, "Box: middle 50% (P25–P75)   |   Dark tick: median   |   Whiskers: P10–P90", fontsize=9, color=MUTED)
    fig.text(.035, .082, "Faint line: full observed range   |   Pooled: total spending ÷ total hours, including short sessions", fontsize=8.6, color=MUTED)
    fig.text(.035, .046, "Current standard Codex tariffs; GPT-5.6 non-read input assumed written. Claude tariffs unchanged.", fontsize=8.2, color=MUTED)
    fig.text(.035, .015, "n: groups with ≥5 primary active minutes. Long-context subsets overlap full cohorts. Source latencies fixed.", fontsize=8.2, color=MUTED)
    fig.subplots_adjust(left=.25,right=.80,top=.83,bottom=.245)
    save(fig, f"figure_3_session_costs_{scenario}")


def figure6_records(records, scenario):
    selected = [r for r in records if r["kind"] == "cost" and r["dataset"] == "TraceLab"
                and r["scenario"] == scenario and r["clock"] == "cap300"
                and r["codex_write_markup"] == MAIN_CODEX_WRITE_MARKUP]
    return [next(r for r in selected if r["model"] == model and r["high_context"] == high)
            for model, high, _label in COHORTS]


def token_figure(records, scenario):
    selected = [r for r in records if r["kind"] == "tokens" and r["scenario"] == scenario
                and r["clock"] == "cap300" and r["cohort"] == "shared_pool"]
    fig, axes = plt.subplots(1,3,figsize=(8.8,4.6), facecolor="white")
    for i,(metric,title,scale,unit,ticks) in enumerate(TOKEN_METRICS):
        ax=axes[i]
        setup_axis(ax)
        ds=[r for r in selected if r["metric"]==metric]
        xmax=max(max(r["values"]) for r in ds)/scale*1.1
        # Explicit log(1+x/pivot) gives a continuous zero-inclusive scale.
        pivot={"cached_input":1.,"nonread_input":100.,"output":20.}[metric]
        ax.set_xscale("function",functions=(lambda x,pivot=pivot:np.log10(1+np.asarray(x)/pivot),
                                           lambda x,pivot=pivot:pivot*(10**np.asarray(x)-1)))
        ax.set_xlim(0,xmax)
        ax.set_xticks([x for x in ticks if x<=xmax])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_:f"{x:,.0f}"))
        ax.xaxis.set_minor_locator(NullLocator())
        for r in ds:
            v=np.array(r["values"])/scale
            p=np.arange(1,len(v)+1)/len(v)
            ax.step(np.r_[0,v,xmax],np.r_[0,p,1]*100,where="post",color=COLORS[r["dataset"]],lw=1.9)
            ax.plot(r["p50"]/scale,50,"o",ms=4.5,mec=COLORS[r["dataset"]],mfc="white",mew=1.2)
            ax.plot(r["pooled"]/scale,-5,"D",color=COLORS[r["dataset"]],ms=4.5,clip_on=False)
        ax.axhline(50,color="#99A4AF",ls=":",lw=.8)
        ax.set_ylim(-7,102)
        ax.set_yticks([0,25,50,75,100],[f"{x}%" for x in [0,25,50,75,100]] if i==0 else [])
        ax.set_title(title,loc="left",fontsize=11,color=INK,pad=9)
        ax.set_xlabel(unit,fontsize=8.5,labelpad=7)
        if i==0:ax.set_ylabel("Share of sessions at or below rate",fontsize=9)
        for j,r in enumerate(ds):
            def fmt(v): return f"{v/scale:,.1f}" if scale==1e6 else f"{v/scale:,.0f}"
            ax.text(0,-.30-j*.095,f"{r['dataset']}: {fmt(r['p50'])} median · {fmt(r['pooled'])} pooled",
                    transform=ax.transAxes,color=COLORS[r['dataset']],fontsize=8.1)
    fig.text(.045,.95,"AgentX traces vs Tracelab",fontsize=17,fontweight="bold",color=INK)
    fig.text(.045,.895,"Hourly token consumption · pooled Claude workloads · " +
             ("retained-cache scenario" if scenario=="retained" else "recorded / reconstructed cache"),fontsize=9.3,color=MUTED)
    handles=[Line2D([],[],color=c,lw=2,label=f"{DISPLAY[ds]} (n={next(r['eligible_groups'] for r in selected if r['dataset']==ds):,})") for ds,c in COLORS.items()]
    fig.legend(handles=handles,loc="upper left",bbox_to_anchor=(.034,.865),ncol=2,frameon=False,fontsize=8.7)
    fig.text(.045,.10,"Curves include every eligible group; log-like x axes keep the full tails and zero. Circles: medians. Diamonds: pooled rates.",fontsize=8,color=MUTED)
    fig.text(.045,.059,"Five-minute gap cap; source timings fixed. WEKA includes children; TraceLab linkage is incomplete. Methods are not identical.",fontsize=8,color=MUTED)
    fig.text(.045,.019,"Non-read input includes writes and cache misses, not just novel text. Pooled similarity does not imply model-by-model equivalence.",fontsize=8,color=MUTED)
    fig.subplots_adjust(left=.092,right=.978,top=.738,bottom=.36,wspace=.16)
    save(fig,f"figure_4_token_distributions_{scenario}")


def build_records(cost_rows, token_rows):
    records=[]
    for scenario in METHODS:
        for clock in ("cap300","cap60"):
            for model,high,label in COHORTS:
                for ds in COLORS:
                    rows=choose(cost_rows,ds,model,high)
                    if not rows:continue
                    for markup in (False,True):
                        if markup and ds=="WEKA":continue
                        records.append(dict(kind="cost",dataset=ds,model=model,high_context=high,label=label,
                            scenario=scenario,clock=clock,codex_write_markup=markup,
                            **distribution(rows,lambda r:cost(r,scenario,markup),clock)))
            for ds in COLORS:
                for cohort in ("shared_pool","flagship_pool"):
                    rows=choose(token_rows,ds)
                    if cohort=="flagship_pool":
                        rows=[r for r in rows if r["model"] in FLAGSHIPS] if ds=="TraceLab" else [r for r in rows if set(r["main_models"])<=FLAGSHIPS]
                    for metric,*_ in TOKEN_METRICS:
                        records.append(dict(kind="tokens",dataset=ds,cohort=cohort,metric=metric,
                            scenario=scenario,clock=clock,
                            **distribution(rows,lambda r:r["tokens"][METHODS[scenario][ds]][metric],clock)))
                    # Diagnostic common tariff, not an actual bill. Price whole-group
                    # token totals BEFORE taking quantiles, preserving covariance.
                    records.append(dict(kind="common_tariff",dataset=ds,cohort=cohort,scenario=scenario,clock=clock,
                        **distribution(rows,lambda r:sum(r["tokens"][METHODS[scenario][ds]][m]*p/1e6 for m,p in PRICE_PROXY.items()),clock)))
    return records


def validate(cost_rows, token_rows, records):
    verified = load(SOURCES["pricing_verification"])
    saved = load(SOURCES["cost_reference"])["price_table"]
    for model, current in verified["prices_per_million_tokens"].items():
        for category, rate in current.items():
            assert saved[model][category] == rate, (model, category, "Recompute from per-request tokens if rates change")
    assert all(r["max_input"] <= 272000 for r in choose(cost_rows, "TraceLab", "gpt-5.5"))
    assert sum(r["max_input"] > 272000 for r in choose(cost_rows, "TraceLab", "gpt-5.6-sol")) == 4
    for scenario in METHODS:
        selected = figure6_records(records, scenario)
        assert len(selected) == 6 and all(r["dataset"] == "TraceLab" for r in selected)
    reference=load(SOURCES["cost_reference"])["rows"]
    for d in records:
        assert d["p0"]<=d["p25"]<=d["p50"]<=d["p75"]<=d["p100"]
        assert len(d["values"])==d["eligible_groups"]
        assert np.isclose(d["pooled"]*d["hours"],d["numerator"])
        if d["kind"]=="cost" and d["dataset"]=="TraceLab":
            sc=("recorded_categories_or_all_nonreads_written" if d["codex_write_markup"] else "recorded_categories_no_codex_write_markup") if d["scenario"]=="baseline" else (
                "retained_cache_all_nonreads_written" if d["codex_write_markup"] else "retained_cache_no_codex_write_markup")
            ref=next(r for r in reference if r["model"]==d["model"] and r["cohort"]==("session_peak>500k" if d["high_context"] else "all") and r["clock"]==d["clock"] and r["scenario"]==sc)
            assert d["groups"]==ref["sessions"] and d["eligible_groups"]==ref["percentile_sessions"]
            for k in ("p25","p50","p75","pooled"):assert np.isclose(d[k],ref[k],rtol=1e-11)
    token_ref=load(SOURCES["token_reference"])["rows"]
    for d in records:
        if d["kind"]=="tokens" and d["clock"]=="cap300":
            ref=next(r for r in token_ref if r["dataset"]==d["dataset"] and r["model"]==d["cohort"] and r["metric"]==d["metric"] and r["scenario"]==d["scenario"] and r["clock"]==d["clock"])
            for k in ("p25","p50","p75","pooled"):assert np.isclose(d[k],ref[k],rtol=1e-11)
    for r in token_rows:
        for t in r["tokens"].values():assert t["input"]==t["cached_input"]+t["nonread_input"]
    assert len(choose(token_rows,"WEKA"))==393
    assert len(choose(token_rows,"TraceLab"))==5079
    assert sum(r["calls"] for r in choose(token_rows,"WEKA"))==98827
    assert sum(r["child_calls"] for r in choose(token_rows,"WEKA"))==42029
    sparse=next(d for d in records if d["kind"]=="cost" and d["dataset"]=="WEKA" and d["model"]=="claude-fable-5" and d["high_context"])
    assert sparse["groups"]==sparse["eligible_groups"]==1


def write_outputs(records):
    fingerprints={k:dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for k,p in SOURCES.items()}
    payload=dict(sources=fingerprints,price_snapshot="Current standard Codex rates verified against official docs; unchanged audited Claude tariffs",
                 price_table=load(SOURCES["cost_reference"])["price_table"],common_tariff_diagnostic=PRICE_PROXY,
                 pricing_verification=load(SOURCES["pricing_verification"]),
                 figure6_main=dict(dataset="TraceLab",codex_write_markup=MAIN_CODEX_WRITE_MARKUP,clock="cap300",scenario="retained"),
                 records=records)
    (OUT/"numerical_measurements.json").write_text(json.dumps(payload,indent=2)+"\n")
    flat=[{k:v for k,v in r.items() if k!="values"} for r in records]
    fields=sorted({k for r in flat for k in r})
    with (OUT/"numerical_measurements.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(flat)
    main_flat = [{k:v for k,v in r.items() if k != "values"}
                 for scenario in METHODS for r in figure6_records(records, scenario)]
    with (OUT/"figure_3_numerical_measurements.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(main_flat[0]));w.writeheader();w.writerows(main_flat)
    with (OUT/"empirical_cdf_points.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["record_index","value","share_at_or_below"])
        for j,r in enumerate(records):
            v=np.array(r["values"])
            for x in np.unique(v):w.writerow([j,x,float(np.searchsorted(v,x,side="right")/len(v))])
    rows=[]
    for r in records:
        if r["kind"]!="cost" or r["dataset"]!="TraceLab" or r["clock"]!="cap300" or r["codex_write_markup"]!=MAIN_CODEX_WRITE_MARKUP:continue
        rows.append(f"<tr data-scenario='{r['scenario']}'><td>{html.escape(r['label']).replace(chr(10),' ')}</td><td>{DISPLAY[r['dataset']]}</td><td>{r['eligible_groups']}/{r['groups']}</td>"+"".join(f"<td>${r[k]:.2f}</td>" for k in ["p10","p25","p50","p75","p90","pooled"])+"</tr>")
    (OUT/"index.html").write_text("""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent-session cost distributions</title><style>body{font:16px/1.55 system-ui;margin:32px auto;max-width:1080px;padding:0 20px;color:#233448}img{width:100%;height:auto}button{padding:9px 16px;margin-right:8px;cursor:pointer}button.active{background:#177782;color:white;border:2px solid #177782}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;text-align:right;border-bottom:1px solid #ddd}td:first-child,td:nth-child(2){text-align:left}aside{padding:16px;background:#f1f5f7}a{color:#177782}h1{line-height:1.2}</style>
<h1>What does an hour of agent work cost?</h1><p>Figure 3 focuses on TraceLab only. Figure 4 separately connects the AgentX WEKA source corpus with TraceLab using price-independent token rates.</p>
<aside>These are <strong>offline API-equivalent spending estimates</strong>, not invoices, GPU costs, or measured AgentX replay costs. Source model latencies stay fixed. WEKA includes subagents; TraceLab lacks complete child linkage. The five-minute cap is a clock scenario, not proof that every remaining second is autonomous work.</aside>
<p><button id="retained" class="active" onclick="show('retained')">Retained-cache scenario</button><button id="baseline" onclick="show('baseline')">Recorded / reconstructed cache</button></p>
<p id="explain"></p><img id="cost" alt="TraceLab hourly-cost percentile boxes without overlapping point clouds"><p>Current standard Codex tariffs were verified against <a href="https://developers.openai.com/api/docs/pricing">official API pricing</a> and the <a href="https://developers.openai.com/api/docs/models/gpt-5.5">GPT-5.5 model page</a>. Rates match the saved audit; the main chart now uses its all-nonread-write estimate for GPT-5.6. Actual write allocation is unknown. Claude prices are unchanged. No new model speeds are simulated.</p><h2>Exact cost statistics ($ per adjusted hour)</h2><p>n = eligible / total groups. Pooled uses all groups; percentiles use groups with at least five primary active minutes. Long-context rows overlap their all-context rows. The full numerical files also contain the zero-write-surcharge sensitivity (codex_write_markup=false), alternative clocks and earlier WEKA cost diagnostics; none of those are plotted in Figure 3.</p>
<table><thead><tr><th>Cohort</th><th>Source</th><th>n</th><th>P10</th><th>P25</th><th>Median</th><th>P75</th><th>P90</th><th>Pooled</th></tr></thead><tbody>"""+"\n".join(rows)+"""</tbody></table>
<h2>Connecting the workloads without conflating model prices</h2><img id="tokens" alt="Empirical cumulative token-rate distributions"><p>The curves give the fraction of eligible sessions at or below each rate. Similar pooled rates do not imply identical tails, model-specific cohorts, or individual tasks. The seven-model pool is not reweighted to a common model mix.</p>
<p><a href="figure_3_numerical_measurements.csv">Figure 3 measurements</a> · <a href="numerical_measurements.csv">All scenarios CSV</a> · <a href="numerical_measurements.json">Full numerical data and provenance</a> · <a href="empirical_cdf_points.csv">Exact ECDF points</a> · <a href="../index.html">All report outputs</a></p>
<script>function show(s){document.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.id===s));document.querySelectorAll('tr[data-scenario]').forEach(r=>r.hidden=r.dataset.scenario!==s);document.getElementById('cost').src='figure_3_session_costs_'+s+'.png';document.getElementById('tokens').src='figure_4_token_distributions_'+s+'.png';document.getElementById('explain').textContent=s==='retained'?'Retained cache: TraceLab uses the audited human-idle/TTL-gated context-length heuristic. In Figure 4, WEKA searches all previously completed same-model prefixes. Neither method changes recorded latency.':'Baseline: TraceLab uses recorded cache categories, with GPT-5.6 non-read input assumed written. Figure 4 reconstructs recent completed-prefix reuse for WEKA; that is not an observed billing counter.';}show('retained');</script></html>""")


def main(output, inputs=DATA):
    global OUT
    plt.rcdefaults()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "svg.fonttype": "none", "axes.titleweight": "bold"})
    OUT = output
    SOURCES["cost_groups"] = inputs / "cost_groups.json"
    SOURCES["token_groups"] = inputs / "token_groups.json"
    OUT.mkdir(parents=True, exist_ok=True)
    token_rows=load(SOURCES["token_groups"])
    tl=[dict(r,dataset="TraceLab",hours_primary=r["hours_uncapped"]) for r in load(SOURCES["cost_groups"])]
    cost_rows=tl+choose(token_rows,"WEKA")
    records=build_records(cost_rows,token_rows)
    validate(cost_rows,token_rows,records)
    write_outputs(records)
    for scenario in METHODS:
        cost_figure(records,scenario)
        token_figure(records,scenario)
    print(json.dumps({"validated_records":len(records),"output":str(OUT)},indent=2))
