# Handoff Gap Report Review

`handoff_gap_report_review` is an offline reviewer helper that cross-checks implementation acceptance handoff release bundle targets against artifact gap-report evidence.

It is intentionally narrow: it does not run prediction, collect live data, inspect live imagery, validate model quality, identify real-world troop movement, or authorize operational use. The output is reviewer-navigation evidence only.

## Inputs

| Input | Purpose | Narrow regeneration command |
| --- | --- | --- |
| `implementation-acceptance-handoff.json` | Provides `release_bundle_target_projection.targets[]` paths, roles, presence status, and integrity status. | `python -m app.cli.implementation_acceptance_handoff --checklist-json ci_artifacts/implementation-acceptance-checklist.json --decision-record-json ci_artifacts/run-decision-record.json --artifact-manifest-json ci_artifacts/artifact-manifest.json --json-path ci_artifacts/implementation-acceptance-handoff.json --markdown-path ci_artifacts/implementation-acceptance-handoff.md` |
| `artifact-gap-report.json` | Provides missing and suspicious generated-artifact evidence for the same diagnostics directory. | `python -m app.cli.artifact_gap_report --artifact-dir ci_artifacts --manifest-path ci_artifacts/artifact-manifest.json --json-path ci_artifacts/artifact-gap-report.json --markdown-path ci_artifacts/artifact-gap-report.md` |

## Usage

```bash
python -m app.cli.handoff_gap_report_review \
  --handoff-json ci_artifacts/implementation-acceptance-handoff.json \
  --artifact-gap-report-json ci_artifacts/artifact-gap-report.json \
  --json-path ci_artifacts/handoff-gap-report-review.json \
  --markdown-path ci_artifacts/handoff-gap-report-review.md
```

Use strict mode when wiring the review into a release gate:

```bash
python -m app.cli.handoff_gap_report_review \
  --handoff-json ci_artifacts/implementation-acceptance-handoff.json \
  --artifact-gap-report-json ci_artifacts/artifact-gap-report.json \
  --no-markdown \
  --no-json \
  --strict
```

Strict mode exits non-zero if a handoff target appears in missing or suspicious artifact-gap evidence, if no handoff targets are available, or if no parseable gap report is supplied.

## Status vocabulary

| Field | Meaning | Merge handling |
| --- | --- | --- |
| `gap_clear` | Target path was not listed as missing or suspicious in the supplied artifact-gap-report evidence. | Review alongside manifest evidence before merge. |
| `missing_in_gap_report` | Target path appears in missing generated-artifact evidence. | Treat as a blocker until the artifact is regenerated or the decision record is corrected. |
| `suspicious_in_gap_report` | Target path appears in suspicious generated-artifact evidence. | Treat as a blocker until a reviewer confirms the artifact is expected and safe. |
| `not_checked` | No parseable artifact-gap-report JSON was supplied. | Treat as unavailable validation, not a pass. |

## Review order

1. Generate the artifact manifest and artifact gap report from the same diagnostics directory.
2. Generate the implementation acceptance handoff from the same decision record and manifest evidence.
3. Run `handoff_gap_report_review` with both JSON inputs.
4. Open `handoff-gap-report-review.json` and inspect `reviewed_targets[]`.
5. Treat any `gap_blocks_merge=true` target as a blocker until regeneration, correction, or explicit reviewer disposition.
6. Cross-check `presence_status`, `integrity_status`, and `gap_status`; a target should not be considered ready when manifest evidence is present but the gap report still flags it as missing or suspicious.

## JSON contract

Top-level fields:

- `schema_version`: review schema version.
- `artifact_gap_report_supplied`: whether a parseable gap report was supplied.
- `target_count`: number of handoff release bundle target paths reviewed.
- `reviewed_targets[]`: per-target `path`, `role`, `presence_status`, `integrity_status`, `gap_status`, `gap_blocks_merge`, and `review_note`.
- `gap_summary`: counts for missing paths, suspicious paths, and blocking reviewed targets.
- `merge_blockers`: exact blocker strings for release-gate handoff.
- `safe_scope`, `compatibility_notes`, and `rollback_notes`: reviewer guardrails that must remain visible.

## Compatibility

This is additive. Existing implementation acceptance handoff, artifact manifest, artifact gap report, diagnostics bundle, and decision-record workflows remain usable without this CLI. Consumers can ignore the new handoff gap-review artifacts until they opt in.

## Rollback

Rollback by reverting this documentation, the `handoff_gap_report_review` CLI, and its tests. Do not delete unrelated implementation acceptance, manifest, gap-report, diagnostics bundle, or analytical-safety tooling.

## Safe analytical framing

The review is offline artifact-consistency evidence only. It does not establish that an estimate is correct, does not reduce uncertainty by itself, and must not be used as operational targeting guidance or real-world movement proof.
