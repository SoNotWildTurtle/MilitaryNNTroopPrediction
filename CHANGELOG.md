# Changelog

## Unreleased

- Added the offline `workflow_gate_summary` CLI to export a JSON/Markdown map of required hosted validation gates, local reproduction commands, green-check meaning, merge blockers, and safe analytical scope.
- Added `docs/workflow_gate_summary.md` with usage, reviewer workflow, compatibility notes, and rollback guidance.
- Added deterministic tests for workflow gate naming, missing-workflow blocker behavior, Markdown rendering, JSON/Markdown writing, and required-before-merge metadata.
- Added `docs/reviewer_workflow_status_index.md` to map hosted check names to local reproduction commands, green-check meaning, known limits, and merge-blocker triage.
- Added static regression coverage for the reviewer workflow status index so hosted check guidance stays aligned with existing CI, analytical framing, and handoff receipt workflows.
- Added `.github/workflows/handoff-validation-receipt.yml` to independently smoke-test the final handoff receipt and upload its diagnostic bundle.
- Added `docs/handoff_validation_receipt_workflow.md` with focused reproduction, review guidance, compatibility notes, and rollback steps.
- Added static regression coverage for the handoff validation receipt workflow wiring and documentation.
- Added `.github/workflows/analytical-framing-audit.yml` to smoke-test the analytical framing audit CLI and upload its review artifacts.
- Added `docs/analytical_framing_audit_workflow.md` with focused CI reproduction, review guidance, compatibility notes, and rollback steps.
- Added the offline `analytical_framing_audit` CLI for scanning generated handoff artifacts for overconfident wording, operationally framed phrases, and missing analytical-scope caveats.
- Added deterministic unit tests for ready, warning, informational, custom include-pattern, and writer behavior.
- Added `docs/analytical_framing_audit.md` with safe usage, reviewer workflow, and scope notes.
