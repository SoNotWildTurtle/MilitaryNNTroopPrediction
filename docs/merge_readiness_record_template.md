# Merge readiness record template

Use this template when a pull request is ready for final review after local validation, hosted workflow checks, and final diff inspection. It is a copyable record format that complements `docs/final_merge_evidence_packet.md` and keeps the merge decision auditable for future maintainers.

The template is intentionally documentation-only. It does not collect live data, run prediction, perform targeting, bypass branch protection, or replace required hosted checks. If evidence is missing or stale, record the blocker and leave the pull request open.

## Copyable record

```markdown
## Merge readiness record

- Pull request:
- Target branch:
- Base SHA reviewed:
- Final head SHA reviewed:
- Merge method expected: squash | merge | rebase
- Required hosted checks on final head SHA:
  - CI:
  - Analytical Framing Audit:
  - Handoff Validation Receipt:
- Workflow run URLs:
  - CI:
  - Analytical Framing Audit:
  - Handoff Validation Receipt:
- Local validation evidence:
  - Narrowest relevant rerun:
  - Full relevant validation:
  - Artifact/schema validation:
- Diagnostics bundle reviewed:
  - Manifest:
  - Triage summary:
  - Workflow gate summary:
  - Handoff receipt:
  - Reviewer handoff:
- Final diff review:
  - Accidental deletions checked:
  - Secrets checked:
  - Generated artifacts checked:
  - Unsupported claims checked:
  - Unsafe operational framing checked:
  - Target-branch correctness checked:
- Review state:
  - Unresolved review threads:
  - Requested changes:
  - Merge conflicts:
  - Stacked dependencies:
  - Branch protection blockers:
- Compatibility impact:
- Migration notes:
- Rollback path:
- Known limitations:
- Follow-up work:
- Safe analytical framing confirmed:
- Merge decision: ready_to_merge | blocked_ci | blocked_review | blocked_scope | needs_handoff_update
```

## Decision guidance

Use `ready_to_merge` only when the exact final head SHA has green hosted checks, the final diff review is clean, no unresolved review blockers remain, stacked dependencies are satisfied, and the expected merge method can be used without bypassing repository policy.

Use `blocked_ci` when any required hosted workflow is failed, cancelled, stale, missing, queued without inspectable validation, or otherwise unavailable. Do not treat a local-only pass as a replacement for required hosted checks.

Use `blocked_review` when review threads, requested changes, merge conflicts, stacked dependencies, target-branch uncertainty, or branch protection blockers remain unresolved.

Use `blocked_scope` when the final diff includes repository-destructive changes, secrets, generated artifact churn that should not be committed, unsupported claims, operational targeting language, or broad unrelated rewrites.

Use `needs_handoff_update` when code and checks are acceptable but the changelog, README, CLI docs, schema notes, artifact docs, rollback notes, or follow-up work are stale.

## Safe analytical framing

Records should describe predictions as analytical estimates with uncertainty and validation limits. Avoid language that implies certainty, directs operational targeting, or treats synthetic fixtures, static previews, or generated diagnostics as real-world evidence.

## Compatibility and rollback

This template does not change runtime behavior, APIs, schemas, workflows, generated artifact names, model logic, data ingestion, or CLI output. Rollback is a normal documentation revert. Existing review workflows can continue using `docs/final_merge_evidence_packet.md`, `docs/workflow_gate_review_runbook.md`, and generated workflow-gate artifacts.