"""Fable/Opus peak-context cohorts, using the September audit's unchanged clocks.

Request-only response-span diagnostics are not continuous-agent hourly rates.
Writes aggregate metadata only; does not refresh prices or personal collection.
"""
from collections import defaultdict
import csv
import json

from . import tracelab as ca, cache as hc
from .clock import measured_clock
from .intervals import (load_round_facts, load_tool_calls, load_finished_chains,
                        merge_intervals, HUMAN_APPROVAL_TOOLS, duration_us)

MODELS = ('claude-fable-5', 'claude-opus-4-8')
THRESHOLD = 500_000
MIN_SESSION_HOURS_FOR_PERCENTILES = 5 / 60


def session_rate_percentiles(rows):
    """Equal-session quantiles; keep the audit's five-active-minute eligibility rule."""
    eligible = [r for r in rows if r['hours_uncapped'] >= MIN_SESSION_HOURS_FOR_PERCENTILES]
    result = {'percentile_eligible_sessions': len(eligible),
              'percentile_excluded_short_sessions': len(rows) - len(eligible)}
    for cost in ('observed', 'retained'):
        rates = [r[cost + '_cost'] / r['hours_uncapped'] for r in eligible]
        for p in (25, 50, 75):
            result[f'{cost}_session_rate_p{p}'] = ca.quantile(rates, p / 100) if rates else None
    return result


def collect_session_rows(models=MODELS, *, include_token_totals=False, include_identity=False):
    """Shared audited reconstruction; retain private contributor labels in memory only."""
    con = ca.duckdb.connect(str(ca.PUBLIC_DB), read_only=True)
    runs, coverage = ca.build_runs(con)
    print('Runs loaded; reconstructing audited cohorts', flush=True)
    usages = ca.load_usages(con)
    states = hc.load_cache_states(con)
    facts = {r['round_pk']: r for r in load_round_facts(con)}
    calls, _ = load_tool_calls(con)
    chains, _, _ = load_finished_chains(con, ca.REPO_ROOT)
    con.close()
    chain_intervals = defaultdict(list)
    for c in chains.values():
        chain_intervals[(c.provider, c.user, c.session_id)].append((c.started_us, c.finished_us))
    grouped = defaultdict(list)
    for run in runs:
        if run.model in models:
            grouped[(run.provider, run.user, run.session_id, run.model)].append(run)
    rows = []
    request_stats = defaultdict(lambda: defaultdict(float))
    for key, selected in grouped.items():
        pks = {pk for run in selected for pk in run.round_pks}
        windows = merge_intervals((r.start_us, r.end_us) for r in selected)
        human, generation = [], []
        machine = list(chain_intervals[key[:3]])
        observed = retained = no_write = no_write_retained = 0.
        token_totals = {name: defaultdict(int) for name in ('observed', 'retained')}
        high_spans = []
        for pk in pks:
            u = usages[pk]
            if include_token_totals:
                for name, append in [('observed', u.newly_append),
                                     ('retained', states[pk].cf_append_ttl)]:
                    assert 0 <= append <= u.input_total and u.output >= 0
                    t = token_totals[name]
                    t['input'] += u.input_total
                    t['cached_input'] += u.input_total - append
                    t['nonread_input'] += append
                    t['output'] += u.output
                    if u.provider == 'claude':
                        assert u.input_total == u.claude_cache_read + u.claude_cache_write + u.claude_uncached
                        if name == 'observed':
                            assert u.input_total - append == u.claude_cache_read
                        shifted = max(0, u.newly_append - append)
                        write = min(append, max(0, u.claude_cache_write - shifted))
                        t['cache_write'] += write
                        t['ordinary_input'] += append - write
            observed_cost = hc.price_with_split(u, append=u.newly_append, assume_codex_writes=True).total
            retained_cost = hc.price_with_split(u, append=states[pk].cf_append_ttl, assume_codex_writes=True).total
            observed += observed_cost
            retained += retained_cost
            no_write += hc.price_with_split(u, append=u.newly_append, assume_codex_writes=False).total
            no_write_retained += hc.price_with_split(u, append=states[pk].cf_append_ttl,
                                                   assume_codex_writes=False).total
            f = facts.get(pk, {})
            a, b = f.get('generation_start_us'), f.get('last_output_us')
            valid = a is not None and b is not None and b > a
            if valid:
                generation.append((a, b))
            for call in calls.get(pk, []):
                if call.interval:
                    (human if call.tool_name in HUMAN_APPROVAL_TOOLS else machine).append(call.interval)
            if u.model == key[3] and u.input_total > THRESHOLD:
                q = request_stats[key[3]]
                q['calls'] += 1
                q['observed_cost_all_calls'] += observed_cost
                q['retained_cost_all_calls'] += retained_cost
                q['input_tokens'] += u.input_total
                if valid:
                    high_spans.append((a, b))
                    q['timed_calls'] += 1
                    q['observed_cost_timed_calls'] += observed_cost
                    q['retained_cost_timed_calls'] += retained_cost
        request_stats[key[3]]['response_span_hours'] += duration_us(high_spans) / ca.US_PER_HOUR
        protected = merge_intervals([*machine, *generation])
        row = {'model': key[3], 'user': key[1], 'calls': len(pks),
               'max_input': max(usages[pk].input_total for pk in pks),
               'exact_model_max_input': max((usages[pk].input_total for pk in pks
                                             if usages[pk].model == key[3]), default=0),
               'mixed_calls': sum(usages[pk].model != key[3] for pk in pks),
               'unpriced_calls': sum(usages[pk].model not in ca.PRICES for pk in pks),
               'observed_cost': observed, 'retained_cost': retained,
               'no_write_cost': no_write, 'no_write_retained_cost': no_write_retained,
               'high_calls': sum(usages[pk].input_total > THRESHOLD for pk in pks)}
        if include_token_totals:
            row['tokens'] = {name: dict(t) for name, t in token_totals.items()}
        if include_identity:
            # In memory only; never serialize these pseudonymous source identifiers.
            row['_identity'] = key[:3]
            row['_start'] = min(r.start_us for r in selected)
            row['_end'] = max(r.end_us for r in selected)
        for label, cap in [('uncapped', float('inf')), ('cap300', 300e6),
                           ('cap60', 60e6), ('cap30', 30e6)]:
            row['hours_' + label] = measured_clock(windows, protected, human, cap)[0] / ca.US_PER_HOUR
        rows.append(row)
    return rows, request_stats, coverage
