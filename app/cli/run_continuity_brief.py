"""Generate an offline run-continuity brief for recurring repository maintenance.

The brief reads local roadmap, changelog, and decision-register documents to help a
maintainer choose the next cohesive additive increment without duplicating recent
work. It does not collect live data, run prediction, call networks, mutate source
artifacts, or infer operational truth.
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
DEFAULT_MARKDOWN_NAME = "run-continuity-brief.md"
DEFAULT_JSON_NAME = "run-continuity-brief.json"

SAFE_ANALYTICAL_SCOPE = (
    "Use this brief only to plan lawful defensive analytical repository maintenance, "
    "reviewer handoff, reproducibility, validation, uncertainty communication, and "
    "user-friendly tooling. It does not validate operational predictions or imply "
    "certainty about real-world activity."
)

RECENT_CHANGE_LIMIT = 8
ROADMAP_LIMIT = 10

FOCUS_AREAS: Mapping[str, Sequence[str]] = {
    "user_friendliness": (
        "user-friendly",
        "interactive",
        "dashboard",
        "quickstart",
        "setup",
        "guide",
        "status board",
        "handoff",
    ),
    "validation_and_ci": (
        "ci",
        "validation",
        "test",
        "workflow",
        "evidence",
        "artifact",
        "schema",
        "reproduce",
    ),
    "data_provenance": (
        "provenance",
        "synthetic",
        "fixture",
        "osint",
        "sentinel",
        "source",
        "ledger",
        "manifest",
    ),
    "model_diagnostics": (
        "model",
        "confidence",
        "uncertainty",
        "anomaly",
        "cluster",
        "dbscan",
        "trajectory",
        "prediction",
    ),
    "automation_planning": (
        "automation",
        "next-run",
        "decision",
        "roadmap",
        "incremental",
        "preflight",
        "rollback",
        "merge",
    ),
}


@dataclass(frozen=True)
class FocusFinding:
    """A scored focus area for selecting the next increment."""

    name: str
    score: int
    roadmap_matches: int
    recent_change_matches: int
    rationale: str


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def _extract_changelog_items(text: str, limit: int = RECENT_CHANGE_LIMIT) -> List[str]:
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


def _extract_roadmap_items(text: str, limit: int = ROADMAP_LIMIT) -> List[str]:
    items: List[str] = []
    for raw_line in text.splitlines():
        line = _normalize_line(raw_line)
        if re.match(r"^\d+\.\s+", line):
            items.append(re.sub(r"^\d+\.\s+", "", line))
        if len(items) >= limit:
            break
    return items


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _score_focus_areas(roadmap_items: Sequence[str], recent_changes: Sequence[str]) -> List[FocusFinding]:
    findings: List[FocusFinding] = []
    for name, keywords in FOCUS_AREAS.items():
        roadmap_matches = sum(1 for item in roadmap_items if _contains_any(item, keywords))
        recent_matches = sum(1 for item in recent_changes if _contains_any(item, keywords))
        score = roadmap_matches * 3 - recent_matches
        if recent_matches:
            rationale = "roadmap demand exists, but recent work may already cover part of this area"
        elif roadmap_matches:
            rationale = "roadmap demand exists with little evidence of very recent coverage"
        else:
            rationale = "little direct roadmap signal in the inspected slice"
        findings.append(FocusFinding(name, score, roadmap_matches, recent_matches, rationale))
    return sorted(findings, key=lambda item: (-item.score, item.name))


def _load_decision_register(root: Path) -> str:
    return _read_text(root / "docs" / "next_run_decision_register.md")


def _suggest_next_increment(findings: Sequence[FocusFinding]) -> Dict[str, str]:
    best = findings[0] if findings else FocusFinding("validation_and_ci", 0, 0, 0, "default safe maintenance focus")
    suggestions = {
        "user_friendliness": (
            "Prefer a small CLI or generated Markdown/JSON artifact that shortens first-run setup, "
            "operator handoff, or reviewer navigation without introducing live-data dependencies."
        ),
        "validation_and_ci": (
            "Prefer a deterministic validator, schema check, or artifact completeness guard that can run "
            "offline in CI and produce reviewer-friendly evidence."
        ),
        "data_provenance": (
            "Prefer additive provenance labels, fixture lineage checks, or source-disclosure artifacts that "
            "make synthetic, generated, and review-only records harder to confuse with operational evidence."
        ),
        "model_diagnostics": (
            "Prefer non-operational diagnostics around confidence, uncertainty, model metadata, or drift-review "
            "evidence before expanding predictive behavior."
        ),
        "automation_planning": (
            "Prefer tooling that turns existing runbooks into machine-readable next-step evidence, while avoiding "
            "another process-only document unless it unlocks a concrete check."
        ),
    }
    return {
        "focus_area": best.name,
        "recommendation": suggestions.get(best.name, suggestions["validation_and_ci"]),
        "why": best.rationale,
    }


def build_run_continuity_brief(
    repository_root: Path = DEFAULT_REPOSITORY_ROOT,
    generated_at: datetime | None = None,
    changelog_text: str | None = None,
    goals_text: str | None = None,
    decision_register_text: str | None = None,
) -> Dict[str, Any]:
    """Build a machine-readable brief for selecting the next additive run."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    changelog_text = changelog_text if changelog_text is not None else _read_text(repository_root / "CHANGELOG.md")
    goals_text = goals_text if goals_text is not None else _read_text(repository_root / "goals.md")
    decision_register_text = (
        decision_register_text if decision_register_text is not None else _load_decision_register(repository_root)
    )

    recent_changes = _extract_changelog_items(changelog_text)
    roadmap_items = _extract_roadmap_items(goals_text)
    focus_findings = _score_focus_areas(roadmap_items, recent_changes)
    next_increment = _suggest_next_increment(focus_findings)
    decision_register_present = bool(decision_register_text.strip())

    blockers = []
    if not recent_changes:
        blockers.append("CHANGELOG.md has no readable Unreleased entries; inspect recent commits before selecting work.")
    if not roadmap_items:
        blockers.append("goals.md has no numbered roadmap items; inspect repository goals before selecting work.")
    if not decision_register_present:
        blockers.append("docs/next_run_decision_register.md is missing or empty; record next-run context manually.")

    status = "blocked" if blockers else "ready"
    next_action = (
        "Resolve continuity blockers before opening a new PR."
        if blockers
        else "Use the recommended focus area to choose one cohesive additive increment, then capture validation evidence."
    )

    return {
        "generated_at": generated_at.isoformat(),
        "schema_version": "1.0",
        "status": status,
        "next_action": next_action,
        "safe_scope": SAFE_ANALYTICAL_SCOPE,
        "recent_changes": recent_changes,
        "roadmap_items": roadmap_items,
        "decision_register_present": decision_register_present,
        "focus_findings": [finding.__dict__ for finding in focus_findings],
        "recommended_next_increment": next_increment,
        "blockers": blockers,
    }


