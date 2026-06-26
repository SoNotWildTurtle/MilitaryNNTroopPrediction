"""Generate an operator-facing status board from diagnostic bundle artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from app.cli.artifact_manifest import DEFAULT_ARTIFACT_DIR

DEFAULT_MARKDOWN_NAME = "operator-status-board.md"
DEFAULT_JSON_NAME = "operator-status-board.json"

STATUS_LABELS: Mapping[str, str] = {
    "ready": "READY",
    "review_warnings": "WARNINGS",
    "needs_attention": "NEEDS ATTENTION",
    "needs_review": "NEEDS REVIEW",
    "blocked": "BLOCKED",
    "unknown": "UNKNOWN",
}
PASS_WORDS = {"ok", "pass", "passed", "ready", "success", "healthy"}
WARNING_WORDS = {"warning", "warnings", "review_warnings", "needs_review"}
BLOCKED_WORDS = {"blocked", "fail", "failed", "needs_attention", "error", "unhealthy"}


def _load_json(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _normal_status(value: object, default: str = "unknown") -> str:
    text = str(value or default).strip().lower()
    return text or default


def _manifest_files(manifest: Mapping[str, Any] | None) -> Dict[str, Mapping[str, Any]]:
    if not manifest:
        return {}
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return {}
    return {str(entry.get("path")): entry for entry in files if isinstance(entry, Mapping)}


def _missing_expected(manifest: Mapping[str, Any] | None) -> List[str]:
    if not manifest:
        return []
    missing = manifest.get("missing_expected", [])
    if not isinstance(missing, list):
        return []
    return [str(item) for item in missing]


def _first_status(*sources: Mapping[str, Any] | None, keys: Iterable[str], default: str = "unknown") -> str:
    for source in sources:
        if not source:
            continue
        for key in keys:
            value = source.get(key)
            if value:
                return _normal_status(value, default=default)
    return default


def _overall_review_status(
    handoff: Mapping[str, Any] | None,
    readiness: Mapping[str, Any] | None,
    gap_report: Mapping[str, Any] | None,
) -> str:
    status = _first_status(handoff, readiness, keys=("review_status", "status", "decision"))
    gap_status = _first_status(gap_report, keys=("status", "review_status"))
    if gap_status in BLOCKED_WORDS:
        return "needs_attention"
    return status


def _release_status(health: Mapping[str, Any] | None, handoff: Mapping[str, Any] | None) -> str:
    return _first_status(health, handoff, keys=("status", "release_status"))


def _recommended_rerun(*sources: Mapping[str, Any] | None) -> str:
    for source in sources:
        if not source:
            continue
        for key in ("recommended_rerun", "recommended_command", "next_command"):
            value = source.get(key)
            if value:
                return str(value)
        targets = source.get("rerun_targets")
        if isinstance(targets, list) and targets:
            first = targets[0]
            if isinstance(first, Mapping) and first.get("command"):
                return str(first["command"])
            return str(first)
        next_steps = source.get("next_steps")
        if isinstance(next_steps, list) and next_steps:
            first_step = next_steps[0]
            if isinstance(first_step, Mapping) and first_step.get("command"):
                return str(first_step["command"])
    return "make verify"


def _artifact_state(path: str, files_by_path: Mapping[str, Mapping[str, Any]], artifact_dir: Path) -> Dict[str, Any]:
    entry = files_by_path.get(path)
    present = entry is not None or (artifact_dir / path).exists()
    return {
        "path": path,
        "present": present,
        "status": "present" if present else "missing",
        "size_bytes": int(entry.get("size_bytes", 0)) if entry and entry.get("size_bytes") is not None else None,
        "sha256": str(entry.get("sha256")) if entry and entry.get("sha256") else None,
    }


def _task_rows(
    review_status: str,
    release_status: str,
    missing_expected: List[str],
    key_artifacts: List[Mapping[str, Any]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    rows.append(
        {
            "area": "Review readiness",
            "status": STATUS_LABELS.get(review_status, review_status.upper()),
            "action": "Share the bundle" if review_status == "ready" else "Resolve missing artifacts or warnings before handoff",
        }
    )
    rows.append(
        {
            "area": "Release health",
            "status": release_status.upper(),
            "action": "Continue normal review" if release_status in PASS_WORDS else "Read release-health.md and triage-summary.md",
        }
    )
    rows.append(
        {
            "area": "Expected artifacts",
            "status": "COMPLETE" if not missing_expected else f"{len(missing_expected)} MISSING",
            "action": "No artifact gap detected" if not missing_expected else "Regenerate the diagnostics bundle",
        }
    )
    missing_key = [item["path"] for item in key_artifacts if not item.get("present")]
    rows.append(
        {
            "area": "Key reviewer files",
            "status": "COMPLETE" if not missing_key else f"{len(missing_key)} MISSING",
            "action": "Open release-bundle-index.html first" if not missing_key else "Regenerate handoff, manifest, health, and triage outputs",
        }
    )
    return rows


def _status_severity(status: str) -> str:
    if status in BLOCKED_WORDS:
        return "blocked"
    if status in WARNING_WORDS:
        return "warning"
    if status in PASS_WORDS:
        return "ready"
    return "unknown"


def build_status_board(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    *,
    manifest_path: Path | None = None,
    handoff_path: Path | None = None,
    health_path: Path | None = None,
    triage_path: Path | None = None,
    readiness_path: Path | None = None,
    gap_report_path: Path | None = None,
) -> Dict[str, Any]:
    """Build a concise operator status board from generated diagnostics."""

    manifest = _load_json(manifest_path or artifact_dir / "artifact-manifest.json")
    handoff = _load_json(handoff_path or artifact_dir / "reviewer-handoff.json")
    health = _load_json(health_path or artifact_dir / "release-health.json")
    triage = _load_json(triage_path or artifact_dir / "triage-summary.json")
    readiness = _load_json(readiness_path or artifact_dir / "operator-readiness.json")
    gap_report = _load_json(gap_report_path or artifact_dir / "artifact-gap-report.json")
    automation_plan = _load_json(artifact_dir / "automation-plan.json")

    files_by_path = _manifest_files(manifest)
    key_paths = [
        "release-bundle-index.html",
        "reviewer-handoff.md",
        "operator-readiness.md",
        "automation-plan.md",
        "artifact-gap-report.md",
        "release-health.md",
        "triage-summary.md",
        "artifact-manifest.md",
        "dashboard-mockup.html",
    ]
    key_artifacts = [_artifact_state(path, files_by_path, artifact_dir) for path in key_paths]
    missing_expected = _missing_expected(manifest)
    review_status = _overall_review_status(handoff, readiness, gap_report)
    release_status = _release_status(health, handoff)
    recommended_rerun = _recommended_rerun(handoff, triage, readiness, gap_report, automation_plan)
    task_rows = _task_rows(review_status, release_status, missing_expected, key_artifacts)
    severity = _status_severity(review_status)
    if missing_expected and severity == "ready":
        severity = "warning"

    board: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "severity": severity,
        "review_status": review_status,
        "release_status": release_status,
        "recommended_rerun": recommended_rerun,
        "missing_expected": missing_expected,
        "key_artifacts": key_artifacts,
        "task_rows": task_rows,
    }
    board["copyable_status"] = (
        f"Operator status for `{board['artifact_dir']}`: "
        f"review `{STATUS_LABELS.get(review_status, review_status.upper())}`, "
        f"release `{release_status.upper()}`, "
        f"{len(missing_expected)} missing expected artifact(s). "
        f"Next action: `{recommended_rerun}`."
    )
    return board


def _markdown_lines(board: Mapping[str, Any]) -> Iterable[str]:
    yield "# Operator status board"
    yield ""
    yield "Use this board as a quick, non-technical readiness view before sharing a diagnostics bundle."
    yield ""
    yield f"Generated at: `{board['generated_at']}`"
    yield f"Artifact directory: `{board['artifact_dir']}`"
    yield f"Overall severity: **{str(board.get('severity', 'unknown')).upper()}**"
    yield f"Review status: **{STATUS_LABELS.get(str(board['review_status']), str(board['review_status']).upper())}**"
    yield f"Release status: **{str(board['release_status']).upper()}**"
    yield f"Recommended next command: `{board['recommended_rerun']}`"
    yield ""
    yield "## Copyable status"
    yield ""
    yield "```text"
    yield str(board["copyable_status"])
    yield "```"
    yield ""
    yield "## Action table"
    yield ""
    yield "| Area | Status | Action |"
    yield "| --- | --- | --- |"
    for row in board.get("task_rows", []):
        yield f"| {row['area']} | {row['status']} | {row['action']} |"
    yield ""
    yield "## Key artifacts"
    yield ""
    yield "| Path | Status | Size | SHA-256 |"
    yield "| --- | --- | ---: | --- |"
    for artifact in board.get("key_artifacts", []):
        size = artifact.get("size_bytes")
        size_text = str(size) if size is not None else "-"
        sha = artifact.get("sha256") or "-"
        yield f"| `{artifact['path']}` | {artifact['status']} | {size_text} | `{sha}` |"
    missing = board.get("missing_expected", [])
    if missing:
        yield ""
        yield "## Missing expected artifacts"
        yield ""
        for name in missing:
            yield f"- `{name}`"
    yield ""
    yield "## Safe operating scope"
    yield ""
    yield "Keep this status board limited to generated diagnostics, static artifacts, synthetic examples, documentation, and defensive analytical review workflows."


def render_markdown(board: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(board)).rstrip() + "\n"


def write_json(board: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(markdown_text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a concise operator status board from diagnostic bundle artifacts."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory containing generated artifacts. Default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Optional explicit artifact-manifest.json path.",
    )
    parser.add_argument(
        "--handoff-path",
        type=Path,
        default=None,
        help="Optional explicit reviewer-handoff.json path.",
    )
    parser.add_argument(
        "--health-path",
        type=Path,
        default=None,
        help="Optional explicit release-health.json path.",
    )
    parser.add_argument(
        "--triage-path",
        type=Path,
        default=None,
        help="Optional explicit triage-summary.json path.",
    )
    parser.add_argument(
        "--readiness-path",
        type=Path,
        default=None,
        help="Optional explicit operator-readiness.json path.",
    )
    parser.add_argument(
        "--gap-report-path",
        type=Path,
        default=None,
        help="Optional explicit artifact-gap-report.json path.",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=None,
        help="Path for Markdown output. Default: <artifact-dir>/operator-status-board.md",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=None,
        help="Path for JSON output. Default: <artifact-dir>/operator-status-board.json",
    )
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    board = build_status_board(
        args.artifact_dir,
        manifest_path=args.manifest_path,
        handoff_path=args.handoff_path,
        health_path=args.health_path,
        triage_path=args.triage_path,
        readiness_path=args.readiness_path,
        gap_report_path=args.gap_report_path,
    )
    markdown_path = args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = args.json_path or args.artifact_dir / DEFAULT_JSON_NAME

    if not args.no_markdown:
        write_markdown(render_markdown(board), markdown_path)
        print(f"Wrote operator status board Markdown to {markdown_path}")
    if not args.no_json:
        write_json(board, json_path)
        print(f"Wrote operator status board JSON to {json_path}")
    if args.no_markdown and args.no_json:
        print("No outputs requested; remove --no-markdown or --no-json to write status board files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
