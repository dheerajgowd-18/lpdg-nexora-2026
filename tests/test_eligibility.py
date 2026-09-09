"""Unit tests for lifecycle fleet eligibility under the frozen production contract."""

import datetime as dt
import pandas as pd
import pytest

from nexora.eligibility import get_eligible_gateways


@pytest.fixture
def master_fleet():
    """Synthetic master fleet with comprehensive lifecycle boundary cases."""
    return pd.DataFrame({
        "gateway_id": [
            "001A7D000001",  # 1. installed before T, decommissioned is null -> ELIGIBLE
            "001A7D000002",  # 2. installed exactly on T, decommissioned is null -> ELIGIBLE
            "001A7D000003",  # 3. installed after T -> INELIGIBLE
            "001A7D000004",  # 4. installed before T, decommissioned before T -> INELIGIBLE
            "001A7D000005",  # 5. installed before T, decommissioned exactly on T -> INELIGIBLE
            "001A7D000006",  # 6. installed before T, decommissioned after T -> ELIGIBLE
            "001A7D000007",  # 7. installed before T, decommissioned is NaT / None -> ELIGIBLE
            "001A7D000008",  # 8. installed before T, active (zero telemetry asset) -> ELIGIBLE
        ],
        "installed_on": [
            "2025-01-01",  # before T
            "2026-02-02",  # on T
            "2026-02-03",  # after T
            "2025-01-01",  # before T
            "2025-01-01",  # before T
            "2025-01-01",  # before T
            "2025-01-01",  # before T
            "2025-01-01",  # before T
        ],
        "decommissioned_on": [
            None,          # null
            None,          # null
            None,          # null
            "2026-01-31",  # decommissioned < T
            "2026-02-02",  # decommissioned == T
            "2026-02-03",  # decommissioned > T
            pd.NaT,        # explicitly NaT
            None,          # null (no telemetry ever recorded)
        ],
    })


def test_installed_before_t_eligible(master_fleet):
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert "001A7D000001" in eligible


def test_installed_exactly_on_t_eligible(master_fleet):
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert "001A7D000002" in eligible


def test_installed_after_t_ineligible(master_fleet):
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert "001A7D000003" not in eligible


def test_decommissioned_before_t_ineligible(master_fleet):
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert "001A7D000004" not in eligible


def test_decommissioned_exactly_on_t_ineligible(master_fleet):
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert "001A7D000005" not in eligible


def test_decommissioned_after_t_eligible(master_fleet):
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert "001A7D000006" in eligible


def test_null_decommission_date_eligible(master_fleet):
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert "001A7D000007" in eligible


def test_telemetry_absence_does_not_affect_eligibility(master_fleet):
    """Assets with zero telemetry remain lifecycle-eligible if installation criteria hold."""
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert "001A7D000008" in eligible


def test_eligible_deterministic_sorting(master_fleet):
    t_monday = dt.date(2026, 2, 2)
    eligible = get_eligible_gateways(master_fleet, t_monday)
    assert eligible == sorted(eligible)


def test_date_types_accepted(master_fleet):
    """Eligibility function handles dt.date, dt.datetime, and ISO-format strings."""
    date_res = get_eligible_gateways(master_fleet, dt.date(2026, 2, 2))
    datetime_res = get_eligible_gateways(master_fleet, dt.datetime(2026, 2, 2, 0, 0, 0))
    str_res = get_eligible_gateways(master_fleet, "2026-02-02")

    assert date_res == datetime_res == str_res
