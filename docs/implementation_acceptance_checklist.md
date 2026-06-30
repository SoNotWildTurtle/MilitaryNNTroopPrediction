# Implementation Acceptance Checklist

Use the offline implementation acceptance checklist when a recurring maintenance run has selected one next-increment candidate and needs a reviewer-ready set of acceptance gates before handoff or merge.

The checklist is intentionally non-operational. It does not fetch imagery, connect to OSINT feeds, run detection, run prediction, or claim that analytical outputs are true. It converts candidate or run-decision context into repository-maintenance evidence for validation, provenance, rollback, and safe analytical framing.

## Generate from a run decision record

```bash
python -m app.cli.next_increment_candidates \
  --no-markdown \
  --json-path /tmp/next-increment-candidates.json \
  --decision-record-path /tmp/run-decision-record.json

python -m app.cli.implementation_acceptance_checklist \
  --decision-record-path /tmp/run-decision-record.json \
  --markdown-path /tmp/implementation-acceptance-checklist.md \
  --json-path /tmp/implementation-acceptance-checklist.json
```

## Generate a blank safe checklist

```bash
python -m app.cli.implementation_acceptance_checklist \
  --markdown-path /tmp/implementation-acceptance-checklist.md \
  --json-path /tmp/implementation-acceptance-checklist.json
```

A blank checklist is useful when candidate context is unavailable, but `status` will be `needs_candidate_context` so reviewers know the selected increment still needs to be tied back to roadmap, changelog, open PR, or CI failure evidence.

## JSON contract

The JSON output uses `schema_version: "1.0"` and includes:

- `candidate` — selected candidate ID, title, focus area, status, suggested artifact, and rationale when available.
- `acceptance_gates` — blocking reviewer gates for safe framing, additive compatibility, validation evidence, artifact provenance, uncertainty/risk visibility, and rollback recovery.
- `focus_gate_hints` — focus-specific evidence hints for setup validation, artifact provenance, uncertainty review, operator handoff, or scenario comparison increments.
- `validation_commands` — candidate-provided commands, or conservative default compile/unit/CI-report commands when candidate context is absent.
- `merge_blockers` — inherited decision-record blockers, or default hosted-check and unresolved-review blockers.
- `handoff_fields_to_capture` — final head SHA, hosted checks, local validation, artifact evidence, diff safety review, compatibility, rollback, safe framing, and next follow-up fields.

Consumers should preserve unknown fields so future additive schema keys do not break existing readers.

## Reviewer workflow

1. Confirm the selected candidate matches the actual PR scope and does not duplicate recently merged work.
2. Verify every `blocking_if_missing` gate has concrete evidence in the PR body, generated artifacts, or linked CI run.
3. Check that generated, synthetic, preview, and reviewer-only artifacts are labeled before handoff.
4. Confirm uncertainty notes and limitations are visible before any status-positive language.
5. Reproduce the narrowest validation command first when a hosted or local check fails.
6. Treat unavailable hosted validation, unresolved review threads, or missing final-head-SHA evidence as merge blockers.

## Compatibility and rollback

This CLI is additive review tooling. It does not change prediction logic, APIs, database schemas, model training, data ingestion, or generated analytical estimates. Roll back by deleting generated checklist artifacts or reverting the CLI/docs/tests PR. Do not remove unrelated handoff, validation, or analytical-safety runbooks.

## Safe analytical framing

Checklist outputs are repository-maintenance evidence only. They are not operational tasking, targeting guidance, live intelligence, or proof that a prediction is true.
