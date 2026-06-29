# Hosted Check Evidence Log

Use this template when a pull request is blocked on hosted validation, when required checks were unavailable earlier in the review, or when final merge evidence needs to be captured without relying on memory. The log is intentionally documentation-only: it does not replace GitHub branch protection, required checks, or the final PR mergeability state.

## Safe analytical scope

This project frames prediction and diagnostic outputs as analytical estimates for lawful defensive review. A green hosted check only means that deterministic setup, packaging, artifact, schema, and documentation gates completed for the final PR head SHA. It does not prove operational accuracy, targeting certainty, live-data validity, or model fitness for real-world decisions.

## Before filling the log

1. Confirm the target branch and final PR head SHA shown on GitHub.
2. Confirm there are no unresolved review threads, stacked PR dependencies, or branch-protection blockers.
3. Capture hosted check evidence from the exact final head SHA, not from an earlier commit.
4. Prefer the narrow rerun target from `workflow_gate_summary`, `triage_summary`, or `docs/ci_troubleshooting.md` before rerunning broad validation.
5. Keep secrets, credentials, live collection details, and raw private datasets out of the log.

## Copyable evidence log

```markdown
# Hosted Check Evidence Log

- PR:
- Target branch:
- Final PR head SHA:
- Merge method expected:
- Evidence captured by:
- Evidence captured at:

## Required hosted checks

| Check | Workflow file | Run URL | Run conclusion | Job name | Job conclusion | Artifact reviewed | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CI | `.github/workflows/ci.yml` |  |  |  |  |  |  |
| Analytical Framing Audit | `.github/workflows/analytical-framing-audit.yml` |  |  |  |  |  |  |
| Handoff Validation Receipt | `.github/workflows/handoff-validation-receipt.yml` |  |  |  |  |  |  |

## Narrow reruns attempted

| Symptom | Narrow command | Result | Evidence path | Follow-up |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## Final diff review

- Accidental deletions checked:
- Secrets checked:
- Generated artifacts excluded or justified:
- Unsupported operational claims checked:
- Backwards compatibility checked:
- Rollback path documented:

## Merge decision

- Ready to merge:
- Blocker if not ready:
- Required next action:
```

## Evidence quality checklist

- Every required check row references the same final PR head SHA.
- Run URLs are from hosted GitHub Actions, not local-only output.
- Job conclusions are explicit and not inferred from partial logs.
- Artifact names or paths are recorded when diagnostics bundles were uploaded.
- Any rerun uses the smallest relevant command first, then escalates to broader validation only when needed.
- The decision distinguishes green deterministic validation from analytical confidence or operational truth.

## When this log blocks merge

Treat the PR as not merge-ready when any required hosted workflow is missing, queued, cancelled, skipped unexpectedly, failing, tied to an outdated SHA, or impossible to inspect. Do not merge based only on local tests when branch protection requires hosted validation.

## Rollback note

This template is additive documentation. If it causes review friction, revert the documentation/test commit and continue using the existing merge-readiness record, workflow-gate summary, and CI troubleshooting runbooks.
