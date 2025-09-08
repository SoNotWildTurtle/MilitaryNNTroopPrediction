"""Data ingestion from OSINT and satellite sources."""

from pathlib import Path
from typing import Iterable

from .satellite import sentinel_hub_fetcher

from .config import settings


def ingest_osint(files: Iterable[Path]) -> None:
    """Placeholder for ingesting OSINT data files."""
    for path in files:
        # TODO: parse and store relevant fields
        print(f"Ingesting OSINT data from {path}")


def fetch_satellite_images(area: str) -> Path:
    """Retrieve satellite imagery using the Sentinel Hub fetcher."""
    print(f"Fetching satellite imagery for {area}")
    return sentinel_hub_fetcher.download_image(area)
