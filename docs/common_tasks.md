# Common task runner workflows

The root `Makefile` gives contributors one stable command surface for setup, validation, local API startup, diagnostics, and generated reviewer artifacts. Every target wraps an existing repository CLI or script; it does not run live ingestion, detection, prediction, network collection, or destructive workflows.

## Fast path

```bash
make help
make install-core
make configure
make verify
```

Use `make install-core` for the lightweight API, doctor, and CI smoke-test environment. Use `make install-optional` only when you need the heavier ML, dashboard, mapping, and training packages.

## First-time contributor workflow

Start with the safe, minimal path before installing heavier optional dependencies:

```bash
make help
make install-core
make configure
make doctor
make test
make verify
```

Then review `CONTRIBUTING.md` before opening a pull request. It summarizes the lawful defensive scope, test expectations, documentation checklist, and PR summary format.

## One-command verification

```bash
make verify
make verify ARTIFACT_DIR=ci_artifacts/local-verify
```

`make verify` intentionally chains the existing safe validation targets: `doctor`, `test`, `ci-report`, and `validate-handoff`. It is the best pre-PR command when you want one local pass that checks minimal setup health, compiles and runs the unit tests, builds the reviewer diagnostics bundle, and confirms the generated `reviewer-handoff.json` still satisfies the documented downstream contract.

Hosted CI now runs the same entrypoint:

```bash
make verify ARTIFACT_DIR=ci_artifacts
```

That keeps local and pull-request validation aligned. When CI fails, reproduce the run locally with the same command, then open `ci_artifacts/release-bundle-index.html` first to inspect generated health reports, release notes, reviewer handoff notes, triage guidance, API contracts, examples, previews, manifests, and handoff validation results.

After it completes, open `ci_artifacts/release-bundle-index.html` first. That static page links the reviewer handoff, health report, release notes, triage summary, OpenAPI contract, synthetic examples, dashboard preview, HTML previews, and artifact manifest. Use `docs/release_bundle_review.md` as the reviewer checklist before sharing or summarizing the bundle.

## CI failure triage

Use `docs/ci_troubleshooting.md` when a hosted workflow fails. To print the guide path, exact local reproduction command, expected artifact landing page, and narrow rerun targets without opening the docs first, run:

```bash
make ci-triage
```

The short manual path is:

```bash
make install-core
make verify ARTIFACT_DIR=ci_artifacts/local-ci
```

Then open `ci_artifacts/local-ci/release-bundle-index.html` and check `reviewer-handoff.md` first when sharing context with another maintainer. Check `reviewer-handoff-validation.json` next when downstream automation rejects a bundle; it is produced by `scripts/validate_reviewer_handoff.py` and reports the exact contract errors. Check `triage-summary.md` when a run failed. It summarizes failing health checks, missing expected artifacts, and the narrow target to rerun, such as `make doctor`, `make test`, `make ci-report`, `make validate-handoff`, `make openapi`, `make examples`, `make dashboard`, `make previews`, `make manifest`, `make release-notes`, `make reviewer-handoff`, or `make triage-summary`.

## Runtime

```bash
make api
make api HOST=0.0.0.0 PORT=8080
```

The API target starts the existing FastAPI app with `uvicorn`. The default bind address is conservative: `127.0.0.1:8000`.

## Diagnostics and reviewer artifacts

```bash
make ci-report
make openapi
make examples
make dashboard
make bundle-index
make previews
make manifest
make release-notes
make reviewer-handoff
make validate-handoff
make triage-summary
```

By default, artifact targets write into `ci_artifacts/`. Override the output directory when comparing multiple runs:

```bash
make ci-report ARTIFACT_DIR=ci_artifacts/local-smoke
make validate-handoff ARTIFACT_DIR=ci_artifacts/local-smoke
make openapi ARTIFACT_DIR=ci_artifacts/api-contract-review
```

Open `ci_artifacts/release-bundle-index.html` first when reviewing a generated diagnostics bundle. It links the reviewer handoff, health report, release notes, triage summary, OpenAPI contract, synthetic API examples, static dashboard mockup, HTML previews, and manifest from one dependency-free page. The companion guide at `docs/release_bundle_review.md` gives the quick reviewer handoff flow.

`reviewer-handoff.md` includes a normalized review status, a copyable summary, missing expected outputs, missing key artifacts, and the recommended narrow rerun command. Use that file when sending a diagnostics bundle to another maintainer because it summarizes whether the bundle is ready, needs warning review, or needs attention before deeper inspection. `reviewer-handoff-validation.json` and `reviewer-handoff-validation.txt` record the dependency-free validation result from `scripts/validate_reviewer_handoff.py` so reviewers and automation can confirm the machine-readable handoff follows `docs/reviewer_handoff_contract.md` before consuming it.

## Cleanup

```bash
make clean
```

This removes generated local artifacts, Python bytecode caches, and `.pytest_cache` while leaving source files, configuration templates, and dependency files untouched.

## Target map

| Target | Purpose |
| --- | --- |
| `make help` | Print available tasks and the current configurable variables. |
| `make install-core` | Install `requirements-core.txt`. |
| `make install-optional` | Install `requirements-optional.txt`. |
| `make configure` | Create a safe local `.env` when one is missing. |
| `make quickstart` | Run the guided conservative first-run workflow. |
| `make doctor` | Run minimal read-only diagnostics. |
| `make test` | Run the local smoke checks and standard-library test suite. |
| `make verify` | Run doctor, tests, diagnostics bundle generation, and reviewer handoff contract validation in one pre-PR command; CI uses this same target. |
| `make ci-triage` | Print the CI troubleshooting guide path, local reproduction command, artifact page, and narrow rerun targets. |
| `make ci-report` | Build the same diagnostics bundle used by CI artifacts, including handoff validation outputs. |
| `make openapi` | Export OpenAPI JSON and Markdown summaries. |
| `make examples` | Export synthetic API response examples. |
| `make dashboard` | Export the static dashboard mockup. |
| `make bundle-index` | Export the static release bundle landing page. |
| `make previews` | Export SVG previews for static HTML outputs. |
| `make manifest` | Export artifact manifest JSON and Markdown with SHA-256 hashes. |
| `make release-notes` | Export manager-friendly release notes from diagnostics. |
| `make reviewer-handoff` | Export actionable reviewer handoff Markdown/JSON with review status, copyable summary, missing artifacts, and rerun guidance. |
| `make validate-handoff` | Validate `reviewer-handoff.json` against the stable contract using `scripts/validate_reviewer_handoff.py`. |
| `make triage-summary` | Export CI triage Markdown/JSON with failing checks, missing artifacts, and narrow rerun targets. |
| `make api` | Start the FastAPI server. |
| `make clean` | Remove generated local artifacts and caches. |
