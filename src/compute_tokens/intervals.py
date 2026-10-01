"""Core interval and trace analysis for the tool-wait deep dive.

The public functions intentionally use integer epoch microseconds.  That keeps the
interval algebra deterministic across native DuckDB and duckdb-wasm timestamp
marshalling and avoids floating-point drift until final presentation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence


Interval = tuple[int, int]

MODEL_OUTPUT_TYPES = ("reasoning", "text", "tool_call")
INPUT_TYPES = ("user_message", "tool_result")

HUMAN_APPROVAL_TOOLS = {
    "AskUserQuestion",
    "ExitPlanMode",
    "PushNotification",
    "request_user_input",
}
ORCHESTRATION_TOOLS = {
    "Agent",
    "Task",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskOutput",
    "TaskStop",
    "close_agent",
    "resume_agent",
    "spawn_agent",
    "wait_agent",
}
SHELL_TOOLS = {
    "Bash",
    "BashOutput",
    "KillBash",
    "KillShell",
    "exec",
    "exec_command",
    "mcp__ide__executeCode",
    "send_input",
    "shell",
    "shell_command",
    "wait",
    "write_stdin",
}
FILE_WRITE_TOOLS = {"Edit", "MultiEdit", "NotebookEdit", "Write", "apply_patch"}
FILE_READ_TOOLS = {
    "Glob",
    "Grep",
    "LS",
    "NotebookRead",
    "Read",
    "find",
    "list_directory",
    "read_file",
    "rg",
    "search_files",
    "view_image",
}
WEB_PREFIXES = ("mcp__", "web__")
WEB_TOOLS = {
    "LSP",
    "Skill",
    "ToolSearch",
    "WebFetch",
    "WebSearch",
    "list_mcp_resource_templates",
    "list_mcp_resources",
    "read_mcp_resource",
    "web_search",
}


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    """Return sorted, non-overlapping positive intervals; touching spans merge."""
    clean = sorted((int(a), int(b)) for a, b in intervals if a is not None and b is not None and b > a)
    merged: list[list[int]] = []
    for start, end in clean:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def clip_interval(interval: Interval, window: Interval) -> Interval | None:
    start = max(interval[0], window[0])
    end = min(interval[1], window[1])
    return (start, end) if end > start else None


def clip_intervals(intervals: Iterable[Interval], window: Interval) -> list[Interval]:
    return merge_intervals(clipped for item in intervals if (clipped := clip_interval(item, window)))


def intersect_intervals(left: Iterable[Interval], right: Iterable[Interval]) -> list[Interval]:
    a = merge_intervals(left)
    b = merge_intervals(right)
    out: list[Interval] = []
    i = j = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if end > start:
            out.append((start, end))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return out


def subtract_intervals(left: Iterable[Interval], right: Iterable[Interval]) -> list[Interval]:
    """Return the parts of ``left`` not covered by ``right``."""
    source = merge_intervals(left)
    blockers = merge_intervals(right)
    out: list[Interval] = []
    j = 0
    for start, end in source:
        cursor = start
        while j < len(blockers) and blockers[j][1] <= cursor:
            j += 1
        k = j
        while k < len(blockers) and blockers[k][0] < end:
            b_start, b_end = blockers[k]
            if b_start > cursor:
                out.append((cursor, min(b_start, end)))
            cursor = max(cursor, b_end)
            if cursor >= end:
                break
            k += 1
        if cursor < end:
            out.append((cursor, end))
    return out


def duration_us(intervals: Iterable[Interval]) -> int:
    return sum(end - start for start, end in merge_intervals(intervals))


def tool_stratum(tool_name: str) -> str:
    if tool_name in HUMAN_APPROVAL_TOOLS:
        return "human_approval"
    if tool_name in ORCHESTRATION_TOOLS:
        return "agent_orchestration"
    return "machine"


def tool_category(tool_name: str) -> str:
    if tool_name in HUMAN_APPROVAL_TOOLS:
        return "human_approval"
    if tool_name in ORCHESTRATION_TOOLS:
        return "agent_orchestration"
    if tool_name in SHELL_TOOLS or tool_name == "exec_command_chain":
        return "shell_command"
    if tool_name in FILE_WRITE_TOOLS:
        return "file_write_edit"
    if tool_name in FILE_READ_TOOLS:
        return "file_read_search"
    if tool_name in WEB_TOOLS or tool_name.startswith(WEB_PREFIXES):
        return "web_remote"
    return "other_machine"


@dataclass(frozen=True)
class ToolCall:
    round_pk: int
    tool_index: int
    tool_name: str
    tool_call_id: str | None
    continuation_of: str | None
    emitted_us: int | None
    result_us: int | None
    wall_ms: float | None
    internal_ms: float | None
    command_status: str | None

    @property
    def interval(self) -> Interval | None:
        if self.emitted_us is None or self.result_us is None or self.result_us <= self.emitted_us:
            return None
        return self.emitted_us, self.result_us


@dataclass(frozen=True)
class FinishedChain:
    provider: str
    user: str
    session_id: str
    root_id: str
    started_us: int
    finished_us: int
    continuation_calls: int
    tool_call_time_sum_ms: float | None


@dataclass
class ActiveTurn:
    provider: str
    user: str
    session_id: str
    start_us: int
    end_us: int | None = None
    generation_intervals: list[Interval] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)


@dataclass
class TimedItem:
    interval: Interval
    tool_name: str
    stratum: str
    category: str


@dataclass
class TurnSummary:
    provider: str
    user: str
    session_id: str
    start_us: int
    end_us: int
    e2e_us: int
    generation_us: int
    generation_only_us: int
    tool_open_us: int
    exclusive_tool_wait_us: int
    tool_generation_overlap_us: int
    unexplained_us: int
    standard_tool_union_us: int
    summed_wall_us: int
    summed_effective_us: int
    runner_internal_us: int
    overhead_residual_us: int
    call_count: int
    valid_interval_calls: int
    stratum_wait_us: dict[str, int]
    category_wait_us: dict[str, int]
    tool_wait_us: dict[str, int]


@dataclass
class AnalysisResult:
    turns: list[TurnSummary]
    coverage: dict[str, Any]
    chain_statuses: dict[str, int]
    chain_rows: list[FinishedChain]
    lifecycle_available: bool
    dropped_turns: Counter


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fetch_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _timestamp_to_epoch_us(value: Any) -> int | None:
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
    epoch = datetime(1970, 1, 1)
    return round((parsed - epoch).total_seconds() * 1_000_000)


def table_columns(con: Any, table: str) -> set[str]:
    return {str(row[0]) for row in con.execute(f"DESCRIBE {table}").fetchall()}


def load_finished_chains(
    con: Any, repo_root: Path
) -> tuple[dict[tuple[str, str, str, str], FinishedChain], Counter, bool]:
    columns = table_columns(con, "tool_calls")
    required = {"continuation_of_tool_call_id", "command_status", "command_exit_code"}
    if not required.issubset(columns):
        return {}, Counter({"unavailable_schema": 1}), False
    from .command_chains import command_chains

    rows = _fetch_dicts(command_chains(con))
    statuses: Counter = Counter()
    finished: dict[tuple[str, str, str, str], FinishedChain] = {}
    for row in rows:
        status = str(row.get("final_status") or "unknown")
        statuses[status] += 1
        if status != "finished" or row.get("observed_finished_at") is None:
            continue
        started_us = _timestamp_to_epoch_us(row.get("started_at"))
        finished_us = _timestamp_to_epoch_us(row.get("observed_finished_at"))
        if started_us is None or finished_us is None or finished_us <= started_us:
            continue
        provider = str(row.get("provider") or "<unknown-provider>")
        user = str(row.get("user") or "<unknown-user>")
        session_id = str(row.get("session_id") or "<unknown-session>")
        root_id = str(row["initial_tool_call_id"])
        chain = FinishedChain(
            provider=provider,
            user=user,
            session_id=session_id,
            root_id=root_id,
            started_us=int(started_us),
            finished_us=int(finished_us),
            continuation_calls=int(row.get("continuation_calls") or 0),
            tool_call_time_sum_ms=_number(row.get("tool_call_time_sum_ms")),
        )
        finished[(provider, user, session_id, root_id)] = chain
    return finished, statuses, True


def load_round_facts(con: Any) -> list[dict[str, Any]]:
    query = """
        WITH bounds AS (
          SELECT
            round_pk,
            MIN(timestamp) FILTER (WHERE event_type IN ('reasoning', 'text', 'tool_call')) AS first_output,
            MAX(timestamp) FILTER (WHERE event_type IN ('reasoning', 'text', 'tool_call')) AS last_output
          FROM timing_events
          GROUP BY round_pk
        ), qualified AS (
          SELECT
            te.round_pk,
            MAX(te.timestamp) FILTER (
              WHERE te.event_type = 'user_message' AND te.timestamp <= b.first_output
            ) AS user_start,
            MAX(te.timestamp) FILTER (
              WHERE te.event_type IN ('user_message', 'tool_result') AND te.timestamp <= b.first_output
            ) AS generation_start
          FROM timing_events te
          JOIN bounds b USING (round_pk)
          GROUP BY te.round_pk
        )
        SELECT
          r.round_pk,
          CASE WHEN r.provider IS NULL OR r.provider = '' THEN '<unknown-provider>' ELSE r.provider END AS provider,
          CASE WHEN r."user" IS NULL OR r."user" = '' THEN '<unknown-user>' ELSE r."user" END AS user_id,
          CASE WHEN r.session_id IS NULL OR r.session_id = '' THEN '<unknown-session>' ELSE r.session_id END AS session_id,
          CAST(epoch_us(q.user_start) AS BIGINT) AS user_start_us,
          CAST(epoch_us(q.generation_start) AS BIGINT) AS generation_start_us,
          CAST(epoch_us(b.last_output) AS BIGINT) AS last_output_us
        FROM rounds r
        LEFT JOIN bounds b USING (round_pk)
        LEFT JOIN qualified q USING (round_pk)
        ORDER BY r.round_pk
    """
    return _fetch_dicts(con.execute(query))


def load_tool_calls(con: Any) -> tuple[dict[int, list[ToolCall]], dict[str, Any]]:
    columns = table_columns(con, "tool_calls")
    continuation_expr = "tc.continuation_of_tool_call_id" if "continuation_of_tool_call_id" in columns else "NULL::VARCHAR"
    status_expr = "tc.command_status" if "command_status" in columns else "NULL::VARCHAR"
    query = """
        SELECT
          tc.round_pk,
          tc.tool_index,
          CASE WHEN tc.tool_name IS NULL OR trim(tc.tool_name) = '' THEN '<unknown-tool>' ELSE trim(tc.tool_name) END AS tool_name,
          tc.tool_call_id,
          {continuation_expr} AS continuation_of_tool_call_id,
          CAST(epoch_us(tc.emitted_at) AS BIGINT) AS emitted_us,
          CAST(epoch_us(tc.result_at) AS BIGINT) AS result_us,
          TRY_CAST(tc.tool_wall_latency_ms AS DOUBLE) AS wall_ms,
          TRY_CAST(tc.tool_internal_latency_ms AS DOUBLE) AS internal_ms,
          {status_expr} AS command_status
        FROM tool_calls tc
        ORDER BY tc.round_pk, tc.tool_index
    """.format(continuation_expr=continuation_expr, status_expr=status_expr)
    by_round: dict[int, list[ToolCall]] = defaultdict(list)
    coverage: Counter = Counter()
    names: Counter = Counter()
    for row in _fetch_dicts(con.execute(query)):
        call = ToolCall(
            round_pk=int(row["round_pk"]),
            tool_index=int(row["tool_index"]),
            tool_name=str(row["tool_name"]),
            tool_call_id=str(row["tool_call_id"]) if row.get("tool_call_id") is not None else None,
            continuation_of=str(row["continuation_of_tool_call_id"]) if row.get("continuation_of_tool_call_id") is not None else None,
            emitted_us=int(row["emitted_us"]) if row.get("emitted_us") is not None else None,
            result_us=int(row["result_us"]) if row.get("result_us") is not None else None,
            wall_ms=_number(row.get("wall_ms")),
            internal_ms=_number(row.get("internal_ms")),
            command_status=str(row["command_status"]) if row.get("command_status") is not None else None,
        )
        by_round[call.round_pk].append(call)
        coverage["calls"] += 1
        names[call.tool_name] += 1
        if call.interval is not None:
            coverage["valid_intervals"] += 1
        elif call.emitted_us is None or call.result_us is None:
            coverage["missing_interval"] += 1
        else:
            coverage["nonpositive_interval"] += 1
        if call.wall_ms is not None:
            coverage["wall_timed"] += 1
            if call.wall_ms > 0:
                coverage["positive_wall_latency_ms"] += call.wall_ms
        if call.internal_ms is not None:
            coverage["internal_timed"] += 1
        if call.wall_ms is not None and call.internal_ms is not None:
            coverage["both_timed"] += 1
        effective = call.internal_ms if call.internal_ms is not None else call.wall_ms
        if effective is not None and effective > 0:
            coverage["positive_effective_latency_ms"] += effective
    return by_round, {**dict(coverage), "unique_tools": len(names), "tool_names": dict(names)}


def _primary_items(
    turn: ActiveTurn,
    finished_chains: dict[tuple[str, str, str, str], FinishedChain],
    lifecycle_available: bool,
) -> tuple[list[TimedItem], list[TimedItem], Counter]:
    raw: list[TimedItem] = []
    lifecycle: list[TimedItem] = []
    chain_coverage: Counter = Counter()
    added_roots: set[str] = set()
    for call in turn.calls:
        interval = call.interval
        if interval is not None:
            raw.append(TimedItem(interval, call.tool_name, tool_stratum(call.tool_name), tool_category(call.tool_name)))

        if turn.provider == "codex" and call.tool_name in {"exec_command", "write_stdin"}:
            if not lifecycle_available:
                if interval is not None:
                    lifecycle.append(TimedItem(interval, call.tool_name, "machine", "shell_command"))
                continue
            root_id = call.tool_call_id if call.tool_name == "exec_command" else call.continuation_of
            if root_id is None:
                chain_coverage["unlinked_command_calls"] += 1
                continue
            key = (turn.provider, turn.user, turn.session_id, root_id)
            chain = finished_chains.get(key)
            if chain is None:
                chain_coverage["incomplete_command_calls"] += 1
                continue
            chain_coverage["completed_command_calls"] += 1
            if root_id not in added_roots:
                added_roots.add(root_id)
                lifecycle.append(
                    TimedItem(
                        (chain.started_us, chain.finished_us),
                        "exec_command_chain",
                        "machine",
                        "shell_command",
                    )
                )
            continue

        if interval is not None:
            lifecycle.append(TimedItem(interval, call.tool_name, tool_stratum(call.tool_name), tool_category(call.tool_name)))
    return raw, lifecycle, chain_coverage


def summarize_turn(
    turn: ActiveTurn,
    finished_chains: dict[tuple[str, str, str, str], FinishedChain],
    lifecycle_available: bool,
) -> tuple[TurnSummary | None, Counter]:
    if turn.end_us is None:
        return None, Counter({"no_response_end": 1})
    if turn.end_us <= turn.start_us:
        return None, Counter({"nonpositive_e2e": 1})
    window = (turn.start_us, turn.end_us)
    generation = clip_intervals(turn.generation_intervals, window)
    raw_items, lifecycle_items, chain_coverage = _primary_items(
        turn, finished_chains, lifecycle_available
    )

    raw_clipped = [clipped for item in raw_items if (clipped := clip_interval(item.interval, window))]
    primary_clipped = [
        TimedItem(clipped, item.tool_name, item.stratum, item.category)
        for item in lifecycle_items
        if (clipped := clip_interval(item.interval, window))
    ]
    tool_union = merge_intervals(item.interval for item in primary_clipped)
    standard_union = merge_intervals(raw_clipped)
    overlap = intersect_intervals(tool_union, generation)
    exclusive = subtract_intervals(tool_union, generation)
    generation_only = subtract_intervals(generation, tool_union)
    covered = merge_intervals([*tool_union, *generation])

    stratum_wait: dict[str, int] = {}
    category_wait: dict[str, int] = {}
    tool_wait: dict[str, int] = {}
    for attr, target in (
        ("stratum", stratum_wait),
        ("category", category_wait),
        ("tool_name", tool_wait),
    ):
        labels = sorted({getattr(item, attr) for item in primary_clipped})
        for label in labels:
            intervals = [item.interval for item in primary_clipped if getattr(item, attr) == label]
            target[label] = duration_us(subtract_intervals(intervals, generation))

    summed_wall_us = 0
    summed_effective_us = 0
    runner_internal_us = 0
    overhead_residual_us = 0
    for call in turn.calls:
        wall = call.wall_ms
        internal = call.internal_ms
        if wall is not None and wall > 0:
            summed_wall_us += round(wall * 1000)
        effective = internal if internal is not None else wall
        if effective is not None and effective > 0:
            summed_effective_us += round(effective * 1000)
        if internal is not None and internal > 0:
            runner_internal_us += round(internal * 1000)
        if wall is not None and internal is not None and wall > 0 and internal >= 0:
            overhead_residual_us += round(max(wall - internal, 0) * 1000)

    e2e_us = turn.end_us - turn.start_us
    unexplained_us = max(0, e2e_us - duration_us(covered))
    summary = TurnSummary(
        provider=turn.provider,
        user=turn.user,
        session_id=turn.session_id,
        start_us=turn.start_us,
        end_us=turn.end_us,
        e2e_us=e2e_us,
        generation_us=duration_us(generation),
        generation_only_us=duration_us(generation_only),
        tool_open_us=duration_us(tool_union),
        exclusive_tool_wait_us=duration_us(exclusive),
        tool_generation_overlap_us=duration_us(overlap),
        unexplained_us=unexplained_us,
        standard_tool_union_us=duration_us(standard_union),
        summed_wall_us=summed_wall_us,
        summed_effective_us=summed_effective_us,
        runner_internal_us=runner_internal_us,
        overhead_residual_us=overhead_residual_us,
        call_count=len(turn.calls),
        valid_interval_calls=sum(call.interval is not None for call in turn.calls),
        stratum_wait_us=stratum_wait,
        category_wait_us=category_wait,
        tool_wait_us=tool_wait,
    )
    return summary, chain_coverage


def analyze_database(con: Any, repo_root: Path) -> AnalysisResult:
    finished_chains, statuses, lifecycle_available = load_finished_chains(con, repo_root)
    calls_by_round, coverage = load_tool_calls(con)
    round_facts = load_round_facts(con)
    active: dict[tuple[str, str, str], ActiveTurn] = {}
    summaries: list[TurnSummary] = []
    dropped: Counter = Counter()
    chain_coverage: Counter = Counter()

    def close(key: tuple[str, str, str]) -> None:
        turn = active.pop(key, None)
        if turn is None:
            return
        summary, counters = summarize_turn(turn, finished_chains, lifecycle_available)
        if summary is None:
            dropped.update(counters)
        else:
            summaries.append(summary)
            chain_coverage.update(counters)

    for fact in round_facts:
        provider = str(fact["provider"])
        user = str(fact["user_id"])
        session_id = str(fact["session_id"])
        key = (provider, user, session_id)
        user_start = fact.get("user_start_us")
        if user_start is not None:
            close(key)
            active[key] = ActiveTurn(provider, user, session_id, int(user_start))
        turn = active.get(key)
        if turn is None:
            continue
        generation_start = fact.get("generation_start_us")
        last_output = fact.get("last_output_us")
        if generation_start is not None and last_output is not None and last_output > generation_start:
            turn.generation_intervals.append((int(generation_start), int(last_output)))
        if last_output is not None:
            last_output = int(last_output)
            turn.end_us = max(turn.end_us or last_output, last_output)
        turn.calls.extend(calls_by_round.get(int(fact["round_pk"]), []))

    for key in list(active):
        close(key)

    coverage.update({f"chain_{key}": value for key, value in chain_coverage.items()})
    coverage["retained_turns"] = len(summaries)
    coverage["finished_command_chains"] = len(finished_chains)
    coverage["command_lifecycle_available"] = int(lifecycle_available)
    return AnalysisResult(
        turns=summaries,
        coverage=coverage,
        chain_statuses=dict(statuses),
        chain_rows=list(finished_chains.values()),
        lifecycle_available=lifecycle_available,
        dropped_turns=dropped,
    )


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def bootstrap_mean_ci(values: Sequence[float], *, iterations: int = 10_000, seed: int = 20_260_819) -> tuple[float, float, float]:
    """Equal-unit bootstrap mean and percentile 95% interval."""
    if not values:
        return 0.0, 0.0, 0.0
    import numpy as np

    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.empty(iterations, dtype=float)
    batch = 500
    for start in range(0, iterations, batch):
        count = min(batch, iterations - start)
        samples = rng.choice(array, size=(count, len(array)), replace=True)
        means[start : start + count] = samples.mean(axis=1)
    return float(array.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))
