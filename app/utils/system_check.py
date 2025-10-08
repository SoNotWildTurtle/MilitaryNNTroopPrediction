"""Utilities for validating environment prerequisites."""

from __future__ import annotations

import importlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from app.config import settings


@dataclass
class CheckResult:
    """Represents the outcome of a single installation check."""

    name: str
    status: str
    detail: str

    def is_ok(self) -> bool:
        """Return ``True`` when the check passed."""

        return self.status == "pass"


# Modules the application expects to be present for core workflows.
REQUIRED_MODULES: Dict[str, str] = {
    "fastapi": "FastAPI web framework",
    "pymongo": "MongoDB client",
    "torch": "PyTorch deep learning runtime",
    "ultralytics": "Ultralytics YOLO utilities",
    "cv2": "OpenCV image processing",
}


# Optional integrations that unlock enhanced workflows.
OPTIONAL_MODULES: Dict[str, str] = {
    "tensorflow": "TensorFlow GPU runtime",
    "tensorflow_cpu": "TensorFlow CPU runtime",
    "transformers": "Transformers-based translation",
    "folium": "Folium map visualisation",
}


def _import_exists(module_name: str) -> bool:
    """Return ``True`` if ``module_name`` can be imported."""

    try:
        importlib.import_module(module_name)
        return True
    except ModuleNotFoundError:
        return False
    except Exception:
        return False


def _module_checks(modules: Dict[str, str], *, required: bool) -> List[CheckResult]:
    """Check a series of modules and return results."""

    results: List[CheckResult] = []
    for module_name, description in modules.items():
        available = _import_exists(module_name if module_name != "tensorflow_cpu" else "tensorflow")
        status = "pass" if available else ("fail" if required else "warn")
        detail = "available" if available else "missing"
        label = f"{description} ({module_name})"
        results.append(CheckResult(label, status, detail))
    return results


def _check_data_directory() -> CheckResult:
    """Ensure the configured data directory exists or can be created."""

    path: Path = settings.DATA_DIR
    try:
        path.mkdir(parents=True, exist_ok=True)
        detail = str(path)
        return CheckResult("Data directory", "pass", detail)
    except Exception as exc:  # pragma: no cover - very rare unless filesystem broken
        return CheckResult("Data directory", "fail", f"unable to create: {exc}")


def _check_twilio_credentials() -> CheckResult:
    """Warn when SMS credentials are absent to avoid silent failures."""

    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER:
        return CheckResult("Twilio configuration", "pass", "configured")
    return CheckResult("Twilio configuration", "warn", "not configured")


def _check_email_credentials() -> CheckResult:
    """Warn when SMTP credentials are missing."""

    if settings.EMAIL_SMTP_HOST and settings.EMAIL_FROM_ADDRESS:
        return CheckResult("Email configuration", "pass", "configured")
    return CheckResult("Email configuration", "warn", "not configured")


def _check_openai_credentials() -> CheckResult:
    """Warn if ChatGPT discovery is enabled without an API key."""

    if settings.OPENAI_API_KEY:
        return CheckResult("OpenAI API key", "pass", "set")
    return CheckResult("OpenAI API key", "warn", "not set")


def _check_gpu_tools() -> CheckResult:
    """Report whether GPU tooling is accessible on this host."""

    if shutil.which("nvidia-smi"):
        return CheckResult("GPU tooling", "pass", "nvidia-smi available")
    return CheckResult("GPU tooling", "warn", "GPU utilities not detected")


def run_installation_checks(*, include_optional: bool = True) -> List[CheckResult]:
    """Run installation checks and return a list of results."""

    results: List[CheckResult] = [_check_data_directory()]
    results.extend(_module_checks(REQUIRED_MODULES, required=True))
    if include_optional:
        results.extend(_module_checks(OPTIONAL_MODULES, required=False))
    results.extend(
        [
            _check_twilio_credentials(),
            _check_email_credentials(),
            _check_openai_credentials(),
            _check_gpu_tools(),
        ]
    )
    return results


def results_to_json(results: Iterable[CheckResult]) -> str:
    """Serialise ``results`` to a JSON string."""

    payload = [
        {"name": res.name, "status": res.status, "detail": res.detail}
        for res in results
    ]
    return json.dumps(payload, indent=2)
