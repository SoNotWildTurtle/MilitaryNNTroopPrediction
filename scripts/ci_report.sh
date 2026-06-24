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
"${PYTHON_BIN}" -m app.cli.quickstart --help > "${ARTIFACT_DIR}/quickstart-help.txt"
"${PYTHON_BIN}" -m app.cli.doctor --help > "${ARTIFACT_DIR}/doctor-help.txt"
"${PYTHON_BIN}" -m app.cli.release_health --help > "${ARTIFACT_DIR}/release-health-help.txt"

cat > "${ARTIFACT_DIR}/summary.txt" <<'SUMMARY'
MilitaryNNTroopPrediction CI diagnostic artifact bundle

Files:
- python-version.txt: Python interpreter version used by CI.
- pip-version.txt: pip version used by CI.
- pip-freeze.txt: installed package versions for reproducibility.
- doctor-minimal.json: machine-readable core setup diagnostics.
- release-health.md: human-readable release readiness summary.
- release-health.json: machine-readable release readiness summary.
- quickstart-help.txt: current quickstart CLI options.
- doctor-help.txt: current doctor CLI options.
- release-health-help.txt: current release health CLI options.
SUMMARY

printf 'Wrote CI diagnostics to %s\n' "${ARTIFACT_DIR}"
