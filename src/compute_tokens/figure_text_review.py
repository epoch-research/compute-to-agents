"""Draft 2's ten figures: text-only review, preserving plotted artists exactly.

Run python -m compute_tokens.figure_text_review. Original artwork is retained.
"""
import hashlib
import html
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.text import Text
import numpy as np
import pandas as pd

from . import polish as p, distributions as d, serving_curve
from .paths import ROOT, DATA, REFERENCE

OUT = ROOT / 'polished_figures' / 'draft2_text_review'
RENUMBER = {str(i): str(i+1) for i in range(1, 8)} | {'A1':'A1', 'A2':'A2'}
MULTIPLIERS = 'Multipliers give agents per unit of memory on HBM4/4E systems relative to HBM3E.'
BENCH_SOURCE = 'Source: SemiAnalysis InferenceX/AgentX'
CREDITS = {
    '1':'Sources: TrendForce, SemiAnalysis InferenceX/AgentX, TraceLab',
    '2':BENCH_SOURCE, '3':BENCH_SOURCE, 'A1':BENCH_SOURCE, 'A2':BENCH_SOURCE,
    '4':'Sources: TraceLab; API pricing from OpenAI and Anthropic',
    '5':'Sources: TraceLab, SemiAnalysis’s WEKA trace dataset',
    '6':'Sources: TrendForce, SemiAnalysis', '7':'Sources: TrendForce, SemiAnalysis',
    '8':'Sources: TrendForce, SemiAnalysis InferenceX/AgentX',
}
TITLES = {
    '2':'Higher streaming speeds generally allow fewer concurrent agents',
    'A1':'Higher streaming speeds generally allow fewer concurrent agents',
    '3':'Concurrent agents per GPU at different streaming speeds',
    'A2':'Concurrent agents per GPU at a streaming-speed target of 200 tokens/s/user',
    '4':'Hourly agent spending varies across models and harnesses',
    '6':'Potential agent capacity grows with cumulative HBM supply',
    '7':'Estimated agent capacity at different levels of API spending',
    '8':'Potential agent capacity using DeepSeek V4 Pro benchmarks',
}


def plot_signature(fig):
    """Data, geometry, scales, colors and encodings; deliberately excludes text."""
    def arr(x):
        return np.asarray(x).tolist()
    axes=[]
    for ax in fig.axes:
        axes.append(dict(position=arr(ax.get_position().bounds), xlim=arr(ax.get_xlim()),
            ylim=arr(ax.get_ylim()), scales=[ax.get_xscale(),ax.get_yscale()],
            ticks=[arr(ax.get_xticks()),arr(ax.get_yticks())],
            lines=[dict(x=arr(l.get_xdata()),y=arr(l.get_ydata()),c=l.get_color(),
                        lw=l.get_linewidth(),ls=l.get_linestyle(),marker=l.get_marker(),
                        ms=l.get_markersize(),alpha=l.get_alpha()) for l in ax.lines],
            collections=[dict(paths=[arr(v.vertices) for v in c.get_paths()],
                offsets=arr(c.get_offsets()),face=arr(c.get_facecolors()),edge=arr(c.get_edgecolors()),
                widths=arr(c.get_linewidths()),alpha=c.get_alpha()) for c in ax.collections],
            images=[dict(data=arr(im.get_array()),clim=im.get_clim(),
                         colors=arr(im.cmap(np.linspace(0,1,256)))) for im in ax.images],
            patches=[dict(vertices=arr(v.get_path().vertices),transform=arr(v.get_transform().get_matrix()),
                          face=v.get_facecolor(),edge=v.get_edgecolor()) for v in ax.patches]))
    return hashlib.sha256(json.dumps(axes,sort_keys=True,default=str).encode()).hexdigest()


def replace(fig, old, new):
    found=[t for t in fig.findobj(Text) if t.get_text()==old]
    assert found, f'Missing text: {old}'
    for t in found:
        t.set_text(new)
    return found


