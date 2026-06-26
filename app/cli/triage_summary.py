"""Generate a concise CI triage summary from local diagnostic artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "triage-summary.md"
DEFAULT_JSON_NAME = "triage-summary.json"
DEFAULT_HEALTH_NAME = "release-health.json"
DEFAULT_MANIFEST_NAME = "artifact-manifest.json"

RERUN_TARGETS: Dict[str, str] = {
    "python": "make install-core",
    "core_deps": "make install-core",
    "env_example": "make configure",
    "env_file": "make configure",
    "data_dir": "make doctor",
    "sentinel": "make doctor",
    "mongodb": "make doctor",
    "optional_deps": "make doctor",
}

ARTIFACT_TARGETS: Dict[str, str] = {
    "doctor-minimal.json": "make doctor",
    "release-health.md": "make ci-report",
    "release-health.json": "make ci-report",
    "release-notes.md": "make release-notes",
    "release-notes.json": "make release-notes",
    "openapi.json": "make openapi",
    "openapi-summary.md": "make openapi",
    "api-response-examples.json": "make examples",
    "api-response-examples.md": "make examples",
    "dashboard-mockup.html": "make dashboard",
    "release-bundle-index.html": "make bundle-index",
    "html-previews.md": "make previews",
    "previews/dashboard-mockup.svg": "make previews",
    "previews/release-bundle-index.svg": "make previews",
    "artifact-manifest.json": "make manifest",
    "artifact-manifest.md": "make manifest",
}


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def _normalize_health_results(health_payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(health_payload, Mapping):
        checks = health_payload.get("checks", [])
        if isinstance(checks, list):
            return [check for check in checks if isinstance(check, Mapping)]
        return []
    if isinstance(health_payload, list):
        return [check for check in health_payload if isinstance(check, Mapping)]
    return []


def _normalize_status(status: Any) -> str:
    normalized = str(status).lower()
    if normalized == "pass":
        return "ok"
    if normalized == "warning":
        return "warn"
    return normalized


def _count_statuses(health_results: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    summary = {"ok": 0, "warn": 0, "fail": 0}
    for result in health_results:
        status = _normalize_status(result.get("status", ""))
        if status in summary:
            summary[status] += 1
    return summary


def _target_for_check(name: str) -> str:
    return RERUN_TARGETS.get(name, "make verify")


def _target_for_artifact(path: str) -> str:
    return ARTIFACT_TARGETS.get(path, "make ci-report")


def build_triage_summary(
    health_results: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    manifest: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic triage summary from health checks and manifest data."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    normalized_health = _normalize_health_results(health_results)
    status_counts = _count_statuses(normalized_health)
    failing_checks = [dict(item) for item in normalized_health if _normalize_status(item.get("status", "")) == "fail"]
    warning_checks = [dict(item) for item in normalized_health if _normalize_status(item.get("status", "")) == "warn"]
    missing_artifacts = [str(item) for item in manifest.get("missing_expected", [])]

    recommended_actions: List[Dict[str, str]] = []
    for check in failing_checks:
        name = str(check.get("name", "unknown"))
        recommended_actions.append(
            {
                "reason": f"failing health check: {name}",
                "target": _target_for_check(name),
                "detail": str(check.get("detail", "")),
                "remediation": str(check.get("remediation", "")),
            }
        )
    for artifact_path in missing_artifacts:
        recommended_actions.append(
            {
                "reason": f"missing artifact: {artifact_path}",
                "target": _target_for_artifact(artifact_path),
                "detail": "Expected diagnostic artifact was not present in the manifest.",
                "remediation": "Regenerate the narrow artifact target, then rerun `make manifest`.",
            }
        )

    if failing_checks:
        status = "blocked"
        next_step = recommended_actions[0]["target"]
    elif missing_artifacts:
        status = "incomplete"
        next_step = recommended_actions[0]["target"]
    elif warning_checks:
        status = "review"
        next_step = "Review warnings in release-health.md; run make verify after any fixes."
    else:
        status = "ready"
        next_step = "Open release-bundle-index.html and attach the diagnostics bundle for review."

    return {
        "generated_at": generated_at.isoformat(),
        "status": status,
        "health_summary": status_counts,
        "failing_checks": failing_checks,
        "warning_checks": warning_checks,
        "missing_artifacts": missing_artifacts,
        "recommended_actions": recommended_actions,
        "next_step": next_step,
        "artifact_count": int(manifest.get("file_count", 0) or 0),
        "safe_scope": "Local setup, deterministic tests, synthetic examples, API contracts, generated artifacts, and documentation.",
    }


def _markdown_lines(summary: Mapping[str, Any]) -> Iterable[str]:
    yield "# CI Triage Summary"
    yield ""
    yield f"Generated: `{summary['generated_at']}`"
    yield f"Status: **{str(summary['status']).upper()}**"
    yield ""
    yield "## Health summary"
    yield ""
    health = summary["health_summary"]
    yield f"- OK: {health['ok']}"
    yield f"- Warnings: {health['warn']}"
    yield f"- Failures: {health['fail']}"
    yield f"- Indexed artifacts: {summary['artifact_count']}"
    yield ""
    yield "## Recommended next step"
    yield ""
    yield f"`{summary['next_step']}`"
    yield ""

    actions = list(summary["recommended_actions"])
    if actions:
        yield "## Narrow rerun targets"
        yield ""
        yield "| Reason | Target | Detail | Remediation |"
        yield "| --- | --- | --- | --- |"
        for action in actions:
            reason = str(action["reason"]).replace("|", "\\|")
            target = str(action["target"]).replace("|", "\\|")
            detail = str(action["detail"] or "—").replace("|", "\\|")
            remediation = str(action["remediation"] or "—").replace("|", "\\|")
            yield f"| {reason} | `{target}` | {detail} | {remediation} |"
        yield ""

    if summary["warning_checks"]:
        yield "## Warnings to review"
        yield ""
        for warning in summary["warning_checks"]:
            yield f"- `{warning.get('name', 'unknown')}`: {warning.get('detail', '')}"
        yield ""

    if summary["missing_artifacts"]:
        yield "## Missing artifacts"
        yield ""
        for artifact_path in summary["missing_artifacts"]:
            yield f"- `{artifact_path}`"
        yield ""

    yield "## Safe scope"
    yield ""
    yield str(summary["safe_scope"])


def render_markdown(summary: Mapping[str, Any]) -> str:
    """Render a human-readable Markdown triage report."""

    return "\n".join(_markdown_lines(summary)).rstrip() + "\n"


def write_outputs(summary: Mapping[str, Any], markdown_path: Path, json_path: Path | None) -> None:
    """Write Markdown and optional JSON outputs."""

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a CI triage summary from diagnostic artifacts.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"diagnostic artifact directory; default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument("--health-json", type=Path, default=None, help="release health JSON path")
    parser.add_argument("--manifest-json", type=Path, default=None, help="artifact manifest JSON path")
    parser.add_argument("--markdown-path", type=Path, default=None, help="triage Markdown output path")
    parser.add_argument("--json-path", type=Path, default=None, help="triage JSON output path")
    parser.add_argument("--no-json", action="store_true", help="only write Markdown output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    health_path = args.health_json or artifact_dir / DEFAULT_HEALTH_NAME
    manifest_path = args.manifest_json or artifact_dir / DEFAULT_MANIFEST_NAME
    markdown_path = args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)

    health_results = _load_json(health_path, [])
    manifest = _load_json(manifest_path, {"file_count": 0, "missing_expected": []})
    summary = build_triage_summary(health_results, manifest)
    write_outputs(summary, markdown_path, json_path)

    print(f"Wrote CI triage summary Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote CI triage summary JSON to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
