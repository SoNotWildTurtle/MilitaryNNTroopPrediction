# Provenance Validation Matrix Schema

The provenance validation matrix JSON is a deterministic reviewer-handoff contract for the offline `provenance_validation_matrix` CLI. It cross-checks generated diagnostic artifacts so reviewers can confirm which files support bundle integrity, data provenance, evidence completeness, cross-artifact integrity, final validation, reviewer handoff, and uncertainty communication.

This schema is not a live-data validation, not a predictive model quality assessment, and not an operational targeting artifact. It only summarizes generated diagnostics that already exist in the selected artifact directory.

## Producer

```bash
python -m app.cli.provenance_validation_matrix \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/provenance-validation-matrix.md \
  --json-path ci_artifacts/provenance-validation-matrix.json
# or
make provenance-validation-matrix
```

The command is offline and read-only. It does not run OSINT collection, satellite imagery retrieval, model inference, training, database writes, deployment, alerting, or network workflows.

## Top-level fields

- `schema_version` — string contract version for downstream readers. Version `1.0` adds this explicit field without removing existing keys.
- `generated_at` — ISO-8601 timestamp for when the matrix was created.
- `artifact_dir` — artifact directory that was inspected.
- `status` — aggregate status: `ready`, `needs_review`, or `blocked`.
- `source_statuses` — status map for the source diagnostics used by the matrix, including artifact manifest, provenance ledger, evidence checklist, and handoff validation receipt.
- `required_signal_count` — number of required handoff signal rows expected by this contract.
- `ready_signal_count` — number of required rows whose supporting artifact is present and ready.
- `blockers` — merge or handoff blockers inferred from missing required signal artifacts or blocked source diagnostics.
- `warnings` — review-needed findings inferred from warning source diagnostics or rows that need manual review.
- `next_action` — deterministic reviewer recommendation based on blockers and warnings.
- `rows` — ordered list of required validation signal rows.
- `safe_scope` — reminder that the matrix is limited to lawful defensive analytical handoff evidence and does not claim predictive certainty.

## Row fields

Each item in `rows` has these fields:

- `gate` — stable gate identifier, such as `bundle_integrity`, `data_provenance`, `evidence_completeness`, `cross_artifact_integrity`, `final_validation_receipt`, `reviewer_handoff`, or `uncertainty_communication`.
- `artifact` — expected generated file name, such as `artifact-manifest.json` or `uncertainty-review-packet.json`.
- `status` — row status: usually `ready`, `needs_review`, or `missing`.
- `category` — provenance category from the artifact provenance ledger when available.
- `operational_claim` — boolean copied from the provenance ledger to make unsafe operational framing visible during review.
- `sha256` — SHA-256 value from the artifact manifest when the artifact is present.
- `size_bytes` — artifact size from the manifest when present.
- `requirement` — reviewer-readable requirement for the gate.
- `rationale` — provenance rationale from the ledger, or a clear message that no ledger entry was available.

## Compatibility guidance

Consumers should treat `schema_version` as the first compatibility check, then read known keys defensively. Additive keys may appear in future versions. Existing keys should not be removed or renamed without a documented migration note, changelog entry, rollback path, and regression test update.

For this contract, do not remove or rename these required top-level fields: `schema_version`, `generated_at`, `artifact_dir`, `status`, `source_statuses`, `required_signal_count`, `ready_signal_count`, `blockers`, `warnings`, `next_action`, `rows`, and `safe_scope`.

For row entries, do not remove or rename: `gate`, `artifact`, `status`, `category`, `operational_claim`, `sha256`, `size_bytes`, `requirement`, and `rationale`.

## Reviewer workflow

1. Generate or download the diagnostics bundle.
2. Open `release-bundle-index.html` first when available.
3. Confirm `artifact-manifest.json`, `artifact-provenance-ledger.json`, `evidence-checklist.json`, `handoff-integrity-report.json`, `handoff-validation-receipt.json`, `reviewer-handoff.json`, and `uncertainty-review-packet.json` exist.
4. Export `provenance-validation-matrix.json` and `provenance-validation-matrix.md`.
5. Treat `blocked` as a blocker for merge or handoff until the missing source artifact is regenerated and the matrix is re-exported.
6. Treat `needs_review` as a manual review checkpoint. Document accepted limitations and rerun the narrow source generator before relying on the bundle.

## Safe analytical framing

The matrix improves reproducibility, provenance review, and handoff clarity. It does not verify live source truth, infer troop movement certainty, validate targeting decisions, or certify operational readiness. Predictive outputs and generated examples remain analytical estimates or synthetic placeholders unless separately validated with documented provenance and uncertainty.

## Rollback path

If a schema change breaks downstream readers, revert the narrow commit that changed `app/cli/provenance_validation_matrix.py`, this schema document, and the associated tests. Regenerate the diagnostics bundle with `make ci-report`, then rerun `make provenance-validation-matrix` and `python -m unittest tests.test_provenance_validation_matrix`.
