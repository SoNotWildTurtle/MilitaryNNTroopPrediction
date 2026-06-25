# Contributing

Thank you for improving MilitaryNNTroopPrediction. This project should remain a lawful, defensive, analytical software project focused on safe setup, validation, documentation, synthetic examples, API contracts, reviewer artifacts, and reproducible local workflows.

## Safe contribution scope

Good first contributions include:

- Setup and dependency improvements that make the project easier to run.
- Read-only diagnostics, release health checks, and CI artifact improvements.
- API validation, response schemas, tests, and documentation.
- Synthetic fixtures, static mockups, and examples that do not depend on live conflict data.
- Error handling and user-facing messages that make failures easier to fix.

Do not add workflows that perform unauthorized collection, targeting, evasion, disruption, credential access, or operational deployment against real people or systems. Keep examples synthetic unless a maintainer explicitly adds a lawful dataset with clear provenance and usage rights.

## Fast local path

The root `Makefile` is the preferred command surface for common workflows:

```bash
make help
make install-core
make configure
make doctor
make test
```

Use `make install-core` for the minimal environment used by API health checks, diagnostics, and CI smoke tests. Use `make install-optional` only when you need the heavier ML, dashboard, GIS, or training dependencies.

## Before opening a pull request

Run the lightweight checks:

```bash
make test
```

When your change affects generated reviewer artifacts, also run:

```bash
make ci-report
```

Open `ci_artifacts/release-bundle-index.html` first when reviewing the generated bundle locally. It links health reports, release notes, OpenAPI summaries, API examples, dashboard mockups, previews, and manifests from one static page.

If hosted CI fails, use `docs/ci_troubleshooting.md` to reproduce the same `make verify` path locally and triage the uploaded diagnostics bundle before changing workflow code.

## Change checklist

Before committing, verify that your change:

- Preserves existing public commands, API routes, and documented file paths unless the update is intentional and documented.
- Adds or updates tests when behavior changes.
- Updates README or `docs/` when user-facing workflows change.
- Keeps generated local artifacts out of source control.
- Uses synthetic examples for demos and tests.
- Fails with clear remediation guidance when setup is incomplete.

## Documentation map

- `README.md` is the first-run and feature overview.
- `docs/common_tasks.md` explains Makefile targets and task-runner workflows.
- `docs/ci_troubleshooting.md` explains how to reproduce hosted CI failures locally and inspect diagnostic artifacts.
- `.env.example` documents local configuration values.
- `scripts/ci_report.sh` builds the local equivalent of the CI diagnostics bundle.
- `tests/` contains standard-library smoke tests that should stay fast and deterministic.

## Pull request summary template

Use a short summary that helps reviewers understand impact quickly:

```markdown
## Summary
- What changed and why
- User-facing workflows improved

## Validation
- Commands run locally
- Artifacts generated, if any

## Safety notes
- Data source assumptions
- Confirmation that examples/tests are synthetic or otherwise lawful

## Follow-up
- Known limitations
- Best next step
```
