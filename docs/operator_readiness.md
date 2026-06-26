# Operator readiness brief

The operator readiness brief is a lightweight, deterministic summary for maintainers, analysts, and non-technical operators who need a quick launch/no-launch view of a generated diagnostics bundle.

It is intentionally safe and additive:

- reads local JSON artifacts from the diagnostics bundle;
- writes Markdown and JSON summaries;
- never starts ingestion, detection, prediction, database, deployment, or network workflows;
- does not modify analytical data sources; and
- keeps the existing reviewer handoff, release notes, triage summary, dashboard mockup, and manifest workflows unchanged.

## Generate the brief

```bash
python -m app.cli.operator_readiness \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/operator-readiness.md \
  --json-path ci_artifacts/operator-readiness.json
```

Or use the task runner:

```bash
make operator-readiness
```

For a full local validation pass that creates diagnostics and then validates the generated reviewer handoff, run:

```bash
make verify
```

## Status semantics

The JSON output uses three operator-facing launch states:

| Status | Meaning | Typical next action |
| --- | --- | --- |
| `ready` | Required operator artifacts are present and health checks have no blockers or warnings. | Open `release-bundle-index.html` and attach the diagnostics bundle to the PR. |
| `review` | No hard blocker was detected, but one or more warnings need human review. | Read `release-health.md` and `operator-readiness.md`, then decide whether warnings are acceptable. |
| `blocked` | A failing check, missing expected output, or missing required operator artifact was detected. | Run the narrow command listed in `next_step`, then regenerate the diagnostics bundle. |

## Required operator artifacts

The brief expects the following artifacts because together they support a reviewer-friendly, reproducible release decision:

- `release-health.json` and `release-health.md`
- `artifact-manifest.json` and `artifact-manifest.md`
- `triage-summary.json` and `triage-summary.md`
- `reviewer-handoff.json` and `reviewer-handoff.md`

Missing artifacts are reported as blockers so operators do not approve an incomplete diagnostics bundle by accident.

## Compatibility

This is an additive workflow. Existing commands, API behavior, ML helpers, generated release notes, reviewer handoff files, and diagnostics artifacts continue to work. The new brief only adds a clearer final decision layer for human review.
