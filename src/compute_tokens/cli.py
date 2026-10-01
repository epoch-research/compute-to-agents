"""Single offline-first entry point for the frozen report."""
import argparse
import html
import json
import os
from pathlib import Path
import subprocess
import sys
from .paths import ROOT, DATA, REFERENCE


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['quick','full'], default='quick')
    p.add_argument('--output', type=Path, default=ROOT/'build')
    p.add_argument('--data-dir', type=Path, default=ROOT/'raw')
    p.add_argument('--download', action='store_true', help='Explicitly allow pinned raw downloads (about 2 GB)')
    p.add_argument('--offline', action='store_true', help='Forbid network access, including accidental calls')
    p.add_argument('--strict-report', action='store_true', help='Exit nonzero on any report discrepancy (release gate)')
    p.add_argument('--legacy-only', action='store_true', help='Skip current report figures; reproduce the historical Draft 1 set only')
    args = p.parse_args()
    if args.offline and args.download:
        p.error('--offline and --download are incompatible')
    if args.offline:
        import socket
        def denied(*a, **k):
            raise RuntimeError('Network disabled by --offline')
        socket.socket.connect = denied
        socket.socket.connect_ex = denied
    out = args.output.resolve()
    if out == ROOT or out.is_relative_to(DATA) or out.is_relative_to(REFERENCE):
        p.error('Output must not overwrite repository or frozen data/reference directories')
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(out/'.mplconfig'))
    os.environ.setdefault('MPLBACKEND','Agg')
    from . import distributions, benchmark_figures, audits, tables
    from .sources import acquire
    from .rebuild import main as rebuild
    from . import prepare
    import pandas as pd
    inputs = DATA
    if args.mode == 'full':
        paths = acquire(args.data_dir.resolve(), args.download)
        inputs = rebuild(paths['tracelab'], paths['weka'], out/'reconstructed')
    # The normalization is regenerated even in quick mode; no prepared CSV is
    # used as a calculation input.
    saved_argv = sys.argv
    try:
        sys.argv = ['prepare','--input',str(DATA/'inferencex_2026-09-15.csv.gz'),
                    '--output',str(out/'inferencex_prepared.csv'),'--snapshot-date','2026-09-15']
        prepare.main()
    finally:
        sys.argv = saved_argv
    got = pd.read_csv(out/'inferencex_prepared.csv')
    expected = pd.read_csv(REFERENCE/'inferencex_prepared.csv')
    # The legacy export's date label may differ from its UTC retrieval date.
    pd.testing.assert_frame_equal(got.drop(columns='snapshot_date'),expected.drop(columns='snapshot_date'),check_dtype=False,rtol=1e-10,atol=1e-8)
    figures = out/'figures'
    distributions.main(figures, inputs)
    benchmark_figures.main(figures, out/'inferencex_prepared.csv')
    audits.main(out/'audits',inputs,out/'inferencex_prepared.csv')
    discrepancies = tables.main(out/'tables', figures, out/'inferencex_prepared.csv')
    from PIL import Image
    import numpy as np
    render_checks={}
    for reference in sorted((REFERENCE/'figures').glob('*.png')):
        render_checks[reference.name]=np.array_equal(np.asarray(Image.open(reference)),
                                                   np.asarray(Image.open(figures/reference.name)))
    (out/'render_comparison.json').write_text(json.dumps(render_checks,indent=2)+'\n')
    manifest = json.loads((ROOT/'report_manifest.json').read_text())
    sections=[]
    for item in manifest['items']:
        for f in item['outputs']:
            if not (out/f).is_file():
                raise AssertionError(f'Missing report output {f}')
        links=' · '.join(f'<a href="{html.escape(f)}">{html.escape(Path(f).name) if Path(f).suffix in (".csv", ".json") else Path(f).suffix[1:].upper()}</a>' for f in item['outputs'])
        preview = next((f for f in item['outputs'] if f.endswith('.png')),None)
        sections.append(f'<section><h2>{html.escape(item["id"])} — {html.escape(item["title"])}</h2><p>{links}</p>'+ (f'<img loading="lazy" src="{preview}">' if preview else '')+'</section>')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Compute to tokens: reproduction</title><style>body{max-width:1100px;margin:40px auto;padding:0 20px;font:16px/1.5 system-ui;color:#203448}img{max-width:100%}section{border-top:1px solid #ccc;margin:35px 0}</style><h1>Compute to tokens</h1><p>Frozen Draft 1 reproduction. Historical prices and source latencies; API-equivalent spending, not invoices or GPU utilization.</p><p><a href="tables/reconciliation.json">Report discrepancy check</a> · <a href="audits/gap_sensitivity.png">Gap sensitivity</a> · <a href="audits/source_vs_replay.png">Source vs replay</a> · <a href="figures/index.html">Interactive distributions</a></p>'+''.join(sections))
    (out/'validation.json').write_text(json.dumps(dict(mode=args.mode,offline=args.offline,
        report_items=len(manifest['items']),benchmark_rows=len(got),
        distribution_validation='passed',reference_pngs_pixel_identical=all(render_checks.values()),
        table_discrepancies=discrepancies),indent=2)+'\n')
    if not args.legacy_only:
        from .current_report import build
        build(out/'current', inputs, out/'inferencex_prepared.csv')
        page = (out/'index.html').read_text()
        (out/'index.html').write_text(page.replace('<h1>Compute to tokens</h1>',
            '<h1>Compute to tokens</h1><p><strong><a href="current/index.html">Current report: Figures 1–9, A1–A2 and split versions</a></strong></p>'))
        print(f'Current figure set: {out / "current/index.html"}', flush=True)
    print(f'Finished: {out / "index.html"}', flush=True)
    if discrepancies and args.strict_report:
        raise SystemExit('Report discrepancies found; see tables/reconciliation.json. Report not changed.')
    if discrepancies:
        print('WARNING: report discrepancies found; release gate remains blocked. See tables/reconciliation.json.')


if __name__ == '__main__':
    main()
