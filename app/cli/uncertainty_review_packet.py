"""Generate a privacy-safe uncertainty review packet from diagnostics.

The packet is intended for lawful defensive analysis, reviewer handoff, and
reproducibility checks. It reads local generated artifacts only and does not run
collection, prediction, network, database, model, or deployment workflows.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_PLAN_NAME = "operator-next-steps.json"
DEFAULT_HEALTH_NAME = "release-health.json"
DEFAULT_MANIFEST_NAME = "artifact-manifest.json"
DEFAULT_MARKDOWN_NAME = "uncertainty-review-packet.md"
DEFAULT_JSON_NAME = "uncertainty-review-packet.json"

BASE_ASSUMPTIONS: tuple[str, ...] = (
    "Diagnostics are local generated artifacts, not live operational intelligence.",
    "Synthetic examples and dashboard previews are placeholders for validation and onboarding only.",
    "Readiness is bounded by the artifacts present in the bundle and the checks that produced them.",
)

SAFETY_NOTES: tuple[str, ...] = (
    "Frame every prediction or readiness signal as an analytical estimate with uncertainty, never as certainty.",
    "Do not use this packet for targeting, tasking, or operational direction.",
    "Share only generated diagnostics, synthetic fixtures, hashes, and setup status; avoid live sources or sensitive raw data.",
)


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _health_checks(payload: Any) -> List[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        checks = payload.get("checks", [])
    else:
        checks = payload
    if not isinstance(checks, list):
        return []
    return [check for check in checks if isinstance(check, Mapping)]


def _add_factor(
    factors: List[Dict[str, str]],
    seen: set[tuple[str, str]],
    *,
    category: str,
    severity: str,
    detail: str,
    evidence: str,
    validation: str,
) -> None:
    key = (category, evidence)
    if key in seen:
        return
    seen.add(key)
    factors.append(
        {
            "category": category,
            "severity": severity,
            "detail": detail,
            "evidence": evidence,
            "recommended_validation": validation,
        }
    )


def _status_from_inputs(factors: Sequence[Mapping[str, str]], plan: Mapping[str, Any]) -> str:
    severities = {str(factor.get("severity", "")).lower() for factor in factors}
    plan_status = str(plan.get("status", "unknown")).lower()
    if "high" in severities or plan_status == "action_needed":
        return "blocked"
    if "medium" in severities or plan_status in {"needs_review", "review_warnings"}:
        return "review_warnings"
    if plan_status == "ready":
        return "ready"
    return "needs_review"


def build_uncertainty_review_packet(
    *,
    operator_plan: Mapping[str, Any],
    release_health_payload: Any,
    manifest: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic uncertainty and validation packet from diagnostics."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    checks = _health_checks(release_health_payload)
    actions = [action for action in operator_plan.get("actions", []) if isinstance(action, Mapping)]
    missing_artifacts = [str(path) for path in manifest.get("missing_expected", [])]
    factors: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for check in checks:
        status = str(check.get("status", "")).lower()
        if status not in {"fail", "failed", "error", "warn", "warning", "review_warnings"}:
            continue
        name = str(check.get("name", "unknown"))
        detail = str(check.get("detail") or check.get("remediation") or "Review release health output.")
        _add_factor(
            factors,
            seen,
            category="release_health",
            severity="high" if status in {"fail", "failed", "error"} else "medium",
            detail=detail,
            evidence=f"{status} health check: {name}",
            validation="make doctor" if name in {"python", "core_deps", "env_file", "data_dir"} else "make verify",
        )

    for artifact_path in missing_artifacts:
        _add_factor(
            factors,
            seen,
            category="artifact_completeness",
            severity="high",
            detail="Expected diagnostic output is absent from the bundle, so downstream review may be incomplete.",
            evidence=f"missing artifact: {artifact_path}",
            validation="make ci-report",
        )

    for action in actions[:5]:
        _add_factor(
            factors,
            seen,
            category="operator_plan",
            severity="medium",
            detail=str(action.get("detail") or "Review the ranked operator next step before handoff."),
            evidence=str(action.get("reason") or action.get("target") or "operator action"),
            validation=str(action.get("target") or "make verify"),
        )

    next_steps = [str(action.get("target")) for action in actions if action.get("target")]
    if not next_steps:
        next_steps = ["make verify", "Open ci_artifacts/release-bundle-index.html", "Review uncertainty-review-packet.md"]

    status = _status_from_inputs(factors, operator_plan)
    assumptions = list(BASE_ASSUMPTIONS)
    if missing_artifacts:
        assumptions.append("Missing expected artifacts may hide additional validation gaps until the bundle is regenerated.")
    if not checks:
        assumptions.append("Release-health checks were unavailable or unreadable, so readiness cannot be independently confirmed from this packet.")

    return {
        "generated_at": generated_at.isoformat(),
        "status": status,
        "operator_plan_status": str(operator_plan.get("status", "unknown")),
        "artifact_count": int(manifest.get("file_count", 0) or 0),
        "missing_artifact_count": len(missing_artifacts),
        "uncertainty_factors": factors,
        "assumptions": assumptions,
        "next_validation_steps": list(dict.fromkeys(next_steps))[:5],
        "privacy_and_safety_notes": list(SAFETY_NOTES),
        "safe_scope": "Offline diagnostics, generated artifacts, synthetic fixtures, reproducibility checks, and reviewer handoff only.",
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(packet: Mapping[str, Any]) -> Iterable[str]:
    yield "# Uncertainty Review Packet"
    yield ""
    yield f"Generated: `{packet['generated_at']}`"
    yield f"Status: **{str(packet['status']).upper()}**"
    yield f"Operator plan status: `{packet['operator_plan_status']}`"
    yield f"Indexed artifacts: `{packet['artifact_count']}`"
    yield f"Missing expected artifacts: `{packet['missing_artifact_count']}`"
    yield ""
    yield "## What this packet is for"
    yield ""
    yield "Use this as a reviewer checklist for uncertainty, missing evidence, privacy-safe handoff, and the next validation commands before treating generated analytics as ready for downstream review."
    yield ""
    yield "## Assumptions"
    yield ""
    for assumption in packet.get("assumptions", []):
        yield f"- {assumption}"
    yield ""
    yield "## Uncertainty factors"
    yield ""
    factors = list(packet.get("uncertainty_factors", []))
    if factors:
        yield "| Severity | Category | Evidence | Detail | Recommended validation |"
        yield "| --- | --- | --- | --- | --- |"
        for factor in factors:
            yield (
                f"| {_escape_table(factor.get('severity', 'unknown')).upper()} | "
                f"{_escape_table(factor.get('category', 'unknown'))} | "
                f"{_escape_table(factor.get('evidence', ''))} | "
                f"{_escape_table(factor.get('detail', ''))} | "
                f"`{_escape_table(factor.get('recommended_validation', 'make verify'))}` |"
            )
    else:
        yield "No blocking uncertainty factors were detected from the available generated diagnostics."
    yield ""
    yield "## Next validation steps"
    yield ""
    for step in packet.get("next_validation_steps", []):
        yield f"- `{step}`"
    yield ""
    yield "## Privacy and safety notes"
    yield ""
    for note in packet.get("privacy_and_safety_notes", []):
        yield f"- {note}"
    yield ""
    yield "## Safe scope"
    yield ""
    yield str(packet["safe_scope"])


def render_markdown(packet: Mapping[str, Any]) -> str:
    """Render the packet as Markdown."""

    return "\n".join(_markdown_lines(packet)).rstrip() + "\n"


def write_outputs(packet: Mapping[str, Any], markdown_path: Path, json_path: Path | None) -> None:
    """Write Markdown and optional JSON packet outputs."""

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(packet), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an uncertainty review packet from diagnostic artifacts.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR, help=f"diagnostic artifact directory; default: {DEFAULT_ARTIFACT_DIR}")
    parser.add_argument("--operator-plan-json", type=Path, default=None, help="operator next-steps JSON path")
    parser.add_argument("--health-json", type=Path, default=None, help="release health JSON path")
    parser.add_argument("--manifest-json", type=Path, default=None, help="artifact manifest JSON path")
    parser.add_argument("--markdown-path", type=Path, default=None, help="uncertainty packet Markdown output path")
    parser.add_argument("--json-path", type=Path, default=None, help="uncertainty packet JSON output path")
    parser.add_argument("--no-json", action="store_true", help="only write Markdown output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    plan_path = args.operator_plan_json or artifact_dir / DEFAULT_PLAN_NAME
    health_path = args.health_json or artifact_dir / DEFAULT_HEALTH_NAME
    manifest_path = args.manifest_json or artifact_dir / DEFAULT_MANIFEST_NAME
    markdown_path = args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)

    operator_plan = _as_mapping(_load_json(plan_path, {"status": "unknown", "actions": []}))
    release_health_payload = _load_json(health_path, [])
    manifest = _as_mapping(_load_json(manifest_path, {"file_count": 0, "missing_expected": []}))

    packet = build_uncertainty_review_packet(
        operator_plan=operator_plan,
        release_health_payload=release_health_payload,
        manifest=manifest,
    )
    write_outputs(packet, markdown_path, json_path)

    print(f"Wrote uncertainty review packet Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote uncertainty review packet JSON to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
