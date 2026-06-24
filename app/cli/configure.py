"""CLI to set up configuration values in a .env file."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Optional, Sequence


ENV_VARS = [
    ("DATA_DIR", "Directory to store data", "data"),
    ("MONGO_URI", "MongoDB connection string", "mongodb://localhost:27017"),
    ("DB_NAME", "MongoDB database name", "troop_db"),
    ("SENTINEL_CLIENT_ID", "Sentinel Hub client ID", ""),
    ("SENTINEL_CLIENT_SECRET", "Sentinel Hub client secret", ""),
    ("SENTINEL_INSTANCE_ID", "Sentinel Hub instance ID", ""),
]


def load_env(path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from an env file."""

    existing: dict[str, str] = {}
    if not path.exists():
        return existing
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        existing[key.strip()] = value.strip()
    return existing


def prompt(var: str, desc: str, default: Optional[str] = None) -> str:
    """Prompt for a configuration value, preserving the default when blank."""

    value = input(f"{desc} [{default or ''}]: ").strip()
    return value or (default or "")


def _render_env(values: dict[str, str]) -> str:
    lines = []
    for var, _, default in ENV_VARS:
        lines.append(f"{var}={values.get(var, default)}")
    return "\n".join(lines) + "\n"


def write_default_env(path: Path = Path(".env"), overwrite: bool = False) -> bool:
    """Create a .env file from .env.example or built-in defaults.

    Returns True when a file is written and False when an existing file is kept.
    """

    if path.exists() and not overwrite:
        return False

    template = Path(".env.example")
    if template.exists():
        shutil.copyfile(template, path)
    else:
        defaults = {var: default for var, _, default in ENV_VARS}
        path.write_text(_render_env(defaults), encoding="utf-8")
    return True


def run_config_setup(
    path: Path = Path(".env"),
    non_interactive: bool = False,
    overwrite: bool = False,
) -> None:
    """Create or update a .env file for local runs."""

    if non_interactive:
        wrote = write_default_env(path, overwrite=overwrite)
        if wrote:
            print(f"Configuration template written to {path}")
        else:
            print(f"Configuration already exists at {path}; use --overwrite to replace it")
        return

    existing = load_env(path)
    values: dict[str, str] = {}
    for var, desc, default in ENV_VARS:
        values[var] = prompt(var, desc, existing.get(var, default))
    path.write_text(_render_env(values), encoding="utf-8")
    print(f"Configuration saved to {path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or update a local .env file.")
    parser.add_argument("--path", type=Path, default=Path(".env"), help="env file path to write")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="write defaults from .env.example without prompting",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace an existing env file")
    args = parser.parse_args(argv)

    run_config_setup(
        path=args.path,
        non_interactive=args.non_interactive,
        overwrite=args.overwrite,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
