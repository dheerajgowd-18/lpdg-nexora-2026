"""Data contract validation tests for NEXORA 2026 (Phase 3).

Verifies fail-fast data contracts across all ingestion boundaries:
1. Missing required columns
2. Malformed gateway IDs
3. Null or empty gateway IDs
4. Non-numeric / decimal meter counts
5. Negative meter counts
6. meters_read > meters_expected
7. Malformed timestamps / dates
8. Conflicting telemetry duplicates (raises ValueError)
9. Identical telemetry duplicates (safely deduplicated)
10. Invalid lifecycle dates (installed_on > decommissioned_on)
11. Invalid target categories and field visit outcomes
12. Temporal leakage prevention (right-open boundaries t < T)
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import pandas as pd
import pytest

from nexora.config import (
    REQUIRED_MASTER_COLUMNS,
    REQUIRED_TELEMETRY_COLUMNS,
    REQUIRED_METER_COLUMNS,
)
from nexora.data_loader import (
    DataLoader,
    is_valid_gateway_id,
    normalize_gateway_id,
)
from nexora.target_constructor import TargetConstructor


# =============================================================================
# 1. Missing Required Columns
# =============================================================================

def test_contract_missing_required_column_master(tmp_path):
    """load_master() raises ValueError when a required column is missing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Missing required column 'installed_on'
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "region": "Nord",
    }]).to_csv(data_dir / "gateway_master.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="gateway_master.csv missing required column"):
        loader.load_master()


def test_contract_missing_required_column_meter_reads(tmp_path):
    """load_meter_reads() raises ValueError when required column is missing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "week_start": "2026-02-02",
        "meters_read": 100,
        # missing 'meters_expected'
    }]).to_csv(data_dir / "meter_read_success.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="meter_read_success.csv missing required column"):
        loader.load_meter_reads()


def test_contract_missing_required_column_field_visits(tmp_path):
    """load_field_visits() raises ValueError when required column is missing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "visit_id": 1,
        "gateway_id": "001A7D000001",
        "visited_on": "2026-01-15",
        # missing 'requested_on', 'reason_reported', 'outcome'
    }]).to_csv(data_dir / "field_visits.csv", index=False)

    tc = TargetConstructor(data_dir=data_dir)
    with pytest.raises(ValueError, match="field_visits.csv missing required column"):
        tc.load_field_visits()


# =============================================================================
# 2. Malformed Gateway IDs
# =============================================================================

@pytest.mark.parametrize("invalid_id", [
    "001A7D0000G1",       # non-hex 'G'
    "001A7D",             # too short (6 chars)
    "001A7D0000001",      # too long (13 chars)
    "00:1A:7D:00:00:ZZ",  # colon format with non-hex 'ZZ'
    "00-1A-7D-00-00-01",  # hyphenated not supported
])
def test_contract_malformed_gateway_id_rejected(invalid_id):
    """normalize_gateway_id raises ValueError on malformed gateway identifiers."""
    assert not is_valid_gateway_id(invalid_id)
    with pytest.raises(ValueError, match="Invalid gateway ID format"):
        normalize_gateway_id(invalid_id)


