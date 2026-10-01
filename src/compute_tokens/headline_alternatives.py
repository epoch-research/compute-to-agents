"""Three editorial alternatives using the headline candidate's unchanged inputs."""
import html
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.colors import LogNorm
from matplotlib.ticker import NullLocator

from . import headline
from .paths import ROOT
from .polish import theme, clean, TEAL, PURPLE, INK, MUTED, cell_color

OUT=ROOT/'polished_figures'/'headline_alternatives'
ORANGE='#B65820'
TICKS=[5,10,25,50,100,250,500,1000,2500,5000]


def value(row,year,u,endpoint):
    return row[f'capacity_{year}_u{u}_{endpoint}_millions']


def setup(ax, labels):
    ax.set_xscale('log');ax.set_xlim(5,5000)
    ax.set_xticks(TICKS,[f'{v:,}' for v in TICKS],fontsize=10)
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_yticks(range(len(labels)),labels,fontsize=11)
    ax.set_ylim(len(labels)-.4,-.7)
    clean(ax)
    ax.set_xlabel('Potential concurrent sessions (millions) · log scale',labelpad=12,fontsize=11)


def title(fig,main,sub):
    fig.text(.035,.97,main,fontsize=21,weight='bold',va='top')
    fig.text(.035,.91,sub,fontsize=11.5,color=MUTED,va='top')


def footer(fig,text):
    fig.text(.035,.025,text,fontsize=10,color=MUTED,va='bottom')


def save(fig,name,caption):
    fig.canvas.draw()
    for text in fig.texts:
        box=text.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
        assert 0<=box.x0 and box.x1<=1 and box.y0>=0 and box.y1<=1,text.get_text()
    for ext in ('png','svg','pdf'):fig.savefig(OUT/f'{name}.{ext}',dpi=220)
    plt.close(fig)
    return dict(name=name,caption=caption)


def overview(closed,opened):
    fig,axes=plt.subplots(2,1,figsize=(12.6,9.6),gridspec_kw={'height_ratios':[1.3,1]})
    title(fig,'How many concurrent agents could the memory supply support?',
          'Memory shipped from 2025 through 2027 · central 2× HBM4 uplift · full allocation')
    for ax,rows in zip(axes,[closed,opened]):setup(ax,[r['label'] for r in rows])
    axes[0].set_title('Claude/GPT: range from the assumed revenue/cost ratio',loc='left',pad=14)
    for i,r in enumerate(closed):
        lo,hi=value(r,2027,2,'low'),value(r,2027,2,'high')
        axes[0].plot([lo,hi],[i,i],color=PURPLE,lw=5,solid_capstyle='butt')
        axes[0].text(hi*1.12,i,f'{lo:,.0f}–{hi:,.0f}',va='center',fontsize=10.5,color=PURPLE)
    axes[0].axhline(3.5,color='#D3DDE2',ls=':')
    axes[0].set_xlabel('');axes[0].tick_params(labelbottom=False)
    axes[1].set_title('Open models: separate points for two response-speed targets',loc='left',pad=14)
    for i,r in enumerate(opened):
        for ep,color,marker in [('high',TEAL,'o'),('low',ORANGE,'^')]:
            v=value(r,2027,2,ep)
            yy=i+(-.12 if ep=='high' else .12)
            axes[1].plot(v,yy,marker,color=color,ms=8)
            axes[1].text(v*1.10,yy,f'{v:,.0f}',va='center',fontsize=10,color=color)
    fig.legend([Line2D([],[],color=TEAL,marker='o',lw=0),Line2D([],[],color=ORANGE,marker='^',lw=0)],
               ['P90 50 tokens/s/user','P90 100 tokens/s/user'],loc='lower left',bbox_to_anchor=(.25,.063),ncol=2,frameon=False,fontsize=11)
    footer(fig,'Claude/GPT: API-equivalent spending ÷ assumed 5–10× revenue/cost ratio. Open: GB300 benchmarks.\nDifferent workloads and session clocks—not equal capabilities. Peak >500k rows are overlapping whole-session subsets.')
    fig.subplots_adjust(left=.26,right=.97,top=.82,bottom=.185,hspace=.32)
    return save(fig,'a_capacity_overview','A — Recommended single-figure overview. Read capacity directly on the horizontal axis. Claude/GPT bars vary only the revenue/cost ratio (5–10×); open-model circles and triangles are two discrete speed scenarios, not an uncertainty range. Fixes the shipment horizon at 2027 and memory uplift at 2× to remove two layers of interpretation. Wider assumptions appear in option B.')


