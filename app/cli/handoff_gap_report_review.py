"""Review handoff release bundle targets against an offline artifact gap report.

This CLI is intentionally repository-maintenance scoped. It reads local JSON
handoff/gap-report artifacts and emits deterministic reviewer evidence. It does
not collect live data, run prediction, or claim that an analytical estimate is
true.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

DEFAULT_MARKDOWN_NAME = "handoff-gap-report-review.md"
DEFAULT_JSON_NAME = "handoff-gap-report-review.json"
SCHEMA_VERSION = "1.1"

SAFE_SCOPE = (
    "Handoff gap-report review artifacts are offline repository-maintenance "
    "evidence for reviewer navigation only. They are not operational tasking, "
    "targeting guidance, real-world movement proof, or prediction validation."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _read_json(path: Path | None) -> Mapping[str, Any]:
    if path is None:
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, Mapping) else {}


def _as_entries(value: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [entry for entry in value if isinstance(entry, Mapping)]


def _extract_path(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        for key in ("path", "artifact_path", "relative_path", "file", "filename"):
            path = str(value.get(key, "")).strip()
            if path:
                return path
    return ""


def _path_set_from_any(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {_extract_path(entry) for entry in _as_entries(value.get("files")) if _extract_path(entry)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return {_extract_path(entry) for entry in value if _extract_path(entry)}
    return set()


def _gap_report_paths(gap_report: Mapping[str, Any] | None) -> Dict[str, set[str]] | None:
    if not gap_report:
        return None
    missing: set[str] = set()
    suspicious: set[str] = set()
    for key in ("missing_expected_files", "missing_files", "missing", "absent_targets"):
        missing.update(_path_set_from_any(gap_report.get(key)))
    for key in ("suspicious_artifacts", "suspicious_files", "suspicious", "unexpected_files"):
        suspicious.update(_path_set_from_any(gap_report.get(key)))
    return {"missing": missing, "suspicious": suspicious}


def _handoff_targets(handoff: Mapping[str, Any] | None) -> Sequence[Mapping[str, Any]]:
    if not handoff:
        return []
    projection = handoff.get("release_bundle_target_projection", {})
    if not isinstance(projection, Mapping):
        return []
    return [entry for entry in _as_entries(projection.get("targets")) if _extract_path(entry)]


def _review_target(target: Mapping[str, Any], gap_paths: Mapping[str, set[str]] | None) -> Dict[str, Any]:
    path = _extract_path(target)
    if gap_paths is None:
        status = "not_checked"
        blocker = False
        note = "No artifact gap report was supplied; gap-review status remains not_checked."
    elif path in gap_paths.get("missing", set()):
        status = "missing_in_gap_report"
        blocker = True
        note = "Target path appears in artifact-gap-report missing evidence and requires regeneration or record correction."
    elif path in gap_paths.get("suspicious", set()):
        status = "suspicious_in_gap_report"
        blocker = True
        note = "Target path appears in artifact-gap-report suspicious evidence and requires reviewer confirmation."
    else:
        status = "gap_clear"
        blocker = False
        note = "Target path was not listed as missing or suspicious in the supplied artifact-gap-report evidence."
    return {
        "path": path,
        "role": str(target.get("role", "unclassified_artifact")),
        "presence_status": str(target.get("presence_status", "not_checked")),
        "integrity_status": str(target.get("integrity_status", "not_checked")),
        "gap_status": status,
        "gap_blocks_merge": blocker,
        "review_note": note,
    }


def _reviewer_next_actions(
    reviewed_targets: Sequence[Mapping[str, Any]],
    gap_paths: Mapping[str, set[str]] | None,
    blockers: Sequence[str],
) -> Sequence[Dict[str, str]]:
    """Return deterministic reviewer actions for handoff gap-review outcomes."""

    actions: list[Dict[str, str]] = []
    if not reviewed_targets:
        actions.append({
            "priority": "blocking",
            "action": "Regenerate implementation acceptance handoff with release bundle target projection enabled.",
            "rationale": "No release bundle target paths were available for cross-checking.",
            "narrow_rerun": (
                "python -m app.cli.implementation_acceptance_handoff "
                "--checklist-json ci_artifacts/implementation-acceptance-checklist.json "
                "--decision-record-json ci_artifacts/run-decision-record.json "
                "--artifact-manifest-json ci_artifacts/artifact-manifest.json "
                "--json-path ci_artifacts/implementation-acceptance-handoff.json "
                "--markdown-path ci_artifacts/implementation-acceptance-handoff.md"
            ),
        })
    if gap_paths is None:
        actions.append({
            "priority": "blocking",
            "action": "Regenerate or provide a parseable artifact gap report from the same artifact directory.",
            "rationale": "Gap-review status cannot distinguish clear targets from missing or suspicious evidence without the gap report.",
            "narrow_rerun": (
                "python -m app.cli.artifact_gap_report --artifact-dir ci_artifacts "
                "--manifest-path ci_artifacts/artifact-manifest.json "
                "--json-path ci_artifacts/artifact-gap-report.json "
                "--markdown-path ci_artifacts/artifact-gap-report.md"
            ),
        })
    for target in reviewed_targets:
        if not bool(target.get("gap_blocks_merge", False)):
            continue
        status = str(target.get("gap_status", "not_checked"))
        path = str(target.get("path", ""))
        if status == "missing_in_gap_report":
            action = "Regenerate the missing release bundle artifact or correct stale handoff target metadata."
            rationale = f"`{path}` is listed as missing in artifact-gap-report evidence."
        elif status == "suspicious_in_gap_report":
            action = "Review and explicitly disposition the suspicious artifact before merge."
            rationale = f"`{path}` is listed as suspicious in artifact-gap-report evidence."
        else:
            action = "Resolve the handoff gap-review blocker before merge."
            rationale = f"`{path}` has gap_status={status}."
        actions.append({
            "priority": "blocking",
            "action": action,
            "rationale": rationale,
            "narrow_rerun": (
                "python -m app.cli.handoff_gap_report_review "
                "--handoff-json ci_artifacts/implementation-acceptance-handoff.json "
                "--artifact-gap-report-json ci_artifacts/artifact-gap-report.json --strict"
            ),
        })
    if not blockers:
        actions.append({
            "priority": "review",
            "action": "Attach the gap-review JSON/Markdown to the PR evidence packet and cross-check manifest statuses before merge.",
            "rationale": "No reviewed target is missing or suspicious in the supplied artifact-gap-report evidence.",
            "narrow_rerun": (
                "python -m app.cli.handoff_gap_report_review "
                "--handoff-json ci_artifacts/implementation-acceptance-handoff.json "
                "--artifact-gap-report-json ci_artifacts/artifact-gap-report.json "
                "--json-path ci_artifacts/handoff-gap-report-review.json "
                "--markdown-path ci_artifacts/handoff-gap-report-review.md --strict"
            ),
        })
    return actions


def build_gap_report_review(
    handoff: Mapping[str, Any] | None = None,
    gap_report: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build deterministic reviewer evidence for handoff/gap-report alignment."""

    generated_at = generated_at or _utc_now()
    gap_paths = _gap_report_paths(gap_report)
    reviewed_targets = [_review_target(target, gap_paths) for target in _handoff_targets(handoff)]
    blockers = [
        f"Release bundle target `{target['path']}` has gap_status={target['gap_status']}."
        for target in reviewed_targets
        if target["gap_blocks_merge"]
    ]
    if not reviewed_targets:
        blockers.append("No release bundle target paths were available in the handoff input.")
    if gap_paths is None:
        blockers.append("No parseable artifact gap report was supplied for target cross-checking.")
    return {
        "generated_at": generated_at.isoformat(),
        "schema_version": SCHEMA_VERSION,
        "status": "ready_for_review" if not blockers else "blocked_gap_report_review",
        "safe_scope": SAFE_SCOPE,
        "artifact_gap_report_supplied": gap_paths is not None,
        "target_count": len(reviewed_targets),
        "reviewed_targets": reviewed_targets,
        "gap_summary": {
            "missing_path_count": len(gap_paths.get("missing", set())) if gap_paths is not None else 0,
            "suspicious_path_count": len(gap_paths.get("suspicious", set())) if gap_paths is not None else 0,
            "blocking_target_count": sum(1 for target in reviewed_targets if target["gap_blocks_merge"]),
        },
        "merge_blockers": blockers,
        "reviewer_next_actions": _reviewer_next_actions(reviewed_targets, gap_paths, blockers),
        "review_rule": (
            "A release bundle target is clear only when it is not listed in artifact-gap-report missing "
            "or suspicious evidence. Gap review is reviewer-navigation evidence only and must not be "
            "treated as prediction validation or operational certainty."
        ),
        "compatibility_notes": (
            "This additive review reads existing implementation acceptance handoff and artifact gap-report JSON. "
            "It does not change prediction models, APIs, database schemas, generated analytical outputs, or live data workflows."
        ),
        "rollback_notes": (
            "Rollback by deleting generated handoff gap-review artifacts or reverting this CLI/docs/tests PR. "
            "Do not delete unrelated handoff, manifest, gap-report, or analytical-safety tooling."
        ),
    }


