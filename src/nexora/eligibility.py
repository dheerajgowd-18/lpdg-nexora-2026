"""Lifecycle eligibility module for NEXORA 2026.

Determines the active candidate gateway fleet strictly from gateway_master.csv lifecycle dates:
installed_on <= T AND (decommissioned_on > T OR decommissioned_on is null).
"""

from __future__ import annotations

import datetime as dt
from typing import Sequence
import pandas as pd
from .data_loader import normalize_gateway_id


def get_eligible_gateways(
    master_df: pd.DataFrame,
    decision_monday: dt.date | dt.datetime | str,
) -> list[str]:
    """Returns the list of canonical gateway IDs eligible for recommendation on decision Monday T.

    Eligibility condition:
        installed_on <= T and (decommissioned_on > T or decommissioned_on is null)

    Boundary semantics:
        - If installed_on == T: eligible.
        - If decommissioned_on == T: NOT eligible.
        - Telemetry presence does NOT determine eligibility.

    Returns:
        Deterministic list of canonical 12-char hex gateway IDs sorted ascending.
    """
    if isinstance(decision_monday, str):
        target_date = dt.date.fromisoformat(decision_monday)
    elif isinstance(decision_monday, dt.datetime):
        target_date = decision_monday.date()
    elif isinstance(decision_monday, dt.date):
        target_date = decision_monday
    else:
        raise TypeError(f"Unsupported decision_monday type: {type(decision_monday)}")

    df = master_df.copy()
    if "installed_on_dt" not in df.columns:
        df["installed_on_dt"] = pd.to_datetime(df["installed_on"], utc=True)
    if "decommissioned_on_dt" not in df.columns:
        if "decommissioned_on" in df.columns:
            df["decommissioned_on_dt"] = pd.to_datetime(df["decommissioned_on"], utc=True)
        else:
            df["decommissioned_on_dt"] = pd.NaT

    T = pd.Timestamp(target_date, tz="UTC")
    is_installed = df["installed_on_dt"] <= T
    decomm_series = df["decommissioned_on_dt"]
    is_not_decommissioned = decomm_series.isna() | (decomm_series > T)

    eligible_mask = is_installed & is_not_decommissioned
    eligible_df = df[eligible_mask]

    canonical_ids = sorted({normalize_gateway_id(gid) for gid in eligible_df["gateway_id"]})
    return canonical_ids
