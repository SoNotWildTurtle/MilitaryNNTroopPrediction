"""Audit generated diagnostic bundles for missing, empty, or suspicious artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from app.cli.artifact_manifest import DEFAULT_ARTIFACT_DIR, EXPECTED_ARTIFACTS

DEFAULT_JSON_NAME = "artifact-gap-report.json"
DEFAULT_MARKDOWN_NAME = "artifact-gap-report.md"

# Minimum sizes intentionally stay conservative so placeholder or truncated outputs
# are surfaced without making local smoke tests brittle across Python versions.
MIN_SIZE_BYTES: Dict[str, int] = {
    "python-version.txt": 5,
    "pip-version.txt": 5,
    "doctor-minimal.json": 20,
    "release-health.md": 20,
    "release-health.json": 20,
    "openapi.json": 100,
    "openapi-summary.md": 20,
    "api-response-examples.json": 20,
    "api-response-examples.md": 20,
    "dashboard-mockup.html": 100,
    "release-bundle-index.html": 100,
    "artifact-manifest.json": 20,
    "artifact-manifest.md": 20,
    "artifact-gap-report.json": 20,
    "artifact-gap-report.md": 20,
    "reviewer-handoff.md": 20,
    "reviewer-handoff.json": 20,
    "reviewer-handoff-validation.json": 20,
    "triage-summary.md": 20,
    "triage-summary.json": 20,
    "release-notes.md": 20,
    "release-notes.json": 20,
    "operator-readiness.md": 20,
    "operator-readiness.json": 20,
    "automation-plan.md": 20,
    "automation-plan.json": 20,
    "implementation-acceptance-checklist.md": 20,
    "implementation-acceptance-checklist.json": 20,
    "implementation-acceptance-handoff.md": 20,
    "implementation-acceptance-handoff.json": 20,
}


def _load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "missing_manifest": True,
            "artifact_dir": path.parent.as_posix(),
            "files": [],
            "missing_expected": sorted(EXPECTED_ARTIFACTS),
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _entries_by_path(manifest: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    entries: Dict[str, Mapping[str, Any]] = {}
    for entry in manifest.get("files", []):
        if isinstance(entry, Mapping) and isinstance(entry.get("path"), str):
            entries[str(entry["path"])] = entry
    return entries


def build_gap_report(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    manifest_path: Path | None = None,
) -> Dict[str, Any]:
    """Build an operator-friendly report from an artifact manifest."""

    manifest_file = manifest_path or artifact_dir / "artifact-manifest.json"
    manifest = _load_manifest(manifest_file)
    entries = _entries_by_path(manifest)

    expected_paths = sorted(set(EXPECTED_ARTIFACTS) | set(MIN_SIZE_BYTES))
    missing_expected = sorted(
        set(str(path) for path in manifest.get("missing_expected", []))
        | {path for path in expected_paths if path not in entries}
    )

    empty_files: List[str] = []
    undersized_files: List[Dict[str, Any]] = []
    for path, entry in sorted(entries.items()):
        size = int(entry.get("size_bytes", 0))
        if size == 0:
            empty_files.append(path)
        minimum = MIN_SIZE_BYTES.get(path)
        if minimum is not None and 0 < size < minimum:
            undersized_files.append(
                {"path": path, "size_bytes": size, "minimum_size_bytes": minimum}
            )

    severity = "pass"
    if manifest.get("missing_manifest") or missing_expected or empty_files:
        severity = "fail"
    elif undersized_files:
        severity = "warn"

    recommended_next_step = {
        "pass": "Bundle looks complete enough for reviewer handoff.",
        "warn": "Review undersized artifacts, then rerun the narrow generator if any output is truncated.",
        "fail": "Regenerate the diagnostics bundle with make ci-report, then rerun make artifact-gap-report.",
    }[severity]

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "manifest_path": manifest_file.as_posix(),
        "severity": severity,
        "expected_count": len(expected_paths),
        "indexed_count": len(entries),
        "missing_expected": missing_expected,
        "empty_files": empty_files,
        "undersized_files": undersized_files,
        "recommended_next_step": recommended_next_step,
    }


def write_json(report: Mapping[str, Any], path: Path) -> None:
    """Write the machine-readable gap report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown_lines(report: Mapping[str, Any]) -> Iterable[str]:
    yield "# Diagnostic artifact gap report"
    yield ""
    yield f"Generated at: `{report['generated_at']}`"
    yield f"Artifact directory: `{report['artifact_dir']}`"
    yield f"Manifest path: `{report['manifest_path']}`"
    yield f"Severity: **{str(report['severity']).upper()}**"
    yield f"Expected artifacts checked: {report['expected_count']}"
    yield f"Indexed artifacts: {report['indexed_count']}"
    yield ""
    yield f"Recommended next step: {report['recommended_next_step']}"
    yield ""

    if report["missing_expected"]:
        yield "## Missing expected artifacts"
        yield ""
        for path in report["missing_expected"]:
            description = EXPECTED_ARTIFACTS.get(path, "Expected diagnostic artifact.")
            yield f"- `{path}` - {description}"
        yield ""

    if report["empty_files"]:
        yield "## Empty artifacts"
        yield ""
        for path in report["empty_files"]:
            yield f"- `{path}`"
        yield ""

    if report["undersized_files"]:
        yield "## Suspiciously small artifacts"
        yield ""
        yield "| Path | Size | Minimum expected size |"
        yield "| --- | ---: | ---: |"
        for entry in report["undersized_files"]:
            yield (
                f"| `{entry['path']}` | {entry['size_bytes']} | "
                f"{entry['minimum_size_bytes']} |"
            )
        yield ""

    if (
        not report["missing_expected"]
        and not report["empty_files"]
        and not report["undersized_files"]
    ):
        yield "No missing, empty, or suspiciously small expected artifacts were found."


def write_markdown(report: Mapping[str, Any], path: Path) -> None:
    """Write the human-readable gap report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_markdown_lines(report)).rstrip() + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Audit diagnostic bundles for missing, empty, or suspiciously small artifacts."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory containing generated artifacts. Default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Path to artifact-manifest.json. Default: <artifact-dir>/artifact-manifest.json",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=None,
        help="Path for JSON output. Default: <artifact-dir>/artifact-gap-report.json",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=None,
        help="Path for Markdown output. Default: <artifact-dir>/artifact-gap-report.md",
    )
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="Exit with status 1 when missing or empty expected artifacts are found.",
    )
    return parser


def main() -> int:
    """CLI entry point."""

    args = build_parser().parse_args()
    report = build_gap_report(args.artifact_dir, args.manifest_path)
    json_path = args.json_path or args.artifact_dir / DEFAULT_JSON_NAME
    markdown_path = args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME

    if not args.no_json:
        write_json(report, json_path)
        print(f"Wrote artifact gap report JSON to {json_path}")
    if not args.no_markdown:
        write_markdown(report, markdown_path)
        print(f"Wrote artifact gap report Markdown to {markdown_path}")
    if args.no_json and args.no_markdown:
        print("No outputs requested; remove --no-json or --no-markdown to write reports.")

    if args.fail_on_gap and report["severity"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
