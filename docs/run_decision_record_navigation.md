# Run decision record documentation index

Use this index when selecting, reviewing, or handing off a repository maintenance increment. It keeps the run-decision documentation family discoverable without changing runtime code, data collection, prediction behavior, generated artifacts, or existing workflows.

## Start here

| Need | Document | What to verify |
| --- | --- | --- |
| Pick the next non-duplicative increment | `docs/run_continuity_brief.md` | Roadmap/changelog/decision-register context, blockers, and safe analytical scope are reviewed before choosing work. |
| Capture the selected candidate | `docs/run_decision_record.md` | Selected candidate, alternatives, validation plan, blockers, compatibility, rollback, and next follow-up are recorded. |
| Understand the machine-readable contract | `docs/run_decision_record_schema.md` | Required fields, compatibility expectations, unknown-field tolerance, and safe analytical framing are clear. |
| Review the shortest operational summary | `docs/run_decision_record_quick_reference.md` | Final head SHA, hosted checks, local validation, merge blockers, compatibility, rollback, and next follow-up are easy to find. |
| Prepare a copyable maintainer handoff | `docs/run_decision_record_handoff_examples.md` | Merge-ready, blocked, and documentation-only handoff examples preserve evidence fields and uncertainty language. |

## Review flow

1. Confirm the default branch, open PR stack, hosted checks, review threads, branch target, and recent commits before choosing new work.
2. Use the continuity brief and decision record together to avoid duplicating prior automation work.
3. Prefer the quick reference for human review and the schema guide for machine-readable validation.
4. Use the handoff examples only as reviewer-facing templates; they are not operational analysis or prediction evidence.
5. Leave the PR open when required hosted checks are unavailable, failing, or not attached to the final head SHA.

## Compatibility and rollback

This index is additive documentation. It does not change CLI behavior, API contracts, schemas, model outputs, generated diagnostics, test data, or release artifacts. Roll back by reverting the documentation/test PR; existing workflows continue to use the underlying guides directly.

## Safe analytical framing

Run decision records are repository-maintenance evidence. They help reviewers understand what was selected, why it was selected, how it was validated, and what remains blocked. They must not be presented as real-world certainty, operational targeting, or validation of predictive truth.

## Follow-up candidates

- Add README navigation to this index when a safe README patch path is available.
- Add a generated handoff receipt that can reference this index while preserving final-head-SHA and hosted-check evidence.
- Consider wiring decision-record schema validation into diagnostics bundles after the documentation workflow stabilizes.
