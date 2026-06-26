"""Generate a safe additive automation plan from diagnostic artifacts and goals.

The plan is intended for non-interactive maintenance runs. It only reads local
Markdown/JSON files and writes a deterministic Markdown/JSON action plan; it does
not collect data, run model inference, call networks, modify repositories, or
start services.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_GOALS_PATH = Path("goals.md")
DEFAULT_MARKDOWN_NAME = "automation-plan.md"
DEFAULT_JSON_NAME = "automation-plan.json"

SAFE_SCOPE = (
    "Additive maintenance only: documentation, tests, deterministic diagnostics, "
    "synthetic examples, API contracts, validation helpers, and defensive "
    "analytical tooling. Avoid destructive repository changes, force pushes, "
    "broad rewrites, live collection, offensive workflows, or data deletion."
)

KEYWORD_TARGETS: Mapping[str, str] = {
    "gui": "UX and dashboard usability",
    "dashboard": "UX and dashboard usability",
    "interactive": "UX and dashboard usability",
    "map": "Visualization and analyst review",
    "heatmap": "Visualization and analyst review",
    "alert": "Operational alerting and review handoff",
    "api": "API contract and client interoperability",
    "fastapi": "API contract and client interoperability",
    "mongodb": "Persistence readiness and configuration",
    "sentinel": "Satellite feed configuration and safe placeholders",
    "osint": "OSINT ingestion guardrails",
    "yolo": "Detection pipeline validation",
    "train": "Training workflow validation",
    "model": "Model evaluation and reproducibility",
    "prediction": "Prediction quality and regression coverage",
    "test": "Regression coverage",
    "verify": "Regression coverage",
    "automation": "Maintenance automation",
    "pipeline": "Maintenance automation",
    "security": "Security and safe operations",
    "secure": "Security and safe operations",
}


@dataclass(frozen=True)
class Goal:
    """A parsed roadmap goal."""

    number: int
    text: str


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _parse_goals(text: str) -> List[Goal]:
    goals: List[Goal] = []
    for line in text.splitlines():
        match = re.match(r"\s*(\d+)\.\s+(.+?)\s*$", line)
        if not match:
            continue
        goals.append(Goal(number=int(match.group(1)), text=match.group(2)))
    return goals


def load_goals(path: Path = DEFAULT_GOALS_PATH) -> List[Goal]:
    """Load numbered roadmap goals from a Markdown file."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return _parse_goals(text)


def _goal_category(goal_text: str) -> str:
    lowered = goal_text.lower()
    for keyword, category in KEYWORD_TARGETS.items():
        if keyword in lowered:
            return category
    return "Project roadmap"


def _score_goal(goal: Goal, triage_status: str, missing_artifacts: Sequence[str]) -> int:
    text = goal.text.lower()
    score = 0
    if any(word in text for word in ("automate", "pipeline", "cli", "setup", "monitor", "watch")):
        score += 4
    if any(word in text for word in ("gui", "dashboard", "interactive", "map", "visualize", "alert")):
        score += 3
    if any(word in text for word in ("test", "verify", "validate", "log", "statistics", "confidence")):
        score += 2
    if any(word in text for word in ("secure", "security", "sanitize", "safe")):
        score += 2
    if triage_status in {"blocked", "incomplete"} and any(
        word in text for word in ("test", "verify", "automation", "setup", "pipeline")
    ):
        score += 3
    if missing_artifacts and any(word in text for word in ("automate", "pipeline", "verify", "gui", "dashboard")):
        score += 2
    return score


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _recommended_validation_commands(triage: Mapping[str, Any], handoff: Mapping[str, Any]) -> List[str]:
    commands: List[str] = []
    next_step = str(triage.get("next_step", "")).strip()
    rerun = str(handoff.get("recommended_rerun", "")).strip()
    for command in (next_step, rerun, "make test", "make verify"):
        if command:
            commands.append(command)
    return _dedupe_preserve_order(commands)


