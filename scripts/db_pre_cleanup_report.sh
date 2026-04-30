#!/bin/bash
# db_pre_cleanup_report.sh — Show database statistics before cleanup
# Phase 7: Data Backup & Cleanup — Step 2 (run AFTER backup_data.sh)
#
# Usage: bash scripts/db_pre_cleanup_report.sh
# READ-ONLY — safe to run anytime

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
echo "Database Pre-Cleanup Report"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "Server: ${LPR_USER}@${LPR_IP}  DB: ${DB_NAME}"
echo "============================================"

ssh_lpr "PGPASSWORD=${PASS} psql -U ${DB_USER} -h 127.0.0.1 -p 5432 ${DB_NAME} \
  --no-password -q" <<'SQL'

\echo ''
\echo '=== [1] Row Counts Per Table ==='
SELECT 'cameras'          AS table_name, COUNT(*) AS rows FROM cameras
UNION ALL
SELECT 'detections',                     COUNT(*) FROM detections
UNION ALL
SELECT 'camera_health',                  COUNT(*) FROM camera_health
UNION ALL
SELECT 'analytics',                      COUNT(*) FROM analytics
UNION ALL
SELECT 'analytics_events',               COUNT(*) FROM analytics_events
UNION ALL
SELECT 'system_events',                  COUNT(*) FROM system_events
UNION ALL
SELECT 'visualizations',                 COUNT(*) FROM visualizations
ORDER BY table_name;

\echo ''
\echo '=== [2] Detection Confidence Distribution ==='
SELECT
  CASE
    WHEN confidence >= 0.9 THEN '90-100%'
    WHEN confidence >= 0.8 THEN '80-90%'
    WHEN confidence >= 0.7 THEN '70-80%'
    ELSE '< 70%'
  END AS confidence_range,
  COUNT(*) AS count,
  ROUND(COUNT(*) * 100.0 / NULLIF((SELECT COUNT(*) FROM detections), 0), 1) AS pct
FROM detections
GROUP BY confidence_range
ORDER BY confidence_range DESC;

\echo ''
\echo '=== [3] Detection Date Range ==='
SELECT
  MIN(timestamp)::date AS first_detection,
  MAX(timestamp)::date AS last_detection,
  COUNT(DISTINCT timestamp::date) AS active_days
FROM detections;

\echo ''
\echo '=== [4] Detections With/Without License Plate ==='
SELECT
  CASE
    WHEN license_plate IS NOT NULL AND license_plate != '' THEN 'with plate text'
    ELSE 'no plate text'
  END AS status,
  COUNT(*) AS count
FROM detections
GROUP BY 1;

\echo ''
\echo '=== [5] Cameras in Database ==='
SELECT
  id,
  camera_id,
  name,
  status,
  created_at::date AS created
FROM cameras
ORDER BY created_at;

\echo ''
\echo '=== [6] Camera Health Records Per Camera ==='
SELECT
  c.camera_id,
  COUNT(h.id) AS health_records,
  MIN(h.timestamp)::date AS first,
  MAX(h.timestamp)::date AS last
FROM camera_health h
JOIN cameras c ON c.id = h.camera_id
GROUP BY c.camera_id
ORDER BY c.camera_id;

\echo ''
\echo '=== [7] System Events By Type ==='
SELECT
  event_type,
  event_level,
  COUNT(*) AS count
FROM system_events
GROUP BY event_type, event_level
ORDER BY count DESC;

\echo ''
\echo '=== [8] Image Paths Sample (check storage) ==='
SELECT image_path, COUNT(*) AS count
FROM detections
WHERE image_path IS NOT NULL AND image_path != ''
GROUP BY image_path
ORDER BY count DESC
LIMIT 5;

SQL

echo ""
echo "=== [9] Storage on Disk (lprserver) ==="
ssh_lpr "
  echo 'storage/ total:'
  du -sh /home/devuser/aicamera/server/storage/ 2>/dev/null || echo '  (not found)'
  echo 'Subdirectories:'
  find /home/devuser/aicamera/server/storage/ -maxdepth 1 -mindepth 1 -type d 2>/dev/null | \
    while read -r d; do
      CNT=\$(find \"\$d\" -name '*.jpg' -o -name '*.png' 2>/dev/null | wc -l | tr -d ' ')
      SZ=\$(du -sh \"\$d\" 2>/dev/null | cut -f1)
      echo \"  \$(basename \$d)/  \$CNT files  \$SZ\"
    done
  echo 'Total images:'
  find /home/devuser/aicamera/server/storage/ -name '*.jpg' -o -name '*.png' 2>/dev/null | wc -l
"

echo ""
echo "============================================"
echo "Report complete — $(date '+%Y-%m-%d %H:%M:%S')"
echo "Review counts above before running db_cleanup.sh"
echo "============================================"