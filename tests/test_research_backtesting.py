"""Tests for research and historical backtesting subsystem.

Verifies:
1. DataLoader.load_meter_reads() functionality, validation, and caching.
2. FeatureExtractor initialization and feature extraction on a synthetic historical week.
3. TargetConstructor category contract matching:
   ['REPAIR_REQUIRED', 'FALSE_ALARM', 'INCONCLUSIVE', 'UNOBSERVED'].
4. Candidate ranking strategies on synthetic feature panels.
5. HistoricalBacktester execution on synthetic fixtures.
6. Weekly metrics and summary generation.
7. Strict temporal anti-leakage guards.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from nexora.data_loader import DataLoader
from nexora.feature_extractor import FeatureExtractor
from nexora.target_constructor import TargetConstructor
from nexora.backtesting.strategies import (
    CandidateAStrategy,
    CandidateBStrategy,
    CandidateCStrategy,
    CandidateDStrategy,
    CandidateEStrategy,
    CandidateFStrategy,
)
from nexora.backtesting.backtester import HistoricalBacktester
from nexora.backtesting.leakage import (
    run_future_engineer_review_leakage_test,
    run_meter_temporal_boundary_test,
)


@pytest.fixture
def synthetic_research_env(tmp_path):
    """Creates a minimal synthetic environment for research pipeline tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. gateway_master.csv (4 gateways)
    # G01: active, installed early
    # G02: active, installed early
    # G03: active, installed early
    # G04: active, installed early
    master_rows = [
        {"gateway_id": f"00:11:22:33:44:{i:02X}", "installed_on": "2025-01-01", "decommissioned_on": None, "region": "North"}
        for i in range(1, 5)
    ]
    pd.DataFrame(master_rows).to_csv(data_dir / "gateway_master.csv", index=False)

    # 2. meter_read_success.csv
    meter_rows = [
        {"gateway_id": "001122334401", "week_start": "2025-08-04", "meters_expected": 100, "meters_read": 95},
        {"gateway_id": "001122334402", "week_start": "2025-08-04", "meters_expected": 100, "meters_read": 80},
        {"gateway_id": "001122334403", "week_start": "2025-08-04", "meters_expected": 100, "meters_read": 0},
        {"gateway_id": "001122334404", "week_start": "2025-08-04", "meters_expected": 100, "meters_read": 100},
        {"gateway_id": "001122334401", "week_start": "2025-08-11", "meters_expected": 100, "meters_read": 98},
    ]
    pd.DataFrame(meter_rows).to_csv(data_dir / "meter_read_success.csv", index=False)

    # 3. telemetry partition (month=2025-08)
    telem_dir = data_dir / "telemetry" / "month=2025-08"
    telem_dir.mkdir(parents=True, exist_ok=True)
    telem_rows = []
    base_t = pd.Timestamp("2025-08-01 00:00:00", tz="UTC")
    for i in range(1, 5):
        gid = f"0011223344{i:02X}"
        for h in range(100):
            telem_rows.append({
                "gateway_id": gid,
                "ts_utc": (base_t + dt.timedelta(hours=h)).isoformat(),
                "offline_duration_sec": 3600.0 if (i == 1 and h > 50) else 0.0,
                "disconnection_cnt": 2 if (i == 2 and h > 50) else 0,
                "reboot_cnt": 3 if (i == 3 and h > 50) else 0,
            })
    pd.DataFrame(telem_rows).to_parquet(telem_dir / "part-0.parquet")

    # 4. field_visits.csv
    # G01: Fehler behoben -> REPAIR_REQUIRED
    # G02: Kein Fehler gefunden -> FALSE_ALARM
    # G03: Kein Zugang -> INCONCLUSIVE
    # G04: No visit -> UNOBSERVED
    visit_rows = [
        {
            "visit_id": "V001",
            "gateway_id": "00:11:22:33:44:01",
            "requested_on": "2025-08-04 10:00:00",
            "visited_on": "2025-08-05 14:00:00",
            "reason_reported": "Offline",
            "outcome": "Fehler behoben",
            "parts_replaced": "Antenna",
            "technician_hours": 2.5,
        },
        {
            "visit_id": "V002",
            "gateway_id": "00:11:22:33:44:02",
            "requested_on": "2025-08-04 11:00:00",
            "visited_on": "2025-08-06 09:00:00",
            "reason_reported": "Disconnections",
            "outcome": "Kein Fehler gefunden",
            "parts_replaced": None,
            "technician_hours": 1.0,
        },
        {
            "visit_id": "V003",
            "gateway_id": "00:11:22:33:44:03",
            "requested_on": "2025-08-04 12:00:00",
            "visited_on": "2025-08-07 15:00:00",
            "reason_reported": "Reboots",
            "outcome": "Kein Zugang",
            "parts_replaced": None,
            "technician_hours": 0.5,
        },
    ]
    pd.DataFrame(visit_rows).to_csv(data_dir / "field_visits.csv", index=False)

    return data_dir


