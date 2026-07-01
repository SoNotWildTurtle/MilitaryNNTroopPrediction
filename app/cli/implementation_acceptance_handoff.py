"""Persist completed implementation acceptance evidence for reviewer handoff.

The CLI reads an offline implementation acceptance checklist JSON file and emits a
small deterministic Markdown/JSON handoff bundle. It is intentionally
non-operational: it does not collect live data, run prediction, or assert that an
analytical estimate is true. The output preserves completed evidence rows beside
a machine-readable readiness summary so maintainers can hand off merge evidence
without scraping Markdown.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

DEFAULT_MARKDOWN_NAME = "implementation-acceptance-handoff.md"
DEFAULT_JSON_NAME = "implementation-acceptance-handoff.json"
SCHEMA_VERSION = "1.3"
READY_EVIDENCE_STATUSES = {"collected", "verified"}
KNOWN_EVIDENCE_STATUSES = READY_EVIDENCE_STATUSES | {"not_collected", "needs_update", "blocked"}

SAFE_SCOPE = (
    "Implementation acceptance handoff artifacts are repository-maintenance "
    "evidence for lawful defensive analytical review. They are not operational "
    "tasking, targeting guidance, or proof that a prediction is true."
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


def _entry_sources(entry: Mapping[str, Any]) -> Sequence[Any]:
    sources = entry.get("evidence_sources", [])
    if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)):
        return sources
    return []


def _status_value(entry: Mapping[str, Any]) -> str:
    return str(entry.get("evidence_status", "not_collected")).lower()


def _normalized_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    sources = [str(source) for source in _entry_sources(entry) if str(source)]
    return {
        "gate_id": str(entry.get("gate_id", "unknown")),
        "title": str(entry.get("title", "Untitled acceptance gate")),
        "blocking_if_missing": bool(entry.get("blocking_if_missing")),
        "evidence_status": _status_value(entry),
        "evidence_sources": sources,
        "reviewer_notes": str(entry.get("reviewer_notes", "")),
        "missing_evidence_blocks_merge": bool(entry.get("missing_evidence_blocks_merge", True)),
    }


def _manifest_file_index(artifact_manifest: Mapping[str, Any] | None) -> Dict[str, Mapping[str, Any]] | None:
    """Return a path-indexed manifest map when an artifact manifest was supplied."""

    if not artifact_manifest:
        return None
    files = _as_entries(artifact_manifest.get("files"))
    return {
        str(entry.get("path", "")).strip(): entry
        for entry in files
        if str(entry.get("path", "")).strip()
    }


def _positive_size(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _manifest_status_for_path(path: str, manifest_index: Mapping[str, Mapping[str, Any]] | None) -> Dict[str, Any]:
    """Build safe reviewer-navigation status for one release bundle target path."""

    if manifest_index is None:
        return {
            "presence_status": "not_checked",
            "integrity_status": "not_checked",
            "manifest_evidence": {
                "artifact_manifest_supplied": False,
                "review_note": "No artifact manifest was supplied; reviewer status remains not_checked.",
            },
        }

    manifest_entry = manifest_index.get(path)
    if manifest_entry is None:
        return {
            "presence_status": "missing",
            "integrity_status": "needs_review",
            "manifest_evidence": {
                "artifact_manifest_supplied": True,
                "path": path,
                "review_note": "Target path was not found in artifact-manifest.json.",
            },
        }

    sha256 = str(manifest_entry.get("sha256", "")).strip()
    size_bytes = manifest_entry.get("size_bytes")
    hash_recorded = bool(sha256) and _positive_size(size_bytes)
    return {
        "presence_status": "present",
        "integrity_status": "hash_recorded" if hash_recorded else "needs_review",
        "manifest_evidence": {
            "artifact_manifest_supplied": True,
            "path": path,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "review_note": (
                "Manifest row includes a SHA-256 hash and positive size."
                if hash_recorded
                else "Manifest row is present but lacks a non-empty SHA-256 hash or positive size."
            ),
        },
    }


def _normalized_release_bundle_target(
    entry: Mapping[str, Any],
    manifest_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    path = str(entry.get("path", ""))
    status_fields = _manifest_status_for_path(path, manifest_index)
    target: Dict[str, Any] = {
        "path": path,
        "role": str(entry.get("role", "unclassified_artifact")),
        "review_purpose": str(entry.get("review_purpose", "")),
        "presence_status": status_fields["presence_status"],
        "integrity_status": status_fields["integrity_status"],
        "manifest_evidence": status_fields["manifest_evidence"],
    }
    for key, value in sorted(entry.items()):
        if key not in target:
            target[str(key)] = value
    return target


def _release_bundle_target_projection(
    decision_record: Mapping[str, Any] | None,
    artifact_manifest: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    decision_record = decision_record or {}
    manifest_index = _manifest_file_index(artifact_manifest)
    targets = [
        _normalized_release_bundle_target(entry, manifest_index)
        for entry in _as_entries(decision_record.get("release_bundle_targets"))
        if str(entry.get("path", "")).strip()
    ]
    return {
        "source_schema_version": decision_record.get("schema_version"),
        "artifact_manifest_supplied": manifest_index is not None,
        "target_count": len(targets),
        "targets": targets,
        "projection_rule": (
            "Projection preserves path, role, review_purpose, and unknown future keys from "
            "run-decision-record.json. When --artifact-manifest-json is supplied, target "
            "presence_status and integrity_status are derived from exact artifact-manifest.json "
            "path, size, and SHA-256 evidence; otherwise they remain not_checked."
        ),
        "safe_scope": (
            "Release bundle target projection is navigation metadata for reviewer handoff only; it does "
            "not validate model quality, prove predictions, identify real-world troop movement, or "
            "authorize operational use."
        ),
    }


def _evidence_ready(entry: Mapping[str, Any]) -> bool:
    return (
        _status_value(entry) in READY_EVIDENCE_STATUSES
        and bool(_entry_sources(entry))
        and not bool(entry.get("missing_evidence_blocks_merge", True))
    )


def _status_diagnostics(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    status_counts = dict(sorted(Counter(_status_value(entry) for entry in entries).items()))
    unknown_statuses = sorted(status for status in status_counts if status not in KNOWN_EVIDENCE_STATUSES)
    unknown_gate_ids = [
        str(entry.get("gate_id", "unknown"))
        for entry in entries
        if _status_value(entry) in unknown_statuses
    ]
    return {
        "status_counts": status_counts,
        "known_statuses": sorted(KNOWN_EVIDENCE_STATUSES),
        "unknown_statuses": unknown_statuses,
        "unknown_status_gate_ids": unknown_gate_ids,
        "status_review_warning": bool(unknown_statuses),
        "status_review_rule": (
            "Unexpected evidence_status values are preserved for compatibility, but reviewers should "
            "treat unknown statuses as not ready until the row has collected or verified evidence."
        ),
    }


def _readiness_summary(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    blocking_entries = [entry for entry in entries if bool(entry.get("blocking_if_missing"))]
    missing_blocking_gate_ids = [
        str(entry.get("gate_id", "unknown"))
        for entry in blocking_entries
        if not _evidence_ready(entry)
    ]
    ready_blocking_rows = len(blocking_entries) - len(missing_blocking_gate_ids)
    summary = {
        "total_manifest_rows": len(entries),
        "blocking_rows": len(blocking_entries),
        "ready_blocking_rows": ready_blocking_rows,
        "missing_blocking_rows": len(missing_blocking_gate_ids),
        "missing_blocking_gate_ids": missing_blocking_gate_ids,
        "ready_for_merge_evidence_review": bool(blocking_entries) and not missing_blocking_gate_ids,
        "ready_statuses": sorted(READY_EVIDENCE_STATUSES),
        "review_decision_rule": (
            "A blocking evidence row is ready only when status is collected or verified, "
            "at least one evidence source is recorded, and missing_evidence_blocks_merge is false."
        ),
    }
    summary.update(_status_diagnostics(entries))
    return summary


def build_acceptance_handoff(
    checklist: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
    decision_record: Mapping[str, Any] | None = None,
    artifact_manifest: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a deterministic completed-evidence handoff from checklist JSON."""

    checklist = checklist or {}
    generated_at = generated_at or _utc_now()
    entries = [_normalized_entry(entry) for entry in _as_entries(checklist.get("gate_evidence_manifest"))]
    release_bundle_projection = _release_bundle_target_projection(decision_record, artifact_manifest)
    readiness = _readiness_summary(entries)
    blockers = []
    if not entries:
        blockers.append("No gate_evidence_manifest rows were provided in the source checklist.")
    for gate_id in readiness["missing_blocking_gate_ids"]:
        blockers.append(f"Blocking gate `{gate_id}` still needs collected or verified evidence sources.")
    if readiness["unknown_statuses"]:
        blockers.append(
            "Unknown evidence_status values require reviewer confirmation before merge: "
            + ", ".join(readiness["unknown_statuses"])
            + "."
        )
    if not checklist.get("candidate"):
        blockers.append("Source checklist does not include selected candidate metadata for reviewer context.")

    return {
        "generated_at": generated_at.isoformat(),
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": checklist.get("schema_version"),
        "status": "ready_for_review" if not blockers else "blocked_missing_evidence",
        "safe_scope": SAFE_SCOPE,
        "candidate": checklist.get("candidate", {}) if isinstance(checklist.get("candidate"), Mapping) else {},
        "source_gate_summary": checklist.get("gate_summary", {}) if isinstance(checklist.get("gate_summary"), Mapping) else {},
        "completed_gate_evidence_manifest": entries,
        "gate_evidence_readiness_summary": readiness,
        "release_bundle_target_projection": release_bundle_projection,
        "merge_blockers": blockers,
        "handoff_fields_captured": [
            "completed_gate_evidence_manifest",
            "gate_evidence_readiness_summary",
            "release_bundle_target_projection",
            "merge_blockers",
            "safe_analytical_scope",
            "candidate_context",
        ],
        "compatibility_notes": (
            "This handoff artifact is additive and reads existing checklist, optional decision-record JSON, "
            "and optional artifact-manifest JSON files. It does not change prediction models, APIs, database "
            "schemas, generated analytical outputs, or live data workflows."
        ),
        "rollback_notes": (
            "Rollback by deleting the generated handoff artifact or reverting the handoff CLI/docs/tests PR. "
            "Do not delete unrelated acceptance checklist, validation, or analytical-safety tooling."
        ),
    }


