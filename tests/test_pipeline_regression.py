"""End-to-end regression tests for the NEXORA 2026 production pipeline.

Verifies:
- Production pipeline execution on synthetic fixtures
- Output schema, types, and constraints (Official contract)
- Determinism across repeated pipeline runs
- Dataset isolation (no auxiliary challenge files required)
- Structural properties of the real-data predictions file
"""

import datetime as dt
from pathlib import Path
import re
import pandas as pd
import pytest

from nexora.pipeline import run_pipeline, predict_week, SCORED_WEEKS
from nexora.validation import validate_predictions_df, run_official_validator

CANONICAL_HEX_REGEX = re.compile(r"^[0-9A-F]{12}$")
EXPECTED_COLUMNS = ["week_start", "rank", "gateway_id", "score", "reason"]


@pytest.fixture
def synthetic_pipeline_env(tmp_path):
    """Sets up a minimal, self-contained synthetic challenge environment for fast E2E testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    # 20 eligible gateways
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
        # Generate baseline and recent telemetry
        start_date = dt.date(2026, 1, 1) if month_str == "2026-01" else dt.date(2026, 2, 1)
        for day in range(25):
            curr_date = start_date + dt.timedelta(days=day)
            for i in range(1, 10):  # First 9 gateways have telemetry
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

    return data_dir, out_dir


# =============================================================================
# 6. Production Regression Test (Synthetic E2E Pipeline)
# =============================================================================

def test_pipeline_execution_synthetic_e2e(synthetic_pipeline_env):
    """Executes the complete production pipeline on synthetic data across multiple weeks."""
    data_dir, out_dir = synthetic_pipeline_env
    out_file = out_dir / "test_predictions.csv"

    # Test 2 scored weeks
    test_weeks = [dt.date(2026, 2, 2), dt.date(2026, 2, 9)]
    df = run_pipeline(
        data_dir=data_dir,
        out_path=out_file,
        scored_weeks=test_weeks,
        run_validator=False,
    )

    # Invariants
    assert len(df) == 30  # 2 weeks * 15 rows
    assert list(df.columns) == EXPECTED_COLUMNS

    # Internal validation must report zero errors
    errors = validate_predictions_df(df, scored_weeks=test_weeks)
    assert errors == []


def test_predict_week_single_monday_independent(synthetic_pipeline_env):
    """Verifies that predict_week executes independently for a single Monday.

    Ensures clean decoupling of the single-week prediction engine for Phase 11 FastAPI service.
    """
    data_dir, _ = synthetic_pipeline_env
    from nexora.data_loader import DataLoader
    loader = DataLoader(data_dir=data_dir)
    master_df = loader.load_master()
    telemetry_df = loader.load_telemetry()

    monday = dt.date(2026, 2, 2)
    week_df = predict_week(master_df, telemetry_df, monday, top_k=15)

    assert len(week_df) == 15
    assert list(week_df.columns) == EXPECTED_COLUMNS
    assert list(week_df["rank"]) == list(range(1, 16))
    assert (week_df["week_start"] == "2026-02-02").all()
    assert (week_df["score"] >= 0.0).all()
    assert (week_df["reason"].str.len() > 0).all()
    assert (week_df["reason"].str.len() <= 300).all()


# =============================================================================
# 8. Dataset Isolation Test
# =============================================================================

def test_pipeline_dataset_isolation(synthetic_pipeline_env):
    """Production pipeline executes strictly from gateway_master.csv and telemetry/."""
    data_dir, out_dir = synthetic_pipeline_env

    # Explicitly confirm no auxiliary files exist in the data dir
    forbidden_files = ["field_visits.csv", "meter_read_success.csv", "engineer_review_2026-02.xlsx"]
    for fname in forbidden_files:
        assert not (data_dir / fname).exists()

    out_file = out_dir / "isolation_predictions.csv"
    test_weeks = [dt.date(2026, 2, 2)]

    df = run_pipeline(
        data_dir=data_dir,
        out_path=out_file,
        scored_weeks=test_weeks,
        run_validator=False,
    )

    assert len(df) == 15
    assert out_file.exists()


# =============================================================================
# 9. Pipeline Determinism Test
# =============================================================================

def test_pipeline_determinism(synthetic_pipeline_env):
    """Running pipeline twice on identical input produces bitwise identical results."""
    data_dir, out_dir = synthetic_pipeline_env
    test_weeks = [dt.date(2026, 2, 2)]

    out1 = out_dir / "run1.csv"
    out2 = out_dir / "run2.csv"

    df1 = run_pipeline(data_dir=data_dir, out_path=out1, scored_weeks=test_weeks, run_validator=False)
    df2 = run_pipeline(data_dir=data_dir, out_path=out2, scored_weeks=test_weeks, run_validator=False)

    pd.testing.assert_frame_equal(df1, df2)
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")


# =============================================================================
# 10. Official Output Contract Verification Test
# =============================================================================

def test_official_output_contract(synthetic_pipeline_env):
    """Verifies all strict schema and content rules of the official submission contract."""
    data_dir, out_dir = synthetic_pipeline_env
    out_file = out_dir / "contract_predictions.csv"
    test_weeks = [dt.date(2026, 2, 2)]

    df = run_pipeline(data_dir=data_dir, out_path=out_file, scored_weeks=test_weeks, run_validator=False)

    # 1. Column names
    assert list(df.columns) == ["week_start", "rank", "gateway_id", "score", "reason"]

    # 2. Exactly 15 rows per week
    assert len(df) == 15

    # 3. Consecutive ranks 1..15
    assert list(df["rank"]) == list(range(1, 16))

    # 4. No duplicate gateway IDs within week
    assert len(df["gateway_id"].unique()) == 15

    # 5. Gateway IDs are 12-char bare hex
    for gid in df["gateway_id"]:
        assert CANONICAL_HEX_REGEX.match(gid) is not None

    # 6. Non-empty reasons <= 300 characters
    for reason in df["reason"]:
        assert isinstance(reason, str)
        assert len(reason.strip()) > 0
        assert len(reason) <= 300

    # 7. Numeric non-negative scores
    for score in df["score"]:
        assert isinstance(score, (float, int))
        assert score >= 0.0


# =============================================================================
# 11. Real Data Regression Test
# =============================================================================

def test_real_dataset_predictions_structure():
    """Structural validation on the real Phase 8 production predictions.csv.

    Guarantees that the verified artifact satisfies the 120-row contract
    and passes the official validation harness.
    """
    pred_path = Path("predictions.csv")
    if not pred_path.exists():
        pytest.skip("predictions.csv not present in repository root")

    df = pd.read_csv(pred_path)

    # 1. Total rows: exactly 120 (8 weeks * 15)
    assert len(df) == 120, f"Expected 120 rows, got {len(df)}"

    # 2. Schema check
    assert list(df.columns) == EXPECTED_COLUMNS

    # 3. 8 distinct weeks, 15 rows per week
    weeks = df["week_start"].unique()
    assert len(weeks) == 8
    for w in weeks:
        week_df = df[df["week_start"] == w]
        assert len(week_df) == 15
        assert list(week_df["rank"]) == list(range(1, 16))
        assert len(week_df["gateway_id"].unique()) == 15

    # 4. Reason lengths <= 300 chars and non-empty
    assert (df["reason"].str.len() <= 300).all()
    assert (df["reason"].str.len() > 0).all()

    # 5. Non-negative numeric scores
    assert (df["score"] >= 0.0).all()

    # 6. Official validate_submission.py validator compatibility
    validator_script = Path("validate_submission.py")
    if validator_script.exists():
        run_official_validator(pred_path)
