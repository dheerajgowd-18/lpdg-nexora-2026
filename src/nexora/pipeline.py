"""Production pipeline orchestrator for NEXORA 2026.

Executes the frozen 12-stage production architecture:
1. Data loading
2. Schema validation
3. ID normalization
4. Telemetry deduplication
5. Lifecycle eligibility
6. Temporal cutoff [T-28d, T) and [T-7d, T)
7. Baseline_3Sigma scoring
8. Option B silent gateway alignment
9. Deterministic ranking (score desc, gateway_id asc)
10. Top-15 selection
11. Reason generation
12. Output validation and predictions.csv serialization
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys
import time
import pandas as pd

from .data_loader import DataLoader
from .eligibility import get_eligible_gateways
from .scoring import score_week
from .ranking import rank_and_select, VISITS_PER_WEEK
from .reasons import add_reasons
from .validation import validate_predictions_df, run_official_validator

SCORED_WEEKS = [
    dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)
]


def run_pipeline(
    data_dir: str | Path = "data",
    out_path: str | Path = "predictions.csv",
    scored_weeks: list[dt.date] = SCORED_WEEKS,
    run_validator: bool = True,
) -> pd.DataFrame:
    """Executes the authoritative NEXORA 2026 Part 1 production pipeline.

    Returns:
        The generated predictions DataFrame.
    """
    t0 = time.perf_counter()
    data_path = Path(data_dir)
    out_file = Path(out_path)

    print(f"[NEXORA Pipeline] Initializing production pipeline...")
    print(f"  Data directory: {data_path.resolve()}")
    print(f"  Target output:  {out_file.resolve()}")
    print(f"  Scored weeks:   {len(scored_weeks)} Mondays ({scored_weeks[0]} to {scored_weeks[-1]})")

    # 1. Load data
    loader = DataLoader(data_dir=data_path)
    t_load_start = time.perf_counter()
    print("[NEXORA Pipeline] Loading gateway_master.csv...")
    master_df = loader.load_master()
    print(f"  Loaded {len(master_df)} master asset records.")

    print("[NEXORA Pipeline] Loading and deduplicating telemetry partitions...")
    telemetry_df = loader.load_telemetry()
    t_load = time.perf_counter() - t_load_start
    print(f"  Telemetry loaded: {len(telemetry_df):,} rows processed across all partitions ({t_load:.2f}s).")

    # 2. Iterate through scored weeks
    weekly_frames = []
    t_score_start = time.perf_counter()

    for idx, monday in enumerate(scored_weeks, 1):
        w_t0 = time.perf_counter()
        
        # 5. Lifecycle eligibility
        eligible_ids = get_eligible_gateways(master_df, monday)

        # 6 & 7. Temporal cutoff & Baseline_3Sigma scoring
        scored_df = score_week(telemetry_df, monday)

        # 8, 9, 10. Silent gateway alignment, deterministic ranking, Top-15
        top_df = rank_and_select(scored_df, eligible_ids, top_k=VISITS_PER_WEEK)

        # 11. Reason generation
        top_df = add_reasons(top_df)

        top_df["week_start"] = monday.isoformat()
        final_week_cols = ["week_start", "rank", "gateway_id", "score", "reason"]
        weekly_frames.append(top_df[final_week_cols])

        w_time = time.perf_counter() - w_t0
        print(f"  Week {idx}/{len(scored_weeks)} [{monday}]: {len(eligible_ids)} eligible fleet | Top-15 selected ({w_time:.2f}s)")

    t_scoring = time.perf_counter() - t_score_start
    combined_df = pd.concat(weekly_frames, ignore_index=True)

    # 12. Internal validation
    print("[NEXORA Pipeline] Running internal production validation...")
    problems = validate_predictions_df(combined_df, scored_weeks=scored_weeks)
    if problems:
        for p in problems:
            print(f"  ERROR: {p}", file=sys.stderr)
        raise ValueError(f"Pipeline output failed internal validation with {len(problems)} errors.")
    print("  Internal validation PASSED with zero errors.")

    # Write predictions.csv
    out_file.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(out_file, index=False)
    print(f"[NEXORA Pipeline] Serialized {len(combined_df)} rows to {out_file.resolve()}")

    # Official submission validation
    if run_validator:
        print("[NEXORA Pipeline] Executing official validate_submission.py...")
        run_official_validator(out_file)
        print("  Official submission validation PASSED successfully (exit code 0).")

    total_time = time.perf_counter() - t0
    print(f"[NEXORA Pipeline] Execution completed successfully in {total_time:.2f}s!")
    print(f"  Data loading: {t_load:.2f}s | Scoring & ranking: {t_scoring:.2f}s")
    return combined_df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NEXORA 2026 Production Predictive Maintenance Pipeline (Baseline_3Sigma)"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data",
        help="Path to challenge data directory containing gateway_master.csv and telemetry/ (default: data)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="predictions.csv",
        help="Path to output predictions CSV file (default: predictions.csv)",
    )
    args = parser.parse_args()

    try:
        run_pipeline(data_dir=args.data, out_path=args.out)
    except Exception as exc:
        print(f"FATAL ERROR in pipeline execution: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
