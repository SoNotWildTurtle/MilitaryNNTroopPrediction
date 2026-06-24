#!/usr/bin/env bash
# Install Python dependencies and prepare directories.
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}
INSTALL_PROFILE=${INSTALL_PROFILE:-optional}

case "$INSTALL_PROFILE" in
    core)
        REQUIREMENTS_FILE="requirements-core.txt"
        ;;
    optional|full)
        REQUIREMENTS_FILE="requirements-optional.txt"
        ;;
    *)
        echo "Unknown INSTALL_PROFILE='$INSTALL_PROFILE'. Use 'core', 'optional', or 'full'." >&2
        exit 2
        ;;
esac

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r "$REQUIREMENTS_FILE" ${PIP_EXTRA_ARGS:-}
mkdir -p data

echo "Installed $INSTALL_PROFILE dependencies from $REQUIREMENTS_FILE and ensured ./data exists."
