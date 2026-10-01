"""Current report figures from explicit numeric inputs, with no artwork inputs.

Called by reproduce after benchmark normalization and optional raw reconstruction.
Historical design modules supply styling only; no pre-existing polished_figures
directory or reference image is needed.
"""
import html
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from . import benchmark_figures as b, distributions as d, polish as p
from . import text_cleanup as cleanup, comment_text_revision as comments
from . import design_handoff_revision as design, design_tick_preview as ticks
from . import opening_capacity, serving_curve
from .figure_text_review import revise
from .paths import ROOT


def model_measurements(records, estimates):
    rows = []
    for model, label in [('dsv4', 'DeepSeek V4 Pro'), ('glm5.2', 'GLM-5.2'), ('kimik3', 'Kimi K3')]:
        frame = estimates[(estimates.model == model) & (estimates.hardware == 'gb300') &
                          (estimates.metric == 'p90')].set_index('cutoff')
        c50, c100 = float(frame.loc[50, 'estimate']), float(frame.loc[100, 'estimate'])
        rows.append(dict(model=model, label=label, evidence='benchmark', low=5/c50, high=5/c100,
                         concurrency_50=c50, concurrency_100=c100, high_context=False))
    for r in d.figure6_records(records, 'retained'):
        if r['model'] not in ('gpt-5.6-sol', 'claude-fable-5') or r['high_context']:
            continue
        rows.append(dict(model=r['model'], label=r['label'], evidence='assumed',
                         low=r['pooled']/10, high=r['pooled']/5,
                         api_hourly=r['pooled'], high_context=False))
    assert len(rows) == 5
    for r in rows:
        for year in (2026, 2027):
            for u in (1, 2, 4):
                r[f'capacity_{year}_u{u}_low_millions'] = b.capacity(year, u=u, c=5/r['high'])
                r[f'capacity_{year}_u{u}_high_millions'] = b.capacity(year, u=u, c=5/r['low'])
    return pd.DataFrame(rows)


class Gallery:
    def save(self, fig, old, *args):
        historical = str(int(old)+1) if old.isdigit() else old
        revise(fig, historical)
        number = {'6': '7', '7': '8', '8': '9'}.get(historical, historical)
        cleanup.export(fig, number)


