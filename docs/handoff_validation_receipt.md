# Handoff Validation Receipt

`app.cli.handoff_validation_receipt` creates a deterministic, privacy-safe receipt for generated diagnostic bundles. It is meant for reviewer handoffs, release notes, and automation logs where a manager or analyst needs to confirm what evidence bundle was checked without reopening every artifact first.

The receipt is offline and metadata-only. It reads generated JSON artifacts, records upstream validation gate statuses, hashes manifest path/size/SHA-256 tuples into a stable bundle identity, and lists exact rerun commands. It does not collect OSINT, fetch imagery, query MongoDB, train models, run prediction, or provide operational targeting guidance.

## Generate a receipt

```bash
python -m app.cli.handoff_validation_receipt \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/handoff-validation-receipt.md \
  --json-path ci_artifacts/handoff-validation-receipt.json
```

Expected outputs:

- `handoff-validation-receipt.md` for human review.
- `handoff-validation-receipt.json` for automation, release gates, or handoff archives.

## What the receipt checks

The receipt expects these upstream diagnostics to exist in the bundle or artifact manifest:

- `artifact-manifest.json`
- `artifact-provenance-ledger.json`
- `triage-summary.json`
- `reviewer-handoff.json`
- `uncertainty-review-packet.json`
- `handoff-integrity-report.json`
- `evidence-checklist.json`

It reports:

- A deterministic manifest-entry digest derived from artifact paths, sizes, and SHA-256 values.
- Upstream gate statuses for evidence, handoff integrity, triage, reviewer handoff, and uncertainty review.
- Evidence pass/warn/fail totals.
- Missing required artifacts, manifest missing-expected entries, and manifest scan warnings.
- Exact rerun commands: `make verify`, `make ci-report`, and `python -m app.cli.handoff_validation_receipt --artifact-dir ci_artifacts`.

## Status meanings

- `ready`: required receipt artifacts are present and upstream gates are ready/pass/ok.
- `needs_review`: no hard blocker was detected, but one or more upstream gates or scan results need human review.
- `blocked`: a required receipt artifact is missing, the manifest reports missing expected files, or an upstream validation gate is blocked/failing.

## Safe-scope and privacy notes

Use the receipt as release and handoff metadata only. It helps prove which generated bundle was reviewed and which deterministic commands can reproduce it. It must not be treated as operational certainty, tasking, targeting support, or a substitute for human review of uncertainty and provenance notes.

## Rollback guidance

This workflow is additive. To roll it back, stop generating `handoff-validation-receipt.md/json` and remove the CLI/test/doc files added for the receipt. Existing diagnostic artifacts, API contracts, setup commands, and prediction code do not depend on this receipt.

## Follow-up work

- Add the receipt to hosted CI diagnostics after the artifact bundle order is stable.
- Add a release gate that can require `status == ready` for external handoff archives.
- Include the receipt in the release bundle index once downstream reviewers have confirmed the preferred placement.
