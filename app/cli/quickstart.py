"""Guided first-run automation for local project setup.

The quickstart command ties together the safe setup path for new users: install a
chosen dependency profile, create a local .env when needed, run diagnostics, and
optionally launch the API. It does not run detection or prediction by itself.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.cli import configure, doctor


REQUIREMENTS_BY_PROFILE = {
    "core": Path("requirements-core.txt"),
    "optional": Path("requirements-optional.txt"),
    "full": Path("requirements-optional.txt"),
}


@dataclass(frozen=True)
class QuickstartOptions:
    """Options controlling the first-run setup flow."""

    install_profile: str = "core"
    skip_install: bool = False
    env_path: Path = Path(".env")
    overwrite_env: bool = False
    skip_optional_checks: bool = True
    skip_mongo: bool = True
    launch_api: bool = False
    host: str = "127.0.0.1"
    port: int = 8000


def _run_command(command: Sequence[str], label: str) -> None:
    """Run a setup command with a friendly heading."""

    print(f"\n==> {label}")
    print("$ " + " ".join(command))
    subprocess.run(command, check=True)


def _requirements_for_profile(profile: str) -> Path:
    try:
        return REQUIREMENTS_BY_PROFILE[profile]
    except KeyError as exc:
        valid = ", ".join(sorted(REQUIREMENTS_BY_PROFILE))
        raise ValueError(f"Unknown install profile {profile!r}; choose one of: {valid}") from exc


def run_quickstart(options: QuickstartOptions) -> int:
    """Run the quickstart flow and return a shell-friendly exit code."""

    if not options.skip_install:
        requirements = _requirements_for_profile(options.install_profile)
        _run_command(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
            f"Install {options.install_profile} dependencies",
        )
    else:
        print("\n==> Skipping dependency install")

    print("\n==> Ensure local configuration exists")
    configure.run_config_setup(
        path=options.env_path,
        non_interactive=True,
        overwrite=options.overwrite_env,
    )

    print("\n==> Run setup doctor")
    results = doctor.run_checks(
        include_optional=not options.skip_optional_checks,
        check_mongo=not options.skip_mongo,
    )
    doctor._print_text(results)
    _, _, failures = doctor.summarize(results)
    if failures:
        print("\nQuickstart stopped because required setup checks failed.")
        return 1

    print("\nQuickstart complete. Core setup is ready.")
    if options.launch_api:
        _run_command(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.api.main:app",
                "--host",
                options.host,
                "--port",
                str(options.port),
            ],
            "Launch API",
        )
    else:
        print("Next: run `python -m app.cli.dashboard` or `bash scripts/start.sh`.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install, configure, diagnose, and optionally launch the local API."
    )
    parser.add_argument(
        "--install-profile",
        choices=sorted(REQUIREMENTS_BY_PROFILE),
        default="core",
        help="dependency set to install before checks",
    )
    parser.add_argument("--skip-install", action="store_true", help="do not run pip install")
    parser.add_argument("--env-path", type=Path, default=Path(".env"), help="env file path to create")
    parser.add_argument("--overwrite-env", action="store_true", help="replace an existing env file")
    parser.add_argument(
        "--check-optional",
        action="store_true",
        help="include optional ML/dashboard/GIS imports in doctor checks",
    )
    parser.add_argument(
        "--check-mongo",
        action="store_true",
        help="include MongoDB socket connectivity in doctor checks",
    )
    parser.add_argument("--launch-api", action="store_true", help="launch FastAPI after successful checks")
    parser.add_argument("--host", default="127.0.0.1", help="API host when --launch-api is used")
    parser.add_argument("--port", type=int, default=8000, help="API port when --launch-api is used")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_quickstart(
        QuickstartOptions(
            install_profile=args.install_profile,
            skip_install=args.skip_install,
            env_path=args.env_path,
            overwrite_env=args.overwrite_env,
            skip_optional_checks=not args.check_optional,
            skip_mongo=not args.check_mongo,
            launch_api=args.launch_api,
            host=args.host,
            port=args.port,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
