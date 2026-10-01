"""One-time projection of public benchmark exports to fields used by the report."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
raw=root/'data/inferencex_2026-09-15.csv.gz'
ref=root/'reference/inferencex_prepared.csv'
columns={
    'id','model','export.display_model','hardware','framework','precision','spec_method',
    'disagg','conc','num_prefill_gpu','num_decode_gpu','decode_tp','metrics.pp','metrics.pcp_size',
    'benchmark_type','export.in_latest_snapshot','metrics.total_tput_tps','metrics.tput_per_gpu',
    'metrics.output_tput_per_gpu','metrics.input_tput_per_gpu','metrics.p90_intvty',
    'metrics.median_intvty','metrics.p90_ttft','metrics.theoretical_cache_hit_rate',
    'metrics.input_tput_tps','metrics.output_tput_tps','run_url','export.retrieved_at','export.source_url'}
derived={'total_gpus','concurrency_per_gpu','total_token_throughput_per_chip',
    'output_token_throughput_per_chip','input_token_throughput_per_chip','total_gpus_reported',
    'concurrency_per_reported_gpu','gpu_count_corrected','gpu_count_basis',
    'gpu_count_implied_by_throughput','snapshot_date'}
provenance=root/'data/benchmark_projection.json'
if provenance.exists():
    raise SystemExit('Already minimized; preserve original provenance')
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw,ref)}
for path,keep in [(raw,columns),(ref,columns|derived)]:
    text=gzip.decompress(path.read_bytes()).decode() if path==raw else path.read_text()
    reader=csv.DictReader(io.StringIO(text)); fields=[c for c in reader.fieldnames if c in keep]
    rows=list(reader); out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    content=out.getvalue().encode()
    path.write_bytes(gzip.compress(content,mtime=0) if path==raw else content)
provenance.write_text(json.dumps(dict(original_sha256=hashes,kept_source_columns=sorted(columns),
    transformation='Column projection only; all 722 records and selected values retained verbatim. No filtering or numerical changes.',
    retrieved_at_utc='2026-09-15T00:57:02.353938+00:00',source='https://inferencex.semianalysis.com/api/v1/benchmarks'),indent=2)+'\n')
