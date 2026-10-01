"""September 23 design handoff: requested text substitutions only."""
import json
import re
import matplotlib.pyplot as plt
from matplotlib.text import Text
import pandas as pd
from . import polish as p, distributions as d, design_tick_preview as latest
from .figure_text_review import revise, replace, plot_signature
from .paths import ROOT, DATA, REFERENCE

OUT = ROOT / 'polished_figures/figures-update'
EXPORT_FORMATS = ('svg', 'png', 'pdf')
POSTPROCESS = None
FINALIZE = None
SUBTITLES = {
    '2': 'Published AgentX benchmarks. P90 streaming speed. Both axes use logarithmic scales.',
    'A1': 'Published AgentX benchmarks. Median streaming speed. Both axes use logarithmic scales.',
    '5': 'Pooled Claude workloads with a five-minute gap cap and retained-cache comparison.',
    '7': 'Assumes $30 in API spending per agent-hour, a revenue/cost ratio of 5–10×, $5 per GB300-hour, and full allocation.',
    '8': 'Assumes a revenue/cost ratio held at 5–10×, $5 per GB300-hour, and full allocation.',
}


def export(fig, number):
    before = plot_signature(fig)
    if number in SUBTITLES:
        next(t for t in fig.texts if t.get_gid() == 'figure-subtitle').set_text(SUBTITLES[number])
    if number in ('3', 'A2'):
        replace(fig, 'Agent sessions per GPU · logarithmic color scale', 'Agent sessions per GPU (logarithmic color scale)')
    if number == '4':
        for t in fig.findobj(Text):
            match = re.fullmatch(r'(Codex|Claude Code) · n = ([\d,]+)( \(small sample\))?', t.get_text())
            if match:
                t.set_text(f'{match[1]} (n = {match[2]}' + ('; small sample)' if match[3] else ')'))
        replace(fig, 'Box: middle 50% · thick whiskers: middle 80% · dark tick: median · faint line: full range',
                'Boxes show the middle 50%, thick whiskers the middle 80%, dark ticks the median, and faint lines the full range.')
    if number == '5':
        replace(fig, 'TraceLab · n = 1,883', 'TraceLab (n = 1,883)')
        replace(fig, 'AgentX source traces (WEKA) · n = 388', 'AgentX source traces (WEKA; n = 388)')
    if number == '6':
        replace(fig, 'Reference serving cost per agent-hour (US$)', 'Reference serving cost per agent-hour (US$, log scale)')
        replace(fig, 'Potential concurrent agents', 'Potential concurrent agents (log scale)')
        replace(fig, 'Serving cost estimated from GPU rental prices. Both axes use logarithmic scales.', 'Serving cost estimated from GPU rental prices.')
    if POSTPROCESS is not None:
        POSTPROCESS(fig, number)
    assert before == plot_signature(fig), number
    if FINALIZE is not None:
        FINALIZE(fig, number)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for t in fig.texts:
        box = t.get_window_extent(renderer).transformed(fig.transFigure.inverted())
        if box.x1 > .98:
            t.set_fontsize(t.get_fontsize() * (.98 - box.x0) / box.width)
    fig.canvas.draw()
    for t in fig.texts:
        box = t.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
        assert -.001 <= box.x0 and box.x1 <= 1.001 and -.001 <= box.y0 and box.y1 <= 1.001, t.get_text()
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in EXPORT_FORMATS:
        fig.savefig(OUT / f'figure_{number.lower()}.{ext}', dpi=240)
    plt.close(fig)


class Gallery:
    def save(self, fig, old, *args):
        if old == '7':
            plt.close(fig)
            return  # Figure 9 unchanged.
        historical = str(int(old) + 1) if old.isdigit() else old
        revise(fig, historical)
        number = {'6': '7', '7': '8'}.get(historical, historical)
        export(fig, number)


def main():
    p.theme()
    df = pd.read_csv(REFERENCE / 'inferencex_prepared.csv')
    estimates = p.b.r.estimates(df, 'latest')
    raw = json.loads((DATA / 'token_groups.json').read_text())
    costs = [dict(r, dataset='TraceLab', hours_primary=r['hours_uncapped']) for r in json.loads((DATA / 'cost_groups.json').read_text())]
    records = d.build_records(costs + d.choose(raw, 'WEKA'), raw)
    gallery = Gallery()
    p.frontiers(gallery, df, 'p90'); p.matrix(gallery, estimates, [50, 100])
    p.costs(gallery, records)
    # Reuse the approved tick/limit/legend changes before text-only verification.
    latest.save = lambda fig, number: export(fig, str(number))
    p.tokens(latest.Tokens(), records)
    latest.serving_curve.main(frame=pd.read_csv(ROOT / 'polished_figures/headline_candidate/model_measurements.csv'), capture=latest.serving)
    p.theme()
    p.projections(gallery, estimates)
    p.frontiers(gallery, df, 'median'); p.matrix(gallery, estimates, [200])
    print(OUT)


if __name__ == '__main__':
    main()
