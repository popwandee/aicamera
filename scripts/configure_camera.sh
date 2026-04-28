#!/bin/bash
# configure_camera.sh — Configure edge camera before field test
# Phase 8: Field Test Preparation — Step 1
#
# What this does:
#   1. Show current .env.production config
#   2. Prompt for camera metadata (name, location, GPS, thresholds)
#   3. Write to .env.production — removes ALL duplicate keys before writing
#   4. Restart aicamera_lpr service (via sudo, NOPASSWD on device)
#   5. Verify service started and show registration in API
#
# Usage:
#   bash scripts/configure_camera.sh [aicamera1|aicamera2|aicamera3]

set -e

CAMERA="${1:-aicamera2}"
case "$CAMERA" in
  aicamera1) CAM_USER="camuser"; CAM_IP="100.126.178.74"; CAM_NUM="1" ;;
  aicamera2) CAM_USER="camuser"; CAM_IP="100.110.20.53";  CAM_NUM="2" ;;
  aicamera3) CAM_USER="camuser"; CAM_IP="100.68.95.36";   CAM_NUM="3" ;;
  *) echo "Unknown camera: $CAMERA. Use aicamera1, aicamera2, or aicamera3."; exit 1 ;;
esac

PASS="admin88366"
ENV_FILE="/home/${CAM_USER}/aicamera/edge/installation/.env.production"
API_BASE="http://100.95.46.128/server/api"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

ssh_cam() {
  sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    "${CAM_USER}@${CAM_IP}" "$@"
}

echo "============================================"
echo "Camera Configuration — $CAMERA"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "Device : ${CAM_USER}@${CAM_IP}"
echo "============================================"

# ── Show current config ───────────────────────────────────────────────────────

