# Operator Exception Register

The operator exception register is an offline, privacy-safe review artifact that
consolidates blockers, warnings, missing diagnostics, invalid JSON artifacts, and
status-only review items from the generated handoff bundle.

It is intended for lawful defensive/analytical review workflows where staff need
a single queue of unresolved items before a release, handoff, or manager review.
It does not validate live intelligence, does not claim operational certainty, and
does not provide targeting guidance.

## Generate the register

After generating diagnostics, run:

```bash
python -m app.cli.operator_exception_register --artifact-dir ci_artifacts
```

Default outputs:

- `ci_artifacts/operator-exception-register.md`
- `ci_artifacts/operator-exception-register.json`
- `ci_artifacts/operator-exception-register.txt`

For a terminal-only summary without writing files:

```bash
python -m app.cli.operator_exception_register --artifact-dir ci_artifacts --no-markdown --no-json --no-text
```

## Inputs

The register reads the existing generated diagnostics when present:

- `decision-log.json`
- `handoff-closeout-summary.json`
- `handoff-validation-receipt.json`
- `handoff-readiness-scorecard.json`
- `provenance-validation-matrix.json`
- `evidence-checklist.json`
- `handoff-integrity-report.json`
- `artifact-manifest.json`

Missing or invalid inputs are treated as blocker exceptions so reviewers do not
accidentally sign off on incomplete evidence.

## Review flow

1. Generate the diagnostics bundle with `make ci-report`.
2. Generate the exception register.
3. Resolve every `BLOCKER` row before merge, release, or handoff signoff.
4. Assign every `WARNING` or `REVIEW` row to an owner or record an accepted
   limitation in the handoff notes.
5. Regenerate the register after repairs so the final bundle reflects the current
   state.

## Output contract

The JSON output contains:

- `status`: `ready`, `needs_review`, or `blocked`.
- `counts`: blocker, warning, and review counts.
- `exception_count`: total generated entries.
- `entries`: one row per blocker, warning, missing artifact, invalid artifact, or
  status-only review item.
- `owner_hint`: a deterministic owner suggestion based on safe keywords such as
  provenance, evidence, validation, privacy, uncertainty, and handoff.
- `next_action`: recommended review action for the entry or register.

## Privacy and safety notes

The command reads only local generated artifacts and writes local Markdown, JSON,
and text summaries. It does not call network services, ingest live OSINT, run
models, change predictions, or modify source data. Treat all outputs as review
metadata for analytical estimates, not as operational truth.

## Rollback

The feature is additive. To roll it back, remove
`app/cli/operator_exception_register.py`, `tests/test_operator_exception_register.py`,
and this documentation file. No data, model, API, or prediction behavior depends
on the register.
