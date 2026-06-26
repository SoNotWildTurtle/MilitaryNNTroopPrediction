# Additive Automation Plan

`app.cli.automation_plan` turns the existing local diagnostics bundle and `goals.md` roadmap into a deterministic next-run plan for maintainers and scheduled maintenance agents.

The command is intentionally safe and offline-first. It only reads local Markdown/JSON files and writes Markdown/JSON outputs. It does not start services, run prediction models, fetch OSINT, call satellite providers, modify Git history, delete files, deploy infrastructure, or perform network collection.

## Generate a plan

After building a diagnostics bundle, run:

```bash
make automation-plan
```

or call the CLI directly:

```bash
python -m app.cli.automation_plan \
  --artifact-dir ci_artifacts \
  --goals-path goals.md \
  --markdown-path ci_artifacts/automation-plan.md \
  --json-path ci_artifacts/automation-plan.json
```

`make ci-report` also writes `automation-plan.md`, `automation-plan.json`, and `automation-plan-help.txt` into the diagnostics bundle.

## Inputs

The planner reads these local files when present:

- `goals.md` for numbered roadmap goals.
- `ci_artifacts/triage-summary.json` for validation status and narrow remediation commands.
- `ci_artifacts/artifact-manifest.json` for generated artifact coverage and missing expected outputs.
- `ci_artifacts/reviewer-handoff.json` for reviewer status and recommended rerun commands.

Missing or malformed files are treated as empty inputs so the CLI remains useful during partial CI failures.

## Outputs

The Markdown output is optimized for humans and includes:

- The current validation and reviewer-handoff status.
- The recommended next action.
- Missing artifacts and narrow remediation commands when diagnostics are incomplete.
- The highest-value additive roadmap candidates.
- Validation commands to run before publishing.
- Additive guardrails for safe repository maintenance.

The JSON output mirrors the same data for scripts, dashboards, and future automation.

## Safe additive scope

Use the automation plan to choose reviewable improvements such as:

- Documentation and onboarding fixes.
- Deterministic tests and regression coverage.
- Diagnostics, release bundle, and reviewer-handoff improvements.
- Synthetic examples, API-contract exports, and static preview tooling.
- Small defensive analytical helpers that preserve current behavior.

Do not use it to justify destructive changes, broad rewrites, force pushes, branch deletion, live data collection, offensive workflows, or unreviewed model/deployment changes.

## Review checklist

Before acting on an automation plan:

1. Open `release-bundle-index.html` from the same artifact directory.
2. Check `release-health.md` and `triage-summary.md` for failures or warnings.
3. Confirm `automation-plan.md` recommends either validation work or a small additive roadmap increment.
4. Run the listed validation commands before committing.
5. Keep the pull request summary explicit about additive impact, compatibility, tests, risks, and follow-up work.