def revise(fig, number):
    if number in TITLES:
        next(t for t in fig.texts if t.get_gid()=='figure-title').set_text(TITLES[number])
    subtitle = next((t for t in fig.texts if t.get_gid()=='figure-subtitle'),None)
    footer = next((t for t in fig.texts if t.get_gid()=='figure-footnote'),None)
    if number=='1':
        replace(fig,'How many AI agents could the compute buildout support?',
                'How serving cost shapes potential agent capacity')
        replace(fig,'Estimated hardware cost on a GPU-rental basis, rather than the API price paid by users',
                'Serving cost estimated from GPU rental prices. Both axes use logarithmic scales.')
        replace(fig,'Model labels use the central hardware assumption. Each estimate assumes the hardware serves that workload.\nModels differ in capability, workload, and activity accounting. Shipment years do not indicate deployment dates.',
                'Model labels use the central hardware assumption. Models differ in capability, workload, and how agent-hours are measured.\nShipment years do not indicate deployment dates. M = million; B = billion.')
    elif number in ('2','A1'):
        stat='P90' if number=='2' else 'median'
        subtitle.set_text(f'Published AgentX benchmarks · {stat} streaming speed · logarithmic axes')
        footer.set_text('Speed excludes time to first token. Lines may connect configurations with different serving software and hardware layouts.')
    elif number in ('3','A2'):
        subtitle.set_text('Each agent session includes its subagents; values are per physical GPU.')
        starred=any(t.get_text().endswith('*') for ax in fig.axes for t in ax.texts)
        footer.set_text(('* Highest measured concurrency used because its streaming speed still exceeds the target.\n' if number=='3' or starred else '')+
                        '— No benchmark result meeting the target.')
    elif number=='4':
        subtitle.set_text('Codex and Claude Code sessions from TraceLab')
        replace(fig,'API-equivalent cost per agent-hour (US$)','API-equivalent spending per agent-hour (US$)')
        replace(fig,'Pooled','Pooled rate')
        subset=replace(fig,'Subsets: peak context >500k','Subsets: peak context\n>500,000 tokens')
        subset+=replace(fig,'Whole agent sessions; overlap the rows above',
                'Rates cover each full session/model group;\nthese groups are included above.')
        for text in subset:
            text.set_y(4.28)
        footer.set_text('Pooled rate = total spending ÷ total adjusted hours, including short groups.\n'
                        'n = plotted session/model groups with at least five primary active minutes; see Appendix A for definitions.')
    elif number=='5':
        replace(fig,'Non-read input','Input not read from cache')
        replace(fig,'Million tokens per agent-hour','Tokens per agent-hour (millions)')
        replace(fig,'Thousand tokens per agent-hour','Tokens per agent-hour (thousands)')
        replace(fig,'Pooled','Pooled rate')
        footer.set_text('Circles mark medians. Nonlinear x-axes include zero; scales differ by token type.\n'
                        'Calculated from the original traces before benchmark replay. Session and cache accounting differ between datasets.')
    elif number in ('6','7','8'):
        for end in ('26','27'):
            replace(fig,f'2025–{end} shipments',f'2025–{end} HBM shipments')
        replace(fig,'2× HBM4 concurrency uplift','Central hardware assumption: 2×')
        replace(fig,'1–4× HBM4 concurrency uplift','Alternative hardware assumptions: 1–4×')
        if number=='6':
            fig.axes[0].set_yticks([0,1],['2025–26 HBM shipments','2025–27 HBM shipments'])
            subtitle.set_text('$30 in API spending per agent-hour · revenue/cost ratio of 5–10× · $5 per GB300-hour · full allocation')
        if number=='7':
            replace(fig,'API-equivalent cost per agent-hour (US$)','API-equivalent spending per agent-hour (US$)')
            replace(fig,'$30 reference','$30 per agent-hour reference')
        if number=='8':
            subtitle.set_text('GB300 benchmarks at two streaming-speed targets; full allocation to this workload.')
            replace(fig,'50 tokens/s/user','P90: 50 tokens/s/user')
            replace(fig,'100 tokens/s/user','P90: 100 tokens/s/user')
            fig.axes[0].set_yticks([0,1],['P90: 50 tokens/s/user','P90: 100 tokens/s/user'])
            fig.axes[0].tick_params(axis='y',labelsize=10)
            footer.set_text('The two speed targets are alternative uses of the same hardware supply. Shipment years do not indicate deployment dates.')
    # Credits fit below the existing notes without moving any plotted artists.
    fig.text(.035,.004,CREDITS[number],fontsize=8,color=p.MUTED,va='bottom')
    # Fit only changed text; no axes positions, colors, or plotted values change.
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    for t in fig.texts:
        box=t.get_window_extent(renderer).transformed(fig.transFigure.inverted())
        if box.x1>.98:
            t.set_fontsize(t.get_fontsize()*(.98-box.x0)/box.width)
    fig.canvas.draw()


class Review:
    def __init__(self):
        (OUT/'figures').mkdir(parents=True,exist_ok=True)
        self.pdf=PdfPages(OUT/'all_figures.pdf')
        self.entries=[]

    def save(self,fig,old,title,caption,alt,sources):
        self.emit(fig,RENUMBER[old],p.FILES[old],caption)

    def emit(self,fig,number,old_stem,caption,opening=False):
        fig.canvas.draw()
        before=plot_signature(fig)
        if not opening:
            revise(fig,number)
        assert before==plot_signature(fig),f'Non-text plot changed: {number}'
        renderer=fig.canvas.get_renderer()
        for text in fig.texts:
            box=text.get_window_extent(renderer).transformed(fig.transFigure.inverted())
            assert -.001<=box.x0 and box.x1<=1.001 and -.001<=box.y0 and box.y1<=1.001, text.get_text()
        source=CREDITS[number]
        if not opening and number.isdigit():
            old_number=number
            # Draft 2 caption order verified September 21, 2026.
            number={'1':'6','2':'2','3':'3','4':'4','5':'5','6':'7','7':'8','8':'9'}[number]
            caption=caption.replace(f'Figure {old_number}.',f'Figure {number}.')
        stem=f'figure_{number.lower()}'
        for ext in ('png','svg','pdf'):
            fig.savefig(OUT/'figures'/f'{stem}.{ext}',dpi=240)
        self.pdf.savefig(fig)
        texts=[t.get_text() for t in fig.findobj(Text) if t.get_text()]
        self.entries.append(dict(number=number,stem=stem,previous_stem=old_stem,
            source=source,plot_signature=before,methodology=caption,text=texts))
        plt.close(fig)


