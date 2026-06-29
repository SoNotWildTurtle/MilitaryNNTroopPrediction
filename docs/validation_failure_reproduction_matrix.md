# Validation Failure Reproduction Matrix

Use this matrix when a hosted workflow, pull request check, or local verification pass fails. The goal is to identify the narrowest safe rerun that preserves blocker visibility before rerunning the full suite or deciding whether a pull request can merge.

This guide is additive to `docs/ci_troubleshooting.md`, `docs/workflow_gate_review_runbook.md`, `docs/review_blocker_decision_tree.md`, and `docs/artifact_consumer_validation_profile.md`. It does not replace required hosted checks, branch protection, final diff review, or reviewer judgment.

## Triage sequence

1. Capture the exact failing workflow name, run URL, job name, step name, conclusion, final head SHA, and timestamp.
2. Classify the failure using the matrix below before editing code or documentation.
3. Reproduce the narrowest relevant slice locally when the failure type allows it.
4. Fix the root cause or brittle assertion without hiding the failure, deleting evidence, or weakening behavioral guarantees.
5. Rerun the focused command first, then the broader `make test`, `make verify`, or hosted workflow required by branch protection.
6. Record what changed, which artifacts were regenerated, which checks passed, which blockers remain, and the rollback path.

## Failure-to-rerun matrix

| Failure class | Evidence to capture | Narrow reproduction | Root-cause focus | Merge blocker? |
| --- | --- | --- | --- | --- |
| Python import, syntax, or packaging failure | Workflow/job URL, Python version, failing module path, traceback, and final head SHA | `python -m compileall app tests` | Missing dependency, incompatible import path, syntax drift, or packaging metadata mismatch | Yes until compile/import passes on the final head SHA |
| Unit or regression test failure | Test file, test method, assertion text, expected/actual values, and related fixture path | `python -m unittest tests.test_name.TestClass.test_method` when known, otherwise `python -m unittest discover -s tests -p 'test_*.py'` | Behavioral regression, brittle prose assertion, path assumption, unstable ordering, or fixture contract drift | Yes until the failing behavior is fixed and the broader suite passes |
| CLI smoke failure | Command, exit code, stdout/stderr, generated paths, and environment variables that affect safe defaults | The exact failing `python -m app.cli.<name> ...` command from the job log | Argument parsing, missing default, output contract mismatch, artifact write failure, or unsafe live-data assumption | Yes when required artifacts or documented commands fail |
| Schema or artifact validation failure | Artifact path, schema version, missing field, unexpected field, validation profile severity, and consumer impact | Re-run the specific exporter that produces the artifact, then inspect JSON/Markdown outputs | Additive field compatibility, schema-version documentation, provenance labels, unknown-field handling, or malformed generated content | Yes for hard failures; warnings need explicit reviewer sign-off |
| Analytical framing audit failure | Flagged phrase, artifact path, line context, and audit rule name | `python -m app.cli.analytical_framing_audit ...` with the same inputs used by CI | Overconfident wording, operational targeting language, missing uncertainty caveat, or unsupported claim | Yes until safe analytical framing is restored |
| Handoff validation receipt failure | Receipt artifact path, missing section, final head SHA, required check names, and handoff expectation | Re-run the documented handoff receipt smoke command or the static doc regression covering the receipt | Missing hosted-check evidence, unclear blocker state, absent rollback note, or incomplete reviewer instructions | Yes until the receipt is complete and current |
| Documentation static regression failure | Doc path, expected phrase or section, assertion intent, and recent related PRs | Run only the failing documentation test when named, then the documentation/static test group | Missing navigation, duplicate/outdated guidance, brittle exact wording, or unsafe phrasing | Yes if required review, compatibility, rollback, or safety guidance is missing |
| Release bundle or manifest failure | Bundle path, missing artifact, checksum mismatch, generated index link, and artifact provenance label | Run the narrow artifact exporter, then `bash scripts/ci_report.sh` or `make ci-report` when bundle composition is implicated | Missing generated file, stale manifest, path mismatch, provenance classification drift, or index link error | Yes until bundle evidence is complete or the missing artifact is documented as non-required |
| Environment or optional dependency warning | Platform, Python/pip version, optional package name, skip flag, and whether the feature is required for CI | `python -m app.cli.doctor --skip-optional --skip-mongo --json` for core CI; rerun optional checks only when the feature is in scope | Optional dependency availability, MongoDB reachability, local path permissions, or live-data configuration | Not by itself unless a required core check or requested feature depends on it |

## Rerun discipline

- Prefer the smallest deterministic command that reproduces the observed failure before broad reruns.
- Preserve strict behavior checks for data contracts, schema versions, provenance labels, analytical caveats, and merge blockers.
- Harden brittle assertions only when they fail on harmless formatting, ordering, or environment differences.
- Do not convert hard failures into warnings unless the validation profile, reviewer notes, compatibility impact, and rollback path all justify it.
- Never treat a missing hosted conclusion, queued workflow, cancelled job, unavailable artifact, unresolved review thread, or stale head SHA as green.

## Evidence packet fields

Record these fields in the PR body, merge-readiness record, hosted check evidence log, or final handoff note:

- `final_head_sha`: commit SHA reviewed before merge.
- `target_branch`: branch that will receive the merge, usually `main`.
- `workflow_name`: required hosted check or local validation group.
- `run_url`: hosted workflow URL when available.
- `job_name` and `step_name`: exact failing or passing job location.
- `conclusion`: success, failure, cancelled, timed_out, skipped, queued, or unavailable.
- `narrow_rerun`: smallest command used to reproduce or verify the fix.
- `broad_rerun`: full suite or hosted workflow used after the focused pass.
- `artifacts_reviewed`: generated JSON, Markdown, HTML, manifest, or diagnostic bundle paths inspected.
- `blocker_status`: blocker resolved, blocker remains, or reviewer sign-off required.
- `compatibility_impact`: additive field, docs-only guidance, CLI behavior, schema contract, or no API impact.
- `rollback_path`: revert PR, restore previous artifact contract, or re-run prior release bundle.

## Safe analytical framing

All predictive outputs, generated examples, fixture records, and reviewer summaries must remain framed as analytical estimates or synthetic placeholders. A passing reproduction matrix does not certify operational certainty, targeting suitability, or live-data accuracy. It only documents whether the repository checks and handoff artifacts are reproducible enough for review.

## Compatibility and rollback

This document is guidance-only and introduces no runtime behavior. If it conflicts with a newer workflow or schema contract, update this matrix additively with the new command, preserve the old entry as a legacy note when useful, and document the change in the changelog. Roll back by reverting the documentation and its static regression test.
