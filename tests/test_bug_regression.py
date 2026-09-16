"""Bug regression and challenge requirement tests for NEXORA 2026.

This module fulfills the explicit requirement from Challenge Brief Part 2 (Area B):
"Include one test you wrote because you found a bug."

It includes tests written specifically in response to real bugs discovered during
development, alongside regression safeguards for key challenge capabilities.
"""

import datetime as dt
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nexora.api import create_app
from nexora.config import SCORED_WEEKS, VISITS_PER_WEEK
from nexora.ranking import rank_and_select
from nexora.reasons import add_reasons


# =============================================================================
# BUG 1: Silent Masking of Upstream Duplicate Scored Records
# =============================================================================

def test_bug_regression_duplicate_scored_records_raises_valueerror():
    """BUG REGRESSION TEST: Upstream duplicate records must raise ValueError, not be silently masked.

    Discovered during Phase 12 hardening:
    An AI assistant initially implemented silent deduplication via:
        scored_df.drop_duplicates(subset=['gateway_id'], keep='first')
    This was dangerous because duplicate scored records for the same gateway indicate
    an upstream pipeline or telemetry partition corruption. Silently picking one masks
    the corruption and produces unpredictable rankings.

    The fix: rank_and_select() must fail-fast with an explicit ValueError.
    """
    eligible_gateways = ["001A7D000001", "001A7D000002", "001A7D000003"]
    corrupted_scores = pd.DataFrame({
        "gateway_id": ["001A7D000001", "001A7D000001", "001A7D000002"],  # Duplicate G01
        "score": [25.0, 10.0, 5.0],
        "flagged_hours": [25, 10, 5],
        "worst_metric": ["offline_duration_sec", "offline_duration_sec", "reboot_cnt"],
    })

    with pytest.raises(ValueError, match="Duplicate scored records detected"):
        rank_and_select(corrupted_scores, eligible_gateways, top_k=2)


# =============================================================================
# BUG 2: FastAPI App Lifespan AttributeError on Data Directory State
# =============================================================================

def test_bug_regression_api_state_data_dir_initialization(tmp_path):
    """BUG REGRESSION TEST: app.state.data_dir must be set before lifespan executes.

    Discovered during API testing:
    When lifespan was refactored to delegate to _reload_data(app), _reload_data
    attempted to read app.state.data_dir. However, app.state.data_dir was not yet
    assigned on the FastAPI instance before startup, causing an AttributeError:
        AttributeError: 'State' object has no attribute 'data_dir'

    The fix: create_app() explicitly assigns app.state.data_dir = effective_data_dir
    prior to any lifespan context execution.
    """
    # Create minimal valid data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "installed_on": "2025-01-01",
        "decommissioned_on": None,
        "region": "Nord",
    }]).to_csv(data_dir / "gateway_master.csv", index=False)

    t_dir = data_dir / "telemetry" / "month=2026-02"
    t_dir.mkdir(parents=True)
    pd.DataFrame(columns=[
        "gateway_id", "ts_utc", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"
    ]).to_parquet(t_dir / "part-0.parquet")

    # Creating the app and entering TestClient must succeed without AttributeError
    app_instance = create_app(data_dir=data_dir)
    assert hasattr(app_instance.state, "data_dir")

    with TestClient(app_instance) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# =============================================================================
# BUG 3: Observational Reason Length Invariant (<= 300 characters)
# =============================================================================

def test_bug_regression_reason_string_length_within_limit():
    """BUG REGRESSION TEST: All generated reasons must strictly adhere to <= 300 chars.

    The official submission validator (validate_submission.py) rejects any submission
    where even a single reason string exceeds MAX_REASON_CHARS (300).

    This test verifies that under extreme inputs (huge breach counts, multiple metrics,
    and silent retention) reasons remain well below the 300 character ceiling.
    """
    test_df = pd.DataFrame([
        {
            "gateway_id": "001A7D000001",
            "score": 999999.0,
            "flagged_hours": 999999,
            "worst_metric": "offline_duration_sec",
        },
        {
            "gateway_id": "001A7D000002",
            "score": 0.0,
            "flagged_hours": 0,
            "worst_metric": "no_telemetry",
        },
        {
            "gateway_id": "001A7D000003",
            "score": 1.0,
            "flagged_hours": 1,
            "worst_metric": "",
        },
    ])

    result_df = add_reasons(test_df)
    for reason in result_df["reason"]:
        assert len(reason) <= 300, f"Reason exceeded 300 chars: {reason!r}"
        assert len(reason.strip()) > 0, "Reason must not be blank"


