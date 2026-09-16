"""FastAPI service for NEXORA 2026 Predictive Maintenance.

Exposes the validated production Baseline_3Sigma prediction engine via a clean REST API:
- GET  /health
- GET  /predictions/{week_start}
- GET  /gateways/{gateway_id}
- POST /run

Acts strictly as an interface layer without modifying scoring or ranking logic.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import datetime as dt
import os
from pathlib import Path
import threading
from typing import Any, Sequence

from fastapi import FastAPI, HTTPException, Path as PathParam, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd
from pydantic import BaseModel, Field

from .config import (
    MAX_REASON_CHARS,
    SCORED_WEEKS,
    VISITS_PER_WEEK,
)
from .data_loader import DataLoader, is_valid_gateway_id, normalize_gateway_id
from .eligibility import get_eligible_gateways
from .strategy import (
    PredictionStrategy,
    PredictionService,
    default_prediction_service,
)


# =============================================================================
# Response & Request Models
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"


class Prediction(BaseModel):
    """Individual gateway predictive maintenance recommendation."""
    week_start: str = Field(..., description="Decision Monday cutoff date (YYYY-MM-DD)")
    rank: int = Field(..., ge=1, le=15, description="Priority rank (1-15)")
    gateway_id: str = Field(..., description="Canonical 12-char uppercase hex gateway identifier")
    score: float = Field(..., ge=0.0, description="Baseline_3Sigma breach count score")
    reason: str = Field(..., max_length=MAX_REASON_CHARS, description="Observational non-causal reason string")


class PredictionResponse(BaseModel):
    """List of recommendations for a decision Monday."""
    week_start: str
    count: int
    predictions: list[Prediction]


class GatewayResponse(BaseModel):
    """Factual metadata and eligibility status for a gateway asset."""
    gateway_id: str
    installed_on: str
    decommissioned_on: str | None = None
    region: str | None = None
    week_start: str | None = None
    is_eligible: bool | None = None


class GatewayExplanationResponse(BaseModel):
    """A gateway's selection status and explanation for one decision Monday."""
    gateway_id: str
    week_start: str
    selected: bool
    rank: int | None = None
    score: float | None = None
    reason: str


class RunRequest(BaseModel):
    """Programmatic prediction execution request."""
    week_start: str = Field(..., description="Decision Monday date in YYYY-MM-DD format")


# =============================================================================
# Lifespan Management
# =============================================================================

def _ensure_data_loaded(app: FastAPI) -> None:
    """Ensures master and telemetry datasets are loaded into app.state."""
    if not hasattr(app.state, "master_df") or not hasattr(app.state, "telemetry_df") or app.state.master_df is None:
        _reload_data(app)


def _is_monday_supported(t_date: dt.date, telemetry_df: pd.DataFrame | None) -> bool:
    """Checks whether a Monday is supported either as a scored week or via unseen telemetry."""
    if t_date in SCORED_WEEKS:
        return True
    if telemetry_df is not None and not telemetry_df.empty and "ts" in telemetry_df.columns:
        min_ts = telemetry_df["ts"].min().date()
        max_ts = telemetry_df["ts"].max().date()
        # Case 1: Unseen month data extending beyond standard competition horizon
        if max_ts > dt.date(2026, 3, 31):
            if min_ts <= t_date <= max_ts + dt.timedelta(days=7):
                return True
        # Case 2: Synthetic test environment whose date range is entirely outside SCORED_WEEKS
        data_overlaps_scored = any(min_ts <= w <= max_ts + dt.timedelta(days=7) for w in SCORED_WEEKS)
        if not data_overlaps_scored:
            if min_ts <= t_date <= max_ts + dt.timedelta(days=7):
                return True
    return False


