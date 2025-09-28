"""FastAPI service exposing prediction endpoints and a simple web GUI."""

from pathlib import Path
from typing import List, Dict

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..pipeline import realtime
from ..movement_history import recent_detections, recent_predictions

app = FastAPI(title="Troop Movement Prediction API")

# Serve the static web GUI at /gui
ROOT = Path(__file__).resolve().parents[2]
app.mount("/gui", StaticFiles(directory=ROOT / "web", html=True), name="gui")


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
