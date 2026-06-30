"""Generate offline candidate recipes for the next cohesive repository increment.

The CLI reads local roadmap and changelog text, scores non-duplicative focus areas,
and emits Markdown/JSON handoff artifacts for maintainers. It does not collect live
data, call networks, run prediction, or imply certainty about real-world activity.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_REPOSITORY_ROOT = Path(".")
DEFAULT_MARKDOWN_NAME = "next-increment-candidates.md"
DEFAULT_JSON_NAME = "next-increment-candidates.json"
DEFAULT_DECISION_RECORD_NAME = "run-decision-record.json"
SCHEMA_VERSION = "1.0"
DECISION_RECORD_SCHEMA_VERSION = "1.0"

SAFE_SCOPE = (
    "Use these candidates only for lawful defensive analytical repository maintenance, "
    "reviewer handoff, reproducibility, validation, data provenance, uncertainty communication, "
    "and user-friendly tooling. They are not operational tasking, targeting guidance, or "
    "evidence that a prediction is true."
)

FOCUS_DEFINITIONS: Mapping[str, Mapping[str, Sequence[str] | str]] = {
    "setup_validation": {
        "keywords": ("setup", "quickstart", "configure", "install", "environment", "doctor"),
        "artifact": "setup validation report with actionable recovery hints",
        "title": "Add setup validation recovery evidence",
    },
    "artifact_provenance": {
        "keywords": ("artifact", "manifest", "provenance", "synthetic", "fixture", "source", "ledger"),
        "artifact": "artifact provenance matrix with generated/synthetic/review-only labels",
        "title": "Add artifact provenance validation evidence",
    },
    "uncertainty_review": {
        "keywords": ("uncertainty", "confidence", "prediction", "diagnostic", "model", "drift", "explain"),
        "artifact": "uncertainty review packet with caveats and reviewer actions",
        "title": "Add uncertainty review handoff evidence",
    },
    "operator_handoff": {
        "keywords": ("handoff", "status", "readiness", "review", "operator", "dashboard", "user-friendly"),
        "artifact": "operator handoff summary with blockers and next commands",
        "title": "Add operator handoff readiness evidence",
    },
    "scenario_comparison": {
        "keywords": ("scenario", "compare", "visualize", "map", "trajectory", "cluster", "changes"),
        "artifact": "scenario comparison summary with assumptions and uncertainty notes",
        "title": "Add scenario comparison review artifact",
    },
}

VALIDATION_COMMANDS: Sequence[str] = (
    "python -m compileall app tests",
    "python -m unittest discover -s tests -p 'test_*.py'",
    "python -m app.cli.next_increment_candidates --no-markdown --json-path /tmp/next-increment-candidates.json",
)

DECISION_RECORD_REQUIRED_EVIDENCE: Sequence[str] = (
    "final_head_sha",
    "hosted_required_checks",
    "local_validation_commands",
    "diff_review_for_deletions_secrets_generated_artifacts_and_unsupported_claims",
    "compatibility_and_rollback_notes",
    "safe_analytical_framing_confirmation",
    "next_follow_up_candidate",
)


@dataclass(frozen=True)
class CandidateRecipe:
    """A reviewable next-increment candidate derived from local repository context."""

    candidate_id: str
    title: str
    focus_area: str
    status: str
    novelty_score: int
    roadmap_matches: int
    recent_overlap: int
    rationale: str
    suggested_artifact: str
    validation_commands: Sequence[str]
    safety_notes: Sequence[str]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def extract_changelog_items(text: str, limit: int = 12) -> List[str]:
    """Return recent Unreleased changelog bullets without Markdown list markers."""

    items: List[str] = []
    in_unreleased = False
    for raw_line in text.splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue
        if line.startswith("## "):
            if in_unreleased:
                break
            in_unreleased = line.lower() == "## unreleased"
            continue
        if in_unreleased and line.startswith("- "):
            items.append(line[2:])
        if len(items) >= limit:
            break
    return items


def extract_roadmap_items(text: str, limit: int = 20) -> List[str]:
    """Return numbered roadmap items without numeric prefixes."""

    items: List[str] = []
    for raw_line in text.splitlines():
        line = _normalize_line(raw_line)
        if re.match(r"^\d+\.\s+", line):
            items.append(re.sub(r"^\d+\.\s+", "", line))
        if len(items) >= limit:
            break
    return items


def _keyword_matches(items: Sequence[str], keywords: Sequence[str]) -> int:
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    count = 0
    for item in items:
        lowered = item.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            count += 1
    return count


def build_candidate_recipes(
    changelog_text: str,
    goals_text: str,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build deterministic candidate recipes from roadmap and recent-change context."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    recent_changes = extract_changelog_items(changelog_text)
    roadmap_items = extract_roadmap_items(goals_text)
    candidates: List[CandidateRecipe] = []

    for index, (focus_area, definition) in enumerate(FOCUS_DEFINITIONS.items(), start=1):
        keywords = tuple(str(keyword) for keyword in definition["keywords"])
        roadmap_matches = _keyword_matches(roadmap_items, keywords)
        recent_overlap = _keyword_matches(recent_changes, keywords)
        novelty_score = roadmap_matches * 3 - recent_overlap * 2
        status = "recommended" if roadmap_matches and recent_overlap <= 1 else "watch"
        if not roadmap_matches:
            status = "defer"
        rationale = (
            "Roadmap demand exists with limited recent overlap; suitable for one cohesive additive PR."
            if status == "recommended"
            else "Recent work may already cover this area; inspect prior PRs before implementing."
            if status == "watch"
            else "No strong roadmap signal in the inspected slice; defer unless issues or CI failures require it."
        )
        candidates.append(
            CandidateRecipe(
                candidate_id=f"candidate-{index:02d}",
                title=str(definition["title"]),
                focus_area=focus_area,
                status=status,
                novelty_score=novelty_score,
                roadmap_matches=roadmap_matches,
                recent_overlap=recent_overlap,
                rationale=rationale,
                suggested_artifact=str(definition["artifact"]),
                validation_commands=VALIDATION_COMMANDS,
                safety_notes=(
                    "Keep outputs framed as analytical estimates and repository-maintenance evidence.",
                    "Do not add live-data collection, targeting guidance, or unsupported certainty claims.",
                    "Prefer additive JSON fields and Markdown sections so existing consumers remain compatible.",
                ),
            )
        )

    ordered = sorted(candidates, key=lambda item: (-item.novelty_score, item.status, item.focus_area))
    blockers = []
    if not recent_changes:
        blockers.append("CHANGELOG.md has no readable Unreleased bullets; inspect recent commits before choosing work.")
    if not roadmap_items:
        blockers.append("goals.md has no readable numbered roadmap items; inspect roadmap context manually.")

    return {
        "generated_at": generated_at.isoformat(),
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if blockers else "ready",
        "safe_scope": SAFE_SCOPE,
        "recent_changes_inspected": recent_changes,
        "roadmap_items_inspected": roadmap_items,
        "candidate_recipes": [candidate.__dict__ for candidate in ordered],
        "recommended_candidate": ordered[0].__dict__ if ordered else None,
        "blockers": blockers,
    }


def build_candidate_report(repository_root: Path = DEFAULT_REPOSITORY_ROOT) -> Dict[str, Any]:
    """Load repository files and build candidate recipes."""

    return build_candidate_recipes(
        changelog_text=_read_text(repository_root / "CHANGELOG.md"),
        goals_text=_read_text(repository_root / "goals.md"),
    )


def _select_candidate(report: Mapping[str, Any], selected_candidate_id: str | None = None) -> Mapping[str, Any] | None:
    candidates = list(report.get("candidate_recipes", []))
    if selected_candidate_id:
        for candidate in candidates:
            if candidate.get("candidate_id") == selected_candidate_id:
                return candidate
        return None
    recommended = report.get("recommended_candidate")
    if isinstance(recommended, Mapping):
        return recommended
    return candidates[0] if candidates else None


def build_decision_record(report: Mapping[str, Any], selected_candidate_id: str | None = None) -> Dict[str, Any]:
    """Build a machine-readable one-run decision record from candidate output."""

    selected = _select_candidate(report, selected_candidate_id)
    candidates = list(report.get("candidate_recipes", []))
    alternatives = [
        {
            "candidate_id": candidate.get("candidate_id"),
            "title": candidate.get("title"),
            "focus_area": candidate.get("focus_area"),
            "status": candidate.get("status"),
            "novelty_score": candidate.get("novelty_score"),
            "reason_not_selected": "Lower deterministic novelty score or weaker fit for the current one-run increment.",
        }
        for candidate in candidates
        if not selected or candidate.get("candidate_id") != selected.get("candidate_id")
    ]
    inherited_blockers = [str(blocker) for blocker in report.get("blockers", [])]
    merge_blockers = list(inherited_blockers)
    merge_blockers.append("Hosted required checks, review-thread status, and final diff safety review must be captured before merge.")
    validation_plan = list(selected.get("validation_commands", VALIDATION_COMMANDS)) if selected else list(VALIDATION_COMMANDS)
    validation_plan.append(
        "python -m app.cli.next_increment_candidates --no-markdown --json-path /tmp/next-increment-candidates.json --decision-record-path /tmp/run-decision-record.json"
    )

    return {
        "generated_at": report.get("generated_at"),
        "schema_version": DECISION_RECORD_SCHEMA_VERSION,
        "status": "blocked" if inherited_blockers or selected is None else "ready_for_implementation",
        "source_candidate_schema_version": report.get("schema_version"),
        "selected_candidate": selected,
        "selected_candidate_id_requested": selected_candidate_id,
        "selection_reason": (
            "Selected by deterministic candidate score from local roadmap and changelog context."
            if selected and not selected_candidate_id
            else "Selected by explicit candidate ID override after local candidate generation."
            if selected
            else "No candidate could be selected from the available report."
        ),
        "alternatives_considered": alternatives,
        "required_evidence_before_merge": list(DECISION_RECORD_REQUIRED_EVIDENCE),
        "validation_plan": validation_plan,
        "merge_blockers": merge_blockers,
        "safe_scope": report.get("safe_scope", SAFE_SCOPE),
        "compatibility_notes": (
            "Decision records are additive JSON evidence for maintainers. They do not change model behavior, "
            "data ingestion, APIs, schemas consumed by prediction clients, or generated diagnostics unless explicitly requested."
        ),
        "rollback_notes": (
            "Remove the generated decision-record JSON or revert the CLI/docs PR. Existing candidate Markdown/JSON outputs remain compatible."
        ),
        "next_follow_up_candidate": (
            "Wire the decision-record artifact into ci_report.sh and release bundle indexing once reviewers confirm the standalone JSON shape."
        ),
    }


def _markdown_lines(report: Mapping[str, Any]) -> Iterable[str]:
    yield "# Next Increment Candidates"
    yield ""
    yield "Offline candidate recipes for selecting one cohesive, non-duplicative repository increment."
    yield ""
    yield f"Generated: `{report['generated_at']}`"
    yield f"Status: **{str(report['status']).upper()}**"
    yield f"Schema version: `{report['schema_version']}`"
    yield ""
    yield "## Recommended candidate"
    yield ""
    recommended = report.get("recommended_candidate")
    if recommended:
        yield f"- ID: `{recommended['candidate_id']}`"
        yield f"- Title: {recommended['title']}"
        yield f"- Focus area: `{recommended['focus_area']}`"
        yield f"- Status: `{recommended['status']}`"
        yield f"- Suggested artifact: {recommended['suggested_artifact']}"
        yield f"- Rationale: {recommended['rationale']}"
    else:
        yield "- No candidate available. Resolve blockers and inspect repository context manually."
    yield ""
    yield "## Candidate matrix"
    yield ""
    yield "| ID | Focus area | Status | Novelty | Roadmap matches | Recent overlap | Suggested artifact |"
    yield "| --- | --- | --- | ---: | ---: | ---: | --- |"
    for candidate in report["candidate_recipes"]:
        artifact = str(candidate["suggested_artifact"]).replace("|", "\\|")
        yield (
            f"| `{candidate['candidate_id']}` | `{candidate['focus_area']}` | `{candidate['status']}` | "
            f"{candidate['novelty_score']} | {candidate['roadmap_matches']} | "
            f"{candidate['recent_overlap']} | {artifact} |"
        )
    yield ""
    yield "## Validation commands"
    yield ""
    if recommended:
        for command in recommended["validation_commands"]:
            yield f"- `{command}`"
    else:
        yield "- No validation commands available until blockers are resolved."
    yield ""
    yield "## Blockers"
    yield ""
    if report["blockers"]:
        for blocker in report["blockers"]:
            yield f"- {blocker}"
    else:
        yield "- None detected in the offline candidate inputs."
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(report["safe_scope"])


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render candidate recipes as Markdown."""

    return "\n".join(_markdown_lines(report)).rstrip() + "\n"


