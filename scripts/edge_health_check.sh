#!/bin/bash
# edge_health_check.sh — Comprehensive health check for edge camera before field test
# Phase 8: Field Test Preparation
#
# Checks:
#   [1] Hardware   — CPU temp, throttle, memory, disk
#   [2] AI chip    — Hailo-8 detection and firmware version
#   [3] Camera     — IMX708 device availability
#   [4] Network    — Tailscale ping to lprserver, DNS
#   [5] Service    — aicamera_lpr active status, PID, last log lines
#   [6] Config     — .env.production key settings review
#   [7] Readiness  — PASS/FAIL summary for field deployment
#
# Usage:
#   bash scripts/edge_health_check.sh              # default: aicamera2
#   bash scripts/edge_health_check.sh aicamera1
#   bash scripts/edge_health_check.sh aicamera3

set -e

CAMERA="${1:-aicamera2}"
case "$CAMERA" in
  aicamera1) CAM_USER="camuser"; CAM_IP="100.126.178.74" ;;
  aicamera2) CAM_USER="camuser"; CAM_IP="100.110.20.53"  ;;
  aicamera3) CAM_USER="camuser"; CAM_IP="100.68.95.36"   ;;
  *) echo "Unknown camera: $CAMERA. Use aicamera1, aicamera2, or aicamera3."; exit 1 ;;
esac
PASS="admin88366"
LPRSERVER_IP="100.95.46.128"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

ssh_cam() {
  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    "${CAM_USER}@${CAM_IP}" "$@"
}

echo "============================================"
echo "${CAMERA} Health Check"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "Device : ${CAM_USER}@${CAM_IP}"
echo "============================================"

