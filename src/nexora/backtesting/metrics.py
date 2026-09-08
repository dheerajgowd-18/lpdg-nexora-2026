"""
Evaluation metrics module for NEXORA 2026 historical backtesting.
Computes operational dispatch capture, yields, false alarm rates, Top-K curves,
and descriptive economic proxies.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def compute_weekly_metrics(
    ranked_df: pd.DataFrame,
    target_df: pd.DataFrame,
    strategy_name: str,
    week_start: str,
    k_cap: int = 15,
) -> dict[str, Any]:
    """Computes operational evaluation metrics for a single decision Monday T.

    Args:
        ranked_df: DataFrame with columns [gateway_id, rank, score] sorted by rank ascending.
        target_df: DataFrame with columns [gateway_id, target_category] from TargetConstructor.
        strategy_name: Name of candidate ranking strategy.
        week_start: Monday date string (YYYY-MM-DD).
        k_cap: Number of selected gateways (default 15).

    Returns:
        Dictionary of computed weekly metrics.
    """
    # Join ranking with target categories
    merged = ranked_df.merge(target_df, on="gateway_id", how="left")
    merged["target_category"] = merged["target_category"].fillna("UNOBSERVED")

    # Universe ground truth totals
    total_attributable_repairs = int((target_df["target_category"] == "REPAIR_REQUIRED").sum())
    total_attributable_fa = int((target_df["target_category"] == "FALSE_ALARM").sum())
    total_attributable_inc = int((target_df["target_category"] == "INCONCLUSIVE").sum())
    total_attributable_dispatches = total_attributable_repairs + total_attributable_fa + total_attributable_inc

    # Top-K slice
    top_k = merged[merged["rank"] <= k_cap].copy()
    actual_k = len(top_k)

    repairs_in_top15 = int((top_k["target_category"] == "REPAIR_REQUIRED").sum())
    fa_in_top15 = int((top_k["target_category"] == "FALSE_ALARM").sum())
    inc_in_top15 = int((top_k["target_category"] == "INCONCLUSIVE").sum())
    unobserved_in_top15 = int((top_k["target_category"] == "UNOBSERVED").sum())

    # Metric A: Repair Capture @ 15
    repair_capture = (
        float(repairs_in_top15) / total_attributable_repairs
        if total_attributable_repairs > 0
        else 0.0
    )

    # Metric B: Repair Yield @ 15
    repair_yield = float(repairs_in_top15) / actual_k if actual_k > 0 else 0.0

    # Metric C: False Alarm Rate @ 15
    false_alarm_rate = float(fa_in_top15) / actual_k if actual_k > 0 else 0.0

    # Metric D: Precision-like Repair Proportion on observed dispatches
    observed_in_top15 = repairs_in_top15 + fa_in_top15
    precision_like_prop = (
        float(repairs_in_top15) / observed_in_top15
        if observed_in_top15 > 0
        else 0.0
    )

    # Metric E: Missed Repairs
    missed_repairs = total_attributable_repairs - repairs_in_top15

    # Metric F: Top-K capture for K=5, 10, 15
    repairs_top5 = int((merged[merged["rank"] <= 5]["target_category"] == "REPAIR_REQUIRED").sum())
    repairs_top10 = int((merged[merged["rank"] <= 10]["target_category"] == "REPAIR_REQUIRED").sum())

    # Metric G: Economic Proxies
    fa_cost_proxy = fa_in_top15 * 380.0
    # Note: 600 is per week unaddressed. This proxy measures 1-week unaddressed penalty.
    missed_repair_cost_proxy = missed_repairs * 600.0

    return {
        "strategy": strategy_name,
        "week_start": week_start,
        "eligible_universe": len(target_df),
        "selected_k": actual_k,
        "total_repairs": total_attributable_repairs,
        "total_false_alarms": total_attributable_fa,
        "total_inconclusive": total_attributable_inc,
        "total_dispatches": total_attributable_dispatches,
        "repairs_top5": repairs_top5,
        "repairs_top10": repairs_top10,
        "repairs_top15": repairs_in_top15,
        "false_alarms_top15": fa_in_top15,
        "inconclusive_top15": inc_in_top15,
        "unobserved_top15": unobserved_in_top15,
        "repair_capture_at_15": repair_capture,
        "repair_yield_at_15": repair_yield,
        "false_alarm_rate_at_15": false_alarm_rate,
        "precision_like_proportion": precision_like_prop,
        "missed_repairs": missed_repairs,
        "fa_cost_proxy": fa_cost_proxy,
        "missed_repair_cost_proxy": missed_repair_cost_proxy,
    }


def compute_top_k_curve(
    ranked_df: pd.DataFrame,
    target_df: pd.DataFrame,
    strategy_name: str,
    max_k: int = 15,
) -> list[dict[str, Any]]:
    """Computes cumulative repair counts for K = 1..max_k for a single week."""
    merged = ranked_df.merge(target_df, on="gateway_id", how="left")
    merged["target_category"] = merged["target_category"].fillna("UNOBSERVED")

    records = []
    for k in range(1, max_k + 1):
        top_k = merged[merged["rank"] <= k]
        repairs = int((top_k["target_category"] == "REPAIR_REQUIRED").sum())
        fa = int((top_k["target_category"] == "FALSE_ALARM").sum())
        records.append({
            "strategy": strategy_name,
            "k": k,
            "repairs_captured": repairs,
            "false_alarms": fa,
        })
    return records


def compute_strategy_summary(weekly_results_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates weekly backtest metrics per strategy into macro summary and stability statistics."""
    grouped = weekly_results_df.groupby("strategy")

    summary_rows = []
    for name, group in grouped:
        total_weeks = len(group)
        total_eligible = group["eligible_universe"].sum()
        total_repairs = group["total_repairs"].sum()
        total_repairs_top15 = group["repairs_top15"].sum()
        total_fa_top15 = group["false_alarms_top15"].sum()
        total_inc_top15 = group["inconclusive_top15"].sum()
        total_unobserved_top15 = group["unobserved_top15"].sum()
        total_selected = group["selected_k"].sum()

        overall_capture = (
            float(total_repairs_top15) / total_repairs if total_repairs > 0 else 0.0
        )
        overall_yield = (
            float(total_repairs_top15) / total_selected if total_selected > 0 else 0.0
        )
        overall_fa_rate = (
            float(total_fa_top15) / total_selected if total_selected > 0 else 0.0
        )
        observed_selections = total_repairs_top15 + total_fa_top15
        overall_precision_like = (
            float(total_repairs_top15) / observed_selections
            if observed_selections > 0
            else 0.0
        )
        total_missed = group["missed_repairs"].sum()
        total_fa_cost = group["fa_cost_proxy"].sum()
        total_missed_cost = group["missed_repair_cost_proxy"].sum()

        summary_rows.append({
            "strategy": name,
            "total_weeks": total_weeks,
            "total_repairs_captured": total_repairs_top15,
            "total_repairs_available": total_repairs,
            "overall_repair_capture": overall_capture,
            "overall_repair_yield": overall_yield,
            "overall_false_alarm_rate": overall_fa_rate,
            "overall_precision_like_prop": overall_precision_like,
            "total_false_alarms": total_fa_top15,
            "total_inconclusive": total_inc_top15,
            "total_unobserved": total_unobserved_top15,
            "total_missed_repairs": total_missed,
            "total_fa_cost_proxy_eur": total_fa_cost,
            "total_missed_repair_cost_proxy_eur": total_missed_cost,
            # Stability statistics across the 26 weeks
            "weekly_capture_mean": group["repair_capture_at_15"].mean(),
            "weekly_capture_std": group["repair_capture_at_15"].std(),
            "weekly_capture_min": group["repair_capture_at_15"].min(),
            "weekly_capture_max": group["repair_capture_at_15"].max(),
            "weekly_yield_mean": group["repair_yield_at_15"].mean(),
            "weekly_yield_std": group["repair_yield_at_15"].std(),
            "weekly_yield_min": group["repair_yield_at_15"].min(),
            "weekly_yield_max": group["repair_yield_at_15"].max(),
            "weekly_fa_rate_mean": group["false_alarm_rate_at_15"].mean(),
            "weekly_fa_rate_std": group["false_alarm_rate_at_15"].std(),
        })

    return pd.DataFrame(summary_rows).sort_values("overall_repair_capture", ascending=False).reset_index(drop=True)
