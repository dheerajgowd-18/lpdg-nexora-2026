"""NEXORA 2026 Production Package.

Baseline_3Sigma Operational Ranking Pipeline for Utility IoT Gateways.
"""

from .data_loader import DataLoader, normalize_gateway_id, is_valid_gateway_id
from .eligibility import get_eligible_gateways
from .scoring import score_week
from .ranking import rank_and_select, VISITS_PER_WEEK
from .reasons import generate_reason, add_reasons
from .validation import validate_predictions_df, run_official_validator

__all__ = [
    "DataLoader",
    "normalize_gateway_id",
    "is_valid_gateway_id",
    "get_eligible_gateways",
    "score_week",
    "rank_and_select",
    "VISITS_PER_WEEK",
    "generate_reason",
    "add_reasons",
    "validate_predictions_df",
    "run_official_validator",
]
