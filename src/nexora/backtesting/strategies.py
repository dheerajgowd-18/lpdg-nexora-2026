"""
Deterministic candidate ranking strategies for NEXORA 2026 backtesting.
Implements 3-sigma baseline (control) and Candidates A through F.
Strictly deterministic, no random behavior, no machine learning, no parameter optimization.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Protocol
import numpy as np
import pandas as pd

from ..data_loader import DataLoader, normalize_gateway_id


def pct_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    """Computes percentile ranks in [0, 1] within a series.
    Ties receive the average rank.
    """
    if len(series) <= 1:
        return pd.Series(0.5, index=series.index)
    return series.rank(ascending=ascending, pct=True, method="average")


class CandidateStrategy(Protocol):
    """Protocol for a ranking strategy."""

    name: str

    def rank(self, feature_df: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
        """Ranks active gateways for decision Monday T.
        
        Args:
            feature_df: DataFrame containing the active gateway universe and extracted features.
            monday: Decision Monday.
            
        Returns:
            DataFrame with columns: gateway_id, rank, score, strategy_name
        """
        ...


class Baseline3SigmaStrategy:
    """Wraps baseline_3sigma.py as a candidate strategy with deterministic tie-breaking."""

    name = "Baseline_3Sigma"

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self._frame: pd.DataFrame | None = None

    def _load_frame(self) -> pd.DataFrame:
        if self._frame is not None:
            return self._frame

        import baseline_3sigma
        self._frame = baseline_3sigma.load(self.data_dir)
        return self._frame

    def rank(self, feature_df: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
        """Ranks active gateways for decision Monday T using the 3-sigma anomaly baseline.

        Baseline Fairness Invariants:
        1. Temporal Contract: baseline_3sigma.rank_week() strictly evaluates telemetry where
           ts >= T - 28d and ts < T (strictly before Monday T, zero future telemetry).
        2. Universe Parity: The ranked universe is aligned strictly to the active gateway universe
           at T defined by feature_df. Any active gateway with zero telemetry is retained with
           0 flagged hours rather than excluded.
        """
        import baseline_3sigma

        frame = self._load_frame()
        # Verify temporal isolation: rank_week uses frame[ts < end]
        ranked = baseline_3sigma.rank_week(frame, monday)
        
        # Canonicalize gateway IDs
        ranked["gateway_id"] = ranked["gateway_id"].apply(normalize_gateway_id)

        # Universe Parity: Align strictly to active universe from feature_df
        active_ids = set(feature_df["gateway_id"])
        ranked = ranked[ranked["gateway_id"].isin(active_ids)].copy()

        # If any active gateway had zero telemetry, add it with 0 flagged hours (silent gateway retention)
        missing_ids = active_ids - set(ranked["gateway_id"])
        if missing_ids:
            missing_df = pd.DataFrame({
                "gateway_id": sorted(missing_ids),
                "flagged_hours": 0,
                "worst_metric": "no_telemetry",
            })
            ranked = pd.concat([ranked, missing_df], ignore_index=True)

        # Invariant check: Verify exact universe match
        if len(ranked) != len(feature_df):
            raise ValueError(
                f"Baseline universe mismatch on {monday}: {len(ranked)} vs {len(feature_df)}"
            )
        if set(ranked["gateway_id"]) != active_ids:
            raise ValueError(
                f"Baseline gateway ID mismatch on {monday}"
            )

        # Deterministic sorting: flagged_hours descending, gateway_id ascending
        ranked = ranked.sort_values(
            by=["flagged_hours", "gateway_id"], ascending=[False, True]
        ).reset_index(drop=True)

        ranked["rank"] = np.arange(1, len(ranked) + 1)
        ranked["score"] = ranked["flagged_hours"].astype(float)
        ranked["strategy_name"] = self.name
        return ranked[["gateway_id", "rank", "score", "strategy_name"]]


class CandidateAStrategy:
    """Candidate A — Persistence/Core (F02, F09, F16)."""

    name = "Candidate_A_Core"

    def rank(self, feature_df: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
        df = feature_df.copy()

        # Directionality: all 3 are distress features (larger = more concern)
        p_f02 = pct_rank(df["F02"], ascending=True)
        p_f09 = pct_rank(df["F09"], ascending=True)
        p_f16 = pct_rank(df["F16"], ascending=True)

        df["score"] = (p_f02 + p_f09 + p_f16) / 3.0
        df = df.sort_values(by=["score", "gateway_id"], ascending=[False, True]).reset_index(drop=True)
        df["rank"] = np.arange(1, len(df) + 1)
        df["strategy_name"] = self.name
        return df[["gateway_id", "rank", "score", "strategy_name"]]


class CandidateBStrategy:
    """Candidate B — Persistence + Severity (F02, F09, F16, log1p(F06), log1p(F12))."""

    name = "Candidate_B_Severity"

    def rank(self, feature_df: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
        df = feature_df.copy()

        p_f02 = pct_rank(df["F02"], ascending=True)
        p_f09 = pct_rank(df["F09"], ascending=True)
        p_f16 = pct_rank(df["F16"], ascending=True)
        p_f06 = pct_rank(np.log1p(df["F06"]), ascending=True)
        p_f12 = pct_rank(np.log1p(df["F12"]), ascending=True)

        df["score"] = (p_f02 + p_f09 + p_f16 + p_f06 + p_f12) / 5.0
        df = df.sort_values(by=["score", "gateway_id"], ascending=[False, True]).reset_index(drop=True)
        df["rank"] = np.arange(1, len(df) + 1)
        df["strategy_name"] = self.name
        return df[["gateway_id", "rank", "score", "strategy_name"]]


class CandidateCStrategy:
    """Candidate C — Persistence + Severe Offline (F02, F09, F16, F08)."""

    name = "Candidate_C_SevereOffline"

    def rank(self, feature_df: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
        df = feature_df.copy()

        p_f02 = pct_rank(df["F02"], ascending=True)
        p_f09 = pct_rank(df["F09"], ascending=True)
        p_f16 = pct_rank(df["F16"], ascending=True)
        p_f08 = pct_rank(df["F08"], ascending=True)

        df["score"] = (p_f02 + p_f09 + p_f16 + p_f08) / 4.0
        df = df.sort_values(by=["score", "gateway_id"], ascending=[False, True]).reset_index(drop=True)
        df["rank"] = np.arange(1, len(df) + 1)
        df["strategy_name"] = self.name
        return df[["gateway_id", "rank", "score", "strategy_name"]]


class CandidateDStrategy:
    """Candidate D — Persistence + Long-Term Behavior (F02, F09, F16, F10)."""

    name = "Candidate_D_LongTerm"

    def rank(self, feature_df: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
        df = feature_df.copy()

        p_f02 = pct_rank(df["F02"], ascending=True)
        p_f09 = pct_rank(df["F09"], ascending=True)
        p_f16 = pct_rank(df["F16"], ascending=True)
        p_f10 = pct_rank(df["F10"], ascending=True)

        df["score"] = (p_f02 + p_f09 + p_f16 + p_f10) / 4.0
        df = df.sort_values(by=["score", "gateway_id"], ascending=[False, True]).reset_index(drop=True)
        df["rank"] = np.arange(1, len(df) + 1)
        df["strategy_name"] = self.name
        return df[["gateway_id", "rank", "score", "strategy_name"]]


class CandidateEStrategy:
    """Candidate E — Persistence + Historical Reliability (F02, F09, F16, 1.0 - F17)."""

    name = "Candidate_E_Reliability"

    def rank(self, feature_df: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
        df = feature_df.copy()

        p_f02 = pct_rank(df["F02"], ascending=True)
        p_f09 = pct_rank(df["F09"], ascending=True)
        p_f16 = pct_rank(df["F16"], ascending=True)
        # F17 is healthy (high read rate = good). Distress = (1.0 - F17)
        distress_f17 = 1.0 - df["F17"]
        p_f17 = pct_rank(distress_f17, ascending=True)

        df["score"] = (p_f02 + p_f09 + p_f16 + p_f17) / 4.0
        df = df.sort_values(by=["score", "gateway_id"], ascending=[False, True]).reset_index(drop=True)
        df["rank"] = np.arange(1, len(df) + 1)
        df["strategy_name"] = self.name
        return df[["gateway_id", "rank", "score", "strategy_name"]]


class CandidateFStrategy:
    """Candidate F — Conditional Silence (Candidate B with explicit F05 override priority tier).
    
    Gateways completely silent in 7d (F05 == 1) are placed in the top priority tier,
    ordered by Candidate B score. Remaining gateways are ordered by Candidate B score.
    """

    name = "Candidate_F_SilenceOverride"

    def rank(self, feature_df: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
        df = feature_df.copy()

        p_f02 = pct_rank(df["F02"], ascending=True)
        p_f09 = pct_rank(df["F09"], ascending=True)
        p_f16 = pct_rank(df["F16"], ascending=True)
        p_f06 = pct_rank(np.log1p(df["F06"]), ascending=True)
        p_f12 = pct_rank(np.log1p(df["F12"]), ascending=True)

        base_score = (p_f02 + p_f09 + p_f16 + p_f06 + p_f12) / 5.0
        # F05 override tier: add 10.0 if completely silent
        df["is_silent"] = (df["F05"] == 1).astype(int)
        df["score"] = df["is_silent"] * 10.0 + base_score

        df = df.sort_values(by=["score", "gateway_id"], ascending=[False, True]).reset_index(drop=True)
        df["rank"] = np.arange(1, len(df) + 1)
        df["strategy_name"] = self.name
        return df[["gateway_id", "rank", "score", "strategy_name"]]


ALL_STRATEGIES = [
    Baseline3SigmaStrategy(),
    CandidateAStrategy(),
    CandidateBStrategy(),
    CandidateCStrategy(),
    CandidateDStrategy(),
    CandidateEStrategy(),
    CandidateFStrategy(),
]