def write_outputs(
    report: Mapping[str, Any],
    markdown_path: Path | None,
    json_path: Path | None,
    decision_record_path: Path | None = None,
    selected_candidate_id: str | None = None,
) -> None:
    """Write requested Markdown, candidate JSON, and decision-record JSON outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if decision_record_path is not None:
        decision_record_path.parent.mkdir(parents=True, exist_ok=True)
        record = build_decision_record(report, selected_candidate_id=selected_candidate_id)
        decision_record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate offline candidate recipes for the next additive repository increment.")
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=DEFAULT_REPOSITORY_ROOT,
        help=f"Repository root containing CHANGELOG.md and goals.md. Default: {DEFAULT_REPOSITORY_ROOT}",
    )
    parser.add_argument("--markdown-path", type=Path, default=None, help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=None, help="JSON output path.")
    parser.add_argument(
        "--decision-record-path",
        type=Path,
        default=None,
        help="Optional machine-readable JSON run decision record output path.",
    )
    parser.add_argument(
        "--selected-candidate-id",
        default=None,
        help="Optional candidate ID to mark as selected in the decision record.",
    )
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_candidate_report(args.repository_root)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.repository_root / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.repository_root / DEFAULT_JSON_NAME)
    write_outputs(
        report,
        markdown_path,
        json_path,
        decision_record_path=args.decision_record_path,
        selected_candidate_id=args.selected_candidate_id,
    )
    if markdown_path is not None:
        print(f"Wrote next-increment candidate Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote next-increment candidate JSON to {json_path}")
    if args.decision_record_path is not None:
        print(f"Wrote run decision record JSON to {args.decision_record_path}")
    if markdown_path is None and json_path is None and args.decision_record_path is None:
        print("No outputs requested; remove --no-markdown or --no-json or provide --decision-record-path to write files.")
    return 0 if report["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
