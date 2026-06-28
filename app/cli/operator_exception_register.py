"""Export an offline operator exception register for generated diagnostics.

The register turns scattered blockers, warnings, missing artifacts, and review
items from existing handoff diagnostics into a single prioritized queue. It is
local-only, deterministic, and frames every entry as an analytical review item
rather than operational certainty or targeting guidance.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "operator-exception-register.md"
DEFAULT_JSON_NAME = "operator-exception-register.json"
DEFAULT_TEXT_NAME = "operator-exception-register.txt"

SAFE_SCOPE = (
    "Offline exception register for lawful defensive/analytical review. It "
    "helps reviewers resolve evidence, provenance, validation, and handoff "
    "gaps without asserting operational certainty or directing real-world action."
)

INPUTS: Mapping[str, str] = {
    "decision_log": "decision-log.json",
    "closeout_summary": "handoff-closeout-summary.json",
    "validation_receipt": "handoff-validation-receipt.json",
    "readiness_scorecard": "handoff-readiness-scorecard.json",
    "provenance_matrix": "provenance-validation-matrix.json",
    "evidence_checklist": "evidence-checklist.json",
    "handoff_integrity": "handoff-integrity-report.json",
    "artifact_manifest": "artifact-manifest.json",
}

BLOCKED_WORDS = {"blocked", "fail", "failed", "invalid", "error", "missing"}
REVIEW_WORDS = {"needs_review", "review", "warn", "warning", "partial", "unknown"}
READY_WORDS = {"ready", "pass", "passed", "ok", "valid", "success"}

OWNER_HINTS: Sequence[tuple[str, str]] = (
    ("provenance", "data/provenance reviewer"),
    ("evidence", "analytical evidence reviewer"),
    ("schema", "contract/schema maintainer"),
    ("validation", "release validation owner"),
    ("manifest", "artifact bundle owner"),
    ("missing", "artifact bundle owner"),
    ("privacy", "privacy/security reviewer"),
    ("security", "privacy/security reviewer"),
    ("uncertainty", "analytical methods reviewer"),
    ("readiness", "operations handoff owner"),
    ("handoff", "operations handoff owner"),
)


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


def _as_items(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _item_text(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("message", "summary", "description", "name", "path", "id"):
            if value.get(key):
                return str(value[key])
        return json.dumps(value, sort_keys=True)
    return str(value)


def _status(payload: Mapping[str, Any], *, present: bool, error: str | None) -> str:
    if not present:
        return "missing" if error == "missing" else "blocked"
    for key in ("closeout_status", "decision", "launch_status", "status", "result", "conclusion"):
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
    if normalized in REVIEW_WORDS:
        return 1
    if normalized in BLOCKED_WORDS:
        return 2
    return 1


def _owner_for(text: str, source: str) -> str:
    haystack = f"{source} {text}".lower()
    for needle, owner in OWNER_HINTS:
        if needle in haystack:
            return owner
    return "review coordinator"


def _severity(status: str, kind: str) -> str:
    if kind in {"missing_artifact", "invalid_artifact", "blocker"} or _rank(status) >= 2:
        return "blocker"
    if kind == "warning" or _rank(status) == 1:
        return "warning"
    return "review"


def _entry(
    *,
    source: str,
    artifact_path: str,
    status: str,
    kind: str,
    detail: str,
    index: int,
) -> Dict[str, Any]:
    severity = _severity(status, kind)
    return {
        "id": f"{source}:{kind}:{index}",
        "source": source,
        "artifact_path": artifact_path,
        "severity": severity,
        "kind": kind,
        "status": status,
        "detail": detail,
        "owner_hint": _owner_for(detail, source),
        "next_action": _next_action(severity, kind, artifact_path),
    }


def _next_action(severity: str, kind: str, artifact_path: str) -> str:
    if kind == "missing_artifact":
        return f"Regenerate diagnostics with `make ci-report` and confirm `{artifact_path}` is present."
    if kind == "invalid_artifact":
        return f"Rebuild `{artifact_path}`, inspect JSON formatting, and rerun the narrow CLI that produces it."
    if severity == "blocker":
        return "Resolve before merge, promotion, or handoff signoff; rerun the relevant validation after repair."
    if severity == "warning":
        return "Review and document accepted limitation, owner, and follow-up before handoff."
    return "Record reviewer disposition and keep the item attached to the handoff bundle."


def _collect_entries(source: str, filename: str, artifact_dir: Path) -> list[Dict[str, Any]]:
    path = artifact_dir / filename
    payload, present, error = _load_json(path)
    status = _status(payload, present=present, error=error)
    entries: list[Dict[str, Any]] = []
    counter = 1

    if not present:
        kind = "missing_artifact" if error == "missing" else "invalid_artifact"
        entries.append(
            _entry(
                source=source,
                artifact_path=filename,
                status=status,
                kind=kind,
                detail=error or "artifact unavailable",
                index=counter,
            )
        )
        return entries

    for key, kind in (
        ("blockers", "blocker"),
        ("errors", "blocker"),
        ("failures", "blocker"),
        ("missing", "blocker"),
        ("warnings", "warning"),
        ("review_items", "warning"),
        ("limitations", "warning"),
        ("advisories", "warning"),
    ):
        for raw_item in _as_items(payload.get(key)):
            entries.append(
                _entry(
                    source=source,
                    artifact_path=filename,
                    status=status,
                    kind=kind,
                    detail=_item_text(raw_item),
                    index=counter,
                )
            )
            counter += 1

    if not entries and _rank(status) > 0:
        entries.append(
            _entry(
                source=source,
                artifact_path=filename,
                status=status,
                kind="status_review",
                detail=f"Artifact status is {status}; reviewer disposition is required.",
                index=counter,
            )
        )

    return entries


def _counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {"blocker": 0, "warning": 0, "review": 0}
    for entry in entries:
        severity = str(entry.get("severity", "review"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _overall_status(entries: Sequence[Mapping[str, Any]]) -> str:
    counts = _counts(entries)
    if counts.get("blocker", 0):
        return "blocked"
    if counts.get("warning", 0) or counts.get("review", 0):
        return "needs_review"
    return "ready"


def build_exception_register(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic exception register from generated diagnostics."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    entries: list[Dict[str, Any]] = []
    for source, filename in INPUTS.items():
        entries.extend(_collect_entries(source, filename, artifact_dir))
    counts = _counts(entries)
    status = _overall_status(entries)
    return {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "status": status,
        "counts": counts,
        "exception_count": len(entries),
        "entries": entries,
        "next_action": _register_next_action(status),
        "safe_scope": SAFE_SCOPE,
        "analytical_disclaimer": (
            "This register supports reproducible review and staff handoff only. "
            "It does not validate live intelligence, operational targeting, or real-world certainty."
        ),
    }


def _register_next_action(status: str) -> str:
    if status == "blocked":
        return "Resolve blocker entries, regenerate diagnostics with `make ci-report`, then rerun the exception register."
    if status == "needs_review":
        return "Assign warning/review entries to owners, document accepted limitations, and attach the register to handoff notes."
    return "Attach the clean exception register to the handoff bundle as evidence that no generated blockers were detected."


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(register: Mapping[str, Any]) -> Iterable[str]:
    yield "# Operator Exception Register"
    yield ""
    yield "A consolidated offline queue for generated diagnostic blockers, warnings, missing artifacts, and review items."
    yield ""
    yield f"Generated: `{register['generated_at']}`"
    yield f"Artifact directory: `{register['artifact_dir']}`"
    yield f"Register status: **{str(register['status']).upper()}**"
    counts = register["counts"]
    yield f"Counts: blockers={counts.get('blocker', 0)}, warnings={counts.get('warning', 0)}, review={counts.get('review', 0)}"
    yield f"Next action: {register['next_action']}"
    yield ""
    yield "## Exceptions"
    yield ""
    entries = list(register.get("entries", []))
    if not entries:
        yield "No generated exceptions were detected across the configured diagnostics."
    else:
        yield "| ID | Severity | Source | Owner hint | Detail | Next action |"
        yield "| --- | --- | --- | --- | --- | --- |"
        for entry in entries:
            yield (
                f"| `{_escape(entry['id'])}` | {_escape(entry['severity']).upper()} | "
                f"`{_escape(entry['artifact_path'])}` | {_escape(entry['owner_hint'])} | "
                f"{_escape(entry['detail'])} | {_escape(entry['next_action'])} |"
            )
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(register["safe_scope"])
    yield ""
    yield str(register["analytical_disclaimer"])


def render_markdown(register: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(register)).rstrip() + "\n"


def render_text(register: Mapping[str, Any]) -> str:
    counts = register.get("counts", {})
    return (
        f"Exceptions={str(register.get('status', 'unknown')).upper()}; "
        f"blockers={counts.get('blocker', 0)}; warnings={counts.get('warning', 0)}; "
        f"review={counts.get('review', 0)}; next_action={register.get('next_action', 'Review diagnostics before handoff.')} "
        "Scope: analytical review only; no operational certainty claimed.\n"
    )


def write_outputs(
    register: Mapping[str, Any],
    markdown_path: Path | None,
    json_path: Path | None,
    text_path: Path | None,
) -> None:
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(register), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(register, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if text_path is not None:
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(render_text(register), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an offline exception register for handoff diagnostics.")
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
    register = build_exception_register(args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    text_path = None if args.no_text else (args.text_path or args.artifact_dir / DEFAULT_TEXT_NAME)
    write_outputs(register, markdown_path, json_path, text_path)
    if markdown_path is None and json_path is None and text_path is None:
        print(render_text(register), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