def _discover_latest_monday(app: FastAPI) -> dt.date:
    """Determines the latest available decision Monday from loaded data and competition weeks."""
    _ensure_data_loaded(app)
    if hasattr(app.state, "telemetry_df") and app.state.telemetry_df is not None:
        telemetry_df: pd.DataFrame = app.state.telemetry_df
        if not telemetry_df.empty and "ts" in telemetry_df.columns:
            max_ts = telemetry_df["ts"].max().date()
            # If telemetry extends past the standard competition period (unseen month)
            if max_ts > dt.date(2026, 3, 31):
                curr = SCORED_WEEKS[-1] + dt.timedelta(days=7)
                latest_unseen: dt.date | None = None
                while curr - dt.timedelta(days=1) <= max_ts:
                    if curr.weekday() == 0:
                        latest_unseen = curr
                    curr += dt.timedelta(days=7)
                if latest_unseen is not None:
                    return latest_unseen

            # If telemetry is within standard competition period
            covered_scored = [w for w in SCORED_WEEKS if w - dt.timedelta(days=1) <= max_ts]
            if covered_scored:
                return max(covered_scored)

            # Synthetic dataset outside SCORED_WEEKS
            min_ts = telemetry_df["ts"].min().date()
            if max_ts >= min_ts:
                candidate = max_ts
                while candidate >= min_ts:
                    if candidate.weekday() == 0:
                        return candidate
                    candidate -= dt.timedelta(days=1)

    return SCORED_WEEKS[-1]


def _parse_and_validate_monday(week_start: str, app: FastAPI | None = None) -> dt.date:
    """Parses date string and validates that it represents a supported decision Monday."""
    if app is not None:
        _ensure_data_loaded(app)
    try:
        t_date = dt.date.fromisoformat(week_start)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {week_start!r}. Expected YYYY-MM-DD.",
        )

    if t_date.weekday() != 0:
        raise HTTPException(
            status_code=404,
            detail=f"Unsupported week_start: {week_start}. Must be a Monday.",
        )

    telemetry_df = getattr(app.state, "telemetry_df", None) if app is not None else None
    if _is_monday_supported(t_date, telemetry_df):
        return t_date

    valid_options = [w.isoformat() for w in SCORED_WEEKS]
    raise HTTPException(
        status_code=404,
        detail=(
            f"Unsupported week_start: {week_start}. "
            f"Must be one of the 8 scored competition Mondays: {valid_options}"
        ),
    )


