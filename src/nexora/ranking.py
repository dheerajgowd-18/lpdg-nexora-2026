"""Ranking and selection module for NEXORA 2026.

Implements:
1. Fleet universe alignment against the lifecycle-eligible assets.
2. Option B silent-gateway retention: eligible gateways with no recent telemetry
   are assigned score=0.0, flagged_hours=0, and worst_metric='no_telemetry'.
3. Deterministic ranking: score descending, gateway_id ascending.
4. Top-15 selection with rank assignments 1 to 15.
"""

from __future__ import annotations

import datetime as dt
from typing import Sequence
import pandas as pd

VISITS_PER_WEEK = 15


def rank_and_select(
    scored_df: pd.DataFrame,
    eligible_ids: Sequence[str],
    top_k: int = VISITS_PER_WEEK,
) -> pd.DataFrame:
    """Aligns scored gateways with the eligible fleet, retains silent gateways under Option B,
    ranks deterministically, and selects the top-K recommendations.

    Parameters:
        scored_df: DataFrame containing ['gateway_id', 'score', 'flagged_hours', 'worst_metric'].
        eligible_ids: Sequence of canonical gateway IDs eligible for this week.
        top_k: Number of recommendations to select (default 15).

    Returns:
        DataFrame containing exactly top_k rows with columns:
        ['rank', 'gateway_id', 'score', 'flagged_hours', 'worst_metric'].

    Raises:
        ValueError: If total eligible fleet has fewer than top_k assets.
    """
    eligible_set = set(eligible_ids)
    if len(eligible_set) < top_k:
        raise ValueError(
            f"Fewer than {top_k} eligible gateways exist: {len(eligible_set)} found."
        )

    # Filter scored_df to only eligible gateways
    if not scored_df.empty:
        valid_scores = scored_df[scored_df["gateway_id"].isin(eligible_set)].copy()
    else:
        valid_scores = pd.DataFrame(columns=["gateway_id", "score", "flagged_hours", "worst_metric"])

    # Identify silent active gateways (eligible assets with no recent telemetry score)
    scored_ids = set(valid_scores["gateway_id"])
    silent_ids = sorted(eligible_set - scored_ids)

    # Option B: Retain silent gateways with score=0.0, flagged_hours=0, worst_metric='no_telemetry'
    if silent_ids:
        silent_df = pd.DataFrame({
            "gateway_id": silent_ids,
            "score": 0.0,
            "flagged_hours": 0,
            "worst_metric": "no_telemetry",
        })
        if not valid_scores.empty:
            complete_universe = pd.concat([valid_scores, silent_df], ignore_index=True)
        else:
            complete_universe = silent_df
    else:
        complete_universe = valid_scores

    # Invariant assertion: every eligible gateway is accounted for
    assert len(complete_universe) == len(eligible_set), (
        f"Universe size mismatch: {len(complete_universe)} vs {len(eligible_set)}"
    )

    # Deterministic sorting: score descending, gateway_id ascending
    ranked = complete_universe.sort_values(
        by=["score", "gateway_id"],
        ascending=[False, True],
    ).reset_index(drop=True)

    # Select Top-K
    top_df = ranked.head(top_k).copy()
    top_df["rank"] = range(1, len(top_df) + 1)

    return top_df[["rank", "gateway_id", "score", "flagged_hours", "worst_metric"]]
