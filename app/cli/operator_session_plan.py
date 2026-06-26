"""Generate a ranked operator session plan from local diagnostic artifacts.

This CLI reads deterministic CI/release artifacts and produces a short handoff for the
next safe maintenance session. It never performs ingestion, prediction, scanning,
network activity, deployment, or model execution.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "operator-session-plan.md"
DEFAULT_JSON_NAME = "operator-session-plan.json"
DEFAULT_TRIAGE_NAME = "triage-summary.json"
DEFAULT_RELEASE_NOTES_NAME = "release-notes.json"
DEFAULT_HANDOFF_NAME = "reviewer-handoff.json"

STATUS_PRIORITY = {
    "blocked": 100,
    "incomplete": 80,
    "review": 60,
    "ready": 20,
    "unknown": 40,
}


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _append_unique_task(tasks: List[Dict[str, Any]], task: Mapping[str, Any]) -> None:
    key = (str(task.get("title", "")), str(task.get("command", "")), str(task.get("source", "")))
    for existing in tasks:
        existing_key = (
            str(existing.get("title", "")),
            str(existing.get("command", "")),
            str(existing.get("source", "")),
        )
        if existing_key == key:
            return
    tasks.append(dict(task))


def _task_from_recommended_action(action: Mapping[str, Any], index: int) -> Dict[str, Any]:
    reason = _first_text(action.get("reason"), default=f"recommended action {index}")
    return {
        "rank": 0,
        "title": reason,
        "command": _first_text(action.get("target"), default="make verify"),
        "why": _first_text(
            action.get("detail"),
            action.get("remediation"),
            default="Generated from CI triage guidance.",
        ),
        "done_when": _first_text(
            action.get("remediation"),
            default="The target completes cleanly and artifacts are regenerated.",
        ),
        "source": "triage-summary",
    }


def _release_note_tasks(release_notes: Mapping[str, Any]) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for key in ("priority_items", "follow_up_items", "risks", "warnings"):
        for index, item in enumerate(_as_list(release_notes.get(key)), start=1):
            if isinstance(item, Mapping):
                title = _first_text(
                    item.get("title"), item.get("name"), item.get("reason"), default=f"{key} {index}"
                )
                detail = _first_text(
                    item.get("detail"),
                    item.get("summary"),
                    item.get("remediation"),
                    default="Review release notes item.",
                )
            else:
                title = str(item)
                detail = "Review release notes item."
            tasks.append(
                {
                    "rank": 0,
                    "title": title,
                    "command": "make verify",
                    "why": detail,
                    "done_when": "The release notes item is resolved or documented as an accepted risk.",
                    "source": f"release-notes:{key}",
                }
            )
    return tasks


def _handoff_tasks(handoff: Mapping[str, Any]) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for key in ("review_steps", "next_steps", "checklist", "handoff_items"):
        for index, item in enumerate(_as_list(handoff.get(key)), start=1):
            if isinstance(item, Mapping):
                title = _first_text(
                    item.get("title"), item.get("task"), item.get("name"), default=f"{key} {index}"
                )
                command = _first_text(item.get("command"), item.get("target"), default="make verify")
                detail = _first_text(
                    item.get("detail"), item.get("why"), item.get("description"), default="Review handoff item."
                )
            else:
                title = str(item)
                command = "make verify"
                detail = "Review handoff item."
            tasks.append(
                {
                    "rank": 0,
                    "title": title,
                    "command": command,
                    "why": detail,
                    "done_when": "The handoff item is complete or explicitly deferred.",
                    "source": f"reviewer-handoff:{key}",
                }
            )
    return tasks


def _fallback_tasks(status: str) -> List[Dict[str, Any]]:
    if status == "ready":
        return [
            {
                "rank": 0,
                "title": "Review generated bundle landing page",
                "command": "make ci-report",
                "why": "No blockers were detected, so the highest-value next step is reviewer verification.",
                "done_when": "release-bundle-index.html opens and links the expected diagnostics.",
                "source": "fallback",
            }
        ]
    return [
        {
            "rank": 0,
            "title": "Regenerate diagnostics and validation artifacts",
            "command": "make verify",
            "why": "No specific task was available, so rebuild the deterministic local verification bundle.",
            "done_when": "make verify completes and operator-session-plan.md is regenerated.",
            "source": "fallback",
        }
    ]


def build_operator_session_plan(
    triage_summary: Mapping[str, Any],
    release_notes: Mapping[str, Any] | None = None,
    reviewer_handoff: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
    max_tasks: int = 5,
) -> Dict[str, Any]:
    """Build a deterministic ranked maintenance plan from generated artifacts."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    release_notes = release_notes or {}
    reviewer_handoff = reviewer_handoff or {}
    status = _first_text(triage_summary.get("status"), default="unknown").lower()
    health_value = triage_summary.get("health_summary", {})
    health_summary = health_value if isinstance(health_value, Mapping) else {}

    tasks: List[Dict[str, Any]] = []
    for index, action in enumerate(_as_list(triage_summary.get("recommended_actions")), start=1):
        if isinstance(action, Mapping):
            _append_unique_task(tasks, _task_from_recommended_action(action, index))

    for task in _release_note_tasks(release_notes):
        _append_unique_task(tasks, task)
    for task in _handoff_tasks(reviewer_handoff):
        _append_unique_task(tasks, task)

    if not tasks:
        for task in _fallback_tasks(status):
            _append_unique_task(tasks, task)

    base_priority = STATUS_PRIORITY.get(status, STATUS_PRIORITY["unknown"])
    for index, task in enumerate(tasks, start=1):
        source = str(task.get("source", ""))
        source_bonus = 20 if source.startswith("triage") else 10 if source.startswith("release-notes") else 0
        task["rank"] = base_priority + source_bonus + max(0, max_tasks - index)

    tasks = sorted(tasks, key=lambda item: (-int(item.get("rank", 0)), str(item.get("title", ""))))[:max_tasks]

    if status in {"blocked", "incomplete"}:
        objective = "Remove the highest-priority blocker and regenerate deterministic diagnostics."
    elif status == "review":
        objective = "Review warnings, document accepted risk, and rerun verification."
    elif status == "ready":
        objective = "Package the diagnostics bundle for reviewer or operator handoff."
    else:
        objective = "Rebuild diagnostics and establish a clear next action."

    return {
        "generated_at": generated_at.isoformat(),
        "status": status,
        "objective": objective,
        "health_summary": {
            "ok": int(health_summary.get("ok", 0) or 0),
            "warn": int(health_summary.get("warn", 0) or 0),
            "fail": int(health_summary.get("fail", 0) or 0),
        },
        "tasks": tasks,
        "next_command": tasks[0]["command"] if tasks else "make verify",
        "safe_scope": "Local diagnostics, deterministic tests, generated artifacts, documentation, and user-facing handoff automation only.",
    }


