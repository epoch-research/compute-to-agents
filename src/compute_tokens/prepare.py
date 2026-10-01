#!/usr/bin/env python3
"""Prepare the latest InferenceX AgentX rows and derive physical-GPU counts."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "y"}


def open_text(path: Path, mode: str):
    if path.suffix == ".gz":
        return gzip.open(path, mode, encoding="utf-8", newline="")
    return path.open(mode, encoding="utf-8", newline="")


def is_true(value: object) -> bool:
    return str(value).strip().lower() in TRUE_VALUES


def number(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value in (None, ""):
        raise ValueError(f"Missing required numeric field {key!r} in result {row.get('id')}")
    return float(value)


def integerish(value: float, *, tolerance: float = 1e-5) -> int:
    rounded = int(round(value))
    if not math.isclose(value, rounded, rel_tol=tolerance, abs_tol=tolerance):
        raise ValueError(f"Expected an integer-like GPU count, got {value}")
    return rounded


def derive_gpu_count(
    row: dict[str, str], on_unknown_mismatch: str
) -> tuple[int, int, float, bool, str]:
    """Return actual, reported, throughput-implied, corrected, basis."""
    disaggregated = is_true(row.get("disagg", ""))
    prefill = int(float(row.get("num_prefill_gpu") or 0))
    decode = int(float(row.get("num_decode_gpu") or 0))
    if prefill <= 0 and decode <= 0:
        raise ValueError(f"No positive GPU count in result {row.get('id')}")

    reported = prefill + decode if disaggregated else max(prefill, decode)
    implied = number(row, "metrics.total_tput_tps") / number(row, "metrics.tput_per_gpu")
    if math.isclose(reported, implied, rel_tol=1e-5, abs_tol=1e-5):
        basis = (
            "prefill_plus_decode_for_disaggregated"
            if disaggregated
            else "shared_aggregate_chips_counted_once"
        )
        return reported, reported, implied, False, basis

    # The 2026-09-10 snapshot has 105 aggregate rows whose role counts equal
    # TP×EP even though the per-GPU throughput denominator uses TP×PP×PCP.
    # Correct only when the parallelism-derived candidate independently agrees
    # with the throughput normalization.
    candidate = None
    if not disaggregated:
        try:
            candidate_float = (
                number(row, "decode_tp")
                * number(row, "metrics.pp")
                * number(row, "metrics.pcp_size")
            )
            if math.isclose(candidate_float, implied, rel_tol=1e-5, abs_tol=1e-5):
                candidate = integerish(candidate_float)
        except (ValueError, TypeError):
            candidate = None

    if candidate is not None:
        return (
            candidate,
            reported,
            implied,
            True,
            "TP_x_PP_x_PCP_corrects_role_count;validated_against_throughput",
        )

    message = (
        f"Unknown GPU-count mismatch in result {row.get('id')}: "
        f"reported={reported}, throughput_implied={implied:.8g}, "
        f"disaggregated={disaggregated}."
    )
    if on_unknown_mismatch == "error":
        raise ValueError(message + " Inspect the new InferenceX schema before continuing.")
    if on_unknown_mismatch == "use-implied":
        actual = integerish(implied)
        return actual, reported, implied, True, "throughput_implied_user_override"
    return reported, reported, implied, False, "reported_count_user_override"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="InferenceX CSV or CSV.GZ")
    parser.add_argument("--output", required=True, type=Path, help="Prepared CSV path")
    parser.add_argument(
        "--snapshot-date",
        required=True,
        help="Date label for provenance, normally the retrieval date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--on-unknown-mismatch",
        choices=["error", "use-implied", "keep-reported"],
        default="error",
        help="How to handle a new GPU-count inconsistency; error is safest",
    )
    args = parser.parse_args()

    with open_text(args.input, "rt") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Input has no CSV header")
        original_columns = list(reader.fieldnames)
        rows = []
        for row in reader:
            if row.get("benchmark_type") != "agentic_traces":
                continue
            latest = row.get("export.in_latest_snapshot")
            if latest not in (None, "") and not is_true(latest):
                continue
            rows.append(row)

    if not rows:
        raise ValueError("No latest agentic_traces rows found")

    seen_ids: set[str] = set()
    prepared: list[dict[str, object]] = []
    corrected = 0
    for row in rows:
        result_id = str(row.get("id", ""))
        if not result_id:
            raise ValueError("A benchmark row is missing id")
        if result_id in seen_ids:
            continue
        seen_ids.add(result_id)

        actual, reported, implied, was_corrected, basis = derive_gpu_count(
            row, args.on_unknown_mismatch
        )
        corrected += int(was_corrected)
        conc = number(row, "conc")
        row.update(
            total_gpus=actual,
            concurrency_per_gpu=conc / actual,
            total_token_throughput_per_chip=number(row, "metrics.tput_per_gpu"),
            output_token_throughput_per_chip=number(row, "metrics.output_tput_per_gpu"),
            input_token_throughput_per_chip=number(row, "metrics.input_tput_per_gpu"),
            total_gpus_reported=reported,
            concurrency_per_reported_gpu=conc / reported,
            gpu_count_corrected="true" if was_corrected else "false",
            gpu_count_basis=basis,
            gpu_count_implied_by_throughput=implied,
            snapshot_date=args.snapshot_date,
        )
        prepared.append(row)

    derived_columns = [
        "total_gpus",
        "concurrency_per_gpu",
        "total_token_throughput_per_chip",
        "output_token_throughput_per_chip",
        "input_token_throughput_per_chip",
        "total_gpus_reported",
        "concurrency_per_reported_gpu",
        "gpu_count_corrected",
        "gpu_count_basis",
        "gpu_count_implied_by_throughput",
        "snapshot_date",
    ]
    lead = [
        "id",
        "model",
        "export.display_model",
        "hardware",
        "framework",
        "precision",
        "spec_method",
        "disagg",
        "conc",
    ]
    columns = lead + derived_columns + [
        col for col in original_columns if col not in lead and col not in derived_columns
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open_text(args.output, "wt") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(prepared)

    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "snapshot_date": args.snapshot_date,
        "latest_agentic_rows": len(prepared),
        "models": sorted({str(row["model"]) for row in prepared}),
        "corrected_gpu_counts": corrected,
        "unknown_mismatch_policy": args.on_unknown_mismatch,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
