"""Configuration management for the troop prediction app."""

from pathlib import Path
from typing import Any, Dict
import os

def _load_dotenv(path: Path) -> None:
    """Populate environment variables from a simple .env file if present."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if '=' in line:
            key, val = line.split('=', 1)
            os.environ.setdefault(key.strip(), val.strip())

_load_dotenv(Path('.env'))


class Settings:
    """Application settings with defaults that may be overridden by environment variables."""

    def __init__(self) -> None:
        self.DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
        self.MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.DB_NAME: str = os.getenv("DB_NAME", "troop_db")
        self.SENTINEL_CLIENT_ID: str = os.getenv("SENTINEL_CLIENT_ID", "")
        self.SENTINEL_CLIENT_SECRET: str = os.getenv("SENTINEL_CLIENT_SECRET", "")
        self.SENTINEL_INSTANCE_ID: str = os.getenv("SENTINEL_INSTANCE_ID", "")
        self.UI_LANG: str = os.getenv("UI_LANG", "en")
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.SOURCE_CATALOG: Path = Path(os.getenv("SOURCE_CATALOG", "sources.json"))
        self.CAMERA_WEIGHT: float = float(os.getenv("CAMERA_WEIGHT", "1.0"))
        self.LIDAR_WEIGHT: float = float(os.getenv("LIDAR_WEIGHT", "1.0"))
        self.BLUETOOTH_WEIGHT: float = float(os.getenv("BLUETOOTH_WEIGHT", "1.0"))
        self.TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")
        self.RESOLUTION_SCALE: float = float(os.getenv("RESOLUTION_SCALE", "1.0"))
        self.FEATURE_RICHNESS: float = float(os.getenv("FEATURE_RICHNESS", "1.0"))
        high_memory_raw = os.getenv("HIGH_MEMORY_MODE", "0").lower()
        self.HIGH_MEMORY_MODE: bool = high_memory_raw in {"1", "true", "yes", "on"}

    def as_dict(self) -> Dict[str, Any]:
        return {
            "DATA_DIR": str(self.DATA_DIR),
            "MONGO_URI": self.MONGO_URI,
            "DB_NAME": self.DB_NAME,
            "SENTINEL_CLIENT_ID": self.SENTINEL_CLIENT_ID,
            "SENTINEL_CLIENT_SECRET": self.SENTINEL_CLIENT_SECRET,
            "SENTINEL_INSTANCE_ID": self.SENTINEL_INSTANCE_ID,
            "UI_LANG": self.UI_LANG,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "SOURCE_CATALOG": str(self.SOURCE_CATALOG),
            "CAMERA_WEIGHT": self.CAMERA_WEIGHT,
            "LIDAR_WEIGHT": self.LIDAR_WEIGHT,
            "BLUETOOTH_WEIGHT": self.BLUETOOTH_WEIGHT,
            "TWILIO_ACCOUNT_SID": self.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": self.TWILIO_AUTH_TOKEN,
            "TWILIO_FROM_NUMBER": self.TWILIO_FROM_NUMBER,
            "RESOLUTION_SCALE": self.RESOLUTION_SCALE,
            "FEATURE_RICHNESS": self.FEATURE_RICHNESS,
            "HIGH_MEMORY_MODE": self.HIGH_MEMORY_MODE,
        }


settings = Settings()
