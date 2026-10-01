"""Raw reconstruction. Frozen derived rows are used only for final comparison."""
from collections import defaultdict
import json
import math
from pathlib import Path

from .paths import DATA, REFERENCE
from . import tracelab as ca, cache as hc, weka
from .sessions import collect_session_rows
from .prefix import canonical, cache_reads

SHARED = tuple(weka.PRICES)


def comparable(rows):
    # The upstream DuckDB group traversal order is not a stable row identity.
    # Compare multisets, not contributor/group indices or iteration order.
    def canonical_row(row):
        if isinstance(row, dict):
            return {k: canonical_row(v) for k, v in sorted(row.items())
                    if k not in ('contributor_index', 'group_index', 'user')}
        if isinstance(row, list):
            return [canonical_row(x) for x in row]
        return row
    return sorted((canonical_row(r) for r in rows), key=lambda r: (
        r.get('dataset', ''), r['model'], r['calls'], r['max_input'],
        r.get('hours_uncapped', r.get('hours_primary', 0)),
        r.get('retained_cost', 0)))


def compare(a, b, path='root'):
    if isinstance(a, dict):
        if set(a) != set(b):
            raise AssertionError(f'{path}: keys differ {set(a)^set(b)}')
        for k in a:
            compare(a[k], b[k], path + '.' + k)
    elif isinstance(a, list):
        if len(a) != len(b):
            raise AssertionError(f'{path}: lengths {len(a)} != {len(b)}')
        for i, (x, y) in enumerate(zip(a, b)):
            compare(x, y, f'{path}[{i}]')
    elif isinstance(a, float) or isinstance(b, float):
        if not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8):
            raise AssertionError(f'{path}: {a} != {b}')
    elif a != b:
        raise AssertionError(f'{path}: {a} != {b}')


def main(db: Path, weka_source: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    ca.PUBLIC_DB = db
    rows, _, coverage = collect_session_rows(tuple(ca.PRICES), include_token_totals=True, include_identity=True)
    main_models = {'gpt-5.5','gpt-5.6-sol','claude-opus-4-8','claude-fable-5'}
    groups = [r for r in rows if r['model'] in main_models]
    identities = defaultdict(set)
    for r in groups:
        identities[r['_identity']].add(r['model'])
    identity_summary = dict(main_row_session_model_groups=len(groups),
        main_row_distinct_source_sessions=len(identities),
        source_sessions_in_multiple_main_model_rows=sum(len(v)>1 for v in identities.values()))
    expected_identity = json.loads((REFERENCE/'sample_summary.json').read_text())
    for key,value in identity_summary.items():
        if value != expected_identity[key]: raise AssertionError(f'Sample identity check: {key}')
    from datetime import datetime, timezone
    for sample in expected_identity['rows'][:4]:
        selected = [r for r in groups if r['model']==sample['model']]
        start=datetime.fromtimestamp(min(r['_start'] for r in selected)/1e6,timezone.utc).isoformat()
        end=datetime.fromtimestamp(max(r['_end'] for r in selected)/1e6,timezone.utc).isoformat()
        if start != sample['included_run_start_min_utc'] or end != sample['included_run_end_max_utc']:
            raise AssertionError('Sample collection window mismatch')
    for r in rows:
        for key in ('_identity','_start','_end'): r.pop(key)
    (output/'sample_identity_validation.json').write_text(json.dumps(identity_summary,indent=2)+'\n')
    cost = [{k: v for k, v in r.items() if k not in ('user', 'tokens')} for r in rows]
    token = []
    for r in rows:
        if canonical(r['model']) in SHARED:
            clean = {k: v for k, v in r.items() if k != 'user'}
            clean.update(dataset='TraceLab', model=canonical(r['model']), hours_primary=r['hours_uncapped'])
            token.append(clean)
    for index, line in enumerate(weka_source.open()):
        trace = json.loads(line)
        events, _ = weka.flatten(trace)
        events.sort(key=lambda e: (e.t, e.stream))
        main = [e for e in events if e.role == 'main']
        models = sorted({canonical(e.model) for e in main})
        if not set(models) <= set(SHARED):
            raise ValueError(f'Unexpected WEKA models: {models}')
        totals = {m: defaultdict(int) for m in ('recent', 'ttl300', 'ideal')}
        costs, roles = defaultdict(float), defaultdict(int)
        for e, recent, ttl, ideal in cache_reads(events, int(trace.get('block_size') or 64)):
            roles[e.role] += 1
            for method, read in [('recent', recent), ('ttl300', ttl), ('ideal', ideal)]:
                t = totals[method]
                t['input'] += e.input_tokens
                t['cached_input'] += read
                t['nonread_input'] += e.input_tokens - read
                t['output'] += e.output_tokens
                costs[method] += weka.price_request(e, read).total
        token.append(dict(dataset='WEKA', main_models=models,
            model=models[0] if len(models) == 1 else 'mixed_main_models',
            max_input=max((e.input_tokens for e in main), default=0), calls=len(events),
            main_calls=roles['main'], child_calls=roles['subagent'],
            mixed_calls=sum(canonical(e.model) not in models for e in events),
            tokens={k: dict(v) for k, v in totals.items()}, reconstructed_costs=dict(costs),
            hours_primary=weka.span_dropping_long_gaps(events)/3600,
            **{'hours_cap'+str(c): weka.compressed_span(events, c)/3600 for c in (0,30,60,300)}))
        if index % 100 == 0:
            print(f'WEKA roots reconstructed: {index+1}', flush=True)
    for name, records in [('cost_groups', cost), ('token_groups', token)]:
        (output / (name + '.json')).write_text(json.dumps(records, separators=(',', ':'))+'\n')
        compare(comparable(records), comparable(json.loads((DATA / (name+'.json')).read_text())), name)
    (output / 'validation.json').write_text(json.dumps(dict(
        raw_rebuild_matches_frozen=True, coverage=coverage,
        cost_groups=len(cost), token_groups=len(token)), indent=2)+'\n')
    return output
