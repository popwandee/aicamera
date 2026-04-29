#!/bin/bash
# =============================================================================
# Fix Detection & Stream Issues — aicamera2
# สร้างวันที่: 2026-04-28
# ปัญหาที่แก้: DETECTION_INTERVAL=30s, color RGB/BGR swap, aspect ratio
# =============================================================================
# วิธีใช้:
#   chmod +x scripts/fix_detection_issues.sh
#   ./scripts/fix_detection_issues.sh
# =============================================================================

set -e

AICAMERA2_HOST="100.110.20.53"
AICAMERA2_USER="camuser"
AICAMERA2_PASS="admin88366"
AICAMERA2_DIR="/home/camuser/aicamera"
SERVICE_NAME="aicamera_lpr"

echo "=============================================="
echo " AI Camera Detection Fix Script"
echo " Target: ${AICAMERA2_USER}@${AICAMERA2_HOST}"
echo " Date: $(date)"
echo "=============================================="

# Helper: run command on aicamera2
ssh_run() {
    sshpass -p "${AICAMERA2_PASS}" ssh -o StrictHostKeyChecking=no \
        "${AICAMERA2_USER}@${AICAMERA2_HOST}" "$@"
}

# Check connectivity
echo ""
echo "[1/7] Checking connectivity to aicamera2..."
if ! ping -c 1 -W 3 "${AICAMERA2_HOST}" &>/dev/null; then
    echo "ERROR: Cannot reach ${AICAMERA2_HOST} — check Tailscale connection"
    exit 1
fi
echo "      ✅ aicamera2 reachable"

# Pull latest code from git
echo ""
echo "[2/7] Pulling latest code from git (includes video_streaming.py fix)..."
ssh_run "cd ${AICAMERA2_DIR} && git pull origin main 2>&1 | tail -5"
echo "      ✅ Code updated"

# Backup current .env.production
echo ""
echo "[3/7] Backing up current .env.production..."
ssh_run "cp ${AICAMERA2_DIR}/edge/installation/.env.production \
    ${AICAMERA2_DIR}/edge/installation/.env.production.bak.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true"
echo "      ✅ Backup done"

# Show current critical values
echo ""
echo "[4/7] Current .env.production values (before fix):"
ssh_run "grep -E 'DETECTION_INTERVAL|CONFIDENCE_THRESHOLD|LORES_RESOLUTION|MAIN_RESOLUTION|REENTRY_TIME' \
    ${AICAMERA2_DIR}/edge/installation/.env.production 2>/dev/null || echo '  (file not found)'"

# Apply .env.production fixes
echo ""
echo "[5/7] Applying .env.production fixes..."
ssh_run "cd ${AICAMERA2_DIR}/edge/installation && \
    # Fix DETECTION_INTERVAL: 30.0 -> 0.5 (run detection every 0.5s, not every 30s)
    if grep -q 'DETECTION_INTERVAL=' .env.production; then
        sed -i 's/^DETECTION_INTERVAL=.*/DETECTION_INTERVAL=0.5/' .env.production
    else
        echo 'DETECTION_INTERVAL=0.5' >> .env.production
    fi && \
    # Fix DETECTION_CONFIDENCE_THRESHOLD: 0.8 -> 0.65 (more permissive for field)
    if grep -q 'DETECTION_CONFIDENCE_THRESHOLD=' .env.production; then
        sed -i 's/^DETECTION_CONFIDENCE_THRESHOLD=.*/DETECTION_CONFIDENCE_THRESHOLD=0.65/' .env.production
    else
        echo 'DETECTION_CONFIDENCE_THRESHOLD=0.65' >> .env.production
    fi && \
    # Fix LORES_RESOLUTION: 640x640 -> 640x480 (fix aspect ratio in stream)
    if grep -q 'LORES_RESOLUTION=' .env.production; then
        sed -i 's/^LORES_RESOLUTION=.*/LORES_RESOLUTION=640x480/' .env.production
    else
        echo 'LORES_RESOLUTION=640x480' >> .env.production
    fi && \
    # Fix REENTRY_TIME_THRESHOLD: 30.0 -> 10.0 (allow re-detection sooner)
    if grep -q 'REENTRY_TIME_THRESHOLD=' .env.production; then
        sed -i 's/^REENTRY_TIME_THRESHOLD=.*/REENTRY_TIME_THRESHOLD=10.0/' .env.production
    else
        echo 'REENTRY_TIME_THRESHOLD=10.0' >> .env.production
    fi"

echo "      ✅ .env.production updated"

# Verify new values
echo ""
echo "[5b] New .env.production values (after fix):"
ssh_run "grep -E 'DETECTION_INTERVAL|CONFIDENCE_THRESHOLD|LORES_RESOLUTION|MAIN_RESOLUTION|REENTRY_TIME' \
    ${AICAMERA2_DIR}/edge/installation/.env.production"

# Restart service
echo ""
echo "[6/7] Restarting ${SERVICE_NAME} service..."
ssh_run "sudo systemctl restart ${SERVICE_NAME}"
sleep 5
ssh_run "sudo systemctl status ${SERVICE_NAME} --no-pager -l | head -20"
echo "      ✅ Service restarted"

# Verify detection is running
echo ""
echo "[7/7] Verifying detection (watching logs for 15 seconds)..."
echo "      → Look for 'Detection interval' or 'Vehicle detected' messages"
ssh_run "timeout 15 journalctl -u ${SERVICE_NAME} -f --no-pager 2>/dev/null | \
    grep -E '(interval|detect|vehicle|plate|error|Error|WARNING)' || true"

echo ""
echo "=============================================="
echo " ✅ Fix Script Complete!"
echo "=============================================="
echo ""
echo "Fixes applied:"
echo "  1. ✅ video_streaming.py — RGB→BGR color conversion restored (git pull)"
echo "  2. ✅ DETECTION_INTERVAL: 30.0s → 0.5s  (detects every 0.5s, not 30s)"
echo "  3. ✅ DETECTION_CONFIDENCE_THRESHOLD: 0.8 → 0.65 (field-friendly)"
echo "  4. ✅ LORES_RESOLUTION: 640x640 → 640x480  (correct 4:3 aspect ratio)"
echo "  5. ✅ REENTRY_TIME_THRESHOLD: 30.0s → 10.0s"
echo ""
echo "Next steps:"
echo "  - Open stream: http://${AICAMERA2_HOST}:5000/stream"
echo "  - Check colors look normal (not red/blue swapped)"
echo "  - Check aspect ratio looks correct (not stretched/letterboxed)"
echo "  - Drive a car past the camera → should detect within 0.5s"
echo "  - Monitor logs: ssh ${AICAMERA2_USER}@${AICAMERA2_HOST}"
echo "    journalctl -u ${SERVICE_NAME} -f | grep -E '(detect|vehicle|plate|OCR)'"
echo ""
