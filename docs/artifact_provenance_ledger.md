# Artifact provenance ledger

`app.cli.artifact_provenance_ledger` creates a read-only Markdown and JSON ledger that classifies files already present in a diagnostics bundle. It helps reviewers explain which artifacts are environment evidence, generated review evidence, synthetic fixtures, static previews, API contracts, and bundle-integrity records.

The command does **not** run ingestion, prediction, database, network collection, deployment, or live data workflows. It only reads an existing `artifact-manifest.json` and writes provenance summaries.

## Generate the ledger

```bash
make ci-report
make provenance-ledger ARTIFACT_DIR=ci_artifacts
```

Direct CLI usage:

```bash
python -m app.cli.artifact_provenance_ledger \
  --artifact-dir ci_artifacts \
  --json-path ci_artifacts/artifact-provenance-ledger.json \
  --markdown-path ci_artifacts/artifact-provenance-ledger.md
```

Use `--manifest-path` when reviewing an isolated manifest outside the default artifact directory.

## Review flow

Open `artifact-provenance-ledger.md` after `release-bundle-index.html`, `reviewer-handoff.md`, and `artifact-gap-report.md` when you need to answer:

- Which files are synthetic examples or static previews rather than analytical evidence?
- Which files are environment evidence for reproducibility?
- Which files are release-gate, handoff, CI-triage, or bundle-integrity outputs?
- Whether expected artifacts were missing when the ledger was generated.

The JSON output includes:

- `status`: `ready`, `needs_review`, or `missing_manifest`.
- `category_counts`: counts by provenance class.
- `non_operational_artifacts`: artifacts that are synthetic, preview-only, navigation-only, or summary-only.
- `entries`: per-file category, rationale, size, SHA-256, and description.
- `copyable_summary`: short status line for issue comments or release notes.

## Compatibility and rollback

The ledger is additive. Existing artifact manifests, handoff files, status boards, release notes, and API examples keep their current shapes. To roll back the feature, remove the `make provenance-ledger` target and the CI report calls that generate `artifact-provenance-ledger.md/json`; other diagnostics still work independently.

## Safe scope

Keep provenance classification limited to generated local diagnostics, synthetic examples, documentation artifacts, and review metadata. Do not use the ledger to claim live data validity or operational certainty.
