"""FastAPI service exposing prediction endpoints and lightweight health checks."""

from __future__ import annotations

from typing import List

from fastapi import FastAPI, HTTPException, Query

from ..config import settings
from ..movement_history import recent_detections, recent_predictions
from .schemas import (
    AnalyticalRecord,
    HealthStatus,
    PredictionStatus,
    ReadinessStatus,
    ServiceIndex,
    public_records,
)

app = FastAPI(
    title="Troop Movement Prediction API",
    description=(
        "Readiness and analytical endpoints for a defensive, local-first troop "
        "movement prediction toolkit."
    ),
    version="0.2.0",
)


@app.get("/", response_model=ServiceIndex)
def index() -> ServiceIndex:
    """Return a friendly service index for browsers, scripts, and new users."""

    return ServiceIndex(
        service="Troop Movement Prediction API",
        status="ok",
        docs="/docs",
        health="/healthz",
        readiness="/readyz",
        endpoints=[
            "POST /predict/{area}",
            "GET /detections/{area}",
            "GET /predictions/{area}",
        ],
    )


@app.get("/healthz", response_model=HealthStatus)
def healthz() -> HealthStatus:
    """Return a no-dependency liveness check."""

    return HealthStatus(status="ok")


@app.get("/readyz", response_model=ReadinessStatus)
def readyz() -> ReadinessStatus:
    """Return lightweight readiness information without running ML or database calls."""

    data_dir = settings.DATA_DIR
    return ReadinessStatus(
        status="ok",
        data_dir=str(data_dir),
        data_dir_exists=data_dir.exists(),
        database_name=settings.DB_NAME,
        sentinel_configured=bool(
            settings.SENTINEL_CLIENT_ID
            and settings.SENTINEL_CLIENT_SECRET
            and settings.SENTINEL_INSTANCE_ID
        ),
    )


@app.post("/predict/{area}", response_model=PredictionStatus)
def predict(area: str, model_path: str) -> PredictionStatus:
    """Run the real-time pipeline for a given area.

    The heavy TensorFlow/YOLO pipeline is imported lazily so the API can still
    start, self-document, and answer health checks in a minimal core install.
    """

    try:
        from ..pipeline import realtime
    except ImportError as exc:  # pragma: no cover - depends on optional packages
        raise HTTPException(
            status_code=503,
            detail=(
                "Prediction pipeline dependencies are not installed. Install "
                "requirements-optional.txt or run quickstart with the optional profile."
            ),
        ) from exc

    realtime.process_area(area, model_path)
    return PredictionStatus(status="ok")


@app.get("/detections/{area}", response_model=List[AnalyticalRecord])
def detections(
    area: str,
    limit: int = Query(default=10, ge=1, le=100, description="maximum records to return"),
) -> List[dict]:
    """Return recent detections for an area as JSON-safe public records."""

    return public_records(recent_detections(area, limit))


@app.get("/predictions/{area}", response_model=List[AnalyticalRecord])
def predictions(
    area: str,
    limit: int = Query(default=10, ge=1, le=100, description="maximum records to return"),
) -> List[dict]:
    """Return recent trajectory predictions for an area as JSON-safe public records."""

    return public_records(recent_predictions(area, limit))
