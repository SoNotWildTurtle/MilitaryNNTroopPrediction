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

`make verify` intentionally chains the existing safe validation targets: `doctor`, `test`, and `ci-report`. It is the best pre-PR command when you want one local pass that checks minimal setup health, compiles and runs the unit tests, and builds the reviewer diagnostics bundle.

Hosted CI now runs the same entrypoint:

```bash
make verify ARTIFACT_DIR=ci_artifacts
```

That keeps local and pull-request validation aligned. When CI fails, reproduce the run locally with the same command, then open `ci_artifacts/release-bundle-index.html` first to inspect generated health reports, release notes, API contracts, examples, previews, and manifests.

After it completes, open `ci_artifacts/release-bundle-index.html` first. That static page links the health report, release notes, OpenAPI contract, synthetic examples, dashboard preview, HTML previews, and artifact manifest.

## CI failure triage

Use `docs/ci_troubleshooting.md` when a hosted workflow fails. The short path is:

```bash
make install-core
make verify ARTIFACT_DIR=ci_artifacts/local-ci
```

Then open `ci_artifacts/local-ci/release-bundle-index.html` and check `artifact-manifest.md` for missing generated outputs. The troubleshooting guide maps common symptoms to the narrow target to rerun, such as `make doctor`, `make test`, `make ci-report`, `make openapi`, `make examples`, `make dashboard`, `make previews`, `make manifest`, or `make release-notes`.

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
```

By default, artifact targets write into `ci_artifacts/`. Override the output directory when comparing multiple runs:

```bash
make ci-report ARTIFACT_DIR=ci_artifacts/local-smoke
make openapi ARTIFACT_DIR=ci_artifacts/api-contract-review
```

Open `ci_artifacts/release-bundle-index.html` first when reviewing a generated diagnostics bundle. It links the health report, release notes, OpenAPI contract, synthetic API examples, static dashboard mockup, HTML previews, and manifest from one dependency-free page.

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
| `make verify` | Run doctor, tests, and diagnostics bundle generation in one pre-PR command; CI uses this same target. |
| `make ci-report` | Build the same diagnostics bundle used by CI artifacts. |
| `make openapi` | Export OpenAPI JSON and Markdown summaries. |
| `make examples` | Export synthetic API response examples. |
| `make dashboard` | Export the static dashboard mockup. |
| `make bundle-index` | Export the static release bundle landing page. |
| `make previews` | Export SVG previews for static HTML outputs. |
| `make manifest` | Export artifact manifest JSON and Markdown with SHA-256 hashes. |
| `make release-notes` | Export manager-friendly release notes from diagnostics. |
| `make api` | Start the FastAPI server. |
| `make clean` | Remove generated local artifacts and caches. |