def build_automation_plan(
    goals: Sequence[Goal],
    triage: Mapping[str, Any],
    manifest: Mapping[str, Any],
    handoff: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic, additive next-run plan from local project artifacts."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    triage_status = str(triage.get("status", "unknown")).lower()
    review_status = str(handoff.get("review_status", "unknown")).lower()
    missing_artifacts = [str(item) for item in manifest.get("missing_expected", []) if str(item)]
    health_summary = triage.get("health_summary", {}) if isinstance(triage.get("health_summary", {}), Mapping) else {}
    recommended_actions = [
        dict(action) for action in triage.get("recommended_actions", []) if isinstance(action, Mapping)
    ]

    scored_goals = sorted(
        (
            {
                "number": goal.number,
                "text": goal.text,
                "category": _goal_category(goal.text),
                "score": _score_goal(goal, triage_status, missing_artifacts),
            }
            for goal in goals
        ),
        key=lambda item: (-int(item["score"]), int(item["number"])),
    )
    top_goals = [goal for goal in scored_goals if int(goal["score"]) > 0][:5]
    if not top_goals:
        top_goals = scored_goals[:5]

    if triage_status in {"blocked", "incomplete"}:
        priority = "stabilize diagnostics before feature work"
        next_action = str(triage.get("next_step") or "make verify")
    elif review_status in {"needs_attention", "review_warnings", "needs_review"}:
        priority = "complete reviewer handoff and warning review"
        next_action = str(handoff.get("recommended_rerun") or "make verify")
    elif top_goals:
        priority = "implement the highest-scoring additive roadmap goal"
        next_action = f"Add a cohesive, tested increment for goal {top_goals[0]['number']}: {top_goals[0]['text']}"
    else:
        priority = "improve tests, docs, or release validation"
        next_action = "Add regression coverage or documentation for the current maintenance workflow."

    return {
        "generated_at": generated_at.isoformat(),
        "status": "ready_for_additive_iteration" if triage_status not in {"blocked", "incomplete"} else "needs_validation",
        "priority": priority,
        "next_action": next_action,
        "triage_status": triage_status,
        "review_status": review_status,
        "health_summary": {
            "ok": int(health_summary.get("ok", 0) or 0),
            "warn": int(health_summary.get("warn", 0) or 0),
            "fail": int(health_summary.get("fail", 0) or 0),
        },
        "artifact_count": int(manifest.get("file_count", 0) or 0),
        "missing_artifacts": missing_artifacts,
        "recommended_actions": recommended_actions,
        "top_goals": top_goals,
        "validation_commands": _recommended_validation_commands(triage, handoff),
        "additive_guardrails": [
            "Prefer new helpers, tests, docs, examples, and small integrations over replacing working code.",
            "Do not delete repository content, rewrite history, force-push, or make broad subtractive refactors.",
            "Keep live data collection, prediction, deployment, and offensive/security-sensitive behavior out of diagnostics.",
            "Document compatibility impact and migration notes for any narrow breaking change.",
        ],
        "safe_scope": SAFE_SCOPE,
    }


def _markdown_lines(plan: Mapping[str, Any]) -> Iterable[str]:
    yield "# Automation Plan"
    yield ""
    yield "A deterministic next-run plan for safe, additive repository maintenance."
    yield ""
    yield f"Generated: `{plan['generated_at']}`"
    yield f"Status: **{str(plan['status']).upper()}**"
    yield f"Priority: **{plan['priority']}**"
    yield ""
    yield "## Recommended next action"
    yield ""
    yield str(plan["next_action"])
    yield ""
    yield "## Current validation context"
    yield ""
    health = plan["health_summary"]
    yield f"- Triage status: `{plan['triage_status']}`"
    yield f"- Reviewer handoff status: `{plan['review_status']}`"
    yield f"- Health checks: {health['ok']} ok, {health['warn']} warnings, {health['fail']} failures"
    yield f"- Indexed artifacts: {plan['artifact_count']}"
    yield ""

    if plan["missing_artifacts"]:
        yield "## Missing artifacts"
        yield ""
        for artifact in plan["missing_artifacts"]:
            yield f"- `{artifact}`"
        yield ""

    actions = plan["recommended_actions"]
    if actions:
        yield "## Narrow remediation actions"
        yield ""
        yield "| Reason | Target | Detail |"
        yield "| --- | --- | --- |"
        for action in actions:
            reason = str(action.get("reason", "")).replace("|", "\\|")
            target = str(action.get("target", "")).replace("|", "\\|")
            detail = str(action.get("detail", "") or "—").replace("|", "\\|")
            yield f"| {reason} | `{target}` | {detail} |"
        yield ""

    goals = plan["top_goals"]
    if goals:
        yield "## Highest-value additive roadmap candidates"
        yield ""
        yield "| Goal | Category | Score | Summary |"
        yield "| ---: | --- | ---: | --- |"
        for goal in goals:
            text = str(goal["text"]).replace("|", "\\|")
            yield f"| {goal['number']} | {goal['category']} | {goal['score']} | {text} |"
        yield ""

    yield "## Validation commands"
    yield ""
    for command in plan["validation_commands"]:
        yield f"- `{command}`"
    yield ""
    yield "## Additive guardrails"
    yield ""
    for guardrail in plan["additive_guardrails"]:
        yield f"- {guardrail}"
    yield ""
    yield "## Safe scope"
    yield ""
    yield str(plan["safe_scope"])


def render_markdown(plan: Mapping[str, Any]) -> str:
    """Render an automation plan as Markdown."""

    return "\n".join(_markdown_lines(plan)).rstrip() + "\n"


def write_outputs(plan: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested automation-plan outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(plan), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a safe additive automation plan from goals and diagnostic artifacts."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory containing generated diagnostics. Default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument(
        "--goals-path",
        type=Path,
        default=DEFAULT_GOALS_PATH,
        help=f"Roadmap goals Markdown file. Default: {DEFAULT_GOALS_PATH}",
    )
    parser.add_argument("--triage-json", type=Path, default=None, help="Override triage summary JSON path.")
    parser.add_argument("--manifest-json", type=Path, default=None, help="Override artifact manifest JSON path.")
    parser.add_argument("--handoff-json", type=Path, default=None, help="Override reviewer handoff JSON path.")
    parser.add_argument("--markdown-path", type=Path, default=None, help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=None, help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    triage = _load_json(args.triage_json or artifact_dir / "triage-summary.json", {})
    manifest = _load_json(args.manifest_json or artifact_dir / "artifact-manifest.json", {})
    handoff = _load_json(args.handoff_json or artifact_dir / "reviewer-handoff.json", {})
    goals = load_goals(args.goals_path)
    plan = build_automation_plan(goals, triage, manifest, handoff)

    markdown_path = None if args.no_markdown else (args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)
    write_outputs(plan, markdown_path, json_path)

    if markdown_path is not None:
        print(f"Wrote automation plan Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote automation plan JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write automation plan files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
