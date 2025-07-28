#!/usr/bin/env bash
# Launch the API after ensuring dependencies are installed
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

bash "$SCRIPT_DIR/setup.sh"
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
