"""Generate a deterministic evidence checklist for analytical release handoffs.

The checklist reads local diagnostic artifacts and summarizes whether a bundle has
reviewable evidence for provenance, uncertainty, validation, handoff integrity,
and safe analytical framing. It does not run prediction, collect data, call
networks, mutate source artifacts, or infer operational truth.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "evidence-checklist.md"
DEFAULT_JSON_NAME = "evidence-checklist.json"

ANALYTICAL_SCOPE = (
    "Review generated evidence for lawful defensive analysis, reproducibility, "
    "uncertainty communication, safe handoff, and artifact integrity. Do not "
    "present synthetic examples, bundle metadata, or predictive estimates as "
    "operational certainty."
)


@dataclass(frozen=True)
class EvidenceCheck:
    """One deterministic evidence checklist item."""

    name: str
    status: str
    source: str
    detail: str
    action: str


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def _has_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _status(ok: bool, warn: bool = False) -> str:
    if ok:
        return "pass"
    if warn:
        return "warn"
    return "fail"


def _count_status(checks: Sequence[EvidenceCheck]) -> Dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    return counts


def _manifest_files(manifest: Mapping[str, Any]) -> List[str]:
    raw_files = manifest.get("files", [])
    files: List[str] = []
    if isinstance(raw_files, list):
        for item in raw_files:
            if isinstance(item, Mapping):
                name = str(item.get("path") or item.get("name") or "").strip()
            else:
                name = str(item).strip()
            if name:
                files.append(name)
    return files


def _artifact_present(artifact_dir: Path, manifest_files: Sequence[str], artifact_name: str) -> bool:
    return artifact_name in manifest_files or _has_file(artifact_dir / artifact_name)


def _detail_from_count(count: int, noun: str) -> str:
    if count == 1:
        return f"1 {noun} found"
    return f"{count} {noun}s found"


def build_evidence_checklist(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
    manifest: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
    triage: Mapping[str, Any] | None = None,
    handoff: Mapping[str, Any] | None = None,
    uncertainty: Mapping[str, Any] | None = None,
    integrity: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a machine-readable evidence checklist from local artifacts."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    manifest = manifest if manifest is not None else _load_json(artifact_dir / "artifact-manifest.json", {})
    provenance = provenance if provenance is not None else _load_json(
        artifact_dir / "artifact-provenance-ledger.json", {}
    )
    triage = triage if triage is not None else _load_json(artifact_dir / "triage-summary.json", {})
    handoff = handoff if handoff is not None else _load_json(artifact_dir / "reviewer-handoff.json", {})
    uncertainty = uncertainty if uncertainty is not None else _load_json(
        artifact_dir / "uncertainty-review-packet.json", {}
    )
    integrity = integrity if integrity is not None else _load_json(artifact_dir / "handoff-integrity-report.json", {})

    manifest_files = _manifest_files(manifest)
    missing_expected = [str(item) for item in manifest.get("missing_expected", []) if str(item)]
    suspicious = [str(item) for item in manifest.get("suspicious_artifacts", []) if str(item)]
    provenance_entries = provenance.get("entries", []) if isinstance(provenance.get("entries", []), list) else []
    uncertainty_actions = (
        uncertainty.get("recommended_actions", [])
        if isinstance(uncertainty.get("recommended_actions", []), list)
        else []
    )
    triage_actions = triage.get("recommended_actions", []) if isinstance(triage.get("recommended_actions", []), list) else []
    integrity_status = str(integrity.get("status", "unknown")).lower()
    triage_status = str(triage.get("status", "unknown")).lower()
    review_status = str(handoff.get("review_status", "unknown")).lower()

    required_artifacts = [
        "artifact-manifest.json",
        "artifact-provenance-ledger.json",
        "triage-summary.json",
        "reviewer-handoff.json",
        "uncertainty-review-packet.json",
        "handoff-integrity-report.json",
    ]
    missing_required = [name for name in required_artifacts if not _artifact_present(artifact_dir, manifest_files, name)]

    checks = [
        EvidenceCheck(
            name="required_review_artifacts",
            status=_status(not missing_required),
            source="artifact manifest and artifact directory",
            detail=("all required review artifacts are present" if not missing_required else ", ".join(missing_required)),
            action=("review generated Markdown summaries" if not missing_required else "rerun make ci-report"),
        ),
        EvidenceCheck(
            name="manifest_completeness",
            status=_status(not missing_expected, warn=bool(manifest_files)),
            source="artifact-manifest.json",
            detail=("no expected artifacts missing" if not missing_expected else ", ".join(missing_expected)),
            action=("continue release review" if not missing_expected else "rerun the narrow generator for each missing item"),
        ),
        EvidenceCheck(
            name="suspicious_artifact_review",
            status=_status(not suspicious),
            source="artifact-manifest.json",
            detail=("no suspicious artifacts listed" if not suspicious else ", ".join(suspicious[:8])),
            action=("continue release review" if not suspicious else "inspect unexpected files before sharing bundle"),
        ),
        EvidenceCheck(
            name="provenance_labels",
            status=_status(bool(provenance_entries)),
            source="artifact-provenance-ledger.json",
            detail=_detail_from_count(len(provenance_entries), "provenance entry"),
            action=("verify synthetic/preview/review labels" if provenance_entries else "rerun make provenance-ledger"),
        ),
        EvidenceCheck(
            name="uncertainty_actions",
            status=_status(bool(uncertainty_actions), warn=True),
            source="uncertainty-review-packet.json",
            detail=_detail_from_count(len(uncertainty_actions), "uncertainty action"),
            action=(
                "address or acknowledge uncertainty actions before external handoff"
                if uncertainty_actions
                else "confirm the packet explicitly says no uncertainty action is needed"
            ),
        ),
        EvidenceCheck(
            name="handoff_integrity_status",
            status=_status(integrity_status in {"pass", "ready", "ok"}, warn=integrity_status not in {"fail", "blocked"}),
            source="handoff-integrity-report.json",
            detail=f"integrity status: {integrity_status}",
            action=("continue release review" if integrity_status in {"pass", "ready", "ok"} else "inspect cross-artifact mismatch details"),
        ),
        EvidenceCheck(
            name="triage_status",
            status=_status(triage_status in {"ready", "pass", "ok"}, warn=triage_status not in {"blocked", "fail"}),
            source="triage-summary.json",
            detail=f"triage status: {triage_status}; {_detail_from_count(len(triage_actions), 'triage action')}",
            action=("continue release review" if triage_status in {"ready", "pass", "ok"} else "complete narrow triage actions first"),
        ),
        EvidenceCheck(
            name="reviewer_handoff_status",
            status=_status(review_status in {"ready", "pass", "ok"}, warn=review_status not in {"blocked", "fail"}),
            source="reviewer-handoff.json",
            detail=f"review status: {review_status}",
            action=("send handoff to reviewer" if review_status in {"ready", "pass", "ok"} else "review handoff warnings before sharing"),
        ),
    ]

    counts = _count_status(checks)
    if counts["fail"]:
        status = "blocked"
        next_action = "Repair failing evidence checks before handing off or merging."
    elif counts["warn"]:
        status = "needs_review"
        next_action = "Review warnings, document acceptance or rerun narrow generators, then re-export checklist."
    else:
        status = "ready"
        next_action = "Bundle has baseline evidence for defensive analytical review."

    return {
        "generated_at": generated_at.isoformat(),
        "status": status,
        "next_action": next_action,
        "summary": counts,
        "checks": [check.__dict__ for check in checks],
        "required_artifacts": required_artifacts,
        "safe_scope": ANALYTICAL_SCOPE,
    }


def _markdown_lines(report: Mapping[str, Any]) -> Iterable[str]:
    yield "# Evidence Checklist"
    yield ""
    yield "A deterministic review checklist for diagnostic bundles and analytical handoffs."
    yield ""
    yield f"Generated: `{report['generated_at']}`"
    yield f"Status: **{str(report['status']).upper()}**"
    yield f"Next action: {report['next_action']}"
    yield ""
    summary = report["summary"]
    yield "## Summary"
    yield ""
    yield f"- Pass: {summary['pass']}"
    yield f"- Warn: {summary['warn']}"
    yield f"- Fail: {summary['fail']}"
    yield ""
    yield "## Checklist"
    yield ""
    yield "| Check | Status | Source | Detail | Action |"
    yield "| --- | --- | --- | --- | --- |"
    for check in report["checks"]:
        name = str(check["name"]).replace("|", "\\|")
        status = str(check["status"]).upper()
        source = str(check["source"]).replace("|", "\\|")
        detail = str(check["detail"]).replace("|", "\\|")
        action = str(check["action"]).replace("|", "\\|")
        yield f"| `{name}` | {status} | {source} | {detail} | {action} |"
    yield ""
    yield "## Required review artifacts"
    yield ""
    for artifact in report["required_artifacts"]:
        yield f"- `{artifact}`"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(report["safe_scope"])


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render an evidence checklist as Markdown."""

    return "\n".join(_markdown_lines(report)).rstrip() + "\n"


def write_outputs(report: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    """Write requested checklist outputs."""

    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic evidence checklist for analytical handoff artifacts."
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
    report = build_evidence_checklist(args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    write_outputs(report, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote evidence checklist Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote evidence checklist JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write evidence checklist files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
