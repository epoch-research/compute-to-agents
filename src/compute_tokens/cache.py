#!/usr/bin/env python3
"""Reprice coding-agent cohorts as if human pauses did not evict prompt caches.

Two counterfactuals are emitted:

* ``tracelab_upper_bound`` applies TraceLab's published retained-cache transform to every
  user-initiated step with a predecessor in the same session.
* ``ttl_gated`` applies the same transform only when the observed human idle gap exceeds the
  provider/model retention threshold: 5 minutes for Claude, 30 minutes for GPT-5.6, and
  24 hours for GPT-5.5.

For GPT-5.6, all non-cache-read input is treated as a cache write, matching the
explicit sensitivity assumption requested for this investigation.  Models without a listed
cache-write price keep ordinary fresh-input pricing.
"""

from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
from pathlib import Path

import duckdb

from .tracelab import (
    COHORTS,
    LONG_CONTEXT_THRESHOLD,
    OUTPUT_DIR,
    PRICES,
    PUBLIC_DB,
    US_PER_HOUR,
    CostParts,
    RoundUsage,
    build_runs,
    load_usages,
    priced_model,
)


@dataclass(frozen=True)
class CacheState:
    event_type: str | None
    has_predecessor: bool
    idle_gap_s: float | None
    ttl_seconds: int
    cf_append_upper: int
    cf_append_ttl: int


def _as_int(value: object) -> int:
    if value is None:
        return 0
    return int(value)


def load_cache_states(con: duckdb.DuckDBPyConnection) -> dict[int, CacheState]:
    rows = con.execute(
        """
        WITH first_ev AS (
          SELECT round_pk,
                 event_type,
                 CAST(epoch_us(timestamp) AS BIGINT) AS first_event_us
          FROM timing_events
          WHERE event_index = 1
        ),
        activity AS (
          SELECT round_pk, CAST(epoch_us(timestamp) AS BIGINT) AS activity_us
          FROM timing_events WHERE timestamp IS NOT NULL
          UNION ALL
          SELECT round_pk, CAST(epoch_us(emitted_at) AS BIGINT)
          FROM tool_calls WHERE emitted_at IS NOT NULL
          UNION ALL
          SELECT round_pk, CAST(epoch_us(result_at) AS BIGINT)
          FROM tool_calls WHERE result_at IS NOT NULL
        ),
        bounds AS (
          SELECT round_pk, MIN(activity_us) AS min_activity_us,
                 MAX(activity_us) AS last_activity_us
          FROM activity GROUP BY round_pk
        )
        SELECT r.round_pk,
               r.provider,
               COALESCE(r."user", ''),
               r.session_id,
               r.model,
               COALESCE(r.input_tokens_total, 0),
               COALESCE(r.newly_append_tokens, 0),
               f.event_type,
               COALESCE(f.first_event_us, b.min_activity_us),
               b.last_activity_us
        FROM rounds r
        LEFT JOIN first_ev f USING (round_pk)
        LEFT JOIN bounds b USING (round_pk)
        ORDER BY r.round_pk
        """
    ).fetchall()

    last: dict[tuple[str, str, str], tuple[int, int | None, str]] = {}
    states: dict[int, CacheState] = {}
    for raw in rows:
        round_pk = int(raw[0])
        key = (str(raw[1] or ""), str(raw[2] or ""), str(raw[3] or ""))
        model = str(raw[4] or "")
        total = _as_int(raw[5])
        append = _as_int(raw[6])
        event_type = str(raw[7]) if raw[7] is not None else None
        first_us = int(raw[8]) if raw[8] is not None else None
        last_us = int(raw[9]) if raw[9] is not None else None
        previous = last.get(key)
        has_predecessor = previous is not None
        idle_gap_s = None
        if event_type == "user_message" and previous is not None:
            previous_total, previous_last_us, previous_model = previous
            if first_us is not None and previous_last_us is not None and first_us >= previous_last_us:
                idle_gap_s = (first_us - previous_last_us) / 1_000_000
            context_growth = max(0, total - previous_total)
            # A different model cannot reuse KV; a context shrink may be
            # compaction/restructuring rather than expiration of an intact prefix.
            retained_append = (
                min(append, context_growth)
                if model == previous_model and total >= previous_total
                else append
            )
        else:
            retained_append = append
        ttl_seconds = {
            "gpt-5.6-sol": 30 * 60,
            "gpt-5.5": 24 * 60 * 60,
        }.get(model, 5 * 60)
        ttl_append = (
            retained_append
            if event_type == "user_message"
            and idle_gap_s is not None
            and idle_gap_s > ttl_seconds
            else append
        )
        states[round_pk] = CacheState(
            event_type=event_type,
            has_predecessor=has_predecessor,
            idle_gap_s=idle_gap_s,
            ttl_seconds=ttl_seconds,
            cf_append_upper=retained_append,
            cf_append_ttl=ttl_append,
        )
        last[key] = (total, last_us, model)
    return states


def price_with_split(row: RoundUsage, *, append: int, assume_codex_writes: bool) -> CostParts:
    spec = PRICES.get(row.model or "")
    if spec is None:
        return CostParts()
    prefix = max(0, row.input_total - append)
    input_multiplier = 1.0
    output_multiplier = 1.0
    if spec.long_context and row.input_total > LONG_CONTEXT_THRESHOLD:
        input_multiplier = 2.0
        output_multiplier = 1.5

    if spec.provider == "codex":
        write_rate = spec.cache_write_per_mtok if assume_codex_writes else None
        if write_rate is None:
            return CostParts(
                uncached_input=append * spec.input_per_mtok * input_multiplier / 1_000_000,
                cache_read=prefix * spec.cache_read_per_mtok * input_multiplier / 1_000_000,
                output=row.output * spec.output_per_mtok * output_multiplier / 1_000_000,
            )
        return CostParts(
            cache_write=append * write_rate * input_multiplier / 1_000_000,
            cache_read=prefix * spec.cache_read_per_mtok * input_multiplier / 1_000_000,
            output=row.output * spec.output_per_mtok * output_multiplier / 1_000_000,
        )

    shifted = max(0, row.newly_append - append)
    cache_write = min(append, max(0, row.claude_cache_write - shifted))
    uncached = max(0, append - cache_write)
    write_rate = spec.cache_write_per_mtok or spec.input_per_mtok * 1.25
    return CostParts(
        uncached_input=uncached * spec.input_per_mtok / 1_000_000,
        cache_read=prefix * spec.cache_read_per_mtok / 1_000_000,
        cache_write=cache_write * write_rate / 1_000_000,
        output=row.output * spec.output_per_mtok / 1_000_000,
    )


def add(parts: CostParts, other: CostParts) -> None:
    parts.add(other)
