#!/usr/bin/env bash
# Run the same lightweight checks used by CI.
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}

"$PYTHON_BIN" -m compileall app tests
"$PYTHON_BIN" -m app.cli.doctor --skip-optional --skip-mongo --json
"$PYTHON_BIN" -m app.cli.release_health --markdown-path /tmp/militarynntroopprediction-release-health.md --json-path /tmp/militarynntroopprediction-release-health.json
"$PYTHON_BIN" -m app.cli.export_openapi --json-path /tmp/militarynntroopprediction-openapi.json --markdown-path /tmp/militarynntroopprediction-openapi.md
"$PYTHON_BIN" -m app.cli.export_api_examples --json-path /tmp/militarynntroopprediction-api-response-examples.json --markdown-path /tmp/militarynntroopprediction-api-response-examples.md
"$PYTHON_BIN" -m app.cli.export_dashboard_mockup --html-path /tmp/militarynntroopprediction-dashboard-mockup.html
"$PYTHON_BIN" -m app.cli.release_bundle_index --artifact-dir /tmp --html-path /tmp/militarynntroopprediction-release-bundle-index.html
"$PYTHON_BIN" -m app.cli.export_html_previews --artifact-dir /tmp --output-dir /tmp/militarynntroopprediction-html-previews --markdown-path /tmp/militarynntroopprediction-html-previews.md
"$PYTHON_BIN" -m app.cli.artifact_manifest --artifact-dir /tmp --json-path /tmp/militarynntroopprediction-artifact-manifest.json --markdown-path /tmp/militarynntroopprediction-artifact-manifest.md
"$PYTHON_BIN" -m app.cli.release_notes --health-json /tmp/militarynntroopprediction-release-health.json --manifest-json /tmp/militarynntroopprediction-artifact-manifest.json --markdown-path /tmp/militarynntroopprediction-release-notes.md --json-path /tmp/militarynntroopprediction-release-notes.json
"$PYTHON_BIN" -m app.cli.triage_summary --artifact-dir /tmp --health-json /tmp/militarynntroopprediction-release-health.json --manifest-json /tmp/militarynntroopprediction-artifact-manifest.json --markdown-path /tmp/militarynntroopprediction-triage-summary.md --json-path /tmp/militarynntroopprediction-triage-summary.json
"$PYTHON_BIN" -m app.cli.reviewer_handoff --artifact-dir /tmp --markdown-path /tmp/militarynntroopprediction-reviewer-handoff.md --json-path /tmp/militarynntroopprediction-reviewer-handoff.json
"$PYTHON_BIN" -m app.cli.operator_readiness --artifact-dir /tmp --health-json /tmp/militarynntroopprediction-release-health.json --manifest-json /tmp/militarynntroopprediction-artifact-manifest.json --triage-json /tmp/militarynntroopprediction-triage-summary.json --markdown-path /tmp/militarynntroopprediction-operator-readiness.md --json-path /tmp/militarynntroopprediction-operator-readiness.json
"$PYTHON_BIN" scripts/validate_reviewer_handoff.py /tmp/militarynntroopprediction-reviewer-handoff.json --json
"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py'
