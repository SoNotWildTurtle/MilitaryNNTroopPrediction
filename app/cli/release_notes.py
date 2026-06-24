"""Generate reviewer-friendly release notes from diagnostic artifacts.

The command reads the existing release-health JSON and artifact manifest JSON that are
already produced by CI. It does not run ingestion, detection, prediction, network calls,
or any destructive workflow. The goal is to give maintainers, managers, and downstream
integrators a compact handoff summary for each diagnostic bundle.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_HEALTH_PATH = Path("ci_artifacts/release-health.json")
DEFAULT_MANIFEST_PATH = Path("ci_artifacts/artifact-manifest.json")
DEFAULT_MARKDOWN_PATH = Path("ci_artifacts/release-notes.md")
DEFAULT_JSON_PATH = Path("ci_artifacts/release-notes.json")

_STATUS_ORDER = {"fail": 0, "warn": 1, "ok": 2}
_IMPORTANT_ARTIFACTS = [
    "release-bundle-index.html",
    "release-health.md",
    "openapi-summary.md",
    "api-response-examples.md",
    "dashboard-mockup.html",
    "html-previews.md",
    "artifact-manifest.md",
]


def _load_json(path: Path, fallback: Any) -> Any:
    """Load JSON from ``path`` and return ``fallback`` when the file is absent."""

    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _health_counts(health_results: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"ok": 0, "warn": 0, "fail": 0}
    for result in health_results:
        status = str(result.get("status", "")).lower()
        if status in counts:
            counts[status] += 1
    return counts


def _checks_by_priority(health_results: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    for result in health_results:
        status = str(result.get("status", "unknown")).lower()
        checks.append(
            {
                "status": status,
                "name": str(result.get("name", "unknown")),
                "detail": str(result.get("detail", "")),
                "remediation": str(result.get("remediation", "")),
            }
        )
    return sorted(checks, key=lambda item: (_STATUS_ORDER.get(item["status"], 3), item["name"]))


def _select_artifacts(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    files = {str(entry.get("path")): entry for entry in manifest.get("files", [])}
    selected = []
    for path in _IMPORTANT_ARTIFACTS:
        entry = files.get(path)
        if entry:
            selected.append(
                {
                    "path": path,
                    "size_bytes": int(entry.get("size_bytes", 0)),
                    "description": str(entry.get("description", "Generated diagnostic artifact.")),
                }
            )
    return selected


def build_release_notes(
    health_results: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a structured release-notes summary from health and manifest inputs."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    counts = _health_counts(health_results)
    missing_expected = list(manifest.get("missing_expected", []))
    failures = [check for check in _checks_by_priority(health_results) if check["status"] == "fail"]
    warnings = [check for check in _checks_by_priority(health_results) if check["status"] == "warn"]

    if failures:
        readiness = "blocked"
        headline = "Release diagnostics found required setup failures."
    elif missing_expected:
        readiness = "review"
        headline = "Release diagnostics completed, but expected artifacts are missing."
    elif warnings:
        readiness = "review"
        headline = "Release diagnostics completed with optional warnings to review."
    else:
        readiness = "ready"
        headline = "Release diagnostics passed for the lightweight analytical toolkit."

    return {
        "generated_at": generated_at.isoformat(),
        "readiness": readiness,
        "headline": headline,
        "health_summary": counts,
        "artifact_summary": {
            "file_count": int(manifest.get("file_count", 0)),
            "total_size_bytes": int(manifest.get("total_size_bytes", 0)),
            "missing_expected": missing_expected,
        },
        "priority_checks": failures or warnings,
        "review_artifacts": _select_artifacts(manifest),
        "next_step": _next_step(readiness, missing_expected, failures, warnings),
    }


def _next_step(
    readiness: str,
    missing_expected: Sequence[str],
    failures: Sequence[Mapping[str, str]],
    warnings: Sequence[Mapping[str, str]],
) -> str:
    if failures:
        first = failures[0]
        remediation = first.get("remediation") or "fix the failing setup check and rerun diagnostics"
        return f"Resolve `{first['name']}`: {remediation}."
    if missing_expected:
        return "Regenerate the diagnostic bundle so every expected artifact is present, then rerun the manifest."
    if warnings:
        return "Review optional warnings, then publish the release bundle index for reviewers."
    if readiness == "ready":
        return "Publish or attach the release bundle index, OpenAPI summary, examples, and dashboard mockup for reviewers."
    return "Review diagnostic outputs and rerun the release notes generator."


def _markdown_lines(notes: Mapping[str, Any]) -> Iterable[str]:
    yield "# Release Notes"
    yield ""
    yield f"Generated at: `{notes['generated_at']}`"
    yield f"Readiness: **{str(notes['readiness']).upper()}**"
    yield ""
    yield str(notes["headline"])
    yield ""
    yield "## Health summary"
    yield ""
    health = notes["health_summary"]
    yield f"- OK: {health['ok']}"
    yield f"- Warnings: {health['warn']}"
    yield f"- Failures: {health['fail']}"
    yield ""
    yield "## Artifact summary"
    yield ""
    artifacts = notes["artifact_summary"]
    yield f"- Files indexed: {artifacts['file_count']}"
    yield f"- Total size: {artifacts['total_size_bytes']} bytes"
    if artifacts["missing_expected"]:
        yield "- Missing expected artifacts:"
        for path in artifacts["missing_expected"]:
            yield f"  - `{path}`"
    else:
        yield "- Missing expected artifacts: none"
    yield ""

    priority_checks = notes["priority_checks"]
    if priority_checks:
        yield "## Priority checks"
        yield ""
        yield "| Status | Check | Detail | Remediation |"
        yield "| --- | --- | --- | --- |"
        for check in priority_checks:
            detail = str(check.get("detail", "")).replace("|", "\\|").replace("\n", " ")
            remediation = str(check.get("remediation", "")).replace("|", "\\|").replace("\n", " ") or "—"
            yield f"| {str(check.get('status', '')).upper()} | `{check.get('name', '')}` | {detail} | {remediation} |"
        yield ""

    yield "## Reviewer artifacts"
    yield ""
    review_artifacts = notes["review_artifacts"]
    if review_artifacts:
        for artifact in review_artifacts:
            yield f"- `{artifact['path']}` ({artifact['size_bytes']} bytes): {artifact['description']}"
    else:
        yield "- No priority reviewer artifacts were found in the manifest."
    yield ""
    yield "## Best next step"
    yield ""
    yield str(notes["next_step"])
    yield ""


def render_markdown(notes: Mapping[str, Any]) -> str:
    """Render structured release notes as Markdown."""

    return "\n".join(_markdown_lines(notes)).rstrip() + "\n"


def write_outputs(notes: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested release notes outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(notes), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(notes, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate release notes from diagnostic bundle artifacts.")
    parser.add_argument("--health-json", type=Path, default=DEFAULT_HEALTH_PATH, help="release health JSON input")
    parser.add_argument("--manifest-json", type=Path, default=DEFAULT_MANIFEST_PATH, help="artifact manifest JSON input")
    parser.add_argument("--markdown-path", type=Path, default=DEFAULT_MARKDOWN_PATH, help="Markdown release notes output")
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH, help="JSON release notes output")
    parser.add_argument("--no-markdown", action="store_true", help="skip Markdown output")
    parser.add_argument("--no-json", action="store_true", help="skip JSON output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    notes = build_release_notes(
        health_results=_load_json(args.health_json, []),
        manifest=_load_json(args.manifest_json, {"files": [], "missing_expected": []}),
    )
    markdown_path = None if args.no_markdown else args.markdown_path
    json_path = None if args.no_json else args.json_path
    write_outputs(notes, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote release notes Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote release notes JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write release notes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