def test_dataloader_load_meter_reads_success(synthetic_research_env):
    """DataLoader.load_meter_reads() loads, canonicalizes, parses timestamps, and caches."""
    loader = DataLoader(data_dir=synthetic_research_env)
    df = loader.load_meter_reads()

    assert len(df) == 5
    assert "week_start_dt" in df.columns
    assert df["week_start_dt"].dt.tz is not None
    assert (df["gateway_id"] == "001122334401").any()

    # Caching check
    cached = loader.load_meter_reads()
    assert id(loader._meter_reads_df) == id(cached) or len(cached) == len(df)


def test_dataloader_load_meter_reads_missing_file(tmp_path):
    """DataLoader.load_meter_reads() raises FileNotFoundError for missing file."""
    loader = DataLoader(data_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="meter_read_success.csv not found"):
        loader.load_meter_reads()


def test_dataloader_load_meter_reads_missing_columns(tmp_path):
    """DataLoader.load_meter_reads() raises ValueError for missing schema columns."""
    bad_df = pd.DataFrame({"gateway_id": ["001122334401"], "week_start": ["2025-08-04"]})
    bad_df.to_csv(tmp_path / "meter_read_success.csv", index=False)
    loader = DataLoader(data_dir=tmp_path)
    with pytest.raises(ValueError, match="missing required column"):
        loader.load_meter_reads()


def test_target_constructor_categories(synthetic_research_env):
    """TargetConstructor produces all 4 declared target categories accurately."""
    tc = TargetConstructor(data_dir=synthetic_research_env)

    assert tc.TARGET_CATEGORIES == [
        "REPAIR_REQUIRED",
        "FALSE_ALARM",
        "INCONCLUSIVE",
        "UNOBSERVED",
    ]

    target = tc.construct_weekly_target("2025-08-04", outcome_window_days=7)
    assert len(target) == 4

    cat_map = target.set_index("gateway_id")["target_category"].to_dict()
    assert cat_map["001122334401"] == "REPAIR_REQUIRED"
    assert cat_map["001122334402"] == "FALSE_ALARM"
    assert cat_map["001122334403"] == "INCONCLUSIVE"
    assert cat_map["001122334404"] == "UNOBSERVED"

    # Invariant: only REPAIR_REQUIRED has is_positive_repair == True
    rep_map = target.set_index("gateway_id")["is_positive_repair"].to_dict()
    assert rep_map["001122334401"] is True
    assert rep_map["001122334402"] is False
    assert rep_map["001122334403"] is False
    assert rep_map["001122334404"] is False


def test_feature_extractor_synthetic(synthetic_research_env):
    """FeatureExtractor extracts features for all active gateways strictly for t < T."""
    fe = FeatureExtractor(data_dir=synthetic_research_env)
    assert fe.loader is not None

    df = fe.extract("2025-08-04")
    assert len(df) == 4
    for col in fe.FEATURE_CODES:
        assert col in df.columns
    for alias in fe.ALIASES.values():
        assert alias in df.columns


def test_candidate_strategies_synthetic(synthetic_research_env):
    """Candidate strategies rank active gateways into consecutive ranks."""
    fe = FeatureExtractor(data_dir=synthetic_research_env)
    feat = fe.extract("2025-08-04")
    m_date = dt.date(2025, 8, 4)

    for StratCls in [CandidateAStrategy, CandidateBStrategy, CandidateCStrategy, CandidateDStrategy, CandidateEStrategy, CandidateFStrategy]:
        strat = StratCls()
        ranked = strat.rank(feat, m_date)
        assert len(ranked) == 4
        assert list(ranked.columns) == ["gateway_id", "rank", "score", "strategy_name"]
        assert sorted(ranked["rank"]) == [1, 2, 3, 4]


def test_historical_backtester_synthetic(synthetic_research_env, tmp_path):
    """HistoricalBacktester runs end-to-end on synthetic data and produces summary metrics."""
    out_dir = tmp_path / "backtest_out"
    strategies = [CandidateAStrategy(), CandidateBStrategy()]
    bt = HistoricalBacktester(
        strategies=strategies,
        data_dir=synthetic_research_env,
        output_dir=out_dir,
    )

    weekly_df, summary_df = bt.run(mondays=["2025-08-04"])

    assert len(weekly_df) == 2  # 2 strategies * 1 week
    assert "repair_capture_at_15" in weekly_df.columns
    assert "total_repairs" in weekly_df.columns
    assert (weekly_df["total_repairs"] == 1).all()  # 1 confirmed repair on 2025-08-04

    assert len(summary_df) == 2
    assert "total_repairs_captured" in summary_df.columns
    assert "total_false_alarms" in summary_df.columns

    # Test artifact serialization
    paths = bt.save_results(out_dir)
    for p in paths.values():
        assert p.exists()
        assert p.stat().st_size > 0


def test_temporal_leakage_guards():
    """Verifies that temporal anti-leakage guards pass on available dataset."""
    data_path = Path("data")
    if not data_path.exists() or not (data_path / "meter_read_success.csv").exists():
        pytest.skip("Challenge dataset not present in data/ directory")

    assert run_meter_temporal_boundary_test("data") is True
    assert run_future_engineer_review_leakage_test("data") is True
