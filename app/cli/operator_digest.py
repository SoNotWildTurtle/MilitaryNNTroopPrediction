"""Generate a concise operator-facing digest from CI diagnostics artifacts.

The digest is a safe handoff layer: it reads only local generated JSON and
Markdown artifacts, then writes a small Markdown/JSON briefing for users who do
not want to inspect every diagnostic file before deciding what to do next.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from app.cli.artifact_manifest import DEFAULT_ARTIFACT_DIR

DEFAULT_MARKDOWN_NAME = "operator-digest.md"
DEFAULT_JSON_NAME = "operator-digest.json"

STATUS_LABELS = {
    "ready": "Ready for review",
    "review": "Review warnings",
    "review_warnings": "Review warnings",
    "needs_review": "Needs review",
    "needs_attention": "Needs attention",
    "incomplete": "Incomplete bundle",
    "blocked": "Blocked",
}


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_preview(path: Path, max_chars: int = 700) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _status_label(status: str) -> str:
    normalized = status.lower().strip()
    return STATUS_LABELS.get(normalized, normalized.replace("_", " ").title() or "Unknown")


def _first_nonempty(*values: Any, default: str = "make verify") -> str:
    for value in values:
        if value:
            return str(value)
    return default


def build_operator_digest(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build deterministic operator-facing digest data from local artifacts."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    health = _load_json(artifact_dir / "release-health.json")
    manifest = _load_json(artifact_dir / "artifact-manifest.json")
    triage = _load_json(artifact_dir / "triage-summary.json")
    handoff = _load_json(artifact_dir / "reviewer-handoff.json")

    health_status = str(health.get("status") or "unknown")
    review_status = str(handoff.get("review_status") or triage.get("status") or health_status)
    missing_expected = manifest.get("missing_expected", [])
    if not isinstance(missing_expected, list):
        missing_expected = []
    missing_key_artifacts = handoff.get("missing_key_artifacts", [])
    if not isinstance(missing_key_artifacts, list):
        missing_key_artifacts = []

    recommended_actions = triage.get("recommended_actions", [])
    if not isinstance(recommended_actions, list):
        recommended_actions = []

    next_step = _first_nonempty(
        triage.get("next_step"),
        handoff.get("recommended_rerun"),
        default="make verify",
    )
    artifact_count = int(manifest.get("file_count", 0) or triage.get("artifact_count", 0) or 0)

    blocking_reasons = []
    if missing_expected:
        blocking_reasons.append(f"{len(missing_expected)} expected artifact(s) missing")
    if missing_key_artifacts:
        blocking_reasons.append(f"{len(missing_key_artifacts)} key review artifact(s) missing")
    failing_checks = triage.get("failing_checks", [])
    if isinstance(failing_checks, list) and failing_checks:
        blocking_reasons.append(f"{len(failing_checks)} failing health check(s)")

    digest: Dict[str, Any] = {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "status": review_status,
        "status_label": _status_label(review_status),
        "release_status": health_status,
        "next_step": next_step,
        "artifact_count": artifact_count,
        "missing_expected": [str(item) for item in missing_expected],
        "missing_key_artifacts": [str(item) for item in missing_key_artifacts],
        "blocking_reasons": blocking_reasons,
        "recommended_actions": recommended_actions[:5],
        "copyable_summary": handoff.get("copyable_summary") or "",
        "release_health_preview": _read_preview(artifact_dir / "release-health.md"),
        "triage_preview": _read_preview(artifact_dir / "triage-summary.md"),
        "safe_scope": (
            "Local setup, deterministic tests, synthetic examples, API contracts, generated artifacts, "
            "documentation, and defensive analytical software behavior."
        ),
    }
    if not digest["copyable_summary"]:
        digest["copyable_summary"] = (
            f"Operator digest for `{digest['artifact_dir']}`: {digest['status_label']} "
            f"with {artifact_count} indexed artifact(s). Next step: `{next_step}`."
        )
    return digest


def _markdown_lines(digest: Mapping[str, Any]) -> Iterable[str]:
    yield "# Operator Digest"
    yield ""
    yield "Use this as the quick first-read summary before opening the full diagnostics bundle."
    yield ""
    yield f"Generated at: `{digest['generated_at']}`"
    yield f"Artifact directory: `{digest['artifact_dir']}`"
    yield f"Status: **{digest['status_label']}** (`{digest['status']}`)"
    yield f"Release health: **{str(digest['release_status']).upper()}**"
    yield f"Indexed artifacts: **{digest['artifact_count']}**"
    yield ""
    yield "## Recommended next step"
    yield ""
    yield f"`{digest['next_step']}`"
    yield ""
    yield "## Copyable summary"
    yield ""
    yield "```text"
    yield str(digest["copyable_summary"])
    yield "```"
    yield ""

    blocking = list(digest.get("blocking_reasons", []))
    if blocking:
        yield "## Attention needed"
        yield ""
        for reason in blocking:
            yield f"- {reason}"
        yield ""

    actions = list(digest.get("recommended_actions", []))
    if actions:
        yield "## Top rerun actions"
        yield ""
        yield "| Reason | Target | Detail |"
        yield "| --- | --- | --- |"
        for action in actions:
            if not isinstance(action, Mapping):
                continue
            reason = str(action.get("reason", "Review diagnostics")).replace("|", "\\|")
            target = str(action.get("target", "make verify")).replace("|", "\\|")
            detail = str(action.get("detail", "—") or "—").replace("|", "\\|")
            yield f"| {reason} | `{target}` | {detail} |"
        yield ""

    missing_expected = list(digest.get("missing_expected", []))
    missing_key = list(digest.get("missing_key_artifacts", []))
    if missing_expected or missing_key:
        yield "## Missing outputs"
        yield ""
        for item in missing_expected:
            yield f"- Expected artifact: `{item}`"
        for item in missing_key:
            yield f"- Key review artifact: `{item}`"
        yield ""

    yield "## Open first"
    yield ""
    yield "1. `release-bundle-index.html` for the full artifact landing page."
    yield "2. `operator-digest.md` for this quick summary."
    yield "3. `reviewer-handoff.md` when sending the bundle to another reviewer."
    yield "4. `triage-summary.md` when the digest reports failures or missing outputs."
    yield ""
    yield "## Safe scope"
    yield ""
    yield str(digest["safe_scope"])


def render_markdown(digest: Mapping[str, Any]) -> str:
    """Render a digest as Markdown."""

    return "\n".join(_markdown_lines(digest)).rstrip() + "\n"


def write_outputs(digest: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested digest outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(digest), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(digest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a concise operator digest from diagnostics artifacts.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"artifact directory; default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=None,
        help="Markdown output path; default: <artifact-dir>/operator-digest.md",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=None,
        help="JSON output path; default: <artifact-dir>/operator-digest.json",
    )
    parser.add_argument("--no-markdown", action="store_true", help="skip Markdown output")
    parser.add_argument("--no-json", action="store_true", help="skip JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    digest = build_operator_digest(args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    write_outputs(digest, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote operator digest Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote operator digest JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write digest files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
