# Changelog

## Unreleased

- Added `docs/merge_readiness_record_template.md` with a copyable final merge-readiness record for target branch, final head SHA, hosted checks, local validation, diagnostics, diff review, blockers, compatibility, rollback, and safe analytical framing.
- Added static regression coverage for the merge-readiness record template so missing hosted validation remains a documented blocker.
- Added `docs/final_merge_evidence_packet.md` with a final head-SHA, hosted-check, diagnostic-artifact, diff-review, blocker, compatibility, rollback, and safe analytical framing checklist for merge decisions.
- Added static regression coverage for the final merge evidence packet so unavailable validation remains documented as a blocker.
- Added `schema_version`, `status_explanation`, `merge_blockers`, `source_artifacts`, and deterministic review-order metadata to `triage_summary` JSON/Markdown output so CI blockers are easier to parse, reproduce, and hand off safely.
- Added `docs/triage_summary_schema.md` to document the triage summary JSON contract, status semantics, compatibility expectations, safe analytical framing, and rollback path.
- Updated CI troubleshooting guidance and regression coverage for machine-readable triage contract fields.
- Exported `schema_version` and top-level `merge_blockers` from `workflow_gate_summary` so the documented JSON contract matches generated artifacts.
- Added `docs/workflow_gate_summary_schema.md` to document the `workflow_gate_summary` JSON contract, consumer guidance, safety limits, compatibility expectations, and rollback path.
- Added static regression coverage so exported workflow-gate fields remain documented for downstream JSON consumers.
- Added `narrow_rerun_targets` and a top-level `narrow_rerun_plan` to `workflow_gate_summary` output so reviewers can reproduce the smallest relevant validation slice before rerunning broader gates.
- Documented the focused workflow-gate rerun workflow and added regression coverage for JSON, Markdown, and default gate metadata.
- Added `evidence_to_collect` metadata to `workflow_gate_summary` JSON/Markdown output so reviewers know which final-head-SHA workflow run URL, job conclusion, and diagnostic artifact evidence to capture before merge.
- Added regression coverage and documentation for the workflow gate evidence capture checklist.
- Wired `workflow_gate_summary` into the Makefile and CI diagnostics bundle so reviewers get Markdown/JSON hosted-gate artifacts in the standard handoff package.
- Added static regression coverage for workflow gate summary task-runner and CI artifact wiring.
- Added `docs/workflow_gate_review_runbook.md` with a deterministic, offline-first merge gate review checklist, blocker triage table, safe analytical scope notes, rollback guidance, and local reproduction commands for required hosted checks.
- Added static regression coverage for the workflow gate review runbook so required gates, final-head-SHA review, safe analytical framing, and narrow local rerun commands stay documented.
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
