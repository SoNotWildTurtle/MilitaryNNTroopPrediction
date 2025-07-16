#!/usr/bin/env bash
# Install Python dependencies and prepare directories
set -e

PYTHON_BIN=${PYTHON_BIN:-python3}

$PYTHON_BIN -m pip install fastapi pymongo tensorflow pillow uvicorn \
    albumentations opencv-python ultralytics scikit-learn matplotlib rich folium --break-system-packages
mkdir -p data
