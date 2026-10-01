"""Reconstruct Codex command lifecycles from normalized tool-call facts.

The normalized trace stores only per-call facts. An ``exec_command`` keeps its own
``tool_call_id``; each related ``write_stdin`` points back through
``continuation_of_tool_call_id``. This module owns the derived lifecycle policy so experiments do
not independently reinterpret those calls.
"""

# Adapted for the standalone report package; upstream TraceLab attribution in NOTICE.
from __future__ import annotations

from typing import Any


COMMAND_CHAINS_SQL = r"""
WITH command_calls AS (
  SELECT
    r.provider,
    r."user" AS user_id,
    r.session_id,
    tc.round_pk,
    tc.tool_index,
    tc.tool_name,
    tc.tool_call_id,
    CASE
      WHEN tc.tool_name = 'exec_command' THEN tc.tool_call_id
      ELSE tc.continuation_of_tool_call_id
    END AS initial_tool_call_id,
    tc.emitted_at,
    tc.result_at,
    tc.command_status,
    tc.command_exit_code,
    COALESCE(
      TRY_CAST(tc.tool_internal_latency_ms AS DOUBLE),
      TRY_CAST(tc.tool_wall_latency_ms AS DOUBLE)
    ) AS tool_call_time_ms
  FROM tool_calls AS tc
  JOIN rounds AS r USING (round_pk)
  WHERE r.provider = 'codex'
    AND tc.tool_name IN ('exec_command', 'write_stdin')
),
roots AS (
  SELECT *
  FROM command_calls
  WHERE tool_name = 'exec_command'
),
finished_calls AS (
  SELECT
    *,
    row_number() OVER (
      PARTITION BY provider, user_id, session_id, initial_tool_call_id
      ORDER BY round_pk, tool_index
    ) AS finish_order
  FROM command_calls
  WHERE command_status = 'finished'
    AND initial_tool_call_id IS NOT NULL
),
latest_calls AS (
  SELECT
    *,
    row_number() OVER (
      PARTITION BY provider, user_id, session_id, initial_tool_call_id
      ORDER BY round_pk DESC, tool_index DESC
    ) AS latest_order
  FROM command_calls
  WHERE initial_tool_call_id IS NOT NULL
),
call_sums AS (
  SELECT
    provider,
    user_id,
    session_id,
    initial_tool_call_id,
    count(*) FILTER (WHERE tool_name = 'write_stdin') AS continuation_calls,
    CASE
      WHEN count(tool_call_time_ms) > 0 THEN sum(tool_call_time_ms)
    END AS tool_call_time_sum_ms
  FROM command_calls
  WHERE initial_tool_call_id IS NOT NULL
  GROUP BY provider, user_id, session_id, initial_tool_call_id
)
SELECT
  roots.provider,
  roots.user_id AS "user",
  roots.session_id,
  roots.tool_call_id AS initial_tool_call_id,
  roots.emitted_at AS started_at,
  roots.command_status AS initial_status,
  CASE
    WHEN finished_calls.tool_call_id IS NOT NULL THEN 'finished'
    ELSE latest_calls.command_status
  END AS final_status,
  finished_calls.command_exit_code,
  call_sums.continuation_calls,
  finished_calls.tool_call_id AS finishing_tool_call_id,
  finished_calls.result_at AS observed_finished_at,
  CASE
    WHEN roots.emitted_at IS NOT NULL AND finished_calls.result_at IS NOT NULL THEN
      CAST(round(
        (CAST(epoch_us(finished_calls.result_at) AS BIGINT)
         - CAST(epoch_us(roots.emitted_at) AS BIGINT)) / 1000.0
      ) AS BIGINT)
  END AS wall_time_until_finished_ms,
  call_sums.tool_call_time_sum_ms
FROM roots
LEFT JOIN finished_calls
  ON finished_calls.provider = roots.provider
 AND finished_calls.user_id IS NOT DISTINCT FROM roots.user_id
 AND finished_calls.session_id = roots.session_id
 AND finished_calls.initial_tool_call_id = roots.tool_call_id
 AND finished_calls.finish_order = 1
LEFT JOIN latest_calls
  ON latest_calls.provider = roots.provider
 AND latest_calls.user_id IS NOT DISTINCT FROM roots.user_id
 AND latest_calls.session_id = roots.session_id
 AND latest_calls.initial_tool_call_id = roots.tool_call_id
 AND latest_calls.latest_order = 1
LEFT JOIN call_sums
  ON call_sums.provider = roots.provider
 AND call_sums.user_id IS NOT DISTINCT FROM roots.user_id
 AND call_sums.session_id = roots.session_id
 AND call_sums.initial_tool_call_id = roots.tool_call_id
"""


def command_chains(con: Any):
    """Return a DuckDB result containing one derived row per Codex ``exec_command``.

    ``wall_time_until_finished_ms`` spans the initial call's emission through the first call in the
    chain that reports ``finished``. For a continued command that is the first terminal
    ``write_stdin`` result. ``tool_call_time_sum_ms`` instead sums the effective latency of the
    initial call and all linked continuations; the two metrics are intentionally not equated.
    Aborted/failed chains retain that final status but have no observed-finish timestamp.
    """
    return con.execute(COMMAND_CHAINS_SQL)