def _strict_validation_blockers(handoff: Mapping[str, Any]) -> Sequence[str]:
    blockers = handoff.get("merge_blockers", [])
    if isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes)):
        normalized_blockers = [str(blocker) for blocker in blockers if str(blocker)]
    else:
        normalized_blockers = ["merge_blockers is not a parseable sequence."]
    readiness = handoff.get("gate_evidence_readiness_summary", {})
    if not isinstance(readiness, Mapping):
        normalized_blockers.append("gate_evidence_readiness_summary is missing or malformed.")
    elif not bool(readiness.get("ready_for_merge_evidence_review")):
        normalized_blockers.append("Gate evidence readiness summary is not ready for merge evidence review.")
    return normalized_blockers


def strict_validation_passed(handoff: Mapping[str, Any]) -> bool:
    """Return True when a handoff has no merge blockers and ready evidence rows."""

    return not _strict_validation_blockers(handoff)


def _markdown_lines(handoff: Mapping[str, Any]) -> Iterable[str]:
    yield "# Implementation Acceptance Evidence Handoff"
    yield ""
    yield "Completed gate-evidence rows for one offline repository-maintenance acceptance checklist."
    yield ""
    yield f"Generated: `{handoff['generated_at']}`"
    yield f"Status: **{str(handoff['status']).upper()}**"
    yield f"Schema version: `{handoff['schema_version']}`"
    yield ""

    candidate = handoff.get("candidate", {})
    if not isinstance(candidate, Mapping):
        candidate = {}
    yield "## Candidate context"
    yield ""
    yield f"- Candidate ID: `{candidate.get('candidate_id') or 'not-provided'}`"
    yield f"- Title: {candidate.get('title') or 'Unspecified additive increment'}"
    yield f"- Focus area: `{candidate.get('focus_area') or 'general_handoff'}`"
    yield ""

    readiness = handoff.get("gate_evidence_readiness_summary", {})
    if not isinstance(readiness, Mapping):
        readiness = {}
    missing_gate_ids = readiness.get("missing_blocking_gate_ids", [])
    if isinstance(missing_gate_ids, Sequence) and not isinstance(missing_gate_ids, (str, bytes)):
        missing_gate_text = ", ".join(str(gate_id) for gate_id in missing_gate_ids) or "none"
    else:
        missing_gate_text = "unknown"
    unknown_statuses = readiness.get("unknown_statuses", [])
    if isinstance(unknown_statuses, Sequence) and not isinstance(unknown_statuses, (str, bytes)):
        unknown_status_text = ", ".join(str(status) for status in unknown_statuses) or "none"
    else:
        unknown_status_text = "unknown"
    status_counts = readiness.get("status_counts", {})
    if isinstance(status_counts, Mapping) and status_counts:
        status_count_text = ", ".join(f"{status}: {count}" for status, count in sorted(status_counts.items()))
    else:
        status_count_text = "none"
    yield "## Readiness summary"
    yield ""
    yield f"- Ready for merge evidence review: {readiness.get('ready_for_merge_evidence_review', False)}"
    yield f"- Ready blocking rows: {readiness.get('ready_blocking_rows', 0)} / {readiness.get('blocking_rows', 'unknown')}"
    yield f"- Missing blocking gate IDs: {missing_gate_text}"
    yield f"- Evidence status counts: {status_count_text}"
    yield f"- Unknown evidence statuses: {unknown_status_text}"
    yield f"- Review decision rule: {readiness.get('review_decision_rule', 'Blocking evidence rows require sources before merge.')}"
    yield f"- Status review rule: {readiness.get('status_review_rule', 'Unknown statuses require reviewer confirmation before merge.')}"
    yield ""

    release_targets = handoff.get("release_bundle_target_projection", {})
    if not isinstance(release_targets, Mapping):
        release_targets = {}
    targets = _as_entries(release_targets.get("targets"))
    yield "## Release bundle target projection"
    yield ""
    yield f"- Target count: {release_targets.get('target_count', len(targets))}"
    yield f"- Artifact manifest supplied: {release_targets.get('artifact_manifest_supplied', False)}"
    yield f"- Projection rule: {release_targets.get('projection_rule', 'No release bundle target projection was provided.')}"
    yield f"- Safe scope: {release_targets.get('safe_scope', 'Navigation metadata only; not operational evidence.')}"
    if targets:
        yield ""
        yield "| Path | Role | Review purpose | Presence | Integrity |"
        yield "| --- | --- | --- | --- | --- |"
        for target in targets:
            yield (
                f"| `{target.get('path', '')}` | `{target.get('role', '')}` | "
                f"{target.get('review_purpose', '')} | {target.get('presence_status', 'not_checked')} | "
                f"{target.get('integrity_status', 'not_checked')} |"
            )
    yield ""

    yield "## Completed gate evidence manifest"
    yield ""
    yield "| Gate | Evidence status | Sources | Missing evidence blocks merge |"
    yield "| --- | --- | --- | --- |"
    entries = _as_entries(handoff.get("completed_gate_evidence_manifest"))
    for entry in entries:
        source_count = len(_entry_sources(entry))
        yield (
            f"| `{entry.get('gate_id', 'unknown')}` {entry.get('title', '')} | "
            f"{entry.get('evidence_status', 'not_collected')} | {source_count} | "
            f"{entry.get('missing_evidence_blocks_merge', True)} |"
        )
    yield ""

    yield "## Merge blockers"
    yield ""
    blockers = handoff.get("merge_blockers", [])
    if isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes)) and blockers:
        for blocker in blockers:
            yield f"- {blocker}"
    else:
        yield "- none"
    yield ""

    yield "## Safe analytical scope"
    yield ""
    yield str(handoff["safe_scope"])
    yield ""

    yield "## Compatibility and rollback"
    yield ""
    yield f"- Compatibility: {handoff['compatibility_notes']}"
    yield f"- Rollback: {handoff['rollback_notes']}"


