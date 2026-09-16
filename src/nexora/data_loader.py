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
        ValueError: If gateway_id is null, empty, or cannot be normalized to a 12-character hex string.
    """
    if gateway_id is None or pd.isna(gateway_id):
        raise ValueError("Gateway ID cannot be null or NaN.")
    if not isinstance(gateway_id, str):
        gateway_id = str(gateway_id)
    text = gateway_id.strip()
    if not text:
        raise ValueError("Gateway ID cannot be empty.")
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
        Validates required columns, canonicalizes gateway_id, enforces lifecycle integrity
        (installed_on <= decommissioned_on), and parses lifecycle dates into timezone-aware
        UTC timestamps ('installed_on_dt', 'decommissioned_on_dt').
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

        # Disallow duplicate gateway registrations in master asset register
        dup_gateways = df[df.duplicated(subset=["gateway_id"], keep=False)]
        if not dup_gateways.empty:
            raise ValueError(f"gateway_master.csv contains duplicate gateway ID: '{dup_gateways.iloc[0]['gateway_id']}'.")

        # Parse installed_on
        raw_installed = df["installed_on"].astype(str).str.strip()
        if (raw_installed == "").any() or df["installed_on"].isna().any():
            raise ValueError("gateway_master.csv contains null or empty 'installed_on' dates.")
        df["installed_on_dt"] = pd.to_datetime(df["installed_on"], utc=True, errors="coerce")
        if df["installed_on_dt"].isna().any():
            raise ValueError("gateway_master.csv contains unparseable dates in 'installed_on'.")

        # Parse decommissioned_on if present
        if "decommissioned_on" in df.columns:
            raw_decomm = df["decommissioned_on"].dropna().astype(str).str.strip()
            raw_decomm_nonempty = raw_decomm[raw_decomm != ""]
            if not raw_decomm_nonempty.empty:
                test_parsed = pd.to_datetime(raw_decomm_nonempty, utc=True, errors="coerce")
                if test_parsed.isna().any():
                    raise ValueError("gateway_master.csv contains unparseable dates in 'decommissioned_on'.")
            df["decommissioned_on_dt"] = pd.to_datetime(df["decommissioned_on"], utc=True)
        else:
            df["decommissioned_on_dt"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")

        # Lifecycle validity: installed_on <= decommissioned_on where both exist
        both_mask = df["installed_on_dt"].notna() & df["decommissioned_on_dt"].notna()
        if both_mask.any():
            invalid_lifecycle = df[both_mask & (df["installed_on_dt"] > df["decommissioned_on_dt"])]
            if not invalid_lifecycle.empty:
                bad_row = invalid_lifecycle.iloc[0]
                raise ValueError(
                    f"gateway_master.csv contains invalid lifecycle for gateway '{bad_row['gateway_id']}': "
                    f"installed_on ({bad_row['installed_on']}) > decommissioned_on ({bad_row['decommissioned_on']})."
                )

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
            Deterministic deduplication on (gateway_id, normalized UTC timestamp 'ts', and measurement values),
            followed by fail-fast conflict detection on canonical logical key (gateway_id, ts).

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

        # Parse UTC timestamp into canonical normalized UTC 'ts'
        combined["ts"] = pd.to_datetime(combined["ts_utc"], utc=True, errors="coerce")
        if combined["ts"].isna().any():
            # Fall back to mixed format inference for heterogeneous string formats (e.g. ISO-8601 vs space vs offset)
            combined["ts"] = pd.to_datetime(combined["ts_utc"], utc=True, format="mixed", errors="coerce")
            if combined["ts"].isna().any():
                raise ValueError("telemetry partition contains null or unparseable timestamps in 'ts_utc'.")

        # 1. Deterministic deduplication of identical observations using (gateway_id, ts) and measurement values
        measurement_cols = [c for c in combined.columns if c not in ("gateway_id", "ts", "ts_utc")]
        combined = combined.drop_duplicates(subset=["gateway_id", "ts"] + measurement_cols)

        # 2. Conflicting duplicates check on canonical logical key (gateway_id, ts)
        conflicting = combined[combined.duplicated(subset=["gateway_id", "ts"], keep=False)]
        if not conflicting.empty:
            first_bad = conflicting.iloc[0]
            raise ValueError(
                f"Conflicting telemetry duplicates detected for gateway '{first_bad['gateway_id']}' "
                f"at normalized UTC timestamp '{first_bad['ts']}' with differing measurement values."
            )

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
        Enforces Monday requirement on week_start.
        Applies strict numeric integer validation on meter counts and verifies meters_read <= meters_expected.
        Safely deduplicates identical rows while failing on conflicting logical duplicates.
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

        # Validate and parse week_start
        raw_week = df["week_start"].astype(str).str.strip()
        if (raw_week == "").any() or df["week_start"].isna().any():
            raise ValueError("meter_read_success.csv contains null or empty 'week_start' dates.")
        df["week_start_dt"] = pd.to_datetime(df["week_start"], utc=True, errors="coerce")
        if df["week_start_dt"].isna().any():
            raise ValueError("meter_read_success.csv contains null or unparseable dates in 'week_start'.")

        # Monday requirement: weekly reporting contract
        if (df["week_start_dt"].dt.weekday != 0).any():
            non_mondays = df[df["week_start_dt"].dt.weekday != 0]["week_start"].tolist()
            raise ValueError(f"meter_read_success.csv contains non-Monday week_start: {non_mondays[:3]}")

        # Strict numeric validation of meters_expected and meters_read
        for col in ["meters_expected", "meters_read"]:
            if df[col].isna().any():
                raise ValueError(f"meter_read_success.csv contains null values in '{col}'.")
            numeric_s = pd.to_numeric(df[col], errors="coerce")
            if numeric_s.isna().any():
                raise ValueError(f"meter_read_success.csv contains non-numeric values in '{col}'.")
            if (numeric_s < 0).any():
                raise ValueError(f"meter_read_success.csv contains negative values in '{col}'.")
            if not (numeric_s == numeric_s.round()).all():
                raise ValueError(f"meter_read_success.csv contains decimal values in integer column '{col}'.")
            df[col] = numeric_s.astype(int)

        # Invariant: meters_read cannot exceed meters_expected
        invalid_ratio = df[df["meters_read"] > df["meters_expected"]]
        if not invalid_ratio.empty:
            bad = invalid_ratio.iloc[0]
            raise ValueError(
                f"meter_read_success.csv contains records where meters_read ({bad['meters_read']}) > "
                f"meters_expected ({bad['meters_expected']}) for gateway '{bad['gateway_id']}' at '{bad['week_start']}'."
            )

        # Deduplication: identical duplicate records collapsed
        df = df.drop_duplicates()

        # Conflicting duplicates check on (gateway_id, week_start_dt)
        conflicts = df[df.duplicated(subset=["gateway_id", "week_start_dt"], keep=False)]
        if not conflicts.empty:
            bad_row = conflicts.iloc[0]
            raise ValueError(
                f"Conflicting meter read duplicates detected for gateway '{bad_row['gateway_id']}' at week '{bad_row['week_start']}'."
            )

        self._meter_reads_df = df
        return df.copy()
