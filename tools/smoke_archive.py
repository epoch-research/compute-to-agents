"""Test an unpacked release candidate from an unrelated temporary directory."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

p=argparse.ArgumentParser()
p.add_argument('archive',type=Path)
p.add_argument('--data-dir',type=Path,help='Also run full reconstruction from this explicit raw-data directory')
a=p.parse_args()
with tempfile.TemporaryDirectory(prefix='compute-tokens-release-') as directory:
    temp=Path(directory)
    with zipfile.ZipFile(a.archive) as z:
        for name in z.namelist():
            if not (temp/name).resolve().is_relative_to(temp):raise ValueError('Unsafe archive path')
        z.extractall(temp)
    root=temp/'compute-to-tokens-repro'
    env=os.environ.copy()
    env['PYTHONPATH']=str(root/'src')
    env['MPLCONFIGDIR']=str(temp/'mpl')
    subprocess.run([sys.executable,'-c',
        'from pathlib import Path; import compute_tokens; assert Path(compute_tokens.__file__).is_relative_to(Path.cwd()); print("Package loaded from extracted candidate")'],
        cwd=root,env=env,check=True)
    subprocess.run([sys.executable,'-m','compute_tokens.release','--check'],cwd=root,env=env,check=True)
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(root/'tests')],cwd=temp,env=env,check=True)
    subprocess.run([sys.executable,'-m','compute_tokens.cli','--offline'],cwd=temp,env=env,check=True)
    validation=json.loads((root/'build/validation.json').read_text())
    assert validation['report_items']==22
    assert validation['benchmark_rows']==722
    assert validation['distribution_validation']=='passed'
    current=json.loads((root/'build/current/validation.json').read_text())
    assert current['figures']==11 and current['split_parts']==4
    assert current['artwork_inputs_used'] is False
    assert not (root/'polished_figures/headline_candidate').exists()
    expected=json.loads((root/'reference/known_table_discrepancies.json').read_text())
    from math import isclose
    actual=validation['table_discrepancies']
    assert len(actual)==len(expected)
    for got,ref in zip(actual,expected):
        assert got.keys()==ref.keys()
        for key in got:
            if isinstance(got[key],float):assert isclose(got[key],ref[key],rel_tol=1e-10,abs_tol=1e-8)
            else:assert got[key]==ref[key]
    if a.data_dir:
        subprocess.run([sys.executable,'-m','compute_tokens.cli','--offline','--mode','full',
            '--data-dir',str(a.data_dir.resolve()),'--output',str(temp/'full')],cwd=temp,env=env,check=True)
        assert json.loads((temp/'full/reconstructed/validation.json').read_text())['raw_rebuild_matches_frozen']
    print(json.dumps(dict(extracted_candidate_quick_build='passed',
        full_build='passed' if a.data_dir else 'not_requested',
        known_table_discrepancies=len(actual),reference_pngs_pixel_identical=validation['reference_pngs_pixel_identical'])))
