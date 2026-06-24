#!/usr/bin/env bash
# Export synthetic API response examples for dashboards, docs, and client tests.
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}
JSON_PATH=${JSON_PATH:-api-response-examples.json}
MARKDOWN_PATH=${MARKDOWN_PATH:-api-response-examples.md}

"${PYTHON_BIN}" -m app.cli.export_api_examples \
  --json-path "${JSON_PATH}" \
  --markdown-path "${MARKDOWN_PATH}"
