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

## CI bundle integration

`make ci-report` now generates the next-steps Markdown and JSON reports, captures
`operator-next-steps-help.txt`, and indexes those files in `artifact-manifest.*`.
This keeps hosted CI, local release bundles, and PR handoffs aligned with the
same recommended next safe command instead of requiring maintainers to run the
report separately after bundle generation.

The integration is additive and local-only. It does not change predictive output,
model behavior, data ingestion, database access, or live network behavior.

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

This increment is additive. Roll back by removing the `operator_next_steps` calls
from `scripts/ci_report.sh`, the `operator-next-steps.*` and
`operator-next-steps-help.txt` entries from `app.cli.artifact_manifest`, and this
integration note. The standalone CLI, Makefile target, existing bundle
generation, API exports, manifests, and handoff commands continue to work without
this optional bundle wiring.
