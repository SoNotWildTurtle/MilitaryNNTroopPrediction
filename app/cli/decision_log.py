"""Export an offline analytical decision log for reviewer handoffs.

The log is intentionally deterministic and local-only. It summarizes existing
diagnostic artifacts so operators can explain why a handoff is ready, blocked,
or needs review without treating predictive output as operational certainty.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "decision-log.md"
DEFAULT_JSON_NAME = "decision-log.json"
DEFAULT_SUMMARY_NAME = "decision-log-summary.txt"

SAFE_SCOPE = (
    "Offline decision log for lawful defensive/analytical handoff review. It "
    "summarizes generated diagnostics, uncertainty, provenance, and validation "
    "signals without making operational targeting claims or asserting certainty."
)

INPUT_ARTIFACTS: Mapping[str, Mapping[str, str]] = {
    "readiness_scorecard": {
        "path": "handoff-readiness-scorecard.json",
        "purpose": "Weighted readiness score from provenance, evidence, validation, and artifact quality gates.",
    },
    "validation_receipt": {
        "path": "handoff-validation-receipt.json",
        "purpose": "Final validation receipt and blocker summary for handoff promotion.",
    },
    "provenance_matrix": {
        "path": "provenance-validation-matrix.json",
        "purpose": "Cross-artifact provenance gate matrix for generated, synthetic, preview, and review labels.",
    },
    "evidence_checklist": {
        "path": "evidence-checklist.json",
        "purpose": "Baseline evidence checklist for repeatable analytical review.",
    },
    "handoff_integrity": {
        "path": "handoff-integrity-report.json",
        "purpose": "Cross-artifact integrity report for reviewer handoff consistency.",
    },
    "uncertainty_packet": {
        "path": "uncertainty-review-packet.json",
        "purpose": "Uncertainty and limitation review packet for analytical caution.",
    },
    "artifact_manifest": {
        "path": "artifact-manifest.json",
        "purpose": "Generated artifact inventory with size and hash metadata.",
    },
}


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


def _status_rank(status: Any) -> int:
    normalized = str(status or "").strip().lower()
    ranks = {
        "ready": 0,
        "pass": 0,
        "passed": 0,
        "ok": 0,
        "valid": 0,
        "success": 0,
        "needs_review": 1,
        "review": 1,
        "warn": 1,
        "warning": 1,
        "partial": 1,
        "unknown": 1,
        "missing": 2,
        "blocked": 2,
        "fail": 2,
        "failed": 2,
        "invalid": 2,
        "error": 2,
    }
    return ranks.get(normalized, 1)


def _extract_status(payload: Mapping[str, Any], *, present: bool, error: str | None) -> str:
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


def _count(payload: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, list):
            return len(value)
    return 0


def _extract_summary(name: str, payload: Mapping[str, Any]) -> str:
    if name == "readiness_scorecard":
        score = payload.get("score")
        status = payload.get("status", "unknown")
        if score is not None:
            return f"score={score}/100 status={status}"
    if name == "validation_receipt":
        blockers = _count(payload, "blockers", "errors", "failures")
        return f"validation blockers={blockers}"
    if name == "provenance_matrix":
        rows = _count(payload, "rows", "artifacts", "entries")
        return f"provenance rows={rows}"
    if name == "evidence_checklist":
        blockers = _count(payload, "blockers", "missing", "missing_expected")
        warnings = _count(payload, "warnings", "review_items", "needs_review")
        return f"evidence blockers={blockers} warnings={warnings}"
    if name == "handoff_integrity":
        blockers = _count(payload, "blockers", "mismatches", "missing")
        return f"integrity blockers={blockers}"
    if name == "uncertainty_packet":
        warnings = _count(payload, "warnings", "review_items", "limitations")
        return f"uncertainty review_items={warnings}"
    if name == "artifact_manifest":
        return f"artifact_count={payload.get('file_count', _count(payload, 'files'))}"
    return "summary unavailable"


def _artifact_row(artifact_dir: Path, name: str, definition: Mapping[str, str]) -> Dict[str, Any]:
    rel_path = definition["path"]
    path = artifact_dir / rel_path
    payload, present, error = _load_json(path)
    status = _extract_status(payload, present=present, error=error)
    blockers = _count(payload, "blockers", "missing", "missing_expected", "failures", "errors")
    warnings = _count(payload, "warnings", "review_items", "needs_review", "advisories", "limitations")
    if blockers and _status_rank(status) < 2:
        status = "blocked"
    elif warnings and _status_rank(status) == 0:
        status = "needs_review"
    return {
        "name": name,
        "path": rel_path,
        "purpose": definition["purpose"],
        "present": present,
        "status": status,
        "error": error,
        "blocker_count": blockers,
        "warning_count": warnings,
        "summary": _extract_summary(name, payload) if present else str(error or "missing"),
    }


def _overall_decision(rows: Sequence[Mapping[str, Any]]) -> str:
    if any(_status_rank(row.get("status")) >= 2 for row in rows):
        return "blocked"
    if any(_status_rank(row.get("status")) == 1 for row in rows):
        return "needs_review"
    return "ready"


def _next_action(decision: str) -> str:
    if decision == "blocked":
        return "Repair missing or blocked diagnostic artifacts, rerun `make ci-report`, then re-export the decision log."
    if decision == "needs_review":
        return "Review warning rows, document accepted limitations, rerun narrow generators if needed, then attach the log to the handoff."
    return "Attach the decision log to the handoff bundle and run `make verify` before promotion or merge."


def build_decision_log(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic, machine-readable decision log from diagnostics."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    rows = [
        _artifact_row(artifact_dir, name, definition)
        for name, definition in INPUT_ARTIFACTS.items()
    ]
    decision = _overall_decision(rows)
    blockers = [
        f"{row['path']} is {row['status']} ({row['summary']})"
        for row in rows
        if _status_rank(row.get("status")) >= 2
    ]
    warnings = [
        f"{row['path']} needs review ({row['summary']})"
        for row in rows
        if _status_rank(row.get("status")) == 1
    ]
    return {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "decision": decision,
        "next_action": _next_action(decision),
        "artifacts": rows,
        "blockers": blockers,
        "warnings": warnings,
        "safe_scope": SAFE_SCOPE,
        "analytical_disclaimer": (
            "This log supports reproducible review and handoff decisions only. "
            "It does not validate live intelligence, operational targeting, or real-world certainty."
        ),
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(log: Mapping[str, Any]) -> Iterable[str]:
    yield "# Analytical Decision Log"
    yield ""
    yield "A deterministic offline log for deciding whether a generated analytical handoff is ready, blocked, or still needs review."
    yield ""
    yield f"Generated: `{log['generated_at']}`"
    yield f"Artifact directory: `{log['artifact_dir']}`"
    yield f"Decision: **{str(log['decision']).upper()}**"
    yield f"Next action: {log['next_action']}"
    yield ""
    yield "## Artifact signals"
    yield ""
    yield "| Artifact | Status | Blockers | Warnings | Summary | Purpose |"
    yield "| --- | --- | ---: | ---: | --- | --- |"
    for row in log["artifacts"]:
        yield (
            f"| `{_escape_table(row['path'])}` | {_escape_table(row['status']).upper()} | "
            f"{row['blocker_count']} | {row['warning_count']} | {_escape_table(row['summary'])} | "
            f"{_escape_table(row['purpose'])} |"
        )
    yield ""
    yield "## Blockers and warnings"
    yield ""
    blockers = list(log.get("blockers", []))
    warnings = list(log.get("warnings", []))
    if not blockers and not warnings:
        yield "No blockers or warnings were detected from the available diagnostic artifacts."
    else:
        for blocker in blockers:
            yield f"- BLOCKER: {blocker}"
        for warning in warnings:
            yield f"- WARNING: {warning}"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(log["safe_scope"])
    yield ""
    yield str(log["analytical_disclaimer"])


def render_markdown(log: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(log)).rstrip() + "\n"


def render_summary(log: Mapping[str, Any]) -> str:
    """Render a single-line privacy-safe handoff summary for chat/email/status tools."""

    decision = str(log.get("decision", "unknown")).upper()
    blockers = len(list(log.get("blockers", [])))
    warnings = len(list(log.get("warnings", [])))
    next_action = str(log.get("next_action", "Review generated diagnostics before handoff."))
    return (
        f"Decision={decision}; blockers={blockers}; warnings={warnings}; "
        f"next_action={next_action} Scope: analytical review only; no operational certainty claimed.\n"
    )


def write_outputs(
    log: Mapping[str, Any],
    markdown_path: Path | None,
    json_path: Path | None,
    summary_path: Path | None = None,
) -> None:
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(log), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(render_summary(log), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an offline analytical decision log for handoff diagnostics.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--markdown-path", type=Path, default=None)
    parser.add_argument("--json-path", type=Path, default=None)
    parser.add_argument("--summary-path", type=Path, default=None)
    parser.add_argument("--no-markdown", action="store_true")
    parser.add_argument("--no-json", action="store_true")
    parser.add_argument("--no-summary", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log = build_decision_log(args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    summary_path = None if args.no_summary else (args.summary_path or args.artifact_dir / DEFAULT_SUMMARY_NAME)
    write_outputs(log, markdown_path, json_path, summary_path)
    if markdown_path is not None:
        print(f"Wrote analytical decision log Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote analytical decision log JSON to {json_path}")
    if summary_path is not None:
        print(f"Wrote analytical decision log summary to {summary_path}")
    if markdown_path is None and json_path is None and summary_path is None:
        print("No outputs requested; remove --no-markdown, --no-json, or --no-summary to write decision log files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
