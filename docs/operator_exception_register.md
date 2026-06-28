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
make operator-exception-register
```

Default outputs:

- `ci_artifacts/operator-exception-register.md`
- `ci_artifacts/operator-exception-register.json`
- `ci_artifacts/operator-exception-register.txt`

For a terminal-only summary without writing files:

```bash
python -m app.cli.operator_exception_register --artifact-dir ci_artifacts --no-markdown --no-json --no-text
```

Use a separate artifact directory when comparing runs:

```bash
make ci-report ARTIFACT_DIR=ci_artifacts/local-review
make operator-exception-register ARTIFACT_DIR=ci_artifacts/local-review
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
2. Open `release-bundle-index.html` first for the full bundle map.
3. Open `operator-exception-register.md` for the prioritized action queue.
4. Resolve every `BLOCKER` row before merge, release, or handoff signoff.
5. Assign every `WARNING` or `REVIEW` row to an owner or record an accepted
   limitation in the handoff notes.
6. Regenerate the register after repairs so the final bundle reflects the current
   state.

Use `operator-exception-register.txt` when you need a copyable one-line summary
and `operator-exception-register.json` when downstream automation needs stable
fields.

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
- `safe_scope` and `analytical_disclaimer`: reminders that outputs are review
  aids, not operational certainty.

## Task runner and CI integration

The root `Makefile` exposes `make operator-exception-register`, `make help` lists
it with the other diagnostics artifacts, and `make ci-triage` points reviewers to
the generated register when a bundle needs narrow follow-up.

The CI smoke workflow now invokes `python -m app.cli.operator_exception_register`
so import, argument parsing, Markdown, JSON, and text export regressions are caught
before maintainers depend on the artifact. `scripts/ci_report.sh` also includes
the register, its text summary, and its help output in the uploaded diagnostics
bundle.

## Privacy and safety notes

The command reads only local generated artifacts and writes local Markdown, JSON,
and text summaries. It does not call network services, ingest live OSINT, run
models, change predictions, or modify source data. Treat all outputs as review
metadata for analytical estimates, not as operational truth.

## Troubleshooting

If the register reports missing artifacts, regenerate the diagnostics bundle:

```bash
make ci-report
make operator-exception-register
```

If it reports invalid JSON, rerun the narrow CLI that produces the named input
artifact, inspect that file, then rerun the register.

## Rollback

The feature is additive. To roll it back, remove the Makefile target, the CI smoke
step, the `scripts/ci_report.sh` register export lines, this documentation update,
and the wiring regression test. No data, model, API, or prediction behavior depends
on the register.
