"""Unit tests for ranking, silent gateway retention (Option B), tie-breaking, and capacity checks."""

import pandas as pd
import pytest

from nexora.ranking import rank_and_select, VISITS_PER_WEEK


def test_deterministic_ordering_scores_and_ties():
    """Gateways are ranked primarily by score desc, secondarily by gateway_id asc."""
    # 20 eligible gateways
    eligible_ids = [f"001A7D0000{i:02X}" for i in range(1, 21)]

    scored_df = pd.DataFrame({
        "gateway_id": ["001A7D00000B", "001A7D00000A", "001A7D00000C", "001A7D00000D"],
        "score": [20.0, 20.0, 15.0, 5.0],  # A and B are tied at 20.0
        "flagged_hours": [20, 20, 15, 5],
        "worst_metric": ["reboot_cnt", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"],
    })

    top15 = rank_and_select(scored_df, eligible_ids, top_k=15)

    assert len(top15) == 15
    # Tied score check: A precedes B because "001A7D00000A" < "001A7D00000B"
    assert top15.iloc[0]["gateway_id"] == "001A7D00000A"
    assert top15.iloc[0]["score"] == 20.0
    assert top15.iloc[1]["gateway_id"] == "001A7D00000B"
    assert top15.iloc[1]["score"] == 20.0

    # Rank 3 and 4
    assert top15.iloc[2]["gateway_id"] == "001A7D00000C"
    assert top15.iloc[2]["score"] == 15.0
    assert top15.iloc[3]["gateway_id"] == "001A7D00000D"
    assert top15.iloc[3]["score"] == 5.0


def test_exactly_15_output_rows_and_consecutive_ranks():
    """Output contains exactly 15 rows with consecutive ranks 1 to 15."""
    eligible_ids = [f"001A7D0000{i:02X}" for i in range(1, 25)]
    top15 = rank_and_select(pd.DataFrame(), eligible_ids, top_k=15)

    assert len(top15) == 15
    assert list(top15["rank"]) == list(range(1, 16))


def test_no_duplicate_gateway_ids():
    """No duplicate gateway IDs exist in the top-15 selection."""
    eligible_ids = [f"001A7D0000{i:02X}" for i in range(1, 20)]
    top15 = rank_and_select(pd.DataFrame(), eligible_ids, top_k=15)

    assert len(top15["gateway_id"].unique()) == 15


def test_option_b_silent_gateway_retention_and_no_bonus():
    """Eligible gateways with no recent telemetry are retained with score 0.0 and no bonus."""
    eligible_ids = [f"001A7D0000{i:02X}" for i in range(1, 18)]

    # Only 2 gateways have telemetry scores
    scored_df = pd.DataFrame({
        "gateway_id": ["001A7D000001", "001A7D000002"],
        "score": [12.0, 4.0],
        "flagged_hours": [12, 4],
        "worst_metric": ["reboot_cnt", "offline_duration_sec"],
    })

    top15 = rank_and_select(scored_df, eligible_ids, top_k=15)

    # Ranks 1 and 2 are the scored gateways
    assert top15.iloc[0]["gateway_id"] == "001A7D000001"
    assert top15.iloc[1]["gateway_id"] == "001A7D000002"

    # Ranks 3 to 15 are silent gateways retained under Option B
    for r in range(2, 15):
        row = top15.iloc[r]
        assert row["score"] == 0.0, f"Silent gateway at rank {r+1} received non-zero score"
        assert row["flagged_hours"] == 0
        assert row["worst_metric"] == "no_telemetry"

    # Verify silent gateways are NOT elevated above a gateway with score=0.0 that has telemetry
    scored_with_zero = pd.DataFrame({
        "gateway_id": ["001A7D000001", "001A7D000003"],
        "score": [10.0, 0.0],
        "flagged_hours": [10, 0],
        "worst_metric": ["reboot_cnt", ""],
    })
    top15_zero = rank_and_select(scored_with_zero, eligible_ids, top_k=15)
    # Both gateway 001A7D000003 and silent gateways have score 0.0; tie broken strictly by ID
    score_0_gateways = top15_zero[top15_zero["score"] == 0.0]
    assert list(score_0_gateways["gateway_id"]) == sorted(list(score_0_gateways["gateway_id"]))


def test_fewer_than_15_eligible_gateways_raises_error():
    """ValueError is raised if eligible fleet cardinality is strictly less than 15."""
    with pytest.raises(ValueError, match="Fewer than 15 eligible gateways"):
        rank_and_select(pd.DataFrame(), ["001A7D000001", "001A7D000002"], top_k=15)


def test_output_schema_and_column_types():
    """Verifies output dataframe matches required columns and types."""
    eligible_ids = [f"001A7D0000{i:02X}" for i in range(1, 17)]
    top15 = rank_and_select(pd.DataFrame(), eligible_ids, top_k=15)

    expected_cols = ["rank", "gateway_id", "score", "flagged_hours", "worst_metric"]
    assert list(top15.columns) == expected_cols
    assert top15["rank"].dtype in [int, "int32", "int64"]
    assert top15["score"].dtype in [float, "float64"]


def test_duplicate_scored_records_raises_valueerror():
    """rank_and_select explicitly rejects duplicate scored records for the same gateway."""
    eligible_ids = [f"001A7D0000{i:02X}" for i in range(1, 20)]
    duplicated_df = pd.DataFrame({
        "gateway_id": ["001A7D000001", "001A7D000001", "001A7D000002"],
        "score": [12.0, 8.0, 4.0],
        "flagged_hours": [12, 8, 4],
        "worst_metric": ["reboot_cnt", "offline_duration_sec", "disconnection_cnt"],
    })
    with pytest.raises(ValueError, match="Duplicate scored records detected"):
        rank_and_select(duplicated_df, eligible_ids, top_k=15)

