# Operator artifact guide

`operator_artifact_guide` turns the generated diagnostics bundle into a concise operator menu. It is designed for maintainers, reviewers, managers, and API/dashboard integrators who need to know which artifact to open first and what each file is for.

The guide is safe and local-only. It reads existing JSON metadata from the diagnostics bundle and writes Markdown/JSON outputs; it does not run imagery ingestion, OSINT collection, model prediction, deployment, database writes, or network calls.

## Generate the guide

After creating a diagnostics bundle, run:

```bash
make operator-artifact-guide
```

Or call the CLI directly:

```bash
python -m app.cli.operator_artifact_guide \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/operator-artifact-guide.md \
  --json-path ci_artifacts/operator-artifact-guide.json
```

`scripts/ci_report.sh` also generates the guide automatically, so `make ci-report` and `make verify` include it in the local artifact bundle.

## What it helps with

- Identifies the recommended first artifact to open.
- Summarizes health check counts and indexed artifact totals.
- Lists audience-specific artifact guidance for operators, maintainers, reviewers, integrators, and managers.
- Marks missing expected artifacts so incomplete bundles are easier to fix.
- Exports machine-readable JSON for future dashboards or automation.

## Recommended review flow

1. Open `ci_artifacts/operator-artifact-guide.md`.
2. Follow the recommended first step.
3. If the guide points to `triage-summary.md`, fix the highest-priority failure and rerun `make verify`.
4. If the guide points to `artifact-manifest.md`, regenerate missing outputs and rerun `make ci-report`.
5. If the guide points to `release-bundle-index.html`, use it as the main reviewer landing page.

## Safe scope

Keep this workflow limited to local setup validation, deterministic tests, generated artifacts, synthetic examples, API contracts, and documentation. Do not use this guide as approval to run live collection or prediction workflows.