def test_contract_load_master_with_malformed_id_raises(tmp_path):
    """load_master() fails fast if any gateway_id is malformed."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "NOT_A_VALID_HEX_ID",
        "installed_on": "2025-01-01",
        "region": "Nord",
    }]).to_csv(data_dir / "gateway_master.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="Invalid gateway ID format"):
        loader.load_master()


# =============================================================================
# 3. Null or Empty Gateway IDs
# =============================================================================

@pytest.mark.parametrize("empty_val", ["", "   "])
def test_contract_empty_gateway_id(empty_val):
    """normalize_gateway_id raises ValueError for empty strings."""
    assert not is_valid_gateway_id(empty_val)
    with pytest.raises(ValueError, match="Gateway ID cannot be empty"):
        normalize_gateway_id(empty_val)


@pytest.mark.parametrize("null_val", [None, float("nan")])
def test_contract_null_gateway_id(null_val):
    """normalize_gateway_id raises ValueError for null/NaN."""
    assert not is_valid_gateway_id(null_val)
    with pytest.raises(ValueError, match="Gateway ID cannot be null or NaN"):
        normalize_gateway_id(null_val)


def test_contract_load_master_with_null_gateway_id_raises(tmp_path):
    """load_master() raises ValueError if gateway_id is null/empty."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": None,
        "installed_on": "2025-01-01",
        "region": "Nord",
    }]).to_csv(data_dir / "gateway_master.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="Gateway ID cannot be null or NaN"):
        loader.load_master()


# =============================================================================
# 4. Invalid Numeric Meter Counts (Non-Numeric String, Decimals, Nulls)
# =============================================================================

def test_contract_meter_reads_rejects_non_numeric_strings(tmp_path):
    """load_meter_reads() raises ValueError on non-numeric strings in count columns."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "week_start": "2026-02-02",
        "meters_expected": "one_hundred",
        "meters_read": 50,
    }]).to_csv(data_dir / "meter_read_success.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="non-numeric"):
        loader.load_meter_reads()


def test_contract_meter_reads_rejects_nulls(tmp_path):
    """load_meter_reads() raises ValueError on null/NaN in meter count columns."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "week_start": "2026-02-02",
        "meters_expected": None,
        "meters_read": 50,
    }]).to_csv(data_dir / "meter_read_success.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="null values"):
        loader.load_meter_reads()


def test_contract_meter_reads_rejects_fractional_decimals(tmp_path):
    """load_meter_reads() raises ValueError if meter counts contain non-integer decimals."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "week_start": "2026-02-02",
        "meters_expected": 100.5,
        "meters_read": 50,
    }]).to_csv(data_dir / "meter_read_success.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="decimal values"):
        loader.load_meter_reads()


# =============================================================================
# 5. Negative Meter Counts
# =============================================================================

def test_contract_meter_reads_rejects_negative_counts(tmp_path):
    """load_meter_reads() raises ValueError if meters_read or meters_expected < 0."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "week_start": "2026-02-02",
        "meters_expected": 100,
        "meters_read": -5,
    }]).to_csv(data_dir / "meter_read_success.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="negative values"):
        loader.load_meter_reads()


# =============================================================================
# 6. meters_read > meters_expected
# =============================================================================

def test_contract_meter_reads_rejects_read_greater_than_expected(tmp_path):
    """load_meter_reads() raises ValueError if meters_read > meters_expected."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "week_start": "2026-02-02",
        "meters_expected": 50,
        "meters_read": 60,
    }]).to_csv(data_dir / "meter_read_success.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="meters_read.*>.*meters_expected"):
        loader.load_meter_reads()


# =============================================================================
# 7. Malformed Timestamps
# =============================================================================

def test_contract_telemetry_rejects_malformed_timestamp(tmp_path):
    """load_telemetry() raises ValueError on unparseable timestamp strings."""
    data_dir = tmp_path / "data"
    t_dir = data_dir / "telemetry" / "month=2026-02"
    t_dir.mkdir(parents=True)
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "ts_utc": "invalid-datetime-format",
        "offline_duration_sec": 10.0,
        "disconnection_cnt": 0.0,
        "reboot_cnt": 0.0,
    }]).to_parquet(t_dir / "part-0.parquet")

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="null or unparseable timestamps"):
        loader.load_telemetry(filter_known_gateways=False)


def test_contract_master_rejects_malformed_installed_date(tmp_path):
    """load_master() raises ValueError on invalid installed_on date format."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "installed_on": "not-a-date",
        "region": "Nord",
    }]).to_csv(data_dir / "gateway_master.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="unparseable dates in 'installed_on'"):
        loader.load_master()


# =============================================================================
# 8. Conflicting Telemetry Duplicates (Raises ValueError)
# =============================================================================

def test_contract_conflicting_telemetry_duplicates_raises_valueerror(tmp_path):
    """load_telemetry() raises ValueError when identical (gateway, ts) has conflicting values."""
    data_dir = tmp_path / "data"
    t_dir = data_dir / "telemetry" / "month=2026-02"
    t_dir.mkdir(parents=True)
    pd.DataFrame([
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01 10:00:00",
            "offline_duration_sec": 10.0,
            "disconnection_cnt": 1.0,
            "reboot_cnt": 0.0,
        },
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01 10:00:00",
            "offline_duration_sec": 999.0,  # CONFLICTING value
            "disconnection_cnt": 50.0,
            "reboot_cnt": 2.0,
        },
    ]).to_parquet(t_dir / "part-0.parquet")

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="Conflicting telemetry duplicates detected"):
        loader.load_telemetry(filter_known_gateways=False)


