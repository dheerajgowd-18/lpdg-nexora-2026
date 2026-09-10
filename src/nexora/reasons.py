"""Reason string generation module for NEXORA 2026.

Generates factual, observational, non-causal reason strings conforming to
challenge length (<= 300 characters) and explainability requirements.
"""

from __future__ import annotations

import pandas as pd

from .config import MAX_REASON_CHARS, FROZEN_ZERO_SCORE_REASON


def generate_reason(score: float | int, flagged_hours: int, worst_metric: str) -> str:
    """Generates an observational reason string based on 3-sigma metric breach count.

    Avoids unsupported causal claims (e.g. blown fuse, hardware failure).
    """
    count = int(flagged_hours)
    if count > 0:
        metric_desc = worst_metric if worst_metric and worst_metric != "no_telemetry" else "metric breach"
        reason = (
            f"{count} individual 3-sigma metric breach(es) against this gateway's own "
            f"28-day baseline in the last 7 days; first breach on {metric_desc}"
        )
    else:
        reason = FROZEN_ZERO_SCORE_REASON

    if len(reason) > MAX_REASON_CHARS:
        reason = reason[:MAX_REASON_CHARS]
    return reason


def add_reasons(df: pd.DataFrame) -> pd.DataFrame:
    """Adds or updates the 'reason' column in the recommendation DataFrame."""
    res = df.copy()
    reasons = []
    for _, row in res.iterrows():
        reasons.append(
            generate_reason(
                score=row["score"],
                flagged_hours=row.get("flagged_hours", int(row["score"])),
                worst_metric=row.get("worst_metric", ""),
            )
        )
    res["reason"] = reasons
    return res
