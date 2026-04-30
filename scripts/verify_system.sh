#!/bin/bash
# verify_system.sh — Full system verification before/after field test
# Phase 7 Step 6 / Phase 8 Step 9
#
# Checks:
#   [A] lprserver — systemd services (backend-api, ws-service, mqtt-service, mosquitto, nginx, postgresql)
#   [B] API endpoints — HTTP 200 for all key routes
#   [C] WebSocket endpoint — socket.io polling handshake
#   [D] aicamera2 — Tailscale ping, SSH, service status, API reachability from edge
#   [E] Database — table counts
#
# Usage:
#   bash scripts/verify_system.sh           # full check
#   bash scripts/verify_system.sh --quick   # skip DB and edge SSH (faster)

set -e

QUICK="${1:-}"
LPR_USER="devuser"
LPR_IP="100.95.46.128"
CAM_USER="camuser"
CAM_IP_1="100.126.178.74"
CAM_IP_2="100.110.20.53"
PASS="admin88366"
API_BASE="http://${LPR_IP}/server/api"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

ssh_lpr() {
  sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    "${LPR_USER}@${LPR_IP}" "$@" 2>/dev/null
}

ssh_cam() {
  sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    "${CAM_USER}@${CAM_IP}" "$@" 2>/dev/null
}

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() { echo "  [PASS] $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "  [FAIL] $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
warn() { echo "  [WARN] $1"; WARN_COUNT=$((WARN_COUNT + 1)); }

echo "============================================"
echo "AI Camera LPR System Verification"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
if [ "$QUICK" = "--quick" ]; then
  echo "Mode: QUICK (skip DB and edge SSH)"
fi
echo "============================================"

# ── [A] lprserver Services ───────────────────────────────────────────────────

echo ""
echo "--- [A] lprserver Services ---"
echo "  Connecting to ${LPR_USER}@${LPR_IP}..."

SVC_STATUS=$(ssh_lpr "
  check_svc() {
    ST=\$(systemctl is-active \"\$1\" 2>/dev/null)
    [ -z \"\$ST\" ] && ST=unknown
    echo \"\$1=\$ST\"
  }
  check_svc backend-api
  check_svc websocket
  check_svc mqtt
  check_svc mosquitto
  check_svc nginx
  check_svc postgresql
" 2>/dev/null) || SVC_STATUS=""

if [ -z "$SVC_STATUS" ]; then
  fail "lprserver SSH: unreachable"
else
  while IFS="=" read -r svc status; do
    [ -z "$svc" ] && continue
    [[ "$svc" != *[a-z]* ]] && continue
    if [ "$status" = "active" ]; then
      pass "$svc: active"
    else
      fail "$svc: $status"
    fi
  done <<< "$SVC_STATUS"
fi

# ── [B] API Endpoints ────────────────────────────────────────────────────────

echo ""
echo "--- [B] API Endpoints ---"

check_http() {
  local label="$1" url="$2" expect="${3:-200}"
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$url" 2>/dev/null || echo "000")
  if [ "$CODE" = "$expect" ]; then
    pass "${label}: HTTP ${CODE}"
  elif [ "$CODE" = "000" ]; then
    fail "${label}: timeout / unreachable"
  else
    warn "${label}: HTTP ${CODE} (expected ${expect})"
  fi
}

check_http "GET /cameras"        "$API_BASE/cameras"
check_http "GET /detections"     "$API_BASE/detections?limit=1"
check_http "GET /camera-health"  "$API_BASE/camera-health?limit=1"
check_http "GET /analytics"      "$API_BASE/analytics"
check_http "GET /system-events"  "$API_BASE/system-events?limit=1"

# ── [C] WebSocket & Frontend ─────────────────────────────────────────────────

echo ""
echo "--- [C] WebSocket & Frontend ---"

check_http "WebSocket polling"    "http://${LPR_IP}/ws/socket.io/?EIO=4&transport=polling"
check_http "Dashboard SPA"        "http://${LPR_IP}/server/"
check_http "Landing page"         "http://${LPR_IP}/"

# Verify dashboard HTML has expected content
DASH_BODY=$(curl -s --max-time 8 "http://${LPR_IP}/server/" 2>/dev/null || true)
if echo "$DASH_BODY" | grep -qi "html"; then
  pass "Dashboard: HTML content present"
else
  warn "Dashboard: unexpected response body"
fi

# ── [D] aicamera1 ────────────────────────────────────────────────────────────

echo ""
echo "--- [D] aicamera1 Edge Device ---"

if ping -c 2 -W 2 "$CAM_IP_1" &>/dev/null 2>&1; then
  LATENCY=$(ping -c 2 -W 2 "$CAM_IP_1" 2>/dev/null | tail -1 | awk -F'/' '{printf "%.1f", $5}' 2>/dev/null || echo "?")
  pass "Tailscale ping ${CAM_IP_1}: ${LATENCY}ms"
else
  fail "Tailscale ping ${CAM_IP}: UNREACHABLE"
fi

if [ "$QUICK" != "--quick" ]; then
  # SSH access
  SSH_TEST=$(ssh_cam "echo ok" 2>/dev/null || echo "fail")
  if [ "$SSH_TEST" = "ok" ]; then
    pass "SSH to aicamera1: ok"
  else
    fail "SSH to aicamera1: failed"
  fi

  # aicamera_lpr service
  SVC_CAM=$(ssh_cam "systemctl is-active aicamera_lpr 2>/dev/null || echo unknown" 2>/dev/null || echo "ssh-fail")
  if [ "$SVC_CAM" = "active" ]; then
    pass "aicamera_lpr service: active"
  elif [ "$SVC_CAM" = "ssh-fail" ]; then
    warn "aicamera_lpr service: SSH unreachable (already checked above)"
  else
    warn "aicamera_lpr service: $SVC_CAM (start before field test)"
  fi

  # API reachability from edge
  API_FROM_EDGE=$(ssh_cam \
    "curl -s -o /dev/null -w '%{http_code}' --max-time 8 'http://100.95.46.128/server/api/cameras' 2>/dev/null || echo 000" \
    2>/dev/null || echo "000")
  if [ "$API_FROM_EDGE" = "200" ]; then
    pass "API reachable from aicamera1: HTTP 200"
  else
    fail "API reachable from aicamera1: HTTP $API_FROM_EDGE"
  fi
else
  warn "aicamera1 SSH checks: skipped (--quick)"
fi
# ── [E] aicamera2 ────────────────────────────────────────────────────────────

echo ""
echo "--- [E] aicamera2 Edge Device ---"

if ping -c 2 -W 2 "$CAM_IP_2" &>/dev/null 2>&1; then
  LATENCY=$(ping -c 2 -W 2 "$CAM_IP_2" 2>/dev/null | tail -1 | awk -F'/' '{printf "%.1f", $5}' 2>/dev/null || echo "?")
  pass "Tailscale ping ${CAM_IP_2}: ${LATENCY}ms"
else
  fail "Tailscale ping ${CAM_IP}: UNREACHABLE"
fi

if [ "$QUICK" != "--quick" ]; then
  # SSH access
  SSH_TEST=$(ssh_cam "echo ok" 2>/dev/null || echo "fail")
  if [ "$SSH_TEST" = "ok" ]; then
    pass "SSH to aicamera2: ok"
  else
    fail "SSH to aicamera2: failed"
  fi

  # aicamera_lpr service
  SVC_CAM=$(ssh_cam "systemctl is-active aicamera_lpr 2>/dev/null || echo unknown" 2>/dev/null || echo "ssh-fail")
  if [ "$SVC_CAM" = "active" ]; then
    pass "aicamera_lpr service: active"
  elif [ "$SVC_CAM" = "ssh-fail" ]; then
    warn "aicamera_lpr service: SSH unreachable (already checked above)"
  else
    warn "aicamera_lpr service: $SVC_CAM (start before field test)"
  fi

  # API reachability from edge
  API_FROM_EDGE=$(ssh_cam \
    "curl -s -o /dev/null -w '%{http_code}' --max-time 8 'http://100.95.46.128/server/api/cameras' 2>/dev/null || echo 000" \
    2>/dev/null || echo "000")
  if [ "$API_FROM_EDGE" = "200" ]; then
    pass "API reachable from aicamera2: HTTP 200"
  else
    fail "API reachable from aicamera2: HTTP $API_FROM_EDGE"
  fi
else
  warn "aicamera2 SSH checks: skipped (--quick)"
fi

# ── [F] Database Row Counts ──────────────────────────────────────────────────

echo ""
echo "--- [F] Database ---"

if [ "$QUICK" = "--quick" ]; then
  warn "Database check: skipped (--quick)"
else
  DB_OUT=$(ssh_lpr "PGPASSWORD=${PASS} psql -U lpruser -h 127.0.0.1 -p 5432 aicamera_app \
    --no-password -q -c \
    \"SELECT tablename, 0 FROM pg_tables WHERE schemaname='public' LIMIT 1;\"" 2>/dev/null || echo "fail")

  if echo "$DB_OUT" | grep -q "fail\|error\|FATAL"; then
    fail "PostgreSQL: connection failed"
  else
    DB_COUNTS=$(ssh_lpr "PGPASSWORD=${PASS} psql -U lpruser -h 127.0.0.1 -p 5432 aicamera_app \
      --no-password -At -c \
      \"SELECT 'cameras=' || COUNT(*) FROM cameras
        UNION ALL SELECT 'detections=' || COUNT(*) FROM detections
        UNION ALL SELECT 'camera_health=' || COUNT(*) FROM camera_health
        UNION ALL SELECT 'system_events=' || COUNT(*) FROM system_events;\"" 2>/dev/null || echo "")

    if [ -n "$DB_COUNTS" ]; then
      pass "PostgreSQL: connected"
      echo ""
      echo "  Table counts:"
      echo "$DB_COUNTS" | while IFS="=" read -r tbl cnt; do
        printf "    %-20s %s rows\n" "$tbl" "$cnt"
      done
    else
      warn "PostgreSQL: connected but query returned no rows"
    fi
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo "Verification Summary"
echo "  PASS: $PASS_COUNT   WARN: $WARN_COUNT   FAIL: $FAIL_COUNT"
echo "============================================"

if [ "$FAIL_COUNT" -eq 0 ] && [ "$WARN_COUNT" -eq 0 ]; then
  echo "  System READY for field test."
  EXIT_CODE=0
elif [ "$FAIL_COUNT" -eq 0 ]; then
  echo "  System has warnings — review before field test."
  EXIT_CODE=0
else
  echo "  FAILURES detected — fix before deployment!"
  EXIT_CODE=1
fi

echo "============================================"
echo "Done -- $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "Common fixes:"
  echo "  Services down   : ssh ${LPR_USER}@${LPR_IP} 'sudo systemctl restart <service>'"
  echo "  aicamera1 down  : bash scripts/edge_health_check.sh aicamera1"
  echo "  aicamera2 down  : bash scripts/edge_health_check.sh aicamera2"
  echo "  Camera config   : bash scripts/configure_camera.sh"
fi
echo "============================================"

exit $EXIT_CODE
