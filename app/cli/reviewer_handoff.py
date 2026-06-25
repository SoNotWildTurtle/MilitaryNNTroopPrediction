"""Generate reviewer handoff notes from diagnostic bundle artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from app.cli.artifact_manifest import DEFAULT_ARTIFACT_DIR

DEFAULT_MARKDOWN_NAME = "reviewer-handoff.md"
DEFAULT_JSON_NAME = "reviewer-handoff.json"

KEY_ARTIFACTS: Mapping[str, str] = {
    "release-bundle-index.html": "Open this first for a reviewer-friendly artifact landing page.",
    "release-health.md": "Readiness summary for setup, API, docs, and generated outputs.",
    "triage-summary.md": "Failure triage notes and narrow local rerun commands.",
    "release-notes.md": "Manager-friendly summary of the generated diagnostics bundle.",
    "artifact-manifest.md": "File inventory with SHA-256 hashes and missing expected outputs.",
    "openapi-summary.md": "Human-readable API contract summary.",
    "api-response-examples.md": "Synthetic API examples for UI/client review without live services.",
    "dashboard-mockup.html": "Static dashboard preview generated from safe synthetic examples.",
}


def _load_json(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _read_text(path: Path, max_chars: int = 900) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return None
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _manifest_files(manifest: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return {}
    return {str(entry.get("path")): entry for entry in files if isinstance(entry, Mapping)}


def _release_status(health: Mapping[str, Any] | None) -> str:
    if not health:
        return "unknown"
    return str(health.get("status", "unknown"))


def _recommended_rerun(triage: Mapping[str, Any] | None) -> str:
    if not triage:
        return "make verify"
    value = triage.get("recommended_rerun") or triage.get("recommended_command")
    if value:
        return str(value)
    rerun_targets = triage.get("rerun_targets")
    if isinstance(rerun_targets, list) and rerun_targets:
        first = rerun_targets[0]
        if isinstance(first, Mapping):
            return str(first.get("command", "make verify"))
        return str(first)
    return "make verify"


def build_handoff(artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> Dict[str, Any]:
    """Build a deterministic reviewer handoff summary for a diagnostics bundle."""

    manifest = _load_json(artifact_dir / "artifact-manifest.json") or {}
    health = _load_json(artifact_dir / "release-health.json")
    triage = _load_json(artifact_dir / "triage-summary.json")
    files_by_path = _manifest_files(manifest)
    missing_expected = manifest.get("missing_expected", []) if isinstance(manifest, Mapping) else []
    if not isinstance(missing_expected, list):
        missing_expected = []

    key_artifacts: List[Dict[str, Any]] = []
    for path, purpose in KEY_ARTIFACTS.items():
        entry = files_by_path.get(path)
        key_artifacts.append(
            {
                "path": path,
                "purpose": purpose,
                "present": entry is not None or (artifact_dir / path).exists(),
                "size_bytes": int(entry.get("size_bytes", 0)) if entry else None,
                "sha256": str(entry.get("sha256")) if entry and entry.get("sha256") else None,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "release_status": _release_status(health),
        "recommended_rerun": _recommended_rerun(triage),
        "missing_expected": [str(name) for name in missing_expected],
        "key_artifacts": key_artifacts,
        "release_health_preview": _read_text(artifact_dir / "release-health.md"),
        "triage_preview": _read_text(artifact_dir / "triage-summary.md"),
    }


def _markdown_lines(handoff: Mapping[str, Any]) -> Iterable[str]:
    yield "# Reviewer handoff"
    yield ""
    yield "Use this file as the first copy/paste handoff when asking another maintainer, analyst, or reviewer to inspect a diagnostics bundle."
    yield ""
    yield f"Generated at: `{handoff['generated_at']}`"
    yield f"Artifact directory: `{handoff['artifact_dir']}`"
    yield f"Release status: **{str(handoff['release_status']).upper()}**"
    yield f"Recommended local rerun: `{handoff['recommended_rerun']}`"
    yield ""
    yield "## Review order"
    yield ""
    yield "1. Open `release-bundle-index.html`."
    yield "2. Check `release-health.md` for readiness status."
    yield "3. Check `triage-summary.md` if anything is missing or failing."
    yield "4. Use `artifact-manifest.md` to confirm file hashes and expected outputs."
    yield "5. Review `openapi-summary.md`, `api-response-examples.md`, and `dashboard-mockup.html` for user-facing behavior."
    yield ""
    missing_expected = handoff.get("missing_expected", [])
    if missing_expected:
        yield "## Missing expected outputs"
        yield ""
        for name in missing_expected:
            yield f"- `{name}`"
        yield ""
    yield "## Key artifacts"
    yield ""
    yield "| Path | Present | Purpose | SHA-256 |"
    yield "| --- | --- | --- | --- |"
    for artifact in handoff.get("key_artifacts", []):
        status = "yes" if artifact.get("present") else "no"
        sha = artifact.get("sha256") or "-"
        yield f"| `{artifact['path']}` | {status} | {artifact['purpose']} | `{sha}` |"
    yield ""
    yield "## Safe review scope"
    yield ""
    yield "Keep review limited to deterministic local setup, generated documentation, API contracts, synthetic examples, static previews, validation scripts, and defensive analytical software behavior."
    yield ""
    release_preview = handoff.get("release_health_preview")
    if release_preview:
        yield "## Release health preview"
        yield ""
        yield "```text"
        yield str(release_preview)
        yield "```"
        yield ""
    triage_preview = handoff.get("triage_preview")
    if triage_preview:
        yield "## Triage preview"
        yield ""
        yield "```text"
        yield str(triage_preview)
        yield "```"


def render_markdown(handoff: Mapping[str, Any]) -> str:
    """Render handoff data as Markdown."""

    return "\n".join(_markdown_lines(handoff)).rstrip() + "\n"


def write_json(handoff: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(markdown_text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Markdown and JSON reviewer handoff notes from a diagnostics bundle."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory containing generated artifacts. Default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=None,
        help="Path for Markdown output. Default: <artifact-dir>/reviewer-handoff.md",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=None,
        help="Path for JSON output. Default: <artifact-dir>/reviewer-handoff.json",
    )
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    handoff = build_handoff(args.artifact_dir)
    markdown_path = args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = args.json_path or args.artifact_dir / DEFAULT_JSON_NAME

    if not args.no_markdown:
        write_markdown(render_markdown(handoff), markdown_path)
        print(f"Wrote reviewer handoff Markdown to {markdown_path}")
    if not args.no_json:
        write_json(handoff, json_path)
        print(f"Wrote reviewer handoff JSON to {json_path}")
    if args.no_markdown and args.no_json:
        print("No outputs requested; remove --no-markdown or --no-json to write handoff files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
