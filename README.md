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
- `docs/run_decision_record.md` – machine-readable run decision record emitted by the candidate CLI for selected candidate, merge evidence, validation, blockers, rollback, and next follow-up capture
- `docs/implementation_acceptance_checklist.md` – offline acceptance gates and machine-readable gate summary contract for selected additive increments
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

`make verify` runs the minimal setup doctor, local smoke/unit tests, and the diagnostics bundle generator in one safe pre-PR pass. See `docs/common_tasks.md` for the full target map, `CONTRIBUTING.md` for the safe contribution checklist, `docs/automation_run_preflight.md` before opening or merging recurring maintenance work, `docs/ci_troubleshooting.md` when a hosted CI run needs local reproduction, `docs/validation_failure_reproduction_matrix.md` when you need to map a hosted CI, CLI, schema, artifact, documentation, or analytical-framing failure to the narrowest safe rerun, `docs/reviewer_handoff_navigation.md` when you need the first-stop map for reviewer handoff docs and generated artifacts, `docs/release_bundle_review.md` when reviewing generated bundles, `docs/artifact_gap_report.md` when checking bundle completeness, `docs/artifact_provenance_ledger.md` when separating generated review evidence from synthetic fixtures and previews, `docs/operator_status_board.md` when you need a fast non-technical status table, `docs/evidence_checklist.md` when validating baseline handoff evidence, `docs/synthetic_data_fixtures.md` when you need safe demo records without live data sources, `docs/run_continuity_brief.md` when selecting the next cohesive non-duplicative maintenance increment from roadmap, changelog, and decision-register context, `docs/run_decision_record.md` when turning the selected next-increment candidate into a machine-readable merge-evidence, validation, blocker, rollback, and follow-up record, and `docs/implementation_acceptance_checklist.md` when converting that selected candidate into blocking acceptance gates and gate-summary evidence for reviewers.

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
artifact provenance ledger, exports an operator status board, exports a baseline
evidence checklist, and executes the standard-library unit tests:

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
python -m app.cli.artifact_provenance_ledger --artifact-dir /tmp --manifest-path /tmp/militarynntroopprediction-artifact-manifest.json --json-path /tmp/militarynntroopprediction-artifact-provenance-ledger.json --markdown-path /tmp/militarynntroopprediction-artifact-provenance-ledger.md
python -m app.cli.artifact_gap_report --artifact-dir /tmp --manifest-path /tmp/militarynntroopprediction-artifact-manifest.json --json-path /tmp/militarynntroopprediction-artifact-gap-report.json --markdown-path /tmp/militarynntroopprediction-artifact-gap-report.md
python -m app.cli.release_notes --health-json /tmp/militarynntroopprediction-release-health.json --manifest-json /tmp/militarynntroopprediction-artifact-manifest.json --markdown-path /tmp/militarynntroopprediction-release-notes.md --json-path /tmp/militarynntroopprediction-release-notes.json
python -m app.cli.operator_status_board --artifact-dir /tmp --manifest-path /tmp/militarynntroopprediction-artifact-manifest.json --markdown-path /tmp/militarynntroopprediction-operator-status-board.md --json-path /tmp/militarynntroopprediction-operator-status-board.json
python -m app.cli.evidence_checklist --artifact-dir /tmp --markdown-path /tmp/militarynntroopprediction-evidence-checklist.md --json-path /tmp/militarynntroopprediction-evidence-checklist.json
python -m unittest discover -s tests -p 'test_*.py'
```

You can run the same checks locally with:

```bash
bash scripts/test.sh
# or
make test
```

For a fuller local pre-PR verification pass that also creates the diagnostic

```bash
make verify
```

CI also creates a `ci-diagnostics` artifact bundle on every run, even failed
runs. The bundle includes the Python and pip versions, `pip freeze`, doctor JSON,
release health reports, generated release notes, the generated FastAPI OpenAPI
contract, synthetic API response examples, safe JSONL/CSV synthetic data fixtures,
a self-contained static dashboard mockup, a reviewer-friendly release bundle
index page, lightweight SVG previews for static HTML outputs, SHA-256 artifact
manifests, diagnostic artifact gap reports, artifact provenance ledgers, operator
readiness briefs, operator status boards, automation plans, evidence checklists,
and the current help output for the doctor, quickstart, release health, release
notes, OpenAPI export, API example export, dashboard mockup export, synthetic
fixture export, release bundle index, HTML preview export, artifact manifest,
artifact gap report, artifact provenance ledger, operator readiness, operator
status board, evidence checklist, and automation plan CLIs. To build the same
bundle locally:

```bash
bash scripts/ci_report.sh
# or
make ci-report
```

Open `ci_artifacts/release-bundle-index.html` first when reviewing a local or CI
bundle. It links the release health summary, OpenAPI contract, synthetic examples,
dashboard mockup, synthetic data fixtures, artifact manifest, artifact gap report,
artifact provenance ledger, operator readiness, operator status board, automation
plan, baseline evidence checklist, and all indexed bundle files from one static,
dependency-free page. Use `docs/release_bundle_review.md` as the checklist for
confirming the bundle is complete before handing it to another reviewer.

If hosted CI fails, follow `docs/ci_troubleshooting.md` or run the short helper:

```bash
make ci-triage
```

It prints the exact local reproduction command, the expected artifact landing
page, and the narrow targets to rerun when a generated artifact is missing.

To export only the API contract without launching the server:

```bash
python -m app.cli.export_openapi
python -m app.cli.export_openapi --json-path openapi.json --markdown-path openapi-summary.md
# or
make openapi
```

To export synthetic API response examples for dashboard mockups, docs, and
client tests without MongoDB, Sentinel Hub, TensorFlow, YOLO, or live imagery:

```bash
python -m app.cli.export_api_examples
python -m app.cli.export_api_examples --json-path api-response-examples.json --markdown-path api-response-examples.md
# or
bash scripts/export_api_examples.sh
# or
make examples
```

To turn those same safe examples into a self-contained HTML dashboard preview:

```bash
python -m app.cli.export_dashboard_mockup
python -m app.cli.export_dashboard_mockup --html-path dashboard-mockup.html
# or
bash scripts/export_dashboard_mockup.sh
# or
make dashboard
```

The generated page is static and dependency-free. It is intended for user
onboarding, dashboard prototyping, screenshots, and API client planning; it does
not fetch live imagery, connect to MongoDB, or run prediction models. CI and
`scripts/ci_report.sh` include this HTML mockup in the `ci-diagnostics` artifact
bundle so non-technical reviewers can inspect the analytical UI preview without
cloning the repository or launching the API.

To export safe JSONL/CSV fixture records for data-loading demos or client tests:

```bash
python -m app.cli.synthetic_data_fixtures
python -m app.cli.synthetic_data_fixtures --output-dir data/fixtures --json
# or
make synthetic-fixtures
```

These fixture files are generated from `app.api.examples`, so they stay aligned
with the synthetic API response examples and dashboard mockups while remaining
safe placeholders with no live data access.

To generate a release bundle landing page for any diagnostics directory:

```bash
python -m app.cli.release_bundle_index --artifact-dir ci_artifacts
python -m app.cli.release_bundle_index --artifact-dir ci_artifacts --html-path release-bundle-index.html
# or
bash scripts/export_release_bundle_index.sh
# or
make bundle-index
```

To generate lightweight SVG preview cards for static HTML outputs without a
browser, Playwright, Selenium, or live API server:

```bash
python -m app.cli.export_html_previews --artifact-dir ci_artifacts
python -m app.cli.export_html_previews --artifact-dir ci_artifacts --output-dir ci_artifacts/previews --markdown-path ci_artifacts/html-previews.md
# or
make previews
```

The preview exporter reads generated HTML files such as `dashboard-mockup.html`
and `release-bundle-index.html`, extracts titles, headings, excerpts, and simple
link/table/section counts, and writes small SVG cards plus a Markdown index. This
is useful for CI artifact browsing, release notes, and quick screenshots when a
reviewer does not want to launch the full HTML page.

To index any generated diagnostics directory with file sizes, SHA-256 hashes,
and missing expected outputs:

```bash
python -m app.cli.artifact_manifest --artifact-dir ci_artifacts
python -m app.cli.artifact_manifest --artifact-dir ci_artifacts --json-path manifest.json --markdown-path manifest.md
# or
make manifest
```

To audit a generated diagnostics directory for missing, empty, or suspiciously
small expected outputs:

```bash
python -m app.cli.artifact_gap_report --artifact-dir ci_artifacts
python -m app.cli.artifact_gap_report --artifact-dir ci_artifacts --fail-on-gap
# or
make artifact-gap-report
```

This report is a safe local completeness check for reviewer handoff bundles. It
reads only the generated manifest and artifact metadata; it does not run live data
collection, model inference, prediction, deployment, or network workflows.

To classify generated diagnostics, synthetic fixtures, static previews, API
contracts, handoff outputs, and reproducibility evidence by provenance:

```bash
python -m app.cli.artifact_provenance_ledger --artifact-dir ci_artifacts
python -m app.cli.artifact_provenance_ledger --artifact-dir ci_artifacts --json-path ci_artifacts/artifact-provenance-ledger.json --markdown-path ci_artifacts/artifact-provenance-ledger.md
# or
make provenance-ledger
```

The ledger reads only `artifact-manifest.json` and labels files that should not be
mistaken for operational evidence, such as synthetic examples and static previews.

To generate a quick non-technical operator status board from a diagnostics bundle:

```bash
python -m app.cli.operator_status_board --artifact-dir ci_artifacts
python -m app.cli.operator_status_board --artifact-dir ci_artifacts --markdown-path ci_artifacts/operator-status-board.md --json-path ci_artifacts/operator-status-board.json
# or
make operator-status-board
```

The board reads only generated diagnostics such as the manifest, reviewer handoff,
release health, triage summary, operator readiness, artifact gap report, and
automation plan. It emits a copyable status line, severity, action table, key
artifact table, and recommended next command for fast handoff.

To turn a release health JSON file plus an artifact manifest into manager-friendly
release notes:

```bash
python -m app.cli.release_notes
python -m app.cli.release_notes --health-json ci_artifacts/release-health.json --manifest-json ci_artifacts/artifact-manifest.json --markdown-path ci_artifacts/release-notes.md --json-path ci_artifacts/release-notes.json
# or
make release-notes
```

The release notes summarize readiness, health counts, missing expected artifacts,
priority failures or warnings, reviewer artifacts, and a recommended next step.
This is useful when sharing CI bundles with users who need a quick analytical
handoff rather than raw JSON diagnostics.

To generate the baseline evidence checklist for a diagnostics bundle:

```bash
python -m app.cli.evidence_checklist --artifact-dir ci_artifacts
python -m app.cli.evidence_checklist --artifact-dir ci_artifacts --markdown-path ci_artifacts/evidence-checklist.md --json-path ci_artifacts/evidence-checklist.json
# or
make evidence-checklist
```

The checklist summarizes whether key generated evidence exists for provenance,
uncertainty, validation, reviewer handoff, handoff integrity, and safe analytical
framing. It does not validate operational truth or imply certainty.

To generate an offline continuity brief before selecting a new maintenance increment:

```bash
python -m app.cli.run_continuity_brief
python -m app.cli.run_continuity_brief --markdown-path ci_artifacts/run-continuity-brief.md --json-path ci_artifacts/run-continuity-brief.json
```

The brief reads `CHANGELOG.md`, `goals.md`, and `docs/next_run_decision_register.md`; scores focus areas for user friendliness, validation, provenance, diagnostics, and automation planning; and reports blockers when continuity context is missing. It is planning evidence only and does not collect live data, run detection, run prediction, or imply operational certainty.

To turn the offline next-increment candidate matrix into a machine-readable run decision record:

```bash
python -m app.cli.next_increment_candidates \
  --no-markdown \
  --json-path /tmp/next-increment-candidates.json \
  --decision-record-path /tmp/run-decision-record.json
```

The decision record captures the selected candidate, alternatives considered, required merge evidence, validation plan, blockers, compatibility notes, rollback notes, safe analytical framing, and next follow-up candidate. It is repository-maintenance evidence only and does not run live data collection, detection, prediction, or operational tasking.
