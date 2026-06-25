"""Generate a machine-readable manifest for diagnostic artifact bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_JSON_NAME = "artifact-manifest.json"
DEFAULT_MARKDOWN_NAME = "artifact-manifest.md"

EXPECTED_ARTIFACTS: Dict[str, str] = {
    "python-version.txt": "Python interpreter version used by diagnostics.",
    "pip-version.txt": "pip version used by diagnostics.",
    "pip-freeze.txt": "Installed package versions for reproducibility.",
    "doctor-minimal.json": "Machine-readable core setup diagnostics.",
    "release-health.md": "Human-readable release readiness summary.",
    "release-health.json": "Machine-readable release readiness summary.",
    "release-notes.md": "Manager-friendly release notes generated from diagnostics.",
    "release-notes.json": "Machine-readable release notes generated from diagnostics.",
    "reviewer-handoff.md": "Copyable reviewer handoff generated from diagnostics and manifests.",
    "reviewer-handoff.json": "Machine-readable reviewer handoff generated from diagnostics and manifests.",
    "triage-summary.md": "Human-readable CI failure triage summary with narrow rerun targets.",
    "triage-summary.json": "Machine-readable CI failure triage summary with narrow rerun targets.",
    "operator-artifact-guide.md": "Operator-friendly menu explaining which diagnostic artifacts to open first.",
    "operator-artifact-guide.json": "Machine-readable operator artifact guide for dashboards and automation.",
    "openapi.json": "Machine-readable FastAPI OpenAPI contract.",
    "openapi-summary.md": "Human-readable API contract summary.",
    "api-response-examples.json": "Synthetic JSON responses for dashboards and client builders.",
    "api-response-examples.md": "Human-readable synthetic API response examples.",
    "dashboard-mockup.html": "Self-contained static dashboard preview.",
    "release-bundle-index.html": "Self-contained reviewer landing page for the diagnostic bundle.",
    "html-previews.md": "Human-readable index of generated SVG previews for static HTML artifacts.",
    "previews/dashboard-mockup.svg": "Browser-free visual preview of the dashboard mockup artifact.",
    "previews/release-bundle-index.svg": "Browser-free visual preview of the release bundle index artifact.",
    "quickstart-help.txt": "Current quickstart CLI options.",
    "doctor-help.txt": "Current doctor CLI options.",
    "release-health-help.txt": "Current release health CLI options.",
    "release-notes-help.txt": "Current release notes CLI options.",
    "reviewer-handoff-help.txt": "Current reviewer handoff CLI options.",
    "triage-summary-help.txt": "Current CI triage summary CLI options.",
    "operator-artifact-guide-help.txt": "Current operator artifact guide CLI options.",
    "export-openapi-help.txt": "Current OpenAPI export CLI options.",
    "export-api-examples-help.txt": "Current API example export CLI options.",
    "export-dashboard-mockup-help.txt": "Current dashboard mockup export CLI options.",
    "release-bundle-index-help.txt": "Current release bundle index CLI options.",
    "artifact-manifest-help.txt": "Current artifact manifest CLI options.",
    "export-html-previews-help.txt": "Current HTML preview export CLI options.",
    "summary.txt": "Plain-language bundle index for humans.",
}

GENERATED_MANIFEST_NAMES = {DEFAULT_JSON_NAME, DEFAULT_MARKDOWN_NAME}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_entry(path: Path, artifact_dir: Path) -> Dict[str, Any]:
    stat = path.stat()
    relative_path = path.relative_to(artifact_dir).as_posix()
    return {
        "path": relative_path,
        "size_bytes": stat.st_size,
        "sha256": _sha256(path),
        "description": EXPECTED_ARTIFACTS.get(relative_path, "Generated diagnostic artifact."),
    }


def build_manifest(artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> Dict[str, Any]:
    """Build a deterministic manifest for files in ``artifact_dir``."""

    files: List[Dict[str, Any]] = []
    if artifact_dir.exists():
        for path in sorted(p for p in artifact_dir.rglob("*") if p.is_file()):
            if path.name in GENERATED_MANIFEST_NAMES:
                continue
            files.append(_file_entry(path, artifact_dir))

    present_paths = {entry["path"] for entry in files}
    missing_expected = sorted(name for name in EXPECTED_ARTIFACTS if name not in present_paths)

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "file_count": len(files),
        "total_size_bytes": sum(int(entry["size_bytes"]) for entry in files),
        "missing_expected": missing_expected,
        "files": files,
    }


def write_json(manifest: Dict[str, Any], path: Path) -> None:
    """Write manifest JSON to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown_lines(manifest: Dict[str, Any]) -> Iterable[str]:
    yield "# Diagnostic artifact manifest"
    yield ""
    yield f"Generated at: `{manifest['generated_at']}`"
    yield f"Artifact directory: `{manifest['artifact_dir']}`"
    yield f"Files indexed: {manifest['file_count']}"
    yield f"Total size: {manifest['total_size_bytes']} bytes"
    yield ""

    if manifest["missing_expected"]:
        yield "## Missing expected files"
        yield ""
        for name in manifest["missing_expected"]:
            yield f"- `{name}` - {EXPECTED_ARTIFACTS[name]}"
        yield ""

    yield "## Files"
    yield ""
    yield "| Path | Size | SHA-256 | Description |"
    yield "| --- | ---: | --- | --- |"
    for entry in manifest["files"]:
        description = str(entry["description"]).replace("|", "\\|")
        yield f"| `{entry['path']}` | {entry['size_bytes']} | `{entry['sha256']}` | {description} |"


def render_markdown(manifest: Dict[str, Any]) -> str:
    """Render a human-readable manifest."""

    return "\n".join(_markdown_lines(manifest)).rstrip() + "\n"


def write_markdown(manifest: Dict[str, Any], path: Path) -> None:
    """Write manifest Markdown to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(manifest), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a diagnostic artifact manifest.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"artifact directory to index; default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument("--json-path", type=Path, default=None, help="manifest JSON output path")
    parser.add_argument("--markdown-path", type=Path, default=None, help="manifest Markdown output path")
    parser.add_argument("--no-markdown", action="store_true", help="only write JSON output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    artifact_dir = args.artifact_dir
    json_path = args.json_path or artifact_dir / DEFAULT_JSON_NAME
    markdown_path = None if args.no_markdown else (args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME)

    manifest = build_manifest(artifact_dir)
    write_json(manifest, json_path)
    print(f"Wrote artifact manifest JSON to {json_path}")
    if markdown_path is not None:
        write_markdown(manifest, markdown_path)
        print(f"Wrote artifact manifest Markdown to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
