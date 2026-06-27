# Provenance validation matrix

`app.cli.provenance_validation_matrix` builds a deterministic, offline matrix that ties generated diagnostic artifacts to the handoff gates they support. It is intended for reviewers, managers, and operators who need a quick way to confirm that provenance labels, evidence gates, uncertainty notes, integrity checks, reviewer handoff notes, and the final validation receipt are all present before a bundle is handed off.

## Safe scope

The command is read-only and local. It reads generated JSON artifacts from a diagnostics directory and writes Markdown/JSON reports. It does **not** collect OSINT, fetch imagery, connect to MongoDB, run model inference, train models, deploy services, or provide operational targeting guidance. The output frames predictive artifacts as analytical review evidence, not certainty.

## Inputs

By default, the command reads from `ci_artifacts/`:

- `artifact-manifest.json`
- `artifact-provenance-ledger.json`
- `evidence-checklist.json`
- `handoff-integrity-report.json`
- `handoff-validation-receipt.json`
- `reviewer-handoff.json`
- `uncertainty-review-packet.json`

Missing required signals become blockers. Warning or review statuses in the source artifacts become review items.

## Usage

```bash
python -m app.cli.provenance_validation_matrix --artifact-dir ci_artifacts
python -m app.cli.provenance_validation_matrix \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/provenance-validation-matrix.md \
  --json-path ci_artifacts/provenance-validation-matrix.json
```

The Markdown report is the easiest artifact to hand to a human reviewer. The JSON output is stable enough for CI gates, release dashboards, or downstream automation.

## Reviewer workflow

1. Run `make ci-report` or `make verify` to generate the full diagnostics bundle.
2. Open `ci_artifacts/release-bundle-index.html` for navigation.
3. Open `ci_artifacts/provenance-validation-matrix.md` and check the top-level status.
4. If status is `BLOCKED`, regenerate the missing artifact or run the narrow command named by the matrix.
5. If status is `NEEDS_REVIEW`, document whether the warning is accepted or rerun the relevant generator.
6. Attach the matrix, receipt, evidence checklist, and reviewer handoff when sharing a release bundle.

## Rollback

This feature is additive. To roll it back, remove the CLI invocation from CI/report scripts and stop generating `provenance-validation-matrix.md` / `.json`. Existing artifacts, APIs, model code, and user workflows remain unaffected.

## Follow-up work

- Promote the matrix into a stricter release gate once the required signal set stabilizes.
- Add optional CSV output for spreadsheet-based manager review.
- Link the matrix from the release bundle index when artifact navigation is extended.
