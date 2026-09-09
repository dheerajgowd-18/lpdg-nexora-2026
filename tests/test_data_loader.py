"""Unit tests for DataLoader, ID canonicalization, deduplication, and dataset isolation."""

import datetime as dt
from pathlib import Path
import re
import numpy as np
import pandas as pd
import pytest

from nexora.data_loader import (
    DataLoader,
    normalize_gateway_id,
    is_valid_gateway_id,
    REQUIRED_MASTER_COLUMNS,
    REQUIRED_TELEMETRY_COLUMNS,
)

CANONICAL_HEX_REGEX = re.compile(r"^[0-9A-F]{12}$")


# =============================================================================
# 1. Gateway ID Canonicalization Tests
# =============================================================================

def test_canonicalize_colon_delimited():
    """Colon-delimited hexadecimal IDs normalize to 12-char uppercase bare hex."""
    assert normalize_gateway_id("06:39:EA:56:02:C1") == "0639EA5602C1"
    assert normalize_gateway_id("00:1A:7D:00:01:39") == "001A7D000139"


def test_canonicalize_lowercase():
    """Lowercase hex strings normalize to uppercase bare hex."""
    assert normalize_gateway_id("0639ea5602c1") == "0639EA5602C1"
    assert normalize_gateway_id("06:39:ea:56:02:c1") == "0639EA5602C1"


def test_canonicalize_uppercase():
    """Uppercase hex strings remain uppercase bare hex."""
    assert normalize_gateway_id("0639EA5602C1") == "0639EA5602C1"


def test_canonicalize_whitespace():
    """Leading and trailing whitespace is stripped."""
    assert normalize_gateway_id("  0639EA5602C1  ") == "0639EA5602C1"
    assert normalize_gateway_id(" \t06:39:EA:56:02:C1\n ") == "0639EA5602C1"


def test_canonicalize_already_canonical():
    """Already canonical 12-char bare uppercase hex strings pass through unchanged."""
    canonical = "001A7D000139"
    assert normalize_gateway_id(canonical) == canonical
    assert CANONICAL_HEX_REGEX.match(normalize_gateway_id(canonical)) is not None


def test_canonicalize_invalid_ids():
    """Invalid identifiers raise ValueError and fail validation check."""
    invalid_cases = [
        "",                     # empty
        "short",                # too short
        "0639EA",               # 6 chars
        "0639EA5602C1A",        # 13 chars
        "0639EA5602CG",         # non-hex 'G'
        "0639EA5602C!",         # special character
        "06:39:EA:56:02",       # 5 octets
        "06:39:EA:56:02:C1:AA", # 7 octets
        "NOT-A-GATEWAY-ID",     # arbitrary text
        "06-39-EA-56-02-C1",    # dash separated
    ]
    for case in invalid_cases:
        with pytest.raises(ValueError):
            normalize_gateway_id(case)
        assert not is_valid_gateway_id(case)


def test_canonical_format_contract():
    """Every successful normalization strictly conforms to ^[0-9A-F]{12}$."""
    samples = [
        "06:39:EA:56:02:C1",
        "00:1a:7d:00:ff:01",
        "aabbccddeeff",
        "  1234567890AB  ",
    ]
    for sample in samples:
        norm = normalize_gateway_id(sample)
        assert len(norm) == 12
        assert CANONICAL_HEX_REGEX.match(norm) is not None
        assert is_valid_gateway_id(sample)


# =============================================================================
# 2. DataLoader Telemetry Deduplication and Ingestion Tests
# =============================================================================

