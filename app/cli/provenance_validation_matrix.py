"""Build a provenance validation matrix for analytical handoff bundles.

The matrix cross-checks the artifact manifest, provenance ledger, evidence
checklist, and final validation receipt so reviewers can see which generated
files support setup, reproducibility, uncertainty, and handoff gates. It is
offline and read-only: it does not run ingestion, prediction, training,
networking, database, or operational workflows.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "provenance-validation-matrix.md"
DEFAULT_JSON_NAME = "provenance-validation-matrix.json"

SAFE_SCOPE = (
    "Offline diagnostic matrix for lawful defensive analysis handoffs. It "
    "correlates generated artifact metadata, provenance labels, evidence gates, "
    "and validation-receipt status without making operational targeting claims "
    "or claiming predictive certainty."
)

REQUIRED_SIGNALS: Mapping[str, Mapping[str, str]] = {
    "artifact-manifest.json": {
        "gate": "bundle_integrity",
        "requirement": "Every handoff bundle must include a manifest with file hashes and sizes.",
    },
    "artifact-provenance-ledger.json": {
        "gate": "data_provenance",
        "requirement": "Generated, synthetic, preview, and environment evidence must be labeled.",
    },
    "evidence-checklist.json": {
        "gate": "evidence_completeness",
        "requirement": "Baseline evidence gates must be summarized before handoff.",
    },
    "handoff-integrity-report.json": {
        "gate": "cross_artifact_integrity",
        "requirement": "Reviewer-facing outputs should agree across manifest, handoff, and uncertainty artifacts.",
    },
    "handoff-validation-receipt.json": {
        "gate": "final_validation_receipt",
        "requirement": "A deterministic receipt should identify the checked bundle and remaining blockers.",
    },
    "reviewer-handoff.json": {
        "gate": "reviewer_handoff",
        "requirement": "A copyable reviewer handoff must describe safe scope, tests, and next steps.",
    },
    "uncertainty-review-packet.json": {
        "gate": "uncertainty_communication",
        "requirement": "Analytical uncertainty and limitations must be explicit and reviewable.",
    },
}


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _manifest_files(manifest: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    files = manifest.get("files", [])
    if not isinstance(files, list):
        return []
    return [entry for entry in files if isinstance(entry, Mapping) and entry.get("path")]


def _manifest_by_path(manifest: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {str(entry["path"]): entry for entry in _manifest_files(manifest)}


def _ledger_by_path(ledger: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    entries = ledger.get("entries", [])
    if not isinstance(entries, list):
        return {}
    return {
        str(entry["path"]): entry
        for entry in entries
        if isinstance(entry, Mapping) and str(entry.get("path", "")).strip()
    }


def _status_rank(status: Any) -> int:
    normalized = str(status).lower()
    ranks = {
        "ready": 0,
        "pass": 0,
        "ok": 0,
        "present": 0,
        "needs_review": 1,
        "review": 1,
        "warn": 1,
        "warning": 1,
        "incomplete": 1,
        "missing_manifest": 2,
        "blocked": 2,
        "fail": 2,
        "failed": 2,
        "error": 2,
        "missing": 2,
    }
    return ranks.get(normalized, 1)


def _overall_status(rows: Sequence[Mapping[str, Any]], source_statuses: Mapping[str, str]) -> str:
    if any(_status_rank(row.get("status")) >= 2 for row in rows):
        return "blocked"
    if any(_status_rank(status) >= 2 for status in source_statuses.values()):
        return "blocked"
    if any(_status_rank(row.get("status")) == 1 for row in rows):
        return "needs_review"
    if any(_status_rank(status) == 1 for status in source_statuses.values()):
        return "needs_review"
    return "ready"


def _signal_status(path: str, manifest_entry: Mapping[str, Any] | None, ledger_entry: Mapping[str, Any] | None) -> str:
    if manifest_entry is None:
        return "missing"
    if path == "artifact-provenance-ledger.json" and ledger_entry is None:
        return "needs_review"
    return "ready"


def build_provenance_validation_matrix(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
    manifest: Mapping[str, Any] | None = None,
    ledger: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    receipt: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a matrix that links required handoff signals to generated artifacts."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    manifest = _as_mapping(manifest if manifest is not None else _load_json(artifact_dir / "artifact-manifest.json", {}))
    ledger = _as_mapping(ledger if ledger is not None else _load_json(artifact_dir / "artifact-provenance-ledger.json", {}))
    evidence = _as_mapping(evidence if evidence is not None else _load_json(artifact_dir / "evidence-checklist.json", {}))
    receipt = _as_mapping(receipt if receipt is not None else _load_json(artifact_dir / "handoff-validation-receipt.json", {}))

    manifest_entries = _manifest_by_path(manifest)
    ledger_entries = _ledger_by_path(ledger)

    source_statuses = {
        "artifact_manifest": str(manifest.get("status", "ready" if manifest_entries else "missing")).lower(),
        "provenance_ledger": str(ledger.get("status", "missing")).lower(),
        "evidence_checklist": str(evidence.get("status", "missing")).lower(),
        "handoff_validation_receipt": str(receipt.get("status", "missing")).lower(),
    }

    rows: List[Dict[str, Any]] = []
    for path, requirement in REQUIRED_SIGNALS.items():
        manifest_entry = manifest_entries.get(path)
        ledger_entry = ledger_entries.get(path)
        status = _signal_status(path, manifest_entry, ledger_entry)
        category = str(ledger_entry.get("category", "unknown")) if ledger_entry else "unknown"
        operational_claim = bool(ledger_entry.get("operational_claim", True)) if ledger_entry else False
        rows.append(
            {
                "gate": requirement["gate"],
                "artifact": path,
                "status": status,
                "category": category,
                "operational_claim": operational_claim,
                "sha256": str(manifest_entry.get("sha256", "")) if manifest_entry else "",
                "size_bytes": int(manifest_entry.get("size_bytes", 0) or 0) if manifest_entry else 0,
                "requirement": requirement["requirement"],
                "rationale": str(ledger_entry.get("rationale", "")) if ledger_entry else "No provenance ledger entry was available.",
            }
        )

    blockers = [
        f"{row['gate']} missing `{row['artifact']}`"
        for row in rows
        if _status_rank(row["status"]) >= 2
    ]
    warnings = [
        f"{row['gate']} needs review for `{row['artifact']}`"
        for row in rows
        if _status_rank(row["status"]) == 1
    ]
    for source, status in source_statuses.items():
        if _status_rank(status) >= 2:
            blockers.append(f"{source} source status is {status}")
        elif _status_rank(status) == 1:
            warnings.append(f"{source} source status is {status}")

    status = _overall_status(rows, source_statuses)
    if blockers:
        next_action = "Regenerate missing or blocked diagnostics, rerun `make ci-report`, then re-export the matrix."
    elif warnings:
        next_action = "Review warning rows, document accepted limitations, rerun narrow generators, then re-export the matrix."
    else:
        next_action = "Attach this matrix with the diagnostic bundle and rerun `make verify` before handoff or merge."

    return {
        "generated_at": generated_at.isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "status": status,
        "source_statuses": source_statuses,
        "required_signal_count": len(REQUIRED_SIGNALS),
        "ready_signal_count": sum(1 for row in rows if row["status"] == "ready"),
        "blockers": blockers,
        "warnings": warnings,
        "next_action": next_action,
        "rows": rows,
        "safe_scope": SAFE_SCOPE,
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(matrix: Mapping[str, Any]) -> Iterable[str]:
    yield "# Provenance Validation Matrix"
    yield ""
    yield "A deterministic, privacy-safe cross-check of generated handoff evidence, provenance labels, and validation signals."
    yield ""
    yield f"Generated: `{matrix['generated_at']}`"
    yield f"Artifact directory: `{matrix['artifact_dir']}`"
    yield f"Status: **{str(matrix['status']).upper()}**"
    yield f"Ready signals: {matrix['ready_signal_count']} / {matrix['required_signal_count']}"
    yield f"Next action: {matrix['next_action']}"
    yield ""
    yield "## Source statuses"
    yield ""
    yield "| Source | Status |"
    yield "| --- | --- |"
    for source, status in matrix["source_statuses"].items():
        yield f"| `{_escape_table(source)}` | {_escape_table(status).upper()} |"
    yield ""
    yield "## Required validation signals"
    yield ""
    yield "| Gate | Artifact | Status | Category | Operational claim | Requirement |"
    yield "| --- | --- | --- | --- | --- | --- |"
    for row in matrix["rows"]:
        operational = "yes" if row["operational_claim"] else "no"
        yield (
            f"| `{_escape_table(row['gate'])}` | `{_escape_table(row['artifact'])}` | "
            f"{_escape_table(row['status']).upper()} | `{_escape_table(row['category'])}` | "
            f"{operational} | {_escape_table(row['requirement'])} |"
        )
    yield ""
    yield "## Blockers and warnings"
    yield ""
    blockers = list(matrix.get("blockers", []))
    warnings = list(matrix.get("warnings", []))
    if not blockers and not warnings:
        yield "No blockers or warnings were detected from the available generated diagnostics."
    else:
        for blocker in blockers:
            yield f"- BLOCKER: {blocker}"
        for warning in warnings:
            yield f"- WARNING: {warning}"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(matrix["safe_scope"])


def render_markdown(matrix: Mapping[str, Any]) -> str:
    """Render the matrix as reviewer-friendly Markdown."""

    return "\n".join(_markdown_lines(matrix)).rstrip() + "\n"


def write_outputs(matrix: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested matrix outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(matrix), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a provenance validation matrix for analytical handoff artifacts."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"Directory containing generated diagnostics. Default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument("--markdown-path", type=Path, default=None, help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=None, help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    matrix = build_provenance_validation_matrix(args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    write_outputs(matrix, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote provenance validation matrix Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote provenance validation matrix JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write matrix files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
