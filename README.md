# Military Neural Network Troop Prediction

This repository provides a starting point for a machine vision application that predicts troop movements using satellite imagery and OSINT data.

## Structure
- `app/` – Python package containing the main modules
  - `config.py` – configuration settings
  - `database.py` – MongoDB helpers
  - `data_ingestion.py` – OSINT and satellite retrieval
  - `detection/` – YOLO wrappers
  - `models/` – trajectory prediction models
  - `pipeline/` – scripts combining ingestion, detection and prediction
  - `api/` – FastAPI endpoints and typed response schemas
- `scripts/` – setup, diagnostics, quickstart, and startup scripts
- `tests/` – lightweight smoke tests for setup, API health, CLI behavior, and task-runner docs
- `Makefile` – stable task runner for setup, validation, API startup, artifacts, and cleanup
- `CONTRIBUTING.md` – safe contribution scope, PR checklist, and reviewer guidance
- `docs/common_tasks.md` – examples for common `make` workflows
- `docs/ci_troubleshooting.md` – local reproduction and diagnostics guide for CI failures
- `docs/release_bundle_review.md` – reviewer checklist for generated diagnostics bundles
- `docs/artifact_gap_report.md` – bundle completeness and suspicious-artifact audit workflow
- `docs/operator_status_board.md` – quick non-technical status board workflow for diagnostics handoff
- `docs/operator_session_plan.md` – ranked next-session plan workflow for maintainers and operators
- `docs/synthetic_data_fixtures.md` – safe local fixture workflow for demos and client tests
- `.env.example` – copyable first-run configuration template
- `.github/workflows/ci.yml` – GitHub Actions smoke checks for pushes and pull requests
- `requirements-core.txt` – minimal packages for API, doctor, and CI smoke checks
- `requirements-optional.txt` – heavier ML, dashboard, mapping, and training packages
- `notes.md` – project notes
- `dev_notes.md` – developer notes
- `goals.md` – high-level roadmap

## Usage

### Fast first run

For the most convenient contributor workflow, use the root task runner:

```bash
make help
make install-core
make configure
make verify
```

`make verify` runs the minimal setup doctor, local smoke/unit tests, and the diagnostics bundle generator in one safe pre-PR pass. See `docs/common_tasks.md` for the full target map, `CONTRIBUTING.md` for the safe contribution checklist, `docs/ci_troubleshooting.md` when a hosted CI run needs local reproduction, `docs/release_bundle_review.md` when reviewing generated bundles, `docs/artifact_gap_report.md` when checking bundle completeness, `docs/operator_status_board.md` when you need a fast non-technical status table, `docs/operator_session_plan.md` when you need a ranked next-session checklist, and `docs/synthetic_data_fixtures.md` when you need safe demo records without live data sources.

For a guided local setup path that installs the small core dependency set, creates
`.env` when needed, runs diagnostics, and prints the next command to run:

```bash
python -m app.cli.quickstart
# or
bash scripts/quickstart.sh
```

Useful options:

```bash
python -m app.cli.quickstart --skip-install
python -m app.cli.quickstart --install-profile optional --check-optional --check-mongo
python -m app.cli.quickstart --launch-api --host 127.0.0.1 --port 8000
```

The default quickstart path is intentionally conservative: it installs only
`requirements-core.txt`, creates a safe local config if one does not already
exist, skips optional ML/GIS/dashboard dependency checks, skips MongoDB socket
checks, and does not run detection or prediction.

### 1. Install dependencies

For a fast smoke-test/API environment:

```bash
python -m pip install -r requirements-core.txt
# or
make install-core
```

For the full local toolkit, including ML, dashboard, mapping, and training helpers:

```bash
python -m pip install -r requirements-optional.txt
# or
make install-optional
```

You can also use the setup wrapper, which installs the full optional stack by default:

```bash
bash scripts/setup.sh
```

Set `INSTALL_PROFILE=core` when you only want the smaller runtime used by CI:

```bash
INSTALL_PROFILE=core bash scripts/setup.sh
```

Run `scripts/start.sh` to install dependencies and launch the API:

```bash
bash scripts/start.sh
# or
make api
```

This will start a local server at `http://localhost:8000` with user-friendly health
and analytical endpoints:

- `GET /` - service index with useful links and available routes
- `GET /healthz` - no-dependency liveness check for scripts and uptime monitors
- `GET /readyz` - lightweight readiness summary for config and optional Sentinel setup
- `POST /predict/{area}` - run detection and prediction for an area
- `GET /detections/{area}?limit=10` - fetch recent detections
- `GET /predictions/{area}?limit=10` - fetch recent trajectory predictions

The API imports the heavier TensorFlow/YOLO prediction pipeline only when
`POST /predict/{area}` is called, so first-run health checks can work with just
the core dependency profile.

