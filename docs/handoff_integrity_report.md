# Handoff integrity report

The handoff integrity report is an offline-only diagnostic artifact for checking whether the generated review bundle is internally consistent before a maintainer shares it or treats it as release evidence.

It reads generated JSON files from a local diagnostics directory and emits Markdown plus JSON. It does not run ingestion, prediction, model training, database access, network calls, deployment, or operational tasking.

## Generate the report

Build the normal diagnostics bundle first:

```bash
make ci-report
python -m app.cli.handoff_integrity_report --artifact-dir ci_artifacts
# or
make handoff-integrity
```

The command writes:

- `ci_artifacts/handoff-integrity-report.md` for reviewer handoff.
- `ci_artifacts/handoff-integrity-report.json` for automation and release gates.

Use custom paths when reviewing an isolated bundle:

```bash
python -m app.cli.handoff_integrity_report \
  --artifact-dir ci_artifacts/local-ci \
  --health-json ci_artifacts/local-ci/release-health.json \
  --manifest-json ci_artifacts/local-ci/artifact-manifest.json \
  --reviewer-handoff-json ci_artifacts/local-ci/reviewer-handoff.json \
  --operator-next-steps-json ci_artifacts/local-ci/operator-next-steps.json \
  --uncertainty-json ci_artifacts/local-ci/uncertainty-review-packet.json \
  --markdown-path ci_artifacts/local-ci/handoff-integrity-report.md \
  --json-path ci_artifacts/local-ci/handoff-integrity-report.json
```

## What it checks

The report checks metadata-level consistency across:

1. `release-health.json` for failing or warning health checks.
2. `artifact-manifest.json` for missing expected artifacts.
3. `reviewer-handoff.json` for handoff status alignment.
4. `operator-next-steps.json` for the current ranked safe next action status.
5. `uncertainty-review-packet.json` for cautious analytical framing and uncertainty status.

A `blocked` status means the bundle is missing expected review evidence or contains failing health checks. A `review_warnings` status means the bundle may be usable for review only after a maintainer explicitly accepts or resolves the warning-level finding. A `ready` status means no cross-artifact integrity gaps were detected from the available generated diagnostics.

## Safe scope and rollback

This report is limited to generated diagnostics, synthetic fixtures, hashes, and metadata. It must not be used for targeting, tasking, or operational direction.

Rollback is safe: delete the generated `handoff-integrity-report.md/json` files or rerun `make clean`. The feature does not alter source data, model weights, runtime configuration, databases, or live services.

## Follow-up work

Future increments can wire the JSON status into release gates, dashboard badges, and reviewer checklists so incomplete bundles are easier to catch before publication.