# =============================================================================
# 9. Identical Telemetry Duplicates (Safely Deduplicated)
# =============================================================================

def test_contract_identical_telemetry_duplicates_safely_collapsed(tmp_path):
    """load_telemetry() safely collapses identical duplicate rows without error."""
    data_dir = tmp_path / "data"
    t_dir = data_dir / "telemetry" / "month=2026-02"
    t_dir.mkdir(parents=True)
    pd.DataFrame([
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01 10:00:00",
            "offline_duration_sec": 10.0,
            "disconnection_cnt": 1.0,
            "reboot_cnt": 0.0,
        },
        {
            "gateway_id": "00:1A:7D:00:00:01",  # colon format canonicalizes to same ID
            "ts_utc": "2026-02-01 10:00:00",
            "offline_duration_sec": 10.0,       # IDENTICAL measurement values
            "disconnection_cnt": 1.0,
            "reboot_cnt": 0.0,
        },
    ]).to_parquet(t_dir / "part-0.parquet")

    loader = DataLoader(data_dir=data_dir)
    df = loader.load_telemetry(filter_known_gateways=False)
    assert len(df) == 1
    assert df.iloc[0]["gateway_id"] == "001A7D000001"
    assert df.iloc[0]["offline_duration_sec"] == 10.0


# =============================================================================
# 10. Invalid Lifecycle Date (installed_on > decommissioned_on)
# =============================================================================

def test_contract_master_invalid_lifecycle_order_raises(tmp_path):
    """load_master() raises ValueError when installed_on is after decommissioned_on."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "installed_on": "2026-06-01",
        "decommissioned_on": "2025-01-01",  # Decommissioned BEFORE installation
        "region": "Nord",
    }]).to_csv(data_dir / "gateway_master.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="installed_on .* > decommissioned_on"):
        loader.load_master()


# =============================================================================
# 11. Invalid Target Category and Field Visit Outcomes
# =============================================================================

def test_contract_field_visits_invalid_outcome_raises(tmp_path):
    """load_field_visits() raises ValueError on unapproved outcome vocabulary."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "visit_id": 1,
        "gateway_id": "001A7D000001",
        "requested_on": "2026-01-01",
        "visited_on": "2026-01-05",
        "reason_reported": "Test Reason",
        "outcome": "Unknown Status",  # Not one of the 3 official outcomes
    }]).to_csv(data_dir / "field_visits.csv", index=False)

    tc = TargetConstructor(data_dir=data_dir)
    with pytest.raises(ValueError, match="invalid outcome"):
        tc.load_field_visits()


