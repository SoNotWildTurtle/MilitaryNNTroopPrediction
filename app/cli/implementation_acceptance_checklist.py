"""Generate reviewer acceptance gates for one additive maintenance increment.

The CLI turns a selected next-increment candidate or run decision record into a
small, deterministic Markdown/JSON checklist. It is intentionally offline and
non-operational: it does not fetch live data, run prediction, or provide targeting
guidance. The output helps maintainers validate provenance, uncertainty framing,
artifact evidence, rollback, and merge readiness before handoff.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

DEFAULT_MARKDOWN_NAME = "implementation-acceptance-checklist.md"
DEFAULT_JSON_NAME = "implementation-acceptance-checklist.json"
SCHEMA_VERSION = "1.2"

SAFE_SCOPE = (
    "Acceptance gates are for lawful defensive analytical repository maintenance, "
    "reviewer handoff, reproducibility, uncertainty communication, and safe release "
    "validation only. They are not operational tasking, targeting guidance, or proof "
    "that a prediction is true."
)

BASE_ACCEPTANCE_GATES: Sequence[Mapping[str, Any]] = (
    {
        "gate_id": "scope-framing",
        "title": "Safe analytical framing is explicit",
        "required_evidence": (
            "PR summary states that outputs are analytical estimates or repository-maintenance evidence, "
            "not operational tasking or certainty claims."
        ),
        "blocking_if_missing": True,
    },
    {
        "gate_id": "additive-compatibility",
        "title": "Change is additive and backwards-compatible",
        "required_evidence": (
            "Final diff preserves existing files, APIs, examples, and user workflows, or documents any "
            "narrow compatibility impact with migration and rollback notes."
        ),
        "blocking_if_missing": True,
    },
    {
        "gate_id": "validation-evidence",
        "title": "Validation is reproducible from narrow commands",
        "required_evidence": (
            "PR body lists local commands, hosted checks, final head SHA, and the narrowest failed-test "
            "reproduction path if any validation failed during the run."
        ),
        "blocking_if_missing": True,
    },
    {
        "gate_id": "artifact-provenance",
        "title": "Artifacts are labeled by provenance and review purpose",
        "required_evidence": (
            "Generated, synthetic, preview, and reviewer-only artifacts are identified so downstream "
            "readers do not confuse fixtures with real-world observations."
        ),
        "blocking_if_missing": True,
    },
    {
        "gate_id": "uncertainty-and-risk",
        "title": "Uncertainty, risks, and limitations are visible",
        "required_evidence": (
            "Checklist or PR notes call out assumptions, known limits, remaining blockers, and the next "
            "safe follow-up task."
        ),
        "blocking_if_missing": True,
    },
    {
        "gate_id": "rollback-recovery",
        "title": "Rollback is simple and documented",
        "required_evidence": (
            "Rollback notes explain how to revert the additive change without deleting unrelated features "
            "or weakening analytical safety controls."
        ),
        "blocking_if_missing": True,
    },
)

FOCUS_GATE_HINTS: Mapping[str, Sequence[str]] = {
    "setup_validation": (
        "include setup doctor output or a precise skipped-dependency explanation",
        "document recovery hints for first-run environment failures",
    ),
    "artifact_provenance": (
        "include manifest, ledger, and gap-report evidence where applicable",
        "preserve unknown JSON fields for downstream consumers",
    ),
    "uncertainty_review": (
        "separate confidence, uncertainty, caveats, and reviewer action items",
        "avoid wording that implies operational certainty",
    ),
    "operator_handoff": (
        "include a non-technical summary and the next command for reviewers",
        "surface blockers before status-positive language",
    ),
    "scenario_comparison": (
        "label assumptions and input provenance before comparing scenarios",
        "state that scenario outputs are analytical estimates, not ground truth",
    ),
}


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


def _selected_candidate(source: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = source.get("selected_candidate")
    if isinstance(direct, Mapping):
        return direct
    recommended = source.get("recommended_candidate")
    if isinstance(recommended, Mapping):
        return recommended
    candidates = source.get("candidate_recipes")
    if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes)):
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                return candidate
    return {}


def _gate_summary(gates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    gate_ids = [str(gate.get("gate_id", "unknown")) for gate in gates]
    blocking_gate_ids = [
        str(gate.get("gate_id", "unknown"))
        for gate in gates
        if bool(gate.get("blocking_if_missing"))
    ]
    nonblocking_gate_ids = [gate_id for gate_id in gate_ids if gate_id not in blocking_gate_ids]
    return {
        "total_gates": len(gates),
        "blocking_gates": len(blocking_gate_ids),
        "nonblocking_gates": len(nonblocking_gate_ids),
        "gate_ids": gate_ids,
        "blocking_gate_ids": blocking_gate_ids,
        "nonblocking_gate_ids": nonblocking_gate_ids,
        "review_decision_rule": (
            "Every blocking gate requires concrete PR, artifact, or hosted-check evidence before merge. "
            "Missing or unavailable evidence is a merge blocker, not a warning."
        ),
    }


def _gate_evidence_manifest(gates: Sequence[Mapping[str, Any]]) -> Sequence[Dict[str, Any]]:
    return [
        {
            "gate_id": str(gate.get("gate_id", "unknown")),
            "title": str(gate.get("title", "Untitled acceptance gate")),
            "blocking_if_missing": bool(gate.get("blocking_if_missing")),
            "evidence_status": "not_collected",
            "evidence_sources": [],
            "reviewer_notes": "",
            "missing_evidence_blocks_merge": bool(gate.get("blocking_if_missing")),
        }
        for gate in gates
    ]


def build_acceptance_checklist(
    source: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic acceptance checklist from decision/candidate context."""

    source = source or {}
    generated_at = generated_at or _utc_now()
    candidate = _selected_candidate(source)
    focus_area = str(candidate.get("focus_area", "general_handoff"))
    validation_commands = [str(command) for command in candidate.get("validation_commands", [])]
    if not validation_commands:
        validation_commands = [
            "python -m compileall app tests",
            "python -m unittest discover -s tests -p 'test_*.py'",
            "bash scripts/ci_report.sh",
        ]

    merge_blockers = [str(blocker) for blocker in source.get("merge_blockers", [])]
    if not merge_blockers:
        merge_blockers = [
            "Hosted required checks must pass for the final head SHA before merge.",
            "Unresolved review threads or unavailable validation remain blockers.",
        ]

    gate_hints = list(FOCUS_GATE_HINTS.get(focus_area, ()))
    if not gate_hints:
        gate_hints.append("capture final-head-SHA, hosted checks, local validation, rollback, and safe framing evidence")

    acceptance_gates = [dict(gate) for gate in BASE_ACCEPTANCE_GATES]

    return {
        "generated_at": generated_at.isoformat(),
        "schema_version": SCHEMA_VERSION,
        "status": "ready_for_review_planning" if candidate else "needs_candidate_context",
        "safe_scope": SAFE_SCOPE,
        "source_schema_version": source.get("schema_version"),
        "candidate": {
            "candidate_id": candidate.get("candidate_id"),
            "title": candidate.get("title", "Unspecified additive increment"),
            "focus_area": focus_area,
            "status": candidate.get("status", "unknown"),
            "suggested_artifact": candidate.get("suggested_artifact"),
            "rationale": candidate.get("rationale"),
        },
        "acceptance_gates": acceptance_gates,
        "gate_summary": _gate_summary(acceptance_gates),
        "gate_evidence_manifest": _gate_evidence_manifest(acceptance_gates),
        "focus_gate_hints": gate_hints,
        "validation_commands": validation_commands,
        "merge_blockers": merge_blockers,
        "handoff_fields_to_capture": [
            "final_head_sha",
            "hosted_required_checks",
            "local_validation_commands",
            "artifact_manifest_or_generated_outputs",
            "diff_review_for_deletions_secrets_generated_artifacts_and_unsupported_claims",
            "compatibility_and_rollback_notes",
            "safe_analytical_framing_confirmation",
            "gate_evidence_manifest_updates",
            "next_follow_up_task",
        ],
        "compatibility_notes": (
            "This checklist is additive review evidence. It does not change prediction logic, training data, "
            "database schemas, API routes, or generated analytical outputs unless a caller chooses to store it."
        ),
        "rollback_notes": (
            "Remove the generated checklist artifact or revert the checklist CLI/docs PR. Do not delete unrelated "
            "handoff, validation, or analytical-safety documentation."
        ),
    }


