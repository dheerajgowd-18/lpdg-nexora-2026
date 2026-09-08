"""
Data loading and normalization module for NEXORA 2026.
Handles character encoding, gateway ID canonicalization, and deduplication.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Sequence
import pandas as pd


def normalize_gateway_id(gateway_id: str) -> str:
    """Canonicalizes gateway identifiers to 12-character uppercase bare hex.

    Examples:
        '06:39:EA:56:02:C1' -> '0639EA5602C1'
        '0639ea5602c1'      -> '0639EA5602C1'
    """
    if not isinstance(gateway_id, str):
        return str(gateway_id)
    return gateway_id.strip().replace(":", "").upper()


class DataLoader:
    """Loads, normalizes, and caches challenge datasets."""

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self._master_df: pd.DataFrame | None = None
        self._meter_df: pd.DataFrame | None = None
        self._telemetry_cache: dict[str, pd.DataFrame] = {}

    def load_master(self) -> pd.DataFrame:
        """Loads and normalizes gateway_master.csv.

        Note: Uses encoding='latin1' to avoid UnicodeDecodeError on byte 0xDF.
        """
        if self._master_df is not None:
            return self._master_df.copy()

        path = self.data_dir / "gateway_master.csv"
        df = pd.read_csv(path, encoding="latin1")
        df["gateway_id_raw"] = df["gateway_id"]
        df["gateway_id"] = df["gateway_id"].apply(normalize_gateway_id)
        df["installed_on_dt"] = pd.to_datetime(df["installed_on"], utc=True)
        df["decommissioned_on_dt"] = pd.to_datetime(df["decommissioned_on"], utc=True)
        self._master_df = df
        return df.copy()

    def load_meter_reads(self) -> pd.DataFrame:
        """Loads and normalizes meter_read_success.csv."""
        if self._meter_df is not None:
            return self._meter_df.copy()

        path = self.data_dir / "meter_read_success.csv"
        df = pd.read_csv(path)
        df["gateway_id"] = df["gateway_id"].apply(normalize_gateway_id)
        df["week_start_dt"] = pd.to_datetime(df["week_start"], utc=True)
        self._meter_df = df
        return df.copy()

    def load_telemetry(
        self,
        months: Sequence[str] | None = None,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Loads and deduplicates telemetry across specified monthly partitions.

        Deduplication rule: drop_duplicates(subset=['gateway_id', 'ts_utc'], keep='first').
        """
        if months is None:
            month_dirs = sorted(self.data_dir.glob("telemetry/month=*"))
            months = [d.name.split("=")[1] for d in month_dirs if d.is_dir()]

        if columns is None:
            columns = [
                "gateway_id",
                "ts_utc",
                "offline_duration_sec",
                "reboot_cnt",
                "disconnection_cnt",
            ]

        load_cols = list(columns)
        for req in ["gateway_id", "ts_utc"]:
            if req not in load_cols:
                load_cols.append(req)

        dfs = []
        for m in months:
            if m not in self._telemetry_cache:
                part_path = self.data_dir / f"telemetry/month={m}/part-0.parquet"
                if part_path.exists():
                    d = pd.read_parquet(part_path, columns=load_cols)
                    d["gateway_id"] = d["gateway_id"].apply(normalize_gateway_id)
                    d["ts"] = pd.to_datetime(d["ts_utc"], utc=True)
                    d = d.drop_duplicates(subset=["gateway_id", "ts_utc"], keep="first")
                    self._telemetry_cache[m] = d
            if m in self._telemetry_cache:
                dfs.append(self._telemetry_cache[m])

        if not dfs:
            return pd.DataFrame(columns=load_cols + ["ts"])

        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=["gateway_id", "ts_utc"], keep="first")
        return combined
