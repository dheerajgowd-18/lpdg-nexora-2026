"""Validation module for NEXORA 2026 production pipeline outputs.

Performs internal sanity checks and invokes the official validate_submission.py harness.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import subprocess
import sys
from typing import Sequence
import pandas as pd
from .data_loader import is_valid_gateway_id

REQUIRED_COLUMNS = ["week_start", "rank", "gateway_id", "score", "reason"]
VISITS_PER_WEEK = 15
DEFAULT_SCORED_WEEKS = [
    dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)
]
MAX_REASON_CHARS = 300


def validate_predictions_df(
    df: pd.DataFrame,
    scored_weeks: Sequence[dt.date] = DEFAULT_SCORED_WEEKS,
) -> list[str]:
    """Validates an in-memory predictions DataFrame against submission criteria.

    Returns:
        List of error description strings. Empty list indicates full compliance.
    """
    problems: list[str] = []

    # Column checks
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        problems.append(f"Missing required column(s): {missing_cols}")
    extra_cols = [c for c in df.columns if c not in REQUIRED_COLUMNS]
    if extra_cols:
        problems.append(f"Unexpected column(s): {extra_cols}")
    if missing_cols:
        return problems

    # Row count check
    expected_rows = VISITS_PER_WEEK * len(scored_weeks)
    if len(df) != expected_rows:
        problems.append(f"Expected {expected_rows} rows ({len(scored_weeks)} weeks x {VISITS_PER_WEEK}), found {len(df)}")

    # Date parsing check
    try:
        weeks = pd.to_datetime(df["week_start"]).dt.date
    except Exception as e:
        problems.append(f"Cannot parse week_start as date: {e}")
        return problems

    found_weeks = sorted(set(weeks))
    expected_week_dates = sorted(scored_weeks)
    if found_weeks != expected_week_dates:
        problems.append(f"Scored weeks mismatch. Found: {found_weeks}, Expected: {expected_week_dates}")

    # Gateway ID validation
    bad_ids = [gid for gid in df["gateway_id"] if not is_valid_gateway_id(gid)]
    if bad_ids:
        problems.append(f"{len(bad_ids)} invalid gateway ID(s) found, e.g. {bad_ids[0]!r}")

    # Score checks
    if not pd.api.types.is_numeric_dtype(df["score"]):
        problems.append("Column 'score' must be numeric")
    elif df["score"].isna().any():
        problems.append(f"{int(df['score'].isna().sum())} score values are NaN")
    elif (df["score"] < 0).any():
        problems.append("Negative scores are not allowed")

    # Reason checks
    reasons = df["reason"].astype(str).str.strip()
    if (reasons == "").any() or df["reason"].isna().any():
        problems.append(f"{int((reasons == '').sum())} empty reason field(s)")
    too_long = (reasons.str.len() > MAX_REASON_CHARS).sum()
    if too_long > 0:
        problems.append(f"{too_long} reason field(s) exceed {MAX_REASON_CHARS} characters")

    # Per-week rank and duplicate checks
    for w_date, part in df.groupby(weeks):
        if len(part) != VISITS_PER_WEEK:
            problems.append(f"Week {w_date} has {len(part)} recommendations (expected {VISITS_PER_WEEK})")
        ranks = list(part["rank"])
        if sorted(ranks) != list(range(1, VISITS_PER_WEEK + 1)):
            problems.append(f"Week {w_date} ranks are not strictly 1..{VISITS_PER_WEEK}: {ranks}")
        dups = part["gateway_id"].duplicated().sum()
        if dups > 0:
            problems.append(f"Week {w_date} has {dups} duplicate gateway_id recommendations")

    return problems


def run_official_validator(predictions_path: str | Path) -> bool:
    """Executes python validate_submission.py <predictions_path> in a subprocess.

    Returns True if validator passes with exit code 0, raises RuntimeError otherwise.
    """
    path = Path(predictions_path)
    if not path.exists():
        raise FileNotFoundError(f"Predictions file does not exist: {path.resolve()}")

    cmd = [sys.executable, "validate_submission.py", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err_msg = (
            f"Official validator failed with code {result.returncode}:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        raise RuntimeError(err_msg)
    return True
