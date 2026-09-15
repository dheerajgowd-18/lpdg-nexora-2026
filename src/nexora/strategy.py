"""Prediction strategy abstraction and service for NEXORA 2026.

Provides a clean, swappable interface for Area B (Software Development):
"Someone should be able to swap out how the ranking works without touching the API."

Architecture:
    API / CLI Pipeline
           |
    PredictionService
           |
    PredictionStrategy (Protocol)
           |
    Baseline3SigmaStrategy (Production Default)
           |
    Authoritative scoring/ranking core (scoring.py, ranking.py, etc.)
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol, runtime_checkable
import pandas as pd

from .config import REQUIRED_PREDICTION_COLUMNS, VISITS_PER_WEEK
from .eligibility import get_eligible_gateways
from .ranking import rank_and_select
from .reasons import add_reasons
from .scoring import score_week


@runtime_checkable
class PredictionStrategy(Protocol):
    """Protocol defining the interface for gateway ranking/prediction strategies."""

    @property
    def name(self) -> str:
        """Human-readable identifier of the strategy."""
        ...

    def predict(
        self,
        master_df: pd.DataFrame,
        telemetry_df: pd.DataFrame,
        decision_monday: dt.date | dt.datetime | str,
        top_k: int = VISITS_PER_WEEK,
    ) -> pd.DataFrame:
        """Generates top-K recommendations for a decision Monday."""
        ...


class Baseline3SigmaStrategy:
    """Production ranking strategy implementing the frozen Baseline_3Sigma methodology.

    Delegates directly to authoritative core modules (eligibility, scoring, ranking, reasons)
    to guarantee exact behavioral identity with zero code duplication.
    """

    @property
    def name(self) -> str:
        return "Baseline_3Sigma"

    def predict(
        self,
        master_df: pd.DataFrame,
        telemetry_df: pd.DataFrame,
        decision_monday: dt.date | dt.datetime | str,
        top_k: int = VISITS_PER_WEEK,
    ) -> pd.DataFrame:
        """Executes the authoritative 3-sigma anomaly ranking algorithm."""
        if isinstance(decision_monday, str):
            t_date = dt.date.fromisoformat(decision_monday)
        elif isinstance(decision_monday, dt.datetime):
            t_date = decision_monday.date()
        elif isinstance(decision_monday, dt.date):
            t_date = decision_monday
        else:
            raise TypeError(f"Unsupported decision_monday type: {type(decision_monday)}")

        # 1. Lifecycle eligibility
        eligible_ids = get_eligible_gateways(master_df, t_date)

        # 2. Temporal cutoff & Baseline_3Sigma scoring
        scored_df = score_week(telemetry_df, t_date)

        # 3. Silent gateway alignment (Option B), deterministic ranking, Top-K selection
        top_df = rank_and_select(scored_df, eligible_ids, top_k=top_k)

        # 4. Reason generation
        top_df = add_reasons(top_df)

        # 5. Schema formatting
        top_df["week_start"] = t_date.isoformat()
        return top_df[REQUIRED_PREDICTION_COLUMNS].copy()


class PredictionService:
    """Service layer managing the active prediction strategy.

    Decouples the API and CLI callers from concrete strategy implementations.
    """

    def __init__(self, strategy: PredictionStrategy | None = None) -> None:
        self._strategy: PredictionStrategy = strategy or Baseline3SigmaStrategy()

    @property
    def strategy(self) -> PredictionStrategy:
        """The currently active prediction strategy."""
        return self._strategy

    @strategy.setter
    def strategy(self, new_strategy: PredictionStrategy) -> None:
        """Swaps the active prediction strategy."""
        if not isinstance(new_strategy, PredictionStrategy):
            raise TypeError(f"Strategy must implement PredictionStrategy protocol, got {type(new_strategy)}")
        self._strategy = new_strategy

    def predict(
        self,
        master_df: pd.DataFrame,
        telemetry_df: pd.DataFrame,
        decision_monday: dt.date | dt.datetime | str,
        top_k: int = VISITS_PER_WEEK,
    ) -> pd.DataFrame:
        """Delegates prediction execution to the active strategy."""
        return self._strategy.predict(
            master_df=master_df,
            telemetry_df=telemetry_df,
            decision_monday=decision_monday,
            top_k=top_k,
        )


default_prediction_service = PredictionService()
