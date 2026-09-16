"""Tests for NEXORA Phase 2: Live Evaluation + API Hardening.

Verifies:
1. Dynamic latest competition-week discovery in GET /predictions.
2. Unseen-month live-session addition, reload, recomputation, and deterministic output.
3. Failed reload atomicity: corrupt input keeps old state intact without corruption.
4. Concurrency protection on POST /run via application-level lock.
5. API state isolation across independent create_app() instances.
6. Canonical week validation consistency across all endpoints.
7. Health check endpoint speed and independence.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nexora.api import create_app
from nexora.config import SCORED_WEEKS, VISITS_PER_WEEK
from nexora.strategy import Baseline3SigmaStrategy, PredictionStrategy


class DummyTestStrategy:
    """Minimal dummy strategy for state isolation testing."""
    @property
    def name(self) -> str:
        return "DummyTestStrategy"

    def predict(self, master_df, telemetry_df, decision_monday, top_k=VISITS_PER_WEEK):
        return pd.DataFrame()


@pytest.fixture
def live_eval_env(tmp_path):
    """Creates a temporary synthetic challenge environment with initial March 2026 data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)

    # 20 active gateways in master
    master_rows = [
        {
            "gateway_id": f"00:1A:7D:00:00:{i:02X}",
            "installed_on": "2025-01-01",
            "decommissioned_on": None,
            "region": "Nord",
        }
        for i in range(1, 21)
    ]
    pd.DataFrame(master_rows).to_csv(data_dir / "gateway_master.csv", index=False)

    # Initial telemetry: March 2026 partition (2026-03-01 to 2026-03-22)
    m3_dir = data_dir / "telemetry" / "month=2026-03"
    m3_dir.mkdir(parents=True)
    rows = []
    start_date = dt.date(2026, 3, 1)
    for day in range(22):
        curr_date = start_date + dt.timedelta(days=day)
        for i in range(1, 21):
            gid = f"001A7D0000{i:02X}"
            offline_val = 6000.0 if (i == 1 and day == 10) else 15.0
            rows.append({
                "gateway_id": gid,
                "ts_utc": f"{curr_date} 12:00:00",
                "offline_duration_sec": offline_val,
                "disconnection_cnt": 2.0,
                "reboot_cnt": 1.0,
            })
    pd.DataFrame(rows).to_parquet(m3_dir / "part-0.parquet")
    return data_dir


def test_unseen_month_live_session_workflow(live_eval_env):
    """Simulates live challenge session: load initial data, add unseen month, reload and predict."""
    # STEP 1 & 2: Start application
    app = create_app(data_dir=live_eval_env)
    with TestClient(app) as client:
        # STEP 3: Verify initial latest prediction week
        resp_initial = client.get("/predictions")
        assert resp_initial.status_code == 200
        initial_data = resp_initial.json()
        assert initial_data["week_start"] == "2026-03-23"
        assert initial_data["count"] == 15

        # STEP 4: Add new unseen month partition (month=2026-04)
        m4_dir = live_eval_env / "telemetry" / "month=2026-04"
        m4_dir.mkdir(parents=True)
        new_rows = []
        start_date = dt.date(2026, 4, 1)
        for day in range(26):  # up through 2026-04-26 (Sunday)
            curr_date = start_date + dt.timedelta(days=day)
            for i in range(1, 21):
                gid = f"001A7D0000{i:02X}"
                offline_val = 8000.0 if (i == 3 and day == 5) else 20.0
                new_rows.append({
                    "gateway_id": gid,
                    "ts_utc": f"{curr_date} 12:00:00",
                    "offline_duration_sec": offline_val,
                    "disconnection_cnt": 3.0,
                    "reboot_cnt": 2.0,
                })
        pd.DataFrame(new_rows).to_parquet(m4_dir / "part-0.parquet")

        # STEP 5: POST /run for new Monday (2026-04-27)
        resp_run = client.post("/run", json={"week_start": "2026-04-27"})
        assert resp_run.status_code == 200, resp_run.text
        run_data = resp_run.json()

        # STEP 6: Verify result structure
        assert run_data["week_start"] == "2026-04-27"
        assert run_data["count"] == 15
        assert len(run_data["predictions"]) == 15

        # STEP 7: Dynamic latest discovery now reflects the unseen April week
        resp_latest = client.get("/predictions")
        assert resp_latest.status_code == 200
        assert resp_latest.json()["week_start"] == "2026-04-27"

        # STEP 8: Exactly 15 valid ranked gateways with unique IDs
        preds = run_data["predictions"]
        gateway_ids = [p["gateway_id"] for p in preds]
        assert len(set(gateway_ids)) == 15, "Gateway recommendations must be unique"
        ranks = [p["rank"] for p in preds]
        assert ranks == list(range(1, 16)), "Ranks must be strictly 1 through 15"
        for p in preds:
            assert len(p["gateway_id"]) == 12
            assert p["score"] >= 0.0
            assert len(p["reason"]) > 0

        # STEP 9: Verify deterministic output
        resp_again = client.get("/predictions/2026-04-27")
        assert resp_again.status_code == 200
        assert resp_again.json() == run_data