def _markdown_lines(report: Mapping[str, Any]) -> Iterable[str]:
    yield "# Run Continuity Brief"
    yield ""
    yield "A deterministic offline brief for selecting the next cohesive repository increment."
    yield ""
    yield f"Generated: `{report['generated_at']}`"
    yield f"Status: **{str(report['status']).upper()}**"
    yield f"Next action: {report['next_action']}"
    yield ""
    recommendation = report["recommended_next_increment"]
    yield "## Recommended next increment"
    yield ""
    yield f"- Focus area: `{recommendation['focus_area']}`"
    yield f"- Recommendation: {recommendation['recommendation']}"
    yield f"- Rationale: {recommendation['why']}"
    yield ""
    yield "## Focus area scores"
    yield ""
    yield "| Focus area | Score | Roadmap matches | Recent-change matches | Rationale |"
    yield "| --- | ---: | ---: | ---: | --- |"
    for finding in report["focus_findings"]:
        yield (
            f"| `{finding['name']}` | {finding['score']} | {finding['roadmap_matches']} | "
            f"{finding['recent_change_matches']} | {str(finding['rationale']).replace('|', '\\|')} |"
        )
    yield ""
    yield "## Recent changes inspected"
    yield ""
    for item in report["recent_changes"]:
        yield f"- {item}"
    if not report["recent_changes"]:
        yield "- No recent changelog entries detected."
    yield ""
    yield "## Roadmap slice inspected"
    yield ""
    for item in report["roadmap_items"]:
        yield f"- {item}"
    if not report["roadmap_items"]:
        yield "- No roadmap items detected."
    yield ""
    yield "## Blockers"
    yield ""
    for blocker in report["blockers"]:
        yield f"- {blocker}"
    if not report["blockers"]:
        yield "- None detected in the offline continuity inputs."
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(report["safe_scope"])


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the run-continuity brief as Markdown."""

    return "\n".join(_markdown_lines(report)).rstrip() + "\n"


def write_outputs(report: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested brief outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an offline run-continuity brief for the next repository increment.")
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=DEFAULT_REPOSITORY_ROOT,
        help=f"Repository root containing CHANGELOG.md and goals.md. Default: {DEFAULT_REPOSITORY_ROOT}",
    )
    parser.add_argument("--markdown-path", type=Path, default=None, help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=None, help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_run_continuity_brief(args.repository_root)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.repository_root / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.repository_root / DEFAULT_JSON_NAME)
    write_outputs(report, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote run continuity brief Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote run continuity brief JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write run continuity brief files.")
    return 0 if report["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
