"""Validate cross-artifact consistency for generated diagnostic handoffs.

The report is intentionally offline and metadata-only. It reads local generated
artifacts such as release health, artifact manifests, reviewer handoffs, operator
next steps, and uncertainty packets. It does not run collection, prediction,
model training, networking, database, deployment, or targeting workflows.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_HEALTH_NAME = "release-health.json"
DEFAULT_MANIFEST_NAME = "artifact-manifest.json"
DEFAULT_HANDOFF_NAME = "reviewer-handoff.json"
DEFAULT_NEXT_STEPS_NAME = "operator-next-steps.json"
DEFAULT_UNCERTAINTY_NAME = "uncertainty-review-packet.json"
DEFAULT_MARKDOWN_NAME = "handoff-integrity-report.md"
DEFAULT_JSON_NAME = "handoff-integrity-report.json"

SAFE_SCOPE = (
    "Offline diagnostic metadata, generated handoff artifacts, reproducibility "
    "checks, and reviewer release-gate evidence only."
)
SAFETY_NOTES: tuple[str, ...] = (
    "Treat predictions and readiness summaries as analytical estimates, not certainty.",
    "Do not use this report for targeting, tasking, or operational direction.",
    "Regenerate the diagnostics bundle before sharing if required artifacts are missing or stale.",
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


def _manifest_paths(manifest: Mapping[str, Any]) -> set[str]:
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return set()
    paths: set[str] = set()
    for entry in files:
        if isinstance(entry, Mapping) and entry.get("path"):
            paths.add(str(entry["path"]))
    return paths


def _status_rank(status: str) -> int:
    order = {"ready": 0, "pass": 0, "needs_review": 1, "review_warnings": 2, "warn": 2, "blocked": 3, "fail": 3, "failed": 3, "error": 3, "action_needed": 3}
    return order.get(status.lower(), 1)


def _overall_status(findings: Sequence[Mapping[str, str]]) -> str:
    severities = {str(finding.get("severity", "")).lower() for finding in findings}
    if "high" in severities:
        return "blocked"
    if "medium" in severities:
        return "review_warnings"
    return "ready"


def _add_finding(
    findings: List[Dict[str, str]],
    *,
    severity: str,
    category: str,
    evidence: str,
    detail: str,
    recommended_validation: str,
) -> None:
    findings.append(
        {
            "severity": severity,
            "category": category,
            "evidence": evidence,
            "detail": detail,
            "recommended_validation": recommended_validation,
        }
    )


def build_handoff_integrity_report(
    *,
    release_health_payload: Any,
    manifest: Mapping[str, Any],
    reviewer_handoff: Mapping[str, Any],
    operator_next_steps: Mapping[str, Any],
    uncertainty_packet: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic integrity report from generated diagnostics."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    findings: List[Dict[str, str]] = []
    paths = _manifest_paths(manifest)
    missing_expected = [str(path) for path in manifest.get("missing_expected", [])]
    expected_review_artifacts = {
        DEFAULT_HEALTH_NAME,
        DEFAULT_MANIFEST_NAME,
        DEFAULT_HANDOFF_NAME,
        DEFAULT_NEXT_STEPS_NAME,
        DEFAULT_UNCERTAINTY_NAME,
    }

    for required_path in sorted(expected_review_artifacts):
        if required_path not in paths and required_path not in {DEFAULT_MANIFEST_NAME}:
            _add_finding(
                findings,
                severity="high",
                category="missing_review_artifact",
                evidence=required_path,
                detail="A required review artifact was not indexed by the manifest.",
                recommended_validation="make ci-report",
            )

    if missing_expected:
        _add_finding(
            findings,
            severity="high",
            category="manifest_completeness",
            evidence=f"{len(missing_expected)} missing expected artifacts",
            detail="The artifact manifest reports missing expected outputs, so the handoff bundle is incomplete.",
            recommended_validation="make ci-report",
        )

    health_statuses = [str(check.get("status", "unknown")).lower() for check in _health_checks(release_health_payload)]
    failing_health = [status for status in health_statuses if status in {"fail", "failed", "error"}]
    warning_health = [status for status in health_statuses if status in {"warn", "warning", "review_warnings"}]
    if failing_health:
        _add_finding(
            findings,
            severity="high",
            category="release_health",
            evidence=f"{len(failing_health)} failing health checks",
            detail="Release health contains failures that should be fixed before handoff.",
            recommended_validation="make doctor && make test",
        )
    elif warning_health:
        _add_finding(
            findings,
            severity="medium",
            category="release_health",
            evidence=f"{len(warning_health)} warning health checks",
            detail="Release health contains warnings that need explicit review before handoff.",
            recommended_validation="make verify",
        )

    plan_status = str(operator_next_steps.get("status", "unknown"))
    uncertainty_status = str(uncertainty_packet.get("status", "unknown"))
    if _status_rank(uncertainty_status) > _status_rank(plan_status) + 1:
        _add_finding(
            findings,
            severity="medium",
            category="status_alignment",
            evidence=f"operator_next_steps={plan_status}; uncertainty_packet={uncertainty_status}",
            detail="The uncertainty packet is materially more cautious than the operator next-step status.",
            recommended_validation="make operator-next-steps && make ci-report",
        )

    handoff_status = str(reviewer_handoff.get("status") or reviewer_handoff.get("summary", {}).get("status") or "unknown")
    if handoff_status != "unknown" and _status_rank(handoff_status) + 1 < _status_rank(uncertainty_status):
        _add_finding(
            findings,
            severity="medium",
            category="handoff_alignment",
            evidence=f"reviewer_handoff={handoff_status}; uncertainty_packet={uncertainty_status}",
            detail="Reviewer handoff appears less cautious than the uncertainty packet.",
            recommended_validation="make reviewer-handoff && make ci-report",
        )

    next_validation_steps = list(
        dict.fromkeys(
            [finding["recommended_validation"] for finding in findings]
            or ["make verify", "Open ci_artifacts/release-bundle-index.html", "Review handoff-integrity-report.md"]
        )
    )[:5]

    return {
        "generated_at": generated_at.isoformat(),
        "status": _overall_status(findings),
        "artifact_count": int(manifest.get("file_count", 0) or 0),
        "missing_expected_count": len(missing_expected),
        "release_health_check_count": len(health_statuses),
        "operator_next_steps_status": plan_status,
        "uncertainty_packet_status": uncertainty_status,
        "reviewer_handoff_status": handoff_status,
        "findings": findings,
        "next_validation_steps": next_validation_steps,
        "privacy_and_safety_notes": list(SAFETY_NOTES),
        "safe_scope": SAFE_SCOPE,
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(report: Mapping[str, Any]) -> Iterable[str]:
    yield "# Handoff Integrity Report"
    yield ""
    yield f"Generated: `{report['generated_at']}`"
    yield f"Status: **{str(report['status']).upper()}**"
    yield f"Indexed artifacts: `{report['artifact_count']}`"
    yield f"Missing expected artifacts: `{report['missing_expected_count']}`"
    yield f"Release-health checks: `{report['release_health_check_count']}`"
    yield ""
    yield "## Cross-artifact status"
    yield ""
    yield f"- Reviewer handoff: `{report['reviewer_handoff_status']}`"
    yield f"- Operator next steps: `{report['operator_next_steps_status']}`"
    yield f"- Uncertainty packet: `{report['uncertainty_packet_status']}`"
    yield ""
    yield "## Findings"
    yield ""
    findings = list(report.get("findings", []))
    if findings:
        yield "| Severity | Category | Evidence | Detail | Recommended validation |"
        yield "| --- | --- | --- | --- | --- |"
        for finding in findings:
            yield (
                f"| {_escape_table(finding.get('severity', 'unknown')).upper()} | "
                f"{_escape_table(finding.get('category', 'unknown'))} | "
                f"{_escape_table(finding.get('evidence', ''))} | "
                f"{_escape_table(finding.get('detail', ''))} | "
                f"`{_escape_table(finding.get('recommended_validation', 'make verify'))}` |"
            )
    else:
        yield "No cross-artifact integrity gaps were detected from the available generated diagnostics."
    yield ""
    yield "## Next validation steps"
    yield ""
    for step in report.get("next_validation_steps", []):
        yield f"- `{step}`"
    yield ""
    yield "## Privacy and safety notes"
    yield ""
    for note in report.get("privacy_and_safety_notes", []):
        yield f"- {note}"
    yield ""
    yield "## Safe scope"
    yield ""
    yield str(report["safe_scope"])


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the integrity report as Markdown."""

    return "\n".join(_markdown_lines(report)).rstrip() + "\n"