def test_contract_field_visits_chronology_check_raises(tmp_path):
    """load_field_visits() raises ValueError if visited_on < requested_on."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "visit_id": 1,
        "gateway_id": "001A7D000001",
        "requested_on": "2026-01-10",
        "visited_on": "2026-01-05",  # Visited BEFORE requested
        "reason_reported": "Test Reason",
        "outcome": "Fehler behoben",
    }]).to_csv(data_dir / "field_visits.csv", index=False)

    tc = TargetConstructor(data_dir=data_dir)
    with pytest.raises(ValueError, match="invalid chronology"):
        tc.load_field_visits()


def test_contract_engineer_review_invalid_kategorie_raises(tmp_path):
    """load_engineer_review() raises ValueError on invalid Kategorie."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "standort": "Berlin",
        "Kategorie": "Defekt",  # Not Normal or Schlecht
        "reviewed_on": "2026-02-15",
        "reviewer": "M. Weber",
        "Bemerkung": "Test comment",
    }]).to_excel(data_dir / "engineer_review_2026-02.xlsx", index=False)

    tc = TargetConstructor(data_dir=data_dir)
    with pytest.raises(ValueError, match="invalid Kategorie"):
        tc.load_engineer_review()


# =============================================================================
# 12. Temporal Leakage Attempt (Right-Open Boundaries t < T)
# =============================================================================

