"""Unit and integration tests for NEXORA 2026 FastAPI service.

Protects requirements:
- /health returns 200 and {'status': 'ok'}
- /predictions/{week_start} returns Top-15 recommendations with exact schema
- Ranks are 1..15 consecutively
- Reasons are non-empty and <=300 chars
- Unsupported weeks are rejected (404) and malformed dates rejected (400)
- /gateways/{gateway_id} validates IDs (400 for malformed, 404 for unknown, 200 for known)
- /run programmatic execution works identically to GET /predictions/{week_start}
- Parity between API response and predict_week(...) output
- API dataset isolation (no auxiliary competition files required)
- Determinism across repeated requests
- OpenAPI documentation endpoints (/docs, /openapi.json)
"""

import datetime as dt
from pathlib import Path
import re
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nexora.api import app, create_app
from nexora.config import SCORED_WEEKS, VISITS_PER_WEEK
from nexora.data_loader import DataLoader
from nexora.pipeline import predict_week

CANONICAL_HEX_REGEX = re.compile(r"^[0-9A-F]{12}$")


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def synthetic_api_env(tmp_path_factory):
    """Sets up a temporary synthetic challenge environment for fast unit testing."""
    tmp_path = tmp_path_factory.mktemp("synthetic_api")
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Master fleet: 20 active gateways
    master_rows = []
    for i in range(1, 21):
        master_rows.append({
            "gateway_id": f"00:1A:7D:00:00:{i:02X}",
            "installed_on": "2025-01-01",
            "decommissioned_on": None,
            "region": "Nord",
        })
    pd.DataFrame(master_rows).to_csv(data_dir / "gateway_master.csv", index=False)

    # Telemetry partition across 2 months
    for month_str in ["2026-01", "2026-02"]:
        m_dir = data_dir / "telemetry" / f"month={month_str}"
        m_dir.mkdir(parents=True)

        rows = []
        start_date = dt.date(2026, 1, 1) if month_str == "2026-01" else dt.date(2026, 2, 1)
        for day in range(25):
            curr_date = start_date + dt.timedelta(days=day)
            for i in range(1, 10):
                gid = f"001A7D0000{i:02X}"
                offline_val = 5000.0 if (i == 1 and month_str == "2026-02" and day == 1) else 10.0
                rows.append({
                    "gateway_id": gid,
                    "ts_utc": f"{curr_date} 12:00:00",
                    "offline_duration_sec": offline_val,
                    "disconnection_cnt": 2.0,
                    "reboot_cnt": 1.0,
                })
        pd.DataFrame(rows).to_parquet(m_dir / "part-0.parquet")

    return data_dir


@pytest.fixture(scope="module")
def synthetic_client(synthetic_api_env):
    """TestClient using the synthetic test environment."""
    test_app = create_app(data_dir=synthetic_api_env)
    with TestClient(test_app) as client:
        yield client


# =============================================================================
# 1 & 2. /health Tests
# =============================================================================

def test_health_endpoint_status_and_body(synthetic_client):
    """GET /health returns HTTP 200 with {'status': 'ok'}."""
    response = synthetic_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# =============================================================================
# 3, 4, 5, 6, 7. /predictions/{week_start} Tests
# =============================================================================

def test_predictions_supported_week_200(synthetic_client):
    """GET /predictions/{week_start} returns 200 for a supported Monday."""
    response = synthetic_client.get("/predictions/2026-02-02")
    assert response.status_code == 200
    data = response.json()

    # Structural checks
    assert data["week_start"] == "2026-02-02"
    assert data["count"] == 15
    assert len(data["predictions"]) == 15


def test_predictions_rank_sequence_and_uniqueness(synthetic_client):
    """Predictions contain consecutive ranks 1..15 and unique gateway IDs."""
    response = synthetic_client.get("/predictions/2026-02-02")
    assert response.status_code == 200
    preds = response.json()["predictions"]

    ranks = [p["rank"] for p in preds]
    assert ranks == list(range(1, 16))

    gateway_ids = [p["gateway_id"] for p in preds]
    assert len(set(gateway_ids)) == 15
    for gid in gateway_ids:
        assert CANONICAL_HEX_REGEX.match(gid) is not None


def test_predictions_reasons_and_scores(synthetic_client):
    """Reasons are non-empty strings <= 300 chars, scores are non-negative floats."""
    response = synthetic_client.get("/predictions/2026-02-02")
    assert response.status_code == 200
    preds = response.json()["predictions"]

    for p in preds:
        assert isinstance(p["score"], (float, int))
        assert p["score"] >= 0.0
        assert isinstance(p["reason"], str)
        assert len(p["reason"].strip()) > 0
        assert len(p["reason"]) <= 300


# =============================================================================
# 8. Date Validation and Error Handling
# =============================================================================

def test_predictions_malformed_date_returns_400(synthetic_client):
    """Malformed date string returns HTTP 400."""
    response = synthetic_client.get("/predictions/invalid-date-format")
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


def test_predictions_unsupported_monday_returns_404(synthetic_client):
    """Valid date that is not one of the 8 scored Mondays returns HTTP 404."""
    response = synthetic_client.get("/predictions/2025-01-05")
    assert response.status_code == 404
    assert "Unsupported week_start" in response.json()["detail"]


# =============================================================================
# 9 & 10. /gateways/{gateway_id} Tests
# =============================================================================