def build(output: Path, inputs: Path, prepared: Path):
    """Build every current figure using quick aggregates OR reconstructed inputs."""
    output.mkdir(parents=True, exist_ok=True)
    figures = output / 'figures'
    measurements = output / 'measurements'
    figures.mkdir(exist_ok=True); measurements.mkdir(exist_ok=True)
    df = pd.read_csv(prepared)
    estimates = b.r.estimates(df, 'latest')
    raw = json.loads((inputs / 'token_groups.json').read_text())
    costs = [dict(r, dataset='TraceLab', hours_primary=r['hours_uncapped'])
             for r in json.loads((inputs / 'cost_groups.json').read_text())]
    records = d.build_records(costs + d.choose(raw, 'WEKA'), raw)
    d.validate(costs + d.choose(raw, 'WEKA'), raw, records)
    models = model_measurements(records, estimates)
    opening = opening_capacity.measurements(models)
    pd.DataFrame(opening).to_csv(measurements / 'figure_1_capacity.csv', index=False)
    models.to_csv(measurements / 'figure_6_model_anchors.csv', index=False)
    estimates.to_csv(measurements / 'benchmark_target_estimates.csv', index=False)
    (measurements / 'distributions.json').write_text(json.dumps(records, indent=2)+'\n')
    for number, metric in [('2', 'p90'), ('a1', 'median')]:
        frontiers = []
        for model in b.MODELS:
            for hardware in b.HARDWARE:
                group = df[(df.model == model) & (df.hardware == hardware)]
                if not group.empty:
                    frontiers.append(b.r.pareto_frontier(group, f'metrics.{metric}_intvty'))
        pd.concat(frontiers).to_csv(measurements / f'figure_{number}_frontiers.csv', index=False)
    x = np.geomspace(.1, 20, 500)
    pd.DataFrame(dict(serving_usd_per_agent_hour=x,
        low_millions=b.capacity(2027, u=1, c=5/x), central_millions=b.capacity(2027, u=2, c=5/x),
        high_millions=b.capacity(2027, u=4, c=5/x))).to_csv(measurements / 'figure_6_curve.csv', index=False)
    # Rendering adapters are process-local; restore them so repeated builds do
    # not inherit paths or callbacks from a previous invocation.
    saved = (cleanup.OUT, cleanup.EXPORT_FORMATS, cleanup.POSTPROCESS, cleanup.FINALIZE,
             design.OUT, ticks.save)
    design.CHECKS.clear()
    try:
        cleanup.OUT = design.OUT = figures
        cleanup.EXPORT_FORMATS = ('png', 'svg')
        cleanup.POSTPROCESS = comments.revise_comments
        cleanup.FINALIZE = design.finalize
        ticks.save = lambda fig, n: cleanup.export(fig, str(n))
        p.theme()
        gallery = Gallery()
        cleanup.export(opening_capacity.draw(opening), '1')
        p.frontiers(gallery, df, 'p90')
        p.matrix(gallery, estimates, [50, 100])
        p.costs(gallery, records)
        p.tokens(ticks.Tokens(), records)
        serving_curve.main(frame=models, capture=ticks.serving)
        p.theme()
        closed, sensitivity, opened = p.projections(gallery, estimates)
        p.frontiers(gallery, df, 'median')
        p.matrix(gallery, estimates, [200])
        for name, rows in [('figure_7_ranges', closed), ('figure_9_deepseek', opened)]:
            pd.DataFrame(rows).to_csv(measurements / f'{name}.csv', index=False)
        pd.DataFrame([r for r in sensitivity if r['year'] == 2027]).to_csv(
            measurements / 'figure_8_spending_sensitivity.csv', index=False)
        reference = figures / 'full-layout-reference'
        reference.mkdir(exist_ok=True)
        for n in ('2', 'a1'):
            for ext in ('png', 'svg'):
                shutil.copy2(figures / f'figure_{n}.{ext}', reference / f'figure_{n}.{ext}')
    finally:
        (cleanup.OUT, cleanup.EXPORT_FORMATS, cleanup.POSTPROCESS, cleanup.FINALIZE,
         design.OUT, ticks.save) = saved
    manifest = json.loads((ROOT / 'current_report_manifest.json').read_text())
    sections = []
    for item in manifest['figures']:
        stems = item.get('parts', [item['stem']])
        for stem in [item['stem'], *item.get('parts', [])]:
            for ext in ('png', 'svg'):
                assert (figures / f'{stem}.{ext}').is_file(), stem
        links = ' · '.join(f'<a href="figures/{stem}.{ext}">{stem}.{ext}</a>'
                           for stem in stems for ext in ('png', 'svg'))
        images = ''.join(f'<img src="figures/{stem}.svg" alt="{html.escape(item["title"])}" loading="lazy">'
                         for stem in stems)
        sections.append(f'<section><h2>{item["id"]}: {html.escape(item["title"])}</h2>{links}{images}</section>')
        for name in item['measurements']:
            assert (measurements / name).is_file(), name
    (output / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Current report reproduction</title>'
        '<style>body{max-width:1100px;margin:30px auto;font:16px/1.5 system-ui}img{width:100%}section{margin:40px 0}</style>'
        '<h1>Compute to tokens — current figure set</h1><p>September 29, 2026 design handoff. '
        'Frozen source snapshot and pricing; no live data substitutions. See measurements/ for plotted values '
        'and the repository methodology for clock/cache definitions.</p>'+''.join(sections))
    result = dict(figures=len(manifest['figures']), split_parts=4, benchmark_rows=len(df),
                  artwork_inputs_used=False, checks=design.CHECKS.copy())
    (output / 'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
