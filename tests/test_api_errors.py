"""Unit tests for FastAPI error handling, status codes, and edge-case request scenarios.

Verifies:
- 400 Bad Request on malformed dates (empty, non-date text, out-of-bounds)
- 404 Not Found on un-scored competition dates
- 400 Bad Request on malformed gateway IDs (invalid characters, bad length)
- 404 Not Found on unknown gateway IDs
- 422 Unprocessable Entity on schema violations in POST /run
- 405 Method Not Allowed on invalid HTTP verbs
- Error responses do not leak internal filesystem paths or python tracebacks
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nexora.api import create_app


@pytest.fixture(scope="module")
def api_error_client(tmp_path_factory):
    """Sets up a minimal isolated synthetic API client for error testing."""
    tmp_path = tmp_path_factory.mktemp("api_errors")
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # 16 gateways in master
    master_rows = []
    for i in range(1, 17):
        master_rows.append({
            "gateway_id": f"00:1A:7D:00:00:{i:02X}",
            "installed_on": "2025-01-01",
            "decommissioned_on": None,
            "region": "Nord",
        })
    pd.DataFrame(master_rows).to_csv(data_dir / "gateway_master.csv", index=False)

    # Empty telemetry partition
    t_dir = data_dir / "telemetry" / "month=2026-02"
    t_dir.mkdir(parents=True)
    pd.DataFrame(columns=[
        "gateway_id", "ts_utc", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"
    ]).to_parquet(t_dir / "part-0.parquet")

    test_app = create_app(data_dir=data_dir)
    with TestClient(test_app) as client:
        yield client


# =============================================================================
# 1. Date & Calendar Error Handling
# =============================================================================

@pytest.mark.parametrize("bad_date", [
    "invalid-date",
    "2026-02-31",
    "2026_02_02",
    "2026-2-2",
    "02-02-2026",
    " ",
])
def test_predictions_malformed_dates_return_400(api_error_client, bad_date):
    """GET /predictions/{week_start} returns HTTP 400 for non-ISO or invalid dates."""
    response = api_error_client.get(f"/predictions/{bad_date}")
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


@pytest.mark.parametrize("unscored_date", [
    "2025-01-05",  # 2025 date
    "2026-01-26",  # Monday before competition
    "2026-02-03",  # Tuesday
    "2026-03-30",  # Monday after competition
])
def test_predictions_unsupported_dates_return_404(api_error_client, unscored_date):
    """GET /predictions/{week_start} returns HTTP 404 for dates outside 8 competition Mondays."""
    response = api_error_client.get(f"/predictions/{unscored_date}")
    assert response.status_code == 404
    assert "Unsupported week_start" in response.json()["detail"]


# =============================================================================
# 2. Gateway ID Error Handling
# =============================================================================

@pytest.mark.parametrize("bad_id", [
    "SHORT",
    "0639EA5602C1X",        # 13 chars
    "0639EA5602CG",         # Non-hex G
    "06:39:EA:56:02",       # 5 octets
    "06:39:EA:56:02:C1:00", # 7 octets
    "INVALID_ID_VALUE",
])
def test_gateway_malformed_id_returns_400(api_error_client, bad_id):
    """GET /gateways/{gateway_id} returns HTTP 400 for malformed gateway identifiers."""
    response = api_error_client.get(f"/gateways/{bad_id}")
    assert response.status_code == 400
    assert "Malformed gateway ID" in response.json()["detail"]


def test_gateway_unknown_id_returns_404(api_error_client):
    """GET /gateways/{gateway_id} returns HTTP 404 for valid hex ID absent from master."""
    response = api_error_client.get("/gateways/AABBCCDDEEFF")
    assert response.status_code == 404
    assert "Unknown gateway ID" in response.json()["detail"]


def test_gateway_query_malformed_date_returns_400(api_error_client):
    """GET /gateways/{gateway_id}?week_start=bad returns HTTP 400."""
    response = api_error_client.get("/gateways/001A7D000001?week_start=not-a-date")
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


# =============================================================================
# 3. POST /run Payload & Method Errors
# =============================================================================

def test_post_run_missing_body_returns_422(api_error_client):
    """POST /run with missing body returns HTTP 422."""
    response = api_error_client.post("/run")
    assert response.status_code == 422


def test_post_run_missing_field_returns_422(api_error_client):
    """POST /run with empty JSON object returns HTTP 422."""
    response = api_error_client.post("/run", json={})
    assert response.status_code == 422


def test_post_run_wrong_field_type_returns_422(api_error_client):
    """POST /run with non-string week_start returns HTTP 422."""
    response = api_error_client.post("/run", json={"week_start": 20260202})
    assert response.status_code == 422


def test_post_run_malformed_date_returns_400(api_error_client):
    """POST /run with unparseable date string returns HTTP 400."""
    response = api_error_client.post("/run", json={"week_start": "invalid-date"})
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


def test_post_run_unsupported_monday_returns_404(api_error_client):
    """POST /run with unscored date returns HTTP 404."""
    response = api_error_client.post("/run", json={"week_start": "2025-01-01"})
    assert response.status_code == 404
    assert "Unsupported week_start" in response.json()["detail"]


def test_unsupported_http_method_returns_405(api_error_client):
    """Calling POST on GET-only /health or /predictions returns HTTP 405."""
    assert api_error_client.post("/health").status_code == 405
    assert api_error_client.post("/predictions/2026-02-02").status_code == 405
    assert api_error_client.delete("/gateways/001A7D000001").status_code == 405


# =============================================================================
# 4. Clean Information Disclosure (No Internal Paths Leaked)
# =============================================================================

def test_error_responses_do_not_leak_internal_paths(api_error_client):
    """Error responses must contain clean user-facing details without leaking filesystem paths."""
    r1 = api_error_client.get("/predictions/bad-date")
    detail = str(r1.json().get("detail", ""))
    assert "D:\\" not in detail
    assert "C:\\" not in detail
    assert "/home/" not in detail
    assert ".py" not in detail

    r2 = api_error_client.get("/gateways/BAD_ID")
    detail2 = str(r2.json().get("detail", ""))
    assert ".py" not in detail2
    assert "Traceback" not in detail2
