"""Generate an offline handoff readiness scorecard for diagnostic bundles."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "handoff-readiness-scorecard.md"
DEFAULT_JSON_NAME = "handoff-readiness-scorecard.json"

SAFE_SCOPE = (
    "Offline scorecard for defensive analytical handoff bundles. It summarizes "
    "generated diagnostics, provenance, validation, and artifact quality signals "
    "without asserting real-world truth or certainty."
)

CATEGORY_DEFINITIONS: Mapping[str, Mapping[str, Any]] = {
    "provenance": {
        "weight": 25,
        "label": "Data provenance and source labeling",
        "artifact": "provenance-validation-matrix.json",
        "fallback": "artifact-provenance-ledger.json",
        "requirement": "Generated evidence should label synthetic, preview, review, and environment artifacts.",
    },
    "evidence": {
        "weight": 25,
        "label": "Evidence completeness",
        "artifact": "evidence-checklist.json",
        "fallback": None,
        "requirement": "Required handoff evidence gates should be present or marked for review.",
    },
    "validation": {
        "weight": 25,
        "label": "Validation receipt and blockers",
        "artifact": "handoff-validation-receipt.json",
        "fallback": "reviewer-handoff-validation.json",
        "requirement": "The bundle should include deterministic validation output with no unresolved blockers.",
    },
    "artifact_quality": {
        "weight": 25,
        "label": "Artifact integrity and completeness",
        "artifact": "artifact-gap-report.json",
        "fallback": "artifact-manifest.json",
        "requirement": "Expected artifacts should exist, be non-empty, and include manifest metadata.",
    },
}


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _status_rank(status: Any) -> int:
    normalized = str(status or "").strip().lower()
    ranks = {
        "ready": 0,
        "pass": 0,
        "passed": 0,
        "ok": 0,
        "valid": 0,
        "present": 0,
        "success": 0,
        "needs_review": 1,
        "review": 1,
        "warn": 1,
        "warning": 1,
        "incomplete": 1,
        "partial": 1,
        "unknown": 1,
        "missing_manifest": 2,
        "blocked": 2,
        "fail": 2,
        "failed": 2,
        "invalid": 2,
        "error": 2,
        "missing": 2,
    }
    return ranks.get(normalized, 1)


def _normalized_status(payload: Mapping[str, Any], *, present: bool) -> str:
    if not present:
        return "missing"
    for key in ("status", "result", "conclusion"):
        if key in payload:
            value = str(payload.get(key, "")).strip().lower()
            if value:
                return value
    if payload.get("valid") is True or payload.get("is_valid") is True:
        return "ready"
    if payload.get("valid") is False or payload.get("is_valid") is False:
        return "blocked"
    return "needs_review"


def _count_items(payload: Mapping[str, Any], keys: Sequence[str]) -> int:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, list):
            return len(value)
    return 0


def _score_for_status(status: str, weight: int) -> int:
    rank = _status_rank(status)
    if rank >= 2:
        return 0
    if rank == 1:
        return max(weight // 2, 1)
    return weight


def _load_category_payload(
    artifact_dir: Path,
    category: Mapping[str, Any],
    provided: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[Mapping[str, Any], str, bool]:
    artifact = str(category["artifact"])
    fallback = category.get("fallback")
    if provided and artifact in provided:
        return _as_mapping(provided[artifact]), artifact, True
    primary = _load_json(artifact_dir / artifact, None)
    if isinstance(primary, Mapping):
        return primary, artifact, True
    if fallback:
        fallback_name = str(fallback)
        if provided and fallback_name in provided:
            return _as_mapping(provided[fallback_name]), fallback_name, True
        fallback_payload = _load_json(artifact_dir / fallback_name, None)
        if isinstance(fallback_payload, Mapping):
            return fallback_payload, fallback_name, True
    return {}, artifact, False


def _category_row(
    name: str,
    definition: Mapping[str, Any],
    payload: Mapping[str, Any],
    source_artifact: str,
    present: bool,
) -> Dict[str, Any]:
    weight = int(definition["weight"])
    status = _normalized_status(payload, present=present)
    blockers = _count_items(payload, ("blockers", "missing", "missing_expected", "failures", "errors"))
    warnings = _count_items(payload, ("warnings", "review_items", "needs_review", "advisories"))
    score = _score_for_status(status, weight)
    if blockers and _status_rank(status) < 2:
        status = "blocked"
        score = 0
    elif warnings and _status_rank(status) == 0:
        status = "needs_review"
        score = max(weight - min(warnings, weight // 2), weight // 2)
    return {
        "name": name,
        "label": str(definition["label"]),
        "status": status,
        "score": score,
        "weight": weight,
        "source_artifact": source_artifact,
        "present": present,
        "blocker_count": blockers,
        "warning_count": warnings,
        "requirement": str(definition["requirement"]),
    }


def _overall_status(rows: Sequence[Mapping[str, Any]]) -> str:
    if any(_status_rank(row.get("status")) >= 2 for row in rows):
        return "blocked"
    if any(_status_rank(row.get("status")) == 1 for row in rows):
        return "needs_review"
    return "ready"


def build_handoff_readiness_scorecard(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
    payloads: Mapping[str, Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Build a weighted scorecard from existing generated diagnostics."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    rows: List[Dict[str, Any]] = []
    for name, definition in CATEGORY_DEFINITIONS.items():
        payload, source_artifact, present = _load_category_payload(artifact_dir, definition, payloads)
        rows.append(_category_row(name, definition, payload, source_artifact, present))

    total_score = sum(int(row["score"]) for row in rows)
    total_weight = sum(int(row["weight"]) for row in rows)
    score_percent = round((total_score / total_weight) * 100, 1) if total_weight else 0.0
    status = _overall_status(rows)

    blockers = [
        f"{row['label']} blocked by `{row['source_artifact']}`"
        for row in rows
        if _status_rank(row["status"]) >= 2
    ]
    warnings = [
        f"{row['label']} needs review in `{row['source_artifact']}`"
        for row in rows
        if _status_rank(row["status"]) == 1
    ]
    if blockers:
        next_action = "Regenerate or repair blocked diagnostics, rerun `make ci-report`, then re-export this scorecard."
    elif warnings:
        next_action = "Review warning categories, document accepted limitations, rerun narrow generators, then re-export this scorecard."
    else:
        next_action = "Attach this scorecard to the handoff bundle and run `make verify` before merge or handoff."

    return {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "status": status,
        "score": score_percent,
        "score_points": total_score,
        "max_score_points": total_weight,
        "categories": rows,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": next_action,
        "safe_scope": SAFE_SCOPE,
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(scorecard: Mapping[str, Any]) -> Iterable[str]:
    yield "# Handoff Readiness Scorecard"
    yield ""
    yield "A weighted, offline scorecard for generated analytical handoff diagnostics."
    yield ""
    yield f"Generated: `{scorecard['generated_at']}`"
    yield f"Artifact directory: `{scorecard['artifact_dir']}`"
    yield f"Status: **{str(scorecard['status']).upper()}**"
    yield f"Score: **{scorecard['score']} / 100** ({scorecard['score_points']} / {scorecard['max_score_points']} points)"
    yield f"Next action: {scorecard['next_action']}"
    yield ""
    yield "## Weighted categories"
    yield ""
    yield "| Category | Status | Score | Source artifact | Requirement |"
    yield "| --- | --- | ---: | --- | --- |"
    for row in scorecard["categories"]:
        yield (
            f"| {_escape_table(row['label'])} | {_escape_table(row['status']).upper()} | "
            f"{row['score']} / {row['weight']} | `{_escape_table(row['source_artifact'])}` | "
            f"{_escape_table(row['requirement'])} |"
        )
    yield ""
    yield "## Blockers and warnings"
    yield ""
    blockers = list(scorecard.get("blockers", []))
    warnings = list(scorecard.get("warnings", []))
    if not blockers and not warnings:
        yield "No blockers or warnings were detected from the available generated diagnostics."
    else:
        for blocker in blockers:
            yield f"- BLOCKER: {blocker}"
        for warning in warnings:
            yield f"- WARNING: {warning}"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(scorecard["safe_scope"])


def render_markdown(scorecard: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(scorecard)).rstrip() + "\n"


def write_outputs(scorecard: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(scorecard), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a weighted readiness scorecard for handoff diagnostics.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--markdown-path", type=Path, default=None)
    parser.add_argument("--json-path", type=Path, default=None)
    parser.add_argument("--no-markdown", action="store_true")
    parser.add_argument("--no-json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scorecard = build_handoff_readiness_scorecard(args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    write_outputs(scorecard, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote handoff readiness scorecard Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote handoff readiness scorecard JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write scorecard files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
