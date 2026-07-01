# Handoff Manifest Status Review

Use this guide after generating an implementation acceptance handoff with `--decision-record-json` and after generating `artifact-manifest.json`. It turns the handoff `release_bundle_target_projection` into a deterministic reviewer workflow without treating navigation metadata as validation proof.

## Goal

The handoff projection intentionally starts each release bundle target with:

- `presence_status: not_checked`
- `integrity_status: not_checked`

Those values remain the safe defaults when no artifact manifest is supplied. They prevent a generated handoff from claiming that a file exists, has the expected checksum, or is ready for release before diagnostic artifact evidence has been supplied.

When reviewers provide `--artifact-manifest-json`, the CLI can populate manifest-backed reviewer-navigation statuses while preserving the same safety boundary: the enriched status only says whether a target path appears in `artifact-manifest.json` with size/hash evidence. It does not validate prediction quality, operational accuracy, or real-world movement claims.

## Required inputs

| Input | Purpose | Narrow regeneration command |
| --- | --- | --- |
| `implementation-acceptance-handoff.json` | Contains `release_bundle_target_projection.targets[]` from the selected decision record. | `python -m app.cli.implementation_acceptance_handoff --checklist-json ci_artifacts/implementation-acceptance-checklist.json --decision-record-json ci_artifacts/run-decision-record.json --artifact-manifest-json ci_artifacts/artifact-manifest.json --json-path ci_artifacts/implementation-acceptance-handoff.json --markdown-path ci_artifacts/implementation-acceptance-handoff.md` |
| `artifact-manifest.json` | Contains indexed file paths, sizes, and SHA-256 hashes for generated artifacts. | `python -m app.cli.artifact_manifest --artifact-dir ci_artifacts --json-path ci_artifacts/artifact-manifest.json --markdown-path ci_artifacts/artifact-manifest.md` |
| `artifact-gap-report.json` | Shows missing expected files and suspicious generated artifacts. | `python -m app.cli.artifact_gap_report --artifact-dir ci_artifacts --manifest-path ci_artifacts/artifact-manifest.json --json-path ci_artifacts/artifact-gap-report.json --markdown-path ci_artifacts/artifact-gap-report.md` |

Run the narrow command for the artifact that is stale before rerunning the broader diagnostics bundle.

## Optional manifest enrichment

`implementation_acceptance_handoff` accepts:

```bash
python -m app.cli.implementation_acceptance_handoff \
  --checklist-json ci_artifacts/implementation-acceptance-checklist.json \
  --decision-record-json ci_artifacts/run-decision-record.json \
  --artifact-manifest-json ci_artifacts/artifact-manifest.json \
  --json-path ci_artifacts/implementation-acceptance-handoff.json \
  --markdown-path ci_artifacts/implementation-acceptance-handoff.md
```

The enriched handoff sets `release_bundle_target_projection.artifact_manifest_supplied` to `true` and adds per-target `manifest_evidence` with the reviewed path, `size_bytes`, `sha256`, and a reviewer note when a manifest row is present. Without `--artifact-manifest-json`, outputs remain backwards-compatible and target statuses stay `not_checked`.

## Review order

1. Generate `artifact-manifest.json` first so it reflects the same `ci_artifacts` directory that will be handed off.
2. Generate `implementation-acceptance-handoff.json` with both `--decision-record-json` and `--artifact-manifest-json` when manifest-backed target status is desired.
3. Open `implementation-acceptance-handoff.json` and read `release_bundle_target_projection.targets[]`.
4. For every target with a non-empty `path`, confirm the status came from an exact matching `artifact-manifest.json` `files[]` row.
5. Treat `presence_status=present` as path-presence evidence only when the exact relative path appears in the manifest.
6. Treat `presence_status=missing` as a merge blocker until the artifact is regenerated or the decision record is corrected.
7. Treat `integrity_status=hash_recorded` as size/hash evidence only when the manifest row includes a non-empty `sha256` value and a positive `size_bytes` value.
8. Treat `integrity_status=needs_review` as a blocker when a manifest row is missing, malformed, empty, or contradicted by gap-report evidence.
9. Cross-check `artifact-gap-report.json` before merge so a target that is present in the manifest is not still part of a broader bundle-completeness warning.

## Reviewer status vocabulary

Use these terms in PR comments, merge evidence, or future machine-readable enrichment. Do not invent stronger statuses unless a future schema documents them.

| Field | Status | Meaning |
| --- | --- | --- |
| `presence_status` | `not_checked` | Default generated value when no manifest review input was supplied. |
| `presence_status` | `present` | The exact target path appears in `artifact-manifest.json` `files[]`. |
| `presence_status` | `missing` | The target path is absent from the manifest and needs regeneration or decision-record correction. |
| `integrity_status` | `not_checked` | Default generated value when no manifest review input was supplied. |
| `integrity_status` | `hash_recorded` | Manifest row includes a SHA-256 hash and positive size. |
| `integrity_status` | `needs_review` | Manifest row is missing, malformed, empty, or contradicted by gap-report evidence. |

## Merge blockers

Block merge when any of the following are true:

- A release bundle target path from the handoff projection is absent from `artifact-manifest.json`.
- A manifest row for a target has no SHA-256 hash or a zero-byte size.
- `artifact-gap-report.json` still reports the target as missing or suspicious.
- The handoff projection is being described as prediction validation, operational certainty, targeting support, or real-world movement proof.
- required hosted checks for the final head SHA are unavailable, queued, cancelled, or failing.

## Compatibility and rollback

This guide is additive. It does not change generated predictions, model training, API routes, database schemas, live data ingestion, or analytical estimates. Existing handoff consumers can continue to ignore `release_bundle_target_projection`, `artifact_manifest_supplied`, and `manifest_evidence`.

Rollback by reverting this documentation and the optional manifest-enrichment CLI/tests PR. Do not delete implementation acceptance handoff, artifact manifest, gap-report, or diagnostic bundle tooling.

## Follow-up implementation path

A later functional PR can cross-check `artifact-gap-report.json` directly so future handoffs can warn when an artifact is present in the manifest but still suspicious in the broader bundle-completeness audit. That future change should remain additive, preserve unknown target keys, default to `not_checked` when no manifest is supplied, and keep the safe-scope rule that release bundle target status is reviewer navigation evidence rather than analytical truth.
