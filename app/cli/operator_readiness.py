"""Generate an operator-facing readiness brief from local diagnostic artifacts.

This CLI is intentionally read-only with respect to analytical data sources: it only
loads existing JSON artifacts and writes Markdown/JSON summaries for reviewers,
maintainers, and non-technical operators. It does not call ingestion, detection,
prediction, network, database, or deployment workflows.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "operator-readiness.md"
DEFAULT_JSON_NAME = "operator-readiness.json"
DEFAULT_HEALTH_NAME = "release-health.json"
DEFAULT_MANIFEST_NAME = "artifact-manifest.json"
DEFAULT_TRIAGE_NAME = "triage-summary.json"

REQUIRED_ARTIFACTS: Mapping[str, str] = {
    "release-health.json": "Machine-readable readiness checks for setup, docs, generated outputs, and API contract health.",
    "release-health.md": "Human-readable readiness report for reviewers and operators.",
    "artifact-manifest.json": "Machine-readable artifact inventory with expected-output completeness.",
    "artifact-manifest.md": "Human-readable artifact inventory and SHA-256 review table.",
    "triage-summary.json": "Machine-readable narrow rerun and remediation guidance.",
    "triage-summary.md": "Human-readable CI triage and next-step summary.",
    "reviewer-handoff.json": "Copyable maintainer handoff metadata for diagnostics bundle review.",
    "reviewer-handoff.md": "Copyable maintainer handoff instructions.",
}

STATUS_WEIGHTS: Mapping[str, int] = {
    "ok": 0,
    "pass": 0,
    "passed": 0,
    "ready": 0,
    "success": 0,
    "healthy": 0,
    "warn": 1,
    "warning": 1,
    "review": 1,
    "partial": 1,
    "degraded": 1,
    "fail": 2,
    "failed": 2,
    "blocked": 2,
    "error": 2,
    "missing": 2,
}


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _manifest_paths(manifest: Mapping[str, Any]) -> set[str]:
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return set()
    paths: set[str] = set()
    for entry in files:
        if isinstance(entry, Mapping) and entry.get("path"):
            paths.add(str(entry["path"]))
    return paths


def _health_results(health: Any) -> List[Mapping[str, Any]]:
    if isinstance(health, list):
        return [item for item in health if isinstance(item, Mapping)]
    if isinstance(health, Mapping):
        results = health.get("results") or health.get("checks") or []
        if isinstance(results, list):
            return [item for item in results if isinstance(item, Mapping)]
    return []


def _worst_status(statuses: Iterable[str]) -> str:
    worst = "ready"
    worst_weight = 0
    for status in statuses:
        normalized = status.lower().strip()
        weight = STATUS_WEIGHTS.get(normalized, 1)
        if weight > worst_weight:
            worst = normalized
            worst_weight = weight
    return worst


def _status_counts(results: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {"ok": 0, "warn": 0, "fail": 0, "unknown": 0}
    for result in results:
        status = str(result.get("status", "unknown")).lower().strip()
        weight = STATUS_WEIGHTS.get(status)
        if weight == 0:
            counts["ok"] += 1
        elif weight == 1:
            counts["warn"] += 1
        elif weight == 2:
            counts["fail"] += 1
        else:
            counts["unknown"] += 1
    return counts


def _required_artifact_status(artifact_dir: Path, manifest: Mapping[str, Any]) -> List[Dict[str, Any]]:
    manifest_paths = _manifest_paths(manifest)
    statuses: List[Dict[str, Any]] = []
    for path, purpose in REQUIRED_ARTIFACTS.items():
        present = path in manifest_paths or (artifact_dir / path).exists()
        statuses.append(
            {
                "path": path,
                "present": present,
                "status": "present" if present else "missing",
                "purpose": purpose,
            }
        )
    return statuses


def build_readiness_brief(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic operator readiness brief from generated artifacts."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    health = _load_json(artifact_dir / DEFAULT_HEALTH_NAME, [])
    manifest = _load_json(artifact_dir / DEFAULT_MANIFEST_NAME, {"missing_expected": [], "file_count": 0})
    triage = _load_json(artifact_dir / DEFAULT_TRIAGE_NAME, {})

    health_results = _health_results(health)
    health_counts = _status_counts(health_results)
    failing_checks = [dict(item) for item in health_results if STATUS_WEIGHTS.get(str(item.get("status", "")).lower(), 1) == 2]
    warning_checks = [dict(item) for item in health_results if STATUS_WEIGHTS.get(str(item.get("status", "")).lower(), 1) == 1]
    missing_expected = manifest.get("missing_expected", []) if isinstance(manifest, Mapping) else []
    if not isinstance(missing_expected, list):
        missing_expected = []
    artifact_statuses = _required_artifact_status(artifact_dir, manifest if isinstance(manifest, Mapping) else {})
    missing_required = [item["path"] for item in artifact_statuses if not item["present"]]

    signal_status = _worst_status(
        [str(item.get("status", "unknown")) for item in health_results]
        + ["missing" for _ in missing_expected]
        + ["missing" for _ in missing_required]
    )

    if failing_checks or missing_required or missing_expected:
        launch_status = "blocked"
        operator_decision = "Do not rely on this bundle for release or operational review until the listed blockers are fixed."
    elif warning_checks:
        launch_status = "review"
        operator_decision = "Usable for review, but an operator should read warnings before launch or release decisions."
    else:
        launch_status = "ready"
        operator_decision = "Ready for reviewer handoff using the generated diagnostics bundle."

    next_step = str(triage.get("next_step") or triage.get("recommended_rerun") or "make verify") if isinstance(triage, Mapping) else "make verify"
    if launch_status == "ready":
        next_step = "Open ci_artifacts/release-bundle-index.html and attach the diagnostics bundle to the PR."

    return {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "launch_status": launch_status,
        "signal_status": signal_status,
        "operator_decision": operator_decision,
        "next_step": next_step,
        "health_summary": health_counts,
        "failing_checks": failing_checks,
        "warning_checks": warning_checks,
        "missing_expected": [str(item) for item in missing_expected],
        "missing_required_artifacts": missing_required,
        "required_artifacts": artifact_statuses,
        "artifact_count": int(manifest.get("file_count", 0) or 0) if isinstance(manifest, Mapping) else 0,
        "safe_scope": "Summarizes local diagnostic artifacts only; does not run ingestion, detection, prediction, network, database, deployment, or destructive workflows.",
    }


def _markdown_lines(brief: Mapping[str, Any]) -> Iterable[str]:
    yield "# Operator Readiness Brief"
    yield ""
    yield "This brief gives maintainers and non-technical operators a fast launch/no-launch view of the generated diagnostics bundle."
    yield ""
    yield f"Generated: `{brief['generated_at']}`"
    yield f"Artifact directory: `{brief['artifact_dir']}`"
    yield f"Launch status: **{str(brief['launch_status']).upper()}**"
    yield f"Signal status: `{brief['signal_status']}`"
    yield ""
    yield "## Operator decision"
    yield ""
    yield str(brief["operator_decision"])
    yield ""
    yield "## Recommended next step"
    yield ""
    yield f"`{brief['next_step']}`"
    yield ""
    yield "## Health summary"
    yield ""
    health = brief["health_summary"]
    yield f"- OK checks: {health['ok']}"
    yield f"- Warning checks: {health['warn']}"
    yield f"- Failing checks: {health['fail']}"
    yield f"- Unknown checks: {health['unknown']}"
    yield f"- Indexed artifacts: {brief['artifact_count']}"
    yield ""

    if brief["failing_checks"]:
        yield "## Blockers"
        yield ""
        for check in brief["failing_checks"]:
            yield f"- `{check.get('name', 'unknown')}`: {check.get('detail', '') or check.get('remediation', '') or 'No detail provided.'}"
        yield ""

    if brief["warning_checks"]:
        yield "## Warnings"
        yield ""
        for check in brief["warning_checks"]:
            yield f"- `{check.get('name', 'unknown')}`: {check.get('detail', '') or check.get('remediation', '') or 'No detail provided.'}"
        yield ""

    if brief["missing_expected"] or brief["missing_required_artifacts"]:
        yield "## Missing outputs"
        yield ""
        for path in brief["missing_expected"]:
            yield f"- Expected artifact missing from manifest: `{path}`"
        for path in brief["missing_required_artifacts"]:
            yield f"- Required operator artifact missing: `{path}`"
        yield ""

    yield "## Required operator artifacts"
    yield ""
    yield "| Path | Status | Purpose |"
    yield "| --- | --- | --- |"
    for artifact in brief["required_artifacts"]:
        yield f"| `{artifact['path']}` | {artifact['status']} | {artifact['purpose']} |"
    yield ""
    yield "## Safe scope"
    yield ""
    yield str(brief["safe_scope"])


def render_markdown(brief: Mapping[str, Any]) -> str:
    """Render an operator readiness brief as Markdown."""

    return "\n".join(_markdown_lines(brief)).rstrip() + "\n"


def write_outputs(brief: Mapping[str, Any], markdown_path: Path, json_path: Path | None) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(brief), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(brief, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an operator readiness brief from diagnostic artifacts.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"diagnostic artifact directory; default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument("--markdown-path", type=Path, default=None, help="Markdown output path")
    parser.add_argument("--json-path", type=Path, default=None, help="JSON output path")
    parser.add_argument("--no-json", action="store_true", help="only write Markdown output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    markdown_path = args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)
    brief = build_readiness_brief(artifact_dir)
    write_outputs(brief, markdown_path, json_path)
    print(f"Wrote operator readiness Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote operator readiness JSON to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
