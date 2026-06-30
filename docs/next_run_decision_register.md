# Next-run decision register

This register helps recurring automation runs choose one meaningful, mergeable improvement without drifting into duplicated documentation or speculative rewrites. It is intentionally lightweight: each run should update the pull request description or follow-up notes with the selected candidate, not overwrite this guide unless the decision process itself changes.

## Decision sequence

1. **Protect the default branch first.** Inspect the default branch, open pull requests, recent commits, required hosted checks, review threads, branch protection, and prior automation work before starting implementation.
2. **Repair blockers before expansion.** If a hosted check, review thread, merge conflict, schema contract, artifact generator, CLI command, packaging step, or analytical-framing audit is failing or unavailable, select the smallest reproducible repair as the run objective.
3. **Prefer functional unlocks over more process text.** When the repository is healthy, prefer increments that improve CLI ergonomics, generated artifact usefulness, schema validation, setup recovery, user-facing examples, or safe analytical handoff over another standalone guide.
4. **Keep the increment reviewable.** The chosen change must fit in one pull request, include narrow regression coverage, preserve existing workflows, and avoid broad rewrites or repository-destructive operations.
5. **Record the next candidate.** Every PR should leave one concrete next-step candidate so the following run can continue the same product trajectory without guessing.

## Candidate scoring rubric

Use the highest-scoring safe candidate that can be completed and validated in one run.

| Signal | Prefer candidates that... | Avoid candidates that... |
| --- | --- | --- |
| User value | make setup, validation, artifact review, or analytical interpretation easier for a real maintainer | only rename or rearrange existing guidance |
| Validation value | add deterministic unit, CLI, schema, or static regression coverage | depend on live OSINT, live imagery, or unavailable external services |
| Product continuity | build directly on recent merged work and documented goals | duplicate a recent PR or create an isolated process artifact |
| Safety | reinforce uncertainty, provenance, and analytical framing | imply operational certainty, targeting, or live tactical direction |
| Mergeability | preserve public APIs, generated artifact compatibility, and rollback clarity | require large migrations, destructive cleanup, or force pushes |

## Next-run handoff fields

Capture these fields in the PR body, changelog entry, or a follow-up note:

- Selected candidate and why it beat the alternatives.
- Files changed and compatibility impact.
- Exact local validation commands and hosted checks reviewed.
- Any blocker that prevented merge.
- One next concrete candidate for the next automation run.
- Rollback path and safe analytical framing notes.

## When to stop adding new guidance

Do not add another process guide when the existing docs already answer the reviewer question. Instead, improve a runnable command, generated artifact, schema contract, fixture, example, or README path that turns the guidance into executable evidence.

Good next candidates after this register include:

- a CLI command that emits a machine-readable run decision record,
- a diagnostics bundle artifact that includes selected candidate and follow-up fields,
- schema coverage for decision records,
- README navigation that points contributors to the executable decision record once it exists.
