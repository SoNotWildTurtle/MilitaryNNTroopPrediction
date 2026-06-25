# Release bundle review flow

Use this checklist when reviewing a local `ci_artifacts/` directory or a downloaded `ci-diagnostics` artifact from GitHub Actions.

## Start with the landing page

Open:

```bash
ci_artifacts/release-bundle-index.html
```

The landing page is dependency-free and links the most useful reviewer artifacts first:

1. `release-health.md` for the pass/warn/fail readiness summary.
2. `triage-summary.md` for the exact local rerun target when hosted CI fails or an expected artifact is missing.
3. `openapi-summary.md` and `openapi.json` for API contract review.
4. `api-response-examples.md` and `api-response-examples.json` for client/dashboard integration.
5. `dashboard-mockup.html` for the static analytical UI preview.
6. `artifact-manifest.md` and `artifact-manifest.json` for sizes, hashes, and missing expected outputs.

## Triage failed or incomplete bundles

When the index reports missing files or CI fails, review `triage-summary.md` before scanning raw logs. It is designed to answer three questions quickly:

- What failed or appears incomplete?
- Which narrow command should be rerun locally?
- Which generated artifact should exist after the rerun?

The shortest local reproduction path remains:

```bash
make ci-triage
make verify
```

For focused artifact issues, use the rerun target printed in `triage-summary.md` instead of rerunning the full workflow. For example, rerun `make openapi`, `make dashboard`, `make bundle-index`, `make previews`, `make manifest`, or `make release-notes` when only one generated artifact is missing.

## Safe review boundaries

This bundle review flow is limited to defensive, analytical software validation. It does not run prediction models, fetch live imagery, connect to MongoDB, or perform operational tasking. The generated examples and dashboard mockup are synthetic and intended for documentation, onboarding, and client development.

## Expected handoff summary

A reviewer should be able to report:

- Overall release status from `release-health.md`.
- Any missing expected files from `artifact-manifest.md`.
- The recommended narrow rerun target from `triage-summary.md`.
- Whether API docs, examples, dashboard preview, and manifests are present.
- The next engineering action if the bundle is incomplete.
