# Automation run preflight handbook

Use this handbook at the start of a repository-maintenance run before opening a new change. It turns the recurring inspection expectations into a deterministic, documentation-only checklist so maintainers can avoid duplicate work, prioritize existing blockers, and keep every change additive, reviewable, and safe-scoped.

This guide does not fetch live data, run model inference, make predictions, perform targeting, bypass hosted checks, or replace branch protection. Predictive, diagnostic, and generated outputs remain analytical estimates, synthetic fixtures, static previews, or review artifacts with uncertainty and validation limits.

## Preflight order

1. Confirm the default branch is `main` and record the latest default-branch commit SHA.
2. Search for open pull requests, including stacked or automation-created branches, before starting a new increment.
3. Review the most recent merged pull requests and changelog entries so the next change does not duplicate existing workflow-gate, handoff, artifact, or reviewer-navigation features.
4. Inspect open issues, roadmap notes, and recent review comments for active requests or blockers.
5. Confirm required hosted checks for any open PR: `CI`, `Analytical Framing Audit`, and `Handoff Validation Receipt`.
6. Treat missing, queued, stale, unavailable, skipped, cancelled, failed, or wrong-head hosted validation as a merge blocker until the exact final head SHA is green.
7. Fetch exact job status and logs for a failed or unavailable workflow before editing unrelated files.
8. Reproduce the narrowest relevant local target before wider validation.
9. Prefer additive documentation, tests, schema metadata, artifact manifests, CLI ergonomics, setup validation, or handoff improvements over broad rewrites.
10. Review the final diff for accidental deletion, secrets, generated artifacts, unsupported certainty claims, unsafe scope changes, and target-branch correctness before merge.

## Existing evidence map

| Need | Existing first stop | Narrow local target |
| --- | --- | --- |
| Hosted check meaning and local reproduction | `docs/reviewer_workflow_status_index.md` | `make workflow-gate-summary` |
| Failed, missing, queued, or unavailable workflow | `docs/workflow_gate_review_runbook.md` | `make ci-triage` |
| Reviewer routing across docs and artifacts | `docs/reviewer_handoff_navigation.md` | `make validate-handoff` |
| Final merge evidence packet | `docs/final_merge_evidence_packet.md` | `make ci-report` |
| Copyable merge-readiness record | `docs/merge_readiness_record_template.md` | `make validate-handoff` |
| Blocker category decision | `docs/review_blocker_decision_tree.md` | `make triage-summary` |
| Artifact completeness | `docs/artifact_gap_report.md` | `make artifact-gap-report` |
| Provenance and synthetic/live distinction | `docs/artifact_provenance_ledger.md` | `make provenance-ledger` |
| Operator-facing status | `docs/operator_status_board.md` | `make operator-status-board` |
| Analytical wording and scope audit | `docs/analytical_framing_audit_workflow.md` | `python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts` |

## Failure-first triage

When a current PR or required workflow is not green, do not start unrelated feature work. Capture:

- PR number, target branch, base SHA, current head SHA, and whether the branch is current with `main`.
- Workflow name, run URL, job name, conclusion, timestamp, and exact head SHA.
- The precise failing command, assertion, schema field, artifact path, packaging step, CLI output, or compatibility condition.
- The narrowest local reproduction command and result.
- The root-cause fix, not a bypass, broad skip, or loosened behavioral guarantee.
- Rerun evidence proving the same final head SHA now has all required checks green.

If the hosted workflow is only queued or unavailable, leave the PR open and report the unavailable validation as the blocker. Do not merge on local-only evidence when repository policy requires hosted checks.

## Additive increment checklist

Before committing a new increment, confirm:

- The change composes with existing files and preserves current APIs, CLI names, schemas, examples, generated artifact names, and user workflows wherever practical.
- Any removal is narrowly scoped, justified, tested, and documented with migration and rollback notes.
- Tests cover important new behavior or static documentation guarantees.
- README, setup guidance, CLI docs, artifact/schema docs, changelog, risk notes, and follow-up work are updated when the change affects those surfaces.
- Analytical outputs are described as estimates, diagnostics, fixtures, previews, or handoff evidence rather than certainty or operational truth.
- The final PR body records implementation details, validation evidence, risks, compatibility impact, rollback notes, known limitations, dependencies, and follow-up work.

## Merge readiness gate

A PR is ready to merge only when:

- The final head SHA is the same SHA reviewed in the final diff.
- Required hosted checks are green on that final head SHA.
- The PR is mergeable, current with the target branch, and not blocked by review threads or unresolved requested changes.
- Branch protection and repository policy permit the preferred merge method.
- Stacked dependencies are merged in order.
- The final diff contains no secrets, accidental generated artifacts, broad deletions, unsupported claims, or unsafe operational changes.

If any item is false, leave the PR open and report the exact blocker.

## Safe analytical framing

Use language such as `analytical estimate`, `diagnostic artifact`, `synthetic fixture`, `static preview`, `uncertainty`, `validation limit`, `review blocker`, and `safe handoff`. Avoid language that implies certainty, live intelligence, operational targeting advice, or proof of real-world conditions.

## Compatibility and rollback

This handbook changes no runtime behavior, APIs, schemas, generated artifact names, workflows, data ingestion, model logic, or CLI output. Rollback is a normal documentation/test/changelog revert if this preflight checklist becomes outdated or conflicts with repository policy.
