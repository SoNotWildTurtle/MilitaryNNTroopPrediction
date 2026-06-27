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

_EXPECTED_ARTIFACT_ROWS = [
    ("python-version.txt", "Python interpreter version used by diagnostics."),
    ("pip-version.txt", "pip version used by diagnostics."),
    ("pip-freeze.txt", "Installed package versions for reproducibility."),
    ("doctor-minimal.json", "Machine-readable core setup diagnostics."),
    ("release-health.md", "Human-readable release readiness summary."),
    ("release-health.json", "Machine-readable release readiness summary."),
    ("release-notes.md", "Manager-friendly release notes generated from diagnostics."),
    ("release-notes.json", "Machine-readable release notes generated from diagnostics."),
    ("reviewer-handoff.md", "Copyable reviewer handoff generated from diagnostics and manifests."),
    ("reviewer-handoff.json", "Machine-readable reviewer handoff generated from diagnostics and manifests."),
    ("operator-digest.md", "Concise first-read operator digest generated from health, manifest, triage, and handoff artifacts."),
    ("operator-digest.json", "Machine-readable first-read operator digest."),
    ("operator-readiness.md", "Launch/no-launch readiness brief generated from diagnostics."),
    ("operator-readiness.json", "Machine-readable operator readiness brief generated from diagnostics."),
    ("operator-status-board.md", "Quick non-technical operator readiness board generated from diagnostics."),
    ("operator-status-board.json", "Machine-readable operator status board generated from diagnostics."),
    ("operator-session-plan.md", "Ranked next-session operator checklist generated from diagnostics."),
    ("operator-session-plan.json", "Machine-readable ranked next-session operator checklist."),
    ("operator-runbook-index.md", "Operator command, documentation, artifact, and safe-scope map."),
    ("operator-runbook-index.json", "Machine-readable operator runbook index."),
    ("operator-next-steps.md", "Ranked next-safe-command action plan generated from diagnostics."),
    ("operator-next-steps.json", "Machine-readable ranked operator next-steps action plan."),
    ("automation-plan.md", "Safe additive next-run plan generated from goals and diagnostics."),
    ("automation-plan.json", "Machine-readable safe additive next-run plan."),
    ("triage-summary.md", "Human-readable CI failure triage summary with narrow rerun targets."),
    ("triage-summary.json", "Machine-readable CI failure triage summary with narrow rerun targets."),
    ("artifact-gap-report.md", "Human-readable diagnostic bundle completeness and suspicious-artifact report."),
    ("artifact-gap-report.json", "Machine-readable diagnostic bundle completeness and suspicious-artifact report."),
    ("artifact-provenance-ledger.md", "Human-readable provenance ledger for generated, synthetic, preview, and review artifacts."),
    ("artifact-provenance-ledger.json", "Machine-readable provenance ledger for generated, synthetic, preview, and review artifacts."),
    ("openapi.json", "Machine-readable FastAPI OpenAPI contract."),
    ("openapi-summary.md", "Human-readable API contract summary."),
    ("api-response-examples.json", "Synthetic JSON responses for dashboards and client builders."),
    ("api-response-examples.md", "Human-readable synthetic API response examples."),
    ("dashboard-mockup.html", "Self-contained static dashboard preview."),
    ("synthetic-fixtures/synthetic-fixtures-summary.json", "Machine-readable summary of generated safe data fixtures."),
    ("synthetic-fixtures/synthetic-detections.jsonl", "JSON Lines detection fixture records for local demos and client tests."),
    ("synthetic-fixtures/synthetic-predictions.jsonl", "JSON Lines prediction fixture records for local demos and client tests."),
    ("synthetic-fixtures/synthetic-detections.csv", "Spreadsheet-friendly synthetic detection fixture records."),
    ("synthetic-fixtures/synthetic-fixtures.md", "Human-readable synthetic fixture summary."),
    ("release-bundle-index.html", "Self-contained reviewer landing page for the diagnostic bundle."),
    ("html-previews.md", "Human-readable index of generated SVG previews for static HTML artifacts."),
    ("previews/dashboard-mockup.svg", "Browser-free visual preview of the dashboard mockup artifact."),
    ("previews/release-bundle-index.svg", "Browser-free visual preview of the release bundle index artifact."),
    ("quickstart-help.txt", "Current quickstart CLI options."),
    ("doctor-help.txt", "Current doctor CLI options."),
    ("release-health-help.txt", "Current release health CLI options."),
    ("release-notes-help.txt", "Current release notes CLI options."),
    ("reviewer-handoff-help.txt", "Current reviewer handoff CLI options."),
    ("operator-digest-help.txt", "Current operator digest CLI options."),
    ("operator-readiness-help.txt", "Current operator readiness CLI options."),
    ("operator-status-board-help.txt", "Current operator status board CLI options."),
    ("operator-session-plan-help.txt", "Current operator session plan CLI options."),
    ("operator-runbook-index-help.txt", "Current operator runbook index CLI options."),
    ("operator-next-steps-help.txt", "Current operator next steps CLI options."),
    ("automation-plan-help.txt", "Current automation plan CLI options."),
    ("triage-summary-help.txt", "Current CI triage summary CLI options."),
    ("artifact-gap-report-help.txt", "Current artifact gap report CLI options."),
    ("artifact-provenance-ledger-help.txt", "Current artifact provenance ledger CLI options."),
    ("synthetic-data-fixtures-help.txt", "Current synthetic fixture exporter CLI options."),
    ("export-openapi-help.txt", "Current OpenAPI export CLI options."),
    ("export-api-examples-help.txt", "Current API example export CLI options."),
    ("export-dashboard-mockup-help.txt", "Current dashboard mockup export CLI options."),
    ("release-bundle-index-help.txt", "Current release bundle index CLI options."),
    ("artifact-manifest-help.txt", "Current artifact manifest CLI options."),
    ("export-html-previews-help.txt", "Current HTML preview export CLI options."),
    ("summary.txt", "Plain-language bundle index for humans."),
]
EXPECTED_ARTIFACTS: Dict[str, str] = dict(_EXPECTED_ARTIFACT_ROWS)
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
    scan_warnings: List[Dict[str, str]] = []
    if artifact_dir.exists():
        for path in sorted(p for p in artifact_dir.rglob("*") if p.is_file()):
            if path.name in GENERATED_MANIFEST_NAMES:
                continue
            try:
                files.append(_file_entry(path, artifact_dir))
            except (OSError, ValueError) as exc:
                scan_warnings.append({"path": path.as_posix(), "error": exc.__class__.__name__})

    present_paths = {entry["path"] for entry in files}
    missing_expected = sorted(name for name in EXPECTED_ARTIFACTS if name not in present_paths)
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "file_count": len(files),
        "total_size_bytes": sum(int(entry["size_bytes"]) for entry in files),
        "missing_expected": missing_expected,
        "scan_warnings": scan_warnings,
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
    scan_warnings = manifest.get("scan_warnings", [])
    if scan_warnings:
        yield "## Scan warnings"
        yield ""
        yield "Some files could not be read while the manifest was being generated."
        yield ""
        yield "| Path | Error |"
        yield "| --- | --- |"
        for warning in scan_warnings:
            yield f"| `{warning['path']}` | {warning['error']} |"
        yield ""
    yield "## Files"
    yield ""
    yield "| Path | Size | SHA-256 | Description |"
    yield "| --- | ---: | --- | --- |"
    for entry in manifest["files"]:
        yield (
            f"| `{entry['path']}` | {entry['size_bytes']} | "
            f"`{entry['sha256']}` | {entry['description']} |"
        )


