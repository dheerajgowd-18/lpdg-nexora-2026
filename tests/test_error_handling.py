"""Comprehensive unit tests for error handling and edge cases across core modules.

Covers:
- DataLoader missing directories, missing files, missing columns, malformed IDs
- Telemetry timestamp validation (null timestamps, timezone awareness)
- Empty data handling (empty telemetry, empty recent window, all-silent fleet)
- Scoring input validation (missing columns, invalid date types, NaN metric handling)
- Ranking edge cases (top_k <= 0, insufficient fleet < 15, duplicate scored rows)
- Output validation rejection of malformed schemas, corrupt ranks, and invalid reasons
"""

import datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from nexora.config import METRICS, VISITS_PER_WEEK
from nexora.data_loader import DataLoader, normalize_gateway_id
from nexora.eligibility import get_eligible_gateways
from nexora.pipeline import predict_week, run_pipeline
from nexora.ranking import rank_and_select
from nexora.scoring import score_week
from nexora.validation import validate_predictions_df, run_official_validator


# =============================================================================
# 1. DataLoader Error Handling
# =============================================================================

def test_missing_data_directory_raises_filenotfound():
    """DataLoader raises FileNotFoundError when data directory does not exist."""
    with pytest.raises(FileNotFoundError, match="Data directory not found"):
        DataLoader(data_dir="non_existent_data_dir_xyz")


