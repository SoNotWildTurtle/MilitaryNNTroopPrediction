# Artifact Consumer Validation Profile

This profile helps downstream scripts, dashboards, notebooks, spreadsheets, and reviewer
checklists classify diagnostics bundle issues in a consistent way. It complements
`docs/artifact_consumer_compatibility.md` by separating hard failures, warnings, and
informational notes for artifact consumers.

Use this profile when a tool reads generated JSON or Markdown under `ci_artifacts/`,
`/tmp`, or another isolated review directory and needs to decide whether a handoff is
safe to display, compare, archive, or promote for human review.

## Safe analytical scope

Generated artifacts are evidence about repository setup, reproducibility, schema
shape, provenance labels, uncertainty communication, workflow validation, and reviewer
handoff readiness. They are analytical estimates and review aids only. A complete
bundle, green hosted check, populated field, or passing consumer validation profile is
not proof that external conditions are known.

Consumer tools should display the safe-scope caveat beside any copied estimate,
readiness status, score, recommendation, exception, blocker, or next-step summary.
Synthetic fixtures, static previews, API examples, and generated handoff records must
remain clearly labeled before they are exported into external reports.

## Validation levels

| Level | Consumer action | Typical meaning |
| --- | --- | --- |
| `fail` | Stop merge/readiness promotion and show the blocker first. | A required behavioral guarantee is missing, stale, unsafe, or tied to the wrong commit. |
| `warn` | Continue rendering but display the limitation before summaries. | Optional or environment-specific evidence is missing, incomplete, or not yet generated. |
| `info` | Render as context only. | The artifact is present but contains advisory metadata, next steps, or traceability notes. |

A validation level is about the reliability of the handoff package, not the certainty
of any estimate. Even an all-green profile still requires human analytical review.

## Required fail conditions

Consumer tools should treat the following as hard failures:

- a required hosted check is missing, failed, cancelled, skipped, stale, unavailable,
  queued indefinitely, or not run on the final PR head SHA;
- `workflow-gate-summary.json` is absent when merge readiness is being evaluated;
- `triage-summary.json` reports merge blockers without a visible narrow rerun plan;
- `artifact-manifest.json` is missing, empty, unreadable, or lacks SHA-256 evidence for
  required handoff artifacts;
- `artifact-gap-report.json` marks a required artifact as missing, empty, or
  suspiciously small;
- `artifact-provenance-ledger.json` or `provenance-validation-matrix.json` cannot
  distinguish generated evidence from synthetic fixtures, static previews, or API
  examples;
- a schema contract omits required identity, status, blocker, source artifact,
  provenance, or compatibility fields documented in `docs/*_schema.md`;
- generated Markdown or JSON loses analytical-scope caveats around estimates,
  readiness summaries, uncertainty notes, or recommended actions;
- consumer output hides `merge_blockers`, `blockers`, `warnings`, or
  `required_actions` behind a success summary;
- a final diff review finds accidental deletions, secrets, unsupported claims,
  destructive repository changes, or target-branch mismatch.

## Warning conditions

Consumer tools may continue rendering with a warning when:

- optional artifacts are absent but the manifest and gap report clearly identify them
  as optional;
- optional fields are `null`, missing, or empty while required fields remain present;
- timestamps are present but hosted check freshness has not been independently
  verified;
- Markdown headings, table order, wrapping, or punctuation changed while JSON contract
  behavior remains intact;
- a local reproduction command is available but has not been run in the current
  environment;
- an artifact path differs from the default because the reviewer used an isolated
  output directory;
- a new additive JSON key is unknown to the consumer but can be preserved or ignored
  safely.

Warnings should be displayed before recommendations so a reviewer can understand the
limit before acting on a summary.

## Informational conditions

Treat the following as informational metadata:

- `schema_version` values used as compatibility hints rather than the only validation
  gate;
- generated timestamps retained for traceability;
- optional next-step lists, rollback notes, migration notes, and evidence capture
  reminders;
- artifact file sizes and SHA-256 hashes when they are complete and not flagged by a
  gap report;
- links or commands for `make ci-report`, `make workflow-gate-summary`,
  `make triage-summary`, `make artifact-gap-report`, `make provenance-ledger`, and
  `make provenance-validation-matrix`.

## Suggested consumer decision order

1. Load `artifact-manifest.json` and verify required files have non-zero size and
   SHA-256 evidence.
2. Load `artifact-gap-report.json` and stop on required missing, empty, or
   suspiciously small artifacts.
3. Load `artifact-provenance-ledger.json` and `provenance-validation-matrix.json` to
   confirm generated, synthetic, preview, fixture, and review-handoff labels remain
   separable.
4. Load `workflow-gate-summary.json` and `triage-summary.json` to surface hosted-check
   blockers and narrow rerun guidance.
5. Load human-facing Markdown only after JSON blockers and warnings are visible.
6. Attach safe analytical framing to any exported status, estimate, score, or
   recommendation.
7. Preserve unknown additive fields when writing transformed JSON or tabular exports.

## Output contract for consumer tools

A downstream consumer that implements this profile should expose at least:

- `profile_name`: `artifact-consumer-validation-profile`;
- `profile_version`: a consumer-owned compatibility version;
- `artifact_dir`: the reviewed artifact directory;
- `source_artifacts`: the filenames used for validation;
- `failures`: hard blockers shown before summaries;
- `warnings`: limitations that permit rendering but require reviewer attention;
- `info`: advisory notes and traceability details;
- `safe_scope`: the analytical framing caveat copied into downstream reports;
- `unknown_fields_preserved`: whether additive JSON keys were retained or safely
  ignored;
- `final_head_sha_reviewed`: the commit SHA used for hosted-check validation when
  merge readiness is being evaluated.

Consumers may add fields, but should not remove or hide failures, warnings, source
artifact names, provenance labels, or safe-scope text.

## Rollback and compatibility

This guide is documentation-only. It changes no runtime behavior, public API, model
behavior, generated schema, artifact filename, hosted workflow, required check, or
existing command. Rollback is a normal documentation/test/changelog revert.

Future incompatible consumer-profile changes should include a migration note with the
old field or level, the new field or level, whether the change is additive or
breaking, the narrow command used to regenerate affected artifacts, and the rollback
path.

## Related docs and commands

- `docs/artifact_consumer_compatibility.md` for general downstream parsing rules.
- `docs/workflow_gate_summary_schema.md` for hosted-gate JSON fields.
- `docs/triage_summary_schema.md` for CI triage JSON fields.
- `docs/provenance_validation_matrix_schema.md` for provenance validation rows.
- `docs/review_blocker_decision_tree.md` for reviewer blocker classification.
- `docs/final_merge_evidence_packet.md` for final merge evidence capture.
- `make ci-report` to build a local diagnostics bundle.
- `make workflow-gate-summary` and `make triage-summary` to review hosted-gate and CI
  rerun guidance.
- `make artifact-gap-report`, `make provenance-ledger`, and
  `make provenance-validation-matrix` to review bundle completeness and provenance.
