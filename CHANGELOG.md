# Changelog

## Unreleased

- Added evolving workflow concurrency guidance and conservative same-ref concurrency controls for selected GitHub Actions pull-request validation so newer PR runs supersede older duplicate runs while preserving workflow names, required checks, push validation, artifact uploads, rollback guidance, and safe analytical framing.
- Added machine-readable `reviewer_action_summary` counts to `handoff_gap_report_review` JSON/Markdown so reviewer handoff and release gates can count blocking, review, and unknown action priorities without iterating the full action queue or scraping Markdown while preserving offline reviewer-navigation scope.
- Added machine-readable `review_status_summary` counts to `handoff_gap_report_review` JSON/Markdown so reviewers and release-gate automation can count clear, unchecked, blocking, missing, and suspicious handoff targets without scraping Markdown while preserving offline reviewer-navigation scope.
- Added deterministic `reviewer_next_actions[]` guidance to the offline `handoff_gap_report_review` JSON/Markdown output so missing handoff targets, missing gap reports, missing release bundle artifacts, suspicious artifacts, and clear reviews each produce narrow reviewer rerun actions without changing prediction, ingestion, API, database, or live analytical behavior changes.
