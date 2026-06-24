#!/usr/bin/env bash
# Run local preflight diagnostics without launching the API.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}

cd "$REPO_ROOT"
exec "$PYTHON_BIN" -m app.cli.doctor "$@"
