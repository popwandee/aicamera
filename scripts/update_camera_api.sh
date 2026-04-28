#!/bin/bash
# update_camera_api.sh — Update camera metadata in lprserver via REST API
# Phase 8: Field Test Preparation — Step 2
#
# Run this AFTER configure_camera.sh and after aicamera2 re-registers.
# Updates name, location address, GPS coordinates in the database.
#
# Usage:
#   bash scripts/update_camera_api.sh                    # list cameras, pick interactively
#   bash scripts/update_camera_api.sh <uuid>             # update specific camera
#   bash scripts/update_camera_api.sh <uuid> --from-env  # read values from aicamera2 .env.production

set -e

API_BASE="http://100.95.46.128/server/api"
CAM_USER="camuser"
CAM_IP="100.110.20.53"
PASS="admin88366"
ENV_FILE="/home/${CAM_USER}/aicamera/edge/installation/.env.production"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

ssh_cam() {
  sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    "${CAM_USER}@${CAM_IP}" "$@"
}

get_env_val() {
  ssh_cam "grep -E \"^${1}=\" '$ENV_FILE' 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\"'" \
    2>/dev/null || true
}

echo "============================================"
echo "Update Camera API Metadata"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "API: $API_BASE"
echo "============================================"

# ── Fetch camera list ─────────────────────────────────────────────────────────