def split(closed,opened):
    results=[]
    fig,axes=plt.subplots(1,2,figsize=(13.4,7.8),sharey=True)
    title(fig,'Claude/GPT capacity under alternative serving assumptions',
          'TraceLab hourly spending · revenue/cost ratio of 5–10× · full memory allocation')
    for ax,year in zip(axes,[2026,2027]):
        setup(ax,[r['label'] for r in closed]);ax.set_title(f'2025–{str(year)[-2:]} shipments',loc='left',pad=15)
        ax.set_xlim(3,600);ax.set_xticks([5,10,25,50,100,250,500],['5','10','25','50','100','250','500'])
        for i,r in enumerate(closed):
            lo,hi=value(r,year,2,'low'),value(r,year,2,'high')
            ax.plot([value(r,year,1,'low'),value(r,year,4,'high')],[i,i],color='#DED8EC',lw=13,solid_capstyle='butt')
            ax.plot([lo,hi],[i,i],color=PURPLE,lw=5,solid_capstyle='butt')
            ax.text(np.sqrt(lo*hi),i-.25,f'{lo:,.0f}–{hi:,.0f}',ha='center',fontsize=10,color=PURPLE)
        ax.axhline(3.5,color='#D3DDE2',ls=':')
        ax.set_xlabel('Concurrent sessions (millions) · log scale',fontsize=10)
    fig.legend([Line2D([],[],color=PURPLE,lw=5),Line2D([],[],color='#DED8EC',lw=12)],
               ['2× HBM4 uplift; labels show this range','Broader 1–4× HBM4 uplift'],loc='lower left',bbox_to_anchor=(.20,.09),ncol=2,frameon=False,fontsize=11)
    footer(fig,'Bars are scenario ranges, not confidence intervals or measured model serving costs.\nPeak >500k rows include whole groups that ever exceeded the threshold and overlap their parent cohorts.')
    fig.subplots_adjust(left=.235,right=.97,top=.78,bottom=.24,wspace=.16)
    results.append(save(fig,'b1_closed_scenarios','B1 — Separate Claude/GPT figure. Each row shows the 5–10× economic-assumption range; pale extensions add the 1–4× HBM4 uplift sensitivity. Side-by-side panels distinguish shipment horizons. Numbers label the central 2×-uplift range, not the pale outer endpoints.'))
    fig,axes=plt.subplots(1,2,figsize=(13.4,7.8),sharey=True)
    title(fig,'Open-model capacity at two response-speed targets',
          'GB300 AgentX benchmarks · P90 streaming speed · full memory allocation')
    for ax,year in zip(axes,[2026,2027]):
        setup(ax,[r['label'] for r in opened]);ax.set_title(f'2025–{str(year)[-2:]} shipments',loc='left',pad=15)
        ax.set_xlim(25,5000);ax.set_xticks([25,50,100,250,500,1000,2500,5000],['25','50','100','250','500','1,000','2,500','5,000'])
        for i,r in enumerate(opened):
            for ep,color,marker,offset in [('high',TEAL,'o',-.20),('low',ORANGE,'^',.20)]:
                y=i+offset
                lo,mid,hi=[value(r,year,u,ep) for u in (1,2,4)]
                ax.plot([lo,hi],[y,y],color=color,lw=2,alpha=.5)
                ax.plot(mid,y,marker,color=color,ms=8)
                ax.text(mid,y-.12,f'{mid:,.0f}',ha='center',fontsize=10,color=color)
        ax.set_ylim(3.7,-.7);ax.set_xlabel('Concurrent sessions (millions) · log scale',fontsize=10)
    fig.legend([Line2D([],[],color=TEAL,marker='o',lw=2),Line2D([],[],color=ORANGE,marker='^',lw=2)],
               ['50 tokens/s/user','100 tokens/s/user'],loc='lower left',bbox_to_anchor=(.20,.09),ncol=2,frameon=False,fontsize=11)
    footer(fig,'Markers and labels: 2× HBM4 uplift. Whiskers: 1–4× uplift at each fixed speed target.\nConfigured session trees include waiting; models are not capability-equivalent. Speed excludes time to first token.')
    fig.subplots_adjust(left=.205,right=.97,top=.78,bottom=.24,wspace=.16)
    results.append(save(fig,'b2_open_scenarios','B2 — Separate open-model figure. Speed targets get distinct rows/markers rather than endpoints of one range. Each whisker now has one meaning only: HBM4 uplift from 1× to 4× at a fixed speed target. The two shipment horizons share an axis; this figure uses a wider capacity domain than B1.'))
    return results


