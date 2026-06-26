"""Generate a ranked operator action plan from local diagnostic artifacts.

This command is intentionally safe and offline-only. It reads release health,
artifact manifest, and triage summary JSON files, then writes a concise action
plan for maintainers. It does not run collection, prediction, ingestion,
deployment, networking, or model workflows.
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
DEFAULT_TRIAGE_NAME = "triage-summary.json"
DEFAULT_MARKDOWN_NAME = "operator-next-steps.md"
DEFAULT_JSON_NAME = "operator-next-steps.json"

STATUS_PRIORITY = {"fail": 90, "warn": 50, "ok": 0}

KNOWN_CHECK_TARGETS: Dict[str, str] = {
    "python": "make install-core",
    "core_deps": "make install-core",
    "env_example": "make configure",
    "env_file": "make configure",
    "data_dir": "make doctor",
    "sentinel": "make doctor",
    "mongodb": "make doctor",
    "optional_deps": "make doctor",
}

KNOWN_ARTIFACT_TARGETS: Dict[str, str] = {
    "doctor-minimal.json": "make doctor",
    "release-health.md": "make ci-report",
    "release-health.json": "make ci-report",
    "release-notes.md": "make release-notes",
    "release-notes.json": "make release-notes",
    "reviewer-handoff.md": "make reviewer-handoff",
    "reviewer-handoff.json": "make reviewer-handoff",
    "reviewer-handoff-validation.txt": "make validate-handoff",
    "reviewer-handoff-validation.json": "make validate-handoff",
    "operator-digest.md": "make operator-digest",
    "operator-digest.json": "make operator-digest",
    "operator-readiness.md": "make operator-readiness",
    "operator-readiness.json": "make operator-readiness",
    "operator-status-board.md": "make operator-status-board",
    "operator-status-board.json": "make operator-status-board",
    "operator-session-plan.md": "make operator-session-plan",
    "operator-session-plan.json": "make operator-session-plan",
    "operator-runbook-index.md": "make operator-runbook-index",
    "operator-runbook-index.json": "make operator-runbook-index",
    "automation-plan.md": "make automation-plan",
    "automation-plan.json": "make automation-plan",
    "triage-summary.md": "make triage-summary",
    "triage-summary.json": "make triage-summary",
    "artifact-gap-report.md": "make artifact-gap-report",
    "artifact-gap-report.json": "make artifact-gap-report",
    "artifact-provenance-ledger.md": "make provenance-ledger",
    "artifact-provenance-ledger.json": "make provenance-ledger",
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


def _coerce_results(value: Any) -> List[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _score_action(priority: int, index: int) -> int:
    """Keep ordering deterministic while preserving meaningful priority gaps."""

    return max(priority - index, 1)


def _add_action(
    actions: List[Dict[str, Any]],
    seen: set[tuple[str, str]],
    *,
    source: str,
    reason: str,
    target: str,
    detail: str,
    priority: int,
) -> None:
    key = (reason, target)
    if key in seen:
        return
    seen.add(key)
    actions.append(
        {
            "source": source,
            "reason": reason,
            "target": target,
            "detail": detail,
            "priority": int(priority),
        }
    )


def build_operator_next_steps(
    health_results: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    triage_summary: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic operator action plan from diagnostic JSON inputs."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    actions: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for index, check in enumerate(health_results):
        status = str(check.get("status", "")).lower()
        if status not in {"fail", "warn"}:
            continue
        name = str(check.get("name", "unknown"))
        target = KNOWN_CHECK_TARGETS.get(name, "make verify")
        _add_action(
            actions,
            seen,
            source="release-health",
            reason=f"{status} health check: {name}",
            target=target,
            detail=str(check.get("detail") or check.get("remediation") or "Review release health output."),
            priority=_score_action(STATUS_PRIORITY[status], index),
        )

    missing_artifacts = [str(item) for item in manifest.get("missing_expected", [])]
    for index, artifact_path in enumerate(missing_artifacts):
        target = KNOWN_ARTIFACT_TARGETS.get(artifact_path, "make ci-report")
        _add_action(
            actions,
            seen,
            source="artifact-manifest",
            reason=f"missing artifact: {artifact_path}",
            target=target,
            detail="Expected reviewer or CI artifact is absent from the manifest.",
            priority=_score_action(80, index),
        )

    for index, action in enumerate(triage_summary.get("recommended_actions", []) or []):
        if not isinstance(action, Mapping):
            continue
        target = str(action.get("target") or "make verify")
        reason = str(action.get("reason") or "triage recommendation")
        detail = str(action.get("detail") or action.get("remediation") or "Review triage summary.")
        _add_action(
            actions,
            seen,
            source="triage-summary",
            reason=reason,
            target=target,
            detail=detail,
            priority=_score_action(75, index),
        )

    actions.sort(key=lambda item: (-int(item["priority"]), str(item["target"]), str(item["reason"])))

    triage_status = str(triage_summary.get("status") or "unknown").lower()
    if actions:
        status = "action_needed"
        next_step = str(actions[0]["target"])
    elif triage_status == "ready":
        status = "ready"
        next_step = "Open release-bundle-index.html, review operator-next-steps.md, and attach diagnostics for handoff."
    else:
        status = "needs_review"
        next_step = str(triage_summary.get("next_step") or "make verify")

    return {
        "generated_at": generated_at.isoformat(),
        "status": status,
        "triage_status": triage_status,
        "artifact_count": int(manifest.get("file_count", 0) or 0),
        "missing_artifacts": missing_artifacts,
        "actions": actions,
        "next_step": next_step,
        "safe_scope": "Offline diagnostics, deterministic checks, generated artifacts, documentation, and maintainer handoff only.",
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(plan: Mapping[str, Any]) -> Iterable[str]:
    yield "# Operator Next Steps"
    yield ""
    yield f"Generated: `{plan['generated_at']}`"
    yield f"Status: **{str(plan['status']).upper()}**"
    yield f"Triage status: `{plan['triage_status']}`"
    yield f"Indexed artifacts: `{plan['artifact_count']}`"
    yield ""
    yield "## Recommended next step"
    yield ""
    yield f"`{plan['next_step']}`"
    yield ""

    actions = list(plan.get("actions", []))
    if actions:
        yield "## Ranked action plan"
        yield ""
        yield "| Priority | Source | Reason | Target | Detail |"
        yield "| --- | --- | --- | --- | --- |"
        for action in actions:
            yield (
                f"| {action['priority']} | {_escape_table(action['source'])} | "
                f"{_escape_table(action['reason'])} | `{_escape_table(action['target'])}` | "
                f"{_escape_table(action['detail'])} |"
            )
        yield ""
    else:
        yield "## Ranked action plan"
        yield ""
        yield "No blocking or warning actions were detected from the available diagnostic JSON files."
        yield ""

    missing = list(plan.get("missing_artifacts", []))
    if missing:
        yield "## Missing artifacts"
        yield ""
        for artifact_path in missing:
            yield f"- `{artifact_path}`"
        yield ""

    yield "## Safe scope"
    yield ""
    yield str(plan["safe_scope"])


def render_markdown(plan: Mapping[str, Any]) -> str:
    """Render the operator action plan as Markdown."""

    return "\n".join(_markdown_lines(plan)).rstrip() + "\n"


def write_outputs(plan: Mapping[str, Any], markdown_path: Path, json_path: Path | None) -> None:
    """Write Markdown and optional JSON outputs."""

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(plan), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ranked operator next steps from diagnostic artifacts.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"diagnostic artifact directory; default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument("--health-json", type=Path, default=None, help="release health JSON path")
    parser.add_argument("--manifest-json", type=Path, default=None, help="artifact manifest JSON path")
    parser.add_argument("--triage-json", type=Path, default=None, help="triage summary JSON path")
    parser.add_argument("--markdown-path", type=Path, default=None, help="operator plan Markdown output path")
    parser.add_argument("--json-path", type=Path, default=None, help="operator plan JSON output path")
    parser.add_argument("--no-json", action="store_true", help="only write Markdown output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    health_path = args.health_json or artifact_dir / DEFAULT_HEALTH_NAME
    manifest_path = args.manifest_json or artifact_dir / DEFAULT_MANIFEST_NAME
    triage_path = args.triage_json or artifact_dir / DEFAULT_TRIAGE_NAME
    markdown_path = args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)

    health_results = _coerce_results(_load_json(health_path, []))
    manifest = _load_json(manifest_path, {"file_count": 0, "missing_expected": []})
    if not isinstance(manifest, Mapping):
        manifest = {"file_count": 0, "missing_expected": []}
    triage_summary = _load_json(triage_path, {"status": "unknown", "recommended_actions": []})
    if not isinstance(triage_summary, Mapping):
        triage_summary = {"status": "unknown", "recommended_actions": []}

    plan = build_operator_next_steps(health_results, manifest, triage_summary)
    write_outputs(plan, markdown_path, json_path)

    print(f"Wrote operator next steps Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote operator next steps JSON to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