echo ""
echo "Cameras currently in database:"
CAMERAS_JSON=$(curl -s --max-time 10 "$API_BASE/cameras" 2>/dev/null || echo "[]")
CAMERA_COUNT=$(echo "$CAMERAS_JSON" | python3 -c \
  "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

if [ "$CAMERA_COUNT" -eq 0 ]; then
  echo "  No cameras registered. Start aicamera_lpr service first:"
  echo "  ssh camuser@$CAM_IP 'sudo systemctl start aicamera_lpr'"
  exit 1
fi

echo "$CAMERAS_JSON" | python3 -c "
import sys, json
cameras = json.load(sys.stdin)
for i, c in enumerate(cameras):
    lat = c.get('locationLat'); lat = f'{lat:.6f}' if lat else 'null'
    lng = c.get('locationLng'); lng = f'{lng:.6f}' if lng else 'null'
    print(f'  [{i+1}] {c.get(\"id\")}')
    print(f'      cameraId={c.get(\"cameraId\")}  name={c.get(\"name\")}  status={c.get(\"status\")}')
    print(f'      lat={lat}  lng={lng}')
    print(f'      location={c.get(\"locationAddress\") or \"<not set>\"}')
    print()
" 2>/dev/null

# ── Determine target UUID ─────────────────────────────────────────────────────

TARGET_UUID="${1:-}"
FROM_ENV="${2:-}"

if [ -z "$TARGET_UUID" ]; then
  if [ "$CAMERA_COUNT" -eq 1 ]; then
    TARGET_UUID=$(echo "$CAMERAS_JSON" | python3 -c \
      "import sys,json; print(json.load(sys.stdin)[0]['id'])" 2>/dev/null)
    echo "Auto-selected only camera: $TARGET_UUID"
  else
    read -r -p "Enter camera UUID to update (or number 1-${CAMERA_COUNT}): " SEL || true
    if echo "$SEL" | grep -qE '^[0-9]$'; then
      IDX=$((SEL - 1))
      TARGET_UUID=$(echo "$CAMERAS_JSON" | python3 -c \
        "import sys,json; print(json.load(sys.stdin)[$IDX]['id'])" 2>/dev/null)
    else
      TARGET_UUID="$SEL"
    fi
  fi
fi

echo ""
echo "Target UUID: $TARGET_UUID"

# ── Get values (from .env or interactive) ─────────────────────────────────────

if [ "$FROM_ENV" = "--from-env" ]; then
  echo ""
  echo "Reading values from aicamera2 .env.production..."
  NAME=$(get_env_val "CAMERA_NAME")
  LOCATION=$(get_env_val "CAMERA_LOCATION")
  LAT=$(get_env_val "LOCATION_LAT")
  LNG=$(get_env_val "LOCATION_LON")
  echo "  CAMERA_NAME     = $NAME"
  echo "  CAMERA_LOCATION = $LOCATION"
  echo "  LOCATION_LAT    = $LAT"
  echo "  LOCATION_LON    = $LNG"
else
  echo ""
  echo "Enter values to update (press Enter to keep current):"

  # Get current values from API
  CURRENT_JSON=$(curl -s --max-time 10 "$API_BASE/cameras/$TARGET_UUID" 2>/dev/null || echo "{}")
  CUR_NAME=$(echo "$CURRENT_JSON" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('name',''))" 2>/dev/null || true)
  CUR_LOC=$(echo "$CURRENT_JSON" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('locationAddress') or '')" 2>/dev/null || true)
  CUR_LAT=$(echo "$CURRENT_JSON" | python3 -c \
    "import sys,json; v=json.load(sys.stdin).get('locationLat'); print(v if v else '')" 2>/dev/null || true)
  CUR_LNG=$(echo "$CURRENT_JSON" | python3 -c \
    "import sys,json; v=json.load(sys.stdin).get('locationLng'); print(v if v else '')" 2>/dev/null || true)

  read -r -p "  Camera Name     [${CUR_NAME}]: " INPUT_NAME || true
  NAME="${INPUT_NAME:-$CUR_NAME}"

  read -r -p "  Location        [${CUR_LOC}]: " INPUT_LOC || true
  LOCATION="${INPUT_LOC:-$CUR_LOC}"

  read -r -p "  Latitude        [${CUR_LAT}]: " INPUT_LAT || true
  LAT="${INPUT_LAT:-$CUR_LAT}"

  read -r -p "  Longitude       [${CUR_LNG}]: " INPUT_LNG || true
  LNG="${INPUT_LNG:-$CUR_LNG}"
fi

# Validate lat/lng are numbers
if [ -n "$LAT" ] && ! echo "$LAT" | grep -qE '^-?[0-9]+(\.[0-9]+)?$'; then
  echo "ERROR: Latitude '$LAT' is not a valid number."
  exit 1
fi
if [ -n "$LNG" ] && ! echo "$LNG" | grep -qE '^-?[0-9]+(\.[0-9]+)?$'; then
  echo "ERROR: Longitude '$LNG' is not a valid number."
  exit 1
fi

# Build JSON body — include only non-empty fields
BODY=$(python3 -c "
import json
data = {}
name     = '''$NAME'''
location = '''$LOCATION'''
lat      = '''$LAT'''
lng      = '''$LNG'''
if name:     data['name']            = name
if location: data['locationAddress'] = location
if lat:      data['locationLat']     = float(lat)
if lng:      data['locationLng']     = float(lng)
print(json.dumps(data, ensure_ascii=False))
" 2>/dev/null)

echo ""
echo "Request body:"
echo "  $BODY"
echo ""
read -r -p "Send PUT $API_BASE/cameras/$TARGET_UUID ? (y/n): " CONFIRM || true
[ "$CONFIRM" = "y" ] || { echo "Aborted."; exit 0; }

# ── Send PUT request ──────────────────────────────────────────────────────────

echo ""
echo "Sending update..."
RESPONSE=$(curl -s --max-time 15 \
  -X PUT "$API_BASE/cameras/$TARGET_UUID" \
  -H "Content-Type: application/json" \
  -d "$BODY" 2>/dev/null)

HTTP_OK=$(echo "$RESPONSE" | python3 -c \
  "import sys,json
d=json.load(sys.stdin)
print('ok' if 'id' in d else 'error')" 2>/dev/null || echo "error")

if [ "$HTTP_OK" = "ok" ]; then
  echo "  [OK] Camera updated successfully."
  echo ""
  echo "Updated record:"
  echo "$RESPONSE" | python3 -c "
import sys, json
c = json.load(sys.stdin)
lat = c.get('locationLat'); lat = f'{float(lat):.6f}' if lat else 'null'
lng = c.get('locationLng'); lng = f'{float(lng):.6f}' if lng else 'null'
print(f'  id           : {c.get(\"id\")}')
print(f'  cameraId     : {c.get(\"cameraId\")}')
print(f'  name         : {c.get(\"name\")}')
print(f'  locationAddr : {c.get(\"locationAddress\") or \"<not set>\"}')
print(f'  lat / lng    : {lat} / {lng}')
print(f'  status       : {c.get(\"status\")}')
print(f'  updatedAt    : {c.get(\"updatedAt\")}')
" 2>/dev/null
else
  echo "  [!!] Update may have failed. Response:"
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "  $RESPONSE"
fi

echo ""
echo "============================================"
echo "Done -- $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "Next steps:"
echo "  bash scripts/edge_health_check.sh    -- final readiness check"
echo "  bash scripts/verify_system.sh        -- full system verification"
echo "  View dashboard: http://100.95.46.128/server/cameras"
echo "============================================"
