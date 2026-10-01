"""Report table arithmetic, with cell-level rounded-value reconciliation."""
import csv
import html
import json
import re
from pathlib import Path
import pandas as pd
from .paths import DATA, REFERENCE
from .distributions import figure6_records


def numbers(text):
    return re.findall(r'-?\d[\d,]*(?:\.\d+)?', text)


def main(output, figures, prepared):
    from .benchmark_figures import capacity, H3, H4
    output.mkdir(parents=True, exist_ok=True)
    report = json.loads((REFERENCE / 'report_tables.json').read_text())
    specs = json.loads((DATA / 'hardware_specs.json').read_text())
    tables, numeric = {}, {}
    structural_discrepancies=[]
    # Each data row contains independently computed numeric cell arrays. Display
    # precision is inherited from the report; no reported number is used in arithmetic.
    for name, ks in [('1', [5,10]), ('B1', [5,10,20,40])]:
        numeric[name] = [[[k],[30/k],[5*k/30]] for k in ks]
    selected = pd.read_csv(figures / 'economic_selected.csv')
    numeric['2'] = []
    for tier in ('dsv4_offpeak','dsv4_peak','glm5.2','kimik3','minimaxm3'):
        s = selected[selected.tier == tier].set_index('cutoff')
        numeric['2'].append([None,None,[s.loc[50,'K']],[s.loc[100,'K']]])
        row_number=len(numeric['2'])
        expected_hardware=report['2'][row_number][1]
        for cut in (50,100):
            if s.loc[cut,'hardware'].upper()!=expected_hardware:
                structural_discrepancies.append(dict(table='2',row=row_number,column=1,
                    reported=expected_hardware,recomputed=s.loc[cut,'hardware'].upper(),cutoff=cut))
    annual = [3.75/1.7, 3.75, 3.75*1.55]
    s3, s4 = [.8,.625,.2], [0,.375,.8]
    numeric['4'] = [[[2025+i],[a],[100*s3[i]],[100*s4[i]]] for i,a in enumerate(annual)]
    numeric['B2a'] = [r + [[annual[i]*s3[i]],[annual[i]*s4[i]]] for i,r in enumerate(numeric['4'])]
    numeric['B2b'] = [[[y],[H3[y]],[H4[y]],[(H3[y]+2*H4[y])*1000/288]] for y in (2026,2027)]
    numeric['B3'] = [[[y]]+[[capacity(y,u=u),capacity(y,K=10,u=u)] for u in (1,2,4)] for y in (2026,2027)]
    numeric['B5'] = [[[n*100],[r*100],[(n+(1-n)*r)*100]] for n in (.7,.6,.5) for r in (.75,.5)]
    frame = pd.read_csv(prepared)
    kimi = frame[(frame.model=='kimik3') & (frame.hardware=='gb300')]
    numeric['A1'] = []
    ttft_rows = []
    for cut in (50,100,200):
        row = kimi[kimi['metrics.p90_intvty']>=cut].sort_values('concurrency_per_gpu',ascending=False).iloc[0]
        numeric['A1'].append([[cut],[row['metrics.p90_ttft']]])
        ttft_rows.append(dict(cutoff=cut, benchmark_id=int(row.id), p90_ttft=row['metrics.p90_ttft']))
    (output/'table_A1_selection.json').write_text(json.dumps(ttft_rows,indent=2)+'\n')
    measurement = json.loads((figures/'numerical_measurements.json').read_text())
    cohort = figure6_records(measurement['records'], 'retained')
    numeric['A2'] = [[None,[r['groups'],r['eligible_groups']],[r['hours']],[r['pooled']]] for r in cohort]
    samples = [{k:r[k] for k in ('model','high_context','groups','eligible_groups','hours','numerator','pooled')} for r in cohort]
    (output/'sample_summary.json').write_text(json.dumps(samples,indent=2)+'\n')
    cuts = pd.read_csv(figures/'all_cutoff_estimates.csv')
    numeric['B4'] = [[None,None,None,None]]
    for s in (2.5,5,10,20,30,50,75,100,150,200):
        numeric['B4'].append([None,[25/s,50/s]]+[[capacity(y,s,u=1),capacity(y,s,K=10,u=4)] for y in (2026,2027)])
    numeric['B4'].append([None,None,None,None])
    for m in ('dsv4','glm5.2','kimik3'):
        for cut in (50,100):
            c = cuts[(cuts.model==m)&(cuts.hardware=='gb300')&(cuts.metric=='p90')&(cuts.cutoff==cut)].iloc[0].estimate
            numeric['B4'].append([None,[c]]+[[capacity(y,u=1,c=c),capacity(y,u=4,c=c)] for y in (2026,2027)])
    discrepancies = structural_discrepancies
    for name, grid in report.items():
        if name in specs:
            tables[name] = specs[name]
        else:
            cells = [grid[0]]
            values = numeric[name]
            if len(values) != len(grid)-1:
                raise AssertionError(f'Table {name}: row count mismatch')
            for ri, (expected_row, vals) in enumerate(zip(grid[1:], values), 1):
                cells.append([])
                for ci, (expected, nums) in enumerate(zip(expected_row, vals)):
                    if nums is None:
                        # Labels and structural cells, not calculated measurements.
                        cells[-1].append(expected)
                        continue
                    matches = list(re.finditer(r'\d[\d,]*(?:\.\d+)?', expected))
                    if len(matches) != len(nums):
                        raise AssertionError((name,ri,ci,expected,nums))
                    actual, start = '', 0
                    for match, value in zip(matches, nums):
                        token = match.group()
                        decimals = len(token.split('.')[1]) if '.' in token else 0
                        tolerance = .5*10**(-decimals) + 1e-9
                        old = float(token.replace(',',''))
                        if abs(old-value)>tolerance:
                            discrepancies.append(dict(table=name,row=ri,column=ci,reported=old,recomputed=float(value),tolerance=tolerance))
                        fmt = f',.{decimals}f' if ',' in token else f'.{decimals}f'
                        actual += expected[start:match.start()] + format(value,fmt)
                        start = match.end()
                    cells[-1].append(actual+expected[start:])
            tables[name] = cells
    # Include full precision independently of the presentation CSVs.
    (output/'calculations.json').write_text(json.dumps(numeric,indent=2)+'\n')
    (output/'reconciliation.json').write_text(json.dumps(dict(discrepancies=discrepancies,
        checked_tables=list(numeric),static_sourced_tables=list(specs)),indent=2)+'\n')
    for name, cells in tables.items():
        with (output/f'table_{name}.csv').open('w',newline='') as f:
            csv.writer(f).writerows(cells)
        content = ''.join('<tr>'+''.join('<td>'+html.escape(c)+'</td>' for c in row)+'</tr>' for row in cells)
        (output/f'table_{name}.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font:15px system-ui}td{padding:9px;border-bottom:1px solid #ddd}tr:first-child{font-weight:bold}</style><h1>Table '+name+'</h1><table>'+content+'</table>')
    print(f'Tables: {len(tables)}; discrepancies: {len(discrepancies)}', flush=True)
    return discrepancies