def test_contract_temporal_leakage_meter_boundary(tmp_path):
    """Meter reads are strictly filtered with right-open boundary: week_start_dt < T."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([
        # Past week: strictly before decision Monday 2026-02-09
        {
            "gateway_id": "001A7D000001",
            "week_start": "2026-02-02",
            "meters_expected": 100,
            "meters_read": 90,
        },
        # Decision Monday itself (future/concurrent data relative to morning cutoff)
        {
            "gateway_id": "001A7D000001",
            "week_start": "2026-02-09",
            "meters_expected": 100,
            "meters_read": 10,
        },
        # Subsequent week
        {
            "gateway_id": "001A7D000001",
            "week_start": "2026-02-16",
            "meters_expected": 100,
            "meters_read": 5,
        },
    ]).to_csv(data_dir / "meter_read_success.csv", index=False)

    loader = DataLoader(data_dir=data_dir)
    meter_df = loader.load_meter_reads()

    # Apply strict anti-leakage boundary as required for decision Monday 2026-02-09
    decision_monday = pd.to_datetime("2026-02-09", utc=True)
    visible_reads = meter_df[meter_df["week_start_dt"] < decision_monday]

    assert len(visible_reads) == 1
    assert visible_reads.iloc[0]["week_start"] == "2026-02-02"
    assert "2026-02-09" not in visible_reads["week_start"].values
    assert "2026-02-16" not in visible_reads["week_start"].values


# =============================================================================
# 13. Normalized UTC Timestamp Deduplication & Conflict Contracts (FIX 1)
# =============================================================================

def test_contract_normalized_timestamp_duplicate_identical_collapsed(tmp_path):
    """Different raw string formats representing the same UTC instant are collapsed if measurements match."""
    data_dir = tmp_path / "data"
    t_dir = data_dir / "telemetry" / "month=2026-02"
    t_dir.mkdir(parents=True)
    pd.DataFrame([
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01T10:00:00Z",       # ISO-8601 UTC
            "offline_duration_sec": 10.0,
            "disconnection_cnt": 1.0,
            "reboot_cnt": 0.0,
        },
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01 11:00:00+01:00",  # +01:00 offset (same UTC instant 10:00:00Z)
            "offline_duration_sec": 10.0,            # IDENTICAL measurements
            "disconnection_cnt": 1.0,
            "reboot_cnt": 0.0,
        },
    ]).to_parquet(t_dir / "part-0.parquet")

    loader = DataLoader(data_dir=data_dir)
    df = loader.load_telemetry(filter_known_gateways=False)
    assert len(df) == 1, "Identical observations at same UTC instant must collapse to 1 row"
    assert df.iloc[0]["gateway_id"] == "001A7D000001"
    assert df.iloc[0]["offline_duration_sec"] == 10.0


def test_contract_normalized_timestamp_duplicate_conflicting_raises(tmp_path):
    """Different raw string formats representing the same UTC instant with differing values raise ValueError."""
    data_dir = tmp_path / "data"
    t_dir = data_dir / "telemetry" / "month=2026-02"
    t_dir.mkdir(parents=True)
    pd.DataFrame([
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01T10:00:00Z",       # ISO-8601 UTC
            "offline_duration_sec": 10.0,
            "disconnection_cnt": 1.0,
            "reboot_cnt": 0.0,
        },
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01 11:00:00+01:00",  # Same UTC instant
            "offline_duration_sec": 999.0,           # CONFLICTING value
            "disconnection_cnt": 50.0,
            "reboot_cnt": 2.0,
        },
    ]).to_parquet(t_dir / "part-0.parquet")

    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="Conflicting telemetry duplicates detected"):
        loader.load_telemetry(filter_known_gateways=False)


# =============================================================================
# 14. Dynamic Pre-T Scoreability & Week Support Contracts (FIX 2)
# =============================================================================

def test_contract_is_monday_scoreable_requires_pre_t_windows():
    """is_monday_scoreable requires telemetry in pre-T [T-28d, T) and [T-7d, T)."""
    from nexora.api import is_monday_scoreable

    target_monday = dt.date(2026, 4, 27)

    # 1. Telemetry strictly in the future relative to T (temporal leakage attempt)
    future_telem = pd.DataFrame([
        {"gateway_id": "001A7D000001", "ts": pd.Timestamp("2026-04-27 00:00:00", tz="UTC")},
        {"gateway_id": "001A7D000001", "ts": pd.Timestamp("2026-04-28 12:00:00", tz="UTC")},
    ])
    assert not is_monday_scoreable(target_monday, future_telem)

    # 2. Telemetry too stale (ends before T - 7d, so [T-7d, T) is empty)
    stale_telem = pd.DataFrame([
        {"gateway_id": "001A7D000001", "ts": pd.Timestamp("2026-04-10 12:00:00", tz="UTC")},
    ])
    assert not is_monday_scoreable(target_monday, stale_telem)

    # 3. Valid pre-T telemetry covering baseline and recent evaluation windows
    valid_telem = pd.DataFrame([
        # In baseline window [2026-03-30, 2026-04-27)
        {"gateway_id": "001A7D000001", "ts": pd.Timestamp("2026-04-05 12:00:00", tz="UTC")},
        # In recent window [2026-04-20, 2026-04-27)
        {"gateway_id": "001A7D000001", "ts": pd.Timestamp("2026-04-26 12:00:00", tz="UTC")},
    ])
    assert is_monday_scoreable(target_monday, valid_telem)

    # 4. Non-Monday dates are never scoreable
    assert not is_monday_scoreable(dt.date(2026, 4, 28), valid_telem)  # Tuesday


def test_contract_insufficient_pre_t_telemetry_returns_404(tmp_path):
    """API returns 404 for a Monday whose pre-T recent window has insufficient telemetry."""
    from fastapi.testclient import TestClient
    from nexora.api import create_app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "installed_on": "2025-01-01",
        "decommissioned_on": None,
        "region": "Nord",
    }]).to_csv(data_dir / "gateway_master.csv", index=False)

    # Telemetry only through April 10 (insufficient for April 27)
    t_dir = data_dir / "telemetry" / "month=2026-04"
    t_dir.mkdir(parents=True)
    pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "ts_utc": "2026-04-10 12:00:00",
        "offline_duration_sec": 10.0,
        "disconnection_cnt": 1.0,
        "reboot_cnt": 0.0,
    }]).to_parquet(t_dir / "part-0.parquet")

    app = create_app(data_dir=data_dir)
    with TestClient(app) as client:
        # April 27 has zero data in its recent window [2026-04-20, 2026-04-27)
        resp = client.get("/predictions/2026-04-27")
        assert resp.status_code == 404
        assert "Unsupported week_start" in resp.json()["detail"]