def test_missing_master_file_raises_filenotfound(tmp_path):
    """load_master raises FileNotFoundError when gateway_master.csv is absent."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    loader = DataLoader(data_dir=empty_dir)
    with pytest.raises(FileNotFoundError, match="gateway_master.csv not found"):
        loader.load_master()


def test_missing_telemetry_dir_raises_filenotfound(tmp_path):
    """load_telemetry raises FileNotFoundError when telemetry/ directory is absent."""
    d = tmp_path / "no_telem"
    d.mkdir()
    loader = DataLoader(data_dir=d)
    with pytest.raises(FileNotFoundError, match="telemetry directory not found"):
        loader.load_telemetry()


def test_missing_master_columns_raises_valueerror(tmp_path):
    """load_master raises ValueError when required columns (e.g. installed_on) are missing."""
    d = tmp_path / "bad_master"
    d.mkdir()
    # Missing installed_on
    pd.DataFrame({"gateway_id": ["001A7D000001"]}).to_csv(d / "gateway_master.csv", index=False)
    loader = DataLoader(data_dir=d)
    with pytest.raises(ValueError, match="missing required column"):
        loader.load_master()


def test_malformed_gateway_id_in_master_raises_valueerror(tmp_path):
    """Malformed gateway ID in master fleet raises ValueError on normalization."""
    d = tmp_path / "malformed_master"
    d.mkdir()
    pd.DataFrame({
        "gateway_id": ["MALFORMED_ID"],
        "installed_on": ["2025-01-01"],
    }).to_csv(d / "gateway_master.csv", index=False)
    loader = DataLoader(data_dir=d)
    with pytest.raises(ValueError, match="Invalid gateway ID format"):
        loader.load_master()


def test_null_timestamp_in_telemetry_raises_valueerror(tmp_path):
    """Telemetry partition with null or unparseable timestamps raises ValueError."""
    d = tmp_path / "data"
    d.mkdir()
    pd.DataFrame({
        "gateway_id": ["001A7D000001"],
        "installed_on": ["2025-01-01"],
    }).to_csv(d / "gateway_master.csv", index=False)

    t_dir = d / "telemetry" / "month=2026-02"
    t_dir.mkdir(parents=True)
    pd.DataFrame([
        {
            "gateway_id": "001A7D000001",
            "ts_utc": None,  # Null timestamp
            "offline_duration_sec": 10.0,
            "disconnection_cnt": 1.0,
            "reboot_cnt": 0.0,
        }
    ]).to_parquet(t_dir / "part-0.parquet")

    loader = DataLoader(data_dir=d)
    with pytest.raises(ValueError, match="null or unparseable timestamps"):
        loader.load_telemetry()


# =============================================================================
# 2. Scoring Input Validation & Edge Cases
# =============================================================================

def test_scoring_missing_required_columns_raises_valueerror():
    """score_week raises ValueError if telemetry_df lacks required metrics or ts."""
    monday = dt.date(2026, 2, 2)
    bad_df = pd.DataFrame({
        "gateway_id": ["001A7D000001"],
        "ts": [pd.Timestamp(monday, tz="UTC")],
        # Missing offline_duration_sec, disconnection_cnt, reboot_cnt
    })
    with pytest.raises(ValueError, match="missing required column"):
        score_week(bad_df, monday)


def test_scoring_timezone_naive_timestamps_raises_valueerror():
    """score_week raises ValueError if telemetry_df ts column is timezone-naive."""
    monday = dt.date(2026, 2, 2)
    naive_df = pd.DataFrame({
        "gateway_id": ["001A7D000001"],
        "ts": [pd.Timestamp("2026-02-01 10:00:00")],  # No tz
        "offline_duration_sec": [10.0],
        "disconnection_cnt": [1.0],
        "reboot_cnt": [0.0],
    })
    with pytest.raises(ValueError, match="must be timezone-aware"):
        score_week(naive_df, monday)


def test_scoring_invalid_decision_date_type_raises_typeerror():
    """score_week raises TypeError when decision_monday is an unsupported type."""
    df = pd.DataFrame(columns=["gateway_id", "ts", *METRICS])
    with pytest.raises(TypeError, match="Unsupported decision_monday type"):
        score_week(df, 12345678)  # integer instead of date


def test_scoring_empty_telemetry_returns_empty_dataframe():
    """score_week on empty DataFrame returns empty DataFrame with correct columns."""
    monday = dt.date(2026, 2, 2)
    df = pd.DataFrame(columns=["gateway_id", "ts", *METRICS])
    # Add UTC tz to ts column
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    res = score_week(df, monday)
    assert res.empty
    assert list(res.columns) == ["gateway_id", "score", "flagged_hours", "worst_metric"]


def test_scoring_nan_metric_values_do_not_breach():
    """NaN metric observations in recent window evaluate to False and do not produce breaches."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D000001"

    # 50 baseline rows
    base_rows = []
    for i in range(50):
        base_rows.append({
            "gateway_id": gid,
            "ts": end - dt.timedelta(hours=28 * 24 - 10 - i * 8),
            "offline_duration_sec": 10.0 + (i % 2) * 2.0,
            "disconnection_cnt": 5.0,
            "reboot_cnt": 1.0,
        })
    # Recent observation with NaN
    recent_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=2),
        "offline_duration_sec": np.nan,  # NaN
        "disconnection_cnt": 5.0,
        "reboot_cnt": 1.0,
    }]
    scored = score_week(pd.DataFrame(base_rows + recent_rows), monday)
    assert len(scored) == 1
    assert scored.iloc[0]["score"] == 0.0


# =============================================================================
# 3. Ranking Input Validation & Edge Cases
# =============================================================================

def test_ranking_top_k_zero_or_negative_raises_valueerror():
    """rank_and_select raises ValueError when top_k <= 0."""
    eligible = [f"001A7D0000{i:02X}" for i in range(1, 20)]
    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        rank_and_select(pd.DataFrame(), eligible, top_k=0)

    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        rank_and_select(pd.DataFrame(), eligible, top_k=-5)


def test_ranking_insufficient_fleet_raises_valueerror():
    """rank_and_select raises ValueError when eligible fleet cardinality < top_k."""
    with pytest.raises(ValueError, match="Fewer than 15 eligible gateways exist"):
        rank_and_select(pd.DataFrame(), ["001A7D000001", "001A7D000002"], top_k=15)


