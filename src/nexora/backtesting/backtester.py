"""
Historical backtesting simulation engine for NEXORA 2026.
Orchestrates feature extraction, candidate strategy ranking, target resolution,
metrics evaluation, and machine-readable output generation across the 26 historical Mondays.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Sequence
import pandas as pd

from ..data_loader import DataLoader
from ..feature_extractor import FeatureExtractor
from ..target_constructor import TargetConstructor
from .strategies import ALL_STRATEGIES, CandidateStrategy
from .metrics import compute_weekly_metrics, compute_top_k_curve, compute_strategy_summary


class HistoricalBacktester:
    """Simulates weekly gateway prioritization across historical decision Mondays."""

    HISTORICAL_MONDAYS = [
        (pd.Timestamp("2025-08-04") + pd.Timedelta(days=7 * i)).strftime("%Y-%m-%d")
        for i in range(26)
    ]

    def __init__(
        self,
        strategies: Sequence[CandidateStrategy] | None = None,
        data_dir: str | Path = "data",
        output_dir: str | Path = "reports/backtest",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.strategies = list(strategies) if strategies is not None else ALL_STRATEGIES
        self.loader = DataLoader(data_dir=self.data_dir)
        self.extractor = FeatureExtractor(data_loader=self.loader)
        self.target_constructor = TargetConstructor(data_loader=self.loader)

        self.weekly_results_df: pd.DataFrame | None = None
        self.summary_df: pd.DataFrame | None = None
        self.top_k_df: pd.DataFrame | None = None
        self.rankings_df: pd.DataFrame | None = None

    def run(self, mondays: Sequence[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Runs the backtest across specified historical decision Mondays.

        Args:
            mondays: List of Monday date strings (default: the 26 historical Mondays).

        Returns:
            Tuple of (weekly_results_df, summary_df).
        """
        test_mondays = list(mondays) if mondays is not None else self.HISTORICAL_MONDAYS

        weekly_records = []
        top_k_records = []
        rankings_records = []
        weekly_target_repairs: dict[str, int] = {}

        print(f"Starting historical backtest across {len(test_mondays)} weeks for {len(self.strategies)} strategies...")

        for week_idx, monday_str in enumerate(test_mondays, 1):
            m_date = dt.date.fromisoformat(monday_str)
            print(f"  [{week_idx:02d}/{len(test_mondays):02d}] Evaluating decision Monday {monday_str}...")

            # 1. Extract pre-decision features (strictly t < T)
            features = self.extractor.extract(monday_str)

            # 2. Construct operational target (requested_on in [T, T+7d))
            targets = self.target_constructor.construct_weekly_target(
                monday_str, timing_basis="requested_on"
            )
            w_target_repairs = int((targets["target_category"] == "REPAIR_REQUIRED").sum())
            weekly_target_repairs[monday_str] = w_target_repairs

            # 3. Evaluate each strategy
            for strat in self.strategies:
                ranked = strat.rank(features, m_date)

                # Compute standard weekly metrics @ 15
                w_metrics = compute_weekly_metrics(
                    ranked_df=ranked,
                    target_df=targets,
                    strategy_name=strat.name,
                    week_start=monday_str,
                    k_cap=15,
                )
                if w_metrics["total_repairs"] != w_target_repairs:
                    raise ValueError(
                        f"Target mismatch for strategy {strat.name} on {monday_str}: "
                        f"{w_metrics['total_repairs']} vs {w_target_repairs}"
                    )
                weekly_records.append(w_metrics)

                # Compute Top-K curves (K = 1..15)
                w_topk = compute_top_k_curve(
                    ranked_df=ranked,
                    target_df=targets,
                    strategy_name=strat.name,
                    max_k=15,
                )
                for item in w_topk:
                    item["week_start"] = monday_str
                    top_k_records.append(item)

                # Save Top-15 rankings
                top15 = ranked.head(15).copy()
                top15 = top15.merge(
                    targets[["gateway_id", "target_category", "is_positive_repair", "is_delayed_realization"]],
                    on="gateway_id",
                    how="left",
                )
                top15["target_category"] = top15["target_category"].fillna("UNOBSERVED")
                top15["week_start"] = monday_str
                rankings_records.append(top15)

        self.weekly_results_df = pd.DataFrame(weekly_records)

        # Invariant Check: All strategies evaluated for the same week must have identical total_repairs
        for m_str, w_group in self.weekly_results_df.groupby("week_start"):
            unique_totals = w_group["total_repairs"].unique()
            if len(unique_totals) != 1:
                raise ValueError(
                    f"Invariant violation: Differing total_repairs counts across strategies "
                    f"for week {m_str}: {dict(zip(w_group['strategy'], w_group['total_repairs']))}"
                )
            if unique_totals[0] != weekly_target_repairs[m_str]:
                raise ValueError(
                    f"Invariant violation: Strategy total_repairs ({unique_totals[0]}) != target data "
                    f"({weekly_target_repairs[m_str]}) for week {m_str}"
                )

        self.summary_df = compute_strategy_summary(self.weekly_results_df)

        # Aggregate Top-K curves across all evaluated weeks
        top_k_raw = pd.DataFrame(top_k_records)
        top_k_agg = (
            top_k_raw.groupby(["strategy", "k"])
            .agg(
                total_repairs_captured=("repairs_captured", "sum"),
                total_false_alarms=("false_alarms", "sum"),
            )
            .reset_index()
        )
        
        # Denominator derived directly from ground truth target data across evaluated weeks
        total_available_repairs = sum(weekly_target_repairs.values())

        top_k_agg["cumulative_repair_capture"] = (
            top_k_agg["total_repairs_captured"] / total_available_repairs
            if total_available_repairs > 0
            else 0.0
        )
        self.top_k_df = top_k_agg

        self.rankings_df = pd.concat(rankings_records, ignore_index=True)

        return self.weekly_results_df, self.summary_df

    def save_results(self, output_dir: str | Path | None = None) -> dict[str, Path]:
        """Saves machine-readable CSV artifacts under output_dir."""
        out = Path(output_dir) if output_dir is not None else self.output_dir
        out.mkdir(parents=True, exist_ok=True)

        if self.weekly_results_df is None or self.summary_df is None:
            raise RuntimeError("Must call run() before save_results()")

        paths = {
            "weekly_results": out / "backtest_weekly_results.csv",
            "summary": out / "backtest_summary.csv",
            "top_k": out / "backtest_topk.csv",
            "rankings": out / "backtest_rankings.csv",
        }

        self.weekly_results_df.to_csv(paths["weekly_results"], index=False)
        self.summary_df.to_csv(paths["summary"], index=False)
        self.top_k_df.to_csv(paths["top_k"], index=False)
        self.rankings_df.to_csv(paths["rankings"], index=False)

        print(f"Successfully saved backtest artifacts to {out.resolve()}:")
        for k, p in paths.items():
            print(f"  - {k}: {p.name}")

        return paths
