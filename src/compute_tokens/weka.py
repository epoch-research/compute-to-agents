#!/usr/bin/env python3
"""Estimate continuous-agent hourly cost for the SemiAnalysis AgentX corpus.

The public WEKA file preserves reconstructed prompt blocks, source-model labels,
output tokens, request timing, and explicit subagent groups. It does not publish
Anthropic's billed cache counters. This module supplies flattening, price and
clock primitives; prefix.py implements the audited completion-ordered, same-model
recent/TTL/ideal cache reconstructions used by rebuild.py.
"""

from __future__ import annotations

import argparse
import csv
import heapq
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable


IDLE_CAP_SECONDS = 300.0
MIN_RATE_SECONDS = 300.0
IDLE_CAPS = (0.0, 30.0, 60.0, 300.0, 1800.0)


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float
    output_per_mtok: float


# Official list prices re-verified on 2026-08-24.
# Claude's five-minute prompt-cache write multiplier is 1.25x base input.
PRICES: dict[str, Price] = {
    "claude-fable-5": Price(10.0, 12.50, 1.0, 50.0),
    "claude-opus-4-8": Price(5.0, 6.25, 0.50, 25.0),
    "claude-opus-4-7": Price(5.0, 6.25, 0.50, 25.0),
    "claude-opus-4-6": Price(5.0, 6.25, 0.50, 25.0),
    "claude-sonnet-4-6": Price(3.0, 3.75, 0.30, 15.0),
    "claude-sonnet-4-5": Price(3.0, 3.75, 0.30, 15.0),
    "claude-haiku-4-5-20251001": Price(1.0, 1.25, 0.10, 5.0),
}


@dataclass
class Cost:
    input: float = 0.0
    cache_write: float = 0.0
    cache_read: float = 0.0
    output: float = 0.0

    @property
    def total(self) -> float:
        return self.input + self.cache_write + self.cache_read + self.output

    def add(self, other: "Cost") -> None:
        self.input += other.input
        self.cache_write += other.cache_write
        self.cache_read += other.cache_read
        self.output += other.output


@dataclass
class Event:
    stream: str
    role: str
    t: float
    api_time: float
    model: str
    input_tokens: int
    output_tokens: int
    hashes: list[int]

    @property
    def end(self) -> float:
        return self.t + self.api_time


@dataclass
class TraceMetric:
    trace_id: str
    main_max_input: int
    any_max_input: int
    main_requests: int
    subagent_requests: int
    subagent_groups: int
    active_wall_seconds: float
    raw_wall_seconds: float
    main_active_seconds: float
    agent_slot_seconds: float
    retained: Cost = field(default_factory=Cost)
    ttl: Cost = field(default_factory=Cost)
    no_cache: Cost = field(default_factory=Cost)
    retained_main: Cost = field(default_factory=Cost)
    retained_subagent: Cost = field(default_factory=Cost)
    active_wall_by_cap: dict[float, float] = field(default_factory=dict)
    active_wall_drop_long_seconds: float = 0.0
    main_models: set[str] = field(default_factory=set)
    all_models: set[str] = field(default_factory=set)

    @property
    def wall_hours(self) -> float:
        return self.active_wall_seconds / 3600.0

    @property
    def slot_hours(self) -> float:
        return self.agent_slot_seconds / 3600.0


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    weight = pos - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def lcp_tokens(left: Event | None, right: Event, block_size: int) -> int:
    if left is None or left.end > right.t:
        return 0
    count = 0
    for a, b in zip(left.hashes, right.hashes):
        if a != b:
            break
        count += 1
    return min(right.input_tokens, count * block_size)


def price_request(event: Event, cache_read_tokens: int, *, no_cache: bool = False) -> Cost:
    price = PRICES.get(event.model)
    if price is None:
        raise KeyError(f"No price configured for source model {event.model!r}")
    cache_read_tokens = min(max(0, cache_read_tokens), event.input_tokens)
    output = event.output_tokens * price.output_per_mtok / 1_000_000
    if no_cache:
        return Cost(
            input=event.input_tokens * price.input_per_mtok / 1_000_000,
            output=output,
        )
    return Cost(
        cache_write=(event.input_tokens - cache_read_tokens)
        * price.cache_write_per_mtok
        / 1_000_000,
        cache_read=cache_read_tokens * price.cache_read_per_mtok / 1_000_000,
        output=output,
    )


def compressed_span(events: Iterable[Event], idle_cap: float = IDLE_CAP_SECONDS) -> float:
    intervals = sorted((event.t, event.end) for event in events)
    if not intervals:
        return 0.0
    merged: list[tuple[float, float]] = []
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            merged.append((start, end))
            start, end = next_start, next_end
    merged.append((start, end))
    total = merged[0][1] - merged[0][0]
    for previous, current in zip(merged, merged[1:]):
        gap = current[0] - previous[1]
        total += min(gap, idle_cap) + current[1] - current[0]
    return total


def span_dropping_long_gaps(
    events: Iterable[Event], threshold: float = IDLE_CAP_SECONDS
) -> float:
    """Keep model intervals and short gaps, but remove gaps at/above threshold."""
    intervals = sorted((event.t, event.end) for event in events)
    if not intervals:
        return 0.0
    merged: list[tuple[float, float]] = []
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            merged.append((start, end))
            start, end = next_start, next_end
    merged.append((start, end))
    total = merged[0][1] - merged[0][0]
    for previous, current in zip(merged, merged[1:]):
        gap = current[0] - previous[1]
        if gap < threshold:
            total += gap
        total += current[1] - current[0]
    return total


def flatten(trace: dict[str, Any]) -> tuple[list[Event], int]:
    events: list[Event] = []
    group_count = 0
    for outer_index, entry in enumerate(trace.get("requests", [])):
        if entry.get("type") == "subagent":
            group_count += 1
            stream = f"subagent:{entry.get('agent_id') or outer_index}"
            for request in entry.get("requests", []):
                events.append(
                    Event(
                        stream=stream,
                        role="subagent",
                        t=float(request.get("t") or 0.0),
                        api_time=max(0.0, float(request.get("api_time") or 0.0)),
                        model=str(request.get("model") or ""),
                        input_tokens=int(request.get("in") or 0),
                        output_tokens=int(request.get("out") or 0),
                        hashes=request.get("hash_ids") or [],
                    )
                )
            continue
        events.append(
            Event(
                stream="main",
                role="main",
                t=float(entry.get("t") or 0.0),
                api_time=max(0.0, float(entry.get("api_time") or 0.0)),
                model=str(entry.get("model") or ""),
                input_tokens=int(entry.get("in") or 0),
                output_tokens=int(entry.get("out") or 0),
                hashes=entry.get("hash_ids") or [],
            )
        )
    return events, group_count
