"""Render only Figures 5 and 6 for local review; never upload to Drive.

Run python -m compute_tokens.design_tick_preview.
"""
import json
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from . import polish as p, distributions as d, serving_curve
from .figure_text_review import revise, replace
from .paths import ROOT, DATA

OUT = ROOT / 'polished_figures/design_tick_preview'


def save(fig, number):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ('svg', 'png', 'pdf'):
        fig.savefig(OUT / f'figure_{number}.{ext}', dpi=240)
    plt.close(fig)


class Tokens:
    def save(self, fig, *args):
        revise(fig, '5')
        for ax, final_tick in zip(fig.axes, (250, 6000, None)):
            limits = ax.get_xlim()
            if final_tick is not None:
                assert ax.get_xticks()[-1] < final_tick <= limits[1]
                ax.set_xticks([*ax.get_xticks(), final_tick])
            assert ax.get_xlim() == limits
            ax.set_ylim(0, 100)
        save(fig, 5)


def serving(fig):
    revise(fig, '1')  # Historical artwork key; current report number is 6.
    ax = fig.axes[0]
    limits = ax.get_xlim()
    assert limits == (.1, 20)
    ax.set_xticks([.1, .3, 1, 3, 10, 20], ['$0.10', '$0.30', '$1', '$3', '$10', '$20'])
    assert ax.get_xlim() == limits and ax.get_xscale() == 'log'
    for old, new in (
        ('Central hardware assumption', 'Central estimate'),
        ('Alternative hardware assumptions', 'Hardware scenarios'),
        ('Open models: benchmark-based estimates', 'Open models (benchmarked)'),
        ('Closed models: estimates inferred from API spending', 'Closed models (inferred)'),
    ):
        replace(fig, old, new)
    # Inspect every vertex of the full scenario envelope, not model anchors.
    # Capacity is proportional to 1 / serving cost, so its maximum is at $0.10.
    band = ax.collections[0].get_paths()[0].vertices
    visible_band = band[(band[:, 0] >= limits[0]) & (band[:, 0] <= limits[1])]
    maximum = float(visible_band[:, 1].max())  # millions of agents
    minimum = float(visible_band[:, 1].min())
    assert maximum < 10000 and minimum > ax.get_ylim()[0]
    original_band = band.copy()
    ax.set_yticks([10, 30, 100, 300, 1000, 3000, 10000],
                 ['10M', '30M', '100M', '300M', '1B', '3B', '10B'])
    ax.set_ylim(ax.get_ylim()[0], 10000)
    ax.yaxis.grid(True, which='major')
    assert ax.get_yscale() == 'log' and ax.get_xlim() == limits
    assert np.array_equal(original_band, ax.collections[0].get_paths()[0].vertices)
    print(f'Full band range: {minimum:.6f}–{maximum:.6f} million agents; top axis tick: 10B')
    save(fig, 6)


def main():
    p.theme()
    raw = json.loads((DATA / 'token_groups.json').read_text())
    costs = [dict(r, dataset='TraceLab', hours_primary=r['hours_uncapped'])
             for r in json.loads((DATA / 'cost_groups.json').read_text())]
    records = d.build_records(costs + d.choose(raw, 'WEKA'), raw)
    p.tokens(Tokens(), records)
    frame = pd.read_csv(ROOT / 'polished_figures/headline_candidate/model_measurements.csv')
    serving_curve.main(frame=frame, capture=serving)
    print(OUT)


if __name__ == '__main__':
    main()
