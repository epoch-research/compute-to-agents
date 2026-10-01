"""Separate PNG/SVG handoff from September 29 comment review; data unchanged."""
import shutil
import pandas as pd
from . import text_cleanup as cleanup, opening_capacity, polish as p
from .figure_text_review import replace
from .paths import ROOT

OUT = ROOT / 'polished_figures/comment-text-revisions-2026-09-29'


def change_title(fig, title):
    t = next((t for t in fig.texts if t.get_gid() == 'figure-title'), fig.texts[0])
    t.set_text(title)
    if '\n' in title:
        t.set_fontsize(20)
        t.set_va('top')
        t.set_y(.975)


def subtitle(fig, text, y=None):
    t = next((t for t in fig.texts if t.get_gid() == 'figure-subtitle'), fig.texts[1])
    t.set_text(text)
    if y is not None:
        t.set_y(y)
        t.set_va('top')


def revise_comments(fig, number):
    if number == '1':
        change_title(fig, 'The compute buildout could run tens of millions of\nfrontier agents, or billions of cheaper ones')
        subtitle(fig, 'Number of AI agents that could run concurrently on memory shipped during 2025–27, by model.\nAssumes all of that memory is deployed and used to run agents.', .867)
        t = replace(fig, 'Central hardware assumptions. Each estimate assumes all hardware serves the indicated workload.',
            'Closed-model estimates are inferred from API spending. Their ranges reflect alternative serving-cost assumptions,\n'
            'since actual serving costs are not public. Open-model estimates use SemiAnalysis InferenceX benchmarks.\n'
            'Memory volumes for 2026–27 are projections. See Sections 1–2 for methods.')[0]
        t.set_fontsize(9); t.set_y(.046)
    elif number == '3':
        change_title(fig, 'Higher streaming-speed targets generally reduce agent concurrency')
    elif number == '4':
        change_title(fig, 'A continuously running coding agent costs roughly\n$15–50 an hour at API prices')
        subtitle(fig, 'What one hour of continuous agent activity would cost at standard API prices,\nfor Codex and Claude Code sessions from the TraceLab dataset.', .862)
        # Preserve the correct source-artwork mark description and pooled column.
        t = next(t for t in fig.texts if t.get_gid() == 'figure-footnote')
        t.set_text('Hourly rates use adjusted working time with uncovered within-run gaps capped at five minutes; known model/tool work is not capped.\n'
                   'Assumes cached input stays cached. Claude prices: Aug 21, 2026; Codex prices: Sep 14, 2026. Sessions: Apr 23–Jul 24, 2026.\n'
                   'Pooled rate = total spending ÷ total adjusted hours, including short groups. n = groups with at least five primary active minutes.')
        t.set_fontsize(8.4)
    elif number == '5':
        change_title(fig, 'AgentX and TraceLab show similar hourly token-use distributions')
    elif number == '6':
        change_title(fig, 'Lower serving costs allow the same hardware to support more agents')
        replace(fig, 'Central estimate', 'Central hardware assumption')
        replace(fig, 'Hardware scenarios', 'Alternative hardware assumptions')
    elif number == '7':
        change_title(fig, 'Memory shipped through 2027 could support\n33–171 million frontier-model agents')
        subtitle(fig, 'Number of frontier-model agents that could run concurrently on high-bandwidth memory shipped since 2025.\n'
                 'Assumes $30 in API spending per agent-hour, a revenue/cost ratio of 5–10×, $5 per GB300-hour, and full allocation.', .855)
        for old, new in (('20–40 million', '20–40M'), ('16–56', '16–56M'),
                         ('50–101 million', '50–101M'), ('33–171', '33–171M')):
            replace(fig, old, new)
    elif number == '8':
        change_title(fig, 'Even at $100/hour per agent, global compute\ncould run tens of millions concurrently')
        subtitle(fig, 'Concurrent frontier-model agents supported by high-bandwidth memory shipped during the indicated periods,\n'
                 'as API spending varies from $10 to $100 per agent-hour. Assumes a revenue/cost ratio of 5–10×, $5 per GB300-hour, and full allocation.', .879)
        next(t for t in fig.texts if t.get_gid() == 'figure-subtitle').set_fontsize(10.5)


def main():
    cleanup.OUT = OUT
    cleanup.EXPORT_FORMATS = ('png', 'svg')
    cleanup.POSTPROCESS = revise_comments
    cleanup.main()
    rows = opening_capacity.measurements(pd.read_csv(ROOT / 'polished_figures/serving_cost_curve/model_measurements.csv'))
    cleanup.export(opening_capacity.draw(rows), '1')
    for ext in ('png', 'svg'):
        shutil.copy2(ROOT / f'polished_figures/draft2_text_review/figures/figure_9.{ext}', OUT / f'figure_9.{ext}')


if __name__ == '__main__':
    main()
