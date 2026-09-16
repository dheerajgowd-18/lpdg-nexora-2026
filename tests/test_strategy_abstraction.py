"""Tests for swappable prediction strategy abstraction (Area B requirement).

Verifies:
1. Baseline3SigmaStrategy produces identical output to authoritative scoring/ranking.
2. PredictionService executes cleanly through the PredictionStrategy protocol.
3. The API uses PredictionService and can swap strategies without touching API code.
4. A fake/synthetic strategy can be injected into the API and changes the ranking dynamically.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nexora.strategy import (
    PredictionStrategy,
    Baseline3SigmaStrategy,
    PredictionService,
    default_prediction_service,
)
from nexora.pipeline import predict_week
from nexora.api import create_app
from nexora.config import REQUIRED_PREDICTION_COLUMNS, VISITS_PER_WEEK


class SyntheticFakeStrategy:
    """Deliberately simple test strategy returning deterministic synthetic predictions.

    Used ONLY in tests to verify API decoupling.
    """

    @property
    def name(self) -> str:
        return "SyntheticFakeStrategy"

    def predict(
        self,
        master_df: pd.DataFrame,
        telemetry_df: pd.DataFrame,
        decision_monday: dt.date | dt.datetime | str,
        top_k: int = VISITS_PER_WEEK,
    ) -> pd.DataFrame:
        t_str = decision_monday.isoformat() if isinstance(decision_monday, (dt.date, dt.datetime)) else str(decision_monday)
        rows = []
        for i in range(1, top_k + 1):
            rows.append({
                "week_start": t_str,
                "rank": i,
                "gateway_id": f"0080E1{i:06X}",
                "score": float(1000 - i),
                "reason": f"Synthetic test reason for priority asset {i}",
            })
        df = pd.DataFrame(rows)[REQUIRED_PREDICTION_COLUMNS]
        assert len(set(df["gateway_id"])) == top_k, "Synthetic strategy must generate unique gateway IDs"
        return df


@pytest.fixture
def sample_master_telemetry():
    """Minimal valid synthetic master and telemetry frames."""
    master = pd.DataFrame([
        {"gateway_id": f"0080000000{i:02d}", "installed_on": "2025-01-01", "decommissioned_on": None, "region": "North"}
        for i in range(1, 25)
    ])
    now = pd.Timestamp("2026-02-01 12:00:00", tz="UTC")
    telemetry = pd.DataFrame([
        {
            "gateway_id": f"0080000000{i:02d}",
            "ts": now - dt.timedelta(hours=h),
            "offline_duration_sec": 100.0,
            "disconnection_cnt": 1,
            "reboot_cnt": 0,
        }
        for i in range(1, 25)
        for h in range(1, 30)
    ])
    return master, telemetry


@pytest.fixture
def minimal_api_data_dir(tmp_path):
    """Sets up minimal files required by DataLoader for API lifespan initialization."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    master_rows = [
        {"gateway_id": f"00:80:00:00:00:{i:02X}", "installed_on": "2025-01-01", "decommissioned_on": None, "region": "North"}
        for i in range(1, 20)
    ]
    pd.DataFrame(master_rows).to_csv(data_dir / "gateway_master.csv", index=False)

    part_dir = data_dir / "telemetry" / "month=2026-01"
    part_dir.mkdir(parents=True, exist_ok=True)
    telem_rows = [
        {
            "gateway_id": f"0080000000{i:02X}",
            "ts_utc": "2026-01-15 12:00:00",
            "offline_duration_sec": 10.0,
            "disconnection_cnt": 0,
            "reboot_cnt": 0,
        }
        for i in range(1, 20)
    ]
    pd.DataFrame(telem_rows).to_parquet(part_dir / "part-0.parquet")
    return data_dir


def test_baseline3sigma_implements_protocol():
    """Baseline3SigmaStrategy must implement the PredictionStrategy runtime protocol."""
    strat = Baseline3SigmaStrategy()
    assert isinstance(strat, PredictionStrategy)
    assert strat.name == "Baseline_3Sigma"


def test_baseline3sigma_strategy_matches_predict_week(sample_master_telemetry):
    """Baseline3SigmaStrategy.predict() must produce exact same result as predict_week()."""
    master_df, telemetry_df = sample_master_telemetry
    monday = "2026-02-02"

    df_direct = predict_week(master_df, telemetry_df, monday)
    df_strategy = Baseline3SigmaStrategy().predict(master_df, telemetry_df, monday)

    pd.testing.assert_frame_equal(df_direct, df_strategy)


def test_prediction_service_delegation(sample_master_telemetry):
    """PredictionService delegates execution through the strategy abstraction."""
    master_df, telemetry_df = sample_master_telemetry
    monday = "2026-02-02"

    svc = PredictionService()
    assert svc.strategy.name == "Baseline_3Sigma"

    res = svc.predict(master_df, telemetry_df, monday)
    assert len(res) == 15
    assert list(res.columns) == REQUIRED_PREDICTION_COLUMNS


def test_prediction_service_strategy_setter():
    """PredictionService allows dynamic strategy swapping and validates types."""
    svc = PredictionService()
    fake = SyntheticFakeStrategy()

    svc.strategy = fake
    assert svc.strategy.name == "SyntheticFakeStrategy"

    with pytest.raises(TypeError, match="must implement PredictionStrategy"):
        svc.strategy = "not_a_strategy"  # type: ignore


def test_predict_week_accepts_custom_strategy(sample_master_telemetry):
    """predict_week() accepts an optional strategy override."""
    master_df, telemetry_df = sample_master_telemetry
    monday = "2026-02-02"

    fake = SyntheticFakeStrategy()
    res = predict_week(master_df, telemetry_df, monday, strategy=fake)

    assert len(res) == 15
    assert res.iloc[0]["gateway_id"].startswith("0080E1")
    assert res.iloc[0]["score"] == 999.0
    assert "Synthetic test reason" in res.iloc[0]["reason"]


def test_api_with_swapped_strategy(minimal_api_data_dir):
    """The API can swap out ranking strategies without changing API endpoint code."""
    fake_strategy = SyntheticFakeStrategy()
    app = create_app(data_dir=minimal_api_data_dir, strategy=fake_strategy)

    with TestClient(app) as client:
        response = client.get("/predictions/2026-02-02")
        assert response.status_code == 200

        data = response.json()
        assert data["week_start"] == "2026-02-02"
        assert data["count"] == 15
        first_pred = data["predictions"][0]
        assert first_pred["score"] == 999.0
        assert "Synthetic test reason" in first_pred["reason"]
        assert len({p["gateway_id"] for p in data["predictions"]}) == 15


def test_api_dynamic_strategy_swap_at_runtime(minimal_api_data_dir):
    """Demonstrates swapping active strategy on a running API service instance."""
    app = create_app(data_dir=minimal_api_data_dir)

    with TestClient(app) as client:
        # Initial default is Baseline_3Sigma
        assert app.state.prediction_service.strategy.name == "Baseline_3Sigma"

        # Dynamically hot-swap to fake strategy
        app.state.prediction_service.strategy = SyntheticFakeStrategy()
        assert app.state.prediction_service.strategy.name == "SyntheticFakeStrategy"

        # API queries immediately reflect swapped strategy behavior
        response = client.get("/predictions/2026-02-02")
        assert response.status_code == 200
        data = response.json()
        assert data["predictions"][0]["score"] == 999.0
        assert "Synthetic test reason" in data["predictions"][0]["reason"]
        assert len({p["gateway_id"] for p in data["predictions"]}) == 15