def test_gateway_info_known_asset(synthetic_client):
    """GET /gateways/{gateway_id} returns 200 and factual metadata for a known asset."""
    response = synthetic_client.get("/gateways/001A7D000001")
    assert response.status_code == 200
    data = response.json()
    assert data["gateway_id"] == "001A7D000001"
    assert data["installed_on"] == "2025-01-01"
    assert data["region"] == "Nord"


def test_gateway_info_with_week_start_eligibility(synthetic_client):
    """GET /gateways/{gateway_id}?week_start=2026-02-02 evaluates lifecycle eligibility."""
    response = synthetic_client.get("/gateways/00:1a:7d:00:00:01?week_start=2026-02-02")
    assert response.status_code == 200
    data = response.json()
    assert data["gateway_id"] == "001A7D000001"
    assert data["is_eligible"] is True
    assert data["week_start"] == "2026-02-02"


def test_gateway_info_malformed_id_returns_400(synthetic_client):
    """Malformed gateway identifier returns HTTP 400."""
    response = synthetic_client.get("/gateways/NOT_A_VALID_ID_AT_ALL")
    assert response.status_code == 400
    assert "Malformed gateway ID" in response.json()["detail"]


def test_gateway_info_unknown_id_returns_404(synthetic_client):
    """Well-formed hexadecimal ID not present in master fleet returns HTTP 404."""
    response = synthetic_client.get("/gateways/FFFFFFFFFFFF")
    assert response.status_code == 404
    assert "Unknown gateway ID" in response.json()["detail"]


# =============================================================================
# 9. POST /run Test
# =============================================================================

def test_post_run_delegates_to_prediction_engine(synthetic_client):
    """POST /run executes prediction for a specified Monday with identical response schema."""
    response = synthetic_client.post("/run", json={"week_start": "2026-02-02"})
    assert response.status_code == 200
    data = response.json()
    assert data["week_start"] == "2026-02-02"
    assert data["count"] == 15
    assert len(data["predictions"]) == 15


# =============================================================================
# 11 & 15. API / Pipeline Parity Test
# =============================================================================

def test_api_pipeline_parity(synthetic_api_env, synthetic_client):
    """Verifies bitwise parity between GET /predictions response and direct predict_week call."""
    loader = DataLoader(data_dir=synthetic_api_env)
    master_df = loader.load_master()
    telemetry_df = loader.load_telemetry()

    monday = dt.date(2026, 2, 2)
    expected_df = predict_week(master_df, telemetry_df, monday, top_k=15)

    # API call
    response = synthetic_client.get("/predictions/2026-02-02")
    assert response.status_code == 200
    api_preds = response.json()["predictions"]

    api_df = pd.DataFrame(api_preds)

    # Invariants: exact column equality and row values
    pd.testing.assert_frame_equal(
        expected_df[["week_start", "rank", "gateway_id", "score", "reason"]].reset_index(drop=True),
        api_df[["week_start", "rank", "gateway_id", "score", "reason"]].reset_index(drop=True),
    )


# =============================================================================
# 12 & 17. Dataset Isolation Test
# =============================================================================

def test_api_dataset_isolation(synthetic_api_env, synthetic_client):
    """Confirms API runs cleanly in environment without auxiliary competition files."""
    forbidden = ["field_visits.csv", "meter_read_success.csv", "engineer_review_2026-02.xlsx"]
    for f in forbidden:
        assert not (synthetic_api_env / f).exists()

    resp = synthetic_client.get("/predictions/2026-02-02")
    assert resp.status_code == 200


# =============================================================================
# 13. Determinism Test
# =============================================================================

def test_api_determinism(synthetic_client):
    """Repeated identical API requests return bitwise identical payloads."""
    resp1 = synthetic_client.get("/predictions/2026-02-02")
    resp2 = synthetic_client.get("/predictions/2026-02-02")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


# =============================================================================
# 19. OpenAPI Documentation Registration Test
# =============================================================================

def test_openapi_docs_registered(synthetic_client):
    """FastAPI OpenAPI specification and Swagger UI documentation endpoints are accessible."""
    resp_docs = synthetic_client.get("/docs")
    assert resp_docs.status_code == 200

    resp_openapi = synthetic_client.get("/openapi.json")
    assert resp_openapi.status_code == 200
    schema = resp_openapi.json()
    assert "/health" in schema["paths"]
    assert "/predictions/{week_start}" in schema["paths"]
    assert "/gateways/{gateway_id}" in schema["paths"]
    assert "/run" in schema["paths"]


# =============================================================================
# 16. Real Dataset API Integration Test
# =============================================================================

def test_real_dataset_api_integration():
    """Validates structural correctness of API against the real production challenge dataset."""
    data_dir = Path("data")
    if not data_dir.exists() or not (data_dir / "gateway_master.csv").exists():
        pytest.skip("Real data directory not available")

    real_app = create_app(data_dir=data_dir)
    with TestClient(real_app) as client:
        # 1. Health check
        assert client.get("/health").status_code == 200

        # 2. Week 1 prediction
        resp = client.get("/predictions/2026-02-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 15
        assert len(data["predictions"]) == 15
        assert [p["rank"] for p in data["predictions"]] == list(range(1, 16))

        # 3. Known gateway query
        top_gid = data["predictions"][0]["gateway_id"]
        gw_resp = client.get(f"/gateways/{top_gid}?week_start=2026-02-02")
        assert gw_resp.status_code == 200
        assert gw_resp.json()["gateway_id"] == top_gid
        assert gw_resp.json()["is_eligible"] is True
