"""FastAPI service exposing prediction endpoints."""

from fastapi import FastAPI
from typing import List, Dict

from ..pipeline import realtime
from ..movement_history import recent_detections, recent_predictions

app = FastAPI(title="Troop Movement Prediction API")


@app.post("/predict/{area}")
def predict(area: str, model_path: str):
    """Run the real-time pipeline for a given area."""
    realtime.process_area(area, model_path)
    return {"status": "ok"}


@app.get("/detections/{area}")
def detections(area: str, limit: int = 10) -> List[Dict]:
    """Return recent detections for an area."""
    return recent_detections(area, limit)


@app.get("/predictions/{area}")
def predictions(area: str, limit: int = 10) -> List[Dict]:
    """Return recent trajectory predictions for an area."""
    return recent_predictions(area, limit)
