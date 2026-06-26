# Operator runbook index

The operator runbook index is a safe, local, generated map of project commands, documentation, generated artifacts, and first steps. It is intended for maintainers, reviewers, and non-technical operators who need a quick orientation before reading the full diagnostics bundle.

## What it does

`app.cli.operator_runbook_index` creates:

- `operator-runbook-index.md` for a human-readable command, documentation, artifact, and safe-scope map.
- `operator-runbook-index.json` using schema `militarynntroopprediction.operator_runbook_index.v1` for automation and release-gate consumers.

The workflow is read-only except for writing the requested output files. It does not run collection, ingestion, prediction, model training, network access, deployment, or live intelligence workflows.

## Usage

```bash
python -m app.cli.operator_runbook_index
python -m app.cli.operator_runbook_index --artifact-dir ci_artifacts --markdown-path ci_artifacts/operator-runbook-index.md --json-path ci_artifacts/operator-runbook-index.json
make operator-runbook-index
```

The CI diagnostics bundle also generates the runbook index through `scripts/ci_report.sh`.

## Recommended review path

1. Run `make verify` before opening or updating a pull request.
2. Open `ci_artifacts/release-bundle-index.html` first.
3. Use `ci_artifacts/operator-runbook-index.md` to find the right safe command, documentation page, or generated artifact.
4. Use `ci_artifacts/operator-status-board.md` for a fast non-technical readiness summary.
5. Use `ci_artifacts/operator-session-plan.md` and `ci_artifacts/automation-plan.md` to pick the next safe maintenance increment.

## Safety and analytical framing

The runbook keeps predictive outputs framed as analytical estimates and support artifacts. It is designed for reproducibility, validation, and handoff. It must not be used as operational targeting evidence or certainty about real-world movement.

## Rollback

This change is additive. To roll it back, remove:

- `app/cli/operator_runbook_index.py`
- `tests/test_operator_runbook_index.py`
- the `operator-runbook-index` target in `Makefile`
- the runbook index calls and help capture in `scripts/ci_report.sh` and `scripts/test.sh`
- the runbook entries in `app/cli/artifact_manifest.py`
- generated `operator-runbook-index.md/json` files from local artifact directories
