"""Regression protection tests for Baseline_3Sigma strategy integrity.

Verifies behavioral invariants to prevent accidental introduction of:
- Alternative candidate strategies (Candidate A, B, C, D, E, F)
- Learned weights or metric coefficients
- Silence bonuses or penalties
- Unapproved telemetry metrics (e.g. RSSI, meter reads, battery voltage)
- Machine learning models
"""

import datetime as dt
import pandas as pd
import pytest

from nexora.scoring import score_week, METRICS
from nexora.ranking import rank_and_select


def test_metrics_set_strictly_three_approved_signals():
    """Verifies that the production METRICS contract contains strictly the 3 approved signals."""
    expected_metrics = {"offline_duration_sec", "disconnection_cnt", "reboot_cnt"}
    assert set(METRICS) == expected_metrics
    assert len(METRICS) == 3


def test_extraneous_telemetry_columns_ignored():
    """Behavioral test: Extraneous columns (candidate signals, meter reads, RSSI) cannot influence scores."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D000001"

    # Base telemetry
    base_rows = []
    for i in range(20):
        base_rows.append({
            "gateway_id": gid,
            "ts": end - dt.timedelta(days=28 - i),
            "offline_duration_sec": 10.0 + (i % 2) * 2.0,
            "disconnection_cnt": 5.0,
            "reboot_cnt": 1.0,
        })
    recent_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=2),
        "offline_duration_sec": 5000.0,  # 1 breach
        "disconnection_cnt": 5.0,
        "reboot_cnt": 1.0,
    }]

    clean_df = pd.DataFrame(base_rows + recent_rows)
    clean_score = score_week(clean_df, monday)

    # Injected DataFrame with extraneous features and extreme candidate values
    contaminated_df = clean_df.copy()
    contaminated_df["meter_read_success_rate"] = 0.001
    contaminated_df["rssi_dbm"] = -120.0
    contaminated_df["candidate_c_score"] = 99999.0
    contaminated_df["candidate_f_score"] = 88888.0
    contaminated_df["silence_bonus"] = 50.0
    contaminated_df["ml_probability"] = 0.999

    contaminated_score = score_week(contaminated_df, monday)

    pd.testing.assert_frame_equal(clean_score, contaminated_score)


def test_unweighted_individual_breach_accumulation():
    """Behavioral test: Each metric breach contributes exactly 1.0 (no weighting, no composite scaling)."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")

    # Create 3 gateways, each breaching a different single metric
    rows = []
    for idx, metric in enumerate(METRICS):
        gid = f"001A7D00000{idx+1}"
        # Baseline with small variance for that metric
        for i in range(20):
            r = {
                "gateway_id": gid,
                "ts": end - dt.timedelta(days=28 - i),
                "offline_duration_sec": 10.0 + (2.0 if metric == "offline_duration_sec" and i % 2 == 0 else 0.0),
                "disconnection_cnt": 10.0 + (2.0 if metric == "disconnection_cnt" and i % 2 == 0 else 0.0),
                "reboot_cnt": 10.0 + (2.0 if metric == "reboot_cnt" and i % 2 == 0 else 0.0),
            }
            rows.append(r)
        # Recent observation breaching only that metric
        r_rec = {
            "gateway_id": gid,
            "ts": end - dt.timedelta(days=2),
            "offline_duration_sec": 5000.0 if metric == "offline_duration_sec" else 10.0,
            "disconnection_cnt": 5000.0 if metric == "disconnection_cnt" else 10.0,
            "reboot_cnt": 5000.0 if metric == "reboot_cnt" else 10.0,
        }
        rows.append(r_rec)

    scored = score_week(pd.DataFrame(rows), monday)
    assert len(scored) == 3

    # Each single metric breach must have score exactly 1.0 (unweighted)
    for _, row in scored.iterrows():
        assert row["score"] == 1.0, f"Metric breach for {row['worst_metric']} produced non-unitary score {row['score']}"
        assert row["flagged_hours"] == 1


def test_no_silence_bonus_in_ranking():
    """Behavioral test: Silent gateways receive strictly score 0.0, with no artificial bonus."""
    eligible_ids = [f"001A7D0000{i:02X}" for i in range(1, 17)]
    
    # Active gateway with 0 breaches
    active_zero_breaches = pd.DataFrame([{
        "gateway_id": "001A7D000001",
        "score": 0.0,
        "flagged_hours": 0,
        "worst_metric": "",
    }])

    ranked = rank_and_select(active_zero_breaches, eligible_ids, top_k=15)
    
    # All non-scored gateways must have score exactly 0.0
    for _, row in ranked.iterrows():
        assert row["score"] == 0.0