echo ""
echo "Current .env.production (key settings, last-occurrence wins):"
ssh_cam "
  ENV='$ENV_FILE'
  show_last() {
    VAL=\$(grep -E \"^\${1}=\" \"\$ENV\" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\"')
    COUNT=\$(grep -cE \"^\${1}=\" \"\$ENV\" 2>/dev/null) || COUNT=0
    DUP=''
    [ \"\$COUNT\" -gt 1 ] && DUP=\" *** \${COUNT}x DUPLICATE ***\"
    printf '  %-30s = %s%s\n' \"\$1\" \"\${VAL:-<not set>}\" \"\$DUP\"
  }
  show_last AICAMERA_ID
  show_last CHECKPOINT_ID
  show_last CAMERA_NAME
  show_last CAMERA_LOCATION
  show_last LOCATION_LAT
  show_last LOCATION_LON
  show_last SERVER_URL
  show_last WEBSOCKET_SERVER_URL
  show_last MQTT_BROKER_HOST
  show_last DETECTION_CONFIDENCE_THRESHOLD
  show_last PLATE_CONFIDENCE_THRESHOLD
"

# ── Collect new values ────────────────────────────────────────────────────────

echo ""
echo "Enter new values (press Enter to keep current):"
echo ""

get_val() {
  local KEY="$1" PROMPT="$2" DEFAULT="$3"
  local CURRENT
  CURRENT=$(sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "${CAM_USER}@${CAM_IP}" \
    "grep -E \"^${KEY}=\" '$ENV_FILE' 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\"'" 2>/dev/null || true)
  local SHOW="${CURRENT:-${DEFAULT}}"
  read -r -p "  $PROMPT [${SHOW}]: " INPUT || true
  if [ -n "$INPUT" ]; then
    echo "$INPUT"
  else
    echo "${CURRENT:-${DEFAULT}}"
  fi
}

CAMERA_NAME=$(get_val "CAMERA_NAME" "Camera Name (Thai OK, e.g. กล้อง 1 ถนนสุขุมวิท)" "AI Camera")
CAMERA_LOCATION=$(get_val "CAMERA_LOCATION" "Location (e.g. ถนนสุขุมวิท กม.5 ขาเข้า)" "Test Location")
LOCATION_LAT=$(get_val "LOCATION_LAT" "Latitude  (xx.xxxxxx from Google Maps)" "13.729610")
LOCATION_LON=$(get_val "LOCATION_LON" "Longitude (xxx.xxxxxx from Google Maps)" "100.501443")
DETECTION_CONF=$(get_val "DETECTION_CONFIDENCE_THRESHOLD" "Vehicle Confidence Threshold (0.0-1.0)" "0.75")
PLATE_CONF=$(get_val "PLATE_CONFIDENCE_THRESHOLD" "Plate Confidence Threshold (0.0-1.0)" "0.5")

echo ""
echo "============================================"
echo "Preview — values to write:"
printf "  %-35s = %s\n" "CAMERA_NAME"                      "$CAMERA_NAME"
printf "  %-35s = %s\n" "CAMERA_LOCATION"                  "$CAMERA_LOCATION"
printf "  %-35s = %s\n" "LOCATION_LAT"                     "$LOCATION_LAT"
printf "  %-35s = %s\n" "LOCATION_LON"                     "$LOCATION_LON"
printf "  %-35s = %s\n" "DETECTION_CONFIDENCE_THRESHOLD"   "$DETECTION_CONF"
printf "  %-35s = %s\n" "PLATE_CONFIDENCE_THRESHOLD"       "$PLATE_CONF"
echo ""
echo "Also will fix duplicate keys:"
echo "  SERVER_URL, WEBSOCKET_SERVER_URL, AICAMERA_ID, CHECKPOINT_ID"
echo "============================================"
echo ""
read -r -p "Apply and restart service? (y/n): " CONFIRM || true
[ "$CONFIRM" = "y" ] || { echo "Aborted."; exit 0; }

# ── Apply config ──────────────────────────────────────────────────────────────

echo ""
echo "Applying config to $ENV_FILE..."

# Backup first
ssh_cam "cp '$ENV_FILE' '${ENV_FILE}.bak.\$(date +%Y%m%d_%H%M%S)'"
echo "  Backup created."

# update_env: remove ALL occurrences of KEY then append KEY=VALUE
# This cleans up duplicates automatically
ssh_cam "
  ENV='$ENV_FILE'

  update_env() {
    local KEY=\"\$1\" VAL=\"\$2\"
    # Remove all existing lines for this key (quoted or unquoted)
    sed -i \"/^[[:space:]]*\${KEY}=/d\" \"\$ENV\"
    # Ensure file ends with a newline before appending (guards against files
    # with no trailing newline, which would embed the new key in the last line)
    echo >> \"\$ENV\"
    echo \"\${KEY}=\${VAL}\" >> \"\$ENV\"
  }

  # Fix connection URLs (ensure correct values, no duplicates)
  update_env SERVER_URL               'http://100.95.46.128'
  update_env WEBSOCKET_SERVER_URL     'http://100.95.46.128/ws/'
  update_env MQTT_BROKER_HOST         '100.95.46.128'
  update_env MQTT_BROKER_PORT         '1883'
  update_env WEBSOCKET_ENABLED        'true'

  # Camera identity
  update_env AICAMERA_ID              '$CAM_NUM'
  update_env CHECKPOINT_ID            '$CAM_NUM'

  # Camera metadata (user-supplied)
  update_env CAMERA_NAME              '$CAMERA_NAME'
  update_env CAMERA_LOCATION          '$CAMERA_LOCATION'
  update_env LOCATION_LAT             '$LOCATION_LAT'
  update_env LOCATION_LON             '$LOCATION_LON'

  # Detection thresholds
  update_env DETECTION_CONFIDENCE_THRESHOLD  '$DETECTION_CONF'
  update_env PLATE_CONFIDENCE_THRESHOLD      '$PLATE_CONF'

  echo 'Config written.'
"

# Verify written values
echo ""
echo "Verifying written config:"
ssh_cam "
  ENV='$ENV_FILE'
  show_last() {
    VAL=\$(grep -E \"^\${1}=\" \"\$ENV\" | tail -1 | cut -d= -f2-)
    CNT=\$(grep -cE \"^\${1}=\" \"\$ENV\" 2>/dev/null) || CNT=0
    WARN=''; [ \"\$CNT\" -gt 1 ] && WARN=' *** STILL DUPLICATE ***'
    printf '  %-35s = %s%s\n' \"\$1\" \"\$VAL\" \"\$WARN\"
  }
  show_last CAMERA_NAME
  show_last CAMERA_LOCATION
  show_last LOCATION_LAT
  show_last SERVER_URL
  show_last WEBSOCKET_SERVER_URL
  show_last DETECTION_CONFIDENCE_THRESHOLD
"

# ── Restart service ───────────────────────────────────────────────────────────

echo ""
echo "Restarting aicamera_lpr service..."
ssh_cam "sudo systemctl restart aicamera_lpr"
echo "  Restart command sent."
echo "  Waiting 5s for service to come up..."
sleep 5

SVC_STATUS=$(ssh_cam "systemctl is-active aicamera_lpr 2>/dev/null || echo 'unknown'")
if [ "$SVC_STATUS" = "active" ]; then
  echo "  [OK] Service is active."
else
  echo "  [!!] Service status: $SVC_STATUS"
  echo "  Last log:"
  ssh_cam "journalctl -u aicamera_lpr -n 10 --no-pager 2>/dev/null | tail -10" || true
fi

# ── Wait for camera registration ──────────────────────────────────────────────

echo ""
echo "Waiting for camera to register with lprserver (up to 30s)..."
for i in $(seq 1 6); do
  sleep 5
  CAM_COUNT=$(curl -s "$API_BASE/cameras" 2>/dev/null | python3 -c \
    "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
  if [ "$CAM_COUNT" -gt 0 ]; then
    echo "  Camera registered! ($CAM_COUNT camera(s) in DB)"
    break
  fi
  echo "  Attempt $i/6: no cameras yet..."
done

# Show cameras in API
echo ""
echo "Cameras currently in API:"
curl -s "$API_BASE/cameras" 2>/dev/null | python3 -c "
import sys, json
cameras = json.load(sys.stdin)
for c in cameras:
    uid  = c.get('id','?')
    cid  = c.get('cameraId','?')
    name = c.get('name','?')
    stat = c.get('status','?')
    lat  = c.get('locationLat','null')
    lng  = c.get('locationLng','null')
    print(f'  UUID: {uid}')
    print(f'  cameraId: {cid}  name: {name}  status: {stat}')
    print(f'  lat: {lat}  lng: {lng}')
    print()
" 2>/dev/null || echo "  (could not parse cameras)"

# ── Done ──────────────────────────────────────────────────────────────────────

echo "============================================"
echo "Configuration complete -- $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "Next steps:"
echo "  bash scripts/update_camera_api.sh         -- sync metadata to DB"
echo "  bash scripts/edge_health_check.sh         -- final readiness check"
echo "  bash scripts/verify_system.sh             -- full system check"
echo "============================================"
