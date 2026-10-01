"""Optional artifact audit; accepts local public artifacts, never runs inference."""
from pathlib import Path
import json, re
from collections import defaultdict
import numpy as np
import pandas as pd
from .paths import REFERENCE

def union(xs):
    out=[]
    for a,b in sorted(xs):
        if b<=a:continue
        if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
        else:out.append([a,b])
    return out

def analyze(data, output):
    output.mkdir(parents=True, exist_ok=True)
    from .rebuild import compare
    expected_pins=json.loads((REFERENCE/'agentx_pins.json').read_text())
    if (data/'pins.json').exists():
        pins=json.loads((data/'pins.json').read_text())
    else:
        pins=[]
        for expected in expected_pins:
            run=expected['run']
            source=json.loads((data/f'{run}_run.json').read_text())
            pin=json.loads((data/f'{run}_aiperf_pin.json').read_text())
            pins.append(dict(run=run,head_sha=source['head_sha'],aiperf_sha=pin['sha']))
    compare(pins,expected_pins,'harness_pins')
    configs=[];occupancy=[]
    for folder in sorted(data.glob('artifact_*')):
        p=next(folder.rglob('profile_export_aiperf.json'));d=json.loads(p.read_text());cfg=d['input_config']
        phase=cfg['phases'][0];ds=cfg['datasets'][0];log=next(folder.rglob('benchmark.log')).read_text()
        inv=json.loads((folder/'inventory.json').read_text());meta=inv['metadata']
        shifts=re.findall(r'Per-trace idle cap advanced replay root .*? by ([\d.]+)s',log)
        global_stats=re.findall(r'Global system-idle cap summary: limit=([\d.]+)s, jumps=(\d+), skipped=([\d.]+)s',log)
        row=dict(artifact=int(folder.name.split('_')[1]),run=meta['workflow_run']['id'],model=cfg['models']['items'][0]['name'],
            concurrency=phase['concurrency'],duration=phase['duration'],trace_cap=ds.get('trace_idle_gap_cap_seconds'),
            global_cap=phase.get('system_idle_gap_cap_seconds'),start_min=phase.get('trajectory_start_min_ratio'),
            start_max=phase.get('trajectory_start_max_ratio'),warmup=phase.get('warmup_requests_per_lane'),dataset=ds['dataset'],
            version=d['aiperf_version'],valid=d['metadata'].get('submission_valid'),
            per_trace_jumps=len(shifts),root_timer_hours_skipped=sum(map(float,shifts))/3600,
            global_jumps=int(global_stats[-1][1]),global_timer_seconds_skipped=float(global_stats[-1][2]))
        configs.append(row)
        request_paths=list(folder.rglob('profile_export.jsonl'))
        if not request_paths:continue
        phase_stats=re.findall(r'PhaseRecordsStats\(phase=CreditPhase.PROFILING,.*?start_ns=(\d+), sent_end_ns=(\d+)',log)
        assert len(phase_stats)==1,(folder,phase_stats)
        start,end=map(int,phase_stats[0]);duration=(end-start)/1e9
        assert abs(duration-phase['duration'])<.1
        roots=defaultdict(list);credit_roots=defaultdict(list);raw=[];calls=children=cancelled=0
        for line in request_paths[0].open():
            r=json.loads(line);m=r['metadata']
            if m.get('benchmark_phase')!='profiling':continue
            a,b=m.get('request_start_ns'),m.get('request_end_ns')
            if a is None or b is None:continue
            a,b=max(a,start),min(b,end)
            if b<=a:continue
            root=m['root_correlation_id'];assert root
            roots[root].append(((a-start)/1e9,(b-start)/1e9))
            ca=max(m.get('credit_issued_ns',a),start)
            if b>ca:credit_roots[root].append(((ca-start)/1e9,(b-start)/1e9))
            raw.append(((a-start)/1e9,(b-start)/1e9));calls+=1
            children+=m.get('agent_depth',0)>0;cancelled+=m.get('was_cancelled',False)
        merged={r:union(xs) for r,xs in roots.items()}
        gaps=[b[0]-a[1] for intervals in merged.values() for a,b in zip(intervals,intervals[1:])]
        credit_unions={r:union(xs) for r,xs in credit_roots.items()}
        credit_gaps=[b[0]-a[1] for intervals in credit_unions.values() for a,b in zip(intervals,intervals[1:])]
        active=sum(b-a for xs in merged.values() for a,b in xs)
        global_union=union(raw)
        active_share=active/(duration*phase['concurrency'])
        occ=dict(artifact=row['artifact'],model=row['model'],concurrency=phase['concurrency'],
            profiling_seconds=duration,recorded_runtime_roots=len(roots),requests=calls,child_requests=children,cancelled_records=cancelled,
            root_request_active_seconds=active,root_request_active_pct=100*active_share,
            allocated_lane_no_request_pct=100*(1-active_share),
            server_has_any_http_request_pct=100*sum(b-a for a,b in global_union)/duration,
            interior_root_gaps=len(gaps),gap_p50=float(np.median(gaps)),gap_p95=float(np.quantile(gaps,.95)),
            gap_max=max(gaps),gaps_near300=sum(299.5<=g<=300.5 for g in gaps),gaps_over301=sum(g>301 for g in gaps))
        occ.update(credit_gap_max=max(credit_gaps),credit_gaps_over301=sum(g>301 for g in credit_gaps))
        occupancy.append(occ)
    pd.DataFrame(configs).to_csv(output/'verified_configs.csv',index=False)
    pd.DataFrame(occupancy).to_csv(output/'replay_occupancy.csv',index=False)
    
    
    if len(configs) != 13:
        raise ValueError(f"Expected 13 configuration artifacts, got {len(configs)}")
    for row in configs:
        assert row["trace_cap"] == 300 and row["global_cap"] == 10
        assert row["duration"] == 3600 and row["valid"]
        assert row["per_trace_jumps"] > 0
    from .rebuild import compare
    expected = json.loads((REFERENCE / "agentx_audit.json").read_text())
    compare(sorted(configs,key=lambda r:r["artifact"]), expected["configs"], "configs")
    if occupancy:
        compare(sorted(occupancy,key=lambda r:r["artifact"]),expected["occupancy"],"occupancy")
    return {"configs": len(configs), "occupancy_configs": len(occupancy), "verified_run_pins": len(pins)}

def main():
    import argparse
    from .fetch_agentx import fetch_all
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("build/agentx"))
    p.add_argument("--download", action="store_true")
    p.add_argument("--requests", action="store_true", help="Also fetch request records for five configs (about 60 MB transfer, 400 MB extracted)")
    a = p.parse_args()
    if a.download:
        fetch_all(a.data_dir, a.requests)
    result = analyze(a.data_dir, a.output)
    (a.output / "validation.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))

if __name__ == "__main__":
    main()
