"""Unit tests for Baseline_3Sigma scoring formulation and temporal boundary invariants.

Protects frozen requirements:
- Baseline window: [T-28d, T)
- Recent evaluation window: [T-7d, T)
- Monitored metrics: offline_duration_sec, disconnection_cnt, reboot_cnt
- Sample standard deviation (ddof=1)
- Strict inequality breach condition: x > mean + 3 * std
- Zero std -> NaN -> 0 breaches
- Insufficient baseline observations (N=1) -> NaN std -> 0 breaches
- Individual metric breach accumulation: 0, 1, 2, or 3 per observation
- Strict right-open pre-T cutoff (anti-leakage)
"""

import datetime as dt
import numpy as np
import pandas as pd
import pytest

from nexora.scoring import score_week, METRICS, BASELINE_DAYS, RECENT_DAYS, SIGMA


def _build_baseline_series(end_ts, gateway_id, n_days=50, base_val=10.0, step=2.0):
    """Helper to generate baseline telemetry with known mean and stable std."""
    rows = []
    for i in range(n_days):
        # Distribute timestamps across [T-28d, T-7d)
        offset_hours = 28 * 24 - 10 - i * 8
        ts = end_ts - dt.timedelta(hours=offset_hours)
        val = base_val + (i % 3) * step
        rows.append({
            "gateway_id": gateway_id,
            "ts": ts,
            "offline_duration_sec": val,
            "disconnection_cnt": val,
            "reboot_cnt": val,
        })
    return rows


# =============================================================================
# A. No breaches -> Expected score = 0
# =============================================================================

def test_case_a_no_breaches():
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000A"

    base_rows = _build_baseline_series(end, gid, n_days=50, base_val=10.0, step=2.0)
    # Recent observation has values near the mean (no breaches)
    recent_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=3),
        "offline_duration_sec": 10.0,
        "disconnection_cnt": 10.0,
        "reboot_cnt": 10.0,
    }]

    scored = score_week(pd.DataFrame(base_rows + recent_rows), monday)
    assert len(scored) == 1
    assert scored.iloc[0]["score"] == 0.0
    assert scored.iloc[0]["flagged_hours"] == 0


# =============================================================================
# B. One metric breach -> Expected score = 1
# =============================================================================

def test_case_b_one_metric_breach():
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000B"

    base_rows = _build_baseline_series(end, gid, n_days=50, base_val=10.0, step=2.0)
    # Only offline_duration_sec breaches
    recent_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=3),
        "offline_duration_sec": 5000.0,  # breach
        "disconnection_cnt": 10.0,      # normal
        "reboot_cnt": 10.0,             # normal
    }]

    scored = score_week(pd.DataFrame(base_rows + recent_rows), monday)
    assert len(scored) == 1
    row = scored.iloc[0]
    assert row["score"] == 1.0
    assert row["flagged_hours"] == 1
    assert row["worst_metric"] == "offline_duration_sec"


# =============================================================================
# C. Two metrics breached in one observation -> Expected score = 2
# =============================================================================

def test_case_c_two_metrics_breached_in_one_observation():
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000C"

    base_rows = _build_baseline_series(end, gid, n_days=50, base_val=10.0, step=2.0)
    # offline_duration_sec and disconnection_cnt breach, reboot_cnt normal
    recent_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=3),
        "offline_duration_sec": 5000.0,  # breach 1
        "disconnection_cnt": 5000.0,    # breach 2
        "reboot_cnt": 10.0,             # normal
    }]

    scored = score_week(pd.DataFrame(base_rows + recent_rows), monday)
    assert len(scored) == 1
    row = scored.iloc[0]
    assert row["score"] == 2.0
    assert row["flagged_hours"] == 2


# =============================================================================
# D. Three metrics breached in one observation -> Expected score = 3
# =============================================================================

