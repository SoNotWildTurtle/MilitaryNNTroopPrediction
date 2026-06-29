# Artifact Consumer Compatibility Guide

This guide helps downstream reviewers, scripts, and handoff consumers read generated
MilitaryNNTroopPrediction artifacts safely as the diagnostics bundle evolves. It is
focused on deterministic local/CI evidence, not live collection, model inference, or
operational targeting.

Use it when you are writing a parser, spreadsheet import, dashboard widget,
notebook, report template, or review checklist that consumes files from
`ci_artifacts/` or another diagnostics directory.

## Safe scope

Generated artifacts are review evidence for setup, reproducibility, provenance,
uncertainty, workflow validation, and handoff readiness. They are analytical support
materials only. A green artifact, populated JSON field, or complete bundle does not
prove real-world conditions, model quality, tactical certainty, or operational truth.

Consumers must keep predictive language framed as analytical estimates and must not
turn these files into targeting instructions, threat certainty, or live operational
automation. Synthetic fixtures, static previews, API examples, and generated review
records should always remain clearly labeled as synthetic, preview, or reviewer
handoff material.

## Consumer rules of thumb

1. Treat `schema_version` as a compatibility hint, not as the only validation gate.
   Older artifacts may predate the field, while newer artifacts may add optional
   fields without changing existing behavior.
2. Preserve unknown fields. Do not fail merely because a JSON object contains a new
   additive key. Store, pass through, or ignore unknown keys unless your consumer has
   an explicit allowlist requirement.
3. Validate required fields by meaning, not by Markdown formatting. Headings, table
   ordering, bullet punctuation, and whitespace may change while the JSON contract
   remains stable.
4. Prefer JSON for automation and Markdown for human review. Markdown summaries are
   intentionally copyable and may prioritize readability over machine stability.
5. Treat missing, empty, stale, queued, skipped, cancelled, unavailable, failed, or
   wrong-head hosted checks as merge blockers until verified on the final PR head
   SHA.
6. Keep generated artifact paths configurable. CI and local runs may use `/tmp`,
   `ci_artifacts/`, or an isolated review directory.
7. Surface uncertainty and validation limits near any copied result. Do not detach a
   status, score, checklist row, or recommendation from its caveats.

## Recommended parsing order

Start with the bundle landing page for human review, then use JSON artifacts for
repeatable automation:

1. `release-bundle-index.html` - first-stop human navigation surface.
2. `artifact-manifest.json` - file inventory with size and SHA-256 evidence.
3. `artifact-gap-report.json` - missing, empty, or suspiciously small outputs.
4. `artifact-provenance-ledger.json` - generated, synthetic, preview, fixture, and
   review-handoff provenance labels.
5. `provenance-validation-matrix.json` - cross-artifact provenance coverage and
   schema-versioned validation rows.
6. `workflow-gate-summary.json` - required hosted gate names, local reproduction
   commands, narrow rerun targets, evidence to collect, and merge blockers.
7. `triage-summary.json` - status explanation, source artifacts, merge blockers,
   and narrow rerun plan for CI failures.
8. `reviewer-handoff.json` plus `reviewer-handoff-validation.json` - copyable
   handoff and validation result.
9. `operator-readiness.json`, `operator-status-board.json`,
   `operator-next-steps.json`, and `operator-exception-register.json` - concise
   non-technical readiness and next-step summaries.
10. `handoff-validation-receipt.json` and `post_merge_verification_receipt.md` -
    final bundle and target-branch verification evidence.

When an artifact is absent, first check the manifest and gap report. If the file was
expected, rerun the narrow target documented by `workflow-gate-summary.json`,
`triage-summary.json`, or `make ci-triage` before rerunning the full suite.

## Compatibility expectations

Additive evolution is the default. New fields, new Markdown sections, new generated
files, and new Makefile targets should not break consumers that follow this guide.
Consumers should fail only when a required behavioral guarantee is missing, such as:

- a required hosted gate is absent from the workflow gate summary;
- a required artifact is missing from the manifest or marked as a gap;
- a schema contract omits required identity, status, source artifact, provenance,
  or blocker fields;
- a generated handoff artifact loses analytical-scope caveats;
- a final-head-SHA check is missing, stale, unavailable, or tied to the wrong commit;
- a parser cannot tell synthetic fixtures or static previews apart from review
  evidence.

Backwards-compatible consumers should treat `null`, missing optional fields, and
empty optional lists as unknown or not-yet-generated rather than as proof that a risk
is absent.

## Minimal JSON consumer checklist

Before trusting a generated JSON artifact in another tool, confirm:

- the file appears in `artifact-manifest.json` with a non-zero size and SHA-256 hash;
- the file is not flagged by `artifact-gap-report.json` as missing, empty, or
  suspiciously small;
- the artifact includes a recognizable status field, schema version, or documented
  top-level contract from `docs/*_schema.md`;
- any `merge_blockers`, `blockers`, `warnings`, or `required_actions` are displayed
  before summaries or recommendations;
- generated timestamps are retained for traceability but not treated as proof of
  hosted check freshness;
- safe-scope text remains attached to analytical summaries;
- unknown keys are preserved or ignored safely.

## Markdown and report consumers

Markdown files are intentionally reviewer-friendly. Consumers that scrape Markdown
should anchor on stable phrases and section purpose rather than brittle row numbers,
heading order, or exact punctuation. Prefer JSON for dashboards, automation, or
spreadsheets, and use Markdown when a person needs the rationale, rollback notes, or
copyable evidence packet.

## Rollback and migration

This guide changes no runtime behavior, public API, model behavior, generated schema,
artifact filename, hosted workflow, or required check. Rollback is a normal
documentation/test/changelog revert.

When a future PR introduces an incompatible schema or artifact change, it should add a
migration note that includes:

- the old and new field names or artifact paths;
- whether the change is additive, deprecated, or breaking;
- the narrow local command to regenerate the affected artifact;
- the rollback path;
- the safe analytical framing that consumers must preserve.

## Related docs and commands

- `docs/reviewer_handoff_navigation.md` for the first-stop reviewer map.
- `docs/workflow_gate_summary_schema.md` for hosted gate JSON fields.
- `docs/triage_summary_schema.md` for CI triage JSON fields.
- `docs/provenance_validation_matrix_schema.md` for provenance matrix fields.
- `docs/artifact_provenance_ledger.md` for provenance labels.
- `docs/artifact_gap_report.md` for missing or suspicious artifact triage.
- `docs/review_blocker_decision_tree.md` for blocker classification.
- `docs/final_merge_evidence_packet.md` for final merge evidence capture.
- `make ci-report` to build a local diagnostics bundle.
- `make manifest` to refresh the artifact manifest.
- `make artifact-gap-report` to audit expected outputs.
- `make provenance-ledger` and `make provenance-validation-matrix` to review
  provenance labeling.
- `make workflow-gate-summary` and `make triage-summary` to inspect hosted-gate and
  CI rerun guidance.
