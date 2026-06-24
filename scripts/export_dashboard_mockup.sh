#!/usr/bin/env bash
# Export a static dashboard mockup from synthetic API examples.
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}
HTML_PATH=${HTML_PATH:-dashboard-mockup.html}

"${PYTHON_BIN}" -m app.cli.export_dashboard_mockup --html-path "${HTML_PATH}"
