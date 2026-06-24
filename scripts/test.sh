#!/usr/bin/env bash
# Run the same lightweight checks used by CI.
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}

"$PYTHON_BIN" -m compileall app tests
"$PYTHON_BIN" -m app.cli.doctor --skip-optional --skip-mongo --json
"$PYTHON_BIN" -m app.cli.release_health --no-json --markdown-path /tmp/militarynntroopprediction-release-health.md
"$PYTHON_BIN" -m app.cli.export_openapi --json-path /tmp/militarynntroopprediction-openapi.json --markdown-path /tmp/militarynntroopprediction-openapi.md
"$PYTHON_BIN" -m app.cli.export_api_examples --json-path /tmp/militarynntroopprediction-api-response-examples.json --markdown-path /tmp/militarynntroopprediction-api-response-examples.md
"$PYTHON_BIN" -m app.cli.export_dashboard_mockup --html-path /tmp/militarynntroopprediction-dashboard-mockup.html
"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py'
