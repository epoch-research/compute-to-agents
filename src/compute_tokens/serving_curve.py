"""One common serving-cost curve with selected benchmark and inferred anchors."""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator
from . import headline, benchmark_figures as b
from .paths import ROOT
from .polish import theme, clean, TEAL, PURPLE, PALE, INK, MUTED


REPORT_CAPTION=('Figure 1. Potential concurrent agents supported by HBM3E and newer memory shipped during 2025–27, '
    'once fully deployed for the selected workload. The curve converts reference serving cost into capacity using '
    'a common hardware supply estimate. The central line assumes HBM4/4E systems support twice as many agents '
    'per unit of memory as HBM3E systems; shading varies this assumption from one to four times. Open-model '
    'points use GB300 benchmarks at a P90 output speed of 50 tokens per second per user. Closed-model segments '
    'use TraceLab API spending divided by assumed revenue/cost ratios of 5–10×. Serving costs use a reference '
    'rental price of $5 per GB300-hour. Both axes are logarithmic; the ranges represent scenarios, not confidence intervals.')


def main(*, capture=None, frame=None):
    out=ROOT/'polished_figures'/'serving_cost_curve'
    if capture is None:
        out.mkdir(parents=True,exist_ok=True)
    if frame is None:
        headline.main()
        frame=pd.read_csv(ROOT/'polished_figures/headline_candidate/model_measurements.csv')
    theme()
    selected=frame[(frame.model.isin(['dsv4','glm5.2','kimik3','gpt-5.6-sol','claude-fable-5'])) & ~frame.high_context.fillna(False).astype(bool)].copy()
    assert len(selected)==5
    x=np.geomspace(.1,20,500)
    f=lambda x,u=2:b.capacity(2027,u=u,c=5/np.asarray(x))
    fig,ax=plt.subplots(figsize=(12.4,8.0))
    fig.text(.04,.97,'How many AI agents could the compute buildout support?',fontsize=22,weight='bold',va='top')
    fig.text(.04,.916,'Potential capacity from memory shipped during 2025–27, assuming full deployment for the selected workload',fontsize=11.5,color=MUTED)
    neutral_band='#E5E7EB'
    ax.fill_between(x,f(x,1),f(x,4),color=neutral_band)
    ax.plot(x,f(x),color=INK,lw=2.6)
    labels={
        'dsv4':('DeepSeek V4 Pro',(.21,3300)),
        'glm5.2':('GLM-5.2',(.23,210)),
        'kimik3':('Kimi K3',(.72,1050)),
        'gpt-5.6-sol':('GPT-5.6 Sol',(2.5,450)),
        'claude-fable-5':('Claude Fable 5',(4.2,13)),
    }
    for r in selected.to_dict('records'):
        label,pos=labels[r['model']]
        if r['evidence']=='benchmark':
            xx=r['low'];color=TEAL
            ax.plot(xx,f(xx),'o',mfc='white',mec=color,ms=9,mew=2,zorder=5)
            capacity=float(f(xx))
            capacity_label=f'{capacity/1000:.1f}B' if capacity>=1000 else f'{capacity:,.0f}M'
            text=f'{label}\n{capacity_label} agents'
            assert np.isclose(f(xx),b.capacity(2027,c=r['concurrency_50']))
        else:
            segment=np.geomspace(r['low'],r['high'],40);xx=np.sqrt(r['low']*r['high']);color=PURPLE
            ax.plot(segment,f(segment),color=color,lw=7,solid_capstyle='butt',zorder=4)
            ax.plot([r['low'],r['high']],f([r['low'],r['high']]),'o',mfc='white',mec=color,ms=5,mew=1.5,zorder=5)
            text=f'{label}\n{f(r["high"]):.0f}–{f(r["low"]):.0f}M agents'
            assert np.isclose(f(r['low']),b.capacity(2027,S=r['api_hourly'],K=10))
        ax.annotate(text,xy=(xx,float(f(xx))),xytext=pos,textcoords='data',fontsize=12.5,color=color,weight='bold',
                    arrowprops=dict(arrowstyle='-',color=color,lw=1.0,shrinkA=6,shrinkB=8),
                    bbox=dict(facecolor='white',edgecolor='none',alpha=.90,pad=3),va='center',zorder=6)
    ax.set_xscale('log');ax.set_yscale('log');ax.set_xlim(.1,20);ax.set_ylim(5,6000)
    ax.set_xticks([.1,.3,1,3,10],['$0.10','$0.30','$1','$3','$10'])
    ax.set_yticks([10,30,100,300,1000,3000],['10M','30M','100M','300M','1B','3B'])
    ax.xaxis.set_minor_locator(NullLocator());ax.yaxis.set_minor_locator(NullLocator())
    ax.set_xlabel('Reference serving cost per agent-hour (US$)',fontsize=13,labelpad=12)
    ax.set_ylabel('Potential concurrent agents',fontsize=13,labelpad=12)
    clean(ax,'both')
    fig.text(.535,.202,'Estimated hardware cost on a GPU-rental basis, rather than the API price paid by users',
             fontsize=10.3,color=MUTED,ha='center')
    # Matplotlib fills legend columns first: hardware assumptions on row one,
    # model evidence types on row two.
    fig.legend([Line2D([],[],color=INK,lw=2.5),Line2D([],[],color=TEAL,marker='o',mfc='white',lw=0,ms=8),Line2D([],[],color=neutral_band,lw=10),Line2D([],[],color=PURPLE,lw=6)],
               ['Central hardware assumption','Open models: benchmark-based estimates','Alternative hardware assumptions','Closed models: estimates inferred from API spending'],
               loc='lower left',bbox_to_anchor=(.09,.092),ncol=2,frameon=False,fontsize=10.5,columnspacing=2)
    fig.text(.04,.025,'Model labels use the central hardware assumption. Each estimate assumes the hardware serves that workload.\nModels differ in capability, workload, and activity accounting. Shipment years do not indicate deployment dates.',fontsize=10.3,color=MUTED)
    fig.subplots_adjust(left=.105,right=.965,top=.86,bottom=.31)
    if capture is not None:
        return capture(fig)
    fig.canvas.draw()
    for text in fig.texts:
        box=text.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
        assert box.x0>=0 and box.x1<=1 and box.y0>=0 and box.y1<=1,text.get_text()
    for ext in ['png','svg','pdf']:fig.savefig(out/f'serving_cost_capacity.{ext}',dpi=240)
    with PdfPages(out/'serving_cost_axis_comparison.pdf') as pdf:
        pdf.savefig(fig)
        ax.set_yscale('linear');ax.set_ylim(0,5500)
        ax.set_yticks([0,1000,2000,3000,4000,5000],['0','1B','2B','3B','4B','5B'])
        positions={'DeepSeek V4 Pro':(.21,3500),'GLM-5.2':(.35,1600),'Kimi K3':(.8,1050),
                   'GPT-5.6 Sol':(2.3,750),'Claude Fable 5':(6,450)}
        for annotation in ax.texts:
            name=annotation.get_text().split('\n')[0]
            if name in positions:annotation.set_position(positions[name])
        for ext in ['png','svg','pdf']:fig.savefig(out/f'serving_cost_capacity_linear_y.{ext}',dpi=240)
        pdf.savefig(fig)
    plt.close(fig)
    selected.to_csv(out/'model_measurements.csv',index=False)
    pd.DataFrame(dict(serving_usd_per_session_hour=x,low_millions=f(x,1),central_millions=f(x),high_millions=f(x,4))).to_csv(out/'curve_measurements.csv',index=False)
    caption=('Here, agents is shorthand for the accounted agent workloads, not individual model instances: AgentX counts root session trees including subagents, while TraceLab uses session/model groups with incomplete parent/child linkage. Agent-hour labels retain the existing adjusted-session-hour denominator; no accounting or numerical values change. '
        'Potential capacity of cumulative eligible memory shipments since 2025 through 2027, once deployed and fully allocated. '
        'Capacity equals effective GB300 equivalents × $5 per GPU-hour ÷ reference serving cost per session-hour. '
        'The central curve and directly labeled capacity values assume 2× HBM4 concurrency uplift; shading spans 1–4×. '
        'Selected open-model points derive reference serving costs from $5 divided by measured/interpolated GB300 configured sessions per GPU at P90 50 output tokens/s/user. '
        'Sol and Fable segments instead divide their TraceLab pooled API-equivalent spending by an assumed revenue/serving-cost ratio of 5–10×. '
        'Segments follow the central curve; their full memory sensitivity also spans the shaded band over the segment’s horizontal interval. '
        'No central economic ratio is selected: label leaders attach at the geometric midpoint for layout only. '
        'The geometric relationship is an accounting identity, not evidence that model workloads, capabilities, or clocks are equivalent. '
        'Configured AgentX session trees include waiting; TraceLab source-session adjustments differ from replay clocks. '
        'Three open models are shown for label readability; MiniMax is omitted because its cost is close to GLM’s, not because it failed filtering. '
        'Prices, source timing, cache reconstruction, and the September 15 benchmark snapshot remain frozen to the report. '
        'Reference rental costs are not measurements of provider operating expenses. Ranges are scenarios, not confidence intervals.')
    (out/'methodology.txt').write_text(caption+'\n')
    caption=REPORT_CAPTION
    (out/'caption.txt').write_text(caption+'\n')
    (out/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Serving cost and capacity</title><style>body{max-width:1150px;margin:30px auto;padding:20px;font:17px/1.6 system-ui;color:#203448}img{width:100%}a{color:#177782}</style><h1>One curve, selected model anchors</h1><img src="serving_cost_capacity.svg" alt="Continuous log-scale serving-cost curve with DeepSeek, GLM, Kimi benchmark points and Sol and Fable inferred-cost segments"><p>'+caption+'</p><p><a href="serving_cost_capacity.pdf">PDF</a> · <a href="serving_cost_capacity.png">PNG</a> · <a href="serving_cost_capacity.svg">SVG</a> · <a href="model_measurements.csv">Model data</a> · <a href="curve_measurements.csv">Curve data</a></p></html>')
    print(out/'serving_cost_capacity.pdf')
    page=(out/'index.html').read_text()
    page=page.replace('</html>','<h2>Linear capacity axis</h2><img src="serving_cost_capacity_linear_y.svg" alt="The same capacity curve with a zero-based linear vertical axis and unchanged logarithmic cost axis"><p>Only the vertical scale and label positions change. The full memory-uplift envelope remains visible; no data or model estimates change.</p><p><a href="serving_cost_capacity_linear_y.pdf">Linear-y PDF</a> · <a href="serving_cost_axis_comparison.pdf">Both versions in one PDF</a></p></html>')
    (out/'index.html').write_text(page)


if __name__=='__main__':main()