def _markdown_lines(checklist: Mapping[str, Any]) -> Iterable[str]:
    candidate = checklist.get("candidate", {})
    if not isinstance(candidate, Mapping):
        candidate = {}
    yield "# Implementation Acceptance Checklist"
    yield ""
    yield "Offline acceptance gates for one cohesive additive repository increment."
    yield ""
    yield f"Generated: `{checklist['generated_at']}`"
    yield f"Status: **{str(checklist['status']).upper()}**"
    yield f"Schema version: `{checklist['schema_version']}`"
    yield ""
    yield "## Selected increment"
    yield ""
    yield f"- Candidate ID: `{candidate.get('candidate_id') or 'not-provided'}`"
    yield f"- Title: {candidate.get('title') or 'Unspecified additive increment'}"
    yield f"- Focus area: `{candidate.get('focus_area') or 'general_handoff'}`"
    if candidate.get("suggested_artifact"):
        yield f"- Suggested artifact: {candidate['suggested_artifact']}"
    if candidate.get("rationale"):
        yield f"- Rationale: {candidate['rationale']}"
    yield ""
    yield "## Acceptance gate summary"
    yield ""
    gate_summary = checklist.get("gate_summary", {})
    if not isinstance(gate_summary, Mapping):
        gate_summary = {}
    yield f"- Total gates: {gate_summary.get('total_gates', 'unknown')}"
    yield f"- Blocking gates: {gate_summary.get('blocking_gates', 'unknown')}"
    yield f"- Nonblocking gates: {gate_summary.get('nonblocking_gates', 'unknown')}"
    yield f"- Review decision rule: {gate_summary.get('review_decision_rule', 'Every blocking gate requires evidence before merge.')}"
    yield ""
    yield "## Acceptance gates"
    yield ""
    yield "| Gate | Required evidence | Blocking if missing |"
    yield "| --- | --- | --- |"
    for gate in checklist["acceptance_gates"]:
        required = str(gate["required_evidence"]).replace("|", "\\|")
        yield f"| `{gate['gate_id']}` {gate['title']} | {required} | {gate['blocking_if_missing']} |"
    yield ""
    yield "## Gate evidence manifest"
    yield ""
    yield "| Gate | Evidence status | Evidence sources | Missing evidence blocks merge |"
    yield "| --- | --- | --- | --- |"
    evidence_manifest = checklist.get("gate_evidence_manifest", [])
    if not isinstance(evidence_manifest, Sequence) or isinstance(evidence_manifest, (str, bytes)):
        evidence_manifest = []
    for entry in evidence_manifest:
        if not isinstance(entry, Mapping):
            continue
        sources = entry.get("evidence_sources", [])
        if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)):
            source_count = len(sources)
        else:
            source_count = "unknown"
        yield (
            f"| `{entry.get('gate_id', 'unknown')}` {entry.get('title', '')} | "
            f"{entry.get('evidence_status', 'not_collected')} | {source_count} | "
            f"{entry.get('missing_evidence_blocks_merge', True)} |"
        )
    yield ""
    yield "## Focus-specific hints"
    yield ""
    for hint in checklist["focus_gate_hints"]:
        yield f"- {hint}"
    yield ""
    yield "## Validation commands"
    yield ""
    for command in checklist["validation_commands"]:
        yield f"- `{command}`"
    yield ""
    yield "## Merge blockers"
    yield ""
    for blocker in checklist["merge_blockers"]:
        yield f"- {blocker}"
    yield ""
    yield "## Handoff fields to capture"
    yield ""
    for field in checklist["handoff_fields_to_capture"]:
        yield f"- `{field}`"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(checklist["safe_scope"])
    yield ""
    yield "## Compatibility and rollback"
    yield ""
    yield f"- Compatibility: {checklist['compatibility_notes']}"
    yield f"- Rollback: {checklist['rollback_notes']}"


def render_markdown(checklist: Mapping[str, Any]) -> str:
    """Render an acceptance checklist as Markdown."""

    return "\n".join(_markdown_lines(checklist)).rstrip() + "\n"


def write_outputs(checklist: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested Markdown and JSON checklist outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(checklist), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(checklist, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate offline implementation acceptance checklist artifacts.")
    parser.add_argument(
        "--decision-record-path",
        type=Path,
        default=None,
        help="Optional run-decision-record or next-increment-candidates JSON source.",
    )
    parser.add_argument("--markdown-path", type=Path, default=Path(DEFAULT_MARKDOWN_NAME), help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=Path(DEFAULT_JSON_NAME), help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = _read_json(args.decision_record_path)
    checklist = build_acceptance_checklist(source)
    markdown_path = None if args.no_markdown else args.markdown_path
    json_path = None if args.no_json else args.json_path
    write_outputs(checklist, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote implementation acceptance checklist Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote implementation acceptance checklist JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
