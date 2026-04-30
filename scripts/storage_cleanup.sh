#!/bin/bash
# storage_cleanup.sh — Delete test images from lprserver storage
# Phase 7: Data Backup & Cleanup — Step 5
#
# Operates on: /home/devuser/aicamera/server/storage/aicamera2/
#
# Modes:
#   survey  (default) — show what exists, no deletion
#   delete             — delete all images after CONFIRM prompt
#
# Usage:
#   bash scripts/storage_cleanup.sh            # survey mode (safe)
#   bash scripts/storage_cleanup.sh delete     # delete mode
#
# ⚠️  Run backup_data.sh AND db_cleanup.sh FIRST

set -e

MODE="${1:-survey}"
LPR_USER="devuser"
LPR_IP="100.95.46.128"
PASS="admin88366"
STORAGE_PATH="/home/devuser/aicamera/server/storage"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

ssh_lpr() {
  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    "${LPR_USER}@${LPR_IP}" "$@"
}

echo "============================================"
echo "Storage Cleanup — lprserver"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "Mode   : $MODE"
echo "Server : ${LPR_USER}@${LPR_IP}"
echo "Path   : ${STORAGE_PATH}/"
echo "============================================"

# ── Survey (always runs first) ────────────────────────────────────────────────

echo ""
echo "=== Storage Survey ==="
ssh_lpr "
  STORAGE='${STORAGE_PATH}'
  echo ''
  echo '[Total size]'
  du -sh \"\$STORAGE\" 2>/dev/null || echo '  (not found)'

  echo ''
  echo '[Subdirectory breakdown]'
  find \"\$STORAGE\" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort | \
    while read -r d; do
      CNT=\$(find \"\$d\" -name '*.jpg' -o -name '*.png' 2>/dev/null | wc -l)
      SZ=\$(du -sh \"\$d\" 2>/dev/null | cut -f1)
      echo \"  \$(basename \$d)/  \$CNT files  \$SZ\"
    done

  echo ''
  echo '[Image count by date (aicamera2)]'
  find \"\${STORAGE}/aicamera2\" -name '*.jpg' -o -name '*.png' 2>/dev/null | \
    sed 's/.*detection_\([0-9]\{8\}\)_.*/\1/' | sort | uniq -c | \
    awk '{printf \"  %s  %d files\n\", \$2, \$1}' 2>/dev/null || echo '  (no dated files found)'

  echo ''
  echo '[Newest 5 files]'
  find \"\${STORAGE}\" -name '*.jpg' -o -name '*.png' 2>/dev/null | \
    xargs ls -lt 2>/dev/null | head -6 | tail -5 | \
    awk '{printf \"  %s %s  %s\n\", \$6, \$7, \$NF}'

  echo ''
  echo '[Oldest 5 files]'
  find \"\${STORAGE}\" -name '*.jpg' -o -name '*.png' 2>/dev/null | \
    xargs ls -ltr 2>/dev/null | head -6 | tail -5 | \
    awk '{printf \"  %s %s  %s\n\", \$6, \$7, \$NF}'
"

# ── Delete mode ───────────────────────────────────────────────────────────────

if [ "$MODE" != "delete" ]; then
  echo ""
  echo "============================================"
  echo "Survey complete (read-only). No files deleted."
  echo "To delete: bash scripts/storage_cleanup.sh delete"
  echo "============================================"
  exit 0
fi

echo ""
echo "============================================"
echo "DELETE MODE"
echo "WARNING: All images in ${STORAGE_PATH}/ will be deleted."
echo "  - Have you run backup_data.sh?    (local backup complete?)"
echo "  - Have you run db_cleanup.sh?     (DB already cleaned?)"
echo "  - Have you verified backup size?  (check ~/aicamera_backup/)"
echo "============================================"
echo ""
read -r -p "Type CONFIRM to delete all storage images (or anything else to abort): " USER_INPUT
if [ "$USER_INPUT" != "CONFIRM" ]; then
  echo "Aborted. No files deleted."
  exit 0
fi

echo ""
echo "Deleting images from lprserver storage..."

ssh_lpr "
  STORAGE='${STORAGE_PATH}'

  echo 'Before:'
  du -sh \"\$STORAGE\"
  find \"\$STORAGE\" -name '*.jpg' -o -name '*.png' 2>/dev/null | wc -l | \
    xargs -I{} echo '  {} image files'

  echo 'Deleting JPG/PNG files...'
  find \"\$STORAGE\" -name '*.jpg' -delete 2>/dev/null && echo '  .jpg deleted'
  find \"\$STORAGE\" -name '*.png' -delete 2>/dev/null && echo '  .png deleted'

  echo ''
  echo 'After:'
  du -sh \"\$STORAGE\"
  find \"\$STORAGE\" -name '*.jpg' -o -name '*.png' 2>/dev/null | wc -l | \
    xargs -I{} echo '  {} image files remaining'
"

echo ""
echo "============================================"
echo "Storage cleanup complete -- $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "Next steps:"
echo "  bash scripts/verify_system.sh   -- verify API and dashboard still work"
echo "============================================"
