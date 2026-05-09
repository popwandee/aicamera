#!/usr/bin/env bash
# Run inside the GCP VM. Installs Hailo DFC and compiles ONNX -> HEF.
set -euo pipefail

WORKDIR=~/hailo-compiler
VENV=$WORKDIR/hailo_env
WHEEL=$WORKDIR/hailo_dataflow_compiler-3.33.1-py3-none-linux_x86_64.whl
HW_ARCH="${1:-hailo8l}"   # pass hailo8 or hailo8l as first arg

echo "==> Working directory: $WORKDIR"
cd "$WORKDIR"

# ── System deps ──────────────────────────────────────────────────────────────
echo "==> Installing system dependencies …"
sudo apt-get update -q
sudo apt-get install -y python3-pip python3-venv python3-dev \
    libgl1 libglib2.0-0 ffmpeg \
    build-essential \
    graphviz libgraphviz-dev pkg-config \
    python3-tk 2>&1 | tail -5

# ── Python venv ──────────────────────────────────────────────────────────────
if python3 -c "import hailo_sdk_client" 2>/dev/null; then
    echo "==> Hailo DFC already installed, skipping venv rebuild."
else
    if [[ -d "$VENV" ]]; then
        echo "==> Removing incomplete venv …"
        rm -rf "$VENV"
    fi
    echo "==> Creating Python venv …"
    python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"
pip install --upgrade pip --quiet

# ── Install Hailo DFC wheel ──────────────────────────────────────────────────
echo "==> Installing Hailo DFC wheel (488 MB, may take a few minutes) …"
pip install "$WHEEL" 2>&1 | grep -E "Successfully|error|ERROR|warning" || true

# ── Verify install ───────────────────────────────────────────────────────────
echo "==> Hailo DFC version:"
hailo --version 2>&1 || python3 -c "import hailo_sdk_client; print(hailo_sdk_client.__version__)"

# ── Compile ──────────────────────────────────────────────────────────────────
echo "==> Starting ONNX -> HEF compilation (arch: $HW_ARCH) …"
python3 compile_to_hef.py --hw-arch "$HW_ARCH"

echo ""
echo "==> Compilation complete. HEF file:"
ls -lh "$WORKDIR"/*.hef
