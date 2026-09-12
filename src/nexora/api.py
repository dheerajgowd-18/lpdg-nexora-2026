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
from .pipeline import predict_week


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

def _parse_and_validate_monday(week_start: str) -> dt.date:
    """Parses date string and validates that it represents a supported competition Monday."""
    try:
        t_date = dt.date.fromisoformat(week_start)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {week_start!r}. Expected YYYY-MM-DD.",
        )

    if t_date not in SCORED_WEEKS:
        valid_options = [w.isoformat() for w in SCORED_WEEKS]
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unsupported week_start: {week_start}. "
                f"Must be one of the 8 scored competition Mondays: {valid_options}"
            ),
        )
    return t_date


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    """Factory creating the FastAPI application with configurable data directory."""
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
        target_week = week_start or SCORED_WEEKS[-1].isoformat()
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
        t_date = _parse_and_validate_monday(week_start)
        master_df: pd.DataFrame = app.state.master_df
        telemetry_df: pd.DataFrame = app.state.telemetry_df

        # Call existing production prediction engine
        preds_df = predict_week(master_df, telemetry_df, t_date, top_k=VISITS_PER_WEEK)

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
        target_week = week_start or SCORED_WEEKS[-1].isoformat()
        t_date = _parse_and_validate_monday(target_week)
        master_df: pd.DataFrame = app.state.master_df
        telemetry_df: pd.DataFrame = app.state.telemetry_df

        if not (master_df["gateway_id"] == canonical_id).any():
            raise HTTPException(status_code=404, detail=f"Unknown gateway ID: {canonical_id}")

        predictions = predict_week(master_df, telemetry_df, t_date, top_k=VISITS_PER_WEEK)
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
        """Reloads mounted data, then computes a current weekly recommendation list."""
        _reload_data(app)
        return get_predictions(week_start=request.week_start)

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
            try:
                target_date = dt.date.fromisoformat(week_start)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format for week_start: {week_start!r}. Expected YYYY-MM-DD.",
                )
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
