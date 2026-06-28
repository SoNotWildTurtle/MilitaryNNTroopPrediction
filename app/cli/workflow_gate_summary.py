"""Summarize deterministic workflow gates for reviewer handoff.

This offline helper turns the repository's hosted validation expectations into a
copyable JSON/Markdown receipt. It does not call GitHub, run model inference,
query databases, collect OSINT, or make operational claims; it only documents
which safe review gates should be green before a pull request is merged.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

DEFAULT_ARTIFACT_DIR = Path("ci_artifacts")
DEFAULT_MARKDOWN_NAME = "workflow-gate-summary.md"
DEFAULT_JSON_NAME = "workflow-gate-summary.json"

SAFE_SCOPE = (
    "Offline review aid for lawful defensive analysis workflows. It summarizes "
    "deterministic validation gates, local rerun commands, and merge-blocker "
    "meaning; it is not operational targeting guidance, live intelligence, or a "
    "claim that analytical estimates are certain."
)


@dataclass(frozen=True)
class WorkflowGate:
    """A hosted workflow gate and its local reproduction path."""

    name: str
    workflow_path: str
    required_before_merge: bool
    local_reproduction: str
    green_means: str
    green_does_not_mean: str
    blocker_when: str
    evidence_to_collect: str
    narrow_rerun_targets: Sequence[str]


DEFAULT_GATES = (
    WorkflowGate(
        name="CI",
        workflow_path=".github/workflows/ci.yml",
        required_before_merge=True,
        local_reproduction="make verify ARTIFACT_DIR=ci_artifacts/local-review",
        green_means="Core setup, artifact generation, handoff validation, and unit discovery compose successfully.",
        green_does_not_mean="Model quality, live data availability, external services, or predictive truth were validated.",
        blocker_when="The run is queued, missing, cancelled, failing, or tied to a different head SHA.",
        evidence_to_collect=(
            "Record the final PR head SHA, the CI workflow run URL, the Smoke tests job conclusion, "
            "and the uploaded ci-diagnostics artifact name or ID."
        ),
        narrow_rerun_targets=(
            "python -m compileall app tests",
            "python -m app.cli.doctor --skip-optional --skip-mongo --json",
            "make ci-report ARTIFACT_DIR=ci_artifacts/local-review",
            "python -m unittest discover tests",
        ),
    ),
    WorkflowGate(
        name="Analytical Framing Audit",
        workflow_path=".github/workflows/analytical-framing-audit.yml",
        required_before_merge=True,
        local_reproduction=(
            "python -m unittest tests.test_analytical_framing_audit && "
            "python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts"
        ),
        green_means="Generated handoff language keeps analytical-scope caveats and avoids audited overconfident wording.",
        green_does_not_mean="Every possible unsafe phrase was detected or analytical conclusions are correct.",
        blocker_when="The audit is unavailable, failing, or reports unresolved severe framing findings.",
        evidence_to_collect=(
            "Record the framing-audit workflow run URL, Safe-scope wording audit job conclusion, "
            "and analytical-framing-audit artifact availability for the final head SHA."
        ),
        narrow_rerun_targets=(
            "python -m unittest tests.test_analytical_framing_audit",
            "python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts/local-review",
        ),
    ),
    WorkflowGate(
        name="Handoff Validation Receipt",
        workflow_path=".github/workflows/handoff-validation-receipt.yml",
        required_before_merge=True,
        local_reproduction="make ci-report ARTIFACT_DIR=ci_artifacts && make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts",
        green_means="A deterministic diagnostics bundle and final validation receipt can be produced offline.",
        green_does_not_mean="Reviewer judgment, policy review, or predictive certainty can be skipped.",
        blocker_when="The receipt artifact is missing, empty, unavailable, queued, or generated from stale inputs.",
        evidence_to_collect=(
            "Record the receipt workflow run URL, Final handoff receipt check job conclusion, "
            "and handoff-validation-receipt artifact availability for the final head SHA."
        ),
        narrow_rerun_targets=(
            "make ci-report ARTIFACT_DIR=ci_artifacts/local-review",
            "make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts/local-review",
            "make validate-handoff ARTIFACT_DIR=ci_artifacts/local-review",
        ),
    ),
)


def _path_status(root: Path, relative_path: str) -> str:
    return "present" if (root / relative_path).is_file() else "missing"


def build_workflow_gate_summary(
    repo_root: Path = Path("."),
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    generated_at: datetime | None = None,
    gates: Sequence[WorkflowGate] = DEFAULT_GATES,
) -> Dict[str, Any]:
    """Build an offline summary of workflow gates and local reproduction commands."""

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0)
    gate_entries = []
    missing_required = []
    rerun_plan = []
    for gate in gates:
        entry = asdict(gate)
        entry["narrow_rerun_targets"] = list(gate.narrow_rerun_targets)
        entry["workflow_file_status"] = _path_status(repo_root, gate.workflow_path)
        entry["merge_blocker"] = gate.required_before_merge and entry["workflow_file_status"] != "present"
        if entry["merge_blocker"]:
            missing_required.append(gate.workflow_path)
        rerun_plan.extend(
            {
                "gate": gate.name,
                "command": command,
                "purpose": "Reproduce a focused slice before rerunning the broader hosted or local gate.",
            }
            for command in gate.narrow_rerun_targets
        )
        gate_entries.append(entry)

    status = "blocked" if missing_required else "ready_for_review"
    next_action = (
        "Restore missing required workflow files before relying on hosted merge gates."
        if missing_required
        else "Confirm each hosted check is green for the final PR head SHA, then review the diff before merge."
    )
    return {
        "generated_at": generated_at.isoformat(),
        "status": status,
        "next_action": next_action,
        "artifact_dir": artifact_dir.as_posix(),
        "safe_scope": SAFE_SCOPE,
        "required_gate_count": sum(1 for gate in gates if gate.required_before_merge),
        "missing_required_workflows": missing_required,
        "gates": gate_entries,
        "narrow_rerun_plan": rerun_plan,
        "review_order": [
            "Check all hosted gates are complete and green on the final head SHA.",
            "Record the run URL, job conclusion, and uploaded artifact evidence for each required gate.",
            "Fetch exact failing job logs before changing code when any gate fails.",
            "Reproduce the narrow failing command locally before rerunning the full bundle.",
            "Inspect final diff for deletions, secrets, unsafe claims, generated artifacts, and wrong target branch.",
            "Merge only when required validation is available, current, green, and policy permits it.",
        ],
    }


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_lines(summary: Mapping[str, Any]) -> Iterable[str]:
    yield "# Workflow Gate Summary"
    yield ""
    yield "A deterministic offline map of hosted validation gates, local rerun commands, and merge-blocker meaning."
    yield ""
    yield f"Generated: `{summary['generated_at']}`"
    yield f"Status: **{str(summary['status']).upper()}**"
    yield f"Next action: {summary['next_action']}"
    yield ""
    yield "## Safe analytical scope"
    yield ""
    yield str(summary["safe_scope"])
    yield ""
    yield "## Required workflow gates"
    yield ""
    yield "| Gate | Workflow file | File status | Local reproduction | Evidence to collect | Narrow rerun targets | What green means | What green does not mean |"
    yield "| --- | --- | --- | --- | --- | --- | --- | --- |"
    for gate in summary["gates"]:
        rerun_targets = "<br>".join(f"`{target}`" for target in gate["narrow_rerun_targets"])
        yield (
            f"| `{_escape_table(gate['name'])}` | `{_escape_table(gate['workflow_path'])}` | "
            f"{_escape_table(gate['workflow_file_status'])} | `{_escape_table(gate['local_reproduction'])}` | "
            f"{_escape_table(gate['evidence_to_collect'])} | "
            f"{_escape_table(rerun_targets)} | "
            f"{_escape_table(gate['green_means'])} | {_escape_table(gate['green_does_not_mean'])} |"
        )
    yield ""
    yield "## Merge blockers"
    yield ""
    if summary.get("missing_required_workflows"):
        for path in summary["missing_required_workflows"]:
            yield f"- Missing required workflow file: `{path}`"
    else:
        yield "- No required workflow files are missing from this offline checkout."
    for gate in summary["gates"]:
        yield f"- `{gate['name']}` blocks merge when: {gate['blocker_when']}"
    yield ""
    yield "## Evidence capture checklist"
    yield ""
    for gate in summary["gates"]:
        yield f"- `{gate['name']}`: {gate['evidence_to_collect']}"
    yield ""
    yield "## Narrow rerun plan"
    yield ""
    yield "Use the smallest relevant target first when a hosted job fails, then rerun the broader gate after the root cause is fixed."
    yield ""
    for item in summary["narrow_rerun_plan"]:
        yield f"- `{item['gate']}`: `{item['command']}` — {item['purpose']}"
    yield ""
    yield "## Review order"
    yield ""
    for index, item in enumerate(summary["review_order"], start=1):
        yield f"{index}. {item}"


def render_markdown(summary: Mapping[str, Any]) -> str:
    return "\n".join(_markdown_lines(summary)).rstrip() + "\n"


def write_outputs(summary: Mapping[str, Any], markdown_path: Path | None, json_path: Path | None) -> None:
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export an offline summary of required workflow validation gates.")
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repository root to inspect. Default: current directory.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR, help=f"Output directory default: {DEFAULT_ARTIFACT_DIR}")
    parser.add_argument("--markdown-path", type=Path, default=None, help="Markdown output path.")
    parser.add_argument("--json-path", type=Path, default=None, help="JSON output path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown output.")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_workflow_gate_summary(repo_root=args.repo_root, artifact_dir=args.artifact_dir)
    markdown_path = None if args.no_markdown else (args.markdown_path or args.artifact_dir / DEFAULT_MARKDOWN_NAME)
    json_path = None if args.no_json else (args.json_path or args.artifact_dir / DEFAULT_JSON_NAME)
    write_outputs(summary, markdown_path, json_path)
    if markdown_path is not None:
        print(f"Wrote workflow gate summary Markdown to {markdown_path}")
    if json_path is not None:
        print(f"Wrote workflow gate summary JSON to {json_path}")
    if markdown_path is None and json_path is None:
        print("No outputs requested; remove --no-markdown or --no-json to write summary files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