def write_markdown(manifest: Dict[str, Any], path: Path) -> None:
    """Write a human-readable manifest summary to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_markdown_lines(manifest)).rstrip() + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(description="Generate JSON and Markdown manifests for diagnostic artifact bundles.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR, help=f"Directory containing generated artifacts. Default: {DEFAULT_ARTIFACT_DIR}")
    parser.add_argument("--json-path", type=Path, default=None, help="Path for JSON output. Default: <artifact-dir>/artifact-manifest.json")
    parser.add_argument("--markdown-path", type=Path, default=None, help="Path for Markdown output. Default: <artifact-dir>/artifact-manifest.md")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    return parser


def main() -> int:
    """CLI entry point."""

    args = build_parser().parse_args()
    manifest = build_manifest(args.artifact_dir)
    json_path = args.json_path or args.artifact_dir / DEFAULT_JSON_NAME
    markdown_path = args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME
    if not args.no_json:
        write_json(manifest, json_path)
        print(f"Wrote artifact manifest JSON to {json_path}")
    if not args.no_markdown:
        write_markdown(manifest, markdown_path)
        print(f"Wrote artifact manifest Markdown to {markdown_path}")
    if args.no_json and args.no_markdown:
        print("No outputs requested; remove --no-json or --no-markdown to write manifest files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
