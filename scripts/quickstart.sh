#!/usr/bin/env bash
# Run the guided first-run setup flow.
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}
exec "$PYTHON_BIN" -m app.cli.quickstart "$@"
