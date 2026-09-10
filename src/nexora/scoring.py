"""Scoring module implementing Baseline_3Sigma for NEXORA 2026.

Strictly preserves the reference Baseline_3Sigma mathematical formulation:
- 28-day baseline window: [T-28d, T)
- 7-day recent evaluation window: [T-7d, T)
- Monitored metrics: offline_duration_sec, disconnection_cnt, reboot_cnt
- Sample standard deviation (ddof=1)
- Zero standard deviation replaced with NaN (no breach)
- Single observation standard deviation is NaN (no breach)
- Breach condition: x > mean + 3 * std
- Individual metric breach accumulation: 0, 1, 2, or 3 per telemetry hour
"""

from __future__ import annotations

import datetime as dt
from typing import Sequence
import numpy as np
import pandas as pd

from .config import BASELINE_DAYS, RECENT_DAYS, SIGMA, METRICS


def score_week(
    telemetry_df: pd.DataFrame,
    decision_monday: dt.date | dt.datetime | str,
) -> pd.DataFrame:
    """Computes Baseline_3Sigma scores for all gateways with recent telemetry.

    Parameters:
        telemetry_df: Telemetry dataframe with columns ['gateway_id', 'ts', *METRICS].
                      Timestamps must be UTC timezone-aware.
        decision_monday: The decision Monday cutoff T.

    Returns:
        DataFrame with columns ['gateway_id', 'score', 'flagged_hours', 'worst_metric'],
        where score equals flagged_hours (total count of 3-sigma individual metric breaches).
    """
    if isinstance(decision_monday, str):
        t_date = dt.date.fromisoformat(decision_monday)
    elif isinstance(decision_monday, dt.datetime):
        t_date = decision_monday.date()
    elif isinstance(decision_monday, dt.date):
        t_date = decision_monday
    else:
        raise TypeError(f"Unsupported decision_monday type: {type(decision_monday)}")

    required_cols = ["gateway_id", "ts", *METRICS]
    missing = [c for c in required_cols if c not in telemetry_df.columns]
    if missing:
        raise ValueError(f"telemetry_df is missing required column(s): {missing}")

    if not telemetry_df.empty:
        ts_dtype = telemetry_df["ts"].dtype
        if not hasattr(ts_dtype, "tz") or ts_dtype.tz is None:
            raise ValueError("telemetry_df 'ts' column must be timezone-aware (UTC).")

    end = pd.Timestamp(t_date, tz="UTC")
    baseline_start = end - dt.timedelta(days=BASELINE_DAYS)
    recent_start = end - dt.timedelta(days=RECENT_DAYS)

    # Strict pre-T right-open window: [T - 28d, T)
    window = telemetry_df[(telemetry_df["ts"] >= baseline_start) & (telemetry_df["ts"] < end)]
    if window.empty:
        return pd.DataFrame(columns=["gateway_id", "score", "flagged_hours", "worst_metric"])

    # Baseline statistics: mean and sample standard deviation (ddof=1 by default in pandas)
    stats = window.groupby("gateway_id")[METRICS].agg(["mean", "std"])

    # Recent evaluation window: [T - 7d, T)
    recent = window[window["ts"] >= recent_start].copy()
    if recent.empty:
        return pd.DataFrame(columns=["gateway_id", "score", "flagged_hours", "worst_metric"])

    flags = pd.Series(0, index=recent.index, dtype=int)
    worst = pd.Series("", index=recent.index, dtype=object)

    for metric in METRICS:
        mean = recent["gateway_id"].map(stats[(metric, "mean")])
        std = recent["gateway_id"].map(stats[(metric, "std")]).replace(0, np.nan)
        exceeded = (recent[metric] - mean) > (SIGMA * std)
        exceeded = exceeded.fillna(False)
        flags = flags + exceeded.astype(int)
        worst = worst.where(~exceeded | (worst != ""), metric)

    recent["flagged"] = flags
    recent["worst_metric"] = worst

    grouped = recent.groupby("gateway_id").agg(
        flagged_hours=("flagged", "sum"),
        worst_metric=("worst_metric", lambda s: next((v for v in s if v), "")),
    ).reset_index()

    grouped["score"] = grouped["flagged_hours"].astype(float)
    return grouped[["gateway_id", "score", "flagged_hours", "worst_metric"]]
