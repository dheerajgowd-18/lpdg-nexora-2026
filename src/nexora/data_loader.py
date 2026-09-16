"""Data loading and normalization module for NEXORA 2026.

Handles master asset loading, Latin-1 compatibility, gateway ID canonicalization,
telemetry loading, strict temporal parsing (UTC), exact deduplication, and unknown gateway filtering.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import re
from typing import Sequence
import pandas as pd

BARE_HEX_REGEX = re.compile(r"^[0-9A-Fa-f]{12}$")
COLON_HEX_REGEX = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

from .config import (
    REQUIRED_MASTER_COLUMNS,
    REQUIRED_TELEMETRY_COLUMNS,
    REQUIRED_METER_COLUMNS,
)


def normalize_gateway_id(gateway_id: str) -> str:
    """Canonicalizes gateway identifiers to 12-character uppercase bare hexadecimal.

    Accepts 12-char bare hex or colon-separated hex (e.g. MAC address style).
    Strips leading/trailing whitespace and upper-cases all characters.

    Examples:
        '06:39:EA:56:02:C1' -> '0639EA5602C1'
        '0639ea5602c1'      -> '0639EA5602C1'

    Raises:
        ValueError: If gateway_id cannot be normalized to a 12-character hex string.
    """
    if not isinstance(gateway_id, str):
        gateway_id = str(gateway_id)
    text = gateway_id.strip()
    if BARE_HEX_REGEX.match(text):
        return text.upper()
    if COLON_HEX_REGEX.match(text):
        return text.replace(":", "").upper()
    raise ValueError(f"Invalid gateway ID format: {gateway_id!r}")


def is_valid_gateway_id(gateway_id: str) -> bool:
    """Checks whether a string can be normalized into a valid 12-char hex ID."""
    try:
        normalize_gateway_id(gateway_id)
        return True
    except (ValueError, TypeError):
        return False


class DataLoader:
    """Loads, normalizes, deduplicates, and caches challenge datasets."""

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir.resolve()}")
        self._master_df: pd.DataFrame | None = None
        self._telemetry_df: pd.DataFrame | None = None
        self._meter_reads_df: pd.DataFrame | None = None
        self._telemetry_cache: dict[str, pd.DataFrame] = {}

    def load_master(self) -> pd.DataFrame:
        """Loads and normalizes gateway_master.csv.

        Note: Uses encoding='latin1' to handle German umlauts/special characters safely.
        Validates required columns, canonicalizes gateway_id, and parses lifecycle dates
        into timezone-aware UTC timestamps ('installed_on_dt', 'decommissioned_on_dt')
        alongside backward-compatible date aliases ('installed_on_date', 'decommissioned_on_date').
        """
        if self._master_df is not None:
            return self._master_df.copy()

        master_path = self.data_dir / "gateway_master.csv"
        if not master_path.exists():
            raise FileNotFoundError(f"gateway_master.csv not found at {master_path.resolve()}")

        df = pd.read_csv(master_path, encoding="latin1")

        missing = [col for col in REQUIRED_MASTER_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"gateway_master.csv missing required column(s): {missing}")

        df["gateway_id_raw"] = df["gateway_id"]
        df["gateway_id"] = df["gateway_id"].apply(normalize_gateway_id)
        df["installed_on_dt"] = pd.to_datetime(df["installed_on"], utc=True)

        if "decommissioned_on" in df.columns:
            df["decommissioned_on_dt"] = pd.to_datetime(df["decommissioned_on"], utc=True)
        else:
            df["decommissioned_on_dt"] = pd.NaT

        # Backward-compatible date-only aliases
        df["installed_on_date"] = df["installed_on_dt"].dt.date
        df["decommissioned_on_date"] = df["decommissioned_on_dt"].dt.date

        self._master_df = df
        return df.copy()

    def load_telemetry(
        self,
        columns: Sequence[str] | None = None,
        filter_known_gateways: bool = True,
        months: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Loads and deduplicates telemetry across monthly Parquet partitions.

        Deduplication rule:
            telemetry.drop_duplicates(subset=["gateway_id", "ts_utc"], keep="first")

        Preserves timestamps as timezone-aware UTC in 'ts'.
        Optionally filters out telemetry for gateways not present in gateway_master.csv.
        Optionally restricts loading to specific partition months (e.g. ['2025-08', '2025-09']).
        """
        if self._telemetry_df is not None:
            if months is not None:
                months_set = set(months)
                mask = self._telemetry_df["ts"].dt.strftime("%Y-%m").isin(months_set)
                return self._telemetry_df[mask].copy()
            return self._telemetry_df.copy()

        if months is not None and all(m in self._telemetry_cache for m in months):
            cached_parts = [self._telemetry_cache[m] for m in months]
            combined = pd.concat(cached_parts, ignore_index=True)
            return combined.copy()

        telemetry_dir = self.data_dir / "telemetry"
        if not telemetry_dir.exists():
            raise FileNotFoundError(f"telemetry directory not found at {telemetry_dir.resolve()}")

        if columns is None:
            load_cols = list(REQUIRED_TELEMETRY_COLUMNS)
        else:
            load_cols = list(columns)
            for req in ["gateway_id", "ts_utc"]:
                if req not in load_cols:
                    load_cols.append(req)

        partition_files = sorted(telemetry_dir.glob("month=*/part-0.parquet"))
        if not partition_files:
            partition_files = sorted(telemetry_dir.glob("*.parquet"))

        if not partition_files:
            raise FileNotFoundError(f"No Parquet files found under {telemetry_dir.resolve()}")

        if months is not None:
            months_set = set(months)
            filtered = []
            for p in partition_files:
                p_name = p.parent.name
                if p_name.startswith("month="):
                    m = p_name.split("=", 1)[1]
                    if m in months_set:
                        filtered.append(p)
                else:
                    filtered.append(p)
            partition_files = filtered
            if not partition_files:
                raise FileNotFoundError(f"No Parquet partitions found matching months: {months}")

        dfs = []
        for p in partition_files:
            part = pd.read_parquet(p, columns=load_cols)
            dfs.append(part)

        combined = pd.concat(dfs, ignore_index=True)

        # Normalize IDs
        combined["gateway_id"] = combined["gateway_id"].apply(normalize_gateway_id)

        # Parse UTC timestamp
        combined["ts"] = pd.to_datetime(combined["ts_utc"], utc=True)
        if combined["ts"].isna().any():
            raise ValueError("telemetry partition contains null or unparseable timestamps in 'ts_utc'.")

        # Exact deduplication on (gateway_id, ts_utc)
        combined = combined.drop_duplicates(subset=["gateway_id", "ts_utc"], keep="first")

        # Unknown gateway filtering
        if filter_known_gateways:
            master = self.load_master()
            known_ids = set(master["gateway_id"])
            combined = combined[combined["gateway_id"].isin(known_ids)].copy()

        # Update per-month telemetry cache
        for m_str, m_group in combined.groupby(combined["ts"].dt.strftime("%Y-%m")):
            self._telemetry_cache[m_str] = m_group.copy()

        if months is None:
            self._telemetry_df = combined
        return combined.copy()

    def load_meter_reads(self) -> pd.DataFrame:
        """Loads and normalizes meter_read_success.csv for research and backtesting.

        Note: Research/backtesting infrastructure only. Not used in production predictions.
        Validates required columns: gateway_id, week_start, meters_expected, meters_read.
        Normalizes gateway_id to 12-character bare hex.
        Parses week_start into timezone-aware UTC datetime column 'week_start_dt'.
        """
        if self._meter_reads_df is not None:
            return self._meter_reads_df.copy()

        meter_path = self.data_dir / "meter_read_success.csv"
        if not meter_path.exists():
            raise FileNotFoundError(f"meter_read_success.csv not found at {meter_path.resolve()}")

        df = pd.read_csv(meter_path, dtype={"gateway_id": str})

        missing = [col for col in REQUIRED_METER_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"meter_read_success.csv missing required column(s): {missing}")

        df["gateway_id_raw"] = df["gateway_id"]
        df["gateway_id"] = df["gateway_id"].apply(normalize_gateway_id)
        df["week_start_dt"] = pd.to_datetime(df["week_start"], utc=True)
        if df["week_start_dt"].isna().any():
            raise ValueError("meter_read_success.csv contains null or unparseable dates in 'week_start'.")

        df["meters_expected"] = pd.to_numeric(df["meters_expected"], errors="coerce").fillna(0).astype(int)
        df["meters_read"] = pd.to_numeric(df["meters_read"], errors="coerce").fillna(0).astype(int)

        self._meter_reads_df = df
        return df.copy()
