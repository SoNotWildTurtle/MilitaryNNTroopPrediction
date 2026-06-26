# Operator session plan

`app.cli.operator_session_plan` turns generated CI and release artifacts into a ranked, copyable next-session checklist. It is intended for maintainers who want a fast, user-friendly answer to: "What should I do first on the next safe repo maintenance pass?"

The command is read-only with respect to project inputs. It only reads local JSON artifacts and writes Markdown/JSON summaries. It does not run ingestion, model prediction, network calls, deployment, scanning, or live data collection.

## Generate the plan

```bash
python -m app.cli.operator_session_plan --artifact-dir ci_artifacts
# or
make operator-session-plan
```

By default it writes:

- `ci_artifacts/operator-session-plan.md` for human review.
- `ci_artifacts/operator-session-plan.json` for automation.

`scripts/ci_report.sh` also includes these files in the local and hosted diagnostic bundle.

## Inputs

The planner uses whatever generated artifacts are available:

- `triage-summary.json` for blocker status and narrow rerun targets.
- `release-notes.json` for follow-up items, warnings, and risks.
- `reviewer-handoff.json` for copyable reviewer or maintainer steps.

If no specific task can be inferred, it falls back to a safe verification or bundle-review action.

## Useful options

```bash
python -m app.cli.operator_session_plan \
  --artifact-dir ci_artifacts \
  --max-tasks 3 \
  --markdown-path ci_artifacts/operator-session-plan.md \
  --json-path ci_artifacts/operator-session-plan.json
```

Use `--no-json` when only a Markdown handoff is needed.

## Review workflow

1. Run `make ci-report` or `make verify`.
2. Open `ci_artifacts/operator-session-plan.md`.
3. Start with the command under **Start here**.
4. Complete or explicitly defer each ranked task.
5. Regenerate diagnostics before opening a pull request.

Safe-scope reminder: keep this workflow limited to local diagnostics, deterministic tests, generated artifacts, documentation, and user-facing handoff automation.
