#!/usr/bin/env bash
# Generate a self-contained release bundle landing page.
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}
ARTIFACT_DIR=${ARTIFACT_DIR:-ci_artifacts}

"${PYTHON_BIN}" -m app.cli.release_bundle_index \
  --artifact-dir "${ARTIFACT_DIR}" \
  --html-path "${ARTIFACT_DIR}/release-bundle-index.html"