def main():
    p.theme()
    review=Review()
    from . import opening_capacity
    opening_capacity.main()
    opening_rows=opening_capacity.measurements(pd.read_csv(ROOT/'polished_figures/serving_cost_curve/model_measurements.csv'))
    review.emit(opening_capacity.draw(opening_rows),'1','opening_capacity',opening_capacity.CAPTION,opening=True)
    # Derive headline anchors from frozen inputs using the established calculator.
    from . import headline
    headline.main()
    frame=pd.read_csv(ROOT/'polished_figures/headline_candidate/model_measurements.csv')
    p.theme()
    df=pd.read_csv(REFERENCE/'inferencex_prepared.csv')
    estimates=p.b.r.estimates(df,'latest')
    raw=json.loads((DATA/'token_groups.json').read_text())
    costs=[dict(r,dataset='TraceLab',hours_primary=r['hours_uncapped']) for r in json.loads((DATA/'cost_groups.json').read_text())]
    records=d.build_records(costs+d.choose(raw,'WEKA'),raw)
    d.validate(costs+d.choose(raw,'WEKA'),raw,records)
    p.frontiers(review,df,'p90');p.matrix(review,estimates,[50,100])
    p.costs(review,records);p.tokens(review,records)
    serving_curve.main(frame=frame,capture=lambda fig: review.emit(fig,'1','serving_cost_capacity',
        serving_curve.REPORT_CAPTION))
    p.theme()
    p.projections(review,estimates)
    p.frontiers(review,df,'median');p.matrix(review,estimates,[200])
    review.pdf.close()
    counts={ds:dict(total=len(rows:=d.choose(raw,ds)),plotted=sum(r['hours_primary']>=1/12 and r['hours_cap300']>0 for r in rows)) for ds in ('TraceLab','WEKA')}
    note=(f"Pooled rate = total tokens ÷ total adjusted hours. n counts plotted eligible units: "
        f"TraceLab {counts['TraceLab']['plotted']:,} session/model groups; WEKA {counts['WEKA']['plotted']:,} root session trees including parent and subagent calls. "
        "Both require at least five primary active minutes and positive adjusted hours. "
        f"Pooled rates use all {counts['TraceLab']['total']:,} TraceLab groups and {counts['WEKA']['total']:,} WEKA trees, including short units.")
    md='# Report figure bundle\n\nLocal artwork only; no Google Doc edits. Order matched to Draft 2 captions September 21, 2026: opening chart (1), P90 curves (2), heatmaps (3), spending distributions (4), token distributions (5), serving-cost/capacity curve (6), cumulative supply (7), spending sensitivity (8), DeepSeek capacity (9). A1 and A2 unchanged.\n\n'
    md+='## Figure 1 caption\n\n'+opening_capacity.CAPTION+'\n\n'
    md+='## Figure 5 accompanying note\n\n'+note+'\n\n## Figures 7–9 accompanying note\n\n'+MULTIPLIERS+'\n\n'
    urls=dict(p.SOURCES)
    urls['supply']=('TrendForce supply sources',json.loads((DATA/'assumptions.json').read_text())['source_urls'][:3])
    md+='## Sources\n\n'+'\n'.join(f'- {v[0]}: {v[1]}' for v in urls.values())+'\n'
    (OUT/'notes.md').write_text(md)
    (OUT/'metadata.json').write_text(json.dumps(dict(figures=review.entries,figure5_counts=counts,figure5_note=note,sources=urls,
        checks={'all_ten_plot_signatures_unchanged':True,'frozen_distribution_validation_passed':True}),indent=2)+'\n')
    sections=''.join(f'<section><h2>Figure {e["number"]}</h2><img src="figures/{e["stem"]}.svg"><p><a href="figures/{e["stem"]}.pdf">PDF</a> · <a href="figures/{e["stem"]}.png">PNG</a> · <a href="figures/{e["stem"]}.svg">SVG</a></p></section>' for e in review.entries)
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Report figures</title><style>body{max-width:1200px;margin:30px auto;font:17px/1.5 system-ui;color:#203448}img{width:100%}section{margin:40px 0}</style><h1>Report figures</h1><p>Approved opening figure followed by the existing figures, renumbered without changes to their content.</p><p><a href="all_figures.pdf">All eleven figures in one PDF</a> · <a href="notes.md">Accompanying notes and sources</a></p>'+sections)
    from zipfile import ZipFile, ZIP_DEFLATED
    with ZipFile(OUT.parent/'draft2-revised-figures.zip','w',ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                archive.write(path,path.relative_to(OUT))
    print(OUT/'all_figures.pdf')
    print(json.dumps(counts))


if __name__=='__main__':
    main()
