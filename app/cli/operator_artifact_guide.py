"""Generate an operator-friendly guide for CI diagnostic artifacts.

This command turns the local diagnostics bundle into a concise menu that tells
operators which generated files to open first, what each artifact is useful for,
and what the safest next action should be. It only reads local artifact metadata
and writes Markdown/JSON guidance; it never performs ingestion, prediction,
network collection, deployment, or live OSINT activity.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "operator-artifact-guide.md"
DEFAULT_JSON_NAME = "operator-artifact-guide.json"
DEFAULT_HEALTH_NAME = "release-health.json"
DEFAULT_MANIFEST_NAME = "artifact-manifest.json"

ARTIFACT_PURPOSES: Dict[str, Dict[str, str]] = {
    "release-bundle-index.html": {
        "audience": "everyone",
        "purpose": "Start here for a linked, self-contained review landing page.",
        "action": "Open this first before inspecting individual generated files.",
    },
    "release-health.md": {
        "audience": "maintainers",
        "purpose": "Human-readable readiness summary for local setup and release checks.",
        "action": "Review failures and warnings before sharing the bundle.",
    },
    "reviewer-handoff.md": {
        "audience": "reviewers",
        "purpose": "Copyable summary for a PR reviewer or non-technical stakeholder.",
        "action": "Attach or paste this when handing off a diagnostics bundle.",
    },
    "triage-summary.md": {
        "audience": "maintainers",
        "purpose": "Narrow rerun targets for failed or incomplete CI diagnostics.",
        "action": "Use this when a hosted CI run fails or generated artifacts are missing.",
    },
    "release-notes.md": {
        "audience": "managers",
        "purpose": "Manager-friendly release summary generated from diagnostics.",
        "action": "Use this for status updates after readiness checks pass.",
    },
    "dashboard-mockup.html": {
        "audience": "operators",
        "purpose": "Static UI preview built from safe synthetic API examples.",
        "action": "Open this to review the analytical dashboard shape without running the API.",
    },
    "openapi-summary.md": {
        "audience": "integrators",
        "purpose": "Human-readable API contract summary.",
        "action": "Use this when wiring clients, dashboards, or future automation.",
    },
    "api-response-examples.md": {
        "audience": "integrators",
        "purpose": "Safe synthetic responses for UI prototypes and client tests.",
        "action": "Use these examples instead of live data during first-run development.",
    },
    "artifact-manifest.md": {
        "audience": "maintainers",
        "purpose": "File-size and SHA-256 index for generated diagnostics.",
        "action": "Use this to confirm the bundle contents are complete and reproducible.",
    },
    "html-previews.md": {
        "audience": "reviewers",
        "purpose": "Browser-free SVG preview index for generated HTML artifacts.",
        "action": "Use this when reviewing artifacts in CI without opening HTML files.",
    },
}

AUDIENCE_ORDER = {"everyone": 0, "operators": 1, "maintainers": 2, "reviewers": 3, "integrators": 4, "managers": 5}


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def _health_counts(health_results: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {"ok": 0, "warn": 0, "fail": 0}
    for result in health_results:
        status = str(result.get("status", "")).lower()
        if status in counts:
            counts[status] += 1
    return counts


def _first_present(manifest_files: Mapping[str, Mapping[str, Any]], candidates: Sequence[str]) -> str | None:
    for path in candidates:
        if path in manifest_files:
            return path
    return None


def _recommended_first_step(
    health_results: Sequence[Mapping[str, Any]], manifest_files: Mapping[str, Mapping[str, Any]], missing: Sequence[str]
) -> str:
    if any(str(item.get("status", "")).lower() == "fail" for item in health_results):
        return "Open triage-summary.md, fix the first failing check, then rerun make verify."
    if missing:
        return "Open artifact-manifest.md, regenerate the missing outputs, then rerun make ci-report."
    first = _first_present(manifest_files, ["release-bundle-index.html", "reviewer-handoff.md", "release-health.md"])
    if first:
        return f"Open {first} first, then follow the audience-specific artifact menu."
    return "Run make ci-report to generate the diagnostics bundle, then rerun this guide."


def build_operator_artifact_guide(
    health_results: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Build a deterministic, operator-friendly artifact guide."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    files = [dict(item) for item in manifest.get("files", [])]
    manifest_files = {str(item.get("path", "")): item for item in files}
    missing = [str(item) for item in manifest.get("missing_expected", [])]

    menu: List[Dict[str, Any]] = []
    for path, metadata in ARTIFACT_PURPOSES.items():
        item = manifest_files.get(path)
        menu.append(
            {
                "path": path,
                "present": item is not None,
                "audience": metadata["audience"],
                "purpose": metadata["purpose"],
                "action": metadata["action"],
                "size_bytes": int(item.get("size_bytes", 0)) if item else 0,
                "sha256": str(item.get("sha256", "")) if item else "",
            }
        )

    menu.sort(key=lambda item: (not bool(item["present"]), AUDIENCE_ORDER.get(str(item["audience"]), 99), str(item["path"])))
    counts = _health_counts(health_results)

    return {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": str(manifest.get("artifact_dir", DEFAULT_ARTIFACT_DIR.as_posix())),
        "health_summary": counts,
        "artifact_count": int(manifest.get("file_count", 0) or 0),
        "missing_expected": missing,
        "recommended_first_step": _recommended_first_step(health_results, manifest_files, missing),
        "artifact_menu": menu,
        "safe_scope": "Local diagnostics, generated artifacts, synthetic examples, API contracts, and documentation only.",
    }


def _markdown_lines(guide: Mapping[str, Any]) -> Iterable[str]:
    yield "# Operator Artifact Guide"
    yield ""
    yield f"Generated: `{guide['generated_at']}`"
    yield f"Artifact directory: `{guide['artifact_dir']}`"
    yield ""
    yield "## Recommended first step"
    yield ""
    yield str(guide["recommended_first_step"])
    yield ""
    yield "## Health summary"
    yield ""
    health = guide["health_summary"]
    yield f"- OK: {health['ok']}"
    yield f"- Warnings: {health['warn']}"
    yield f"- Failures: {health['fail']}"
    yield f"- Indexed artifacts: {guide['artifact_count']}"
    yield ""
    yield "## Artifact menu"
    yield ""
    yield "| Artifact | Present | Audience | Purpose | Operator action |"
    yield "| --- | --- | --- | --- | --- |"
    for item in guide["artifact_menu"]:
        present = "yes" if item["present"] else "missing"
        path = str(item["path"]).replace("|", "\\|")
        audience = str(item["audience"]).replace("|", "\\|")
        purpose = str(item["purpose"]).replace("|", "\\|")
        action = str(item["action"]).replace("|", "\\|")
        yield f"| `{path}` | {present} | {audience} | {purpose} | {action} |"
    yield ""
    if guide["missing_expected"]:
        yield "## Missing expected artifacts"
        yield ""
        for path in guide["missing_expected"]:
            yield f"- `{path}`"
        yield ""
    yield "## Safe scope"
    yield ""
    yield str(guide["safe_scope"])


def render_markdown(guide: Mapping[str, Any]) -> str:
    """Render the guide as Markdown."""

    return "\n".join(_markdown_lines(guide)).rstrip() + "\n"


def write_outputs(guide: Mapping[str, Any], markdown_path: Path, json_path: Path | None) -> None:
    """Write Markdown and optional JSON outputs."""

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(guide), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(guide, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an operator-friendly guide for diagnostic artifacts.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"diagnostic artifact directory; default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument("--health-json", type=Path, default=None, help="release health JSON path")
    parser.add_argument("--manifest-json", type=Path, default=None, help="artifact manifest JSON path")
    parser.add_argument("--markdown-path", type=Path, default=None, help="artifact guide Markdown output path")
    parser.add_argument("--json-path", type=Path, default=None, help="artifact guide JSON output path")
    parser.add_argument("--no-json", action="store_true", help="only write Markdown output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    health_path = args.health_json or artifact_dir / DEFAULT_HEALTH_NAME
    manifest_path = args.manifest_json or artifact_dir / DEFAULT_MANIFEST_NAME
    markdown_path = args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)

    health_results = _load_json(health_path, [])
    manifest = _load_json(manifest_path, {"artifact_dir": artifact_dir.as_posix(), "file_count": 0, "missing_expected": [], "files": []})
    guide = build_operator_artifact_guide(health_results, manifest)
    write_outputs(guide, markdown_path, json_path)

    print(f"Wrote operator artifact guide Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote operator artifact guide JSON to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
