"""Unit tests for observational reason string generation and schema immutability."""

import pandas as pd
import pytest

from nexora.reasons import generate_reason, add_reasons, MAX_REASON_CHARS

FROZEN_ZERO_SCORE_REASON = (
    "0 individual 3-sigma metric breaches against this gateway's own 28-day baseline in the last 7 days"
)

FORBIDDEN_CAUSAL_WORDS = [
    "fault",
    "fuse",
    "burned",
    "broken",
    "tampered",
    "short circuit",
    "lightning",
    "damaged",
    "failed hardware",
]


def test_positive_score_reason():
    """Positive score reason correctly reflects score, flagged hours, and worst metric."""
    score = 7.0
    flagged = 7
    metric = "reboot_cnt"
    reason = generate_reason(score=score, flagged_hours=flagged, worst_metric=metric)

    assert "7 individual 3-sigma metric breach(es)" in reason
    assert "first breach on reboot_cnt" in reason
    assert len(reason) <= MAX_REASON_CHARS
    assert len(reason.strip()) > 0

    # Non-causal verification
    lower_reason = reason.lower()
    for forbidden in FORBIDDEN_CAUSAL_WORDS:
        assert forbidden not in lower_reason, f"Forbidden causal claim found: {forbidden}"


def test_zero_score_reason_exact_wording():
    """Zero-score reason matches the frozen exact text contract."""
    reason = generate_reason(score=0.0, flagged_hours=0, worst_metric="no_telemetry")

    assert reason == FROZEN_ZERO_SCORE_REASON
    assert reason == "0 individual 3-sigma metric breaches against this gateway's own 28-day baseline in the last 7 days"
    assert len(reason) <= MAX_REASON_CHARS


def test_reason_generation_determinism():
    """Repeated calls with identical parameters produce identical strings."""
    r1 = generate_reason(score=12.0, flagged_hours=12, worst_metric="offline_duration_sec")
    r2 = generate_reason(score=12.0, flagged_hours=12, worst_metric="offline_duration_sec")
    assert r1 == r2

    r3 = generate_reason(score=0.0, flagged_hours=0, worst_metric="")
    r4 = generate_reason(score=0.0, flagged_hours=0, worst_metric="")
    assert r3 == r4


def test_add_reasons_dataframe_immutability():
    """add_reasons appends 'reason' column without modifying existing score/rank data."""
    df = pd.DataFrame({
        "rank": [1, 2],
        "gateway_id": ["001A7D000001", "001A7D000002"],
        "score": [15.0, 0.0],
        "flagged_hours": [15, 0],
        "worst_metric": ["offline_duration_sec", "no_telemetry"],
    })
    original_copy = df.copy()

    augmented = add_reasons(df)

    # Invariants on existing columns
    pd.testing.assert_frame_equal(df, original_copy)  # original was not mutated in place
    for col in ["rank", "gateway_id", "score", "flagged_hours", "worst_metric"]:
        pd.testing.assert_series_equal(augmented[col], original_copy[col])

    # Reason column properties
    assert "reason" in augmented.columns
    assert len(augmented.iloc[0]["reason"]) <= MAX_REASON_CHARS
    assert len(augmented.iloc[1]["reason"]) <= MAX_REASON_CHARS
    assert augmented.iloc[1]["reason"] == FROZEN_ZERO_SCORE_REASON
