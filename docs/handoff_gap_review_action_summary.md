# Handoff Gap Review Action Summary

This guide explains how reviewers should consume the `reviewer_next_actions[]` queue emitted by `handoff_gap_report_review` without scraping Markdown tables or treating maintenance evidence as operational certainty.

The workflow is intentionally offline and repository-maintenance scoped. It reads generated handoff artifacts, gap-report evidence, and action metadata only. It does not collect live data, run model inference, validate predictions, identify real-world movement, or authorize operational use.

## When to use this guide

Use this guide when a PR includes `ci_artifacts/handoff-gap-report-review.json` or `ci_artifacts/handoff-gap-report-review.md` and a reviewer needs to decide the next narrow validation step.

Start with this file after checking:

1. the PR final head SHA;
2. hosted check conclusions for CI, analytical framing, and handoff validation;
3. the diagnostics bundle landing page;
4. `artifact-gap-report.json` and `implementation-acceptance-handoff.json` generated from the same artifact directory.

## Action priority contract

| Priority | Meaning | Merge handling |
| --- | --- | --- |
| `blocking` | A release-bundle target, input artifact, or parseable report is missing, suspicious, or unavailable. | Do not merge until the narrow rerun succeeds or a reviewer records a justified disposition. |
| `review` | No gap-review blocker was detected, but generated evidence still needs attachment and cross-checking. | Continue final diff review, manifest review, hosted check review, and safe-scope review before merge. |
| Unknown future priority | A future producer emitted a priority this guide does not recognize. | Treat as unavailable validation until the producer documentation and tests are reviewed. |

## Reviewer sequence

1. Open `handoff-gap-report-review.json` first and inspect `status`, `review_status_summary`, `reviewer_action_summary`, `merge_blockers`, and `reviewer_next_actions[]`.
2. If `reviewer_action_summary.has_blocking_actions` is true, use `reviewer_action_summary.first_blocking_action` to identify the first blocker and then copy the matching action's `narrow_rerun` command into the PR evidence packet.
3. If any action has `priority=blocking`, run the narrow command before broad validation.
4. If every action is `priority=review`, attach the JSON and Markdown outputs to the evidence packet and cross-check the manifest-backed `presence_status` and `integrity_status` fields before merge.
5. If an action priority is unknown, mark the PR blocked until the schema documentation, tests, and generated artifacts explain the new priority.
6. Record the final decision in the merge-readiness evidence packet with the final head SHA and hosted check results.

## Machine-readable checks

Downstream automation should avoid Markdown scraping. Prefer these JSON fields:

- `review_status_summary.merge_blocker_count` for top-level blockers;
- `review_status_summary.blocking_target_count` for target-specific blockers;
- `reviewer_action_summary.action_count` for queue cardinality;
- `reviewer_action_summary.priority_counts.blocking` and `reviewer_action_summary.priority_counts.review` for direct action totals;
- `reviewer_action_summary.unknown_priorities` for forward-compatibility blockers;
- `reviewer_action_summary.first_blocking_action` for the first action reviewers should disposition;
- `reviewer_next_actions[].priority` for queue triage;
- `reviewer_next_actions[].narrow_rerun` for smallest safe reproduction commands;
- `safe_scope` for analytical-framing guardrails.

A merge gate should treat any non-zero blocker count, any blocking action, missing `reviewer_next_actions[]`, missing `reviewer_action_summary`, or an unknown priority as unavailable validation rather than as a pass.

## Narrow rerun examples

Regenerate the release bundle target projection:

```bash
python -m app.cli.implementation_acceptance_handoff \
  --checklist-json ci_artifacts/implementation-acceptance-checklist.json \
  --decision-record-json ci_artifacts/run-decision-record.json \
  --artifact-manifest-json ci_artifacts/artifact-manifest.json \
  --json-path ci_artifacts/implementation-acceptance-handoff.json \
  --markdown-path ci_artifacts/implementation-acceptance-handoff.md
```

Regenerate the artifact gap report from the same directory:

```bash
python -m app.cli.artifact_gap_report \
  --artifact-dir ci_artifacts \
  --manifest-path ci_artifacts/artifact-manifest.json \
  --json-path ci_artifacts/artifact-gap-report.json \
  --markdown-path ci_artifacts/artifact-gap-report.md
```

Re-run the gap-review strict check after regeneration:

```bash
python -m app.cli.handoff_gap_report_review \
  --handoff-json ci_artifacts/implementation-acceptance-handoff.json \
  --artifact-gap-report-json ci_artifacts/artifact-gap-report.json \
  --json-path ci_artifacts/handoff-gap-report-review.json \
  --markdown-path ci_artifacts/handoff-gap-report-review.md \
  --strict
```

## Compatibility and rollback

This guide is additive documentation. It adds `reviewer_action_summary` to the generated review JSON/Markdown while preserving `reviewer_next_actions[]` and all existing fields. It does not change prediction APIs, ingestion behavior, database schemas, model behavior, or live analytical workflows. Existing consumers can continue reading `handoff-gap-report-review.json` directly and can ignore the new summary block until they are ready to use it.

Rollback by reverting the CLI, guide, changelog, and tests from the summary-count PR. Do not delete unrelated handoff, artifact manifest, gap report, diagnostics, or analytical-safety tooling.

## Safe analytical framing

This action summary is offline review-navigation evidence only. It does not prove a prediction, reduce real-world uncertainty by itself, validate a model, or provide operational targeting guidance.
