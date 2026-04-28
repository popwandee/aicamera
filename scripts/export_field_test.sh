#!/bin/bash
# export_field_test.sh — Export field test data from lprserver
# Phase 8: Field Test — Step 12 (run after field test session)
#
# Exports:
#   1. detections.json       — all detections via API
#   2. camera_health.json    — health records via API
#   3. cameras.json          — camera list with status
#   4. stats.txt             — summary stats via PostgreSQL
#   5. images/               — detection images via rsync
#
# Usage:
#   bash scripts/export_field_test.sh               # today's date
#   bash scripts/export_field_test.sh 2026-04-27    # specific date

set -e

EXPORT_DATE="${1:-$(date +%Y-%m-%d)}"
EXPORT_DIR="$HOME/field_test_exports/$EXPORT_DATE"
API_BASE="http://100.95.46.128/server/api"
LPR_USER="devuser"
LPR_IP="100.95.46.128"
PASS="admin88366"
STORAGE_PATH="/home/devuser/aicamera/server/storage"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

rsync_lpr() {
  sshpass -p "$PASS" rsync -e "ssh -o StrictHostKeyChecking=no" "$@"
}

ssh_lpr() {
  sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    "${LPR_USER}@${LPR_IP}" "$@"
}

echo "============================================"
echo "Field Test Data Export"
echo "Date: $EXPORT_DATE"
echo "Export dir: $EXPORT_DIR"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

mkdir -p "$EXPORT_DIR"

# ── 1. Detections ─────────────────────────────────────────────────────────────

echo ""
echo "[1] Downloading detections..."
DET_JSON=$(curl -s --max-time 30 \
  "$API_BASE/detections?limit=5000&sortBy=createdAt&sortOrder=ASC" 2>/dev/null || echo "[]")
echo "$DET_JSON" > "$EXPORT_DIR/detections_${EXPORT_DATE}.json"
DET_COUNT=$(echo "$DET_JSON" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); \
   print(len(d) if isinstance(d,list) else len(d.get('data',[])))" 2>/dev/null || echo "?")
echo "  → detections_${EXPORT_DATE}.json  ($DET_COUNT records)"

# ── 2. Camera Health ──────────────────────────────────────────────────────────

echo ""
echo "[2] Downloading camera health..."
HEALTH_JSON=$(curl -s --max-time 30 \
  "$API_BASE/camera-health?limit=5000&sortBy=createdAt&sortOrder=ASC" 2>/dev/null || echo "[]")
echo "$HEALTH_JSON" > "$EXPORT_DIR/camera_health_${EXPORT_DATE}.json"
HEALTH_COUNT=$(echo "$HEALTH_JSON" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); \
   print(len(d) if isinstance(d,list) else len(d.get('data',[])))" 2>/dev/null || echo "?")
echo "  → camera_health_${EXPORT_DATE}.json  ($HEALTH_COUNT records)"

# ── 3. Cameras ────────────────────────────────────────────────────────────────

echo ""
echo "[3] Downloading camera list..."
curl -s --max-time 15 "$API_BASE/cameras" 2>/dev/null \
  > "$EXPORT_DIR/cameras_${EXPORT_DATE}.json" || echo "[]" > "$EXPORT_DIR/cameras_${EXPORT_DATE}.json"
echo "  → cameras_${EXPORT_DATE}.json"

# ── 4. PostgreSQL Stats ───────────────────────────────────────────────────────

echo ""
echo "[4] Generating stats via PostgreSQL..."
ssh_lpr "PGPASSWORD=${PASS} psql -U lpruser -h 127.0.0.1 -p 5432 aicamera_app \
  --no-password -q -c \
  \"SELECT
      COUNT(*)                                                          AS total_detections,
      COUNT(CASE WHEN CAST(confidence AS FLOAT) >= 0.9 THEN 1 END)    AS conf_90_plus,
      COUNT(CASE WHEN CAST(confidence AS FLOAT) >= 0.8 THEN 1 END)    AS conf_80_plus,
      COUNT(CASE WHEN CAST(confidence AS FLOAT) >= 0.7 THEN 1 END)    AS conf_70_plus,
      COUNT(CASE WHEN license_plate IS NOT NULL
                  AND license_plate != '' THEN 1 END)                  AS with_plate,
      ROUND(AVG(CAST(confidence AS FLOAT))::numeric, 4)               AS avg_confidence,
      COUNT(DISTINCT license_plate)                                     AS unique_plates,
      MIN(created_at)                                                   AS first_detection,
      MAX(created_at)                                                   AS last_detection
    FROM detections;\"" > "$EXPORT_DIR/stats_${EXPORT_DATE}.txt" 2>&1 || \
  echo "(stats unavailable — SSH/DB error)" > "$EXPORT_DIR/stats_${EXPORT_DATE}.txt"

# Also capture per-camera counts
ssh_lpr "PGPASSWORD=${PASS} psql -U lpruser -h 127.0.0.1 -p 5432 aicamera_app \
  --no-password -q -c \
  \"SELECT camera_id, COUNT(*) AS detections, COUNT(DISTINCT license_plate) AS unique_plates
    FROM detections GROUP BY camera_id ORDER BY camera_id;\"" \
  >> "$EXPORT_DIR/stats_${EXPORT_DATE}.txt" 2>&1 || true

echo "  → stats_${EXPORT_DATE}.txt"
cat "$EXPORT_DIR/stats_${EXPORT_DATE}.txt" | sed 's/^/  /'

# ── 5. Detection Images ───────────────────────────────────────────────────────

echo ""
echo "[5] Downloading detection images..."
IMG_DIR="$EXPORT_DIR/images"
mkdir -p "$IMG_DIR"

REMOTE_COUNT=$(ssh_lpr "find '${STORAGE_PATH}' -name '*.jpg' 2>/dev/null | wc -l | tr -d ' '" 2>/dev/null || echo 0)
echo "  Remote image count: $REMOTE_COUNT"

if [ "$REMOTE_COUNT" -gt 0 ]; then
  rsync_lpr -az --ignore-existing --progress \
    "${LPR_USER}@${LPR_IP}:${STORAGE_PATH}/" \
    "${IMG_DIR}/" 2>/dev/null || echo "  [WARN] rsync partial or failed"
  LOCAL_COUNT=$(find "$IMG_DIR" -name "*.jpg" 2>/dev/null | wc -l | tr -d ' ')
  echo "  → images/  ($LOCAL_COUNT / $REMOTE_COUNT files)"
else
  echo "  No images found on lprserver storage."
fi

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo "Export Complete"
TOTAL_SIZE=$(du -sh "$EXPORT_DIR" 2>/dev/null | cut -f1 || echo "?")
echo "  Directory : $EXPORT_DIR"
echo "  Total size: $TOTAL_SIZE"
echo ""
echo "Files exported:"
ls -lh "$EXPORT_DIR/" 2>/dev/null | grep -v '^total' | sed 's/^/  /' || true
echo ""
echo "Next steps:"
echo "  python3 scripts/evaluate_accuracy.py $EXPORT_DIR/detections_${EXPORT_DATE}.json"
echo "  View dashboard: http://100.95.46.128/server/detections"
echo "============================================"
echo "Done -- $(date '+%Y-%m-%d %H:%M:%S')"
