# Run decision record handoff examples

Use these examples when a maintainer needs a copyable, review-ready way to summarize a selected repository maintenance increment. This guide is additive navigation only: it does not collect data, run analysis workflows, alter generated artifacts, or replace `docs/run_decision_record.md`, `docs/run_decision_record_schema.md`, or `docs/run_decision_record_quick_reference.md`.

## Minimal merge-ready handoff

```text
Selected candidate: <cohesive additive increment>
Final head SHA: <sha reviewed before merge>
Required hosted checks: CI, Analytical Framing Audit, Handoff Validation Receipt
Local validation: <narrow tests first>, then `python -m unittest discover -s tests -p 'test_*.py'`
Merge blockers: none after hosted checks passed on the final head SHA
Compatibility impact: additive; no runtime, API, CLI, schema, ingestion, model, or generated-output contract changes
Rollback: revert this PR; no migration required
Safe analytical framing: repository-maintenance evidence only, not real-world certainty
Next follow-up: <smallest next cohesive increment>
```

## Blocked handoff

```text
Selected candidate: <candidate name>
Current blocker: <failed or unavailable required check, unresolved review thread, branch-stack issue, or missing validation evidence>
Narrow reproduction: <smallest local command or exact hosted job log reviewed>
Root cause: <precise assertion, packaging, artifact, CLI, schema, compatibility, or documentation point>
Repair plan: fix the implementation or brittle assertion without bypassing checks
Merge status: leave PR open until required checks pass on the final head SHA and review blockers are resolved
Rollback: no merge performed; branch can be closed after a superseding PR if needed
Safe analytical framing: reviewer evidence only; do not imply certainty from incomplete validation
```

## Documentation-only increment handoff

```text
Scope: documentation and static regression coverage only
Runtime impact: none
Validation evidence: static tests verify discoverability, rollback language, merge-blocker language, compatibility notes, and safe analytical-scope language
Compatibility: backwards compatible with existing workflows and generated artifacts
Rollback: revert the documentation/test PR; existing CLIs and runtime behavior remain unchanged
Known limitation: does not enforce schema contracts at runtime or in CI unless separately wired
```

## Reviewer checklist

Before merging, confirm that:

- The PR is based on the intended target branch and any stacked dependency has already merged.
- The final diff has no accidental deletions, generated artifacts, secrets, unsupported claims, or unsafe language.
- Hosted checks are available and successful on the final head SHA.
- The PR body records required evidence, validation performed, compatibility impact, rollback notes, known limitations, dependencies, and follow-up work.
- Any uncertainty is framed as reviewer evidence rather than certainty.

## Follow-up candidates

- Add README navigation to `docs/run_decision_record_quick_reference.md` when the patch path is available.
- Wire decision-record schema validation into diagnostics bundles after the guide and examples stabilize.
- Add a generated handoff receipt that imports these examples as reviewer-facing templates while preserving safe analytical framing.