def test_case_d_three_metrics_breached_in_one_observation():
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000D"

    base_rows = _build_baseline_series(end, gid, n_days=50, base_val=10.0, step=2.0)
    # All 3 metrics breach
    recent_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=3),
        "offline_duration_sec": 5000.0,  # breach 1
        "disconnection_cnt": 5000.0,    # breach 2
        "reboot_cnt": 5000.0,           # breach 3
    }]

    scored = score_week(pd.DataFrame(base_rows + recent_rows), monday)
    assert len(scored) == 1
    row = scored.iloc[0]
    assert row["score"] == 3.0
    assert row["flagged_hours"] == 3


# =============================================================================
# E. Multiple observations with breaches -> Accumulation
# =============================================================================

def test_case_e_multiple_observations_breach_accumulation():
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000E"

    # Use 100 baseline rows so baseline sample stats are stable
    base_rows = []
    for i in range(100):
        ts = end - dt.timedelta(hours=28 * 24 - 10 - i * 4)
        val = 10.0 + (i % 2) * 2.0
        base_rows.append({
            "gateway_id": gid,
            "ts": ts,
            "offline_duration_sec": val,
            "disconnection_cnt": val,
            "reboot_cnt": val,
        })

    # Obs 1: 1 breach (offline)
    # Obs 2: 2 breaches (offline, disconnection)
    # Obs 3: 3 breaches (offline, disconnection, reboot)
    # Total = 1 + 2 + 3 = 6
    recent_rows = [
        {
            "gateway_id": gid,
            "ts": end - dt.timedelta(days=5),
            "offline_duration_sec": 5000.0,
            "disconnection_cnt": 10.0,
            "reboot_cnt": 10.0,
        },
        {
            "gateway_id": gid,
            "ts": end - dt.timedelta(days=3),
            "offline_duration_sec": 5000.0,
            "disconnection_cnt": 5000.0,
            "reboot_cnt": 10.0,
        },
        {
            "gateway_id": gid,
            "ts": end - dt.timedelta(days=1),
            "offline_duration_sec": 5000.0,
            "disconnection_cnt": 5000.0,
            "reboot_cnt": 5000.0,
        },
    ]

    scored = score_week(pd.DataFrame(base_rows + recent_rows), monday)
    assert len(scored) == 1
    row = scored.iloc[0]
    assert row["score"] == 6.0
    assert row["flagged_hours"] == 6


# =============================================================================
# F & G. Strict threshold behavior: equal or below is NOT a breach, strictly greater is
# =============================================================================

