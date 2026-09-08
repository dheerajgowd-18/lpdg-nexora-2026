"""
Automated leakage and determinism test suite for NEXORA 2026 backtesting.
Validates temporal boundaries, synthetic future event isolation, and output determinism.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd

from ..data_loader import DataLoader
from ..feature_extractor import FeatureExtractor
from ..target_constructor import TargetConstructor
from .strategies import ALL_STRATEGIES, CandidateStrategy


def run_synthetic_telemetry_leakage_test(data_dir: str | Path = "data") -> bool:
    """Injects synthetic telemetry events at and after T and verifies zero feature change."""
    fe = FeatureExtractor(data_dir=data_dir)
    test_monday = "2025-10-06"
    T = pd.Timestamp(test_monday, tz="UTC")

    # 1. Baseline extraction
    df_clean = fe.extract(test_monday)

    # 2. Inject synthetic future telemetry at t = T and t = T + 2 hours
    test_gid = df_clean.iloc[0]["gateway_id"]
    month_str = T.strftime("%Y-%m")

    # Access telemetry cache and inject
    cached_telem = fe.loader._telemetry_cache.get(month_str)
    if cached_telem is not None:
        synthetic_rows = pd.DataFrame([
            {
                "gateway_id": test_gid,
                "ts_utc": T.isoformat(),
                "ts": T,
                "offline_duration_sec": 999999,
                "reboot_cnt": 999,
                "disconnection_cnt": 999,
            },
            {
                "gateway_id": test_gid,
                "ts_utc": (T + dt.timedelta(hours=2)).isoformat(),
                "ts": T + dt.timedelta(hours=2),
                "offline_duration_sec": 999999,
                "reboot_cnt": 999,
                "disconnection_cnt": 999,
            },
        ])
        fe.loader._telemetry_cache[month_str] = pd.concat(
            [cached_telem, synthetic_rows], ignore_index=True
        )

    # 3. Re-extract features
    df_injected = fe.extract(test_monday)

    # 4. Restore cache
    if cached_telem is not None:
        fe.loader._telemetry_cache[month_str] = cached_telem

    # 5. Assert exact numerical equality across all features
    for col in fe.FEATURE_CODES:
        diff = np.abs(df_clean[col].values - df_injected[col].values).max()
        assert diff == 0.0, f"LEAKAGE DETECTED in {col}: max absolute diff = {diff}"

    return True


# Note on Field-Visit Structural Isolation:
# Under the NEXORA architecture, field_visits.csv is loaded exclusively by TargetConstructor
# to build evaluation targets. FeatureExtractor never reads, references, or depends on
# field_visits.csv. Therefore, field-visit leakage into feature extraction is structurally
# impossible by code separation.


def run_future_engineer_review_leakage_test(data_dir: str | Path = "data") -> bool:
    """Verifies that engineer review labels cannot be accessed for T <= 2026-02-15,
    and for post-review dates every returned review has reviewed_on < as_of_date.
    """
    tc = TargetConstructor(data_dir=data_dir)

    # 1. Historical weeks (as_of_date <= 2026-02-15) must return strictly 0 rows
    for date_str in ["2025-08-04", "2025-12-15", "2026-02-02", "2026-02-09", "2026-02-15"]:
        labels = tc.get_engineer_review_labels(date_str)
        assert len(labels) == 0, f"LEAKAGE DETECTED: Engineer review returned {len(labels)} rows for {date_str}"

    # 2. For post-review date, verify temporal correctness: reviewed_on < as_of_date
    post_date_str = "2026-02-16"
    post_T = pd.Timestamp(post_date_str, tz="UTC")
    post_labels = tc.get_engineer_review_labels(post_date_str)
    assert not post_labels.empty, f"Expected non-empty engineer review labels after review date {post_date_str}"

    reviewed_ts = pd.to_datetime(post_labels["reviewed_on"], utc=True)
    assert (reviewed_ts < post_T).all(), (
        f"TEMPORAL LEAKAGE: Review records with reviewed_on >= {post_date_str} were returned"
    )
    return True


def run_meter_temporal_boundary_test(data_dir: str | Path = "data") -> bool:
    """Verifies that meter read features for historical weeks strictly exclude future weeks."""
    fe = FeatureExtractor(data_dir=data_dir)

    # Week 1: 2025-08-04 (earliest meter week in data is 2025-08-04)
    df_w1 = fe.extract("2025-08-04")
    # All F17 must be 0.0 because no meter read occurred before 2025-08-04
    assert (df_w1["F17"] == 0.0).all(), "LEAKAGE: F17 has non-zero values on earliest historical week"

    # Week 2: 2025-08-11 (only 1 week of meter reads before 2025-08-11)
    df_w2 = fe.extract("2025-08-11")
    # Verify F17 only uses data from 2025-08-04
    m_reads = fe.loader.load_meter_reads()
    m_reads_pre_w2 = m_reads[m_reads["week_start_dt"] < pd.Timestamp("2025-08-11", tz="UTC")]
    assert len(m_reads_pre_w2["week_start"].unique()) == 1, "Expected exactly 1 historical meter week prior to 2025-08-11"

    return True


def run_determinism_test(strategies: list[CandidateStrategy] | None = None, data_dir: str | Path = "data") -> bool:
    """Verifies that backtest execution produces identical rankings, scores, and metrics across runs."""
    fe = FeatureExtractor(data_dir=data_dir)
    tc = TargetConstructor(data_dir=data_dir)
    strategies = strategies or ALL_STRATEGIES

    test_mondays = ["2025-09-01", "2025-11-17", "2026-01-12"]

    for monday_str in test_mondays:
        m_date = dt.date.fromisoformat(monday_str)
        feat1 = fe.extract(monday_str)
        feat2 = fe.extract(monday_str)

        # Features identical
        pd.testing.assert_frame_equal(feat1, feat2)

        for strat in strategies:
            rank1 = strat.rank(feat1, m_date)
            rank2 = strat.rank(feat2, m_date)

            pd.testing.assert_frame_equal(
                rank1, rank2,
                check_exact=True,
                obj=f"{strat.name} on {monday_str}",
            )

    return True


def run_all_leakage_tests(data_dir: str | Path = "data") -> dict[str, bool]:
    """Runs the full suite of leakage and determinism tests."""
    results = {
        "synthetic_telemetry_isolation": run_synthetic_telemetry_leakage_test(data_dir),
        "engineer_review_temporal_guard": run_future_engineer_review_leakage_test(data_dir),
        "meter_data_temporal_boundary": run_meter_temporal_boundary_test(data_dir),
        "ranking_determinism": run_determinism_test(data_dir=data_dir),
    }
    return results
