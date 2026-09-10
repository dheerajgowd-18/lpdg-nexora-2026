"""NEXORA 2026 Production Package.

Baseline_3Sigma Operational Ranking Pipeline for Utility IoT Gateways.
"""

from .config import (
    BASELINE_DAYS,
    RECENT_DAYS,
    SIGMA,
    METRICS,
    VISITS_PER_WEEK,
    SCORED_WEEKS,
    MAX_REASON_CHARS,
    REQUIRED_PREDICTION_COLUMNS,
)
from .data_loader import DataLoader, normalize_gateway_id, is_valid_gateway_id
from .eligibility import get_eligible_gateways
from .scoring import score_week
from .ranking import rank_and_select
from .reasons import generate_reason, add_reasons
from .validation import validate_predictions_df, run_official_validator


def __getattr__(name: str):
    """Lazy loads pipeline functions to avoid runpy circular module warnings."""
    if name in ("predict_week", "run_pipeline"):
        from . import pipeline
        return getattr(pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DataLoader",
    "normalize_gateway_id",
    "is_valid_gateway_id",
    "get_eligible_gateways",
    "score_week",
    "rank_and_select",
    "generate_reason",
    "add_reasons",
    "validate_predictions_df",
    "run_official_validator",
    "predict_week",
    "run_pipeline",
    "VISITS_PER_WEEK",
    "SCORED_WEEKS",
    "METRICS",
    "BASELINE_DAYS",
    "RECENT_DAYS",
    "SIGMA",
    "MAX_REASON_CHARS",
    "REQUIRED_PREDICTION_COLUMNS",
]