def test_case_f_and_g_strict_threshold():
    """Verifies that x <= mean + 3*std is NOT a breach, while x > mean + 3*std IS a breach."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")

    # Construct window with 18 zeros, 1 value of 2.0 in [T-28d, T-7d), and 1 recent value in [T-7d, T)
    # Mathematical boundary: with base = [0.0]*18 + [2.0],
    # the exact threshold where (val - m) == 3.0 * s is approx 2.0969663
    base_rows = [
        {
            "gateway_id": "001A7D00000F",
            "ts": end - dt.timedelta(days=28 - i),
            "offline_duration_sec": 0.0 if i < 18 else 2.0,
            "disconnection_cnt": 0.0,
            "reboot_cnt": 0.0,
        }
        for i in range(19)
    ]

    # Below / on threshold: val = 2.095 -> (val - m) <= 3.0 * s -> NOT a breach
    recent_not_breach = [{
        "gateway_id": "001A7D00000F",
        "ts": end - dt.timedelta(days=2),
        "offline_duration_sec": 2.095,
        "disconnection_cnt": 0.0,
        "reboot_cnt": 0.0,
    }]
    scored_not = score_week(pd.DataFrame(base_rows + recent_not_breach), monday)
    assert scored_not.iloc[0]["score"] == 0.0

    # Strictly greater than threshold: val = 2.150 -> (val - m) > 3.0 * s -> BREACH
    base_rows_g = [
        {
            "gateway_id": "001A7D00000G",
            "ts": end - dt.timedelta(days=28 - i),
            "offline_duration_sec": 0.0 if i < 18 else 2.0,
            "disconnection_cnt": 0.0,
            "reboot_cnt": 0.0,
        }
        for i in range(19)
    ]
    recent_breach = [{
        "gateway_id": "001A7D00000G",
        "ts": end - dt.timedelta(days=2),
        "offline_duration_sec": 2.150,
        "disconnection_cnt": 0.0,
        "reboot_cnt": 0.0,
    }]
    scored_breach = score_week(pd.DataFrame(base_rows_g + recent_breach), monday)
    assert scored_breach.iloc[0]["score"] == 1.0


# =============================================================================
# H. std == 0 -> Zero breaches
# =============================================================================

def test_case_h_zero_variance_std_zero():
    """When baseline observations have zero variance, std is 0.0 -> NaN -> 0 breaches."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000H"

    # All observations across [T-28d, T) have identical constant value 10.0
    all_rows = [
        {
            "gateway_id": gid,
            "ts": end - dt.timedelta(days=25 - i),
            "offline_duration_sec": 10.0,
            "disconnection_cnt": 10.0,
            "reboot_cnt": 10.0,
        }
        for i in range(20)
    ]

    scored = score_week(pd.DataFrame(all_rows), monday)
    assert len(scored) == 1
    # Constant baseline gives std=0, replaced with NaN, yielding score=0.0
    assert scored.iloc[0]["score"] == 0.0
    assert scored.iloc[0]["flagged_hours"] == 0


# =============================================================================
# I. N=1 baseline observation -> Zero breaches
# =============================================================================

def test_case_i_single_baseline_observation():
    """With N=1 baseline observation, sample std (ddof=1) is NaN, yielding 0 breaches."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000I"

    base_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=15),
        "offline_duration_sec": 10.0,
        "disconnection_cnt": 10.0,
        "reboot_cnt": 10.0,
    }]
    recent_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=2),
        "offline_duration_sec": 99999.0,
        "disconnection_cnt": 99999.0,
        "reboot_cnt": 99999.0,
    }]

    scored = score_week(pd.DataFrame(base_rows + recent_rows), monday)
    assert len(scored) == 1
    assert scored.iloc[0]["score"] == 0.0


# =============================================================================
# J. No recent telemetry -> Omitted by scoring layer
# =============================================================================

def test_case_j_no_recent_telemetry():
    """Gateways with telemetry in [T-28d, T-7d) but none in [T-7d, T) are omitted by scoring."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000J"

    base_rows = [
        {
            "gateway_id": gid,
            "ts": end - dt.timedelta(days=20 - i),
            "offline_duration_sec": 10.0,
            "disconnection_cnt": 10.0,
            "reboot_cnt": 10.0,
        }
        for i in range(10)
    ]
    # No rows in [T-7d, T)
    scored = score_week(pd.DataFrame(base_rows), monday)
    assert gid not in set(scored["gateway_id"]) if not scored.empty else True


# =============================================================================
# K, L, M. Window Boundary Invariants: T, T-28d, T-7d
# =============================================================================

