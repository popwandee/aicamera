#!/usr/bin/env bash
# Run this INSIDE the GCP VM after SSH-ing in.
# Installs Hailo DFC prerequisites on Ubuntu 22.04 x86_64.

set -euo pipefail

echo "==> Updating system packages"
sudo apt-get update -q
sudo apt-get install -y \
  python3-pip python3-venv python3-dev \
  libgl1 libglib2.0-0 \
  wget curl git unzip \
  build-essential cmake

echo "==> Creating hailo Python venv"
python3 -m venv ~/hailo_env
source ~/hailo_env/bin/activate

echo "==> Install Hailo DFC wheel (upload or copy hailo_dataflow_compiler-*.whl first)"
echo "    Then run:"
echo "      pip install hailo_dataflow_compiler-*.whl"
echo ""
echo "==> Or install from Hailo developer zone package:"
echo "    https://hailo.ai/developer-zone/software-downloads/"
echo ""
echo "Prerequisites installed. Activate venv with:"
echo "  source ~/hailo_env/bin/activate"
