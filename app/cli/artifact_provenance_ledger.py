"""Generate a provenance ledger for local diagnostic artifact bundles.

The ledger is intentionally read-only: it classifies generated artifacts, synthetic
fixtures, dependency evidence, and review handoff files without executing model,
ingestion, database, network, or deployment workflows.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from app.cli.artifact_manifest import DEFAULT_ARTIFACT_DIR

DEFAULT_MARKDOWN_NAME = "artifact-provenance-ledger.md"
DEFAULT_JSON_NAME = "artifact-provenance-ledger.json"

CATEGORY_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "synthetic-fixtures/",
        "synthetic_fixture",
        "Safe deterministic fixture generated locally for demos, tests, and client integration; not operational evidence.",
    ),
    (
        "previews/",
        "visual_preview",
        "Generated browser-free preview of an HTML artifact for reviewer convenience.",
    ),
    (
        "pip-",
        "environment_evidence",
        "Local dependency/version evidence captured for reproducibility and troubleshooting.",
    ),
    (
        "python-version.txt",
        "environment_evidence",
        "Local interpreter evidence captured for reproducibility and troubleshooting.",
    ),
    (
        "doctor-",
        "setup_diagnostic",
        "Local setup diagnostic generated without prediction, ingestion, or deployment side effects.",
    ),
    (
        "release-health",
        "release_gate",
        "Generated release readiness evidence for review gates and operator handoff.",
    ),
    (
        "implementation-acceptance-",
        "implementation_acceptance_evidence",
        "Generated implementation acceptance checklist or completed-evidence handoff for reviewer merge gates.",
    ),
    (
        "reviewer-handoff",
        "handoff",
        "Generated reviewer handoff artifact intended for human and machine review.",
    ),
    (
        "operator-",
        "operator_handoff",
        "Generated operator-facing handoff artifact summarizing local diagnostics and next safe actions.",
    ),
    (
        "artifact-",
        "bundle_integrity",
        "Generated bundle-integrity artifact used to verify expected files, hashes, and completeness.",
    ),
    (
        "triage-summary",
        "ci_triage",
        "Generated CI triage artifact with narrow local rerun targets.",
    ),
    (
        "automation-plan",
        "automation_planning",
        "Generated additive next-run planning artifact constrained to safe local maintenance scope.",
    ),
    (
        "openapi",
        "api_contract",
        "Generated API contract artifact for client validation and compatibility review.",
    ),
    (
        "api-response-examples",
        "synthetic_api_example",
        "Synthetic API example artifact generated for docs, clients, and tests; not operational evidence.",
    ),
    (
        "dashboard-mockup",
        "ux_preview",
        "Generated static dashboard preview for UX review without live data access.",
    ),
    (
        "release-bundle-index",
        "bundle_navigation",
        "Generated offline landing page for navigating diagnostic artifacts.",
    ),
    (
        "html-previews",
        "visual_preview_index",
        "Generated index of static visual previews for reviewer convenience.",
    ),
    (
        "summary.txt",
        "bundle_summary",
        "Plain-language generated summary of diagnostic bundle contents.",
    ),
)

NON_OPERATIONAL_CATEGORIES = {
    "synthetic_fixture",
    "synthetic_api_example",
    "ux_preview",
    "visual_preview",
    "visual_preview_index",
    "bundle_navigation",
    "bundle_summary",
}


def _load_json(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _classify(path: str) -> Dict[str, str]:
    for prefix, category, rationale in CATEGORY_RULES:
        if path == prefix or path.startswith(prefix) or path.startswith(prefix.rstrip("/")):
            return {"category": category, "rationale": rationale}
    return {
        "category": "generated_diagnostic",
        "rationale": "Generated local diagnostic artifact not matched by a more specific provenance rule.",
    }


def _manifest_files(manifest: Mapping[str, Any] | None) -> List[Mapping[str, Any]]:
    if not manifest:
        return []
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return []
    return [entry for entry in files if isinstance(entry, Mapping) and entry.get("path")]


def build_provenance_ledger(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    *,
    manifest_path: Path | None = None,
) -> Dict[str, Any]:
    """Build a machine-readable provenance ledger from an artifact manifest."""

    resolved_manifest_path = manifest_path or artifact_dir / "artifact-manifest.json"
    manifest = _load_json(resolved_manifest_path)
    entries: List[Dict[str, Any]] = []
    category_counts: Dict[str, int] = {}
    non_operational: List[str] = []
    missing_expected: List[str] = []

    if manifest and isinstance(manifest.get("missing_expected"), list):
        missing_expected = [str(item) for item in manifest["missing_expected"]]

    for item in _manifest_files(manifest):
        path = str(item.get("path"))
        classification = _classify(path)
        category = classification["category"]
        category_counts[category] = category_counts.get(category, 0) + 1
        operational_claim = category not in NON_OPERATIONAL_CATEGORIES
        if not operational_claim:
            non_operational.append(path)
        entries.append(
            {
                "path": path,
                "category": category,
                "operational_claim": operational_claim,
                "rationale": classification["rationale"],
                "size_bytes": item.get("size_bytes"),
                "sha256": item.get("sha256"),
                "description": item.get("description", "Generated diagnostic artifact."),
            }
        )

    status = "ready" if manifest and not missing_expected else "needs_review"
    if not manifest:
        status = "missing_manifest"

    ledger: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "manifest_path": resolved_manifest_path.as_posix(),
        "status": status,
        "file_count": len(entries),
        "category_counts": dict(sorted(category_counts.items())),
        "missing_expected": missing_expected,
        "non_operational_artifacts": sorted(non_operational),
        "entries": sorted(entries, key=lambda entry: str(entry["path"])),
        "safe_scope": "Classifies local diagnostic artifacts only; does not run ingestion, prediction, network, database, deployment, or targeting workflows.",
    }
    ledger["copyable_summary"] = (
        f"Provenance ledger for `{ledger['artifact_dir']}`: {ledger['file_count']} artifact(s), "
        f"status `{ledger['status']}`, {len(ledger['non_operational_artifacts'])} synthetic/preview artifact(s), "
        f"{len(ledger['missing_expected'])} missing expected artifact(s)."
    )
    return ledger


def _markdown_lines(ledger: Mapping[str, Any]) -> Iterable[str]:
    yield "# Artifact provenance ledger"
    yield ""
    yield "Use this ledger to explain where diagnostics artifacts came from and which outputs are synthetic, preview-only, or review evidence."
    yield ""
    yield f"Generated at: `{ledger['generated_at']}`"
    yield f"Artifact directory: `{ledger['artifact_dir']}`"
    yield f"Manifest path: `{ledger['manifest_path']}`"
    yield f"Status: **{str(ledger['status']).upper()}**"
    yield f"Files classified: {ledger['file_count']}"
    yield ""
    yield "## Copyable summary"
    yield ""
    yield "```text"
    yield str(ledger["copyable_summary"])
    yield "```"
    yield ""
    yield "## Category counts"
    yield ""
    yield "| Category | Count |"
    yield "| --- | ---: |"
    for category, count in ledger.get("category_counts", {}).items():
        yield f"| `{category}` | {count} |"
    if not ledger.get("category_counts"):
        yield "| `none` | 0 |"
    yield ""
    yield "## Classified artifacts"
    yield ""
    yield "| Path | Category | Operational claim | SHA-256 | Rationale |"
    yield "| --- | --- | --- | --- | --- |"
    for entry in ledger.get("entries", []):
        operational = "yes" if entry.get("operational_claim") else "no"
        sha = entry.get("sha256") or "-"
        yield f"| `{entry['path']}` | `{entry['category']}` | {operational} | `{sha}` | {entry['rationale']} |"
    if ledger.get("missing_expected"):
        yield ""
        yield "## Missing expected artifacts"
        yield ""
        for path in ledger["missing_expected"]:
            yield f"- `{path}`"
    yield ""
    yield "## Safe operating scope"
    yield ""
    yield str(ledger["safe_scope"])


def render_markdown(ledger: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(ledger)).rstrip() + "\n"


def write_json(ledger: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(markdown_text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a provenance ledger for local diagnostic artifact bundles."
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
        help="Optional explicit artifact-manifest.json path.",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        default=None,
        help="Path for Markdown output. Default: <artifact-dir>/artifact-provenance-ledger.md",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=None,
        help="Path for JSON output. Default: <artifact-dir>/artifact-provenance-ledger.json",
    )
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ledger = build_provenance_ledger(args.artifact_dir, manifest_path=args.manifest_path)
    markdown_path = args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = args.json_path or args.artifact_dir / DEFAULT_JSON_NAME

    if not args.no_markdown:
        write_markdown(render_markdown(ledger), markdown_path)
        print(f"Wrote artifact provenance ledger Markdown to {markdown_path}")
    if not args.no_json:
        write_json(ledger, json_path)
        print(f"Wrote artifact provenance ledger JSON to {json_path}")
    if args.no_markdown and args.no_json:
        print("No outputs requested; remove --no-markdown or --no-json to write provenance ledger files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
