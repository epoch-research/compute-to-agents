"""Low-density headline layouts; same frozen report arithmetic."""
import json
import html
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import NullLocator
from .paths import ROOT
from . import headline, benchmark_figures as b
from .headline_alternatives import value
from .polish import theme, clean, PURPLE, TEAL, MUTED

OUT=ROOT/'polished_figures'/'headline_simple'


def header(fig,title,sub):
    fig.text(.045,.96,title,fontsize=23,weight='bold',va='top')
    fig.text(.045,.885,sub,fontsize=13,color=MUTED,va='top')


def save(fig,name,caption):
    fig.canvas.draw()
    for t in fig.texts:
        box=t.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
        assert box.x0>=0 and box.x1<=1 and box.y0>=0 and box.y1<=1,t.get_text()
    for ext in ['png','svg','pdf']:fig.savefig(OUT/f'{name}.{ext}',dpi=220)
    plt.close(fig)
    return dict(name=name,caption=caption)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    headline.main();theme()
    df=pd.read_csv(ROOT/'polished_figures/headline_candidate/model_measurements.csv')
    closed=df[(df.evidence=='assumed')&~df.high_context.fillna(False).astype(bool)].to_dict('records')
    opened=df[df.evidence=='benchmark'].to_dict('records')
    assert len(closed)==len(opened)==4
    entries=[]
    common=('All estimates use cumulative eligible memory shipped since 2025 through 2027, full allocation, '
            'and the central 2× HBM4 concurrency uplift. Claude/GPT ranges vary only the assumed revenue/serving-cost ratio '
            'from 5× to 10×, using TraceLab pooled API-equivalent hourly spending. Open-model points use GB300 '
            'frontiers at P90 50 output tokens/s/user. This is not an equal-capability or equal-task comparison; '
            'source session clocks and benchmark session-tree clocks differ. Historical report inputs are unchanged. '
            'Long-context subsets, the 100-token/s target, 2026 horizon, and broader 1–4× uplift are deliberately omitted.')
    # 1. All models, one shared capacity scale; no intermediate cost axis.
    fig,ax=plt.subplots(figsize=(11.8,8.2))
    header(fig,'Potential agent capacity, by model scenario','Memory shipped through 2027 · central memory assumption')
    labels=[r['label'] for r in closed+opened]
    positions=[0,1,2,3,5,6,7,8]
    for i,r in enumerate(closed+opened):
        y=positions[i]
        lo,hi=value(r,2027,2,'low'),value(r,2027,2,'high')
        if i<4:
            ax.plot([lo,hi],[y,y],lw=7,color=PURPLE,solid_capstyle='butt')
            ax.text(hi*1.12,y,f'{lo:.0f}–{hi:.0f} million',va='center',fontsize=13,color=PURPLE)
        else:
            ax.plot(hi,y,'o',color=TEAL,ms=9)
            ax.text(hi*1.12,y,f'{hi:,.0f} million',va='center',fontsize=13,color=TEAL)
    ax.text(0,4.15,'Open benchmarks · 50 tokens/s/user (P90)',transform=ax.get_yaxis_transform(),fontsize=13,weight='bold',color=TEAL)
    ax.set_title('Claude/GPT · assumed revenue/cost ratio of 5–10×',loc='left',fontsize=13,color=PURPLE,pad=14)
    ax.set_yticks(positions,labels,fontsize=13);ax.set_ylim(8.6,-.7)
    ax.set_xscale('log');ax.set_xlim(20,4000);ax.set_xticks([25,100,500,2000],['25','100','500','2,000']);ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlabel('Concurrent sessions (millions) · logarithmic scale',fontsize=13,labelpad=14);clean(ax)
    fig.text(.045,.03,'Different workloads and evidence—not equally capable agents. Full assumptions in caption.',fontsize=11,color=MUTED)
    fig.subplots_adjust(left=.28,right=.96,top=.765,bottom=.16)
    entries.append(save(fig,'1_all_models','1 — All models, fewer moving parts. One year, one memory-uplift assumption, and one open-model speed target. Values sit beside the marks, with only four axis ticks. '+common))
    # 2. Two independent, linear-scale figures, not a shared-axis comparison.
    for key,rows in [('closed',closed),('open',opened)]:
        fig,ax=plt.subplots(figsize=(10.7,6.1))
        isclosed=key=='closed'
        header(fig,'Claude/GPT capacity scenarios' if isclosed else 'Open-model benchmark capacity',
               'Through-2027 memory · central uplift · full allocation')
        for i,r in enumerate(rows):
            lo,hi=value(r,2027,2,'low'),value(r,2027,2,'high')
            if isclosed:
                ax.plot([lo,hi],[i,i],lw=10,color=PURPLE,solid_capstyle='butt')
                ax.text(hi+7,i,f'{lo:.0f}–{hi:.0f}',va='center',color=PURPLE,fontsize=15,weight='bold')
            else:
                ax.barh(i,hi,height=.38,color=TEAL)
                ax.text(hi+35,i,f'{hi:,.0f}',va='center',color=TEAL,fontsize=15,weight='bold')
        ax.set_yticks(range(4),[r['label'] for r in rows],fontsize=14);ax.set_ylim(3.65,-.65)
        ax.set_xlim(0,250 if isclosed else 2400)
        ax.set_xticks([0,50,100,150,200] if isclosed else [0,500,1000,1500,2000])
        ax.set_xticklabels(['0','50','100','150','200'] if isclosed else ['0','500','1,000','1,500','2,000'],fontsize=12)
        ax.set_xlabel('Potential concurrent sessions (millions)',fontsize=13,labelpad=13);clean(ax)
        fig.text(.045,.04,'Range: assumed revenue/cost ratio of 5–10×; not a confidence interval.' if isclosed else 'GB300 benchmarks · P90 50 output tokens/s/user · not equal-capability workloads.',fontsize=11,color=MUTED)
        fig.subplots_adjust(left=.30,right=.97,top=.76,bottom=.20)
        entries.append(save(fig,f'2_{key}','2 — Split into simple linear-scale figures. Each contains four models and no legend. The two charts deliberately have different horizontal ranges (0–250 versus 0–2,400 million); compare the numbers, not bar lengths across charts. '+common))
    # 3. Headline = headline assumption, model breakdown belongs later.
    fig,ax=plt.subplots(figsize=(10.7,5.7))
    header(fig,'Tens of millions of concurrent agents','Central closed-model scenario · $30 per session-hour')
    for i,y in enumerate([2026,2027]):
        lo,hi=b.capacity(y),b.capacity(y,K=10)
        ax.plot([lo,hi],[i,i],lw=15,color=TEAL,solid_capstyle='butt')
        ax.text((lo+hi)/2,i-.26,f'{lo:.0f}–{hi:.0f} million',ha='center',fontsize=19,weight='bold',color=TEAL)
    ax.set_yticks([0,1],['Shipments through 2026','Shipments through 2027'],fontsize=14)
    ax.set_ylim(1.6,-.7);ax.set_xlim(0,125);ax.set_xticks([0,25,50,75,100,125]);clean(ax)
    ax.set_xlabel('Potential concurrent sessions (millions)',fontsize=13,labelpad=12)
    fig.text(.045,.03,'Memory shipments since 2025, once deployed and fully allocated—not agents active at year-end.',fontsize=11,color=MUTED)
    fig.subplots_adjust(left=.34,right=.96,top=.73,bottom=.23)
    entries.append(save(fig,'3_headline_only','3 — Separate the headline from the evidence. Show just the report’s central closed-model scenario; put the model-specific charts later. This retains both shipment horizons but fixes spending at $30 per session-hour, GB300 reference rent at $5/hour, HBM4 concurrency uplift at 2×, and allocation at 100%. Ranges reflect the assumed revenue/serving-cost ratio of 5–10× only. It does not summarize the full model range, include open-model scenarios, or show the broader memory sensitivity.'))
    df.to_csv(OUT/'model_measurements.csv',index=False)
    (OUT/'captions.json').write_text(json.dumps(entries,indent=2)+'\n')
    blocks=[]
    for e in entries:
        blocks.append(f'<section><img src="{e["name"]}.svg" alt="{html.escape(e["caption"],quote=True)}"><p>{html.escape(e["caption"])}</p>'+ ' · '.join(f'<a href="{e["name"]}.{x}">{x.upper()}</a>' for x in ['png','svg','pdf'])+'</section>')
    (OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Simpler headline figures</title><style>body{max-width:1080px;margin:30px auto;padding:20px;font:18px/1.6 system-ui;color:#203448;background:#f5f7f8}section{padding:25px;margin:25px 0;background:white;border:1px solid #dde4e8;border-radius:8px}img{width:100%}a{color:#177782}</style><h1>Less information, larger type</h1><p>1 keeps every main model in one chart. 2 splits closed and open scenarios into simple linear-scale charts. 3 puts just the central scenario up front and moves model detail later. No source calculations or report content were changed.</p>'''+''.join(blocks)+'<p><a href="model_measurements.csv">Numerical data</a> · <a href="../headline_candidate/README.md">Underlying methodology</a></p></html>')
    print(OUT/'index.html')


if __name__=='__main__':main()