def test_ranking_duplicate_scored_rows_raises_valueerror():
    """rank_and_select explicitly rejects scored_df with ValueError if duplicate gateway IDs are passed."""
    eligible = [f"001A7D0000{i:02X}" for i in range(1, 20)]
    duplicated_scores = pd.DataFrame({
        "gateway_id": ["001A7D000001", "001A7D000001", "001A7D000002"],  # G01 duplicated
        "score": [15.0, 15.0, 10.0],
        "flagged_hours": [15, 15, 10],
        "worst_metric": ["offline_duration_sec", "offline_duration_sec", "reboot_cnt"],
    })
    with pytest.raises(ValueError, match="Duplicate scored records detected"):
        rank_and_select(duplicated_scores, eligible, top_k=15)


def test_ranking_all_zero_scores_sorted_deterministically_by_id():
    """When all gateways have score 0.0, ranking tie-breaks strictly by gateway_id ascending."""
    eligible = [f"001A7D0000{i:02X}" for i in range(1, 25)]
    # All silent
    res = rank_and_select(pd.DataFrame(), eligible, top_k=15)
    assert len(res) == 15
    assert (res["score"] == 0.0).all()
    assert list(res["gateway_id"]) == sorted(list(res["gateway_id"]))


# =============================================================================
# 4. Pipeline & Output Validation Edge Cases
# =============================================================================

def test_pipeline_empty_scored_weeks_raises_valueerror():
    """run_pipeline raises ValueError when scored_weeks is empty."""
    with pytest.raises(ValueError, match="scored_weeks sequence cannot be empty"):
        run_pipeline(scored_weeks=[])


def test_output_validation_rejects_missing_column():
    """validate_predictions_df reports missing required columns."""
    df = pd.DataFrame({
        "week_start": ["2026-02-02"],
        "rank": [1],
        "gateway_id": ["001A7D000001"],
        "score": [10.0],
        # Missing 'reason'
    })
    problems = validate_predictions_df(df, scored_weeks=[dt.date(2026, 2, 2)])
    assert any("Missing required column" in p for p in problems)


def test_output_validation_rejects_negative_scores():
    """validate_predictions_df reports negative scores."""
    df = pd.DataFrame({
        "week_start": ["2026-02-02"] * 15,
        "rank": list(range(1, 16)),
        "gateway_id": [f"001A7D0000{i:02X}" for i in range(1, 16)],
        "score": [-1.0] + [0.0] * 14,
        "reason": ["Valid reason"] * 15,
    })
    problems = validate_predictions_df(df, scored_weeks=[dt.date(2026, 2, 2)])
    assert any("Negative scores" in p for p in problems)


def test_output_validation_rejects_empty_reasons():
    """validate_predictions_df reports empty reasons."""
    df = pd.DataFrame({
        "week_start": ["2026-02-02"] * 15,
        "rank": list(range(1, 16)),
        "gateway_id": [f"001A7D0000{i:02X}" for i in range(1, 16)],
        "score": [0.0] * 15,
        "reason": [""] + ["Valid reason"] * 14,
    })
    problems = validate_predictions_df(df, scored_weeks=[dt.date(2026, 2, 2)])
    assert any("empty reason" in p for p in problems)


def test_output_validation_rejects_reasons_exceeding_max_chars():
    """validate_predictions_df reports reasons exceeding 300 characters."""
    df = pd.DataFrame({
        "week_start": ["2026-02-02"] * 15,
        "rank": list(range(1, 16)),
        "gateway_id": [f"001A7D0000{i:02X}" for i in range(1, 16)],
        "score": [0.0] * 15,
        "reason": ["X" * 301] + ["Valid reason"] * 14,
    })
    problems = validate_predictions_df(df, scored_weeks=[dt.date(2026, 2, 2)])
    assert any("exceed 300 characters" in p for p in problems)


def test_official_validator_missing_file_raises_filenotfound():
    """run_official_validator raises FileNotFoundError when predictions file does not exist."""
    with pytest.raises(FileNotFoundError, match="Predictions file does not exist"):
        run_official_validator("non_existent_file_path.csv")