API responses are backed by Pydantic models in `app/api/schemas.py`, so the
exported OpenAPI contract includes stable response shapes for health, readiness,
prediction status, detections, and predictions. MongoDB `_id` values are exposed
as public `id` strings, while analytical records remain forward-compatible with
extra fields produced by future pipeline stages.

### 2. Create local configuration

The app reads a simple `.env` file when present. To create one with safe local
defaults from `.env.example`, run:

```bash
python -m app.cli.configure --non-interactive
# or
make configure
```

For guided setup, run the interactive mode instead:

```bash
python -m app.cli.configure
```

Use `--path custom.env` to write a different file and `--overwrite` to replace an
existing file. The default configuration uses `data/`, `mongodb://localhost:27017`,
and `troop_db`; Sentinel Hub values can be left blank when you want placeholder
imagery instead of live Sentinel imagery.

### 3. Check your setup first

Before launching heavier workflows, run the setup doctor to verify that Python,
configuration templates, local environment files, core dependencies, optional
analysis dependencies, the data directory, Sentinel Hub environment variables,
and MongoDB socket connectivity are configured:

```bash
python -m app.cli.doctor
# or
bash scripts/doctor.sh
# or
make doctor
```

Useful options:

```bash
python -m app.cli.doctor --skip-optional --skip-mongo
python -m app.cli.doctor --skip-env-files
python -m app.cli.doctor --json
```

The command is read-only except for creating the configured `DATA_DIR` and a
short-lived write probe inside it. Warnings identify optional capabilities that
are missing; failures identify core setup problems that should be fixed before
running the API or automation pipeline.

### 4. Generate safe local demo data

When you need fixture records for dashboards, screenshots, client tests, or docs
without connecting to live OSINT, imagery, database, or model workflows, run:

```bash
python -m app.cli.synthetic_data_fixtures
python -m app.cli.synthetic_data_fixtures --output-dir data/fixtures --json
# or
make synthetic-fixtures
```

The exporter writes JSONL, CSV, Markdown, and summary JSON files under
`data/fixtures/` by default. Use `--output-dir` for isolated CI or review
artifacts. These records are analytical placeholders for reproducible demos and
must not be presented as operational truth.

### Automated checks

A lightweight GitHub Actions workflow runs on pushes and pull requests to catch
basic breakage before heavier ML workflows are attempted. It installs the shared
core requirements file, compiles the Python package and tests, runs the setup
doctor in minimal mode, validates the lightweight API health layer, exports the
OpenAPI contract, exports synthetic API response examples, exports the static
dashboard mockup, exports safe synthetic data fixtures, exports a release bundle
index page, exports lightweight SVG previews for static HTML artifacts, exports a
diagnostic artifact manifest, exports a diagnostic artifact gap report, exports an
operator status board, and executes the standard-library unit tests:

```bash
python -m pip install -r requirements-core.txt
python -m compileall app tests
python -m app.cli.doctor --skip-optional --skip-mongo --json
python -m app.cli.export_openapi --json-path /tmp/militarynntroopprediction-openapi.json --markdown-path /tmp/militarynntroopprediction-openapi.md
python -m app.cli.export_api_examples --json-path /tmp/militarynntroopprediction-api-response-examples.json --markdown-path /tmp/militarynntroopprediction-api-response-examples.md
python -m app.cli.export_dashboard_mockup --html-path /tmp/militarynntroopprediction-dashboard-mockup.html
python -m app.cli.synthetic_data_fixtures --output-dir /tmp/militarynntroopprediction-synthetic-fixtures --json
python -m app.cli.release_bundle_index --artifact-dir /tmp --html-path /tmp/militarynntroopprediction-release-bundle-index.html
python -m app.cli.export_html_previews --artifact-dir /tmp --output-dir /tmp/militarynntroopprediction-html-previews --markdown-path /tmp/militarynntroopprediction-html-previews.md
python -m app.cli.artifact_manifest --artifact-dir /tmp --json-path /tmp/militarynntroopprediction-artifact-manifest.json --markdown-path /tmp/militarynntroopprediction-artifact-manifest.md
python -m app.cli.artifact_gap_report --artifact-dir /tmp --manifest-path /tmp/militarynntroopprediction-artifact-manifest.json --json-path /tmp/militarynntroopprediction-artifact-gap-report.json --markdown-path /tmp/militarynntroopprediction-artifact-gap-report.md
python -m app.cli.release_notes --health-json /tmp/militarynntroopprediction-release-health.json --manifest-json /tmp/militarynntroopprediction-artifact-manifest.json --markdown-path /tmp/militarynntroopprediction-release-notes.md --json-path /tmp/militarynntroopprediction-release-notes.json
python -m app.cli.operator_status_board --artifact-dir /tmp --manifest-path /tmp/militarynntroopprediction-artifact-manifest.json --markdown-path /tmp/militarynntroopprediction-operator-status-board.md --json-path /tmp/militarynntroopprediction-operator-status-board.json
python -m unittest discover -s tests -p 'test_*.py'
```
