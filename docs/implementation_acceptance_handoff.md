# Implementation Acceptance Evidence Handoff

`implementation_acceptance_handoff` converts a completed `implementation_acceptance_checklist` JSON file into a reviewer handoff artifact that keeps completed gate evidence rows beside a machine-readable readiness summary.

The command is offline and safe by default. It reads a local checklist JSON file, writes Markdown and JSON outputs, and does not collect live data, call external services, run detection, run prediction, or imply operational certainty.

## Usage

Generate a checklist first:

```bash
python -m app.cli.implementation_acceptance_checklist \
  --decision-record-path /tmp/run-decision-record.json \
  --json-path /tmp/implementation-acceptance-checklist.json
```

Copy or edit the generated JSON so each blocking `gate_evidence_manifest` row has:

- `evidence_status` set to `collected` or `verified`.
- At least one `evidence_sources` entry, such as a PR URL, final-head-SHA check URL, artifact path, command transcript, or reviewer note reference.
- `missing_evidence_blocks_merge` set to `false` only after the reviewer confirms the evidence exists.

Then export the handoff bundle:

```bash
python -m app.cli.implementation_acceptance_handoff \
  --checklist-json /tmp/implementation-acceptance-checklist.json \
  --markdown-path /tmp/implementation-acceptance-handoff.md \
  --json-path /tmp/implementation-acceptance-handoff.json
```

## JSON contract

The JSON output uses `schema_version: "1.0"` and includes:

- `status` — `ready_for_review` when every blocking row is ready, otherwise `blocked_missing_evidence`.
- `candidate` — selected candidate context copied from the source checklist when present.
- `source_gate_summary` — the source checklist gate summary when present.
- `completed_gate_evidence_manifest` — normalized completed evidence rows copied from the source checklist.
- `gate_evidence_readiness_summary` — counts of total rows, blocking rows, ready blocking rows, missing blocking rows, missing blocking gate IDs, accepted ready statuses, and the reviewer decision rule.
- `merge_blockers` — explicit blocker messages for missing manifest rows, missing candidate context, or incomplete blocking evidence.
- `handoff_fields_captured` — the fields this artifact is intended to preserve for downstream reviewers.
- `compatibility_notes` and `rollback_notes` — additive compatibility and recovery guidance.

Consumers should preserve unknown fields so future additive schema keys do not break older handoff readers.

## Readiness rule

A blocking evidence row is ready only when all of these are true:

1. `evidence_status` is `collected` or `verified`.
2. `evidence_sources` contains at least one source.
3. `missing_evidence_blocks_merge` is `false`.

Generated checklist templates therefore start as blocked until a reviewer fills evidence. That is expected and avoids claiming readiness from an empty template.

## Reviewer workflow

1. Generate the implementation acceptance checklist for the selected additive increment.
2. Fill every blocking evidence row with concrete PR, CI, artifact, command, rollback, or reviewer-note evidence.
3. Export the handoff artifact.
4. Confirm `gate_evidence_readiness_summary.ready_for_merge_evidence_review` is `true` before describing the evidence package as ready.
5. Treat any `merge_blockers` entry as a blocker until resolved.
6. Keep the generated handoff JSON beside final-head-SHA evidence so later runs can inspect completed evidence without scraping Markdown.

## Compatibility and rollback

This CLI is additive. It reads an existing checklist JSON file and writes new handoff artifacts; it does not modify prediction logic, training data, APIs, database schemas, generated analytical outputs, or live data workflows.

Rollback is to delete the generated handoff artifact or revert the handoff CLI/docs/tests PR. Do not remove unrelated acceptance-checklist, validation, artifact-provenance, or analytical-safety tooling.
