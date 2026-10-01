"""Headline candidate: common reference serving-cost axis, distinct evidence types."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, NullLocator

from . import benchmark_figures as b, distributions as d
from .paths import DATA, ROOT, REFERENCE
from .polish import theme, clean, INK, MUTED, TEAL, PURPLE


def main():
    out=ROOT/'polished_figures'/'headline_candidate'
    out.mkdir(parents=True,exist_ok=True)
    theme()
    token=json.loads((DATA/'token_groups.json').read_text())
    cost=[dict(r,dataset='TraceLab',hours_primary=r['hours_uncapped']) for r in json.loads((DATA/'cost_groups.json').read_text())]
    records=d.build_records(cost+d.choose(token,'WEKA'),token)
    d.validate(cost+d.choose(token,'WEKA'),token,records)
    selected=d.figure6_records(records,'retained')
    estimates=b.r.estimates(pd.read_csv(REFERENCE/'inferencex_prepared.csv'),'latest')
    rows=[]
    for model,label in [('dsv4','DeepSeek V4 Pro'),('glm5.2','GLM-5.2'),('minimaxm3','MiniMax M3'),('kimik3','Kimi K3')]:
        frame=estimates[(estimates.model==model)&(estimates.hardware=='gb300')&(estimates.metric=='p90')].set_index('cutoff')
        a,z=5/frame.loc[50,'estimate'],5/frame.loc[100,'estimate']
        rows.append(dict(model=model,label=label,evidence='benchmark',low=a,high=z,api_hourly=None,
                         concurrency_50=float(frame.loc[50,'estimate']),concurrency_100=float(frame.loc[100,'estimate'])))
    labels=['GPT-5.5 · Codex','GPT-5.6 Sol · Codex','Claude Opus 4.8','Claude Fable 5','Opus 4.8 · peak >500k','Fable 5 · peak >500k']
    for r,label in zip(selected,labels):
        rows.append(dict(model=r['model'],label=label,evidence='assumed',low=r['pooled']/10,high=r['pooled']/5,api_hourly=r['pooled'],high_context=r['high_context']))
    for r in rows:
        for year in [2026,2027]:
            for u in [1,2,4]:
                r[f'capacity_{year}_u{u}_low_millions']=b.capacity(year,u=u,c=5/r['high'])
                r[f'capacity_{year}_u{u}_high_millions']=b.capacity(year,u=u,c=5/r['low'])
    pd.DataFrame(rows).to_csv(out/'model_measurements.csv',index=False)
    fig=plt.figure(figsize=(12.5,11.8))
    gs=fig.add_gridspec(2,1,left=.255,right=.965,top=.865,bottom=.16,height_ratios=[1.05,1],hspace=.12)
    ax=fig.add_subplot(gs[0]); rug=fig.add_subplot(gs[1],sharex=ax)
    x=np.geomspace(.1,30,500)
    curve=[]
    for year,color in [(2026,'#8496A1'),(2027,TEAL)]:
        lo=b.capacity(year,u=1,c=5/x);hi=b.capacity(year,u=4,c=5/x);mid=b.capacity(year,u=2,c=5/x)
        ax.fill_between(x,lo,hi,color=color,alpha=.13)
        ax.plot(x,mid,color=color,lw=2.5)
        ax.text(19,b.capacity(year,u=2,c=5/19)*1.13,f'Through {year}',color=color,ha='right',fontsize=11,weight='bold')
        curve.extend(dict(year=year,reference_serving_usd_per_hour=float(xx),low_millions=float(ll),central_millions=float(mm),high_millions=float(hh)) for xx,ll,mm,hh in zip(x,lo,mid,hi))
    for row in rows:
        if row['evidence']=='benchmark':
            for val,marker in [(row['low'],'o'),(row['high'],'^')]:
                ax.plot(val,b.capacity(2027,u=2,c=5/val),marker,mfc='white',mec=TEAL,ms=6,mew=1.3,zorder=4)
    ax.set_xscale('log');ax.set_yscale('log');ax.set_xlim(.1,30);ax.set_ylim(2,6000)
    ax.set_yticks([2,5,10,25,50,100,250,500,1000,2500,5000])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:,.0f}'))
    ax.yaxis.set_minor_locator(NullLocator());ax.tick_params(axis='x',labelbottom=False)
    ax.set_ylabel('Potential concurrent sessions (millions)',labelpad=12)
    clean(ax,'both')
    ax.text(.02,.04,'Lines: 2× HBM4 uplift\nShading: 1–4× uplift',transform=ax.transAxes,color=MUTED,fontsize=10)
    rug.set_ylim(len(rows)-.4,-.9);rug.set_yticks(range(len(rows)),[r['label'] for r in rows],fontsize=10.5)
    rug.set_xticks([.1,.2,.5,1,2,5,10,20,30])
    rug.xaxis.set_major_formatter(FuncFormatter(lambda v,_:f'${v:g}'))
    rug.xaxis.set_minor_locator(NullLocator());clean(rug,'x')
    for i,row in enumerate(rows):
        color=TEAL if row['evidence']=='benchmark' else PURPLE
        rug.plot([row['low'],row['high']],[i,i],lw=3,color=color,alpha=.55 if row.get('high_context') else 1)
        if row['evidence']=='benchmark':
            rug.plot(row['low'],i,'o',mfc='white',mec=color,ms=7,mew=1.5)
            rug.plot(row['high'],i,'^',mfc='white',mec=color,ms=7,mew=1.5)
        else:
            rug.plot([row['low'],row['high']],[i,i],'|',color=color,ms=10)
    rug.axhline(3.5,color='#CDD8DE',lw=1)
    rug.axhline(7.5,color='#CDD8DE',lw=1,ls=':')
    rug.set_xlabel('Reference serving cost per session-hour (US$) · logarithmic scale',labelpad=11)
    fig.text(.035,.97,'Agent capacity spans millions to billions across model scenarios',fontsize=21,weight='bold',va='top')
    fig.text(.035,.93,'Cumulative memory shipments since 2025 · full allocation · $5 per GB300-hour',fontsize=12,color=MUTED)
    fig.text(.035,.90,'Report-snapshot model anchors—not estimates of equal task capability',fontsize=11,color=MUTED)
    fig.legend([Line2D([],[],color=TEAL,lw=3,marker='o',mfc='white'),Line2D([],[],color=TEAL,lw=0,marker='^',mfc='white'),Line2D([],[],color=PURPLE,lw=3)],
               ['Open: P90 50 tokens/s/user','Open: P90 100 tokens/s/user','Claude/GPT: assumed revenue/cost 5–10×'],
               loc='lower left',bbox_to_anchor=(.035,.065),ncol=2,frameon=False,fontsize=10.5)
    fig.text(.035,.025,'Ranges represent different assumptions, not statistical uncertainty. Long-context rows overlap full cohorts.\nOpen-model sessions are configured AgentX trees, including waiting; source-session and replay clocks differ.',fontsize=10,color=MUTED)
    fig.canvas.draw()
    for text in fig.texts:
        box=text.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
        assert box.x0>=0 and box.x1<=1 and box.y0>=0 and box.y1<=1,text.get_text()
    for ext in ['png','svg','pdf']:
        fig.savefig(out/f'headline_capacity.{ext}',dpi=240)
    plt.close(fig)
    pd.DataFrame(curve).to_csv(out/'capacity_curve.csv',index=False)
    caption=("Potential capacity from memory shipped since 2025 through 2026 or 2027, once deployed and fully allocated. "
        "At a reference GB300 rental price of $5/hour, serving cost C corresponds to 5/C configured sessions per GPU. "
        "Lines use 2× HBM4 concurrency uplift; shading spans 1–4×. Open-model endpoints use GB300 AgentX frontiers at "
        "P90 streaming-speed targets of 50 and 100 tokens/s/user. Claude/GPT ranges divide TraceLab's pooled API-equivalent "
        "hourly spending by an assumed revenue/serving-cost ratio of 5–10×. These anchor ranges have different meanings: "
        "speed targets for open models versus economic assumptions for closed models. They are neither uncertainty intervals "
        "nor quality-adjusted comparisons. The report's original clock, cache, price, and memory assumptions remain unchanged.")
    notes='''# Headline figure candidate

This is an additional figure, not a replacement for Figures 6 or 7 yet. No report edits.

## Why use a different horizontal axis?

API spending alone cannot put benchmarked open models and source-corpus Claude/GPT workloads on one physical-capacity curve: their revenue/cost ratios differ. Use reference serving cost instead. C = S/K for Claude/GPT; C = $5/c for GB300 benchmarks. Then capacity = effective GB300 equivalents × $5/C. This is an accounting normalization, not a measurement of a provider's actual operating costs or GPU fleet.

The main curves use central 2× HBM4 uplift; shading spans 1–4×. Every model row maps to either shipment horizon. Open circles and triangles on the through-2027 curve illustrate the open endpoints only; the lower rows supply all model labels without overlapping the curves. Closed rows deliberately show ranges rather than inventing a central K point.

## Scope and caveats

- Uses the same frozen September 15, 2026 benchmark snapshot and historical prices as the report, not a fresh search for September 17 results. These are report-snapshot model anchors, not all currently available models.
- All open-model anchors use GB300. MiniMax's report table selected B300 on rental economics, but substituting that chip count into a GB300-memory projection would mix assumptions; this figure instead uses its GB300 results.
- The four open models are those in the report's economic comparison. No API tariff is needed for their position, so DeepSeek peak/off-peak prices do not produce separate physical-capacity points.
- TraceLab uses the retained-cache, five-minute gap-cap pooled rates. Those rates are not per-session medians. The >500k rows use whole groups that ever exceeded the threshold and overlap the parent cohorts. They are not new independent samples.
- Model labels describe different measured workloads and, for Claude/GPT, harnesses; they are not controlled equal-task comparisons. Open AgentX configured trees include waiting. Offline source clocks are not the same as replay clocks. No common output-speed constraint is imposed on Claude/GPT.
- The displayed $0.10–$30/hour span contains all model anchor ranges. It is an illustrative scenario domain, not a statistical full-support interval or claim that future costs are bounded by this range.
- Capacity is once deployed, not active agents at calendar year-end. Full allocation and the report's memory assumptions remain hypothetical.

## Reproduce

From the repository root: `.venv/bin/python -m compute_tokens.headline`.

`model_measurements.csv` contains the input rates, benchmark concurrencies, and capacity envelopes for both years at each uplift. `capacity_curve.csv` contains every curve coordinate. Underlying assumptions and source provenance are in `docs/METHODOLOGY.md` and `docs/PROVENANCE.md`.
'''
    (out/'README.md').write_text(notes)
    (out/'caption.txt').write_text(caption+'\n')
    (out/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Headline capacity candidate</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:17px/1.6 system-ui;color:#203448}img{width:100%}a{color:#177782}</style><h1>Headline figure candidate</h1><img src="headline_capacity.svg" alt="Capacity curves across reference serving costs, with separately labeled open-model benchmark ranges and Claude/GPT economic-assumption ranges"><p>'+caption+'</p><p><a href="headline_capacity.png">PNG</a> · <a href="headline_capacity.svg">SVG</a> · <a href="headline_capacity.pdf">PDF</a> · <a href="model_measurements.csv">Model measurements</a> · <a href="README.md">Methodological notes</a></p></html>')
    # Algebraic consistency with Figure 7 and Figure 6.
    for r in rows:
        if r['evidence']=='benchmark':
            assert np.isclose(r['capacity_2027_u2_high_millions'],b.capacity(2027,u=2,c=r['concurrency_50']))
        else:
            assert np.isclose(r['capacity_2027_u2_high_millions'],b.capacity(2027,S=r['api_hourly'],K=10,u=2))
    print(out/'index.html')


if __name__=='__main__':
    main()