def test_failed_reload_preserves_old_valid_state(live_eval_env):
    """Proves atomic state replacement: corrupted input during POST /run preserves previous state."""
    app = create_app(data_dir=live_eval_env)
    with TestClient(app) as client:
        # Initial valid query
        resp_before = client.get("/predictions/2026-03-23")
        assert resp_before.status_code == 200
        orig_data = resp_before.json()
        assert orig_data["count"] == 15

        # Deliberately corrupt master data
        master_file = live_eval_env / "gateway_master.csv"
        valid_master_content = master_file.read_text()
        master_file.write_text("corrupted,header,without,required,gateway_id\n1,2,3,4,5\n")

        # POST /run should fail
        resp_fail = client.post("/run", json={"week_start": "2026-03-23"})
        assert resp_fail.status_code == 500
        assert "Data reload" in resp_fail.json()["detail"] or "Invalid master data" in resp_fail.json()["detail"]

        # CRITICAL ASSERTION: Previous valid state is still intact and accessible!
        resp_after = client.get("/predictions/2026-03-23")
        assert resp_after.status_code == 200
        assert resp_after.json() == orig_data, "Application state must not be corrupted by failed reload"

        # Health endpoint remains fast and healthy
        assert client.get("/health").status_code == 200

        # Restore valid master data
        master_file.write_text(valid_master_content)

        # POST /run now succeeds and state is refreshed
        resp_recover = client.post("/run", json={"week_start": "2026-03-23"})
        assert resp_recover.status_code == 200
        assert resp_recover.json()["count"] == 15


def test_concurrent_run_protection(live_eval_env):
    """Verifies that simultaneous POST /run calls are safely serialized by app.state.run_lock."""
    app = create_app(data_dir=live_eval_env)
    assert hasattr(app.state, "run_lock")

    with TestClient(app) as client:
        def invoke_run(week: str):
            return client.post("/run", json={"week_start": week})

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(invoke_run, "2026-03-23")
            future2 = executor.submit(invoke_run, "2026-03-23")
            res1 = future1.result()
            res2 = future2.result()

        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["count"] == 15
        assert res2.json()["count"] == 15


def test_api_state_isolation(live_eval_env):
    """Multiple application instances must not share mutable PredictionService state."""
    app1 = create_app(data_dir=live_eval_env)
    app2 = create_app(data_dir=live_eval_env)

    # State objects are distinct instances
    assert app1.state.prediction_service is not app2.state.prediction_service

    # Mutating app1 strategy does not affect app2
    app1.state.prediction_service.strategy = DummyTestStrategy()
    assert app1.state.prediction_service.strategy.name == "DummyTestStrategy"
    assert app2.state.prediction_service.strategy.name == "Baseline_3Sigma"


def test_canonical_week_validation_consistency(live_eval_env):
    """Endpoints accept and reject week_start parameters consistently."""
    app = create_app(data_dir=live_eval_env)
    with TestClient(app) as client:
        # Non-Monday Tuesday (2026-02-03)
        resp_pred = client.get("/predictions/2026-02-03")
        assert resp_pred.status_code == 404
        assert "Must be a Monday" in resp_pred.json()["detail"]

        resp_gw = client.get("/gateways/001A7D000001?week_start=2026-02-03")
        assert resp_gw.status_code == 404
        assert "Must be a Monday" in resp_gw.json()["detail"]

        resp_run = client.post("/run", json={"week_start": "2026-02-03"})
        assert resp_run.status_code == 404
        assert "Must be a Monday" in resp_run.json()["detail"]

        # Malformed date strings return HTTP 400 across endpoints
        assert client.get("/predictions/not-a-date").status_code == 400
        assert client.get("/gateways/001A7D000001?week_start=not-a-date").status_code == 400
        assert client.post("/run", json={"week_start": "not-a-date"}).status_code == 400


def test_health_endpoint_is_fast_and_independent(live_eval_env):
    """GET /health responds immediately with 200 without expensive pipeline execution."""
    app = create_app(data_dir=live_eval_env)
    with TestClient(app) as client:
        t0 = dt.datetime.now()
        response = client.get("/health")
        duration = (dt.datetime.now() - t0).total_seconds()
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert duration < 0.2, f"Health check took too long: {duration:.3f}s"
