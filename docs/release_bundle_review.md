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

## Use the reviewer handoff

Open `reviewer-handoff.md` when you need a copyable human handoff for a PR, issue, or chat review. Use `reviewer-handoff.json` when downstream automation needs the same status fields without parsing Markdown.

The JSON handoff includes:

- `review_status` and `release_status` for quick pass/warn/attention routing.
- `recommended_rerun` for the narrow local command to run next.
- `missing_expected` and `missing_key_artifacts` for incomplete-bundle checks.
- `review_order`, a machine-readable checklist matching the landing page review sequence. Each step includes the step number, action, artifact path, present/missing status, and why the artifact matters.

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

- Overall release status from `release-health.md` or `reviewer-handoff.json`.
- Any missing expected files from `artifact-manifest.md` or the handoff JSON.
- The recommended narrow rerun target from `triage-summary.md` or the handoff JSON.
- Whether API docs, examples, dashboard preview, manifests, and review-order artifacts are present.
- The next engineering action if the bundle is incomplete.
