#!/bin/bash
# edge_cleanup.sh — Survey and clean edge camera device
# Phase 7: Data Backup & Cleanup — Step 3
#
# Modes:
#   survey  (default) — show what can be cleaned, no changes made
#   clean             — perform cleanup after per-item confirmation
#
# What this covers:
#   [A] gunicorn_access.log  — truncate (145 MB active log)
#   [B] Rotated aicamera.log.* — delete old rotated logs
#   [C] Zero-byte hailort_backup_*.log — delete empty files
#   [D] lpr_data.db (SQLite) — show size, offer to clear data
#   [E] captured_images/ — show remaining count (delete after backup only)
#   [F] Test scripts in project root — list and offer to delete
#
# Usage:
#   bash scripts/edge_cleanup.sh                      # aicamera2, survey
#   bash scripts/edge_cleanup.sh clean                # aicamera2, clean
#   bash scripts/edge_cleanup.sh survey aicamera1     # aicamera1, survey
#   bash scripts/edge_cleanup.sh clean  aicamera1     # aicamera1, clean

set -e

MODE="${1:-survey}"
CAMERA="${2:-aicamera2}"
case "$CAMERA" in
  aicamera1) CAM_USER="camuser"; CAM_IP="100.126.178.74" ;;
  aicamera2) CAM_USER="camuser"; CAM_IP="100.110.20.53"  ;;
  aicamera3) CAM_USER="camuser"; CAM_IP="100.68.95.36"   ;;
  *) echo "Unknown camera: $CAMERA. Use aicamera1, aicamera2, or aicamera3."; exit 1 ;;
esac
PASS="admin88366"
EDGE_BASE="/home/camuser/aicamera"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

ssh_cam() {
  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    "${CAM_USER}@${CAM_IP}" "$@"
}

echo "============================================"
echo "${CAMERA} Edge Cleanup"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "Mode   : $MODE"
echo "Device : ${CAM_USER}@${CAM_IP}"
echo "============================================"

# ── Survey (always runs) ──────────────────────────────────────────────────────

echo ""
echo "=== Disk Usage ==="
ssh_cam "df -h / | tail -1 | awk '{print \"  Used: \" \$3 \" / \" \$2 \" (\" \$5 \")  Free: \" \$4}'"