ssh_cam 'bash -s' <<'REMOTE'
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() { echo "  [PASS] $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "  [FAIL] $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
warn() { echo "  [WARN] $1"; WARN_COUNT=$((WARN_COUNT + 1)); }
info() { echo "         $1"; }

EDGE_BASE="/home/camuser/aicamera"

# ── [1] Hardware ──────────────────────────────────────────────────────────────
echo ""
echo "--- [1] Hardware ---"

# CPU temperature
TEMP_RAW=$(vcgencmd measure_temp 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' || echo "N/A")
if [ "$TEMP_RAW" != "N/A" ]; then
  TEMP_INT=${TEMP_RAW%.*}
  if [ "$TEMP_INT" -le 70 ]; then
    pass "CPU temp: ${TEMP_RAW}°C (OK ≤70°C)"
  elif [ "$TEMP_INT" -le 80 ]; then
    warn "CPU temp: ${TEMP_RAW}°C (elevated, check cooling)"
  else
    fail "CPU temp: ${TEMP_RAW}°C (CRITICAL >80°C)"
  fi
else
  warn "CPU temp: not available (vcgencmd missing?)"
fi

# Throttle status
THROTTLE=$(vcgencmd get_throttled 2>/dev/null || echo "N/A")
if echo "$THROTTLE" | grep -q "0x0$"; then
  pass "Throttle: 0x0 (no throttling)"
elif [ "$THROTTLE" = "N/A" ]; then
  warn "Throttle: not available"
else
  warn "Throttle: $THROTTLE (check power supply)"
fi

# Memory
MEM_INFO=$(free -m | grep Mem)
MEM_TOTAL=$(echo "$MEM_INFO" | awk '{print $2}')
MEM_USED=$(echo "$MEM_INFO" | awk '{print $3}')
MEM_PCT=$((MEM_USED * 100 / MEM_TOTAL))
if [ "$MEM_PCT" -le 80 ]; then
  pass "Memory: ${MEM_USED}/${MEM_TOTAL} MB (${MEM_PCT}%)"
else
  warn "Memory: ${MEM_USED}/${MEM_TOTAL} MB (${MEM_PCT}% — high)"
fi

# Disk
DISK_PCT=$(df / | tail -1 | awk '{gsub(/%/,""); print $5}')
DISK_FREE=$(df -h / | tail -1 | awk '{print $4}')
if [ "$DISK_PCT" -le 85 ]; then
  pass "Disk: ${DISK_PCT}% used, ${DISK_FREE} free"
elif [ "$DISK_PCT" -le 92 ]; then
  warn "Disk: ${DISK_PCT}% used, ${DISK_FREE} free (getting full)"
else
  fail "Disk: ${DISK_PCT}% used (CRITICAL — run edge_cleanup.sh)"
fi

# ── [2] Hailo-8 AI Chip ───────────────────────────────────────────────────────
echo ""
echo "--- [2] Hailo-8 AI Chip ---"

HAILO_INFO=$(hailortcli fw-control identify 2>/dev/null | strings 2>/dev/null || true)
if [ -n "$HAILO_INFO" ]; then
  FW_VER=$(echo "$HAILO_INFO" | grep -i "Firmware" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  ARCH=$(echo "$HAILO_INFO" | grep -i "Architecture\|HAILO" | grep -oE 'HAILO[0-9]+[A-Z]*' | head -1)
  pass "Hailo: detected  FW: ${FW_VER:-unknown}  Arch: ${ARCH:-unknown}"
elif ls /dev/hailo* &>/dev/null 2>&1; then
  warn "Hailo: device node found (/dev/hailo*) but fw-control unavailable"
else
  fail "Hailo: NOT detected (check PCIe connection and HailoRT install)"
fi

# ── [3] Camera ────────────────────────────────────────────────────────────────
echo ""
echo "--- [3] Camera ---"

if ls /dev/video0 &>/dev/null 2>&1; then
  pass "Camera: /dev/video0 present"
  CAM_INFO=$(libcamera-hello --list-cameras 2>&1 | head -5 | tr '\n' ' ')
  info "libcamera: $CAM_INFO"
else
  fail "Camera: /dev/video0 NOT found (check ribbon cable)"
fi

# ── [4] Network ───────────────────────────────────────────────────────────────
echo ""
echo "--- [4] Network ---"

# Tailscale status
if command -v tailscale &>/dev/null; then
  TS_STATUS=$(tailscale status 2>/dev/null | head -1 || echo "unknown")
  if echo "$TS_STATUS" | grep -qi "aicamera2"; then
    pass "Tailscale: connected"
  else
    warn "Tailscale: $TS_STATUS"
  fi
else
  warn "Tailscale: CLI not found"
fi

# Ping lprserver
if ping -c 2 -W 2 100.95.46.128 &>/dev/null 2>&1; then
  LATENCY=$(ping -c 2 -W 2 100.95.46.128 2>/dev/null | tail -1 | awk -F'/' '{print $5}')
  if [ -n "$LATENCY" ]; then
    LATENCY_INT=${LATENCY%.*}
    if [ "$LATENCY_INT" -le 100 ]; then
      pass "Ping lprserver: ${LATENCY}ms avg"
    else
      warn "Ping lprserver: ${LATENCY}ms (high latency)"
    fi
  else
    pass "Ping lprserver: reachable"
  fi
else
  fail "Ping lprserver (100.95.46.128): UNREACHABLE"
fi

# HTTP to lprserver API
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  "http://100.95.46.128/server/api/cameras" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  pass "API reachable: GET /server/api/cameras → 200"
elif [ "$HTTP_CODE" = "000" ]; then
  fail "API unreachable: http://100.95.46.128/server/api/cameras (timeout/refused)"
else
  warn "API response: HTTP $HTTP_CODE"
fi

# WebSocket endpoint
WS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
  "http://100.95.46.128/ws/socket.io/?EIO=4&transport=polling" 2>/dev/null || echo "000")
if [ "$WS_CODE" = "200" ]; then
  pass "WebSocket endpoint: /ws/ → 200"
else
  warn "WebSocket endpoint: HTTP $WS_CODE"
fi

# ── [5] Service ───────────────────────────────────────────────────────────────
echo ""
echo "--- [5] Service: aicamera_lpr ---"

SVC_STATUS=$(systemctl is-active aicamera_lpr 2>/dev/null || echo "unknown")
if [ "$SVC_STATUS" = "active" ]; then
  pass "aicamera_lpr: active (running)"
  MAIN_PID=$(systemctl show aicamera_lpr --property=MainPID --value 2>/dev/null)
  info "PID: $MAIN_PID"
  info "Recent restarts: $(systemctl show aicamera_lpr --property=NRestarts --value 2>/dev/null || echo N/A)"
elif [ "$SVC_STATUS" = "inactive" ]; then
  warn "aicamera_lpr: inactive (not running — start before field test)"
  info "Start with: sudo systemctl start aicamera_lpr"
else
  fail "aicamera_lpr: $SVC_STATUS"
fi

echo "  Last 5 log lines:"
journalctl -u aicamera_lpr -n 5 --no-pager 2>/dev/null | sed 's/^/    /' || \
  tail -5 /home/camuser/aicamera/edge/logs/aicamera.log 2>/dev/null | sed 's/^/    /' || \
  echo "    (no log available)"

# ── [6] Config review ─────────────────────────────────────────────────────────
echo ""
echo "--- [6] Config: .env.production ---"

ENV_FILE="/home/camuser/aicamera/edge/installation/.env.production"

check_env() {
  local KEY="$1" LABEL="$2"
  # Get LAST occurrence of key (effective value when file has duplicates)
  VAL=$(grep -E "^${KEY}=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"')
  if [ -n "$VAL" ] && [ "$VAL" != "your-secret-key-here-change-in-production" ]; then
    pass "${LABEL}: ${VAL}"
  else
    fail "${LABEL}: NOT SET (required before field test)"
  fi
}

check_env "AICAMERA_ID"    "AICAMERA_ID"
check_env "SERVER_URL"     "SERVER_URL"
check_env "MQTT_BROKER_HOST" "MQTT_BROKER_HOST"

# Check WEBSOCKET_SERVER_URL (must not be empty)
WS_URL=$(grep -E "^WEBSOCKET_SERVER_URL=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"')
if [ -n "$WS_URL" ]; then
  pass "WEBSOCKET_SERVER_URL: $WS_URL"
else
  fail "WEBSOCKET_SERVER_URL: EMPTY (last occurrence is blank — fix .env.production)"
fi

# CAMERA_NAME (for dashboard display)
CAM_NAME=$(grep -E "^CAMERA_NAME=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"')
if [ -n "$CAM_NAME" ]; then
  pass "CAMERA_NAME: $CAM_NAME"
else
  warn "CAMERA_NAME: not set (will show as default in dashboard)"
fi

# Warn about duplicate keys
DUP_COUNT=$(grep -c "^WEBSOCKET_SERVER_URL=" "$ENV_FILE" 2>/dev/null) || DUP_COUNT=0
if [ "$DUP_COUNT" -gt 1 ]; then
  warn ".env.production has $DUP_COUNT WEBSOCKET_SERVER_URL entries (duplicates — run configure_camera.sh to fix)"
fi
DUP_COUNT2=$(grep -c "^SERVER_URL=" "$ENV_FILE" 2>/dev/null) || DUP_COUNT2=0
if [ "$DUP_COUNT2" -gt 1 ]; then
  warn ".env.production has $DUP_COUNT2 SERVER_URL entries (duplicates — run configure_camera.sh to fix)"
fi

# ── [7] Readiness summary ─────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "Readiness Summary"
echo "  PASS: $PASS_COUNT   WARN: $WARN_COUNT   FAIL: $FAIL_COUNT"
echo "============================================"
if [ "$FAIL_COUNT" -eq 0 ] && [ "$WARN_COUNT" -eq 0 ]; then
  echo "  ✔ Device READY for field test"
elif [ "$FAIL_COUNT" -eq 0 ]; then
  echo "  ~ Device has warnings — review before field test"
else
  echo "  ✗ Device NOT ready — fix FAIL items before deployment"
fi
echo "============================================"
REMOTE

echo ""
echo "Health check complete -- $(date '+%Y-%m-%d %H:%M:%S')"
