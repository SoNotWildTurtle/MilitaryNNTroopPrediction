# Validation Evidence Crosswalk

This guide maps common reviewer questions to the existing local command, hosted workflow, expected artifact, and merge blocker evidence that should be captured before a pull request is merged. It is intentionally additive: it does not replace `docs/validation_failure_reproduction_matrix.md`, `docs/workflow_gate_review_runbook.md`, `docs/hosted_check_evidence_log.md`, or the generated diagnostics bundle.

Use this page when a reviewer or maintainer asks, "What evidence proves this change is safe to merge?" The answer should stay grounded in reproducible checks, final head SHA evidence, and analytical-scope caveats rather than operational certainty.

## Safe scope

- Treat generated predictions and summaries as analytical estimates, not operational targeting instructions or certainty.
- Prefer synthetic fixtures, local smoke checks, schema validation, documentation regression tests, and generated artifacts over live-source assumptions.
- Preserve blocker visibility. A missing hosted conclusion, stale final head SHA, unresolved review thread, merge conflict, unavailable artifact, or branch-protection failure remains a blocker.
- Do not bypass failing workflows, delete evidence, rewrite history, force push, or merge when validation is unavailable.
- Keep compatibility additive by preserving existing files, schemas, commands, and unknown JSON fields unless a narrowly documented migration says otherwise.

## Reviewer question crosswalk

| Reviewer question | Primary local command | Hosted evidence to capture | Artifact or document to inspect | Merge blocker if missing or stale |
| --- | --- | --- | --- | --- |
| Does the repository still install and import with the lightweight dependency set? | `make doctor` | `CI` conclusion for the final head SHA | `ci_artifacts/release-health.json` and `ci_artifacts/release-health.md` | Yes; setup failures can hide all downstream validation. |
| Do tests and static regressions pass for the changed behavior? | `make test` | `CI` conclusion for the final head SHA | Test logs plus changed test files | Yes; do not convert behavior failures into documentation-only warnings. |
| Can the reviewer handoff bundle still be generated? | `make ci-report` | `CI` artifact upload for the final head SHA | `ci_artifacts/release-bundle-index.html` | Yes; missing diagnostics make review and rollback evidence incomplete. |
| Does generated handoff JSON still satisfy its contract? | `make validate-handoff` | `Handoff Validation Receipt` conclusion for the final head SHA | `ci_artifacts/reviewer-handoff-validation.json` | Yes; schema or contract drift must be fixed or documented with migration notes. |
| Are analytical-scope caveats preserved in artifacts? | `python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts --json-path ci_artifacts/analytical-framing-audit.json --markdown-path ci_artifacts/analytical-framing-audit.md` | `Analytical Framing Audit` conclusion for the final head SHA | `ci_artifacts/analytical-framing-audit.md` | Yes; unsupported certainty or operationally framed language blocks merge. |
| Are artifact provenance and suspicious outputs easy to audit? | `make provenance-validation-matrix` and `make artifact-gap-report` | `CI` artifact bundle for the final head SHA | `ci_artifacts/provenance-validation-matrix.md` and `ci_artifacts/artifact-gap-report.md` | Yes when provenance labels, generated/synthetic markers, or expected artifacts are absent. |
| Can downstream consumers parse artifact changes safely? | `make workflow-gate-summary` and `make triage-summary` | Required hosted workflow conclusions for the final head SHA | Schema docs and generated JSON summaries | Yes when required fields disappear, unknown-field tolerance is contradicted, or compatibility notes are missing. |
| Is there enough evidence to hand off or roll back the merge? | `make handoff-validation-receipt` | Required check conclusions plus PR final diff review | `docs/post_merge_verification_receipt.md` and `ci_artifacts/handoff-validation-receipt.md` | Yes when rollback path, target branch, merge commit expectation, or stacked PR status is missing. |

## Evidence packet fields

A merge-ready PR should record these fields in the PR description, hosted check evidence log, or handoff receipt:

- `target_branch`: the branch that will receive the merge, normally `main`.
- `final_head_sha`: the exact PR head SHA that hosted checks validated.
- `required_checks`: `CI`, `Analytical Framing Audit`, and `Handoff Validation Receipt` with conclusions and run URLs.
- `local_validation`: focused commands run locally, including the narrowest relevant rerun for the changed files.
- `artifacts_reviewed`: generated JSON, Markdown, HTML, or text artifacts inspected after `make ci-report` or a narrower artifact command.
- `diff_review`: confirmation that the final diff has no accidental deletions, secrets, unsupported claims, unsafe scope, or target-branch mistakes.
- `compatibility_impact`: whether schemas, CLI commands, generated fields, or docs changed; additive changes should say how old consumers continue to work.
- `rollback_path`: the smallest safe revert path, normally reverting the documentation, CLI, or regression-test commit introduced by the PR.
- `known_limits`: validation or documentation limits that remain after the change.
- `next_step`: the most useful follow-up if the PR is left open or after it merges.

## Narrow rerun examples

Use the smallest command that can reproduce the suspected issue before broad reruns:

```bash
python -m unittest tests.test_validation_evidence_crosswalk_docs
make workflow-gate-summary ARTIFACT_DIR=ci_artifacts/local-ci
make triage-summary ARTIFACT_DIR=ci_artifacts/local-ci
make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts/local-ci
make verify ARTIFACT_DIR=ci_artifacts/local-ci
```

If a narrow rerun passes but a hosted workflow still fails, capture the exact job name, failed step, log excerpt, artifact path, final head SHA, and environment difference before changing code or tests.

## Relationship to existing docs

- Use `docs/validation_failure_reproduction_matrix.md` to classify a failure and choose the narrowest safe rerun.
- Use `docs/hosted_check_evidence_log.md` to copy hosted check conclusions and run URLs into a reviewable record.
- Use `docs/artifact_consumer_compatibility.md` and `docs/artifact_consumer_validation_profile.md` when downstream JSON or Markdown consumers may be affected.
- Use `docs/post_merge_verification_receipt.md` after merging to confirm the resulting commit exists on the intended target branch.

## Rollback

Roll back this guidance by reverting this document, its changelog reference, and its static regression test. That rollback is documentation-only and should not remove existing CLI commands, generated artifact contracts, or prior validation runbooks.
