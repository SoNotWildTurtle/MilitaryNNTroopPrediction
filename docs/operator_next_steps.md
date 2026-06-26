# Operator Next Steps

`operator-next-steps` turns the local diagnostic bundle into a ranked action plan
for maintainers. It is designed for recurring automation, artifact review, and
non-technical handoff notes where the next safe task should be obvious without
reading raw JSON.

The command is offline-only. It reads diagnostic JSON files that are already
created by the project tooling and writes Markdown plus optional JSON. It does
not run model inference, collection, ingestion, network calls, deployment, or
operational workflows.

## Generate a plan

```bash
make ci-report
make operator-next-steps
```

The default output paths are:

- `ci_artifacts/operator-next-steps.md`
- `ci_artifacts/operator-next-steps.json`

You can also call the module directly:

```bash
python -m app.cli.operator_next_steps \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/operator-next-steps.md \
  --json-path ci_artifacts/operator-next-steps.json
```

## Inputs

By default, the command reads:

- `release-health.json` for setup failures and warnings.
- `artifact-manifest.json` for missing expected reviewer artifacts.
- `triage-summary.json` for narrow rerun targets that were already derived from
  health and manifest data.

Custom paths are available with `--health-json`, `--manifest-json`, and
`--triage-json`.

## Output interpretation

The Markdown report includes:

- Current plan status.
- The highest-priority next command to run.
- A ranked table of actions with source, reason, target, and detail.
- Missing expected artifacts, when present.
- The safe project scope for the generated plan.

Use the top-ranked target first, rerun the diagnostic bundle, then refresh the
operator plan. If the status is `ready`, open `release-bundle-index.html`, review
the generated dashboard/API artifacts, and attach the diagnostics bundle to the
handoff or pull request.

## Rollback

This increment is additive. Roll back by removing `app.cli.operator_next_steps`,
its tests, this document, and the `operator-next-steps` Makefile target. Existing
bundle generation, API exports, manifests, and handoff commands continue to work
without this optional report.
