# Operator status board

`app.cli.operator_status_board` generates a concise Markdown and JSON readiness board from an existing diagnostics artifact directory. It is designed for quick, non-technical handoffs after `make ci-report` or `make verify`.

The command reads these generated files when present:

- `artifact-manifest.json`
- `reviewer-handoff.json`
- `release-health.json`
- `triage-summary.json`
- `operator-readiness.json`
- `artifact-gap-report.json`
- `automation-plan.json`

It then writes:

- `operator-status-board.md` with a copyable status line, severity, action table, key-artifact table, and safe-scope reminder.
- `operator-status-board.json` with the same data for downstream automation.

## Usage

```bash
python -m app.cli.operator_status_board --artifact-dir ci_artifacts
python -m app.cli.operator_status_board --artifact-dir ci_artifacts --markdown-path ci_artifacts/operator-status-board.md --json-path ci_artifacts/operator-status-board.json
make operator-status-board
```

The CLI also supports explicit input paths for isolated smoke tests or custom bundle layouts:

```bash
python -m app.cli.operator_status_board \
  --artifact-dir /tmp \
  --manifest-path /tmp/militarynntroopprediction-artifact-manifest.json \
  --handoff-path /tmp/militarynntroopprediction-reviewer-handoff.json \
  --health-path /tmp/militarynntroopprediction-release-health.json \
  --triage-path /tmp/militarynntroopprediction-triage-summary.json \
  --readiness-path /tmp/militarynntroopprediction-operator-readiness.json \
  --gap-report-path /tmp/militarynntroopprediction-artifact-gap-report.json
```

## Review flow

1. Run `make ci-report` or `make verify`.
2. Open `ci_artifacts/operator-status-board.md` for the fastest readiness view.
3. If the board reports missing outputs, warnings, or blocked severity, run the recommended next command shown in the file.
4. Use `release-bundle-index.html`, `reviewer-handoff.md`, `operator-readiness.md`, and `artifact-gap-report.md` for deeper review context.

## Safe scope

The status board only summarizes generated diagnostics, static artifacts, synthetic examples, documentation, and defensive analytical review workflows. It does not run live collection, model inference, network scanning, targeting, or destructive actions.

## Rollback

The feature is additive. To roll it back, remove the `operator-status-board` Make target, delete `app/cli/operator_status_board.py`, remove `tests/test_operator_status_board.py`, and remove the status-board entries from `scripts/test.sh`, `scripts/ci_report.sh`, `app/cli/artifact_manifest.py`, and documentation. Existing diagnostics CLIs and generated artifacts remain compatible without the status board.
