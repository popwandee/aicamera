#!/usr/bin/env bash
# GCP VM setup script for Hailo DFC (Data Flow Compiler)
# Hailo DFC requires Ubuntu 22.04, x86_64, 8+ vCPUs, 32GB+ RAM

set -euo pipefail

GCLOUD=/Users/sqh/google-cloud-sdk/bin/gcloud
export CLOUDSDK_PYTHON=/Users/sqh/.pyenv/versions/3.11.9/bin/python3

# ── Configuration ────────────────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-}"          # set via env or edit here
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="${VM_NAME:-hailo-dfc-vm}"
MACHINE_TYPE="${MACHINE_TYPE:-n2-standard-8}"   # 8 vCPU, 32 GB — adjust as needed
DISK_SIZE="${DISK_SIZE:-100}"                    # GB
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"

# ── Validate ─────────────────────────────────────────────────────────────────
if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: Set GCP_PROJECT_ID environment variable first."
  echo "  export GCP_PROJECT_ID=your-project-id"
  exit 1
fi

echo "Creating VM: $VM_NAME in $PROJECT_ID / $ZONE"

$GCLOUD compute instances create "$VM_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --image-family="$IMAGE_FAMILY" \
  --image-project="$IMAGE_PROJECT" \
  --boot-disk-size="${DISK_SIZE}GB" \
  --boot-disk-type="pd-ssd" \
  --metadata=enable-oslogin=true \
  --scopes=cloud-platform

echo ""
echo "VM created. SSH with:"
echo "  $GCLOUD compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID"
