# Uncertainty review packet

The uncertainty review packet is a generated, offline-only handoff artifact for reviewers and operators. It summarizes assumptions, uncertainty factors, missing evidence, privacy notes, and the next safe validation commands from the local diagnostics bundle.

The packet is intentionally scoped to generated diagnostics. It does not run ingestion, prediction, model training, database access, networking, collection, or deployment workflows.

## Generate the packet

Build the normal diagnostics bundle first so the packet can read the release-health, manifest, and operator-next-steps JSON files:

```bash
make ci-report
python -m app.cli.uncertainty_review_packet --artifact-dir ci_artifacts
```

The command writes:

- `ci_artifacts/uncertainty-review-packet.md` for reviewers and handoff notes.
- `ci_artifacts/uncertainty-review-packet.json` for automation, release gates, or downstream dashboards.

Use custom paths when reviewing an isolated artifact directory:

```bash
python -m app.cli.uncertainty_review_packet \
  --artifact-dir ci_artifacts/local-ci \
  --operator-plan-json ci_artifacts/local-ci/operator-next-steps.json \
  --health-json ci_artifacts/local-ci/release-health.json \
  --manifest-json ci_artifacts/local-ci/artifact-manifest.json \
  --markdown-path ci_artifacts/local-ci/uncertainty-review-packet.md \
  --json-path ci_artifacts/local-ci/uncertainty-review-packet.json
```

## Review order

1. Open `release-bundle-index.html` to confirm the bundle is complete.
2. Read `reviewer-handoff.md` for the copyable review summary.
3. Read `operator-next-steps.md` for the ranked next safe action.
4. Read `uncertainty-review-packet.md` before treating generated analytics as ready for downstream review.
5. If the packet reports `blocked` or `review_warnings`, run the listed validation commands before sharing the bundle.

## Status meanings

- `ready`: no blocking uncertainty factors were found in the available generated diagnostics.
- `review_warnings`: warning-level health checks or review uncertainty should be resolved or explicitly accepted.
- `blocked`: failed health checks, missing expected artifacts, or action-needed operator plans must be fixed first.
- `needs_review`: the required inputs were unavailable or did not prove readiness.

## Safety and privacy rationale

The packet keeps outputs framed as defensive analytical estimates. It makes missing artifacts, assumptions, and validation gaps explicit so a reviewer does not mistake synthetic fixtures, preview dashboards, or generated readiness text for live operational truth.

Safe rollback is simple: remove the generated `uncertainty-review-packet.*` files from an artifact directory or stop invoking `python -m app.cli.uncertainty_review_packet`. The command does not modify repository state, local configuration, source data, models, databases, or network services.
