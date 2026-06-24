#!/usr/bin/env bash
# Generate lightweight CI diagnostics and save them as workflow artifacts.
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}
ARTIFACT_DIR=${ARTIFACT_DIR:-ci_artifacts}

mkdir -p "${ARTIFACT_DIR}"

"${PYTHON_BIN}" --version > "${ARTIFACT_DIR}/python-version.txt"
"${PYTHON_BIN}" -m pip --version > "${ARTIFACT_DIR}/pip-version.txt"
"${PYTHON_BIN}" -m pip freeze > "${ARTIFACT_DIR}/pip-freeze.txt"
"${PYTHON_BIN}" -m app.cli.doctor --skip-optional --skip-mongo --skip-env-files --json > "${ARTIFACT_DIR}/doctor-minimal.json"
"${PYTHON_BIN}" -m app.cli.release_health \
  --markdown-path "${ARTIFACT_DIR}/release-health.md" \
  --json-path "${ARTIFACT_DIR}/release-health.json"
"${PYTHON_BIN}" -m app.cli.export_openapi \
  --json-path "${ARTIFACT_DIR}/openapi.json" \
  --markdown-path "${ARTIFACT_DIR}/openapi-summary.md"
"${PYTHON_BIN}" -m app.cli.export_api_examples \
  --json-path "${ARTIFACT_DIR}/api-response-examples.json" \
  --markdown-path "${ARTIFACT_DIR}/api-response-examples.md"
"${PYTHON_BIN}" -m app.cli.export_dashboard_mockup \
  --html-path "${ARTIFACT_DIR}/dashboard-mockup.html"
"${PYTHON_BIN}" -m app.cli.quickstart --help > "${ARTIFACT_DIR}/quickstart-help.txt"
"${PYTHON_BIN}" -m app.cli.doctor --help > "${ARTIFACT_DIR}/doctor-help.txt"
"${PYTHON_BIN}" -m app.cli.release_health --help > "${ARTIFACT_DIR}/release-health-help.txt"
"${PYTHON_BIN}" -m app.cli.release_notes --help > "${ARTIFACT_DIR}/release-notes-help.txt"
"${PYTHON_BIN}" -m app.cli.export_openapi --help > "${ARTIFACT_DIR}/export-openapi-help.txt"
"${PYTHON_BIN}" -m app.cli.export_api_examples --help > "${ARTIFACT_DIR}/export-api-examples-help.txt"
"${PYTHON_BIN}" -m app.cli.export_dashboard_mockup --help > "${ARTIFACT_DIR}/export-dashboard-mockup-help.txt"
"${PYTHON_BIN}" -m app.cli.release_bundle_index --help > "${ARTIFACT_DIR}/release-bundle-index-help.txt"
"${PYTHON_BIN}" -m app.cli.artifact_manifest --help > "${ARTIFACT_DIR}/artifact-manifest-help.txt"
"${PYTHON_BIN}" -m app.cli.export_html_previews --help > "${ARTIFACT_DIR}/export-html-previews-help.txt"

cat > "${ARTIFACT_DIR}/summary.txt" <<'SUMMARY'
MilitaryNNTroopPrediction CI diagnostic artifact bundle

Files:
- python-version.txt: Python interpreter version used by CI.
- pip-version.txt: pip version used by CI.
- pip-freeze.txt: installed package versions for reproducibility.
- doctor-minimal.json: machine-readable core setup diagnostics.
- release-health.md: human-readable release readiness summary.
- release-health.json: machine-readable release readiness summary.
- release-notes.md: manager-friendly release notes generated from diagnostics.
- release-notes.json: machine-readable release notes generated from diagnostics.
- openapi.json: machine-readable FastAPI OpenAPI contract.
- openapi-summary.md: human-readable API contract summary.
- api-response-examples.json: synthetic JSON responses for dashboard and client builders.
- api-response-examples.md: human-readable synthetic API response examples.
- dashboard-mockup.html: self-contained static dashboard preview generated from synthetic examples.
- release-bundle-index.html: self-contained reviewer landing page linking key bundle outputs.
- html-previews.md: human-readable index of SVG previews for static HTML artifacts.
- previews/dashboard-mockup.svg: lightweight browser-free visual preview of the dashboard mockup.
- previews/release-bundle-index.svg: lightweight browser-free visual preview of the release bundle index.
- quickstart-help.txt: current quickstart CLI options.
- doctor-help.txt: current doctor CLI options.
- release-health-help.txt: current release health CLI options.
- release-notes-help.txt: current release notes CLI options.
- export-openapi-help.txt: current OpenAPI export CLI options.
- export-api-examples-help.txt: current API example export CLI options.
- export-dashboard-mockup-help.txt: current dashboard mockup export CLI options.
- release-bundle-index-help.txt: current release bundle index CLI options.
- artifact-manifest-help.txt: current artifact manifest CLI options.
- export-html-previews-help.txt: current HTML preview export CLI options.
- artifact-manifest.json: machine-readable index of generated artifacts with sizes and SHA-256 hashes.
- artifact-manifest.md: human-readable index of generated artifacts with sizes and SHA-256 hashes.
SUMMARY

"${PYTHON_BIN}" -m app.cli.release_bundle_index \
  --artifact-dir "${ARTIFACT_DIR}" \
  --html-path "${ARTIFACT_DIR}/release-bundle-index.html"
"${PYTHON_BIN}" -m app.cli.export_html_previews \
  --artifact-dir "${ARTIFACT_DIR}" \
  --markdown-path "${ARTIFACT_DIR}/html-previews.md"

# Release notes summarize the manifest, while the manifest must also include the
# final release-note files. A two-pass handoff keeps both human notes and the
# final machine-readable manifest useful without requiring any network calls.
"${PYTHON_BIN}" -m app.cli.artifact_manifest \
  --artifact-dir "${ARTIFACT_DIR}" \
  --json-path "${ARTIFACT_DIR}/artifact-manifest.json" \
  --markdown-path "${ARTIFACT_DIR}/artifact-manifest.md"
"${PYTHON_BIN}" -m app.cli.release_notes \
  --health-json "${ARTIFACT_DIR}/release-health.json" \
  --manifest-json "${ARTIFACT_DIR}/artifact-manifest.json" \
  --markdown-path "${ARTIFACT_DIR}/release-notes.md" \
  --json-path "${ARTIFACT_DIR}/release-notes.json"
"${PYTHON_BIN}" -m app.cli.artifact_manifest \
  --artifact-dir "${ARTIFACT_DIR}" \
  --json-path "${ARTIFACT_DIR}/artifact-manifest.json" \
  --markdown-path "${ARTIFACT_DIR}/artifact-manifest.md"
"${PYTHON_BIN}" -m app.cli.release_notes \
  --health-json "${ARTIFACT_DIR}/release-health.json" \
  --manifest-json "${ARTIFACT_DIR}/artifact-manifest.json" \
  --markdown-path "${ARTIFACT_DIR}/release-notes.md" \
  --json-path "${ARTIFACT_DIR}/release-notes.json"
"${PYTHON_BIN}" -m app.cli.artifact_manifest \
  --artifact-dir "${ARTIFACT_DIR}" \
  --json-path "${ARTIFACT_DIR}/artifact-manifest.json" \
  --markdown-path "${ARTIFACT_DIR}/artifact-manifest.md"

printf 'Wrote CI diagnostics to %s\n' "${ARTIFACT_DIR}"
