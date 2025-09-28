#!/usr/bin/env bash
# Install Python dependencies and prepare directories
set -e

PYTHON_BIN=${PYTHON_BIN:-python3}

# Install core dependencies, avoiding GPU-heavy packages for quicker setup
$PYTHON_BIN -m pip install --break-system-packages fastapi pymongo tensorflow-cpu pillow uvicorn \
    albumentations scikit-learn matplotlib rich folium twilio \
    transformers openai

# Automatically install GPU-accelerated libraries when a GPU is present
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "GPU detected; installing CUDA-enabled libraries" >&2
    # Install PyTorch with CUDA support
    $PYTHON_BIN -m pip install --break-system-packages torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cu118
    # Replace cpu-only TensorFlow with the GPU build
    $PYTHON_BIN -m pip install --break-system-packages tensorflow
else
    echo "No GPU detected; skipping GPU library installation" >&2
fi
mkdir -p data
