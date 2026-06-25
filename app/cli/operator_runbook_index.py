"""Generate an operator-facing runbook index for safe project workflows.

This module is intentionally documentation- and artifact-focused. It does not run
collection, prediction, detection, network, deployment, or live intelligence
workflows. The generated outputs help maintainers find the right local command,
review artifact, or documentation page without reading the entire repository.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "operator-runbook-index.md"
DEFAULT_JSON_NAME = "operator-runbook-index.json"

SAFE_SCOPE = (
    "Local setup, deterministic tests, synthetic examples, API contracts, "
    "generated artifacts, reviewer handoff notes, CI triage, and documentation."
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
        "when_to_use": "Use before heavier optional ML or dashboard dependencies are installed.",
        "output": "Guided setup status and recommended next command.",
    },
    {
        "name": "configure",
        "command": "make configure",
        "category": "onboarding",
        "purpose": "Create a safe local .env from the example template when needed.",
        "when_to_use": "Run before API, doctor, or local diagnostics on a new checkout.",
        "output": ".env with local defaults when one is missing.",
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
        "when_to_use": "Use after changing Python modules, scripts, docs contracts, or generated artifact CLIs.",
        "output": "Compile and unittest results.",
    },
    {
        "name": "verify",
        "command": "make verify",
        "category": "validation",
        "purpose": "Run doctor, tests, diagnostics, and handoff contract validation in one pass.",
        "when_to_use": "Use as the standard pre-PR command.",
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
        "name": "reviewer-handoff",
        "command": "make reviewer-handoff",
        "category": "review",
        "purpose": "Generate copyable reviewer status and missing-artifact guidance.",
        "when_to_use": "Use before summarizing a diagnostics bundle to another maintainer.",
        "output": "reviewer-handoff.md and reviewer-handoff.json.",
    },
    {
        "name": "validate-handoff",
        "command": "make validate-handoff",
        "category": "review",
        "purpose": "Validate reviewer-handoff.json against the stable downstream contract.",
        "when_to_use": "Use when automation or reviewers reject a generated handoff.",
        "output": "Human-readable or JSON validation status.",
    },
    {
        "name": "triage-summary",
        "command": "make triage-summary",
        "category": "triage",
        "purpose": "Generate narrow rerun targets for failing health checks or missing artifacts.",
        "when_to_use": "Use after CI or local verification fails.",
        "output": "triage-summary.md and triage-summary.json.",
    },
    {
        "name": "operator-runbook-index",
        "command": "make runbook-index",
        "category": "orientation",
        "purpose": "Generate this command, document, artifact, and safe-scope index.",
        "when_to_use": "Use when onboarding operators, maintainers, or reviewers.",
        "output": "operator-runbook-index.md and operator-runbook-index.json.",
    },
]

DOCUMENTS: List[Dict[str, str]] = [
    {
        "path": "README.md",
        "purpose": "Project overview, setup path, API routes, and generated artifact workflow.",
        "use_when": "You need the fastest human overview of the repository.",
    },
    {
        "path": "CONTRIBUTING.md",
        "purpose": "Safe contribution scope, PR checklist, and reviewer expectations.",
        "use_when": "You are preparing or reviewing a PR.",
    },
    {
        "path": "docs/common_tasks.md",
        "purpose": "Task-runner workflows and target map.",
        "use_when": "You need the exact make target for setup, validation, artifacts, or cleanup.",
    },
    {
        "path": "docs/ci_troubleshooting.md",
        "purpose": "Hosted CI failure reproduction and local diagnostics guidance.",
        "use_when": "A pull request or hosted workflow fails.",
    },
    {
        "path": "docs/release_bundle_review.md",
        "purpose": "Checklist for reviewing generated diagnostics bundles.",
        "use_when": "You are inspecting ci_artifacts before sharing or merging.",
    },
    {
        "path": "docs/reviewer_handoff_contract.md",
        "purpose": "Stable machine-readable reviewer handoff contract.",
        "use_when": "Downstream automation consumes reviewer-handoff.json.",
    },
]

ARTIFACTS: List[Dict[str, str]] = [
    {
        "path": "release-bundle-index.html",
        "purpose": "Static landing page linking key generated diagnostics.",
        "review_tip": "Open this first when browsing a diagnostics bundle.",
    },
    {
        "path": "reviewer-handoff.md",
        "purpose": "Copyable review summary with status and missing-artifact guidance.",
        "review_tip": "Use this when handing work to another maintainer.",
    },
    {
        "path": "reviewer-handoff-validation.json",
        "purpose": "Machine-readable contract validation result for reviewer handoff output.",
        "review_tip": "Check this when downstream automation rejects a bundle.",
    },
    {
        "path": "triage-summary.md",
        "purpose": "Narrow rerun guidance for failed checks and missing outputs.",
        "review_tip": "Open this after a failed or incomplete verification run.",
    },
    {
        "path": "artifact-manifest.md",
        "purpose": "File sizes, hashes, descriptions, and missing expected outputs.",
        "review_tip": "Use this to confirm the bundle is complete and reproducible.",
    },
    {
        "path": "operator-runbook-index.md",
        "purpose": "Generated command, documentation, artifact, and safe-scope map.",
        "review_tip": "Use this as the first operator orientation page.",
    },
]


def _group_commands(commands: Sequence[Mapping[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for command in commands:
        category = str(command.get("category", "other"))
        grouped.setdefault(category, []).append(dict(command))
    return {category: sorted(items, key=lambda item: item["name"]) for category, items in sorted(grouped.items())}


def build_runbook_index(generated_at: datetime | None = None) -> Dict[str, Any]:
    """Build a deterministic operator runbook index payload."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    grouped = _group_commands(COMMANDS)
    first_steps = [
        "make help",
        "make install-core",
        "make configure",
        "make verify",
        "open ci_artifacts/release-bundle-index.html",
    ]
    return {
        "generated_at": generated_at.isoformat(),
        "safe_scope": SAFE_SCOPE,
        "first_steps": first_steps,
        "commands": COMMANDS,
        "commands_by_category": grouped,
        "documents": DOCUMENTS,
        "artifacts": ARTIFACTS,
        "counts": {
            "commands": len(COMMANDS),
            "categories": len(grouped),
            "documents": len(DOCUMENTS),
            "artifacts": len(ARTIFACTS),
        },
    }


