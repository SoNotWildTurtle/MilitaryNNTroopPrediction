# Release Health Reports

`python -m app.cli.release_health` creates a compact, read-only readiness report from the same checks used by the setup doctor. It is designed for maintainers, first-time users, and CI artifacts.

The command does not run detection, prediction, ingestion, drone feeds, Sentinel downloads, or database writes. It only checks local setup status and writes report files.

## Default usage

```bash
python -m app.cli.release_health
```

By default, this writes:

- `ci_artifacts/release_health.md` for a human-readable summary.
- `ci_artifacts/release_health.json` for automation and future tooling.

The default checks are CI-safe: optional ML/dashboard/GIS imports and MongoDB socket checks are skipped unless requested.

## Useful options

```bash
python -m app.cli.release_health --no-json
python -m app.cli.release_health --markdown-path release_health.md --json-path release_health.json
python -m app.cli.release_health --check-optional --check-mongo
```

## Dashboard usage

The Rich dashboard includes a `Generate release health report` action so non-technical users can create the same report without remembering the full command.

## CI artifacts

`scripts/ci_report.sh` now includes release health Markdown and JSON output in the `ci-diagnostics` artifact bundle. This gives failed CI runs a quick triage file that is easier to read than raw logs.

## Interpreting results

- Failures should block a release or first run until fixed.
- Warnings usually mean optional capabilities are missing or intentionally disabled.
- OK checks indicate the local environment passed that specific setup test.
