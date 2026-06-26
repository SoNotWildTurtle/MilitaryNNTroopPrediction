"""Generate an operator-facing runbook index for safe local workflows.

The runbook index is documentation and diagnostics oriented. It does not run
collection, prediction, detection, network, deployment, or live-intelligence
workflows. Its purpose is to make generated bundles easier to review, explain,
and hand off by connecting safe commands, docs, artifacts, and next steps.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from app.cli.artifact_manifest import DEFAULT_ARTIFACT_DIR

DEFAULT_MARKDOWN_NAME = "operator-runbook-index.md"
DEFAULT_JSON_NAME = "operator-runbook-index.json"

SAFE_SCOPE = (
    "Local setup, deterministic tests, synthetic examples, API contracts, generated artifacts, "
    "reviewer handoff notes, CI triage, and documentation."
)

COMMANDS: List[Dict[str, str]] = [
    {
        "name": "help",
        "command": "make help",
        "category": "orientation",
        "purpose": "List supported task-runner commands and configurable variables.",
        "when_to_use": "Start here when joining the project or checking available workflows.",
        "output": "Terminal task map.",
    },
    {
        "name": "quickstart",
        "command": "make quickstart",
        "category": "onboarding",
        "purpose": "Run the conservative first-run setup flow.",
        "when_to_use": "Use before optional ML, GIS, or dashboard dependencies are installed.",
        "output": "Guided setup status and recommended next command.",
    },
    {
        "name": "doctor",
        "command": "make doctor",
        "category": "validation",
        "purpose": "Run minimal read-only setup diagnostics.",
        "when_to_use": "Use when environment setup is suspect or before opening a PR.",
        "output": "JSON setup health summary.",
    },
    {
        "name": "test",
        "command": "make test",
        "category": "validation",
        "purpose": "Run local smoke checks and standard-library unit tests.",
        "when_to_use": "Use after changing Python modules, scripts, docs contracts, or artifact CLIs.",
        "output": "Compile and unittest results.",
    },
    {
        "name": "verify",
        "command": "make verify",
        "category": "validation",
        "purpose": "Run doctor, tests, diagnostics, and handoff contract validation in one pass.",
        "when_to_use": "Use as the standard pre-PR validation command.",
        "output": "Full local validation plus ci_artifacts diagnostics bundle.",
    },
    {
        "name": "ci-report",
        "command": "make ci-report",
        "category": "artifacts",
        "purpose": "Build the local CI diagnostics bundle.",
        "when_to_use": "Use when a reviewer needs static reports without running live services.",
        "output": "ci_artifacts directory with reviewer pages, examples, manifests, and summaries.",
    },
    {
        "name": "operator-status-board",
        "command": "make operator-status-board",
        "category": "handoff",
        "purpose": "Export a quick non-technical status board for generated diagnostics.",
        "when_to_use": "Use for manager/operator first-read handoff.",
        "output": "operator-status-board.md/json.",
    },
    {
        "name": "operator-session-plan",
        "command": "make operator-session-plan",
        "category": "handoff",
        "purpose": "Export a ranked next-session maintenance checklist.",
        "when_to_use": "Use when planning the next safe repository improvement run.",
        "output": "operator-session-plan.md/json.",
    },
    {
        "name": "automation-plan",
        "command": "make automation-plan",
        "category": "planning",
        "purpose": "Export a safe additive next-run plan from diagnostics and goals.",
        "when_to_use": "Use for scheduled maintenance and automation handoffs.",
        "output": "automation-plan.md/json.",
    },
    {
        "name": "artifact-gap-report",
        "command": "make artifact-gap-report",
        "category": "artifacts",
        "purpose": "Audit bundle completeness and suspicious generated artifacts.",
        "when_to_use": "Use when expected files are missing or empty.",
        "output": "artifact-gap-report.md/json.",
    },
    {
        "name": "provenance-ledger",
        "command": "make provenance-ledger",
        "category": "artifacts",
        "purpose": "Label generated, synthetic, preview, and review artifacts for safer handoff.",
        "when_to_use": "Use before sharing bundles to clarify artifact origin and limitations.",
        "output": "artifact-provenance-ledger.md/json.",
    },
    {
        "name": "synthetic-fixtures",
        "command": "make synthetic-fixtures",
        "category": "examples",
        "purpose": "Export safe JSONL/CSV fixtures for demos and client tests.",
        "when_to_use": "Use when examples are needed without live data sources.",
        "output": "data/fixtures synthetic records and summary.",
    },
]

DOCS: List[Dict[str, str]] = [
    {
        "path": "README.md",
        "category": "orientation",
        "purpose": "Project overview, setup, API routes, and common validation flow.",
    },
    {
        "path": "CONTRIBUTING.md",
        "category": "governance",
        "purpose": "Safe contribution scope, PR checklist, and reviewer expectations.",
    },
    {
        "path": "docs/common_tasks.md",
        "category": "operations",
        "purpose": "Copyable make workflows for setup, validation, artifacts, and cleanup.",
    },
    {
        "path": "docs/ci_troubleshooting.md",
        "category": "recovery",
        "purpose": "Narrow local reproduction and diagnostics guidance for hosted CI failures.",
    },
    {
        "path": "docs/release_bundle_review.md",
        "category": "review",
        "purpose": "Review checklist for generated diagnostics bundles.",
    },
    {
        "path": "docs/artifact_provenance_ledger.md",
        "category": "review",
        "purpose": "Explains generated, synthetic, preview, and reviewer artifact provenance labels.",
    },
    {
        "path": "docs/operator_status_board.md",
        "category": "handoff",
        "purpose": "Fast non-technical status board workflow.",
    },
    {
        "path": "docs/operator_session_plan.md",
        "category": "planning",
        "purpose": "Ranked next-session maintenance checklist workflow.",
    },
    {
        "path": "docs/operator_runbook_index.md",
        "category": "orientation",
        "purpose": "This generated runbook index workflow and rollback notes.",
    },
]

ARTIFACTS: List[Dict[str, str]] = [
    {
        "path": "release-bundle-index.html",
        "category": "landing_page",
        "purpose": "Open first when reviewing a generated diagnostics bundle.",
    },
    {
        "path": "operator-status-board.md",
        "category": "handoff",
        "purpose": "Quick readable readiness/status board for non-technical operators.",
    },
    {
        "path": "operator-session-plan.md",
        "category": "planning",
        "purpose": "Ranked checklist for the next maintenance session.",
    },
    {
        "path": "automation-plan.md",
        "category": "planning",
        "purpose": "Safe additive next-run plan for scheduled improvement work.",
    },
    {
        "path": "reviewer-handoff.md",
        "category": "review",
        "purpose": "Copyable reviewer summary and validation guidance.",
    },
    {
        "path": "triage-summary.md",
        "category": "recovery",
        "purpose": "CI failure triage summary with narrow rerun targets.",
    },
    {
        "path": "artifact-manifest.md",
        "category": "evidence",
        "purpose": "File sizes, hashes, and missing expected artifacts.",
    },
    {
        "path": "artifact-provenance-ledger.md",
        "category": "evidence",
        "purpose": "Artifact origin, synthetic/preview labels, and sharing notes.",
    },
    {
        "path": "artifact-gap-report.md",
        "category": "evidence",
        "purpose": "Completeness and suspicious artifact audit.",
    },
]

FIRST_STEPS: Sequence[str] = (
    "Run `make help` to confirm the task runner is available.",
    "Run `make quickstart` on a new checkout for conservative setup.",
    "Run `make verify` before opening or updating a pull request.",
    "Open `ci_artifacts/release-bundle-index.html` first when reviewing generated artifacts.",
    "Use `ci_artifacts/operator-status-board.md` for a fast non-technical handoff.",
    "Use `ci_artifacts/operator-session-plan.md` or `ci_artifacts/automation-plan.md` to pick the next safe improvement.",
)


def _artifact_state(artifact_dir: Path, path: str) -> Dict[str, Any]:
    artifact_path = artifact_dir / path
    return {
        "path": path,
        "present": artifact_path.exists(),
        "status": "present" if artifact_path.exists() else "not_generated_yet",
        "size_bytes": artifact_path.stat().st_size if artifact_path.exists() else None,
    }


def _group_by_category(items: Iterable[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        category = str(item.get("category", "uncategorized"))
        grouped.setdefault(category, []).append(dict(item))
    return {category: sorted(values, key=lambda entry: str(entry.get("name") or entry.get("path"))) for category, values in sorted(grouped.items())}


def build_runbook_index(artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> Dict[str, Any]:
    """Build a machine-readable operator runbook index."""

    artifacts = []
    for artifact in ARTIFACTS:
        row = dict(artifact)
        row.update(_artifact_state(artifact_dir, artifact["path"]))
        artifacts.append(row)

    missing_artifacts = [artifact["path"] for artifact in artifacts if not artifact["present"]]
    index: Dict[str, Any] = {
        "schema_version": "militarynntroopprediction.operator_runbook_index.v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_dir": artifact_dir.as_posix(),
        "safe_scope": SAFE_SCOPE,
        "first_steps": list(FIRST_STEPS),
        "commands": COMMANDS,
        "docs": DOCS,
        "artifacts": artifacts,
        "missing_artifacts": missing_artifacts,
        "command_categories": _group_by_category(COMMANDS),
        "doc_categories": _group_by_category(DOCS),
        "artifact_categories": _group_by_category(artifacts),
    }
    index["copyable_handoff"] = (
        f"Runbook index for `{index['artifact_dir']}`: {len(COMMANDS)} safe commands, "
        f"{len(DOCS)} docs, {len(artifacts)} key artifacts, {len(missing_artifacts)} not generated yet. "
        "Start with `make verify` and open `release-bundle-index.html`."
    )
    return index


def _markdown_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> Iterable[str]:
    yield "| " + " | ".join(headers) + " |"
    yield "| " + " | ".join("---" for _ in headers) + " |"
    for row in rows:
        yield "| " + " | ".join(row) + " |"


def _markdown_lines(index: Mapping[str, Any]) -> Iterable[str]:
    yield "# Operator runbook index"
    yield ""
    yield "Use this as the first map for safe local commands, generated artifacts, and project documentation."
    yield ""
    yield f"Generated at: `{index['generated_at']}`"
    yield f"Artifact directory: `{index['artifact_dir']}`"
    yield f"Schema: `{index['schema_version']}`"
    yield ""
    yield "## Copyable handoff"
    yield ""
    yield "```text"
    yield str(index["copyable_handoff"])
    yield "```"
    yield ""
    yield "## First steps"
    yield ""
    for step in index.get("first_steps", []):
        yield f"- {step}"
    yield ""
    yield "## Safe operating scope"
    yield ""
    yield str(index["safe_scope"])
    yield ""
    yield "## Commands"
    yield ""
    command_rows = (
        [f"`{row['command']}`", row["category"], row["purpose"], row["when_to_use"], row["output"]]
        for row in index.get("commands", [])
    )
    yield from _markdown_table(["Command", "Category", "Purpose", "When to use", "Output"], command_rows)
    yield ""
    yield "## Documentation"
    yield ""
    doc_rows = ([f"`{row['path']}`", row["category"], row["purpose"]] for row in index.get("docs", []))
    yield from _markdown_table(["Path", "Category", "Purpose"], doc_rows)
    yield ""
    yield "## Key artifacts"
    yield ""
    artifact_rows = (
        [f"`{row['path']}`", row["category"], row["status"], row["purpose"]]
        for row in index.get("artifacts", [])
    )
    yield from _markdown_table(["Path", "Category", "Status", "Purpose"], artifact_rows)
    missing = index.get("missing_artifacts", [])
    if missing:
        yield ""
        yield "## Artifacts not generated yet"
        yield ""
        for path in missing:
            yield f"- `{path}`"
    yield ""
    yield "## Rollback"
    yield ""
    yield "This workflow is additive. To roll it back, remove the runbook-index Make target, CI report calls, this CLI, its tests, and generated runbook artifacts."


def render_markdown(index: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(index)).rstrip() + "\n"


def write_json(index: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(markdown_text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an operator runbook index for safe local workflows.")
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
        help="Path for Markdown output. Default: <artifact-dir>/operator-runbook-index.md",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=None,
        help="Path for JSON output. Default: <artifact-dir>/operator-runbook-index.json",
    )
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    index = build_runbook_index(args.artifact_dir)
    markdown_path = args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = args.json_path or args.artifact_dir / DEFAULT_JSON_NAME

    if not args.no_markdown:
        write_markdown(render_markdown(index), markdown_path)
        print(f"Wrote operator runbook index Markdown to {markdown_path}")
    if not args.no_json:
        write_json(index, json_path)
        print(f"Wrote operator runbook index JSON to {json_path}")
    if args.no_markdown and args.no_json:
        print("No outputs requested; remove --no-markdown or --no-json to write runbook files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