def _markdown_lines(review: Mapping[str, Any]) -> Iterable[str]:
    yield "# Handoff Gap Report Review"
    yield ""
    yield "Offline cross-check of implementation acceptance handoff release bundle targets against artifact gap-report evidence."
    yield ""
    yield f"Generated: `{review['generated_at']}`"
    yield f"Status: **{str(review['status']).upper()}**"
    yield f"Schema version: `{review['schema_version']}`"
    yield ""
    yield "## Summary"
    yield ""
    summary = review.get("gap_summary", {})
    if not isinstance(summary, Mapping):
        summary = {}
    yield f"- Artifact gap report supplied: {review.get('artifact_gap_report_supplied', False)}"
    yield f"- Target count: {review.get('target_count', 0)}"
    yield f"- Missing path count: {summary.get('missing_path_count', 0)}"
    yield f"- Suspicious path count: {summary.get('suspicious_path_count', 0)}"
    yield f"- Blocking target count: {summary.get('blocking_target_count', 0)}"
    yield f"- Review rule: {review.get('review_rule', '')}"
    yield ""
    yield "## Reviewed targets"
    yield ""
    targets = _as_entries(review.get("reviewed_targets"))
    if targets:
        yield "| Path | Role | Presence | Integrity | Gap status | Blocks merge |"
        yield "| --- | --- | --- | --- | --- | --- |"
        for target in targets:
            yield (
                f"| `{target.get('path', '')}` | `{target.get('role', '')}` | "
                f"{target.get('presence_status', 'not_checked')} | "
                f"{target.get('integrity_status', 'not_checked')} | "
                f"{target.get('gap_status', 'not_checked')} | {target.get('gap_blocks_merge', True)} |"
            )
    else:
        yield "- No release bundle targets were available for review."
    yield ""
    yield "## Reviewer next actions"
    yield ""
    actions = _as_entries(review.get("reviewer_next_actions"))
    if actions:
        for action in actions:
            yield f"- **{action.get('priority', 'review')}**: {action.get('action', '')}"
            yield f"  - Rationale: {action.get('rationale', '')}"
            yield f"  - Narrow rerun: `{action.get('narrow_rerun', '')}`"
    else:
        yield "- none"
    yield ""
    yield "## Merge blockers"
    yield ""
    blockers = review.get("merge_blockers", [])
    if isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes)) and blockers:
        for blocker in blockers:
            yield f"- {blocker}"
    else:
        yield "- none"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(review["safe_scope"])
    yield ""
    yield "## Compatibility and rollback"
    yield ""
    yield f"- Compatibility: {review['compatibility_notes']}"
    yield f"- Rollback: {review['rollback_notes']}"


