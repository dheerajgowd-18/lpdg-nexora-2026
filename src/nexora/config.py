"""Central configuration constants for the NEXORA 2026 production pipeline.

Authoritative parameter definitions for:
- Challenge evaluation calendar (scored Mondays)
- Temporal baseline and recent evaluation windows
- Recommendation fleet capacity (Top-15)
- Approved telemetry monitoring metrics (Baseline_3Sigma)
- Observational reason formatting and length limits
- Required ingestion and output schema specifications
"""

from __future__ import annotations

import datetime as dt
from typing import Final

# =============================================================================
# 1. Scored Evaluation Calendar
# =============================================================================
FIRST_SCORED_MONDAY: Final[dt.date] = dt.date(2026, 2, 2)
NUM_SCORED_WEEKS: Final[int] = 8
SCORED_WEEKS: Final[list[dt.date]] = [
    FIRST_SCORED_MONDAY + dt.timedelta(days=7 * i) for i in range(NUM_SCORED_WEEKS)
]

# =============================================================================
# 2. Recommendation Fleet Capacity
# =============================================================================
VISITS_PER_WEEK: Final[int] = 15

# =============================================================================
# 3. Baseline_3Sigma Scoring Parameters
# =============================================================================
BASELINE_DAYS: Final[int] = 28
RECENT_DAYS: Final[int] = 7
SIGMA: Final[float] = 3.0

METRICS: Final[list[str]] = [
    "offline_duration_sec",
    "disconnection_cnt",
    "reboot_cnt",
]

# =============================================================================
# 4. Reason String Specifications
# =============================================================================
MAX_REASON_CHARS: Final[int] = 300
FROZEN_ZERO_SCORE_REASON: Final[str] = (
    "0 individual 3-sigma metric breaches against this gateway's own "
    "28-day baseline in the last 7 days"
)

# =============================================================================
# 5. Schema Contracts
# =============================================================================
REQUIRED_PREDICTION_COLUMNS: Final[list[str]] = [
    "week_start",
    "rank",
    "gateway_id",
    "score",
    "reason",
]

REQUIRED_MASTER_COLUMNS: Final[list[str]] = [
    "gateway_id",
    "installed_on",
]

REQUIRED_TELEMETRY_COLUMNS: Final[list[str]] = [
    "gateway_id",
    "ts_utc",
    "offline_duration_sec",
    "disconnection_cnt",
    "reboot_cnt",
]

REQUIRED_METER_COLUMNS: Final[list[str]] = [
    "gateway_id",
    "week_start",
    "meters_expected",
    "meters_read",
]
