# Reviewer handoff navigation

Use this map when a pull request has multiple generated artifacts, workflow-specific runbooks, or documentation-only review aids. It is a quick routing layer for maintainers who need to decide which file to open first, what evidence to collect, and which local command to rerun without duplicating existing review guides.

This guide is documentation-only. It does not fetch live data, run model inference, perform targeting, bypass hosted checks, or replace branch protection. Predictive and diagnostic outputs remain analytical estimates, synthetic fixtures, or review artifacts with uncertainty and validation limits.

## Start here

1. Confirm the pull request number, target branch, base SHA, and final head SHA.
2. Check open or stacked pull requests before reviewing a new change.
3. Confirm `CI`, `Analytical Framing Audit`, and `Handoff Validation Receipt` are present on the final head SHA.
4. Open the first matching document in the routing table below.
5. Record the narrowest rerun command before broader validation.
6. Treat missing, queued, unavailable, stale, or failed hosted validation as a merge blocker until resolved.

## Routing table

| Situation | Open first | Why | Narrow command |
| --- | --- | --- | --- |
| You need to understand what each hosted check proves. | `docs/reviewer_workflow_status_index.md` | Maps `CI`, `Analytical Framing Audit`, and `Handoff Validation Receipt` to local reproduction commands and validation limits. | `make verify` |
| A hosted workflow is failed, missing, stale, queued, or unavailable. | `docs/workflow_gate_review_runbook.md` | Gives a focused gate review checklist and rerun order for required hosted checks. | `make workflow-gate-summary` |
| A workflow-gate artifact consumer needs field names or blocker semantics. | `docs/workflow_gate_summary_schema.md` | Documents the workflow-gate JSON contract, schema version, merge blockers, and rerun metadata. | `make workflow-gate-summary` |
| A triage summary consumer needs status semantics or JSON contract details. | `docs/triage_summary_schema.md` | Documents triage `schema_version`, `status_explanation`, `merge_blockers`, and review-order fields. | `make triage-summary` |
| The final merge record needs a copyable evidence template. | `docs/merge_readiness_record_template.md` | Provides a final-head-SHA record for hosted checks, review state, compatibility, rollback, and limitations. | `make validate-handoff` |
| A reviewer needs to collect the final merge evidence packet. | `docs/final_merge_evidence_packet.md` | Lists the final diff, hosted run, diagnostic artifact, review, compatibility, and rollback evidence to record. | `make ci-report` |
| A PR is blocked and the reason is unclear. | `docs/review_blocker_decision_tree.md` | Routes `blocked_ci`, `blocked_review`, `blocked_scope`, `needs_handoff_update`, and `ready_to_merge` decisions. | `make ci-triage` |
| Handoff receipt evidence is missing or outdated. | `docs/handoff_validation_receipt_workflow.md` | Explains how to regenerate and review the focused handoff validation receipt workflow. | `make handoff-validation-receipt` |
| Analytical wording or overconfident framing is the concern. | `docs/analytical_framing_audit_workflow.md` | Explains focused reproduction for the analytical framing audit workflow and generated audit artifacts. | `python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts` |
| Generated artifacts need provenance or synthetic/live distinction. | `docs/artifact_provenance_ledger.md` | Separates static previews, synthetic fixtures, generated diagnostics, API contracts, and review evidence. | `make provenance-ledger` |
| A diagnostics bundle might be incomplete or suspiciously small. | `docs/artifact_gap_report.md` | Audits missing, empty, or suspicious expected outputs before handoff. | `make artifact-gap-report` |
| A non-technical status summary is needed. | `docs/operator_status_board.md` | Produces a quick status line, severity, evidence table, and next command for handoff. | `make operator-status-board` |

## Evidence sequence

For most PRs, collect evidence in this order:

1. Pull request number, target branch, base SHA, and final head SHA.
2. Hosted workflow names, run URLs, job conclusions, and timestamps for the exact final head SHA.
3. Review threads, requested changes, merge conflicts, stacked dependencies, and branch protection state.
4. Final diff summary with changed files, additions, deletions, generated artifact decisions, and secret-scan notes.
5. Diagnostic bundle landing page plus manifest, provenance ledger, gap report, triage summary, workflow gate summary, handoff validation receipt, evidence checklist, and release notes.
6. Narrow local rerun command and result when hosted validation fails or is unavailable.
7. Compatibility impact, rollback path, known limitations, and follow-up work.
8. Safe analytical framing confirmation.

## Safe analytical framing

Use review language such as `estimate`, `diagnostic artifact`, `synthetic fixture`, `static preview`, `uncertainty`, `validation limit`, `review blocker`, and `safe handoff`. Do not describe generated outputs as certainty, live intelligence, operational targeting advice, or proof of real-world conditions.

## Compatibility and rollback

This guide changes no runtime behavior, APIs, schemas, generated artifact names, workflows, data ingestion, model logic, or CLI output. Rollback is a normal documentation/test/README/changelog revert if this routing map becomes outdated or conflicts with repository policy.
