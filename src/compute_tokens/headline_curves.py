"""Figure 6-style continuous API-hourly-cost curves with labeled workload anchors."""
import json
import html
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator
from .paths import ROOT, DATA
from . import distributions as d, benchmark_figures as b
from .polish import theme, clean, TEAL, PALE, INK, MUTED

OUT=ROOT/'polished_figures'/'headline_curves'


def main():
    OUT.mkdir(parents=True,exist_ok=True);theme()
    combined=PdfPages(OUT/'headline_curve_options.pdf')
    tokens=json.loads((DATA/'token_groups.json').read_text())
    costs=[dict(r,dataset='TraceLab',hours_primary=r['hours_uncapped']) for r in json.loads((DATA/'cost_groups.json').read_text())]
    records=d.build_records(costs+d.choose(tokens,'WEKA'),tokens)
    d.validate(costs+d.choose(tokens,'WEKA'),tokens,records)
    rows=d.figure6_records(records,'retained')
    anchors=[(next(r['pooled'] for r in rows if r['model']==m and not r['high_context']),label) for m,label in [('gpt-5.6-sol','GPT-5.6 Sol'),('claude-fable-5','Claude Fable 5')]]
    x=np.linspace(10,100,361)
    entries=[];measurements=[]
    for key,years,broad in [('1_simple_2027',[2027],False),('2_figure6_with_anchors',[2026,2027],True)]:
        fig,axes=plt.subplots(1,len(years),figsize=(12.4,7.3),squeeze=False,sharey=True)
        fig.text(.04,.96,'How hourly workload cost changes potential agent capacity',fontsize=21,weight='bold',va='top')
        fig.text(.04,.895,'Model labels mark pooled TraceLab spending—not different curves or equal-capability workloads.',fontsize=11.5,color=MUTED)
        for ax,year in zip(axes[0],years):
            low,high=b.capacity(year,x),b.capacity(year,x,K=10)
            if broad:ax.fill_between(x,b.capacity(year,x,u=1),b.capacity(year,x,K=10,u=4),color=PALE)
            ax.fill_between(x,low,high,color=TEAL,alpha=.27)
            ax.plot(x,low,color=TEAL,lw=1.7);ax.plot(x,high,color=TEAL,lw=1.7)
            ax.set_xlim(10,100)
            if broad:
                ax.set_yscale('log');ax.set_ylim(4,650)
                ax.set_yticks([5,10,25,50,100,250,500],['5','10','25','50','100','250','500']);ax.yaxis.set_minor_locator(NullLocator())
            else:
                ax.set_ylim(0,335);ax.set_yticks([0,50,100,150,200,250,300])
            for amount,label in anchors:
                a,z=b.capacity(year,amount),b.capacity(year,amount,K=10)
                ax.axvline(amount,color=INK,ls=':',lw=1,alpha=.55)
                ax.plot([amount,amount],[a,z],color=INK,lw=2.6)
                ax.plot([amount,amount],[a,z],'_',color=INK,ms=10,mew=2)
                ax.text(amount,.98,f'{label}\n${amount:.1f}/hour',transform=ax.get_xaxis_transform(),ha='left',va='top',fontsize=11.5,weight='bold',bbox=dict(facecolor='white',edgecolor='none',alpha=.92,pad=3))
                measurements.append(dict(option=key,year=year,model=label,api_equivalent_usd_per_hour=amount,central_low_millions=a,central_high_millions=z))
                if not broad:
                    ax.annotate(f'{a:.0f}–{z:.0f} million',xy=(amount,(a+z)/2),xytext=(9,0),textcoords='offset points',va='center',fontsize=12,color=INK)
            ax.set_title(f'Shipments through {year}' if broad else f'Memory shipped from 2025 through {year}',loc='left',pad=13,fontsize=13)
            ax.set_xticks([10,30,50,75,100],['$10','$30','$50','$75','$100'])
            ax.set_xlabel('API-equivalent spending per session-hour',fontsize=12,labelpad=13)
            clean(ax,'y')
        axes[0,0].set_ylabel('Potential concurrent sessions (millions)'+ ('\nLogarithmic scale' if broad else ''),fontsize=12,labelpad=11)
        if broad:
            fig.legend([Line2D([],[],color=TEAL,lw=7,alpha=.6),Line2D([],[],color=PALE,lw=10)],['2× HBM4 uplift','Broader 1–4× HBM4 uplift'],loc='lower left',bbox_to_anchor=(.09,.10),ncol=2,frameon=False,fontsize=12)
        else:
            fig.text(.11,.135,'Shaded range: assumed revenue/serving-cost ratio of 5–10×',fontsize=12,color=TEAL)
        fig.text(.04,.025,'$5/GB300-hour · full allocation · '+('shipments since 2025 · revenue/cost ratio: 5–10×' if broad else '2× HBM4 uplift')+'\nNot the effect of API repricing alone: a price change also changes the revenue/cost ratio.',fontsize=10.5,color=MUTED)
        fig.subplots_adjust(left=.10,right=.965,top=.775,bottom=.26,wspace=.17)
        fig.canvas.draw()
        for text in fig.texts:
            box=text.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
            assert box.x0>=0 and box.x1<=1 and box.y0>=0 and box.y1<=1,text.get_text()
        for ext in ['png','svg','pdf']:fig.savefig(OUT/f'{key}.{ext}',dpi=220)
        combined.savefig(fig)
        plt.close(fig)
        caption=('Simpler headline: one year, linear capacity axis, and only the central 2× memory-uplift assumption. ' if not broad else 'Closest to Figure 6: both shipment horizons, matching logarithmic capacity axes, and the wider 1–4× memory-uplift envelope. ')
        caption+='The continuous horizontal axis is pooled API-equivalent spending per adjusted session-hour, not token price. Model labels locate GPT-5.6 Sol ($15.5/hour) and Claude Fable 5 ($50.2/hour) on that axis, using the same retained-cache and 300-second gap-cap TraceLab accounting as Figure 3. Vertical dark segments mark the 5–10× revenue/serving-cost scenario at each anchor, not sampling uncertainty. All underlying assumptions and historical report inputs are unchanged. Differences in observed hourly spending reflect pricing, token mix, model-call density, timing, and sampled workloads—not controlled differences in intrinsic model efficiency. Open-model benchmark results are deliberately omitted because placing them on these same curves would impose the same unverified revenue/cost ratio and source-clock equivalence. Capacity is potential after deployment of cumulative eligible memory shipments since 2025, not a year-end activity forecast.'
        entries.append(dict(name=key,caption=caption))
    combined.close()
    pd.DataFrame(measurements).to_csv(OUT/'model_anchors.csv',index=False)
    pd.DataFrame([dict(year=y,api_equivalent_usd_per_hour=float(s),central_low=b.capacity(y,s),central_high=b.capacity(y,s,K=10),outer_low=b.capacity(y,s,u=1),outer_high=b.capacity(y,s,K=10,u=4)) for y in [2026,2027] for s in x]).to_csv(OUT/'curve_measurements.csv',index=False)
    (OUT/'captions.json').write_text(json.dumps(entries,indent=2)+'\n')
    sections=[]
    for e in entries:
        sections.append(f'<section><img src="{e["name"]}.svg" alt="Continuous cost-to-capacity curve with Sol and Fable workload anchors"><p>{html.escape(e["caption"])}</p>'+ ' · '.join(f'<a href="{e["name"]}.{ext}">{ext.upper()}</a>' for ext in ['png','svg','pdf'])+'</section>')
    (OUT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Continuous headline curves</title><style>body{max-width:1120px;margin:30px auto;padding:20px;font:17px/1.6 system-ui;color:#203448;background:#f5f7f8}section{background:white;padding:24px;margin:24px 0;border:1px solid #dce4e8}img{width:100%}a{color:#177782}</style><h1>Continuous cost curves with two model anchors</h1><p>First: a simpler 2027-only headline. Second: Figure 6 with model annotations. The model labels explain positions on the same continuous cost axis; they do not define separate curves.</p>'+''.join(sections)+'<p><a href="model_anchors.csv">Anchor measurements</a> · <a href="curve_measurements.csv">Full curves</a></p></html>')
    print(OUT/'index.html')


if __name__=='__main__':main()
