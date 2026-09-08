"""
Backtesting package for NEXORA 2026.
Provides simulation, strategy definitions, metrics computation, and leakage tests.
"""

from .strategies import (
    CandidateStrategy,
    Baseline3SigmaStrategy,
    CandidateAStrategy,
    CandidateBStrategy,
    CandidateCStrategy,
    CandidateDStrategy,
    CandidateEStrategy,
    CandidateFStrategy,
    ALL_STRATEGIES,
)
from .metrics import (
    compute_weekly_metrics,
    compute_top_k_curve,
    compute_strategy_summary,
)
from .leakage import (
    run_all_leakage_tests,
    run_synthetic_telemetry_leakage_test,
    run_future_engineer_review_leakage_test,
    run_meter_temporal_boundary_test,
    run_determinism_test,
)
from .backtester import HistoricalBacktester

__all__ = [
    "HistoricalBacktester",
    "CandidateStrategy",
    "Baseline3SigmaStrategy",
    "CandidateAStrategy",
    "CandidateBStrategy",
    "CandidateCStrategy",
    "CandidateDStrategy",
    "CandidateEStrategy",
    "CandidateFStrategy",
    "ALL_STRATEGIES",
    "compute_weekly_metrics",
    "compute_top_k_curve",
    "compute_strategy_summary",
    "run_all_leakage_tests",
    "run_synthetic_telemetry_leakage_test",
    "run_future_engineer_review_leakage_test",
    "run_meter_temporal_boundary_test",
    "run_determinism_test",
]
