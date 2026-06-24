"""FastAPI service exposing prediction endpoints and lightweight health checks."""

from __future__ import annotations

from typing import Dict, List

from fastapi import FastAPI, HTTPException, Query

from ..config import settings
from ..movement_history import recent_detections, recent_predictions

app = FastAPI(
    title="Troop Movement Prediction API",
    description=(
        "Readiness and analytical endpoints for a defensive, local-first troop "
        "movement prediction toolkit."
    ),
    version="0.2.0",
)


@app.get("/")
def index() -> Dict[str, object]:
    """Return a friendly service index for browsers, scripts, and new users."""

    return {
        "service": "Troop Movement Prediction API",
        "status": "ok",
        "docs": "/docs",
        "health": "/healthz",
        "readiness": "/readyz",
        "endpoints": [
            "POST /predict/{area}",
            "GET /detections/{area}",
            "GET /predictions/{area}",
        ],
    }


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    """Return a no-dependency liveness check."""

    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> Dict[str, object]:
    """Return lightweight readiness information without running ML or database calls."""

    data_dir = settings.DATA_DIR
    return {
        "status": "ok",
        "data_dir": str(data_dir),
        "data_dir_exists": data_dir.exists(),
        "database_name": settings.DB_NAME,
        "sentinel_configured": bool(
            settings.SENTINEL_CLIENT_ID
            and settings.SENTINEL_CLIENT_SECRET
            and settings.SENTINEL_INSTANCE_ID
        ),
    }


@app.post("/predict/{area}")
def predict(area: str, model_path: str) -> Dict[str, str]:
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
    return {"status": "ok"}


@app.get("/detections/{area}")
def detections(
    area: str,
    limit: int = Query(default=10, ge=1, le=100, description="maximum records to return"),
) -> List[Dict]:
    """Return recent detections for an area."""

    return recent_detections(area, limit)


@app.get("/predictions/{area}")
def predictions(
    area: str,
    limit: int = Query(default=10, ge=1, le=100, description="maximum records to return"),
) -> List[Dict]:
    """Return recent trajectory predictions for an area."""

    return recent_predictions(area, limit)