@pytest.fixture
def synthetic_data_dir(tmp_path):
    """Creates a temporary synthetic challenge data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Master fleet: 16 active gateways
    master_rows = []
    for i in range(1, 17):
        master_rows.append({
            "gateway_id": f"00:1A:7D:00:00:{i:02X}",
            "installed_on": "2025-01-01",
            "decommissioned_on": None,
            "region": "Region-Nord",
        })
    pd.DataFrame(master_rows).to_csv(data_dir / "gateway_master.csv", index=False)

    # Telemetry partition directory
    telem_dir = data_dir / "telemetry" / "month=2026-02"
    telem_dir.mkdir(parents=True)

    # Telemetry with known gateway and exact duplicate records
    # plus an unknown gateway
    telem_rows = [
        # Record 1
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01 10:00:00",
            "offline_duration_sec": 100.0,
            "disconnection_cnt": 2.0,
            "reboot_cnt": 1.0,
        },
        # Exact duplicate of Record 1 on (gateway_id, ts_utc)
        {
            "gateway_id": "00:1A:7D:00:00:01",  # colon format of same gateway
            "ts_utc": "2026-02-01 10:00:00",
            "offline_duration_sec": 999.0,      # should be discarded by keep='first'
            "disconnection_cnt": 99.0,
            "reboot_cnt": 99.0,
        },
        # Record 2 for same gateway at different timestamp
        {
            "gateway_id": "001A7D000001",
            "ts_utc": "2026-02-01 11:00:00",
            "offline_duration_sec": 50.0,
            "disconnection_cnt": 1.0,
            "reboot_cnt": 0.0,
        },
        # Record for unknown gateway (not in master)
        {
            "gateway_id": "FFFFFFFFFFFF",
            "ts_utc": "2026-02-01 12:00:00",
            "offline_duration_sec": 200.0,
            "disconnection_cnt": 3.0,
            "reboot_cnt": 1.0,
        },
    ]
    pd.DataFrame(telem_rows).to_parquet(telem_dir / "part-0.parquet")
    return data_dir


def test_telemetry_deduplication(synthetic_data_dir):
    """Verifies drop_duplicates on (gateway_id, ts_utc) keeping first record."""
    loader = DataLoader(data_dir=synthetic_data_dir)
    df = loader.load_telemetry(filter_known_gateways=False)

    # 4 rows raw: 1 exact duplicate removed -> 3 rows remaining
    assert len(df) == 3

    # Check that the first record's values were preserved
    rec1 = df[(df["gateway_id"] == "001A7D000001") & (df["ts_utc"] == "2026-02-01 10:00:00")]
    assert len(rec1) == 1
    assert rec1.iloc[0]["offline_duration_sec"] == 100.0


def test_telemetry_timestamp_utc_tz_aware(synthetic_data_dir):
    """Verifies that 'ts' is converted to timezone-aware UTC datetime."""
    loader = DataLoader(data_dir=synthetic_data_dir)
    df = loader.load_telemetry()
    assert "ts" in df.columns
    assert isinstance(df["ts"].dtype, pd.DatetimeTZDtype)
    assert str(df["ts"].dt.tz) == "UTC"


def test_unknown_gateway_filtering(synthetic_data_dir):
    """Telemetry for gateways not in gateway_master.csv is filtered when filter_known_gateways=True."""
    loader = DataLoader(data_dir=synthetic_data_dir)

    # Default filter_known_gateways=True
    df_filtered = loader.load_telemetry(filter_known_gateways=True)
    assert "FFFFFFFFFFFF" not in set(df_filtered["gateway_id"])
    assert "001A7D000001" in set(df_filtered["gateway_id"])

    # Reset cache and test filter_known_gateways=False
    loader._telemetry_df = None
    df_unfiltered = loader.load_telemetry(filter_known_gateways=False)
    assert "FFFFFFFFFFFF" in set(df_unfiltered["gateway_id"])


def test_missing_data_directory():
    """Non-existent data directory raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        DataLoader(data_dir="non_existent_dir_12345")


def test_missing_master_file(tmp_path):
    """Missing gateway_master.csv raises FileNotFoundError."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    loader = DataLoader(data_dir=empty_dir)
    with pytest.raises(FileNotFoundError):
        loader.load_master()


def test_missing_master_required_columns(tmp_path):
    """Missing required master columns raises ValueError."""
    data_dir = tmp_path / "bad_master"
    data_dir.mkdir()
    # Missing installed_on
    pd.DataFrame({"gateway_id": ["001A7D000001"]}).to_csv(data_dir / "gateway_master.csv", index=False)
    loader = DataLoader(data_dir=data_dir)
    with pytest.raises(ValueError, match="missing required column"):
        loader.load_master()


def test_dataset_isolation(synthetic_data_dir):
    """Production data loading succeeds with ONLY gateway_master.csv and telemetry/.

    Explicitly verifies that no auxiliary challenge files (field_visits.csv,
    meter_read_success.csv, engineer_review_2026-02.xlsx) are required.
    """
    assert not (synthetic_data_dir / "field_visits.csv").exists()
    assert not (synthetic_data_dir / "meter_read_success.csv").exists()
    assert not (synthetic_data_dir / "engineer_review_2026-02.xlsx").exists()

    loader = DataLoader(data_dir=synthetic_data_dir)
    master = loader.load_master()
    assert len(master) == 16

    telemetry = loader.load_telemetry()
    assert len(telemetry) == 2  # 2 known non-duplicate rows
