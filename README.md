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
- `docs/validation_failure_reproduction_matrix.md` – failure-to-rerun matrix for hosted CI, CLI, schema, artifact, documentation, and analytical-framing blockers
- `docs/automation_run_preflight.md` – start-of-run checklist for default branch, open PRs, hosted checks, narrow reruns, additive scope, and merge readiness
- `docs/reviewer_handoff_navigation.md` – first-stop routing map for reviewer handoff docs, generated artifacts, and narrow rerun commands
- `docs/release_bundle_review.md` – reviewer checklist for generated diagnostics bundles
- `docs/artifact_gap_report.md` – bundle completeness and suspicious-artifact audit workflow
- `docs/artifact_provenance_ledger.md` – generated/synthetic/preview/review artifact provenance workflow
- `docs/operator_status_board.md` – quick non-technical status board workflow for diagnostics handoff
- `docs/evidence_checklist.md` – baseline evidence checklist workflow for analytical handoff bundles
- `docs/synthetic_data_fixtures.md` – safe local fixture workflow for demos and client tests
- `docs/run_continuity_brief.md` – offline roadmap/changelog/decision-register brief for choosing the next non-duplicative maintenance increment
- `docs/next_increment_candidates.md` – offline candidate matrix for selecting a PR-sized increment with duplicate-work warnings and validation commands
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

`make verify` runs the minimal setup doctor, local smoke/unit tests, and the diagnostics bundle generator in one safe pre-PR pass. See `docs/common_tasks.md` for the full target map, `CONTRIBUTING.md` for the safe contribution checklist, `docs/automation_run_preflight.md` before opening or merging recurring maintenance work, `docs/ci_troubleshooting.md` when a hosted CI run needs local reproduction, `docs/validation_failure_reproduction_matrix.md` when you need to map a hosted CI, CLI, schema, artifact, documentation, or analytical-framing failure to the narrowest safe rerun, `docs/reviewer_handoff_navigation.md` when you need the first-stop map for reviewer handoff docs and generated artifacts, `docs/release_bundle_review.md` when reviewing generated bundles, `docs/artifact_gap_report.md` when checking bundle completeness, `docs/artifact_provenance_ledger.md` when separating generated review evidence from synthetic fixtures and previews, `docs/operator_status_board.md` when you need a fast non-technical status table, `docs/evidence_checklist.md` when validating baseline handoff evidence, `docs/synthetic_data_fixtures.md` when you need safe demo records without live data sources, `docs/run_continuity_brief.md` when selecting the next cohesive non-duplicative maintenance increment from roadmap, changelog, and decision-register context, and `docs/next_increment_candidates.md` when you need PR-sized candidate recipes with duplicate-work warnings and validation commands.

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
