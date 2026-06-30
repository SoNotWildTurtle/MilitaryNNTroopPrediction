# Implementation Acceptance Handoff CI Bundle

This note documents how the standard `ci-diagnostics` bundle now carries the offline implementation acceptance evidence handoff.

## What the bundle writes

`scripts/ci_report.sh` builds the next-increment decision record, converts it into an implementation acceptance checklist, then derives the implementation acceptance handoff from that checklist:

```bash
python -m app.cli.next_increment_candidates \
  --markdown-path ci_artifacts/next-increment-candidates.md \
  --json-path ci_artifacts/next-increment-candidates.json \
  --decision-record-path ci_artifacts/run-decision-record.json

python -m app.cli.implementation_acceptance_checklist \
  --decision-record-path ci_artifacts/run-decision-record.json \
  --markdown-path ci_artifacts/implementation-acceptance-checklist.md \
  --json-path ci_artifacts/implementation-acceptance-checklist.json

python -m app.cli.implementation_acceptance_handoff \
  --checklist-json ci_artifacts/implementation-acceptance-checklist.json \
  --markdown-path ci_artifacts/implementation-acceptance-handoff.md \
  --json-path ci_artifacts/implementation-acceptance-handoff.json
```

The generated handoff is intentionally passive repository-maintenance evidence. It does not collect live data, run detection, run prediction, or assert that an analytical estimate is true.

## Reviewer workflow

1. Open `ci_artifacts/implementation-acceptance-checklist.json` and fill the `gate_evidence_manifest` rows with final-head-SHA evidence, hosted check URLs, artifact paths, diff-review notes, compatibility notes, rollback notes, and safe analytical framing confirmation.
2. Re-run `python -m app.cli.implementation_acceptance_handoff --checklist-json ci_artifacts/implementation-acceptance-checklist.json --markdown-path ci_artifacts/implementation-acceptance-handoff.md --json-path ci_artifacts/implementation-acceptance-handoff.json`.
3. Treat any `merge_blockers` or `missing_blocking_gate_ids` in the handoff JSON as blockers before merging.
4. Rebuild the diagnostic bundle with `bash scripts/ci_report.sh` or `make ci-report` before attaching handoff evidence to a PR.

## Compatibility

This wiring is additive. It preserves the existing checklist CLI, handoff CLI, JSON contracts, release bundle index, artifact manifest, provenance ledger, reviewer handoff, and analytical safety workflows. Existing consumers can ignore the new files safely.

## Rollback

Rollback by reverting the CI-bundle wiring and this document. Do not remove unrelated acceptance-checklist, handoff, reviewer-validation, provenance, or analytical-safety tooling.

## Follow-up work

A later increment can teach `artifact_gap_report` and `artifact_provenance_ledger` to classify the implementation acceptance handoff as an expected reviewer-evidence artifact with a dedicated provenance label.
