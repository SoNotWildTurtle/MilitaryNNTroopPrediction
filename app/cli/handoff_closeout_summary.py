"""Export a concise offline closeout summary for analytical handoff bundles.

This command composes existing generated diagnostics into a manager-friendly
ready/blocked closeout note. It is deterministic, local-only, and intentionally
keeps predictions framed as analytical estimates rather than operational truth.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "handoff-closeout-summary.md"
DEFAULT_JSON_NAME = "handoff-closeout-summary.json"
DEFAULT_TEXT_NAME = "handoff-closeout-summary.txt"

SAFE_SCOPE = (
    "Offline closeout summary for lawful defensive/analytical handoff review. "
    "It records validation readiness, blockers, warnings, and next steps without "
    "asserting operational certainty or directing real-world action."
)

INPUTS: Mapping[str, str] = {
    "decision_log": "decision-log.json",
    "validation_receipt": "handoff-validation-receipt.json",
    "readiness_scorecard": "handoff-readiness-scorecard.json",
    "artifact_manifest": "artifact-manifest.json",
}

READY_WORDS = {"ready", "pass", "passed", "ok", "valid", "success"}
REVIEW_WORDS = {"needs_review", "review", "warn", "warning", "partial", "unknown"}
BLOCKED_WORDS = {"blocked", "fail", "failed", "invalid", "error", "missing"}


def _load_json(path: Path) -> tuple[Mapping[str, Any], bool, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, False, "missing"
    except json.JSONDecodeError as exc:
        return {}, False, f"invalid_json:{exc.lineno}:{exc.colno}"
    except OSError as exc:
        return {}, False, f"io_error:{exc.__class__.__name__}"
    if not isinstance(payload, Mapping):
        return {}, False, "not_object"
    return payload, True, None


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _status(payload: Mapping[str, Any], *, present: bool, error: str | None) -> str:
    if not present:
        return "missing" if error == "missing" else "blocked"
    for key in ("decision", "launch_status", "status", "result", "conclusion"):
        value = str(payload.get(key, "")).strip().lower()
        if value:
            return value
    if payload.get("valid") is True or payload.get("is_valid") is True:
        return "ready"
    if payload.get("valid") is False or payload.get("is_valid") is False:
        return "blocked"
    return "needs_review"


def _rank(status: str) -> int:
    normalized = status.strip().lower()
    if normalized in READY_WORDS:
        return 0
    if normalized in BLOCKED_WORDS:
        return 2
    if normalized in REVIEW_WORDS:
        return 1
    return 1


def _first_present(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _input_row(artifact_dir: Path, name: str, filename: str) -> Dict[str, Any]:
    path = artifact_dir / filename
    payload, present, error = _load_json(path)
    status = _status(payload, present=present, error=error)
    blockers = _as_list(_first_present(payload, "blockers", "errors", "failures", "missing", default=[]))
    warnings = _as_list(_first_present(payload, "warnings", "review_items", "limitations", "advisories", default=[]))
    if blockers and _rank(status) < 2:
        status = "blocked"
    elif warnings and _rank(status) == 0:
        status = "needs_review"
    return {
        "name": name,
        "path": filename,
        "present": present,
        "status": status,
        "error": error,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "score": payload.get("score"),
        "next_action": payload.get("next_action"),
    }


def _overall_status(rows: Sequence[Mapping[str, Any]]) -> str:
    if any(_rank(str(row.get("status", ""))) >= 2 for row in rows):
        return "blocked"
    if any(_rank(str(row.get("status", ""))) == 1 for row in rows):
        return "needs_review"
    return "ready"


def _closeout_action(status: str) -> str:
    if status == "blocked":
        return "Resolve blocker rows, regenerate diagnostics with `make ci-report`, then rerun this closeout summary."
    if status == "needs_review":
        return "Review warning rows, document accepted limitations, then attach the summary to the handoff bundle."
    return "Attach this closeout summary, decision log, and validation receipt to the review handoff before merge or promotion."


def build_closeout_summary(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic closeout summary from generated handoff diagnostics."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    rows = [_input_row(artifact_dir, name, filename) for name, filename in INPUTS.items()]
    status = _overall_status(rows)
    blockers = [f"{row['path']} is {row['status']}" for row in rows if _rank(str(row.get("status", ""))) >= 2]
    warnings = [f"{row['path']} needs review" for row in rows if _rank(str(row.get("status", ""))) == 1]
    ready = [row["path"] for row in rows if _rank(str(row.get("status", ""))) == 0]
    return {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "closeout_status": status,
        "next_action": _closeout_action(status),
        "ready_artifacts": ready,
        "blockers": blockers,
        "warnings": warnings,
        "inputs": rows,
        "safe_scope": SAFE_SCOPE,
        "analytical_disclaimer": (
            "This closeout summary supports reproducible review and handoff only. "
            "It does not validate live intelligence, operational targeting, or real-world certainty."
        ),
    }


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(summary: Mapping[str, Any]) -> Iterable[str]:
    yield "# Handoff Closeout Summary"
    yield ""
    yield "A concise offline closeout record for reviewer and manager handoff decisions."
    yield ""
    yield f"Generated: `{summary['generated_at']}`"
    yield f"Artifact directory: `{summary['artifact_dir']}`"
    yield f"Closeout status: **{str(summary['closeout_status']).upper()}**"
    yield f"Next action: {summary['next_action']}"
    yield ""
    yield "## Input artifacts"
    yield ""
    yield "| Artifact | Status | Blockers | Warnings | Score | Present |"
    yield "| --- | --- | ---: | ---: | --- | --- |"
    for row in summary["inputs"]:
        score = "" if row.get("score") is None else row.get("score")
        yield (
            f"| `{_escape(row['path'])}` | {_escape(row['status']).upper()} | "
            f"{row['blocker_count']} | {row['warning_count']} | {_escape(score)} | {row['present']} |"
        )
    yield ""
    yield "## Closeout notes"
    yield ""
    blockers = list(summary.get("blockers", []))
    warnings = list(summary.get("warnings", []))
    if not blockers and not warnings:
        yield "No blockers or warnings were detected from the closeout inputs."
    else:
        for blocker in blockers:
            yield f"- BLOCKER: {blocker}"
        for warning in warnings:
            yield f"- WARNING: {warning}"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(summary["safe_scope"])
    yield ""
    yield str(summary["analytical_disclaimer"])


def render_markdown(summary: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(summary)).rstrip() + "\n"


def render_text(summary: Mapping[str, Any]) -> str:
    status = str(summary.get("closeout_status", "unknown")).upper()
    blockers = len(list(summary.get("blockers", [])))
    warnings = len(list(summary.get("warnings", [])))
    return (
        f"Closeout={status}; blockers={blockers}; warnings={warnings}; "
        f"next_action={summary.get('next_action', 'Review generated diagnostics before handoff.')} "
        "Scope: analytical review only; no operational certainty claimed.\n"
    )


def write_outputs(
    summary: Mapping[str, Any],
    markdown_path: Path | None,
    json_path: Path | None,
    text_path: Path | None,
) -> None:
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if text_path is not None:
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(render_text(summary), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an offline closeout summary for handoff diagnostics.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--markdown-path", type=Path, default=None)
    parser.add_argument("--json-path", type=Path, default=None)
    parser.add_argument("--text-path", type=Path, default=None)
    parser.add_argument("--no-markdown", action="store_true")
    parser.add_argument("--no-json", action="store_true")
    parser.add_argument("--no-text", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_closeout_summary(args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    text_path = None if args.no_text else (args.text_path or args.artifact_dir / DEFAULT_TEXT_NAME)
    write_outputs(summary, markdown_path, json_path, text_path)
    if markdown_path is None and json_path is None and text_path is None:
        print(render_text(summary), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