def write_outputs(report: Mapping[str, Any], markdown_path: Path, json_path: Path | None) -> None:
    """Write Markdown and optional JSON report outputs."""

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a cross-artifact handoff integrity report from diagnostics.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR, help=f"diagnostic artifact directory; default: {DEFAULT_ARTIFACT_DIR}")
    parser.add_argument("--health-json", type=Path, default=None, help="release health JSON path")
    parser.add_argument("--manifest-json", type=Path, default=None, help="artifact manifest JSON path")
    parser.add_argument("--reviewer-handoff-json", type=Path, default=None, help="reviewer handoff JSON path")
    parser.add_argument("--operator-next-steps-json", type=Path, default=None, help="operator next-steps JSON path")
    parser.add_argument("--uncertainty-json", type=Path, default=None, help="uncertainty review packet JSON path")
    parser.add_argument("--markdown-path", type=Path, default=None, help="handoff integrity Markdown output path")
    parser.add_argument("--json-path", type=Path, default=None, help="handoff integrity JSON output path")
    parser.add_argument("--no-json", action="store_true", help="only write Markdown output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    health_path = args.health_json or artifact_dir / DEFAULT_HEALTH_NAME
    manifest_path = args.manifest_json or artifact_dir / DEFAULT_MANIFEST_NAME
    handoff_path = args.reviewer_handoff_json or artifact_dir / DEFAULT_HANDOFF_NAME
    next_steps_path = args.operator_next_steps_json or artifact_dir / DEFAULT_NEXT_STEPS_NAME
    uncertainty_path = args.uncertainty_json or artifact_dir / DEFAULT_UNCERTAINTY_NAME
    markdown_path = args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)

    report = build_handoff_integrity_report(
        release_health_payload=_load_json(health_path, []),
        manifest=_as_mapping(_load_json(manifest_path, {"file_count": 0, "files": [], "missing_expected": []})),
        reviewer_handoff=_as_mapping(_load_json(handoff_path, {})),
        operator_next_steps=_as_mapping(_load_json(next_steps_path, {"status": "unknown"})),
        uncertainty_packet=_as_mapping(_load_json(uncertainty_path, {"status": "unknown"})),
    )
    write_outputs(report, markdown_path, json_path)

    print(f"Wrote handoff integrity report Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote handoff integrity report JSON to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
