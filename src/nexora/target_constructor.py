"""
Backtesting Target Construction Module for NEXORA 2026 Phase 6.1.
Enforces strict temporal contracts, event-level outcome mapping,
policy-attribution by dispatch initiation (requested_on), and physical
outcome tracking (visited_on).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Sequence, Literal
import pandas as pd
import numpy as np

from .data_loader import DataLoader, normalize_gateway_id


class TargetConstructor:
    """Constructs leakage-safe operational evaluation targets from historical field visits
    and engineer reviews.
    """

    TARGET_CATEGORIES = [
        "REPAIR_REQUIRED",
        "FALSE_ALARM",
        "INCONCLUSIVE",
        "UNOBSERVED",
    ]

    def __init__(self, data_loader: DataLoader | None = None, data_dir: str | Path = "data") -> None:
        self.loader = data_loader or DataLoader(data_dir=data_dir)
        self.data_dir = self.loader.data_dir
        self._visits_df: pd.DataFrame | None = None
        self._engineer_review_df: pd.DataFrame | None = None

    def load_field_visits(self) -> pd.DataFrame:
        """Loads and canonicalizes field_visits.csv.
        Columns:
            visit_id, gateway_id (normalized), requested_on, visited_on,
            req_dt, vis_dt, reason_reported, outcome, parts_replaced, technician_hours
        """
        if self._visits_df is not None:
            return self._visits_df.copy()

        path = self.data_dir / "field_visits.csv"
        df = pd.read_csv(path)
        df["gateway_id_raw"] = df["gateway_id"]
        df["gateway_id"] = df["gateway_id"].apply(normalize_gateway_id)
        df["req_dt"] = pd.to_datetime(df["requested_on"], utc=True)
        df["vis_dt"] = pd.to_datetime(df["visited_on"], utc=True)
        self._visits_df = df
        return df.copy()

    def load_engineer_review(self) -> pd.DataFrame:
        """Loads and canonicalizes engineer_review_2026-02.xlsx.
        Review Date: Strictly 2026-02-15.
        Columns: gateway_id (normalized), standort, Kategorie, reviewed_on, reviewer, Bemerkung
        """
        if self._engineer_review_df is not None:
            return self._engineer_review_df.copy()

        path = self.data_dir / "engineer_review_2026-02.xlsx"
        df = pd.read_excel(path)
        df["gateway_id_raw"] = df["gateway_id"]
        df["gateway_id"] = df["gateway_id"].apply(normalize_gateway_id)
        df["reviewed_on_dt"] = pd.to_datetime(df["reviewed_on"], utc=True)
        self._engineer_review_df = df
        return df.copy()

    def construct_weekly_target(
        self,
        cutoff_date: str | dt.date | pd.Timestamp,
        outcome_window_days: int = 7,
        timing_basis: Literal["requested_on", "visited_on"] = "requested_on",
    ) -> pd.DataFrame:
        """Constructs an operational backtesting target for a specific decision Monday T.

        Primary Policy-Attribution Principle (timing_basis='requested_on'):
            - Eligible Work Orders: requested_on in [T, T + outcome_window_days).
              Only work orders initiated at or after decision Monday T and before T+7d can be attributed
              to the hypothetical decision made at T.
            - Outcome Realization: Evaluates outcome ('Fehler behoben', 'Kein Fehler gefunden',
              'Kein Zugang') realized when visited_on occurred.
            - Delay Tracking: Flags whether visited_on >= T + outcome_window_days (delayed outcome).

        Sensitivity Analysis (timing_basis='visited_on'):
            - Physical visit timing sensitivity: filters strictly on visited_on in [T, T + outcome_window_days).

        Target Categories:
            - REPAIR_REQUIRED: Eligible dispatch resulting in confirmed repair ('Fehler behoben').
            - FALSE_ALARM: Eligible dispatch resulting in false alarm ('Kein Fehler gefunden').
            - INCONCLUSIVE: Eligible dispatch resulting in access denied ('Kein Zugang').
            - UNOBSERVED: No eligible dispatch was initiated in the window.
              (Crucial Invariant: UNOBSERVED != healthy!).

        Args:
            cutoff_date: Decision Monday T (e.g. '2026-02-02').
            outcome_window_days: Evaluation window length (default: 7 days, [T, T+7d)).
            timing_basis: 'requested_on' (PRIMARY: policy-attribution by dispatch initiation)
                          or 'visited_on' (SENSITIVITY: physical visit timing).

        Returns:
            DataFrame with one row per active gateway at T containing:
                gateway_id, cutoff_date, target_category, is_dispatched (bool),
                is_positive_repair (bool), dispatch_count, is_delayed_realization (bool),
                parts_replaced, technician_hours_sum
        """
        T = pd.Timestamp(cutoff_date, tz="UTC")
        W_end = T + dt.timedelta(days=outcome_window_days)

        # 1. Active Universe at T
        master = self.loader.load_master()
        active_master = master[
            (master["installed_on_dt"] <= T)
            & (master["decommissioned_on_dt"].isna() | (master["decommissioned_on_dt"] > T))
        ].copy()
        active_ids = sorted(active_master["gateway_id"].unique())

        # 2. Field Visits Filtering
        fv = self.load_field_visits()
        time_col = "req_dt" if timing_basis == "requested_on" else "vis_dt"
        w_visits = fv[
            (fv[time_col] >= T)
            & (fv[time_col] < W_end)
            & (fv["gateway_id"].isin(active_ids))
        ].copy()

        # 3. Aggregate Multiple Visits per Gateway in Window
        summary_records = []
        for gid in active_ids:
            g_vis = w_visits[w_visits["gateway_id"] == gid]
            if g_vis.empty:
                cat = "UNOBSERVED"
                is_disp = False
                is_rep = False
                v_cnt = 0
                is_delayed = False
                parts = []
                hours = 0.0
            else:
                is_disp = True
                v_cnt = len(g_vis)
                hours = float(g_vis["technician_hours"].sum())
                parts = [str(p) for p in g_vis["parts_replaced"].dropna().tolist()]
                
                # Check delay: did any visit take place outside the 7-day window?
                is_delayed = bool((g_vis["vis_dt"] >= W_end).any())

                # Outcome Precedence:
                # 1. 'Fehler behoben' (REPAIR_REQUIRED)
                # 2. 'Kein Fehler gefunden' (FALSE_ALARM)
                # 3. 'Kein Zugang' (INCONCLUSIVE)
                has_repair = (g_vis["outcome"] == "Fehler behoben").any()
                has_nofault = (g_vis["outcome"] == "Kein Fehler gefunden").any()

                if has_repair:
                    cat = "REPAIR_REQUIRED"
                    is_rep = True
                elif has_nofault:
                    cat = "FALSE_ALARM"
                    is_rep = False
                else:
                    cat = "INCONCLUSIVE"
                    is_rep = False

            summary_records.append({
                "gateway_id": gid,
                "cutoff_date": T.strftime("%Y-%m-%d"),
                "outcome_window_days": outcome_window_days,
                "timing_basis": timing_basis,
                "target_category": cat,
                "is_dispatched": is_disp,
                "is_positive_repair": is_rep,
                "dispatch_count": v_cnt,
                "is_delayed_realization": is_delayed,
                "parts_replaced": ";".join(parts) if parts else "None",
                "technician_hours_sum": hours,
            })

        df_target = pd.DataFrame(summary_records)
        return df_target

    def get_engineer_review_labels(
        self,
        as_of_date: str | dt.date | pd.Timestamp,
    ) -> pd.DataFrame:
        """Retrieves engineer review labels strictly if as_of_date > 2026-02-15.
        If as_of_date <= 2026-02-15, returns an empty frame (strict anti-leakage).
        """
        T = pd.Timestamp(as_of_date, tz="UTC")
        review_date = pd.Timestamp("2026-02-15", tz="UTC")

        if T <= review_date:
            return pd.DataFrame(columns=["gateway_id", "engineer_category", "reviewed_on"])

        er = self.load_engineer_review()
        df = er[["gateway_id", "Kategorie", "reviewed_on"]].copy()
        df = df.rename(columns={"Kategorie": "engineer_category"})
        return df