def test_case_k_boundary_t_strictly_excluded():
    """Telemetry exactly at T must NOT participate."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000K"

    base_rows = _build_baseline_series(end, gid, n_days=50, base_val=10.0, step=2.0)
    # Telemetry timestamp EXACTLY at end (T): must be excluded
    boundary_t_row = [{
        "gateway_id": gid,
        "ts": end,
        "offline_duration_sec": 99999.0,
        "disconnection_cnt": 99999.0,
        "reboot_cnt": 99999.0,
    }]

    scored = score_week(pd.DataFrame(base_rows + boundary_t_row), monday)
    # Because recent window has no participating observations (< T), score must be 0
    if not scored.empty:
        assert scored.iloc[0]["score"] == 0.0


def test_case_l_boundary_t_minus_28d_included():
    """Telemetry timestamp exactly at T - 28d MUST participate in baseline window.

    Mathematical verification via Samuelson's inequality:
    In any sample of size N, max z-score is (N-1)/sqrt(N).
    For N=10, max z-score is 2.846 < 3.0 (breach is mathematically impossible).
    For N=11, max z-score is 3.015 > 3.0 (breach is possible).
    Therefore, with 10 zero observations plus 1 recent observation:
    If the observation at T-28d participates, N=11 -> breach occurs (score=1).
    If the observation at T-28d were excluded, N=10 -> score must be 0.
    """
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000L"

    # Exactly at T - 28d
    t_28d = end - dt.timedelta(days=28)
    row_at_28d = {
        "gateway_id": gid,
        "ts": t_28d,
        "offline_duration_sec": 0.0,
        "disconnection_cnt": 0.0,
        "reboot_cnt": 0.0,
    }
    # 9 other baseline rows with value 0.0
    other_base = [
        {
            "gateway_id": gid,
            "ts": end - dt.timedelta(days=20 - i),
            "offline_duration_sec": 0.0,
            "disconnection_cnt": 0.0,
            "reboot_cnt": 0.0,
        }
        for i in range(9)
    ]
    # 1 recent observation with extreme value
    recent_row = {
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=3),
        "offline_duration_sec": 1000.0,
        "disconnection_cnt": 0.0,
        "reboot_cnt": 0.0,
    }

    # Total observations = 1 (at T-28d) + 9 (other baseline) + 1 (recent) = 11 rows
    scored = score_week(pd.DataFrame([row_at_28d] + other_base + [recent_row]), monday)
    assert len(scored) == 1
    # Because row_at_28d is included, N=11, z-score is 3.015 > 3.0 -> score = 1.0!
    assert scored.iloc[0]["score"] == 1.0


def test_case_m_boundary_t_minus_7d_included():
    """Telemetry timestamp exactly at T - 7d MUST participate in recent window."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000M"

    base_rows = _build_baseline_series(end, gid, n_days=50, base_val=10.0, step=2.0)
    # Exactly at T - 7d
    t_7d = end - dt.timedelta(days=7)
    recent_at_7d = [{
        "gateway_id": gid,
        "ts": t_7d,
        "offline_duration_sec": 5000.0,
        "disconnection_cnt": 10.0,
        "reboot_cnt": 10.0,
    }]

    scored = score_week(pd.DataFrame(base_rows + recent_at_7d), monday)
    assert len(scored) == 1
    assert scored.iloc[0]["score"] == 1.0


# =============================================================================
# N. Future Injection Test: Temporal Leakage Resistance
# =============================================================================

def test_case_n_future_telemetry_injection_leakage_safe():
    """Injecting extreme telemetry at T + 1 hour must NOT alter scoring or ranking."""
    monday = dt.date(2026, 2, 2)
    end = pd.Timestamp(monday, tz="UTC")
    gid = "001A7D00000N"

    base_rows = _build_baseline_series(end, gid, n_days=50, base_val=10.0, step=2.0)
    recent_rows = [{
        "gateway_id": gid,
        "ts": end - dt.timedelta(days=3),
        "offline_duration_sec": 5000.0,
        "disconnection_cnt": 10.0,
        "reboot_cnt": 10.0,
    }]
    clean_df = pd.DataFrame(base_rows + recent_rows)
    clean_score = score_week(clean_df, monday)

    # Injected future observation at T + 1 hour with catastrophic values
    future_rows = [{
        "gateway_id": gid,
        "ts": end + dt.timedelta(hours=1),
        "offline_duration_sec": 999999.0,
        "disconnection_cnt": 999999.0,
        "reboot_cnt": 999999.0,
    }]
    contaminated_df = pd.DataFrame(base_rows + recent_rows + future_rows)
    contaminated_score = score_week(contaminated_df, monday)

    pd.testing.assert_frame_equal(clean_score, contaminated_score)
