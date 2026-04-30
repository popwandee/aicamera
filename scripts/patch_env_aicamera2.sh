#!/bin/bash
# =============================================================================
# Patch .env.production บน aicamera2 — รัน script นี้บนเครื่อง Mac ที่อยู่ใน Tailscale
# =============================================================================
# วิธีใช้:
#   chmod +x scripts/patch_env_aicamera2.sh
#   ./scripts/patch_env_aicamera2.sh
#
# หรือรันแบบ manual บน aicamera2:
#   ssh camuser@aicamera2
#   แล้ว copy-paste คำสั่งใน "MANUAL COMMANDS" ด้านล่าง
# =============================================================================

AICAMERA2="camuser@100.110.20.53"
ENV_FILE="/home/camuser/aicamera/edge/installation/.env.production"
SERVICE="aicamera_lpr"

echo "=== Patching aicamera2 .env.production ==="
echo ""

# Backup
echo "[1] Backup .env.production..."
ssh $AICAMERA2 "cp $ENV_FILE ${ENV_FILE}.bak.\$(date +%Y%m%d_%H%M%S)"

# Show current values
echo "[2] Current values:"
ssh $AICAMERA2 "grep -E 'DETECTION_INTERVAL|CONFIDENCE_THRESHOLD|LORES_RESOLUTION|MAIN_RESOLUTION|REENTRY_TIME' $ENV_FILE || echo 'Key not found'"

# Apply fixes
echo ""
echo "[3] Applying fixes..."
ssh $AICAMERA2 "
    # Fix 1: Detection interval 30s -> 0.5s (ROOT CAUSE fix)
    if grep -q '^DETECTION_INTERVAL=' $ENV_FILE; then
        sed -i 's|^DETECTION_INTERVAL=.*|DETECTION_INTERVAL=0.5|' $ENV_FILE
    else
        echo 'DETECTION_INTERVAL=0.5' >> $ENV_FILE
    fi
    echo 'DETECTION_INTERVAL=0.5 ✅'

    # Fix 2: Confidence threshold 0.8 -> 0.65
    if grep -q '^DETECTION_CONFIDENCE_THRESHOLD=' $ENV_FILE; then
        sed -i 's|^DETECTION_CONFIDENCE_THRESHOLD=.*|DETECTION_CONFIDENCE_THRESHOLD=0.65|' $ENV_FILE
    else
        echo 'DETECTION_CONFIDENCE_THRESHOLD=0.65' >> $ENV_FILE
    fi
    echo 'DETECTION_CONFIDENCE_THRESHOLD=0.65 ✅'

    # Fix 3: Lores resolution 640x640 -> 640x480 (4:3 aspect ratio)
    if grep -q '^LORES_RESOLUTION=' $ENV_FILE; then
        sed -i 's|^LORES_RESOLUTION=.*|LORES_RESOLUTION=640x480|' $ENV_FILE
    else
        echo 'LORES_RESOLUTION=640x480' >> $ENV_FILE
    fi
    echo 'LORES_RESOLUTION=640x480 ✅'

    # Fix 4: Reentry time 30s -> 10s
    if grep -q '^REENTRY_TIME_THRESHOLD=' $ENV_FILE; then
        sed -i 's|^REENTRY_TIME_THRESHOLD=.*|REENTRY_TIME_THRESHOLD=10.0|' $ENV_FILE
    else
        echo 'REENTRY_TIME_THRESHOLD=10.0' >> $ENV_FILE
    fi
    echo 'REENTRY_TIME_THRESHOLD=10.0 ✅'
"

# Verify new values
echo ""
echo "[4] New values after fix:"
ssh $AICAMERA2 "grep -E 'DETECTION_INTERVAL|CONFIDENCE_THRESHOLD|LORES_RESOLUTION|MAIN_RESOLUTION|REENTRY_TIME' $ENV_FILE"

# Pull latest code (with video_streaming.py fix)
echo ""
echo "[5] Pulling latest code (includes RGB->BGR fix in video_streaming.py)..."
ssh $AICAMERA2 "cd /home/camuser/aicamera && git pull origin main 2>&1 | tail -5"

# Restart service
echo ""
echo "[6] Restarting $SERVICE..."
ssh $AICAMERA2 "sudo systemctl restart $SERVICE"
sleep 6
ssh $AICAMERA2 "sudo systemctl status $SERVICE --no-pager | head -10"

# Tail logs
echo ""
echo "[7] Watching logs for 20 seconds..."
ssh $AICAMERA2 "timeout 20 journalctl -u $SERVICE -f --no-pager | grep -E '(interval|detect|vehicle|plate|Error|WARNING)'" || true

echo ""
echo "=== DONE ==="
echo "  Stream: http://100.110.20.53:5000/stream"
echo "  Dashboard: http://100.110.20.53:5000"
echo ""

# =============================================================================
# MANUAL COMMANDS (รันแบบ manual ถ้า script ข้างบนใช้ไม่ได้):
# =============================================================================
# ssh camuser@100.110.20.53
#
# cd /home/camuser/aicamera
# cp edge/installation/.env.production edge/installation/.env.production.bak
#
# # ดู current values:
# grep -E 'DETECTION_INTERVAL|CONFIDENCE' edge/installation/.env.production
#
# # แก้ไข:
# nano edge/installation/.env.production
# # หรือใช้ sed:
# sed -i 's|^DETECTION_INTERVAL=.*|DETECTION_INTERVAL=0.5|' edge/installation/.env.production
# sed -i 's|^DETECTION_CONFIDENCE_THRESHOLD=.*|DETECTION_CONFIDENCE_THRESHOLD=0.65|' edge/installation/.env.production
# sed -i 's|^LORES_RESOLUTION=.*|LORES_RESOLUTION=640x480|' edge/installation/.env.production
# sed -i 's|^REENTRY_TIME_THRESHOLD=.*|REENTRY_TIME_THRESHOLD=10.0|' edge/installation/.env.production
#
# # git pull (ดึงโค้ด fix RGB->BGR):
# git pull origin main
#
# # Restart:
# sudo systemctl restart aicamera_lpr
# sudo systemctl status aicamera_lpr
#
# # ดู logs:
# journalctl -u aicamera_lpr -f | grep -E '(detect|vehicle|plate|interval)'
