#!/bin/bash
# monitor_field_test.sh — Real-time monitoring dashboard during field test
# Phase 8: Field Test — Step 11 (run while camera is deployed)
#
# Usage:
#   bash scripts/monitor_field_test.sh          # refresh every 10s
#   bash scripts/monitor_field_test.sh 30       # refresh every 30s
#   bash scripts/monitor_field_test.sh 5 <uuid> # refresh 5s, filter one camera

set -e

INTERVAL="${1:-10}"
CAMERA_UUID="${2:-}"
API_BASE="http://100.95.46.128/server/api"
CAM_IP="100.110.20.53"

# ── helpers ───────────────────────────────────────────────────────────────────

api_get() {
  curl -s --max-time 8 "$API_BASE/$1" 2>/dev/null
}

count_in_response() {
  echo "$1" | python3 -c \
    "import sys,json
d=json.load(sys.stdin)
if isinstance(d,list): print(len(d))
elif isinstance(d,dict) and 'data' in d: print(len(d['data']))
else: print('?')" 2>/dev/null || echo "?"
}

# ── main loop ─────────────────────────────────────────────────────────────────

TRAP_FIRED=0
trap 'TRAP_FIRED=1' INT TERM

while [ "$TRAP_FIRED" -eq 0 ]; do
  clear
  echo "============================================"
  echo "AI Camera LPR — Field Test Monitor"
  echo "$(date '+%Y-%m-%d %H:%M:%S')  (refresh: ${INTERVAL}s)"
  echo "API: $API_BASE"
  echo "============================================"

  # ── [1] Cameras ──────────────────────────────────────────────────────────────

  echo ""
  echo "--- [1] Cameras ---"
  CAM_JSON=$(api_get "cameras")
  echo "$CAM_JSON" | python3 -c "
import sys, json
try:
  cams = json.load(sys.stdin)
  if not isinstance(cams, list): cams = cams.get('data', [])
  if not cams:
    print('  (no cameras registered)')
  for c in cams:
    cid    = c.get('cameraId', '?')
    name   = c.get('name', '?')
    status = c.get('status', '?')
    flag   = '✓' if status in ('active','online','connected') else '✗'
    print(f'  [{flag}] cam:{cid}  {name:<20}  status:{status}')
except Exception as e:
  print(f'  (parse error: {e})')
" 2>/dev/null || echo "  (API unreachable)"

  # ── [2] Detection Totals ──────────────────────────────────────────────────────

  echo ""
  echo "--- [2] Detection Count ---"
  if [ -n "$CAMERA_UUID" ]; then
    DET_URL="detections?cameraId=${CAMERA_UUID}&limit=1000"
  else
    DET_URL="detections?limit=1000"
  fi
  DET_JSON=$(api_get "$DET_URL")
  TOTAL=$(count_in_response "$DET_JSON")
  echo "  Total detections in DB: $TOTAL"

  # Count last hour
  HOUR_AGO=$(python3 -c \
    "from datetime import datetime,timedelta,timezone; \
     print((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()[:19])" 2>/dev/null)
  DET_1H_JSON=$(api_get "detections?limit=500&startDate=${HOUR_AGO}")
  LAST_HOUR=$(count_in_response "$DET_1H_JSON")
  echo "  Detections last hour:   $LAST_HOUR"

  # ── [3] Latest Detections ─────────────────────────────────────────────────────

  echo ""
  echo "--- [3] Latest 8 Detections ---"
  LATEST_JSON=$(api_get "detections?limit=8&sortBy=createdAt&sortOrder=DESC")
  echo "$LATEST_JSON" | python3 -c "
import sys, json
try:
  data = json.load(sys.stdin)
  if isinstance(data, dict): data = data.get('data', [])
  if not data:
    print('  (none yet)')
  for d in data[:8]:
    plate = d.get('licensePlate') or d.get('license_plate') or ''
    plate = plate.strip() if plate else '—'
    conf  = d.get('confidence', 0)
    try:    pct = f'{float(conf)*100:.1f}%'
    except: pct = str(conf)
    ts = d.get('createdAt') or d.get('timestamp') or ''
    ts = ts[:19].replace('T',' ') if ts else '?'
    img = '📷' if d.get('imagePath') or d.get('image_path') else '  '
    print(f'  {ts}  {plate:<15}  conf:{pct:<7}  {img}')
except Exception as e:
  print(f'  (parse error: {e})')
" 2>/dev/null || echo "  (API unreachable)"

  # ── [4] Camera Health ─────────────────────────────────────────────────────────

  echo ""
  echo "--- [4] Camera Health (latest) ---"
  HEALTH_JSON=$(api_get "camera-health?limit=10&sortBy=createdAt&sortOrder=DESC")
  echo "$HEALTH_JSON" | python3 -c "
import sys, json
try:
  data = json.load(sys.stdin)
  if isinstance(data, dict): data = data.get('data', [])
  seen = set()
  for h in data[:20]:
    cid = h.get('cameraId') or h.get('camera_id') or '?'
    if cid in seen: continue
    seen.add(cid)
    cpu  = h.get('cpuUsage')  or h.get('cpu_usage')  or '?'
    temp = h.get('temperature') or '?'
    mem  = h.get('memoryUsage') or h.get('memory_usage') or '?'
    ts   = h.get('createdAt') or h.get('timestamp') or ''
    ts   = ts[:19].replace('T',' ') if ts else '?'
    try:    cpu_s  = f'{float(cpu):.1f}%'
    except: cpu_s  = str(cpu)
    try:    temp_s = f'{float(temp):.1f}°C'
    except: temp_s = str(temp)
    try:    mem_s  = f'{float(mem):.1f}%'
    except: mem_s  = str(mem)
    print(f'  cam:{cid}  CPU:{cpu_s:<7}  Temp:{temp_s:<8}  Mem:{mem_s:<7}  @ {ts}')
  if not seen:
    print('  (no health data yet)')
except Exception as e:
  print(f'  (parse error: {e})')
" 2>/dev/null || echo "  (API unreachable)"

  # ── [5] Network Ping ──────────────────────────────────────────────────────────

  echo ""
  echo "--- [5] Network ---"
  if ping -c 1 -W 2 "$CAM_IP" &>/dev/null 2>&1; then
    LATENCY=$(ping -c 2 -W 2 "$CAM_IP" 2>/dev/null | tail -1 | awk -F'/' '{printf "%.1f", $5}' 2>/dev/null || echo "?")
    echo "  aicamera2 ping: ${LATENCY}ms"
  else
    echo "  aicamera2 ping: UNREACHABLE ⚠"
  fi

  API_HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    "$API_BASE/cameras" 2>/dev/null || echo "000")
  echo "  API status:     HTTP $API_HTTP"

  # ── footer ───────────────────────────────────────────────────────────────────

  echo ""
  echo "============================================"
  echo "Press Ctrl+C to stop. Next refresh in ${INTERVAL}s..."
  sleep "$INTERVAL"
done

echo ""
echo "Monitor stopped."
