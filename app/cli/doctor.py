"""Preflight diagnostics for the troop prediction project.

This module is intentionally read-only: it checks local setup, dependency
availability, writable paths, optional Sentinel credentials, and optional
MongoDB connectivity without running detection or prediction.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse

from app.config import settings


REQUIRED_IMPORTS: tuple[tuple[str, str], ...] = (
    ("fastapi", "FastAPI API server"),
    ("pymongo", "MongoDB client"),
    ("PIL", "Pillow image processing"),
    ("uvicorn", "ASGI server"),
)

OPTIONAL_IMPORTS: tuple[tuple[str, str], ...] = (
    ("tensorflow", "trajectory model training/inference"),
    ("albumentations", "dataset augmentation"),
    ("cv2", "OpenCV image/video processing"),
    ("ultralytics", "YOLO training/inference"),
    ("sklearn", "clustering and statistics"),
    ("matplotlib", "heatmap generation"),
    ("rich", "interactive CLI dashboard"),
    ("folium", "HTML map generation"),
)

SENTINEL_ENV_VARS: tuple[str, ...] = (
    "SENTINEL_CLIENT_ID",
    "SENTINEL_CLIENT_SECRET",
    "SENTINEL_INSTANCE_ID",
)

RECOMMENDED_ENV_VARS: tuple[str, ...] = (
    "DATA_DIR",
    "MONGO_URI",
    "DB_NAME",
    *SENTINEL_ENV_VARS,
)


@dataclass
class CheckResult:
    """Single diagnostic check result."""

    name: str
    status: str
    detail: str
    remediation: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _check_imports(imports: Iterable[tuple[str, str]], required: bool) -> list[CheckResult]:
    results: list[CheckResult] = []
    for module_name, purpose in imports:
        available = _module_available(module_name)
        if available:
            results.append(CheckResult(f"import:{module_name}", "ok", purpose))
        else:
            severity = "fail" if required else "warn"
            remediation = (
                "Run `bash scripts/setup.sh` or install the missing package in "
                "your virtual environment."
            )
            results.append(CheckResult(f"import:{module_name}", severity, purpose, remediation))
    return results


def _read_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _ = line.split("=", 1)
        keys.add(key.strip())
    return keys


def _check_env_template(template_path: Path = Path(".env.example")) -> CheckResult:
    if not template_path.exists():
        return CheckResult(
            "env_template",
            "warn",
            f"{template_path} is missing",
            "Add .env.example so new users can bootstrap configuration safely.",
        )

    missing = sorted(set(RECOMMENDED_ENV_VARS) - _read_env_keys(template_path))
    if missing:
        return CheckResult(
            "env_template",
            "warn",
            f"{template_path} is missing keys: {', '.join(missing)}",
            "Keep .env.example aligned with app.config.Settings.",
        )
    return CheckResult("env_template", "ok", f"{template_path} includes recommended keys")


def _check_local_env(env_path: Path = Path(".env")) -> CheckResult:
    if not env_path.exists():
        return CheckResult(
            "local_env",
            "warn",
            f"{env_path} has not been created yet",
            "Run `python -m app.cli.configure --non-interactive` for defaults, "
            "or `python -m app.cli.configure` for interactive setup.",
        )

    missing = sorted(set(RECOMMENDED_ENV_VARS) - _read_env_keys(env_path))
    if missing:
        return CheckResult(
            "local_env",
            "warn",
            f"{env_path} is missing keys: {', '.join(missing)}",
            "Run `python -m app.cli.configure` to fill missing values.",
        )
    return CheckResult("local_env", "ok", f"{env_path} includes recommended keys")


def _check_data_dir() -> CheckResult:
    data_dir = Path(settings.DATA_DIR)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return CheckResult("data_dir", "ok", f"{data_dir} exists and is writable")
    except OSError as exc:
        return CheckResult(
            "data_dir",
            "fail",
            f"{data_dir} is not writable: {exc}",
            "Set DATA_DIR to a writable directory or fix filesystem permissions.",
        )


def _check_env() -> CheckResult:
    missing = [name for name in SENTINEL_ENV_VARS if not os.getenv(name)]
    if not missing:
        return CheckResult("sentinel_env", "ok", "Sentinel Hub environment variables are set")
    return CheckResult(
        "sentinel_env",
        "warn",
        f"Missing optional Sentinel Hub variables: {', '.join(missing)}",
        (
            "Run `python -m app.cli.configure` if you want live Sentinel Hub imagery. "
            "Placeholder imagery is used otherwise."
        ),
    )


def _mongo_host_port() -> tuple[str, int]:
    parsed = urlparse(settings.MONGO_URI)
    if parsed.scheme == "mongodb+srv":
        # SRV discovery is handled by pymongo. A raw socket probe cannot resolve
        # the final host:port accurately, so use the standard TLS MongoDB port.
        return parsed.hostname or "localhost", 27017
    if parsed.scheme and parsed.hostname:
        return parsed.hostname, parsed.port or 27017

    host_port = settings.MONGO_URI.split("/", 1)[0].split("@")[-1]
    host, _, port_text = host_port.partition(":")
    return host or "localhost", int(port_text or "27017")


def _check_mongo(timeout: float) -> CheckResult:
    try:
        host, port = _mongo_host_port()
        with socket.create_connection((host, port), timeout=timeout):
            return CheckResult("mongo_socket", "ok", f"Connected to {host}:{port}")
    except Exception as exc:  # noqa: BLE001 - diagnostics should preserve connection failures.
        return CheckResult(
            "mongo_socket",
            "warn",
            f"Could not connect using MONGO_URI={settings.MONGO_URI!r}: {exc}",
            (
                "Start MongoDB, update MONGO_URI, or continue with workflows "
                "that do not require the database."
            ),
        )


def run_checks(
    include_optional: bool = True,
    check_mongo: bool = True,
    check_env_files: bool = True,
    timeout: float = 2.0,
) -> list[CheckResult]:
    """Run project preflight checks and return structured results."""

    results: list[CheckResult] = [CheckResult("python", "ok", sys.version.split()[0])]
    if check_env_files:
        results.extend([_check_env_template(), _check_local_env()])
    results.extend([
        _check_data_dir(),
        _check_env(),
    ])
    results.extend(_check_imports(REQUIRED_IMPORTS, required=True))
    if include_optional:
        results.extend(_check_imports(OPTIONAL_IMPORTS, required=False))
    if check_mongo:
        results.append(_check_mongo(timeout))
    return results


def summarize(results: Sequence[CheckResult]) -> tuple[int, int, int]:
    """Return ok, warning, and failure counts."""

    ok = sum(1 for result in results if result.status == "ok")
    warn = sum(1 for result in results if result.status == "warn")
    fail = sum(1 for result in results if result.status == "fail")
    return ok, warn, fail


def _print_text(results: Sequence[CheckResult]) -> None:
    ok, warn, fail = summarize(results)
    print(f"Preflight summary: {ok} ok, {warn} warnings, {fail} failures")
    for result in results:
        marker = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[result.status]
        print(f"[{marker}] {result.name}: {result.detail}")
        if result.remediation:
            print(f"      fix: {result.remediation}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether the local project setup is ready to run."
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--skip-optional",
        action="store_true",
        help="only check core runtime dependencies",
    )
    parser.add_argument(
        "--skip-mongo",
        action="store_true",
        help="do not test MongoDB socket connectivity",
    )
    parser.add_argument(
        "--skip-env-files",
        action="store_true",
        help="do not check .env.example or local .env presence",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="socket timeout for external checks",
    )
    args = parser.parse_args(argv)

    results = run_checks(
        include_optional=not args.skip_optional,
        check_mongo=not args.skip_mongo,
        check_env_files=not args.skip_env_files,
        timeout=args.timeout,
    )
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        _print_text(results)

    _, _, failures = summarize(results)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
