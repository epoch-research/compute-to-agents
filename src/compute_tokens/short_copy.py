"""Focused short-copy handoff for Figures 1, 4, 7 and 8; no Drive writes."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from .figure_text_review import plot_signature
from .paths import ROOT, DATA, REFERENCE

OUT = ROOT / 'polished_figures/short-copy-2026-09-29'
CHECKS = {}
SUBTITLES = {
    '1': 'Potential capacity from 2025–27 memory shipments, assuming all memory is deployed for the indicated workload.',
    '7': 'Assumes $30 in API spending per agent-hour and full allocation to this workload.',
    '8': 'Capacity from 2025–27 memory shipments, assuming full allocation and an API revenue/serving-cost ratio held at 5–10×.',
}
NOTE1 = 'Closed-model ranges reflect alternative serving-cost assumptions. Memory supply for 2026–27 is projected.'
NOTE4 = ('Boxes show the middle 50%, thick whiskers the middle 80%, ticks the median, and faint lines the full range.\n'
         'Identified waits for human input are removed; other idle gaps are capped at five minutes.')


def wrap(fig, text, content, right=.97):
    """Wrap using the existing font metrics; never reduce its point size."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    lines = []
    for paragraph in content.split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = (line+' '+word).strip()
            text.set_text(candidate)
            bounds = text.get_window_extent(renderer).transformed(fig.transFigure.inverted())
            if bounds.x1 > right and line:
                lines.append(line); line = word
            else:
                line = candidate
        lines.append(line)
    text.set_text('\n'.join(lines))


def revise(fig, number):
    if number not in ('1', '4', '7', '8'):
        return
    before = plot_signature(fig)
    original_sizes = {id(t): t.get_fontsize() for t in fig.texts}
    credits = [t.get_text() for t in fig.texts if t.get_text().startswith(('Source:', 'Sources:'))]
    if number in SUBTITLES:
        subtitle = next((t for t in fig.texts if t.get_gid() == 'figure-subtitle'), fig.texts[1])
        wrap(fig, subtitle, SUBTITLES[number])
    if number == '1':
        footer = next(t for t in fig.texts if t.get_text().startswith('Closed-model estimates are inferred'))
        wrap(fig, footer, NOTE1)
    elif number == '4':
        old = next(t for t in fig.texts if t.get_gid() == 'figure-footnote')
        old.remove()
        marks = next(t for t in fig.texts if t.get_text().startswith('Boxes show the middle 50%'))
        wrap(fig, marks, NOTE4)
        marks.set_y(.055); marks.set_va('bottom')
    # All plotted data, colors, limits, marks and existing axes are unchanged.
    assert before == plot_signature(fig)
    assert credits == [t.get_text() for t in fig.texts if t.get_text().startswith(('Source:', 'Sources:'))]
    assert all(t.get_fontsize() == original_sizes[id(t)] for t in fig.texts)
    # Use the space vacated by subtitles for a taller plotting area, retaining
    # the same coordinates, scales and bottom axis/legend positions.
    if number in ('7', '8'):
        ax = fig.axes[0]
        x, y, w, h = ax.get_position().bounds
        ax.set_position([x, y, w, h+.035])
    CHECKS[number] = dict(plot_signature_before=before,
                         text_only_before_layout=True, font_sizes_preserved=True,
                         source_credits=credits, expanded_plot=number in ('7', '8'))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = []
    for t in fig.texts:
        box = t.get_window_extent(renderer).transformed(fig.transFigure.inverted())
        assert box.x0 >= 0 and box.x1 <= 1 and box.y0 >= 0 and box.y1 <= 1, t.get_text()
        if t.get_text(): boxes.append((t.get_text(), box))
    for i, (label, box) in enumerate(boxes):
        for other, other_box in boxes[i+1:]:
            assert not box.overlaps(other_box), (label, other)


def main():
    from . import current_report, distributions as d, polish as p, opening_capacity
    from . import text_cleanup as cleanup, comment_text_revision as comments, design_handoff_revision as design
    cleanup.OUT = OUT
    cleanup.EXPORT_FORMATS = ('png', 'svg')
    cleanup.POSTPROCESS = comments.revise_comments
    cleanup.FINALIZE = design.finalize
    raw = json.loads((DATA/'token_groups.json').read_text())
    costs = [dict(r, dataset='TraceLab', hours_primary=r['hours_uncapped'])
             for r in json.loads((DATA/'cost_groups.json').read_text())]
    records = d.build_records(costs+d.choose(raw, 'WEKA'), raw)
    estimates = p.b.r.estimates(pd.read_csv(REFERENCE/'inferencex_prepared.csv'), 'latest')
    class Selected(current_report.Gallery):
        def save(self, fig, old, *args):
            if old not in ('3', '5', '6'):
                plt.close(fig); return
            super().save(fig, old, *args)
    p.theme()
    rows = opening_capacity.measurements(current_report.model_measurements(records, estimates))
    cleanup.export(opening_capacity.draw(rows), '1')
    p.costs(Selected(), records)
    p.projections(Selected(), estimates)
    from . import short_copy as active_module
    assert set(active_module.CHECKS) == {'1', '4', '7', '8'}
    (OUT/'validation.json').write_text(json.dumps(active_module.CHECKS, indent=2)+'\n')
    print(OUT)


if __name__ == '__main__':
    main()
