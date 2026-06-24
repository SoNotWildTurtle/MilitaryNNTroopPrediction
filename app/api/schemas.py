"""Typed API response models and safe serialization helpers.

The API intentionally keeps analytical records flexible because MongoDB records may
come from different pipeline stages. These helpers still give OpenAPI consumers a
stable envelope and convert common database-only objects into JSON-safe values.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FlexibleModel(BaseModel):
    """Base model that allows forward-compatible analytical fields."""

    class Config:
        extra = "allow"


class ServiceIndex(BaseModel):
    """Friendly service index shown at the API root."""

    service: str
    status: str
    docs: str
    health: str
    readiness: str
    endpoints: List[str]


class HealthStatus(BaseModel):
    """No-dependency liveness response."""

    status: str


class ReadinessStatus(BaseModel):
    """Lightweight readiness summary that avoids ML and database calls."""

    status: str
    data_dir: str
    data_dir_exists: bool
    database_name: str
    sentinel_configured: bool


class PredictionStatus(BaseModel):
    """Response returned after the prediction pipeline is launched."""

    status: str


class AnalyticalRecord(FlexibleModel):
    """JSON-safe analytical record returned from MongoDB-backed endpoints."""

    id: Optional[str] = Field(default=None, description="Stringified MongoDB _id when present")


def json_safe(value: Any) -> Any:
    """Convert common database/runtime values into JSON-safe structures."""

    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        from bson import ObjectId  # type: ignore
    except Exception:  # pragma: no cover - bson may not be importable outside pymongo installs
        ObjectId = ()  # type: ignore
    if ObjectId and isinstance(value, ObjectId):
        return str(value)
    return value


def public_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return a public, JSON-safe copy of one analytical record."""

    safe_record = json_safe(record)
    if isinstance(safe_record, dict) and "_id" in safe_record:
        safe_record["id"] = str(safe_record.pop("_id"))
    return safe_record


def public_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return public, JSON-safe copies of analytical records."""

    return [public_record(record) for record in records]
