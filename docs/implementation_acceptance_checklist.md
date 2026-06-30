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

The JSON output uses `schema_version: "1.3"` and includes:

- `candidate` — selected candidate ID, title, focus area, status, suggested artifact, and rationale when available.
- `acceptance_gates` — blocking reviewer gates for safe framing, additive compatibility, validation evidence, artifact provenance, uncertainty/risk visibility, and rollback recovery.
- `gate_summary` — machine-readable gate totals, blocking gate counts, nonblocking gate counts, gate IDs, blocking gate IDs, nonblocking gate IDs, and the review decision rule that missing blocking evidence remains a merge blocker.
- `gate_evidence_manifest` — one reviewer-fillable evidence row per acceptance gate with an initial `not_collected` status, empty evidence source list, notes placeholder, and `missing_evidence_blocks_merge` flag for blocking gates.
- `gate_evidence_readiness_summary` — machine-readable counts of ready blocking rows, missing blocking rows, missing blocking gate IDs, accepted ready statuses, and the rule used to decide whether evidence review is merge-ready.
- `focus_gate_hints` — focus-specific evidence hints for setup validation, artifact provenance, uncertainty review, operator handoff, or scenario comparison increments.
- `validation_commands` — candidate-provided commands, or conservative default compile/unit/CI-report commands when candidate context is absent.
- `merge_blockers` — inherited decision-record blockers, or default hosted-check and unresolved-review blockers.
- `handoff_fields_to_capture` — final head SHA, hosted checks, local validation, artifact evidence, diff safety review, compatibility, rollback, safe framing, gate evidence manifest updates, evidence readiness summary, and next follow-up fields.

Consumers should preserve unknown fields so future additive schema keys do not break existing readers.

For a field-by-field consumer contract, see `docs/implementation_acceptance_schema.md`. That schema guide documents top-level keys, candidate fields, gate rows, evidence-manifest readiness rules, compatibility expectations, rollback guidance, and safe analytical framing for downstream bundle readers.

## Gate summary review use

`gate_summary` is intended for dashboards, release-bundle readers, and handoff validators that need to check acceptance-gate shape without parsing Markdown tables. A reviewer can compare `gate_summary.blocking_gates` with the number of gate rows in `acceptance_gates` and require concrete evidence for every ID in `gate_summary.blocking_gate_ids` before merge.

The field is additive. Existing consumers that only read `acceptance_gates`, `merge_blockers`, or `handoff_fields_to_capture` can ignore it safely.

## Gate evidence manifest review use

`gate_evidence_manifest` gives reviewers and future release-bundle validators a stable place to record whether each blocking gate has actual evidence. Generated rows intentionally start with `evidence_status: "not_collected"` and an empty `evidence_sources` list because the CLI cannot prove hosted check, review-thread, artifact, or final-diff evidence by itself.

Before merge, reviewers can copy the generated JSON, update each row with PR links, hosted check names, artifact paths, command output references, or reviewer notes, and keep `missing_evidence_blocks_merge` as the machine-readable reason an unfilled blocking row prevents merge. This keeps green-check language separate from the actual evidence that supports it.

## Gate evidence readiness summary review use

`gate_evidence_readiness_summary` makes the manifest easier for future release gates and handoff validators to consume without scraping Markdown. A blocking row is counted as ready only when `evidence_status` is `collected` or `verified`, `evidence_sources` contains at least one source, and `missing_evidence_blocks_merge` is `false`.

Generated checklists therefore start with `ready_for_merge_evidence_review: false` and every blocking gate listed in `missing_blocking_gate_ids`. Reviewers should treat that as expected template behavior until they have copied the JSON, filled source evidence, and re-exported or stored the completed handoff artifact.

## Reviewer workflow

1. Confirm the selected candidate matches the actual PR scope and does not duplicate recently merged work.
2. Verify every `blocking_if_missing` gate has concrete evidence in the PR body, generated artifacts, or linked CI run.
3. Check `gate_summary.blocking_gate_ids` against the PR evidence list so machine-readable and Markdown views agree.
4. Fill or review `gate_evidence_manifest` rows so each blocking gate has evidence sources before merge.
5. Check `gate_evidence_readiness_summary.missing_blocking_gate_ids` before handoff; any remaining blocking row is still a merge blocker.
6. Check that generated, synthetic, preview, and reviewer-only artifacts are labeled before handoff.
7. Confirm uncertainty notes and limitations are visible before any status-positive language.
8. Reproduce the narrowest validation command first when a hosted or local check fails.
9. Treat unavailable hosted validation, unresolved review threads, unfilled blocking evidence rows, or missing final-head-SHA evidence as merge blockers.

## Compatibility and rollback

This CLI is additive review tooling. It does not change prediction logic, APIs, database schemas, model training, data ingestion, or generated analytical estimates. Roll back by deleting generated checklist artifacts or reverting the CLI/docs/tests PR. Do not remove unrelated handoff, validation, or analytical-safety runbooks.

## Safe analytical framing

Checklist outputs are repository-maintenance evidence only. They are not operational tasking, targeting guidance, live intelligence, or proof that a prediction is true.