def create_app(
    data_dir: str | Path | None = None,
    prediction_service: PredictionService | None = None,
    strategy: PredictionStrategy | None = None,
) -> FastAPI:
    """Factory creating the FastAPI application with configurable data directory and strategy."""
    effective_data_dir = Path(data_dir or os.getenv("NEXORA_DATA_DIR", "data"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _reload_data(app)
        yield

    app = FastAPI(
        title="NEXORA 2026 Predictive Maintenance Service",
        description=(
            "REST API exposing the authoritative Baseline_3Sigma gateway anomaly "
            "ranking engine for the LPDG Innovation Hub Selection Challenge 2026."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.data_dir = effective_data_dir
    app.state.run_lock = threading.Lock()
    if prediction_service is not None:
        app.state.prediction_service = prediction_service
    elif strategy is not None:
        app.state.prediction_service = PredictionService(strategy=strategy)
    else:
        app.state.prediction_service = PredictionService()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
    def health_check() -> HealthResponse:
        """Liveness and health check endpoint."""
        return HealthResponse(status="ok")

    @app.get(
        "/predictions",
        response_model=PredictionResponse,
        tags=["Predictions"],
        summary="Retrieve this week's 15 recommendations (or specified week)",
    )
    def get_current_predictions(
        week_start: str | None = Query(
            None,
            description="Optional decision Monday date (YYYY-MM-DD). Defaults to latest scored week.",
        ),
    ) -> PredictionResponse:
        """Ask for this week's 15 gateways to visit. Defaults to the latest competition Monday."""
        target_week = week_start or _discover_latest_monday(app).isoformat()
        return get_predictions(week_start=target_week)

    @app.get(
        "/predictions/{week_start}",
        response_model=PredictionResponse,
        tags=["Predictions"],
        summary="Retrieve Top-15 recommendations for a decision Monday",
    )
    def get_predictions(
        week_start: str = PathParam(..., description="Decision Monday date (YYYY-MM-DD)"),
    ) -> PredictionResponse:
        """Computes and returns the 15 gateways most worth visiting for the specified Monday."""
        t_date = _parse_and_validate_monday(week_start, app=app)
        master_df: pd.DataFrame = app.state.master_df
        telemetry_df: pd.DataFrame = app.state.telemetry_df

        # Call active prediction service (strategy pattern)
        preds_df = app.state.prediction_service.predict(
            master_df=master_df,
            telemetry_df=telemetry_df,
            decision_monday=t_date,
            top_k=VISITS_PER_WEEK,
        )

        records = [Prediction(**row) for row in preds_df.to_dict(orient="records")]
        return PredictionResponse(
            week_start=t_date.isoformat(),
            count=len(records),
            predictions=records,
        )

    @app.get(
        "/gateways/{gateway_id}/explanation",
        response_model=GatewayExplanationResponse,
        tags=["Gateways"],
        summary="Explain why a particular gateway is where it is (rank/score/reason)",
    )
    def get_gateway_explanation(
        gateway_id: str = PathParam(..., description="12-character hexadecimal gateway identifier"),
        week_start: str | None = Query(
            None,
            description="Optional decision Monday date (YYYY-MM-DD). Defaults to latest scored week.",
        ),
    ) -> GatewayExplanationResponse:
        """Returns the selected rank, score, and reason explaining why a gateway is where it is."""
        if not is_valid_gateway_id(gateway_id):
            raise HTTPException(
                status_code=400,
                detail=f"Malformed gateway ID: {gateway_id!r}. Expected 12-char hex string.",
            )

        canonical_id = normalize_gateway_id(gateway_id)
        target_week = week_start or _discover_latest_monday(app).isoformat()
        t_date = _parse_and_validate_monday(target_week, app=app)
        master_df: pd.DataFrame = app.state.master_df
        telemetry_df: pd.DataFrame = app.state.telemetry_df

        if not (master_df["gateway_id"] == canonical_id).any():
            raise HTTPException(status_code=404, detail=f"Unknown gateway ID: {canonical_id}")

        predictions = app.state.prediction_service.predict(
            master_df=master_df,
            telemetry_df=telemetry_df,
            decision_monday=t_date,
            top_k=VISITS_PER_WEEK,
        )
        match = predictions[predictions["gateway_id"] == canonical_id]
        if match.empty:
            return GatewayExplanationResponse(
                gateway_id=canonical_id,
                week_start=t_date.isoformat(),
                selected=False,
                reason="Not selected in this week's top-15 recommendations.",
            )

        row = match.iloc[0]
        return GatewayExplanationResponse(
            gateway_id=canonical_id,
            week_start=t_date.isoformat(),
            selected=True,
            rank=int(row["rank"]),
            score=float(row["score"]),
            reason=str(row["reason"]),
        )

    @app.post(
        "/run",
        response_model=PredictionResponse,
        tags=["Predictions"],
        summary="Execute prediction for a decision Monday",
    )
    def run_prediction(request: RunRequest) -> PredictionResponse:
        """Reloads mounted data, validates candidate state, and atomically updates API state."""
        with app.state.run_lock:
            # 1. Parse date syntax
            try:
                t_date = dt.date.fromisoformat(request.week_start)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: {request.week_start!r}. Expected YYYY-MM-DD.",
                )

            # 2. Validate Monday requirement
            if t_date.weekday() != 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unsupported week_start: {request.week_start}. Must be a Monday.",
                )

            # 3. Reload candidate data from disk bypassing cache
            candidate_loader = DataLoader(data_dir=app.state.data_dir)
            try:
                candidate_master = candidate_loader.load_master()
                candidate_telemetry = candidate_loader.load_telemetry()
            except FileNotFoundError as e:
                raise HTTPException(status_code=500, detail=f"Data reload failed: {e}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Data reload error: {e}")

            # 4. Validate candidate dataframes
            if candidate_master is None or candidate_master.empty or "gateway_id" not in candidate_master.columns:
                raise HTTPException(status_code=500, detail="Invalid master data: empty or missing required columns.")
            if candidate_telemetry is None or candidate_telemetry.empty or "ts" not in candidate_telemetry.columns:
                raise HTTPException(status_code=500, detail="Invalid telemetry data: empty or missing required columns.")

            # 5. Validate whether requested week is supported in the candidate telemetry
            if not _is_monday_supported(t_date, candidate_telemetry):
                valid_options = [w.isoformat() for w in SCORED_WEEKS]
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Unsupported week_start: {request.week_start}. "
                        f"Must be one of the 8 scored competition Mondays: {valid_options}"
                    ),
                )

            # 6. Compute candidate predictions
            try:
                candidate_preds = app.state.prediction_service.predict(
                    master_df=candidate_master,
                    telemetry_df=candidate_telemetry,
                    decision_monday=t_date,
                    top_k=VISITS_PER_WEEK,
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Prediction computation failed: {e}")

            # 7. Validate complete candidate result
            if len(candidate_preds) != VISITS_PER_WEEK:
                raise HTTPException(
                    status_code=500,
                    detail=f"Prediction result invalid: expected {VISITS_PER_WEEK} rows, got {len(candidate_preds)}.",
                )
            if len(set(candidate_preds["gateway_id"])) != VISITS_PER_WEEK:
                raise HTTPException(
                    status_code=500,
                    detail="Prediction result invalid: duplicate gateway IDs detected.",
                )

            # 8. Atomically replace application state
            app.state.loader = candidate_loader
            app.state.master_df = candidate_master
            app.state.telemetry_df = candidate_telemetry

            # 9. Return validated predictions
            records = [Prediction(**row) for row in candidate_preds.to_dict(orient="records")]
            return PredictionResponse(
                week_start=t_date.isoformat(),
                count=len(records),
                predictions=records,
            )

    @app.get(
        "/gateways/{gateway_id}",
        response_model=GatewayResponse,
        tags=["Gateways"],
        summary="Retrieve asset metadata and lifecycle eligibility",
    )
    def get_gateway_info(
        gateway_id: str = PathParam(..., description="12-character hexadecimal gateway identifier"),
        week_start: str | None = Query(
            None,
            description="Optional decision Monday to evaluate lifecycle eligibility (YYYY-MM-DD)",
        ),
    ) -> GatewayResponse:
        """Returns factual master asset metadata and optional lifecycle eligibility status."""
        if not is_valid_gateway_id(gateway_id):
            raise HTTPException(
                status_code=400,
                detail=f"Malformed gateway ID: {gateway_id!r}. Expected 12-char hex string.",
            )

        canonical_id = normalize_gateway_id(gateway_id)
        _ensure_data_loaded(app)
        master_df: pd.DataFrame = app.state.master_df

        matched = master_df[master_df["gateway_id"] == canonical_id]
        if matched.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown gateway ID: {canonical_id}",
            )

        row = matched.iloc[0]
        installed_str = str(row["installed_on"])
        decomm_str = None if pd.isna(row.get("decommissioned_on")) else str(row["decommissioned_on"])
        region_str = None if pd.isna(row.get("region")) else str(row["region"])

        is_eligible = None
        if week_start is not None:
            target_date = _parse_and_validate_monday(week_start, app=app)
            eligible_fleet = get_eligible_gateways(master_df, target_date)
            is_eligible = canonical_id in set(eligible_fleet)

        return GatewayResponse(
            gateway_id=canonical_id,
            installed_on=installed_str,
            decommissioned_on=decomm_str,
            region=region_str,
            week_start=week_start,
            is_eligible=is_eligible,
        )

    # Mount evaluator frontend interface if directory exists
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    if frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


def _reload_data(app: FastAPI) -> None:
    """Reload challenge inputs and replace API state only after both loads succeed.

    A fresh loader intentionally bypasses its per-instance cache. This lets POST /run
    discover a new ``month=YYYY-MM`` partition added to the mounted data directory
    while the API process remains running.
    """
    loader = DataLoader(data_dir=app.state.data_dir)
    master_df = loader.load_master()
    telemetry_df = loader.load_telemetry()
    app.state.loader = loader
    app.state.master_df = master_df
    app.state.telemetry_df = telemetry_df


# Module-level default application instance for uvicorn nexora.api:app
app = create_app()