def _markdown_lines(plan: Mapping[str, Any]) -> Iterable[str]:
    yield "# Operator Session Plan"
    yield ""
    yield f"Generated: `{plan['generated_at']}`"
    yield f"Status: **{str(plan['status']).upper()}**"
    yield f"Objective: {plan['objective']}"
    yield ""
    yield "## Health summary"
    yield ""
    health = plan["health_summary"]
    yield f"- OK: {health['ok']}"
    yield f"- Warnings: {health['warn']}"
    yield f"- Failures: {health['fail']}"
    yield ""
    yield "## Start here"
    yield ""
    yield f"`{plan['next_command']}`"
    yield ""
    yield "## Ranked tasks"
    yield ""
    yield "| Rank | Task | Command | Why | Done when | Source |"
    yield "| ---: | --- | --- | --- | --- | --- |"
    for task in plan["tasks"]:
        title = str(task.get("title", "")).replace("|", "\\|")
        command = str(task.get("command", "make verify")).replace("|", "\\|")
        why = str(task.get("why", "")).replace("|", "\\|")
        done_when = str(task.get("done_when", "")).replace("|", "\\|")
        source = str(task.get("source", "")).replace("|", "\\|")
        yield f"| {task.get('rank', 0)} | {title} | `{command}` | {why} | {done_when} | {source} |"
    yield ""
    yield "## Safe scope"
    yield ""
    yield str(plan["safe_scope"])


def render_markdown(plan: Mapping[str, Any]) -> str:
    """Render the operator session plan as Markdown."""

    return "\n".join(_markdown_lines(plan)).rstrip() + "\n"


def write_outputs(plan: Mapping[str, Any], markdown_path: Path, json_path: Path | None) -> None:
    """Write Markdown and optional JSON outputs."""

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(plan), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a ranked operator session plan from diagnostic artifacts.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"diagnostic artifact directory; default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument("--triage-json", type=Path, default=None, help="triage summary JSON path")
    parser.add_argument("--release-notes-json", type=Path, default=None, help="release notes JSON path")
    parser.add_argument("--handoff-json", type=Path, default=None, help="reviewer handoff JSON path")
    parser.add_argument("--markdown-path", type=Path, default=None, help="operator session plan Markdown output path")
    parser.add_argument("--json-path", type=Path, default=None, help="operator session plan JSON output path")
    parser.add_argument("--max-tasks", type=int, default=5, help="maximum ranked tasks to include; default: 5")
    parser.add_argument("--no-json", action="store_true", help="only write Markdown output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    triage_path = args.triage_json or artifact_dir / DEFAULT_TRIAGE_NAME
    release_notes_path = args.release_notes_json or artifact_dir / DEFAULT_RELEASE_NOTES_NAME
    handoff_path = args.handoff_json or artifact_dir / DEFAULT_HANDOFF_NAME
    markdown_path = args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)

    plan = build_operator_session_plan(
        triage_summary=_load_json(triage_path, {"status": "unknown", "health_summary": {}, "recommended_actions": []}),
        release_notes=_load_json(release_notes_path, {}),
        reviewer_handoff=_load_json(handoff_path, {}),
        max_tasks=max(1, args.max_tasks),
    )
    write_outputs(plan, markdown_path, json_path)

    print(f"Wrote operator session plan Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote operator session plan JSON to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