# =============================================================================
# BUG 4: SyntheticFakeStrategy Non-Unique Gateway IDs via Slicing Truncation
# =============================================================================

def test_bug_regression_synthetic_strategy_generates_strictly_unique_ids():
    """BUG REGRESSION TEST: Synthetic strategy must generate strictly unique gateway IDs.

    Discovered during Task 1 (Strategy Abstraction):
    A test mock strategy attempted to create 12-character hex gateway IDs using:
        f"0080E1FFFFFF{i:02X}"[:12]
    Because the prefix '0080E1FFFFFF' was already 12 characters long, slicing [:12]
    truncated the variable index suffix '{i:02X}', causing all 15 synthetic rows
    to receive the identical gateway ID '0080E1FFFFFF'.

    When plugged into the API, this triggered downstream validation errors
    ("duplicate gateway IDs detected").

    The fix:
    Format IDs using f"0080E1{i:06X}" ensuring 12 characters with unique suffixes,
    and assert strictly unique gateway IDs.
    """
    try:
        from test_strategy_abstraction import SyntheticFakeStrategy
    except ImportError:
        from tests.test_strategy_abstraction import SyntheticFakeStrategy

    strategy = SyntheticFakeStrategy()
    mock_master = pd.DataFrame([
        {"gateway_id": f"0080E1{i:06X}", "installed_on": "2025-01-01", "decommissioned_on": None, "region": "North"}
        for i in range(1, 25)
    ])
    mock_telem = pd.DataFrame(columns=["gateway_id", "ts_utc", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"])

    preds = strategy.predict(mock_master, mock_telem, dt.date(2026, 2, 2), top_k=15)

    assert len(preds) == 15
    assert len(set(preds["gateway_id"])) == 15, "Synthetic strategy must produce exactly 15 distinct gateway IDs"
    assert list(preds["rank"]) == list(range(1, 16)), "Ranks must be contiguous 1..15"
    for gid in preds["gateway_id"]:
        assert len(gid) == 12, f"Gateway ID '{gid}' must be exactly 12 characters"


# =============================================================================
# CHALLENGE FEATURE: Web API Requirements
# =============================================================================

def test_api_ask_for_this_weeks_15(tmp_path):
    """Challenge Brief Requirement: 'ask it for this week's 15'.

    GET /predictions with no parameters must return recommendations for the
    latest competition Monday (SCORED_WEEKS[-1]).
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    master_rows = [{"gateway_id": f"001A7D0000{i:02X}", "installed_on": "2025-01-01", "decommissioned_on": None} for i in range(1, 20)]
    pd.DataFrame(master_rows).to_csv(data_dir / "gateway_master.csv", index=False)

    t_dir = data_dir / "telemetry" / "month=2026-03"
    t_dir.mkdir(parents=True)
    pd.DataFrame(columns=["gateway_id", "ts_utc", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"]).to_parquet(t_dir / "part-0.parquet")

    app_instance = create_app(data_dir=data_dir)
    with TestClient(app_instance) as client:
        resp = client.get("/predictions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["week_start"] == SCORED_WEEKS[-1].isoformat()
        assert data["count"] == VISITS_PER_WEEK
        assert len(data["predictions"]) == VISITS_PER_WEEK


def test_api_ask_why_a_particular_gateway_is_where_it_is(tmp_path):
    """Challenge Brief Requirement: 'ask it why a particular gateway is where it is'.

    GET /gateways/{gateway_id}/explanation returns rank, score, and observational reason.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    master_rows = [{"gateway_id": f"001A7D0000{i:02X}", "installed_on": "2025-01-01", "decommissioned_on": None} for i in range(1, 20)]
    pd.DataFrame(master_rows).to_csv(data_dir / "gateway_master.csv", index=False)

    t_dir = data_dir / "telemetry" / "month=2026-03"
    t_dir.mkdir(parents=True)
    pd.DataFrame(columns=["gateway_id", "ts_utc", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"]).to_parquet(t_dir / "part-0.parquet")

    app_instance = create_app(data_dir=data_dir)
    with TestClient(app_instance) as client:
        # Query known gateway
        resp = client.get("/gateways/001A7D000001/explanation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gateway_id"] == "001A7D000001"
        assert "selected" in data
        assert "reason" in data
        assert isinstance(data["reason"], str)

        # Query unknown gateway
        resp404 = client.get("/gateways/FFFFFFFFFFFF/explanation")
        assert resp404.status_code == 404