def render_markdown(review: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(review)).rstrip() + "\n"


def write_outputs(review: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(review), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _strict_validation_blockers(review: Mapping[str, Any]) -> Sequence[str]:
    blockers = review.get("merge_blockers", [])
    if isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes)):
        return [str(blocker) for blocker in blockers if str(blocker)]
    return ["merge_blockers is not a parseable sequence."]


def strict_validation_passed(review: Mapping[str, Any]) -> bool:
    return not _strict_validation_blockers(review)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-check handoff release bundle targets against artifact gap-report evidence.")
    parser.add_argument("--handoff-json", type=Path, default=None, help="Implementation acceptance handoff JSON.")
    parser.add_argument("--artifact-gap-report-json", type=Path, default=None, help="Artifact gap-report JSON.")
    parser.add_argument("--markdown-path", type=Path, default=Path(DEFAULT_MARKDOWN_NAME), help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=Path(DEFAULT_JSON_NAME), help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    parser.add_argument("--strict", action="store_true", help="Exit with status 1 when gap-report blockers remain.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    review = build_gap_report_review(
        handoff=_read_json(args.handoff_json),
        gap_report=_read_json(args.artifact_gap_report_json),
    )
    markdown_path = None if args.no_markdown else args.markdown_path
    json_path = None if args.no_json else args.json_path
    write_outputs(review, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote handoff gap-report review Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote handoff gap-report review JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write files.")
    strict_blockers = _strict_validation_blockers(review) if args.strict else []
    if strict_blockers:
        print("Strict handoff gap-report review failed:")
        for blocker in strict_blockers:
            print(f"- {blocker}")
        return 1
    if args.strict:
        print("Strict handoff gap-report review passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
