# Common task runner workflows

The root `Makefile` gives contributors one stable command surface for setup, validation, local API startup, diagnostics, and generated reviewer artifacts. Every target wraps an existing repository CLI or script; it does not run live ingestion, detection, prediction, network collection, or destructive workflows.

## Fast path

```bash
make help
make install-core
make configure
make doctor
make test
```

Use `make install-core` for the lightweight API, doctor, and CI smoke-test environment. Use `make install-optional` only when you need the heavier ML, dashboard, mapping, and training packages.

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
