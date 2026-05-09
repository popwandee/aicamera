#!/usr/bin/env bash
# =============================================================================
# deploy_dualbranch_lpr.sh
# Deploy DualBranchLPRNet to aicamera1, tag stable, run hardware test.
#
# Run from your Mac:
#   bash scripts/deploy_dualbranch_lpr.sh
# =============================================================================
set -euo pipefail

CAMERA_HOST="camuser@aicamera1"
CAMERA_IP="camuser@100.126.178.74"    # use IP if hostname not resolving
REMOTE_DIR="/home/camuser/aicamera"
STABLE_TAG="stable-before-dualbranch-lpr"
MODEL_DIR="resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503"

# Use IP directly for reliability
HOST="${CAMERA_IP}"

echo "======================================================"
echo " DualBranchLPRNet Deploy Script"
echo "======================================================"

# --- Step 1: rsync model files ---
echo ""
echo "[1/5] Copying model files to aicamera1 ..."
rsync -avz --progress \
    "${MODEL_DIR}/" \
    "${HOST}:${REMOTE_DIR}/${MODEL_DIR}/"
echo "✅ Model files synced"

# --- Step 2: rsync new code files ---
echo ""
echo "[2/5] Syncing code changes ..."
rsync -avz \
    edge/src/components/dual_branch_lpr_ocr.py \
    "${HOST}:${REMOTE_DIR}/edge/src/components/dual_branch_lpr_ocr.py"
rsync -avz \
    edge/src/components/detection_processor.py \
    "${HOST}:${REMOTE_DIR}/edge/src/components/detection_processor.py"
rsync -avz \
    edge/src/components/parallel_ocr_processor.py \
    "${HOST}:${REMOTE_DIR}/edge/src/components/parallel_ocr_processor.py"
rsync -avz \
    test_dual_branch_lpr.py \
    CONTEXT.md PROMPT.md GUARDRAIL.md CLAUDE.md \
    "${HOST}:${REMOTE_DIR}/"
echo "✅ Code synced"

# --- Step 3: git tag on remote ---
echo ""
echo "[3/5] Tagging stable version on aicamera1 ..."
ssh "${HOST}" "
    cd ${REMOTE_DIR}
    # Only tag if not already tagged
    if git tag | grep -q '${STABLE_TAG}'; then
        echo 'Tag ${STABLE_TAG} already exists — skipping'
    else
        git tag -a ${STABLE_TAG} -m 'Stable: pre-DualBranchLPRNet OCR integration 2026-05-07'
        echo 'Created tag: ${STABLE_TAG}'
    fi
    git log --oneline -3
"
echo "✅ Git tagged"

# --- Step 4: run hardware test ---
echo ""
echo "[4/5] Running hardware test on aicamera1 ..."
echo "      (stopping service to release Hailo device for test)"
ssh "${HOST}" "
    sudo systemctl stop aicamera_lpr.service
    sleep 2
    cd ${REMOTE_DIR}
    source edge/venv_hailo/bin/activate
    python3 test_dual_branch_lpr.py --debug 2>&1 | tail -30
"
echo ""
echo "======================================================"
echo "If all checks pass above, proceed with Step 5."
echo "If any check FAILS — do NOT restart the service."
echo "Fix the issue (likely CTC vocab or HEF path) and re-run."
echo "======================================================"

# --- Step 5: optional restart ---
read -r -p "Restart aicamera_lpr.service now? [y/N] " confirm
if [[ "${confirm}" =~ ^[Yy]$ ]]; then
    echo ""
    echo "[5/5] Restarting service ..."
    ssh "${HOST}" "sudo systemctl restart aicamera_lpr.service && sleep 3 && sudo systemctl status aicamera_lpr.service --no-pager | head -20"
    echo ""
    echo "✅ Service restarted. Monitor logs with:"
    echo "   ssh ${HOST} 'sudo journalctl -u aicamera_lpr -f'"
else
    echo ""
    echo "Service NOT restarted. To restart manually:"
    echo "  ssh ${HOST} 'sudo systemctl restart aicamera_lpr.service'"
fi

echo ""
echo "======================================================"
echo " Rollback command (if needed):"
echo "   ssh ${HOST} 'cd ${REMOTE_DIR} && git checkout ${STABLE_TAG} && sudo systemctl restart aicamera_lpr.service'"
echo "======================================================"