def _markdown_table(rows: Sequence[Mapping[str, str]], columns: Sequence[str]) -> Iterable[str]:
    yield "| " + " | ".join(columns) + " |"
    yield "| " + " | ".join("---" for _ in columns) + " |"
    for row in rows:
        values = [str(row.get(column, "")).replace("|", "\\|") for column in columns]
        yield "| " + " | ".join(values) + " |"


def render_markdown(index: Mapping[str, Any]) -> str:
    """Render a human-readable operator runbook index."""

    lines: List[str] = [
        "# Operator Runbook Index",
        "",
        f"Generated: `{index['generated_at']}`",
        "",
        "## Safe scope",
        "",
        str(index["safe_scope"]),
        "",
        "## First safe path",
        "",
    ]
    lines.extend(f"{number}. `{step}`" for number, step in enumerate(index["first_steps"], start=1))
    lines.extend(["", "## Command map", ""])

    grouped = index["commands_by_category"]
    for category in sorted(grouped):
        lines.extend([f"### {category.title()}", ""])
        lines.extend(
            _markdown_table(
                grouped[category],
                ["name", "command", "purpose", "when_to_use", "output"],
            )
        )
        lines.append("")

    lines.extend(["## Documentation map", ""])
    lines.extend(_markdown_table(index["documents"], ["path", "purpose", "use_when"]))
    lines.extend(["", "## Artifact review map", ""])
    lines.extend(_markdown_table(index["artifacts"], ["path", "purpose", "review_tip"]))
    lines.extend(["", "## Counts", ""])
    for key, value in index["counts"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(index: Mapping[str, Any], markdown_path: Path, json_path: Path | None) -> None:
    """Write Markdown and optional JSON runbook index outputs."""

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(index), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an operator runbook index for safe local workflows.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help=f"diagnostic artifact directory; default: {DEFAULT_ARTIFACT_DIR}",
    )
    parser.add_argument("--markdown-path", type=Path, default=None, help="runbook Markdown output path")
    parser.add_argument("--json-path", type=Path, default=None, help="runbook JSON output path")
    parser.add_argument("--no-json", action="store_true", help="only write Markdown output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_dir = args.artifact_dir
    markdown_path = args.markdown_path or artifact_dir / DEFAULT_MARKDOWN_NAME
    json_path = None if args.no_json else (args.json_path or artifact_dir / DEFAULT_JSON_NAME)

    index = build_runbook_index()
    write_outputs(index, markdown_path, json_path)
    print(f"Wrote operator runbook index Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote operator runbook index JSON to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
