#!/bin/bash
# db_cleanup.sh — Delete all test data from lprserver database
# Phase 7: Data Backup & Cleanup — Step 4
#
# Truncates: detections, camera_health, analytics, analytics_events,
#            system_events, visualizations
# Preserves: cameras table (shows contents for review before optional delete)
#
# Usage: bash scripts/db_cleanup.sh
# ⚠️  Run backup_data.sh AND db_pre_cleanup_report.sh FIRST
# ⚠️  IRREVERSIBLE — ensure backup is verified before proceeding

set -e

LPR_USER="devuser"
LPR_IP="100.95.46.128"
PASS="admin88366"
DB_USER="lpruser"
DB_NAME="aicamera_app"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

ssh_lpr() {
  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    "${LPR_USER}@${LPR_IP}" "$@"
}

echo "============================================"
echo "Database Cleanup — lprserver"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "Server: ${LPR_USER}@${LPR_IP}  DB: ${DB_NAME}"
echo "============================================"
echo ""
echo "Tables to TRUNCATE (all test data will be deleted):"
echo "  - detections"
echo "  - camera_health"
echo "  - analytics"
echo "  - analytics_events"
echo "  - system_events"
echo "  - visualizations"
echo ""
echo "Tables PRESERVED:"
echo "  - cameras  (shown below for review)"
echo ""

echo "Current cameras in DB:"
ssh_lpr "PGPASSWORD=${PASS} psql -U ${DB_USER} -h 127.0.0.1 -p 5432 ${DB_NAME} \
  --no-password -q -c \
  'SELECT id, \"camera_id\", name, status, \"created_at\"::date FROM cameras ORDER BY \"created_at\";'"

echo ""
echo "============================================"
echo "WARNING: This will DELETE ALL test data."
echo "  - Have you run backup_data.sh?     (backup images + DB dump)"
echo "  - Have you verified backup size?   (check ~/aicamera_backup/)"
echo "============================================"
echo ""
read -r -p "Type CONFIRM to proceed (or anything else to abort): " USER_INPUT
if [ "$USER_INPUT" != "CONFIRM" ]; then
  echo "Aborted. No changes made."
  exit 0
fi

echo ""
read -r -p "Also DELETE cameras table? (yes = full reset, n = keep cameras): " CAM_INPUT
echo ""
echo "Starting cleanup..."

# Phase 1: Delete all non-camera test data
ssh_lpr "PGPASSWORD=${PASS} psql -U ${DB_USER} -h 127.0.0.1 -p 5432 ${DB_NAME} \
  --no-password -q" <<'SQL'
BEGIN;
\echo '[1/6] Deleting detections...'
DELETE FROM detections;
\echo '[2/6] Deleting camera_health...'
DELETE FROM camera_health;
\echo '[3/6] Deleting analytics...'
DELETE FROM analytics;
\echo '[4/6] Deleting analytics_events...'
DELETE FROM analytics_events;
\echo '[5/6] Deleting system_events...'
DELETE FROM system_events;
\echo '[6/6] Deleting visualizations...'
DELETE FROM visualizations;
COMMIT;
SQL

# Phase 2: Optionally delete cameras
if [ "$CAM_INPUT" = "yes" ]; then
  echo "[7/7] Deleting cameras..."
  ssh_lpr "PGPASSWORD=${PASS} psql -U ${DB_USER} -h 127.0.0.1 -p 5432 ${DB_NAME} \
    --no-password -q -c 'DELETE FROM cameras;'"
  echo "Cameras cleared. aicamera2 will re-register on next service start."
else
  echo "Cameras preserved."
fi

# Show final counts
echo ""
ssh_lpr "PGPASSWORD=${PASS} psql -U ${DB_USER} -h 127.0.0.1 -p 5432 ${DB_NAME} \
  --no-password -q" <<'SQL'
\echo '=== Post-Cleanup Row Counts ==='
SELECT 'cameras'          AS table_name, COUNT(*) AS rows FROM cameras
UNION ALL SELECT 'detections',           COUNT(*) FROM detections
UNION ALL SELECT 'camera_health',        COUNT(*) FROM camera_health
UNION ALL SELECT 'analytics',            COUNT(*) FROM analytics
UNION ALL SELECT 'analytics_events',     COUNT(*) FROM analytics_events
UNION ALL SELECT 'system_events',        COUNT(*) FROM system_events
UNION ALL SELECT 'visualizations',       COUNT(*) FROM visualizations
ORDER BY table_name;
SQL

echo ""
echo "============================================"
echo "Database cleanup complete -- $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "Next steps:"
echo "  1. bash scripts/storage_cleanup.sh   -- clean image files on lprserver"
echo "  2. bash scripts/verify_system.sh     -- verify API and dashboard still work"
echo "  3. Restart aicamera_lpr on aicamera2 to re-register camera"
echo "============================================"
