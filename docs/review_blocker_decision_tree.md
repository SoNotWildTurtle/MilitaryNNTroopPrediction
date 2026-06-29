# Review blocker decision tree

Use this decision tree when a pull request, diagnostics bundle, or handoff record is not ready to merge. It complements the workflow gate summary, triage summary, final merge evidence packet, and merge readiness record template by giving reviewers a short recovery path for each blocker class.

This guide is documentation-only. It does not fetch live data, run model inference, perform targeting, bypass branch protection, or replace required hosted checks. It keeps predictive outputs framed as analytical estimates with uncertainty, validation limits, and safe review context.

## Fast path

1. Confirm the pull request target branch and final head SHA.
2. Confirm whether the branch is stacked on another open pull request.
3. Check required hosted workflows on the exact final head SHA.
4. Inspect review threads, requested changes, merge conflicts, and branch protection state.
5. Review the final diff for accidental deletions, secrets, generated artifact churn, unsupported claims, unsafe operational framing, and target-branch mistakes.
6. Open the diagnostics landing page and verify that the manifest, triage summary, workflow gate summary, handoff validation receipt, reviewer handoff, provenance ledger, evidence checklist, and release notes agree.
7. Pick the first matching blocker class below and run the narrowest safe rerun before wider validation.

## Blocker classes

| Blocker class | Symptoms | Narrow recovery action | Merge decision |
| --- | --- | --- | --- |
| `blocked_ci` | A required hosted workflow is failed, cancelled, missing, queued without inspectable validation, stale, or unavailable on the final head SHA. | Fetch the job log or workflow status, reproduce the smallest matching command locally, fix the root cause, then rerun the hosted workflow. | Leave open until the exact final head SHA is green. |
| `blocked_review` | Unresolved review threads, requested changes, merge conflicts, target-branch uncertainty, branch protection blockers, or unsatisfied stacked dependencies remain. | Resolve the specific review item or dependency first; do not hide it behind a broad rewrite. | Leave open until reviewers and branch policy are clear. |
| `blocked_scope` | The final diff includes repository-destructive changes, broad unrelated rewrites, mass deletions, secrets, generated artifact churn, unsupported claims, or unsafe operational framing. | Revert or narrow only the offending change and document compatibility, migration, and rollback notes. | Leave open until the final diff is safe and reviewable. |
| `needs_handoff_update` | Code and checks look acceptable, but README, setup guidance, CLI docs, schema notes, artifact docs, changelog, risk notes, rollback notes, or follow-up work are stale. | Update only the stale handoff material and add static regression coverage when the guidance is important. | Leave open until the handoff accurately matches the final change. |
| `ready_to_merge` | Final head SHA is green, final diff is clean, branch protection is satisfied, review blockers are resolved, stacked dependencies are promoted, and the expected merge method is available. | Record the merge readiness evidence and merge using the expected method and head SHA. | Merge. |

## Narrow rerun map

Use the most specific safe check before running the full bundle:

- Setup or dependency issue: `make doctor`
- Python syntax/import issue: `python -m compileall app tests`
- Static documentation guidance: `python -m unittest discover -s tests -p 'test_*.py'`
- Missing API contract artifact: `make openapi`
- Missing synthetic examples: `make examples`
- Missing static dashboard preview: `make dashboard`
- Missing manifest or hash evidence: `make manifest`
- Missing provenance labels: `make provenance-ledger`
- Missing workflow gate evidence: `make workflow-gate-summary`
- Missing handoff validation evidence: `make handoff-validation-receipt`
- Missing triage summary or narrow rerun targets: `make triage-summary`
- Cross-artifact disagreement: `make ci-report && make validate-handoff`
- Full local pre-PR validation: `make verify`

## Diff safety checklist

Before merge, explicitly confirm:

- No secrets, credentials, tokens, private keys, or personal data were added.
- No broad file removal, branch deletion, history rewrite, force-push assumption, or destructive cleanup was introduced.
- No generated artifacts were committed unless the repository already expects them.
- No predictive output is described as certainty, real-time operational truth, or targeting instruction.
- No synthetic fixture, static preview, mockup, or generated diagnostic is presented as real-world evidence.
- No API, schema, CLI, file path, workflow, or user workflow changed incompatibly without migration and rollback notes.
- The target branch is correct and the PR is based on the intended default branch or approved stack dependency.

## Evidence to record

A complete blocker handoff should include:

- Pull request number, target branch, base SHA, and final head SHA.
- Required hosted workflow names, run URLs, job conclusions, and timestamps.
- Narrow local rerun command, result, and failure excerpt when applicable.
- Diagnostics bundle landing page and the key artifact names reviewed.
- Final diff summary with additions, deletions, changed files, and any generated artifact decision.
- Review thread state, requested changes, merge conflict state, and branch protection status.
- Compatibility impact, rollback path, known limitations, and follow-up work.
- Safe analytical framing confirmation.

## Safe analytical framing

Use neutral review language such as "estimate", "synthetic fixture", "static preview", "diagnostic artifact", "validation limit", "uncertainty", and "review blocker". Avoid language that claims certainty, recommends operational targeting, or treats generated review material as live intelligence.

## Compatibility and rollback

This guide changes no runtime behavior, APIs, schemas, workflows, generated artifact names, data ingestion, model logic, or CLI output. Rollback is a normal documentation/test revert. Existing reviewer workflows can continue using `docs/workflow_gate_review_runbook.md`, `docs/final_merge_evidence_packet.md`, `docs/merge_readiness_record_template.md`, and generated workflow-gate artifacts.
