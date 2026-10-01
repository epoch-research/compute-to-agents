"""Simplified opening-figure preview; original Figure 1 is never overwritten.

Run: python -m compute_tokens.opening_capacity
"""
import hashlib

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerLine2D
from matplotlib.ticker import NullLocator
import numpy as np
import pandas as pd

from . import benchmark_figures as b
from .polish import theme, clean, TEAL, PURPLE, INK, MUTED
from .figure_text_review import CREDITS
from .paths import ROOT

TITLE = 'How many AI agents could the compute buildout support?'
CAPTION = ('Figure 1. Potential agent capacity under our central hardware assumptions. '
           'Each estimate allocates the same projected hardware supply to the indicated workload. '
           'Models differ in capability and workload. Closed-model ranges reflect alternative '
           'assumptions about serving costs. The horizontal axis is logarithmic.')
ORDER = ['dsv4', 'glm5.2', 'kimik3', 'gpt-5.6-sol', 'claude-fable-5']
NAMES = ['DeepSeek V4 Pro', 'GLM-5.2', 'Kimi K3', 'GPT-5.6 Sol', 'Claude Fable 5']


def measurements(frame):
    rows = []
    for model, name in zip(ORDER, NAMES):
        row = frame.loc[frame.model == model].iloc[0]
        # Open points use the 50-token/s benchmark only, NOT the saved
        # 50–100-token/s sensitivity range in the source CSV.
        high = b.capacity(2027, u=2, c=5 / row.low)
        low = high if row.evidence == 'benchmark' else b.capacity(2027, u=2, c=5 / row.high)
        assert np.isclose(high, row.capacity_2027_u2_high_millions)
        if row.evidence != 'benchmark':
            assert np.isclose(low, row.capacity_2027_u2_low_millions)
        label = (f'{high / 1000:.1f} billion' if high >= 1000 else f'{high:.0f} million') if low == high else f'{low:.0f}–{high:.0f} million'
        rows.append(dict(model=model, name=name, evidence=row.evidence,
                         low_agents=low * 1e6, high_agents=high * 1e6, label=label))
    return rows


def draw(rows):
    theme()
    fig, ax = plt.subplots(figsize=(12.4, 7.4))
    fig.text(.035, .966, TITLE, fontsize=22, weight='bold', va='top')
    fig.text(.035, .903,
             'Potential concurrent agents supported by memory shipped during 2025–27, once fully deployed for the indicated workload',
             fontsize=11.3, color=MUTED, va='top')
    fig.subplots_adjust(left=.25, right=.97, top=.815, bottom=.275)
    ax.set_xscale('log')
    ax.set_xlim(1e7, 7e9)
    ax.set_ylim(4.6, -.6)
    ax.set_xticks([1e7, 1e8, 1e9], ['10 million', '100 million', '1 billion'])
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_yticks([])
    ax.set_xlabel('Concurrent agents (log scale)', fontsize=13, labelpad=14)
    clean(ax, 'x')
    value_text = []
    for y, row in enumerate(rows):
        color = TEAL if row['evidence'] == 'benchmark' else PURPLE
        fig.text(.035, ax.transData.transform((1e7, y))[1] / fig.bbox.height,
                 row['name'], fontsize=13, weight='bold', va='center', color=INK)
        lo, hi = row['low_agents'], row['high_agents']
        if lo == hi:
            ax.plot(hi, y, 'o', color=color, markersize=10, zorder=3)
        else:
            ax.plot([lo, hi], [y, y], color=color, lw=5, solid_capstyle='butt')
            ax.plot([lo, hi], [y, y], '|', color=color, markersize=15, markeredgewidth=2.5)
        value_text.append(ax.annotate(row['label'], xy=(hi, y), xytext=(13, 0),
                        textcoords='offset points', va='center', fontsize=14, weight='bold', color=color))
    open_handle = Line2D([], [], marker='o', color=TEAL, lw=0, ms=8)
    fig.legend([open_handle,
                Line2D([], [], color=PURPLE, lw=4, marker='|', ms=12)],
               ['Open models: benchmark estimates', 'Closed models: inferred estimates'],
               loc='lower left', bbox_to_anchor=(.035, .125), ncol=2,
               frameon=False, fontsize=11, columnspacing=2.5, numpoints=2,
               handler_map={open_handle: HandlerLine2D(numpoints=1)})
    fig.text(.035, .064,
             'Central hardware assumptions. Each estimate assumes all hardware serves the indicated workload.',
             fontsize=10, color=MUTED)
    fig.text(.035, .023, CREDITS['1'], fontsize=9, color=MUTED)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for text in fig.texts + value_text:
        box = text.get_window_extent(renderer).transformed(fig.transFigure.inverted())
        assert 0 <= box.x0 < box.x1 <= 1 and 0 <= box.y0 < box.y1 <= 1, text.get_text()
    for i, text in enumerate(value_text):
        assert not any(text.get_window_extent(renderer).overlaps(other.get_window_extent(renderer)) for other in value_text[i+1:])
    return fig


def main():
    source = ROOT / 'polished_figures/serving_cost_curve/model_measurements.csv'
    if not source.exists():
        from . import serving_curve
        serving_curve.main()
    out = ROOT / 'polished_figures/opening_capacity_preview'
    out.mkdir(parents=True, exist_ok=True)
    original = ROOT / 'polished_figures/draft2_text_review/figures/figure_1.svg'
    before = hashlib.sha256(original.read_bytes()).hexdigest() if original.exists() else None
    rows = measurements(pd.read_csv(source))
    fig = draw(rows)
    for ext in ('png', 'svg', 'pdf'):
        fig.savefig(out / f'opening_capacity.{ext}', dpi=240)
    plt.close(fig)
    pd.DataFrame(rows).to_csv(out / 'measurements.csv', index=False)
    (out / 'caption.txt').write_text(CAPTION + '\n')
    (out / 'README.md').write_text('# Opening capacity preview\n\n'
        'Reproduce: `.venv/bin/python -m compute_tokens.opening_capacity`.\n\n'
        'Uses unrounded existing Figure 1 data, central hardware scenario, 2025–27 shipments. '
        'Open estimates retain the 50-token/s benchmark anchors; closed ranges retain the original economic assumptions. '
        'No midpoint or hardware-sensitivity interval is added.\n\n'
        'Original body-figure candidate is now `../draft2_text_review/figures/figure_6.*` '
        'and `../serving_cost_curve/`. No document edits.\n\n'
        'Branding deferred: the current exports are unbranded and no verified official Epoch logo asset was available locally. '
        'The established palette, typography and source attribution are retained.\n')
    assert before is None or before == hashlib.sha256(original.read_bytes()).hexdigest()
    print(out / 'opening_capacity.png')
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    main()
