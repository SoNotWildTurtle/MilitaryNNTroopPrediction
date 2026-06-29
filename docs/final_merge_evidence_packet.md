# Final merge evidence packet

Use this runbook after local validation, reviewer handoff generation, and hosted workflow checks have completed. It gives reviewers a compact, repeatable evidence checklist before merging an additive pull request into the default branch.

The packet is intentionally offline-first and review-focused. It does not collect live OSINT, run prediction against real people, perform operational targeting, bypass branch protection, or assert certainty about analytical estimates.

## When to use it

Use this packet when a pull request appears ready but still needs a final merge decision record. It complements `docs/workflow_gate_review_runbook.md`, `docs/workflow_gate_summary_schema.md`, `docs/triage_summary_schema.md`, and `docs/ci_troubleshooting.md`.

Do not use it to justify merging while required checks are missing, queued, cancelled, failing, stale, or unavailable. Missing validation is a blocker, not a paperwork gap.

## Evidence to collect

Capture these items in the pull request body, a final PR comment, or the release handoff notes:

| Evidence | Required detail | Merge blocker if missing |
| --- | --- | --- |
| Target branch | Default branch name and base SHA reviewed before merge. | Yes; reviewers may be looking at the wrong target. |
| Final head SHA | Exact PR head SHA used for final workflow status checks and diff review. | Yes; stale evidence can hide regressions. |
| Required hosted checks | Names and conclusions for `CI`, `Analytical Framing Audit`, and `Handoff Validation Receipt`. | Yes; unavailable or non-green checks must not be bypassed. |
| Workflow run URLs | URL for each required check on the final head SHA. | Yes; status must be independently inspectable. |
| Diagnostic artifacts | Confirmation that the latest diagnostics bundle includes workflow gate, triage summary, handoff receipt, manifest, and reviewer handoff artifacts. | Yes when the change touches generated artifacts, CI wiring, or handoff contracts. |
| Narrow rerun target | First narrow rerun command from the triage or workflow-gate summary when a failure was fixed. | Yes for CI-fix PRs; root-cause proof is required. |
| Final diff review | Confirmation that the diff was checked for accidental deletions, secrets, generated artifacts, unsafe claims, and target-branch correctness. | Yes. |
| Review blockers | Unresolved review threads, requested changes, merge conflicts, stacked dependencies, or branch protection blockers. | Yes. |
| Compatibility notes | Backwards-compatibility impact, migration notes, and rollback path. | Yes for contract, CLI, artifact, or workflow changes. |
| Safe analytical framing | Confirmation that predictive outputs remain framed as estimates, not targeting instructions or certainty claims. | Yes for docs, examples, UI, API, or artifact text. |

## Merge decision states

| State | Meaning | Action |
| --- | --- | --- |
| `ready_to_merge` | Final head SHA is current, required checks are green, review blockers are resolved, and final diff review is clean. | Merge with the preferred repository method and expected head SHA. |
| `blocked_ci` | A hosted check failed, is queued too long to verify, was cancelled, or never appeared. | Leave the PR open and report the exact check/run blocker. |
| `blocked_review` | Review threads, requested changes, conflicts, or stacked dependencies remain unresolved. | Leave the PR open and resolve the blocker first. |
| `blocked_scope` | The final diff includes destructive changes, unsafe claims, unsupported operational framing, secrets, or broad unrelated rewrites. | Stop and narrow the change before merge. |
| `needs_handoff_update` | Code is sound, but docs, changelog, contract notes, or handoff evidence are stale. | Update the handoff artifacts and rerun focused validation. |

## Copyable final packet

```markdown
## Final merge evidence packet

- Target branch:
- Base SHA reviewed:
- Final PR head SHA:
- Required checks on final head SHA:
  - CI:
  - Analytical Framing Audit:
  - Handoff Validation Receipt:
- Workflow run URLs:
  - CI:
  - Analytical Framing Audit:
  - Handoff Validation Receipt:
- Diagnostics bundle reviewed:
- Narrow rerun target used after any failure:
- Final diff reviewed for accidental deletions/secrets/generated artifacts/unsafe claims:
- Review threads or requested changes remaining:
- Stacked PR dependencies remaining:
- Compatibility impact:
- Rollback path:
- Safe analytical framing confirmed:
- Merge decision: ready_to_merge | blocked_ci | blocked_review | blocked_scope | needs_handoff_update
```

## Compatibility and rollback

This runbook is documentation-only and does not change exported JSON schemas, CLI behavior, workflows, prediction logic, data ingestion, or generated artifact names. If it ever conflicts with repository policy or branch protection, follow the repository policy and update this runbook in a narrow documentation PR.

Rollback is safe: revert the documentation and static regression test that references it. Existing contributors can still use `docs/workflow_gate_review_runbook.md`, `docs/ci_troubleshooting.md`, and generated workflow-gate artifacts for merge review.