def matrix(closed,opened):
    fig,axes=plt.subplots(2,1,figsize=(12.6,9.8),gridspec_kw={'height_ratios':[1.5,1]})
    title(fig,'Model scenarios at a glance',
          'Potential concurrent sessions, in millions · central 2× HBM4 uplift · full allocation')
    norm=LogNorm(5,2500);cmap=plt.get_cmap('PuBuGn')
    for ax,rows,heading,sub in [(axes[0],closed,'Claude/GPT · assumed revenue/cost ratio',['5×','10×']),
                               (axes[1],opened,'Open models · P90 streaming speed',['100 tokens/s/user','50 tokens/s/user'])]:
        values=np.array([[value(r,y,2,ep) for y in (2026,2027) for ep in ('low','high')] for r in rows])
        ax.imshow(values,cmap=cmap,norm=norm,aspect='auto')
        ax.set_title(heading,loc='left',pad=48)
        ax.set_yticks(range(len(rows)),[r['label'] for r in rows],fontsize=11)
        ax.set_xticks(range(4),sub*2,fontsize=10.5);ax.xaxis.tick_top()
        for x,label in [(.25,'2025–26 shipments'),(.75,'2025–27 shipments')]:
            ax.text(x,1.15,label,transform=ax.transAxes,ha='center',fontsize=11,weight='bold')
        for (i,j),v in np.ndenumerate(values):ax.text(j,i,f'{v:,.0f}',ha='center',va='center',fontsize=14,color=cell_color(cmap(norm(v))))
        ax.spines[:].set_visible(False);ax.tick_params(length=0)
        ax.set_xticks(np.arange(-.5,4),minor=True);ax.set_yticks(np.arange(-.5,len(rows)),minor=True)
        ax.grid(which='minor',color='white',lw=3);ax.tick_params(which='minor',length=0)
        ax.axvline(1.5,color='white',lw=8)
    footer(fig,'Darker cells mean greater capacity; cell values are authoritative. Fixed uplift: no uncertainty range shown.\nPeak >500k subsets overlap full cohorts. Different evidence types—not comparisons of equal-capability agents.')
    fig.subplots_adjust(left=.275,right=.97,top=.77,bottom=.12,hspace=.65)
    return save(fig,'c_scenario_matrix','C — Numeric scenario matrix. Most convenient for reading off and quoting a capacity, rather than tracing a curve. Both sections use the same color mapping, but clearly different column assumptions: revenue/cost multiples for Claude/GPT and response-speed targets for open models. All figures are millions of sessions at 2× uplift; no broader envelope is shown.')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    headline.main()  # Recompute the source rather than silently reusing stale measurements.
    theme()
    frame=pd.read_csv(ROOT/'polished_figures/headline_candidate/model_measurements.csv')
    closed=frame[frame.evidence=='assumed'].to_dict('records')
    opened=frame[frame.evidence=='benchmark'].to_dict('records')
    entries=[overview(closed,opened),*split(closed,opened),matrix(closed,opened)]
    frame.to_csv(OUT/'model_measurements.csv',index=False)
    (OUT/'captions.json').write_text(json.dumps(entries,indent=2)+'\n')
    sections=[]
    for e in entries:
        links=' · '.join(f'<a href="{e["name"]}.{ext}">{ext.upper()}</a>' for ext in ['png','svg','pdf'])
        sections.append(f'<section><h2>{html.escape(e["caption"].split(" — ")[0])}</h2><img src="{e["name"]}.svg" alt="{html.escape(e["caption"],quote=True)}"><p>{html.escape(e["caption"])}</p>{links}</section>')
    (OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Headline alternatives</title><style>body{max-width:1150px;margin:30px auto;padding:20px;font:17px/1.6 system-ui;color:#203448;background:#f6f8f9}section{background:white;padding:24px;margin:30px 0;border:1px solid #d8e2e6;border-radius:8px}img{width:100%}a{color:#177782}</style><h1>Three ways to tell the headline story</h1><p><b>Recommendation:</b> A for a compact headline overview; B1 + B2 if the full scenario ranges matter more than fitting everything in one image. C is the easiest to use as a numerical reference.</p><p>All use the same frozen report inputs and reproduce the previous candidate's values. No report edits. A and C deliberately fix memory uplift at 2×; B retains the 1–4× sensitivity. Long-context subsets overlap full cohorts. Models differ in capability, workload, harness, and available session timing.</p>'''+''.join(sections)+'<p><a href="model_measurements.csv">All numerical inputs</a> · <a href="../headline_candidate/README.md">Full methodology</a> · <a href="../headline_candidate/index.html">Original candidate</a></p></html>')
    print(OUT/'index.html')


if __name__=='__main__':main()
