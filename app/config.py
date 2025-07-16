"""Configuration management for the troop prediction app."""

from pathlib import Path
from typing import Any, Dict
import os


class Settings:
    """Application settings with defaults that may be overridden by environment variables."""

    def __init__(self) -> None:
        self.DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
        self.MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.DB_NAME: str = os.getenv("DB_NAME", "troop_db")
        self.SENTINEL_CLIENT_ID: str = os.getenv("SENTINEL_CLIENT_ID", "")
        self.SENTINEL_CLIENT_SECRET: str = os.getenv("SENTINEL_CLIENT_SECRET", "")
        self.SENTINEL_INSTANCE_ID: str = os.getenv("SENTINEL_INSTANCE_ID", "")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "DATA_DIR": str(self.DATA_DIR),
            "MONGO_URI": self.MONGO_URI,
            "DB_NAME": self.DB_NAME,
            "SENTINEL_CLIENT_ID": self.SENTINEL_CLIENT_ID,
            "SENTINEL_CLIENT_SECRET": self.SENTINEL_CLIENT_SECRET,
            "SENTINEL_INSTANCE_ID": self.SENTINEL_INSTANCE_ID,
        }


settings = Settings()