def render_markdown(handoff: Mapping[str, Any]) -> str:
    """Render a completed-evidence handoff as Markdown."""

    return "\n".join(_markdown_lines(handoff)).rstrip() + "\n"


def write_outputs(handoff: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested Markdown and JSON handoff outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(handoff), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate offline implementation acceptance evidence handoff artifacts.")
    parser.add_argument(
        "--checklist-json",
        type=Path,
        default=None,
        help="Source implementation-acceptance-checklist JSON with completed gate_evidence_manifest rows.",
    )
    parser.add_argument(
        "--decision-record-json",
        type=Path,
        default=None,
        help=(
            "Optional run-decision-record JSON whose release_bundle_targets should be projected into the handoff "
            "as navigation metadata."
        ),
    )
    parser.add_argument(
        "--artifact-manifest-json",
        type=Path,
        default=None,
        help=(
            "Optional artifact-manifest JSON used to enrich projected release bundle targets with manifest-backed "
            "presence_status and integrity_status reviewer evidence."
        ),
    )
    parser.add_argument("--markdown-path", type=Path, default=Path(DEFAULT_MARKDOWN_NAME), help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=Path(DEFAULT_JSON_NAME), help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit with status 1 when generated handoff evidence still has merge blockers or is not ready "
            "for merge evidence review. Use after reviewers have filled the offline checklist evidence rows."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checklist = _read_json(args.checklist_json)
    decision_record = _read_json(args.decision_record_json)
    artifact_manifest = _read_json(args.artifact_manifest_json)
    handoff = build_acceptance_handoff(
        checklist,
        decision_record=decision_record,
        artifact_manifest=artifact_manifest,
    )
    markdown_path = None if args.no_markdown else args.markdown_path
    json_path = None if args.no_json else args.json_path
    write_outputs(handoff, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote implementation acceptance handoff Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote implementation acceptance handoff JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write files.")
    strict_blockers = _strict_validation_blockers(handoff) if args.strict else []
    if strict_blockers:
        print("Strict implementation acceptance handoff validation failed:")
        for blocker in strict_blockers:
            print(f"- {blocker}")
        return 1
    if args.strict:
        print("Strict implementation acceptance handoff validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
