#!/usr/bin/env python3
"""Rebuild the six numbered figures in the Compute to agents report."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D


@dataclass(frozen=True)
class CutoffEstimate:
    estimate: float | None
    measured: float | None
    method: str
    left_x: float | None
    left_y: float | None
    right_x: float | None
    right_y: float | None


def truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["1", "true", "yes", "y"])


def pareto_frontier(group: pd.DataFrame, x_col: str) -> pd.DataFrame:
    """Keep points not dominated on both interactivity and concurrency.

    At duplicate x-values, the highest-concurrency row dominates. We then scan
    from high to low interactivity and retain a point only when it sets a new
    high in concurrency. The returned rows are ordered by increasing x.
    """
    columns = [x_col, "concurrency_per_gpu", "id"]
    work = group.dropna(subset=[x_col, "concurrency_per_gpu"])[columns].copy()
    work = work[(work[x_col] > 0) & (work["concurrency_per_gpu"] > 0)]
    work = work.sort_values(
        [x_col, "concurrency_per_gpu", "id"], ascending=[False, False, True]
    ).drop_duplicates(x_col, keep="first")
    retained = []
    best_y = -math.inf
    for row in work.itertuples(index=False):
        y = float(row.concurrency_per_gpu)
        if y > best_y:
            retained.append(row)
            best_y = y
    return pd.DataFrame(retained, columns=columns).sort_values(x_col)


def estimate_at_cutoff(
    group: pd.DataFrame, frontier: pd.DataFrame, x_col: str, cutoff: float
) -> CutoffEstimate:
    raw_at_or_above = group[group[x_col] >= cutoff]
    measured = (
        float(raw_at_or_above["concurrency_per_gpu"].max())
        if not raw_at_or_above.empty
        else None
    )
    if frontier.empty or float(frontier[x_col].max()) < cutoff:
        return CutoffEstimate(None, measured, "not_reached", None, None, None, None)

    left = frontier[frontier[x_col] <= cutoff]
    right = frontier[frontier[x_col] >= cutoff]
    if left.empty:
        estimate = float(frontier["concurrency_per_gpu"].max())
        first = frontier.loc[frontier[x_col].idxmin()]
        return CutoffEstimate(
            estimate,
            measured,
            "maximum_measured_frontier_starts_above_cutoff",
            None,
            None,
            float(first[x_col]),
            float(first["concurrency_per_gpu"]),
        )

    left_row = left.loc[left[x_col].idxmax()]
    right_row = right.loc[right[x_col].idxmin()]
    lx, ly = float(left_row[x_col]), float(left_row["concurrency_per_gpu"])
    rx, ry = float(right_row[x_col]), float(right_row["concurrency_per_gpu"])
    if math.isclose(lx, rx):
        estimate = ly
        method = "exact_frontier_point"
    else:
        estimate = ly + (ry - ly) * (cutoff - lx) / (rx - lx)
        method = "linear_interpolation_frontier_original_units"
    return CutoffEstimate(estimate, measured, method, lx, ly, rx, ry)
