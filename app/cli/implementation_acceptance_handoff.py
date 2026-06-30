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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

DEFAULT_MARKDOWN_NAME = "implementation-acceptance-handoff.md"
DEFAULT_JSON_NAME = "implementation-acceptance-handoff.json"
SCHEMA_VERSION = "1.0"
READY_EVIDENCE_STATUSES = {"collected", "verified"}

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


def _normalized_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    sources = [str(source) for source in _entry_sources(entry) if str(source)]
    return {
        "gate_id": str(entry.get("gate_id", "unknown")),
        "title": str(entry.get("title", "Untitled acceptance gate")),
        "blocking_if_missing": bool(entry.get("blocking_if_missing")),
        "evidence_status": str(entry.get("evidence_status", "not_collected")).lower(),
        "evidence_sources": sources,
        "reviewer_notes": str(entry.get("reviewer_notes", "")),
        "missing_evidence_blocks_merge": bool(entry.get("missing_evidence_blocks_merge", True)),
    }


def _evidence_ready(entry: Mapping[str, Any]) -> bool:
    return (
        str(entry.get("evidence_status", "not_collected")).lower() in READY_EVIDENCE_STATUSES
        and bool(_entry_sources(entry))
        and not bool(entry.get("missing_evidence_blocks_merge", True))
    )


def _readiness_summary(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    blocking_entries = [entry for entry in entries if bool(entry.get("blocking_if_missing"))]
    missing_blocking_gate_ids = [
        str(entry.get("gate_id", "unknown"))
        for entry in blocking_entries
        if not _evidence_ready(entry)
    ]
    ready_blocking_rows = len(blocking_entries) - len(missing_blocking_gate_ids)
    return {
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


def build_acceptance_handoff(
    checklist: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic completed-evidence handoff from checklist JSON."""

    checklist = checklist or {}
    generated_at = generated_at or _utc_now()
    entries = [_normalized_entry(entry) for entry in _as_entries(checklist.get("gate_evidence_manifest"))]
    readiness = _readiness_summary(entries)
    blockers = []
    if not entries:
        blockers.append("No gate_evidence_manifest rows were provided in the source checklist.")
    for gate_id in readiness["missing_blocking_gate_ids"]:
        blockers.append(f"Blocking gate `{gate_id}` still needs collected or verified evidence sources.")
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
        "merge_blockers": blockers,
        "handoff_fields_captured": [
            "completed_gate_evidence_manifest",
            "gate_evidence_readiness_summary",
            "merge_blockers",
            "safe_analytical_scope",
            "candidate_context",
        ],
        "compatibility_notes": (
            "This handoff artifact is additive and reads an existing checklist JSON file. It does not change "
            "prediction models, APIs, database schemas, generated analytical outputs, or live data workflows."
        ),
        "rollback_notes": (
            "Delete the generated handoff artifact or revert the handoff CLI/docs/tests PR. Do not delete "
            "unrelated acceptance checklist, validation, or analytical-safety tooling."
        ),
    }


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
    yield "## Readiness summary"
    yield ""
    yield f"- Ready for merge evidence review: {readiness.get('ready_for_merge_evidence_review', False)}"
    yield f"- Ready blocking rows: {readiness.get('ready_blocking_rows', 0)} / {readiness.get('blocking_rows', 'unknown')}"
    yield f"- Missing blocking gate IDs: {missing_gate_text}"
    yield f"- Review decision rule: {readiness.get('review_decision_rule', 'Blocking evidence rows require sources before merge.')}"
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
    parser.add_argument("--markdown-path", type=Path, default=Path(DEFAULT_MARKDOWN_NAME), help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=Path(DEFAULT_JSON_NAME), help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checklist = _read_json(args.checklist_json)
    handoff = build_acceptance_handoff(checklist)
    markdown_path = None if args.no_markdown else args.markdown_path
    json_path = None if args.no_json else args.json_path
    write_outputs(handoff, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote implementation acceptance handoff Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote implementation acceptance handoff JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
