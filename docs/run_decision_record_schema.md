# Run Decision Record JSON Schema Contract

This guide documents the machine-readable JSON emitted when `python -m app.cli.next_increment_candidates` is called with `--decision-record-path`. Use it when reviewing recurring maintenance runs, writing downstream bundle consumers, or deciding whether a selected additive increment has enough evidence to move from planning into implementation.

The artifact is intentionally offline and non-operational. It is repository-maintenance evidence for candidate selection, validation planning, merge-blocker capture, rollback planning, and uncertainty communication. It does not fetch imagery, connect to OSINT feeds, run detection, run prediction, direct action, or prove that analytical estimates are true.

## Producer

```bash
python -m app.cli.next_increment_candidates \
  --no-markdown \
  --json-path /tmp/next-increment-candidates.json \
  --decision-record-path /tmp/run-decision-record.json
```

Use `--selected-candidate-id candidate-XX` only after inspecting the generated candidate matrix and documenting why the explicit override is safer than the deterministic recommendation.

## Current schema version

`schema_version` is currently `1.0` for the decision-record artifact. Consumers should preserve unknown fields and treat new top-level fields as additive unless release notes explicitly describe an incompatible change.

A consumer that only understands the current minimum contract can read `status`, `selected_candidate`, `required_evidence_before_merge`, `validation_plan`, `merge_blockers`, `compatibility_notes`, `rollback_notes`, and `next_follow_up_candidate` while ignoring future additive fields.

## Top-level fields

| Field | Type | Required | Review purpose |
| --- | --- | --- | --- |
| `generated_at` | string/null | yes | Timestamp inherited from the candidate report for artifact freshness review. |
| `schema_version` | string | yes | Contract version for downstream parsers. |
| `status` | string | yes | `ready_for_implementation` when candidate context exists, otherwise `blocked`. |
| `source_candidate_schema_version` | string/null | yes | Schema version from the source candidate report. |
| `selected_candidate` | object/null | yes | The candidate chosen for the next cohesive increment. |
| `selected_candidate_id_requested` | string/null | yes | Explicit candidate override requested by the caller, if any. |
| `selection_reason` | string | yes | Human-readable reason for deterministic or explicit selection. |
| `alternatives_considered` | array | yes | Non-selected candidate summaries and reason-not-selected notes. |
| `required_evidence_before_merge` | array | yes | Evidence fields reviewers must capture before merging the implementation PR. |
| `validation_plan` | array | yes | Narrow local validation commands to run before broader CI or release gates. |
| `merge_blockers` | array | yes | Required hosted-check, review-thread, final-diff, or inherited blockers to resolve before merge. |
| `safe_scope` | string | yes | Required caveat that the artifact is maintenance evidence, not operational tasking or certainty. |
| `compatibility_notes` | string | yes | Additive compatibility statement for reviewers and consumers. |
| `rollback_notes` | string | yes | Recovery path if the decision artifact or related implementation needs to be reverted. |
| `next_follow_up_candidate` | string | yes | Concrete next increment candidate for the following run. |

## Selected candidate object

`selected_candidate` mirrors one row from the generated candidate matrix:

- `candidate_id`
- `title`
- `focus_area`
- `status`
- `novelty_score`
- `roadmap_matches`
- `recent_overlap`
- `rationale`
- `suggested_artifact`
- `validation_commands`
- `safety_notes`

When `selected_candidate` is `null`, the record is not implementation-ready. Reviewers should inspect `merge_blockers`, `selection_reason`, `CHANGELOG.md`, `goals.md`, open issues, open pull requests, and hosted checks before choosing work manually.

## Required merge evidence

The default `required_evidence_before_merge` entries are:

1. `final_head_sha`
2. `hosted_required_checks`
3. `local_validation_commands`
4. `diff_review_for_deletions_secrets_generated_artifacts_and_unsupported_claims`
5. `compatibility_and_rollback_notes`
6. `safe_analytical_framing_confirmation`
7. `next_follow_up_candidate`

Missing evidence remains a merge blocker. The decision record selects work; it does not prove that a later implementation PR is safe to merge.

## Validation plan

`validation_plan` begins with the selected candidate's narrow validation commands and adds a command that regenerates both candidate JSON and the decision record. Downstream automation may add hosted workflow URLs, artifact paths, or run IDs in separate evidence packets, but should not overwrite the original local validation plan.

## Merge blockers

`merge_blockers` always includes a reminder that hosted required checks, review-thread status, and final diff safety review must be captured before merge. Additional blockers may be inherited from missing changelog or roadmap context.

A green decision record means the run has selected a reviewable candidate. It is not a substitute for hosted checks, branch protection, unresolved review-thread review, final target-branch verification, or PR dependency ordering.

## Compatibility and Rollback

This schema documentation is additive and does not change prediction logic, training behavior, API routes, database schemas, live data ingestion, generated estimates, or CLI output fields. Roll back by reverting the documentation/test PR or removing generated local decision-record artifacts. Do not delete unrelated validation, provenance, handoff, or analytical-safety runbooks.

## Safe analytical framing

Decision-record JSON is reviewer evidence for repository maintenance. It must not be presented as live intelligence, targeting guidance, operational tasking, or proof that a prediction is true.