echo ""
echo "=== [A] gunicorn_access.log ==="
ssh_cam "
  F='${EDGE_BASE}/edge/logs/gunicorn_access.log'
  if [ -f \"\$F\" ]; then
    SZ=\$(du -sh \"\$F\" | cut -f1)
    LINES=\$(wc -l < \"\$F\")
    echo \"  \$F\"
    echo \"  Size: \$SZ  Lines: \$LINES\"
    echo \"  Action: TRUNCATE (empty the file, keep log rotation intact)\"
  else
    echo \"  Not found\"
  fi
"

echo ""
echo "=== [B] Rotated aicamera.log.* ==="
ssh_cam "
  FILES=\$(find '${EDGE_BASE}/edge/logs' -name 'aicamera.log.*' 2>/dev/null)
  if [ -n \"\$FILES\" ]; then
    echo \"\$FILES\" | while read -r f; do
      SZ=\$(du -sh \"\$f\" | cut -f1)
      echo \"  \$f  (\$SZ)\"
    done
    TOTAL=\$(find '${EDGE_BASE}/edge/logs' -name 'aicamera.log.*' 2>/dev/null | wc -l | tr -d ' ')
    echo \"  Total: \$TOTAL file(s) — safe to delete (rotated, already captured in current log)\"
  else
    echo \"  None found\"
  fi
"

echo ""
echo "=== [C] Zero-byte hailort_backup_*.log ==="
ssh_cam "
  FILES=\$(find '${EDGE_BASE}/edge/logs' -name 'hailort_backup_*.log' -empty 2>/dev/null)
  if [ -n \"\$FILES\" ]; then
    echo \"\$FILES\" | while read -r f; do echo \"  \$f  (0 bytes)\"; done
    COUNT=\$(echo \"\$FILES\" | wc -l | tr -d ' ')
    echo \"  Total: \$COUNT empty file(s) — safe to delete\"
  else
    echo \"  None found\"
  fi
"

echo ""
echo "=== [D] SQLite Database ==="
ssh_cam "
  DB='${EDGE_BASE}/edge/db/lpr_data.db'
  BAK='${EDGE_BASE}/edge/db/lpr_data.db.backup_v3_20250824_175354'
  if [ -f \"\$DB\" ]; then
    SZ=\$(du -sh \"\$DB\" | cut -f1)
    echo \"  \$DB  (\$SZ)\"
    echo \"  Tables:\"
    sqlite3 \"\$DB\" '.tables' 2>/dev/null | sed 's/^/    /' || echo \"    (sqlite3 not available)\"
    echo \"  NOTE: Backup this DB before clearing. Contains local detection history.\"
  fi
  if [ -f \"\$BAK\" ]; then
    SZ2=\$(du -sh \"\$BAK\" | cut -f1)
    echo \"  \$BAK  (\$SZ2) — old backup\"
  fi
"

echo ""
echo "=== [E] captured_images/ ==="
ssh_cam "
  DIR='${EDGE_BASE}/edge/captured_images'
  COUNT=\$(find \"\$DIR\" -name '*.jpg' 2>/dev/null | wc -l | tr -d ' ')
  SZ=\$(du -sh \"\$DIR\" 2>/dev/null | cut -f1)
  echo \"  \$DIR\"
  echo \"  Files: \$COUNT  Size: \$SZ\"
  echo \"  Date range:\"
  find \"\$DIR\" -name '*.jpg' 2>/dev/null | \
    sed 's/.*detection_\([0-9]\{8\}\)_.*/\1/' | sort -u | \
    awk 'NR==1{first=\$0} END{print \"    \",first,\"→\",\$0,\"(\",NR,\"date groups)\"}' 2>/dev/null
  echo \"  NOTE: Delete ONLY after backup_data.sh is fully complete.\"
"

echo ""
echo "=== [F] Test scripts in project root ==="
ssh_cam "
  FILES=\$(find '${EDGE_BASE}' -maxdepth 1 \( -name 'test_*.py' -o -name 'test_*.sh' \) 2>/dev/null)
  if [ -n \"\$FILES\" ]; then
    echo \"\$FILES\" | while read -r f; do
      SZ=\$(du -sh \"\$f\" 2>/dev/null | cut -f1)
      echo \"  \$f  (\$SZ)\"
    done
  else
    echo \"  None found\"
  fi
"

echo ""
echo "=== Summary ==="
ssh_cam "
  GUNICORN_SZ=\$(du -sh '${EDGE_BASE}/edge/logs/gunicorn_access.log' 2>/dev/null | cut -f1 || echo '0')
  ROTATED_SZ=\$(find '${EDGE_BASE}/edge/logs' -name 'aicamera.log.*' -exec du -ch {} + 2>/dev/null | tail -1 | cut -f1 || echo '0')
  DB_SZ=\$(du -sh '${EDGE_BASE}/edge/db/lpr_data.db' 2>/dev/null | cut -f1 || echo '0')
  IMG_SZ=\$(du -sh '${EDGE_BASE}/edge/captured_images' 2>/dev/null | cut -f1 || echo '0')
  echo \"  [A] gunicorn_access.log : \$GUNICORN_SZ (truncate)\"
  echo \"  [B] Rotated aicamera logs: \$ROTATED_SZ (delete)\"
  echo \"  [C] Zero-byte hailort logs: negligible (delete)\"
  echo \"  [D] lpr_data.db         : \$DB_SZ (backup first, then decide)\"
  echo \"  [E] captured_images     : \$IMG_SZ (delete after backup complete)\"
  echo \"  [F] Test scripts        : small (delete after review)\"
"

# ── Clean mode ────────────────────────────────────────────────────────────────

if [ "$MODE" != "clean" ]; then
  echo ""
  echo "============================================"
  echo "Survey complete (read-only). No changes made."
  echo "To clean: bash scripts/edge_cleanup.sh clean"
  echo "============================================"
  exit 0
fi

echo ""
echo "============================================"
echo "CLEAN MODE — each item requires confirmation"
echo "============================================"

# [A] Truncate gunicorn_access.log
echo ""
read -r -p "[A] Truncate gunicorn_access.log (145MB → 0)? (y/n): " A
if [ "$A" = "y" ]; then
  ssh_cam "> '${EDGE_BASE}/edge/logs/gunicorn_access.log'"
  echo "  Done. gunicorn_access.log truncated."
else
  echo "  Skipped."
fi

# [B] Delete rotated aicamera.log.*
echo ""
read -r -p "[B] Delete rotated aicamera.log.* files? (y/n): " B
if [ "$B" = "y" ]; then
  ssh_cam "find '${EDGE_BASE}/edge/logs' -name 'aicamera.log.*' -delete && echo '  Done.'"
else
  echo "  Skipped."
fi

# [C] Delete zero-byte hailort_backup_*.log
echo ""
read -r -p "[C] Delete zero-byte hailort_backup_*.log files? (y/n): " C
if [ "$C" = "y" ]; then
  ssh_cam "find '${EDGE_BASE}/edge/logs' -name 'hailort_backup_*.log' -empty -delete && echo '  Done.'"
else
  echo "  Skipped."
fi

# [D] SQLite DB — backup then decide
echo ""
echo "[D] lpr_data.db (806 MB) — options:"
echo "    1) Skip (keep as-is)"
echo "    2) Download DB to Mac then delete"
echo "    3) Delete without backup (IRREVERSIBLE)"
read -r -p "    Choice (1/2/3): " D
case "$D" in
  2)
    echo "  Downloading lpr_data.db to ~/aicamera_backup/..."
    mkdir -p "$HOME/aicamera_backup"
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no \
      "${CAM_USER}@${CAM_IP}:${EDGE_BASE}/edge/db/lpr_data.db" \
      "$HOME/aicamera_backup/lpr_data_$(date +%Y%m%d_%H%M%S).db"
    echo "  Downloaded. Now deleting from device..."
    ssh_cam "rm -f '${EDGE_BASE}/edge/db/lpr_data.db' && echo '  lpr_data.db deleted.'"
    # Also remove old backup
    ssh_cam "rm -f '${EDGE_BASE}/edge/db/lpr_data.db.backup_v3_20250824_175354' && echo '  Old .bak deleted.'"
    ;;
  3)
    read -r -p "  CONFIRM delete lpr_data.db without backup? (yes/n): " D3
    if [ "$D3" = "yes" ]; then
      ssh_cam "rm -f '${EDGE_BASE}/edge/db/lpr_data.db' '${EDGE_BASE}/edge/db/lpr_data.db.backup_v3_20250824_175354' && echo '  Done.'"
    else
      echo "  Aborted."
    fi
    ;;
  *)
    echo "  Skipped."
    ;;
esac

# [E] captured_images — only if backup is confirmed complete
echo ""
echo "[E] captured_images/ (1.7 GB)"
REMAINING=$(ssh_cam "find '${EDGE_BASE}/edge/captured_images' -name '*.jpg' | wc -l | tr -d ' '")
LOCAL_BACKED=$(find "$HOME/aicamera_backup/aicamera1_images" -name "*.jpg" 2>/dev/null | wc -l | tr -d ' ')
echo "    On device : $REMAINING files"
echo "    Backed up : $LOCAL_BACKED files (in ~/aicamera_backup/aicamera1_images/)"
if [ "$LOCAL_BACKED" -lt "$REMAINING" ]; then
  echo "    WARNING: Backup appears incomplete ($LOCAL_BACKED < $REMAINING). Skipping."
else
  read -r -p "    Backup looks complete. Delete captured_images on device? (yes/n): " E
  if [ "$E" = "yes" ]; then
    ssh_cam "find '${EDGE_BASE}/edge/captured_images' -name '*.jpg' -delete && echo '  All JPGs deleted.'"
  else
    echo "  Skipped."
  fi
fi

# [F] Test scripts
echo ""
TESTFILES=$(ssh_cam "find '${EDGE_BASE}' -maxdepth 1 -name 'test_*.py' 2>/dev/null | tr '\n' ' '")
if [ -n "$TESTFILES" ]; then
  echo "[F] Test scripts: $TESTFILES"
  read -r -p "    Delete these test scripts? (y/n): " F
  if [ "$F" = "y" ]; then
    ssh_cam "find '${EDGE_BASE}' -maxdepth 1 -name 'test_*.py' -delete && echo '  Done.'"
  else
    echo "  Skipped."
  fi
else
  echo "[F] No test scripts found."
fi

# ── Post-clean summary ────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo "Post-Cleanup Status"
ssh_cam "
  df -h / | tail -1 | awk '{print \"  Disk: \" \$3 \" used / \" \$2 \" total (\" \$5 \"free: \" \$4 \")\"}';
  echo \"  Logs: \$(du -sh '${EDGE_BASE}/edge/logs/' | cut -f1)\";
  IMG=\$(find '${EDGE_BASE}/edge/captured_images' -name '*.jpg' 2>/dev/null | wc -l | tr -d ' ')
  echo \"  Images remaining: \$IMG\";
"
echo "============================================"
echo "Cleanup complete -- $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "Next steps:"
echo "  bash scripts/edge_health_check.sh   -- verify device ready for field test"
echo "  bash scripts/configure_camera.sh    -- set camera name/location before deploy"
echo "============================================"
