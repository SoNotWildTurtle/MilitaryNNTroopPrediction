# Release Bundle Target Handoff Profile

Use this profile when copying `release_bundle_targets` from `run-decision-record.json` into reviewer handoff packets, release-bundle summaries, or downstream validation notes. It is a consumer guide for already-generated repository-maintenance evidence; it does not run predictions, collect live data, create operational tasking, or claim that an analytical estimate is true.

## Purpose

The `release_bundle_targets` field gives downstream consumers a stable list of generated artifact paths, machine-readable review roles, and reviewer-purpose text. Handoff tools should use it to route reviewers to the right files without scraping Markdown tables or inferring artifact meaning from filenames alone.

## Preservation rules

- Preserve every `release_bundle_targets` entry from the source decision record when copying records into a handoff packet.
- Preserve the original `path`, `role`, and `review_purpose` values exactly unless a later schema version explicitly documents a migration.
- Preserve unknown future keys as additive metadata rather than dropping them.
- Do not treat the existence of a target as evidence that the target was generated, reviewed, or validated.
- Continue to require final head SHA evidence, hosted required-check conclusions, review-thread status, target-branch correctness, final diff review, compatibility notes, rollback notes, and stacked dependency order before merge.

## Recommended handoff projection

A handoff summary may present a compact projection with these columns:

| Field | Source | Review use |
| --- | --- | --- |
| `path` | `release_bundle_targets[].path` | Locate the artifact inside diagnostics or release bundles. |
| `role` | `release_bundle_targets[].role` | Route the artifact to the correct reviewer responsibility. |
| `review_purpose` | `release_bundle_targets[].review_purpose` | Explain what the artifact helps validate without inflating it into proof. |
| `presence_status` | Handoff or artifact manifest layer | Record whether the file exists in the current bundle. |
| `integrity_status` | Artifact manifest or checksum layer | Record non-zero size and SHA-256 evidence when available. |

## Validation checklist

Before a handoff consumer marks bundle navigation complete, reviewers should confirm:

1. `run-decision-record.json` contains `release_bundle_targets` and the decision record remains framed as offline repository-maintenance evidence.
2. The release-bundle index or handoff summary links or names each target path that is expected for the current diagnostics bundle.
3. `artifact-manifest.json` confirms generated files with non-zero sizes and hashes when the files are present.
4. `artifact-provenance-ledger.json` labels generated candidate, decision-record, acceptance, manifest, provenance, and bundle artifacts as review evidence rather than live intelligence or operational truth.
5. Missing targets are reported as handoff warnings or merge blockers according to the existing acceptance checklist and hosted workflow rules.
6. Required hosted checks remain the source of validation status; this profile is not a substitute for CI, review threads, branch protection, or final diff review.

## Safe analytical framing

Release bundle targets are navigation metadata only. They help reviewers find generated evidence and understand the intended review purpose, but they do not validate model quality, prove predictions, assign tasks, identify real-world troop movement, or authorize operational use.

## Compatibility and rollback

This profile is additive documentation. Consumers that do not use `release_bundle_targets` can ignore the guide and continue reading existing candidate, decision-record, acceptance checklist, handoff, manifest, provenance, and release-bundle artifacts. Roll back by reverting the documentation and static-test PR; no prediction, ingestion, API, database, or CLI behavior changes are required.
