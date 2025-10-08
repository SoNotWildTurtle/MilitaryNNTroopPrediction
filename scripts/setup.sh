#!/usr/bin/env bash
# Install Python dependencies and prepare directories
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
SETUP_CACHE_DIR="$PROJECT_ROOT/.cache"
STAMP_FILE="$SETUP_CACHE_DIR/setup.sha"
CURRENT_HASH=$(sha256sum "$SCRIPT_DIR/setup.sh" | awk '{print $1}')

if [[ -f "$STAMP_FILE" && $(<"$STAMP_FILE") == "$CURRENT_HASH" && "${FORCE_SETUP:-0}" != "1" ]]; then
    echo "Dependencies already installed (use FORCE_SETUP=1 to reinstall)" >&2
    mkdir -p "$PROJECT_ROOT/data"
    exit 0
fi

mkdir -p "$SETUP_CACHE_DIR"

# Core packages shared by the API, pipelines and dashboards
BASE_PACKAGES=(
    fastapi
    pymongo
    tensorflow-cpu
    pillow
    uvicorn
    albumentations
    scikit-learn
    matplotlib
    rich
    folium
    twilio
    transformers
    openai
    opencv-python-headless
    scikit-image
    ultralytics
)

echo "Installing core Python dependencies" >&2
"$PYTHON_BIN" -m pip install --break-system-packages "${BASE_PACKAGES[@]}"

# Install a CPU build of PyTorch by default; GPU environments will override below.
TORCH_PACKAGES=(torch torchvision torchaudio)
TORCH_CPU_INDEX="https://download.pytorch.org/whl/cpu"
echo "Installing PyTorch CPU wheels" >&2
"$PYTHON_BIN" -m pip install --break-system-packages --index-url "$TORCH_CPU_INDEX" "${TORCH_PACKAGES[@]}"

# Automatically install GPU-accelerated libraries when a GPU is present
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "GPU detected; upgrading to CUDA-enabled libraries" >&2
    "$PYTHON_BIN" -m pip install --break-system-packages --index-url \
        https://download.pytorch.org/whl/cu118 "${TORCH_PACKAGES[@]}"
    # Replace cpu-only TensorFlow with the GPU build
    "$PYTHON_BIN" -m pip install --break-system-packages tensorflow
else
    echo "No GPU detected; keeping CPU-only deep learning libraries" >&2
fi

mkdir -p "$PROJECT_ROOT/data"

echo "$CURRENT_HASH" >"$STAMP_FILE"
