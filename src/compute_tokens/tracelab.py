#!/usr/bin/env python3
"""Estimate API-equivalent hourly cost for continuously running coding agents.

The analysis has two deliberately different denominators:

* agent-slot hours sum each session's autonomous wall time;
* root-workflow hours union parent and descendant intervals, when exact edges exist.

Human approval waits are removed. Machine tools, orchestration waits, model latency, and
otherwise-unexplained within-turn elapsed time remain because a continuously operated agent still
spends clock time on them.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import gzip
import hashlib
import html
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
from typing import Any, Iterable, Sequence

from .paths import ROOT, DATA
REPO_ROOT = ROOT
PUBLIC_DB = None
OUTPUT_DIR = ROOT / "build"
import duckdb  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .intervals import (  # noqa: E402
    HUMAN_APPROVAL_TOOLS,
    analyze_database,
    duration_us,
    intersect_intervals,
    load_round_facts,
    load_tool_calls,
    merge_intervals,
    percentile,
    subtract_intervals,
)


US_PER_HOUR = 3_600_000_000
LONG_CONTEXT_THRESHOLD = 272_000
MIN_SESSION_SECONDS_FOR_PERCENTILES = 300

OPENAI_PRICING_URL = "https://platform.openai.com/pricing"
OPENAI_FAST_URL = "https://developers.openai.com/api/docs/guides/fast-mode"
ANTHROPIC_PRICING_URL = "https://platform.claude.com/docs/en/about-claude/pricing"


@dataclass(frozen=True)
class Price:
    provider: str
    input_per_mtok: float
    cache_read_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float | None = None
    fast_input_per_mtok: float | None = None
    fast_cache_read_per_mtok: float | None = None
    fast_output_per_mtok: float | None = None
    fast_cache_write_per_mtok: float | None = None
    long_context: bool = False


# Prices retrieved from the official vendor pages on 2026-08-21. Claude cache writes assume the
# normal five-minute cache used by interactive coding; the report includes the one-hour sensitivity.
PRICES = {model: Price(**p) for model, p in json.loads((DATA / "prices.json").read_text()).items()}

COHORTS = [
    ("gpt56", "GPT-5.6 Sol", "gpt-5.6-sol"),
    ("gpt55", "GPT-5.5", "gpt-5.5"),
    ("fable5", "Claude Fable 5", "claude-fable-5"),
    ("opus48", "Claude Opus 4.8", "claude-opus-4-8"),
]


@dataclass
class CostParts:
    uncached_input: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0
    output: float = 0.0

    @property
    def total(self) -> float:
        return self.uncached_input + self.cache_read + self.cache_write + self.output

    def add(self, other: "CostParts") -> None:
        self.uncached_input += other.uncached_input
        self.cache_read += other.cache_read
        self.cache_write += other.cache_write
        self.output += other.output


@dataclass(frozen=True)
class RoundUsage:
    round_pk: int
    provider: str
    user: str
    session_id: str
    turn_id: str | None
    model: str | None
    input_total: int
    prefix: int
    newly_append: int
    claude_uncached: int
    claude_cache_write: int
    claude_cache_read: int
    output: int
    min_event_us: int | None
    last_output_us: int | None


@dataclass
class Run:
    provider: str
    user: str
    session_id: str
    start_us: int
    end_us: int
    model: str
    round_pks: list[int]
    standard: CostParts
    fast: CostParts
    generation_only_us: int
    exclusive_tool_us: int
    human_wait_us: int
    synthetic_start: bool
    mixed_model_cost: float = 0.0

    @property
    def autonomous_us(self) -> int:
        return max(0, self.end_us - self.start_us - self.human_wait_us)

    @property
    def fixed_us(self) -> int:
        return max(0, self.autonomous_us - self.generation_only_us)


def as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def epoch_us(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return round((parsed - datetime(1970, 1, 1)).total_seconds() * 1_000_000)


def price_round(row: RoundUsage, *, fast: bool = False, claude_one_hour_cache: bool = False) -> CostParts:
    spec = PRICES.get(row.model or "")
    if spec is None:
        return CostParts()
    if fast and spec.fast_input_per_mtok is not None:
        input_rate = spec.fast_input_per_mtok
        cache_read_rate = spec.fast_cache_read_per_mtok or spec.cache_read_per_mtok
        output_rate = spec.fast_output_per_mtok or spec.output_per_mtok
        cache_write_rate = spec.fast_cache_write_per_mtok
    else:
        input_rate = spec.input_per_mtok
        cache_read_rate = spec.cache_read_per_mtok
        output_rate = spec.output_per_mtok
        cache_write_rate = spec.cache_write_per_mtok

    input_multiplier = 1.0
    output_multiplier = 1.0
    if spec.long_context and row.input_total > LONG_CONTEXT_THRESHOLD:
        input_multiplier = 2.0
        output_multiplier = 1.5

    if spec.provider == "codex":
        return CostParts(
            uncached_input=row.newly_append * input_rate * input_multiplier / 1_000_000,
            cache_read=row.prefix * cache_read_rate * input_multiplier / 1_000_000,
            output=row.output * output_rate * output_multiplier / 1_000_000,
        )

    # Claude's extracted token categories are mutually exclusive. Cache write rates shown in the
    # official table are 1.25x base for five minutes and 2x base for one hour.
    if claude_one_hour_cache:
        cache_write_rate = input_rate * 2.0
    elif cache_write_rate is None:
        cache_write_rate = input_rate * 1.25
    return CostParts(
        uncached_input=row.claude_uncached * input_rate / 1_000_000,
        cache_read=row.claude_cache_read * cache_read_rate / 1_000_000,
        cache_write=row.claude_cache_write * cache_write_rate / 1_000_000,
        output=row.output * output_rate / 1_000_000,
    )


def load_usages(con: duckdb.DuckDBPyConnection) -> dict[int, RoundUsage]:
    query = """
        SELECT
          r.round_pk,
          COALESCE(NULLIF(r.provider, ''), '<unknown-provider>'),
          COALESCE(NULLIF(r."user", ''), '<unknown-user>'),
          COALESCE(NULLIF(r.session_id, ''), '<unknown-session>'),
          CAST(r.turn_id AS VARCHAR),
          r.model,
          r.input_tokens_total,
          r.prefix_tokens,
          r.newly_append_tokens,
          TRY_CAST(r.claude_uncached_input_tokens AS BIGINT),
          TRY_CAST(r.claude_cache_creation_input_tokens AS BIGINT),
          TRY_CAST(r.claude_cache_read_input_tokens AS BIGINT),
          r.output_tokens,
          MIN(te.timestamp),
          MAX(te.timestamp) FILTER (WHERE te.event_type IN ('reasoning', 'text', 'tool_call'))
        FROM rounds r
        LEFT JOIN timing_events te USING (round_pk)
        GROUP BY ALL
        ORDER BY r.round_pk
    """
    rows: dict[int, RoundUsage] = {}
    for raw in con.execute(query).fetchall():
        row = RoundUsage(
            round_pk=int(raw[0]),
            provider=str(raw[1]),
            user=str(raw[2]),
            session_id=str(raw[3]),
            turn_id=str(raw[4]) if raw[4] is not None else None,
            model=str(raw[5]) if raw[5] is not None else None,
            input_total=as_int(raw[6]),
            prefix=as_int(raw[7]),
            newly_append=as_int(raw[8]),
            claude_uncached=as_int(raw[9]),
            claude_cache_write=as_int(raw[10]),
            claude_cache_read=as_int(raw[11]),
            output=as_int(raw[12]),
            min_event_us=epoch_us(raw[13]),
            last_output_us=epoch_us(raw[14]),
        )
        rows[row.round_pk] = row
    return rows


def priced_model(round_pks: Sequence[int], usages: dict[int, RoundUsage]) -> str | None:
    return next((usages[pk].model for pk in round_pks if usages[pk].model in PRICES), None)


def sum_cost(round_pks: Sequence[int], usages: dict[int, RoundUsage], *, fast: bool = False) -> CostParts:
    out = CostParts()
    for pk in round_pks:
        out.add(price_round(usages[pk], fast=fast))
    return out


def load_external_turn_starts(path: Path | None) -> dict[tuple[str, str], int]:
    if path is None or not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {
        (str(item["session_id"]), str(item["turn_id"])): int(item["start_us"])
        for item in doc.get("turn_starts", [])
        if item.get("session_id") is not None
        and item.get("turn_id") is not None
        and item.get("start_us") is not None
    }


def build_runs(
    con: duckdb.DuckDBPyConnection, *, external_turn_starts: Path | None = None,
    eligible_models: set[str] | None = None,
) -> tuple[list[Run], dict[str, Any]]:
    """Reconstruct runs; opt-in model eligibility makes token-only work price-independent.

    Default cost-analysis selection is unchanged. With eligible_models, choose the
    first allowed model and retain timed runs even when no price is available.
    Computed cost fields may then be incomplete and must not be used as bills.
    """
    allowed_models = set(PRICES) if eligible_models is None else eligible_models

    def select_model(pks):
        return next((usages[pk].model for pk in pks if usages[pk].model in allowed_models), None)

    result = analyze_database(con, REPO_ROOT)
    facts = load_round_facts(con)
    calls_by_round, _ = load_tool_calls(con)
    usages = load_usages(con)
    exact_starts = load_external_turn_starts(external_turn_starts)

    current: dict[tuple[str, str, str], int] = {}
    round_groups: dict[tuple[str, str, str, int], list[int]] = defaultdict(list)
    fact_by_pk: dict[int, dict[str, Any]] = {}
    for fact in facts:
        pk = int(fact["round_pk"])
        fact_by_pk[pk] = fact
        session = (str(fact["provider"]), str(fact["user_id"]), str(fact["session_id"]))
        if fact.get("user_start_us") is not None:
            current[session] = int(fact["user_start_us"])
        if session in current:
            round_groups[(*session, current[session])].append(pk)

    summaries = {
        (turn.provider, turn.user, turn.session_id, turn.start_us): turn for turn in result.turns
    }
    runs: list[Run] = []
    assigned: set[int] = set()
    for key, pks in round_groups.items():
        turn = summaries.get(key)
        if turn is None:
            continue
        model = select_model(pks)
        if model is None:
            continue
        assigned.update(pks)
        standard = sum_cost(pks, usages)
        fast = sum_cost(pks, usages, fast=True)
        mixed = sum(
            price_round(usages[pk]).total
            for pk in pks
            if usages[pk].model in PRICES and usages[pk].model != model
        )
        runs.append(
            Run(
                provider=turn.provider,
                user=turn.user,
                session_id=turn.session_id,
                start_us=turn.start_us,
                end_us=turn.end_us,
                model=model,
                round_pks=list(pks),
                standard=standard,
                fast=fast,
                generation_only_us=turn.generation_only_us,
                exclusive_tool_us=turn.exclusive_tool_wait_us,
                human_wait_us=as_int(turn.stratum_wait_us.get("human_approval")),
                synthetic_start=False,
                mixed_model_cost=mixed,
            )
        )

    # Codex subagent files can start from a synthetic prompt. They then contain tool_result/output
    # events but no human user_message, so the normal request state machine has no start marker.
    # Treat all residual priced rounds in one session as one autonomous child run.
    residual: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for pk, usage in usages.items():
        if pk not in assigned and usage.model in allowed_models:
            residual_turn = usage.turn_id or f"unlinked:{usage.session_id}"
            residual[(usage.provider, usage.user, usage.session_id, residual_turn)].append(pk)

    residual_with_time = 0
    residual_without_time = 0
    exact_synthetic_starts = 0
    inferred_synthetic_starts = 0
    for (provider, user, session_id, turn_id), pks in residual.items():
        starts = [usages[pk].min_event_us for pk in pks if usages[pk].min_event_us is not None]
        ends = [usages[pk].last_output_us for pk in pks if usages[pk].last_output_us is not None]
        exact_start = exact_starts.get((session_id, turn_id))
        if not ends or (not starts and exact_start is None):
            residual_without_time += len(pks)
            continue
        start_us = exact_start if exact_start is not None else min(starts)
        end_us = max(ends)
        if end_us <= start_us:
            residual_without_time += len(pks)
            continue
        if exact_start is not None:
            exact_synthetic_starts += 1
        else:
            inferred_synthetic_starts += 1
        assert start_us is not None and end_us is not None
        model = select_model(pks)
        if model is None:
            continue
        generation_intervals = []
        tool_intervals = []
        human_intervals = []
        for pk in pks:
            fact = fact_by_pk.get(pk, {})
            g_start = fact.get("generation_start_us")
            g_end = fact.get("last_output_us")
            if g_start is not None and g_end is not None and int(g_end) > int(g_start):
                generation_intervals.append((int(g_start), int(g_end)))
            for call in calls_by_round.get(pk, []):
                if call.interval is None:
                    continue
                tool_intervals.append(call.interval)
                if call.tool_name in HUMAN_APPROVAL_TOOLS:
                    human_intervals.append(call.interval)
        generation_only = duration_us(subtract_intervals(generation_intervals, tool_intervals))
        exclusive_tool = duration_us(subtract_intervals(tool_intervals, generation_intervals))
        human_wait = duration_us(human_intervals)
        standard = sum_cost(pks, usages)
        fast = sum_cost(pks, usages, fast=True)
        mixed = sum(
            price_round(usages[pk]).total
            for pk in pks
            if usages[pk].model in PRICES and usages[pk].model != model
        )
        runs.append(
            Run(
                provider=provider,
                user=user,
                session_id=session_id,
                start_us=start_us,
                end_us=end_us,
                model=model,
                round_pks=list(pks),
                standard=standard,
                fast=fast,
                generation_only_us=generation_only,
                exclusive_tool_us=exclusive_tool,
                human_wait_us=human_wait,
                synthetic_start=True,
                mixed_model_cost=mixed,
            )
        )
        assigned.update(pks)
        residual_with_time += len(pks)

    total_priced = sum(price_round(row).total for row in usages.values())
    assigned_priced = sum(run.standard.total for run in runs)
    unpriced_models = Counter(row.model or "<missing>" for row in usages.values() if row.model not in PRICES)
    coverage = {
        "rounds": len(usages),
        "normal_runs": sum(not run.synthetic_start for run in runs),
        "synthetic_start_runs": sum(run.synthetic_start for run in runs),
        "priced_round_cost_usd": total_priced,
        "assigned_run_cost_usd": assigned_priced,
        "priced_cost_coverage": assigned_priced / total_priced if total_priced else 0.0,
        "unpriced_rounds": sum(unpriced_models.values()),
        "unpriced_models": dict(unpriced_models),
        "residual_rounds_with_time": residual_with_time,
        "residual_rounds_without_time": residual_without_time,
        "exact_synthetic_turn_starts": exact_synthetic_starts,
        "inferred_synthetic_turn_starts": inferred_synthetic_starts,
        "human_wait_hours_removed": sum(run.human_wait_us for run in runs) / US_PER_HOUR,
    }
    return [run for run in runs if run.autonomous_us > 0 and
            (eligible_models is not None or run.standard.total > 0)], coverage


def quantile(values: Sequence[float], q: float) -> float:
    return percentile(values, q) if values else 0.0
