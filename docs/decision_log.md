# Analytical Decision Log

`python -m app.cli.decision_log` exports a deterministic offline decision log for generated handoff bundles.

The command reads existing diagnostics in an artifact directory and writes:

- `decision-log.md` for reviewers who need a concise handoff narrative.
- `decision-log.json` for automation, CI evidence, and future release gates.

## Why this exists

The repository already produces readiness, evidence, provenance, integrity, and uncertainty artifacts. The decision log composes those signals into one review surface so a handoff can explain whether it is ready, blocked, or still needs human review.

This is deliberately scoped to local generated artifacts. It does not validate live data, replace analyst judgment, or convert estimates into certainty.

## Usage

```bash
python -m app.cli.decision_log --artifact-dir ci_artifacts
python -m app.cli.decision_log \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/decision-log.md \
  --json-path ci_artifacts/decision-log.json
```

The Makefile exposes the same workflow for operators and CI triage:

```bash
make decision-log ARTIFACT_DIR=ci_artifacts
make ci-report ARTIFACT_DIR=ci_artifacts
```

`make ci-report` now includes the decision log in the uploaded diagnostics bundle after the prerequisite handoff, evidence, validation, provenance, integrity, uncertainty, and manifest artifacts have been generated.

## Inputs reviewed

The exporter checks for these generated files when present:

- `handoff-readiness-scorecard.json`
- `handoff-validation-receipt.json`
- `provenance-validation-matrix.json`
- `evidence-checklist.json`
- `handoff-integrity-report.json`
- `uncertainty-review-packet.json`
- `artifact-manifest.json`

Missing or invalid required inputs are reported as blockers. Warning-like signals are reported as review items. A clean bundle is marked ready.

## Output contract

The JSON output includes:

- `decision`: `ready`, `needs_review`, or `blocked`.
- `next_action`: the recommended safe next step.
- `artifacts`: per-artifact status, blocker count, warning count, and summary.
- `blockers` and `warnings`: copyable review lists.
- `safe_scope` and `analytical_disclaimer`: explicit scope limits for handoff consumers.

## CI and handoff review

The CI workflow smoke-tests the exporter and the diagnostics bundle includes:

- `decision-log-help.txt` for command-line contract visibility.
- `decision-log.md` for human review.
- `decision-log.json` for automation, future gates, and release evidence.

Reviewers should treat a blocked decision as a handoff blocker, a needs-review decision as a prompt for documented analyst review, and a ready decision as supporting evidence rather than operational certainty.

## Rollback

This feature is additive. To roll it back, remove `app/cli/decision_log.py`, `tests/test_decision_log.py`, this document, the `make decision-log` target, and the decision-log calls in `scripts/ci_report.sh` and `.github/workflows/ci.yml`. No existing API, model, data, or artifact schema is changed.
