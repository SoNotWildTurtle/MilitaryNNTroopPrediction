# Operator Readiness Checklist

Use the operator readiness checklist when a contributor, reviewer, or analyst needs a short go/no-go view of the generated diagnostics bundle before sharing it with another user.

The checklist is offline, read-only, and built from existing local artifacts. It does not connect to MongoDB, Sentinel Hub, live imagery, external OSINT sources, or prediction models.

## Generate the checklist

After building the diagnostics bundle, run:

```bash
make ci-report
make operator-readiness
```

The default outputs are:

- `ci_artifacts/operator-readiness.md` — human-readable checklist for handoff notes.
- `ci_artifacts/operator-readiness.json` — machine-readable status for automation.

You can customize paths directly:

```bash
python -m app.cli.operator_readiness \
  --artifact-dir ci_artifacts \
  --markdown-path ci_artifacts/operator-readiness.md \
  --json-path ci_artifacts/operator-readiness.json
```

## What it checks

The checklist looks for the reviewer-facing artifacts that make the project easier to hand off:

- `release-bundle-index.html`
- `release-health.md`
- `release-notes.md`
- `reviewer-handoff.md`
- `triage-summary.md`
- `artifact-manifest.md`
- `dashboard-mockup.html`
- `openapi-summary.md`

It also reads `release-health.json` when present and summarizes failures, warnings, or ready status.

## Readiness levels

- `ready` means release health did not report failures or warnings and the key handoff artifacts exist.
- `review` means at least one expected handoff artifact is missing, health data is unavailable, or warnings need human review.
- `blocked` means release health reported at least one failure that should be fixed before sharing the bundle as ready.

## Recommended reviewer path

1. Open `release-bundle-index.html` first.
2. Read `operator-readiness.md` for the short checklist.
3. Read `release-health.md` for detailed setup status.
4. Use `reviewer-handoff.md` as the copyable PR or release handoff note.
5. If blocked, use `triage-summary.md` to rerun the narrowest failing target.

## Safe scope

This workflow is documentation and diagnostics only. It is intended for safer project onboarding, release review, and local verification. It does not introduce new collection, targeting, prediction, or external network behavior.
