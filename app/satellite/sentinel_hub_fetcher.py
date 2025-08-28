"""Fetch satellite images using Sentinel Hub API."""
from pathlib import Path
from datetime import datetime
import os
from typing import Dict

import requests

from ..config import settings

TOKEN_URL = "https://services.sentinel-hub.com/oauth/token"
WMS_URL = "https://services.sentinel-hub.com/ogc/wms"


def _get_token() -> str:
    """Return an OAuth token using configured credentials."""
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.SENTINEL_CLIENT_ID,
            "client_secret": settings.SENTINEL_CLIENT_SECRET,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _bbox(area: str) -> str:
    """Return a simple bounding box for a named area.

    In a production deployment this could map area identifiers to
    real coordinates or query a geospatial database.
    """

    predefined: Dict[str, str] = {
        "kyiv": "30.239,50.302,30.659,50.541",
        "kharkiv": "36.15,49.9,36.5,50.1",
    }
    return predefined.get(area, "30,50,31,51")


def download_image(area: str) -> Path:
    """Retrieve a WMS tile for the given area.

    If Sentinel Hub credentials are not configured, an empty file is
    created to keep the pipeline running in demo mode.
    """

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    dest = settings.DATA_DIR / f"{area}_{ts}.tif"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not (
        settings.SENTINEL_CLIENT_ID
        and settings.SENTINEL_CLIENT_SECRET
        and settings.SENTINEL_INSTANCE_ID
    ):
        print("Sentinel credentials not configured; creating placeholder image")
        dest.touch()
        return dest

    token = _get_token()
    params = {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": "1.3.0",
        "LAYERS": "TRUE_COLOR",
        "BBOX": _bbox(area),
        "FORMAT": "image/tiff",
        "WIDTH": 512,
        "HEIGHT": 512,
        "TIME": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{WMS_URL}/{settings.SENTINEL_INSTANCE_ID}"
    print(f"Downloading Sentinel image for {area} -> {dest}")
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    with open(dest, "wb") as f:
        f.write(response.content)
    return dest
