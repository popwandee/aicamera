#!/bin/bash
# backup_data.sh — Resumable backup with date-organized image folders
# Phase 7: Data Backup & Cleanup
#
# Folder structure:
#   ~/aicamera_backup/
#   ├── aicamera2_images/
#   │   ├── 20251121/   ← detection_20251121_*.jpg
#   │   ├── 20251122/
#   │   └── ...
#   ├── lprserver_storage/   ← mirrors remote storage/
#   └── db_dumps/
#       └── aicamera_app_YYYYMMDD_HHMMSS.sql
#
# Resume logic:
#   - For each date group: compare remote count vs local count
#   - If local >= remote → skip (already complete)
#   - If local < remote  → rsync only that date with --ignore-existing
#   - lprserver storage: --ignore-existing throughout
#   - DB dump: always creates a new timestamped file
#
# Usage: bash scripts/backup_data.sh
# ⚠️  Run this BEFORE any cleanup script

set -e

BACKUP_ROOT="$HOME/aicamera_backup"
CAM_USER="camuser"
CAM_IP="100.126.178.74" ## CAMERA IP 1
##CAM_IP="100.110.20.53" ## CAMERA IP 2
LPR_USER="devuser"
LPR_IP="100.95.46.128"
PASS="admin88366"

CAM_REMOTE_PATH="/home/camuser/aicamera/edge/captured_images"
LPR_REMOTE_PATH="/home/devuser/aicamera/server/storage"

DEST_CAM="$BACKUP_ROOT/aicamera1_images"
DEST_LPR="$BACKUP_ROOT/lprserver_storage"
DEST_DB="$BACKUP_ROOT/db_dumps"

# ── Helpers ───────────────────────────────────────────────────────────────────

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

ssh_cam()   { sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
                "${CAM_USER}@${CAM_IP}" "$@"; }
ssh_lpr()   { sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
                "${LPR_USER}@${LPR_IP}" "$@"; }
rsync_cam() { sshpass -p "$PASS" rsync -e "ssh -o StrictHostKeyChecking=no" "$@"; }
rsync_lpr() { sshpass -p "$PASS" rsync -e "ssh -o StrictHostKeyChecking=no" "$@"; }

# ── Init ──────────────────────────────────────────────────────────────────────

mkdir -p "$DEST_CAM" "$DEST_LPR" "$DEST_DB"

echo "============================================"
echo "AI Camera LPR -- Resumable Data Backup"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "Backup root: $BACKUP_ROOT"
echo "============================================"

# ── Part 1: aicamera images (organized by date from filename) ────────────────

echo ""
echo "[1/3] Backing up images from aicamera..."
echo "  Remote : ${CAM_USER}@${CAM_IP}:${CAM_REMOTE_PATH}/"
echo "  Local  : ${DEST_CAM}/YYYYMMDD/"
echo ""

echo "  Fetching remote date list..."
REMOTE_DATES=$(ssh_cam \
  "find '${CAM_REMOTE_PATH}' -maxdepth 1 -name 'detection_*.jpg' 2>/dev/null | \
   sed 's/.*detection_\([0-9]\{8\}\)_.*/\1/' | sort -u")

if [ -z "$REMOTE_DATES" ]; then
  echo "  No detection images found on aicamera."
