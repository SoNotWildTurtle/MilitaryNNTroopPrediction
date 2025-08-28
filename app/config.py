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
        }


settings = Settings()
