"""Requested September 29 structural handoff; retain frozen numeric inputs."""
import json
import pickle
import shutil
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from . import comment_text_revision as comments, text_cleanup as cleanup, polish as p
from .figure_text_review import replace
from .paths import ROOT

OUT = ROOT / 'polished_figures/design-handoff-2026-09-29'
GROUPS = [
    ('Nvidia Blackwell', [('b200', '#144B74', 'o'), ('b300', '#287FB0', 's'),
                         ('gb200', '#569BC4', '^'), ('gb300', '#80BEDA', 'D')]),
    ('Nvidia Hopper', [('h100', '#715095', 'P'), ('h200', '#AB83C4', 'X')]),
    ('AMD', [('mi300x', '#9B451F', 'v'), ('mi325x', '#C66F36', '<'),
             ('mi355x', '#E4A15B', '>')]),
]
STYLE = {h: (c, m) for _, systems in GROUPS for h, c, m in systems}
CHECKS = {}


def split_frontiers(original, number):
    """Reuse the plotted artists exactly; only remove/reposition whole panels."""
    arrangements = [
        ['DeepSeek V4 Pro', 'GLM-5.2', 'Kimi K3', 'MiniMax M3'],
        ['Qwen 3.5 397B', 'Qwen 3.8 Flash Next', 'DeepSeek V4.1 Flash'],
    ]
    for part, names in enumerate(arrangements, 1):
        fig = pickle.loads(pickle.dumps(original))
        fig.set_size_inches(12.4, 10.8)
        panels = {ax.get_title(loc='left'): ax for ax in fig.axes}
        for ax in list(fig.axes):
            if ax.get_title(loc='left') not in names:
                fig.delaxes(ax)
        for i, name in enumerate(names):
            ax = panels[name]
            ax.set_position([.10 + .48 * (i % 2), .60 - .325 * (i // 2), .385, .245])
            assert ax.get_xlim() == (1., 1000.) and ax.get_ylim() == (.025, 100.)
            assert ax.get_xscale() == ax.get_yscale() == 'log'
            ax.tick_params(labelleft=True, labelbottom=True)
        for t in fig.texts:
            if t.get_text() == 'Configured agent sessions per GPU':
                t.set_y(.56)
            elif 'streaming speed (tokens/s/user)' in t.get_text():
                t.set_y(.215)
        for x, (name, systems) in zip((.08, .46, .70), GROUPS):
            handles = [Line2D([], [], color=c, marker=m, lw=2, ms=5, label=h.upper())
                       for h, c, m in systems]
            legend = fig.legend(handles=handles, title=name, loc='upper left',
                                bbox_to_anchor=(x, .169), ncol=len(systems), frameon=False,
                                fontsize=9, title_fontsize=10, handlelength=1.3,
                                columnspacing=.85, borderaxespad=0)
            legend._legend_box.align = 'left'
        fig.text(.10, .078, 'Lines: best observed trade-offs    Dotted guides: 50 and 100 tokens/s/user',
                 fontsize=10, color=p.MUTED)
        fig.canvas.draw()
        from matplotlib.text import Text
        for t in fig.findobj(Text):
            if not t.get_visible() or not t.get_text():
                continue
            box = t.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
            assert box.x0 >= -.001 and box.x1 <= 1.001 and box.y0 >= -.001 and box.y1 <= 1.001, t.get_text()
        OUT.mkdir(parents=True, exist_ok=True)
        for ext in ('png', 'svg'):
            fig.savefig(OUT / f'figure_{number.lower()}_part_{part}.{ext}', dpi=240)
        plt.close(fig)
        CHECKS[f'{number}_part_{part}'] = {'models': names, 'unchanged_frontier_artists': True}


def finalize(fig, number):
    if number in ('2', 'A1'):
        # Match original series by frozen hardware color, not by panel order.
        from matplotlib.colors import to_rgba
        old = {to_rgba(p.b.CONFIG['hardware_colors'][h]): h for h in p.b.HARDWARE}
        for ax in fig.axes[:-1]:
            for line in ax.lines:
                h = old.get(to_rgba(line.get_color()))
                if h is not None:
                    color, marker = STYLE[h]
                    line.set_color(color); line.set_marker(marker)
            # Remove only the faint raw configurations; frontier markers stay.
            for collection in list(ax.collections):
                assert collection.get_alpha() == .13
                collection.remove()
        ax = fig.axes[-1]
        ax.get_legend().remove()
        for t in list(ax.texts):
            t.remove()
        for y, (name, systems) in zip((1.02, .73, .44), GROUPS):
            handles = [Line2D([], [], color=c, marker=m, lw=2, ms=5, label=h.upper())
                       for h, c, m in systems]
            legend = ax.legend(handles=handles, title=name, loc='upper left',
                               bbox_to_anchor=(0, y), ncol=len(systems), frameon=False,
                               fontsize=9, title_fontsize=10, handlelength=1.3,
                               columnspacing=.85, borderaxespad=0)
            legend._legend_box.align = 'left'
            ax.add_artist(legend)
        ax.text(0, .11, 'Lines: best observed trade-offs\nDotted guides: 50 and 100 tokens/s/user',
                transform=ax.transAxes, va='top', color=p.MUTED, fontsize=10, linespacing=1.5)
        CHECKS[number] = {'hardware_styles': STYLE, 'faint_points_removed': True}
        split_frontiers(fig, number)
    elif number == '4':
        comments.change_title(fig, 'Coding agents averaged roughly $15–50 per hour\nof continuous activity at API prices')
        t = next(t for t in fig.texts if t.get_gid() == 'figure-footnote')
        old, rest = t.get_text().split('\n', 1)
        assert old.startswith('Hourly rates use adjusted working time')
        t.set_text('Hourly rates divide API-equivalent spending by adjusted working time, removing identified waits for human input\n'
                   'and capping other idle gaps at five minutes. Known model and tool work is not capped.\n' + rest)
    elif number == '7':
        ax = fig.axes[0]
        assert len(ax.lines) == 4
        before = [line.get_xydata().copy() for line in ax.lines]
        for i, line in enumerate(ax.lines):
            outer = i % 2 == 0
            line.set_linewidth(2 if outer else 8)
            line.set_marker('|')
            line.set_markersize(13 if outer else 15)
            line.set_markeredgewidth(2)
            # Stronger outer endpoints are visible against the white background.
            if outer:
                line.set_color('#8CA6AF')
        assert all(np.array_equal(a, line.get_xydata()) for a, line in zip(before, ax.lines))
        for line, outer in zip(fig.legends[0].get_lines(), (False, True)):
            line.set_linewidth(2 if outer else 8)
            line.set_marker('|'); line.set_markersize(12); line.set_markeredgewidth(2)
            if outer:
                line.set_color('#8CA6AF')
        CHECKS[number] = {'unchanged_range_coordinates': [a.tolist() for a in before]}
    elif number == '8':
        left, ax = fig.axes
        bands = [c.get_paths()[0].vertices.copy() for c in ax.collections]
        ylabel = left.get_ylabel()
        fig.delaxes(left)
        ax.set_position([.11, .26, .86, .49])
        ax.tick_params(axis='y', labelleft=True)
        ax.set_ylabel(ylabel, labelpad=10)
        comments.subtitle(fig,
            'Number of frontier-model agents that could run concurrently on high-bandwidth memory shipped during 2025–27,\n'
            'as API spending varies from $10 to $100 per agent-hour. Assumes a revenue/cost ratio of 5–10×,\n'
            '$5 per GB300-hour, and full allocation.', .879)
        assert all(np.array_equal(a, c.get_paths()[0].vertices) for a, c in zip(bands, ax.collections))
        assert ax.get_yscale() == 'log'
        CHECKS[number] = {'panels': 1, 'year': 2027, 'band_vertices_unchanged': True}
    elif number == 'A2':
        ax = fig.axes[0]
        row = [t.get_text() for t in ax.get_yticklabels()].index('GLM-5.2')
        col = [t.get_text() for t in ax.get_xticklabels()].index('B200')
        cell = next(t.get_text() for t in ax.texts if t.get_position() == (col, row))
        assert cell == '0.975', cell
        CHECKS[number] = {'GLM-5.2 / B200': cell}
    if number in ('7', '8'):
        replace(fig, 'Central hardware assumption: 2×', 'Central hardware assumption')
        replace(fig, 'Alternative hardware assumptions: 1–4×', 'Alternative hardware assumptions')
    from .short_copy import revise as shorten_copy
    shorten_copy(fig, number)


def main():
    comments.OUT = OUT
    cleanup.FINALIZE = finalize
    comments.main()
    reference = OUT / 'full-layout-reference'
    reference.mkdir(exist_ok=True)
    for number in ('2', 'a1'):
        for ext in ('png', 'svg'):
            shutil.copy2(OUT / f'figure_{number}.{ext}', reference / f'figure_{number}.{ext}')
    (OUT / 'validation.json').write_text(json.dumps(CHECKS, indent=2) + '\n')


if __name__ == '__main__':
    main()
