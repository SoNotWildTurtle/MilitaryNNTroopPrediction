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


def _check_mongo(timeout: float) -> CheckResult:
    host_port = settings.MONGO_URI.removeprefix("mongodb://").split("/", 1)[0].split("@")[-1]
    host, _, port_text = host_port.partition(":")
    port = int(port_text or "27017")
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return CheckResult("mongo_socket", "ok", f"Connected to {host}:{port}")
    except Exception as exc:  # noqa: BLE001 - diagnostics should preserve connection failures.
        return CheckResult(
            "mongo_socket",
            "warn",
            f"Could not connect to {host}:{port}: {exc}",
            (
                "Start MongoDB, update MONGO_URI, or continue with workflows "
                "that do not require the database."
            ),
        )


def run_checks(
    include_optional: bool = True,
    check_mongo: bool = True,
    timeout: float = 2.0,
) -> list[CheckResult]:
    """Run project preflight checks and return structured results."""

    results: list[CheckResult] = [
        CheckResult("python", "ok", sys.version.split()[0]),
        _check_data_dir(),
        _check_env(),
    ]
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
        "--timeout",
        type=float,
        default=2.0,
        help="socket timeout for external checks",
    )
    args = parser.parse_args(argv)

    results = run_checks(
        include_optional=not args.skip_optional,
        check_mongo=not args.skip_mongo,
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
