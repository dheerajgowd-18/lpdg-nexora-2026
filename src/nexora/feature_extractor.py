"""
Feature extraction engine implementing the 15 READY features for NEXORA 2026.
Strictly respects the right-open temporal horizon: t < T.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Sequence
import numpy as np
import pandas as pd

from .data_loader import DataLoader, normalize_gateway_id


class FeatureExtractor:
    """Extracts the 15 READY candidate features for active gateways on a prediction Monday."""

    FEATURE_CODES = [
        "F01",
        "F02",
        "F03",
        "F04",
        "F05",
        "F06",
        "F08",
        "F09",
        "F10",
        "F12",
        "F16",
        "F17",
        "F18",
        "F19",
        "F20",
    ]

    ALIASES = {
        "F01": "reported_hours_7d",
        "F02": "missing_hours_7d",
        "F03": "reporting_ratio_7d",
        "F04": "consecutive_missing_at_cutoff",
        "F05": "is_completely_silent_7d",
        "F06": "offline_duration_max_7d",
        "F08": "offline_hours_gt_3600_7d",
        "F09": "reboot_cnt_sum_7d",
        "F10": "reboot_cnt_sum_28d",
        "F12": "disconnection_cnt_sum_7d",
        "F16": "acute_chronic_divergence",
        "F17": "hist_meter_success_pre_feb",
        "F18": "hist_meter_outage_freq",
        "F19": "is_lifecycle_active",
        "F20": "installed_age_days",
    }

    def __init__(self, data_loader: DataLoader | None = None, data_dir: str | Path = "data") -> None:
        self.loader = data_loader or DataLoader(data_dir=data_dir)
        self._master = self.loader.load_master()
        self._meter_reads = self.loader.load_meter_reads()
        self._static_meter_features: pd.DataFrame | None = None

    def _get_static_meter_features(self, T: pd.Timestamp | None = None) -> pd.DataFrame:
        """Computes pre-February meter reliability priors (F17, F18).

        For scored window (T >= 2026-02-02 or T is None):
            Uses all historical data strictly <= 2026-01-26 (cached).
        For historical weeks (T < 2026-02-02):
            Strictly enforces week_start_dt < T to prevent future meter read leakage.
        """
        if T is None or T >= pd.Timestamp("2026-02-02", tz="UTC"):
            if self._static_meter_features is not None:
                return self._static_meter_features

            pre_feb = self._meter_reads[
                self._meter_reads["week_start_dt"] <= pd.Timestamp("2026-01-26", tz="UTC")
            ]
            agg = pre_feb.groupby("gateway_id").agg(
                tot_read=("meters_read", "sum"),
                tot_exp=("meters_expected", "sum"),
                zero_weeks=("meters_read", lambda s: (s == 0).sum()),
                tot_weeks=("meters_read", "count"),
            )
            agg["F17"] = (agg["tot_read"] / agg["tot_exp"].replace(0, np.nan)).fillna(0.0)
            agg["F18"] = (agg["zero_weeks"] / agg["tot_weeks"].replace(0, np.nan)).fillna(0.0)
            self._static_meter_features = agg[["F17", "F18"]]
            return self._static_meter_features

        # Historical week: strictly filter week_start_dt < T
        hist_reads = self._meter_reads[self._meter_reads["week_start_dt"] < T]
        if hist_reads.empty:
            return pd.DataFrame(columns=["F17", "F18"])

        agg = hist_reads.groupby("gateway_id").agg(
            tot_read=("meters_read", "sum"),
            tot_exp=("meters_expected", "sum"),
            zero_weeks=("meters_read", lambda s: (s == 0).sum()),
            tot_weeks=("meters_read", "count"),
        )
        agg["F17"] = (agg["tot_read"] / agg["tot_exp"].replace(0, np.nan)).fillna(0.0)
        agg["F18"] = (agg["zero_weeks"] / agg["tot_weeks"].replace(0, np.nan)).fillna(0.0)
        return agg[["F17", "F18"]]

    def get_active_universe(self, monday: dt.date | pd.Timestamp) -> pd.DataFrame:
        """Determines the active gateway universe for prediction Monday T.

        Rule: installed_on <= T AND (decommissioned_on > T OR decommissioned_on is null).
        """
        T = pd.Timestamp(monday, tz="UTC")
        active = self._master[
            (self._master["installed_on_dt"] <= T)
            & (
                self._master["decommissioned_on_dt"].isna()
                | (self._master["decommissioned_on_dt"] > T)
            )
        ].copy()
        return active

    def extract(self, week_start: str | dt.date | pd.Timestamp) -> pd.DataFrame:
        """Extracts the 15 READY features for all active gateways strictly for t < T.

        Args:
            week_start: Prediction Monday (e.g. '2026-02-02' or datetime.date(2026, 2, 2)).

        Returns:
            DataFrame containing gateway_id, week_start, F01-F20, and descriptive aliases.
        """
        if isinstance(week_start, str):
            monday = dt.date.fromisoformat(week_start)
        elif isinstance(week_start, pd.Timestamp):
            monday = week_start.date()
        else:
            monday = week_start

        T = pd.Timestamp(monday, tz="UTC")
        w7_start = T - dt.timedelta(days=7)
        w28_start = T - dt.timedelta(days=28)
        w21_end = w7_start

        # 1. Active Gateway Universe
        active_master = self.get_active_universe(monday)
        active_ids = sorted(active_master["gateway_id"].unique())

        cols_order = ["gateway_id", "week_start"] + self.FEATURE_CODES + list(self.ALIASES.values())
        if not active_ids:
            return pd.DataFrame(columns=cols_order)

        # 2. Identify and Load Required Telemetry Partitions
        start_month = w28_start.strftime("%Y-%m")
        end_month = (T - dt.timedelta(seconds=1)).strftime("%Y-%m")
        months = sorted(list({start_month, end_month}))
        telem = self.loader.load_telemetry(months=months)

        # 3. Apply Strict Temporal Filtering (Strictly t < T)
        t28 = telem[
            (telem["ts"] >= w28_start)
            & (telem["ts"] < T)
            & (telem["gateway_id"].isin(active_ids))
        ]
        t7 = t28[t28["ts"] >= w7_start]
        t21 = t28[t28["ts"] < w21_end]

        # 4. Construct Base Active Frame (Ensures silent gateways are retained)
        df = pd.DataFrame({"gateway_id": active_ids})
        df["week_start"] = monday.isoformat()

        # F01: reported_hours_7d
        h7_dict = t7.groupby("gateway_id")["ts"].nunique().to_dict()
        df["F01"] = df["gateway_id"].map(h7_dict).fillna(0).astype(int)

        # F02: missing_hours_7d
        df["F02"] = 168 - df["F01"]

        # F03: reporting_ratio_7d
        df["F03"] = df["F01"] / 168.0

        # F04: consecutive_missing_at_cutoff
        latest_ts_dict = t28.groupby("gateway_id")["ts"].max().to_dict()
        df["_latest_ts"] = df["gateway_id"].map(latest_ts_dict)
        df["F04"] = (T - df["_latest_ts"]).dt.total_seconds() / 3600.0
        df["F04"] = df["F04"].fillna(672.0)  # Capped at 28 days (672 hours)
        df = df.drop(columns=["_latest_ts"])

        # F05: is_completely_silent_7d
        df["F05"] = (df["F01"] == 0).astype(int)

        # F06: offline_duration_max_7d (Peak reported counter value in 7d window)
        off_max_dict = t7.groupby("gateway_id")["offline_duration_sec"].max().to_dict()
        df["F06"] = df["gateway_id"].map(off_max_dict).fillna(0.0).astype(float)

        # F08: offline_hours_gt_3600_7d (Observations where reported counter >= 3600s)
        off_gt_dict = (
            t7[t7["offline_duration_sec"] >= 3600]
            .groupby("gateway_id")["ts"]
            .nunique()
            .to_dict()
        )
        df["F08"] = df["gateway_id"].map(off_gt_dict).fillna(0).astype(int)

        # F09: reboot_cnt_sum_7d
        reb7_dict = t7.groupby("gateway_id")["reboot_cnt"].sum().to_dict()
        df["F09"] = df["gateway_id"].map(reb7_dict).fillna(0).astype(int)

        # F10: reboot_cnt_sum_28d
        reb28_dict = t28.groupby("gateway_id")["reboot_cnt"].sum().to_dict()
        df["F10"] = df["gateway_id"].map(reb28_dict).fillna(0).astype(int)

        # F12: disconnection_cnt_sum_7d
        disc7_dict = t7.groupby("gateway_id")["disconnection_cnt"].sum().to_dict()
        df["F12"] = df["gateway_id"].map(disc7_dict).fillna(0).astype(int)

        # F16: acute_chronic_divergence
        h21_dict = t21.groupby("gateway_id")["ts"].nunique().to_dict()
        prior_21d_ratio = df["gateway_id"].map(h21_dict).fillna(0) / (21 * 24.0)
        df["F16"] = np.maximum(0.0, prior_21d_ratio - df["F03"])

        # F17 & F18: Static Pre-February Meter Priors (strictly week_start_dt < T for historical weeks)
        meter_features = self._get_static_meter_features(T)
        df["F17"] = df["gateway_id"].map(meter_features["F17"]).fillna(0.0)
        df["F18"] = df["gateway_id"].map(meter_features["F18"]).fillna(0.0)

        # F19: is_lifecycle_active (Exactly 1 for all active gateways)
        df["F19"] = 1

        # F20: installed_age_days
        inst_dict = active_master.set_index("gateway_id")["installed_on_dt"].to_dict()
        df["_inst_dt"] = df["gateway_id"].map(inst_dict)
        df["F20"] = (T - df["_inst_dt"]).dt.total_seconds() / 86400.0
        df = df.drop(columns=["_inst_dt"])

        # Add descriptive alias columns
        for code, alias in self.ALIASES.items():
            df[alias] = df[code]

        # Deterministic sorting
        df = df.sort_values("gateway_id").reset_index(drop=True)
        return df

    def extract_all(
        self, scored_weeks: Sequence[str | dt.date] | None = None
    ) -> pd.DataFrame:
        """Extracts features across all scored prediction Mondays into a single panel frame."""
        if scored_weeks is None:
            scored_weeks = [
                dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)
            ]

        frames = []
        for week in scored_weeks:
            frames.append(self.extract(week))
        return pd.concat(frames, ignore_index=True)
