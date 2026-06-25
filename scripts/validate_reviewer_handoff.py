#!/usr/bin/env python3
"""Validate reviewer-handoff.json without third-party dependencies.

This lightweight helper is intended for CI artifact consumers, release reviewers,
and local maintainers who want a quick contract check before parsing a diagnostics
bundle. It intentionally validates only the stable repository contract documented
in docs/reviewer_handoff_contract.md rather than implementing a full JSON Schema
engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = {
    "artifact_dir",
    "copyable_summary",
    "generated_at",
    "key_artifacts",
    "missing_expected",
    "missing_key_artifacts",
    "recommended_rerun",
    "release_status",
    "review_order",
    "review_status",
}

ALLOWED_REVIEW_STATUS = {
    "ready",
    "review_warnings",
    "needs_attention",
    "needs_review",
}

ALLOWED_REVIEW_ORDER_STATUS = {"present", "missing"}
REQUIRED_KEY_ARTIFACT_FIELDS = {"path", "present", "purpose"}
REQUIRED_REVIEW_ORDER_FIELDS = {"action", "artifact", "detail", "present", "status", "step"}


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_handoff(data: Any) -> list[str]:
    """Return a list of contract validation errors for a parsed handoff object."""

    errors: list[str] = []
    if not isinstance(data, dict):
        return ["handoff must be a JSON object"]

    missing = sorted(REQUIRED_TOP_LEVEL - set(data))
    for field in missing:
        errors.append(f"missing required field: {field}")

    for field in ["artifact_dir", "copyable_summary", "generated_at", "recommended_rerun", "release_status"]:
        if field in data and not _is_non_empty_string(data[field]):
            errors.append(f"{field} must be a non-empty string")

    review_status = data.get("review_status")
    if review_status is not None and review_status not in ALLOWED_REVIEW_STATUS:
        errors.append(
            "review_status must be one of: " + ", ".join(sorted(ALLOWED_REVIEW_STATUS))
        )

    for field in ["missing_expected", "missing_key_artifacts"]:
        if field in data and not _is_string_list(data[field]):
            errors.append(f"{field} must be a list of strings")

    key_artifacts = data.get("key_artifacts")
    if key_artifacts is not None:
        if not isinstance(key_artifacts, list):
            errors.append("key_artifacts must be a list")
        else:
            for index, artifact in enumerate(key_artifacts, start=1):
                if not isinstance(artifact, dict):
                    errors.append(f"key_artifacts[{index}] must be an object")
                    continue
                missing_artifact_fields = sorted(REQUIRED_KEY_ARTIFACT_FIELDS - set(artifact))
                for field in missing_artifact_fields:
                    errors.append(f"key_artifacts[{index}] missing required field: {field}")
                if "path" in artifact and not _is_non_empty_string(artifact["path"]):
                    errors.append(f"key_artifacts[{index}].path must be a non-empty string")
                if "purpose" in artifact and not _is_non_empty_string(artifact["purpose"]):
                    errors.append(f"key_artifacts[{index}].purpose must be a non-empty string")
                if "present" in artifact and not isinstance(artifact["present"], bool):
                    errors.append(f"key_artifacts[{index}].present must be a boolean")

    review_order = data.get("review_order")
    if review_order is not None:
        if not isinstance(review_order, list) or not review_order:
            errors.append("review_order must be a non-empty list")
        else:
            previous_step = 0
            for index, step in enumerate(review_order, start=1):
                if not isinstance(step, dict):
                    errors.append(f"review_order[{index}] must be an object")
                    continue
                missing_step_fields = sorted(REQUIRED_REVIEW_ORDER_FIELDS - set(step))
                for field in missing_step_fields:
                    errors.append(f"review_order[{index}] missing required field: {field}")
                step_number = step.get("step")
                if not isinstance(step_number, int) or step_number < 1:
                    errors.append(f"review_order[{index}].step must be a positive integer")
                elif step_number <= previous_step:
                    errors.append("review_order steps must be strictly increasing")
                else:
                    previous_step = step_number
                for field in ["action", "artifact", "detail"]:
                    if field in step and not _is_non_empty_string(step[field]):
                        errors.append(f"review_order[{index}].{field} must be a non-empty string")
                if "present" in step and not isinstance(step["present"], bool):
                    errors.append(f"review_order[{index}].present must be a boolean")
                status = step.get("status")
                if status is not None and status not in ALLOWED_REVIEW_ORDER_STATUS:
                    errors.append(f"review_order[{index}].status must be present or missing")

    return errors


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate reviewer-handoff.json using the repository's stable handoff contract."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="ci_artifacts/reviewer-handoff.json",
        help="Path to reviewer-handoff.json (default: ci_artifacts/reviewer-handoff.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable validation results.",
    )
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        data = _load_json(path)
    except FileNotFoundError:
        errors = [f"file not found: {path}"]
    except json.JSONDecodeError as exc:
        errors = [f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"]
    else:
        errors = validate_handoff(data)

    result = {"path": str(path), "valid": not errors, "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif errors:
        print(f"reviewer handoff validation failed: {path}")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"reviewer handoff validation passed: {path}")

    return 0 if not errors else 1


if __name__ == "__main__":  # pragma: no cover - exercised by CLI users
    sys.exit(main())
