"""CLI to set up configuration values in a .env file."""
from pathlib import Path
from typing import Optional

from ..config import settings
from ..translation import translate_text

_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


ENV_VARS = [
    ("DATA_DIR", "Directory to store data"),
    ("MONGO_URI", "MongoDB connection string"),
    ("DB_NAME", "MongoDB database name"),
    ("SENTINEL_CLIENT_ID", "Sentinel Hub client ID"),
    ("SENTINEL_CLIENT_SECRET", "Sentinel Hub client secret"),
    ("SENTINEL_INSTANCE_ID", "Sentinel Hub instance ID"),
]


def prompt(var: str, desc: str, default: Optional[str] = None) -> str:
    value = input(f"{_t(desc)} [{default or ''}]: ").strip()
    return value or (default or "")


def run_config_setup(path: Path = Path('.env')) -> None:
    """Prompt for configuration values and write them to a .env file."""
    existing = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                existing[k.strip()] = v.strip()
    lines = []
    for var, desc in ENV_VARS:
        val = prompt(var, desc, existing.get(var))
        lines.append(f"{var}={val}")
    path.write_text("\n".join(lines) + "\n")
    print(_t("Configuration saved to"), path)


if __name__ == "__main__":
    run_config_setup()