else
  DATE_COUNT=$(echo "$REMOTE_DATES" | wc -l | tr -d ' ')
  echo "  Found images spanning ${DATE_COUNT} date group(s) on remote."
  echo ""

  DATES_SKIPPED=0
  DATES_SYNCED=0
  FILES_NEW=0

  for IMG_DATE in $REMOTE_DATES; do
    LOCAL_DIR="${DEST_CAM}/${IMG_DATE}"
    mkdir -p "$LOCAL_DIR"

    # Count remote files for this date (trim whitespace from wc output)
    REMOTE_COUNT=$(ssh_cam \
      "find '${CAM_REMOTE_PATH}' -maxdepth 1 -name 'detection_${IMG_DATE}_*.jpg' 2>/dev/null \
       | wc -l" | tr -d ' \n\r')

    # Count local files already downloaded
    LOCAL_COUNT=$(find "$LOCAL_DIR" -maxdepth 1 \
      -name "detection_${IMG_DATE}_*.jpg" 2>/dev/null | wc -l | tr -d ' \n\r')

    if [ "$REMOTE_COUNT" -gt 0 ] && [ "$LOCAL_COUNT" -ge "$REMOTE_COUNT" ]; then
      printf "  [OK]   %s -- %d/%d files (complete, skipping)\n" \
        "$IMG_DATE" "$LOCAL_COUNT" "$REMOTE_COUNT"
      DATES_SKIPPED=$((DATES_SKIPPED + 1))
    else
      printf "  [SYNC] %s -- %d/%d files (downloading...)\n" \
        "$IMG_DATE" "$LOCAL_COUNT" "$REMOTE_COUNT"

      rsync_cam -az --ignore-existing \
        --include="detection_${IMG_DATE}_*.jpg" --exclude="*" \
        "${CAM_USER}@${CAM_IP}:${CAM_REMOTE_PATH}/" \
        "${LOCAL_DIR}/"

      NEW_COUNT=$(find "$LOCAL_DIR" -maxdepth 1 \
        -name "detection_${IMG_DATE}_*.jpg" | wc -l | tr -d ' \n\r')
      ADDED=$((NEW_COUNT - LOCAL_COUNT))
      printf "        -> %d files saved  (+%d new)\n" "$NEW_COUNT" "$ADDED"
      FILES_NEW=$((FILES_NEW + ADDED))
      DATES_SYNCED=$((DATES_SYNCED + 1))
    fi
  done

  echo ""
  CAM_TOTAL=$(find "$DEST_CAM" -name "*.jpg" 2>/dev/null | wc -l | tr -d ' ')
  CAM_SIZE=$(du -sh "$DEST_CAM" 2>/dev/null | cut -f1)
  echo "  Done: ${CAM_TOTAL} files total, ${CAM_SIZE}"
  echo "  (${DATES_SKIPPED} date(s) skipped, ${DATES_SYNCED} date(s) synced, ${FILES_NEW} new files)"
fi

# ── Part 2: lprserver storage (resume-safe) ───────────────────────────────────

##echo ""
#echo "[2/3] Backing up lprserver storage (--ignore-existing for resume)..."
#echo "  Remote : ${LPR_USER}@${LPR_IP}:${LPR_REMOTE_PATH}/"
#echo "  Local  : ${DEST_LPR}/"

#rsync_lpr -az --ignore-existing --progress \
#  "${LPR_USER}@${LPR_IP}:${LPR_REMOTE_PATH}/" \
#  "${DEST_LPR}/" || { echo "ERROR: rsync from lprserver failed"; exit 1; }

#LPR_TOTAL=$(find "$DEST_LPR" -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l | tr -d ' ')
#LPR_SIZE=$(du -sh "$DEST_LPR" 2>/dev/null | cut -f1)
#echo "  Done: ${LPR_TOTAL} files, ${LPR_SIZE}"

# ── Part 3: Database dump (always new timestamped file) ───────────────────────

#echo ""
#echo "[3/3] Dumping database from lprserver..."
#DB_FILE="${DEST_DB}/aicamera_app_$(date +%Y%m%d_%H%M%S).sql"

#ssh_lpr "PGPASSWORD=${PASS} pg_dump -U lpruser -h 127.0.0.1 -p 5432 aicamera_app" \
#  > "$DB_FILE" || { echo "ERROR: pg_dump failed"; exit 1; }

#DB_SIZE=$(du -sh "$DB_FILE" | cut -f1)
#echo "  -> ${DB_FILE} (${DB_SIZE})"

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo "Backup Complete -- $(date '+%Y-%m-%d %H:%M:%S')"
CAM_TOTAL=$(find "$DEST_CAM" -name "*.jpg" 2>/dev/null | wc -l | tr -d ' ')
CAM_SIZE=$(du -sh "$DEST_CAM" 2>/dev/null | cut -f1)
LPR_SIZE=$(du -sh "$DEST_LPR" 2>/dev/null | cut -f1)
echo "  aicamera images : ${CAM_TOTAL} files, ${CAM_SIZE}"
echo "                     organized in: ${DEST_CAM}/YYYYMMDD/"
#echo "  lprserver storage: ${LPR_SIZE}  -> ${DEST_LPR}/"
#echo "  database dump    : ${DB_SIZE}   -> ${DB_FILE}"
echo "============================================"
echo "WARNING: Verify backup before running any cleanup scripts!"
