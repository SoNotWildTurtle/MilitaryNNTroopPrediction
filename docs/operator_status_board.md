# Operator status board

`app.cli.operator_status_board` generates a concise Markdown and JSON readiness board from an existing diagnostics artifact directory. It is designed for quick, non-technical handoffs after `make ci-report` or `make verify`.

The command reads these generated files when present:

- `artifact-manifest.json`
- `reviewer-handoff.json`
- `release-health.json`
- `triage-summary.json`

It then writes:

- `operator-status-board.md` with a copyable status line, action table, key-artifact table, and safe-scope reminder.
- `operator-status-board.json` with the same data for downstream automation.

## Usage

```bash
python -m app.cli.operator_status_board --artifact-dir ci_artifacts
python -m app.cli.operator_status_board --artifact-dir ci_artifacts --markdown-path ci_artifacts/operator-status-board.md --json-path ci_artifacts/operator-status-board.json
make operator-status-board
```

## Review flow

1. Run `make ci-report` or `make verify`.
2. Open `ci_artifacts/operator-status-board.md` for the fastest readiness view.
3. If the board reports missing outputs or warnings, run the recommended next command shown in the file.
4. Use `release-bundle-index.html` and `reviewer-handoff.md` for deeper review context.

## Safe scope

The status board only summarizes generated diagnostics, static artifacts, synthetic examples, documentation, and defensive analytical review workflows. It does not run live collection, model inference, network scanning, or destructive actions.
