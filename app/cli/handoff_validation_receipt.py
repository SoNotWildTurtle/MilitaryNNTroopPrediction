"""Generate a privacy-safe validation receipt for analytical handoff bundles.

The receipt records deterministic, offline metadata from generated diagnostics so
reviewers can confirm which bundle was checked, which safety gates were present,
and which local validation commands should be rerun. It never runs collection,
prediction, training, networking, database, or operational workflows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "handoff-validation-receipt.md"
DEFAULT_JSON_NAME = "handoff-validation-receipt.json"

SAFE_SCOPE = (
    "Offline diagnostic receipt for lawful defensive analysis handoffs. It only "
    "summarizes generated artifact metadata, safety-gate statuses, reproducible "
    "hashes, and rerun commands; it is not operational targeting guidance or a "
    "claim of predictive certainty."
)

REQUIRED_RECEIPT_ARTIFACTS = (
    "artifact-manifest.json",
    "artifact-provenance-ledger.json",
    "triage-summary.json",
    "reviewer-handoff.json",
    "uncertainty-review-packet.json",
    "handoff-integrity-report.json",
    "evidence-checklist.json",
)

RERUN_COMMANDS = (
    "make verify",
    "make ci-report",
    "make handoff-validation-receipt",
)


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
    return [entry for entry in files if isinstance(entry, Mapping)]


def _manifest_paths(manifest: Mapping[str, Any]) -> set[str]:
    paths: set[str] = set()
    for entry in _manifest_files(manifest):
        path = str(entry.get("path", "")).strip()
        if path:
            paths.add(path)
    return paths


def _artifact_present(artifact_dir: Path, manifest: Mapping[str, Any], name: str) -> bool:
    return name in _manifest_paths(manifest) or (artifact_dir / name).is_file()


def _status_rank(status: str) -> int:
    ranks = {
        "ready": 0,
        "pass": 0,
        "ok": 0,
        "needs_review": 1,
        "review_warnings": 1,
        "warn": 1,
        "warning": 1,
        "blocked": 2,
        "fail": 2,
        "failed": 2,
        "error": 2,
    }
    return ranks.get(status.lower(), 1)


def _receipt_status(statuses: Mapping[str, str], missing_required: Sequence[str]) -> str:
    if missing_required:
        return "blocked"
    worst = max((_status_rank(value) for value in statuses.values()), default=1)
    if worst >= 2:
        return "blocked"
    if worst == 1:
        return "needs_review"
    return "ready"


def _hash_manifest_entries(manifest: Mapping[str, Any]) -> str:
    """Hash manifest path/sha/size tuples without reading generated artifacts again."""

    relevant_entries = []
    for entry in _manifest_files(manifest):
        path = str(entry.get("path", "")).strip()
        if not path:
            continue
        relevant_entries.append(
            {
                "path": path,
                "sha256": str(entry.get("sha256", "")),
                "size_bytes": int(entry.get("size_bytes", 0) or 0),
            }
        )
    payload = json.dumps(sorted(relevant_entries, key=lambda item: item["path"]), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_handoff_validation_receipt(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
    manifest: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    integrity: Mapping[str, Any] | None = None,
    triage: Mapping[str, Any] | None = None,
    handoff: Mapping[str, Any] | None = None,
    uncertainty: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a deterministic validation receipt from generated local artifacts."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    manifest = _as_mapping(manifest if manifest is not None else _load_json(artifact_dir / "artifact-manifest.json", {}))
    evidence = _as_mapping(evidence if evidence is not None else _load_json(artifact_dir / "evidence-checklist.json", {}))
    integrity = _as_mapping(
        integrity if integrity is not None else _load_json(artifact_dir / "handoff-integrity-report.json", {})
    )
    triage = _as_mapping(triage if triage is not None else _load_json(artifact_dir / "triage-summary.json", {}))
    handoff = _as_mapping(handoff if handoff is not None else _load_json(artifact_dir / "reviewer-handoff.json", {}))
    uncertainty = _as_mapping(
        uncertainty if uncertainty is not None else _load_json(artifact_dir / "uncertainty-review-packet.json", {})
    )

    missing_required = [
        name for name in REQUIRED_RECEIPT_ARTIFACTS if not _artifact_present(artifact_dir, manifest, name)
    ]
    evidence_summary = evidence.get("summary", {}) if isinstance(evidence.get("summary", {}), Mapping) else {}
    handoff_summary = handoff.get("summary", {}) if isinstance(handoff.get("summary", {}), Mapping) else {}
    statuses = {
        "evidence_checklist": str(evidence.get("status", "unknown")).lower(),
        "handoff_integrity": str(integrity.get("status", "unknown")).lower(),
        "triage_summary": str(triage.get("status", "unknown")).lower(),
        "reviewer_handoff": str(
            handoff.get("review_status") or handoff.get("status") or handoff_summary.get("status", "unknown")
        ).lower(),
        "uncertainty_packet": str(uncertainty.get("status", "unknown")).lower(),
    }
    manifest_missing_expected = [str(item) for item in manifest.get("missing_expected", []) if str(item).strip()]
    manifest_scan_warnings = [
        str(item.get("path", item)) if isinstance(item, Mapping) else str(item)
        for item in manifest.get("scan_warnings", [])
        if str(item).strip()
    ]

    blockers: List[str] = []
    if missing_required:
        blockers.append(f"missing required receipt artifacts: {', '.join(missing_required)}")
    if manifest_missing_expected:
        blockers.append(f"manifest reports missing expected artifacts: {len(manifest_missing_expected)}")
    if any(_status_rank(status) >= 2 for status in statuses.values()):
        blockers.append("one or more upstream handoff gates are blocked or failing")

    warnings: List[str] = []
    if manifest_scan_warnings:
        warnings.append(f"manifest scan warnings: {len(manifest_scan_warnings)}")
    if any(_status_rank(status) == 1 for status in statuses.values()):
        warnings.append("one or more upstream handoff gates need review")
    if not evidence_summary:
        warnings.append("evidence checklist summary is unavailable")

    status = _receipt_status(statuses, [*missing_required, *manifest_missing_expected])
    if blockers:
        next_action = "Repair blocked validation gates, regenerate the diagnostic bundle, then re-export the receipt."
    elif warnings:
        next_action = "Review warnings, document acceptance or rerun narrow generators, then re-export the receipt."
    else:
        next_action = "Attach this receipt with the diagnostic bundle and rerun make verify before merge or external handoff."

    return {
        "generated_at": generated_at.isoformat(),
        "status": status,
        "next_action": next_action,
        "artifact_dir": artifact_dir.as_posix(),
        "artifact_count": int(manifest.get("file_count", 0) or 0),
        "total_size_bytes": int(manifest.get("total_size_bytes", 0) or 0),
        "bundle_manifest_digest": _hash_manifest_entries(manifest),
        "required_artifacts": list(REQUIRED_RECEIPT_ARTIFACTS),
        "missing_required_artifacts": missing_required,
        "upstream_statuses": statuses,
        "evidence_summary": {
            "pass": int(evidence_summary.get("pass", 0) or 0),
            "warn": int(evidence_summary.get("warn", 0) or 0),
            "fail": int(evidence_summary.get("fail", 0) or 0),
        },
        "manifest_missing_expected": manifest_missing_expected,
        "manifest_scan_warnings": manifest_scan_warnings,
        "blockers": blockers,
        "warnings": warnings,
        "rerun_commands": list(RERUN_COMMANDS),
        "safe_scope": SAFE_SCOPE,
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(receipt: Mapping[str, Any]) -> Iterable[str]:
    yield "# Handoff Validation Receipt"
    yield ""
    yield "A deterministic, privacy-safe receipt for analytical diagnostic bundle validation."
    yield ""
    yield f"Generated: `{receipt['generated_at']}`"
    yield f"Status: **{str(receipt['status']).upper()}**"
    yield f"Next action: {receipt['next_action']}"
    yield ""
    yield "## Bundle identity"
    yield ""
    yield f"- Artifact directory: `{receipt['artifact_dir']}`"
    yield f"- Indexed artifacts: `{receipt['artifact_count']}`"
    yield f"- Total indexed size: `{receipt['total_size_bytes']}` bytes"
    yield f"- Manifest entry digest: `{receipt['bundle_manifest_digest']}`"
    yield ""
    yield "## Upstream validation gates"
    yield ""
    yield "| Gate | Status |"
    yield "| --- | --- |"
    for gate, status in receipt["upstream_statuses"].items():
        yield f"| `{_escape_table(gate)}` | {_escape_table(status).upper()} |"
    yield ""
    yield "## Evidence summary"
    yield ""
    summary = receipt["evidence_summary"]
    yield f"- Pass: {summary['pass']}"
    yield f"- Warn: {summary['warn']}"
    yield f"- Fail: {summary['fail']}"
    yield ""
    yield "## Blockers and warnings"
    yield ""
    blockers = list(receipt.get("blockers", []))
    warnings = list(receipt.get("warnings", []))
    if not blockers and not warnings:
        yield "No blockers or warnings were detected from the available generated diagnostics."
    else:
        for blocker in blockers:
            yield f"- BLOCKER: {blocker}"
        for warning in warnings:
            yield f"- WARNING: {warning}"
    yield ""
    yield "## Required receipt artifacts"
    yield ""
    for artifact in receipt["required_artifacts"]:
        marker = "missing" if artifact in receipt.get("missing_required_artifacts", []) else "present"
        yield f"- `{artifact}` — {marker}"
    yield ""
    yield "## Reproducible rerun commands"
    yield ""
    for command in receipt["rerun_commands"]:
        yield f"- `{command}`"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(receipt["safe_scope"])


def render_markdown(receipt: Mapping[str, Any]) -> str:
    """Render a validation receipt as Markdown."""

    return "\n".join(_markdown_lines(receipt)).rstrip() + "\n"


def write_outputs(receipt: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested receipt outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(receipt), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic validation receipt for analytical handoff artifacts."
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
    receipt = build_handoff_validation_receipt(args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    write_outputs(receipt, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote handoff validation receipt Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote handoff validation receipt JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write receipt files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
