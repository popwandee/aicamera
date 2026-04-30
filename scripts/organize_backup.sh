#!/bin/bash
# organize_backup.sh — Reorganize flat backup into date-based folder structure
# Phase 7: Data Backup & Cleanup
#
# Moves existing detection_YYYYMMDD_*.jpg from any flat backup folder(s) into:
#   ~/aicamera_backup/aicamera2_images/YYYYMMDD/detection_YYYYMMDD_*.jpg
#
# Safe to re-run: skips files already at destination.
# Does NOT delete source folders — shows cleanup command at end.
#
# Usage:
#   bash scripts/organize_backup.sh               # uses ~/aicamera_backup
#   bash scripts/organize_backup.sh /path/to/dir  # custom backup root

set -e

BACKUP_ROOT="${1:-$HOME/aicamera_backup}"
DEST_BASE="$BACKUP_ROOT/aicamera2_images"

echo "============================================"
echo "AI Camera LPR -- Organize Backup Images"
echo "$(date '+%Y-%m-%d %H:%M:%S')"
echo "Backup root : $BACKUP_ROOT"
echo "Destination : $DEST_BASE/YYYYMMDD/"
echo "============================================"

# ── Scan source ───────────────────────────────────────────────────────────────

echo ""
echo "Scanning for detection images (outside $DEST_BASE)..."

# Find all detection images NOT already inside the destination
TOTAL_FOUND=$(find "$BACKUP_ROOT" -maxdepth 2 -name "detection_*.jpg" \
  ! -path "${DEST_BASE}/*" 2>/dev/null | wc -l | tr -d ' ')

if [ "$TOTAL_FOUND" -eq 0 ]; then
  echo "No images to organize. Already done or nothing found."
  exit 0
fi

echo "Found $TOTAL_FOUND image(s) to organize."

# List source folders (only timestamped flat ones, not the new dest)
echo ""
echo "Source folder(s):"
find "$BACKUP_ROOT" -maxdepth 1 -type d -name "aicamera2_images_*" 2>/dev/null | \
  while read -r d; do
    CNT=$(find "$d" -maxdepth 1 -name "detection_*.jpg" | wc -l | tr -d ' ')
    echo "  $d  ($CNT files)"
  done

# Gather unique dates across all source folders
echo ""
echo "Analyzing date groups..."
ALL_DATES=$(find "$BACKUP_ROOT" -maxdepth 2 -name "detection_*.jpg" \
  ! -path "${DEST_BASE}/*" 2>/dev/null | \
  sed 's/.*detection_\([0-9]\{8\}\)_.*/\1/' | sort -u)

DATE_COUNT=$(echo "$ALL_DATES" | grep -c . || true)
echo "$DATE_COUNT date group(s) found:"
find "$BACKUP_ROOT" -maxdepth 2 -name "detection_*.jpg" \
  ! -path "${DEST_BASE}/*" 2>/dev/null | \
  sed 's/.*detection_\([0-9]\{8\}\)_.*/\1/' | sort | uniq -c | \
  awk '{printf "  %s  %d files\n", $2, $1}'

# ── Confirm ───────────────────────────────────────────────────────────────────

echo ""
echo "Plan: MOVE $TOTAL_FOUND files into $DEST_BASE/YYYYMMDD/"
echo "      (files already at destination will be skipped)"
echo ""
read -r -p "Proceed? (y/n): " CONFIRM
[ "$CONFIRM" = "y" ] || { echo "Aborted."; exit 0; }
echo ""

mkdir -p "$DEST_BASE"

# ── Move by date group ────────────────────────────────────────────────────────

TOTAL_MOVED=0
TOTAL_SKIPPED=0

for IMG_DATE in $ALL_DATES; do
  DEST_DIR="$DEST_BASE/$IMG_DATE"
  mkdir -p "$DEST_DIR"

  # Count source files for this date (outside dest)
  SRC_COUNT=$(find "$BACKUP_ROOT" -maxdepth 2 \
    -name "detection_${IMG_DATE}_*.jpg" \
    ! -path "${DEST_BASE}/*" 2>/dev/null | wc -l | tr -d ' ')

  # Count already at destination
  DEST_COUNT=$(find "$DEST_DIR" -maxdepth 1 \
    -name "detection_${IMG_DATE}_*.jpg" 2>/dev/null | wc -l | tr -d ' ')

  printf "  %-10s  src:%4d  dest_existing:%4d  " \
    "$IMG_DATE" "$SRC_COUNT" "$DEST_COUNT"

  if [ "$SRC_COUNT" -eq 0 ]; then
    printf "nothing to move\n"
    continue
  fi

  # Move in batches of 500 (stay within ARG_MAX, handle any number of files)
  find "$BACKUP_ROOT" -maxdepth 2 \
    -name "detection_${IMG_DATE}_*.jpg" \
    ! -path "${DEST_BASE}/*" -print0 2>/dev/null | \
  xargs -0 -n 500 sh -c '
    DEST_DIR="$1"; shift
    for f; do
      bn=$(basename "$f")
      [ ! -f "$DEST_DIR/$bn" ] && mv "$f" "$DEST_DIR/"
    done
  ' _ "$DEST_DIR" || true

  # Recount after move to get accurate numbers (xargs subshells lose vars)
  AFTER_COUNT=$(find "$DEST_DIR" -maxdepth 1 \
    -name "detection_${IMG_DATE}_*.jpg" | wc -l | tr -d ' ')
  ACTUALLY_MOVED=$((AFTER_COUNT - DEST_COUNT))
  ACTUALLY_SKIPPED=$((SRC_COUNT - ACTUALLY_MOVED))

  printf "moved:%4d  skipped:%4d  total_in_dest:%4d\n" \
    "$ACTUALLY_MOVED" "$ACTUALLY_SKIPPED" "$AFTER_COUNT"

  TOTAL_MOVED=$((TOTAL_MOVED + ACTUALLY_MOVED))
  TOTAL_SKIPPED=$((TOTAL_SKIPPED + ACTUALLY_SKIPPED))
done

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "============================================"
echo "Done -- $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Moved  : $TOTAL_MOVED files"
echo "  Skipped: $TOTAL_SKIPPED files (already at destination)"
echo ""

DEST_TOTAL=$(find "$DEST_BASE" -name "detection_*.jpg" 2>/dev/null | wc -l | tr -d ' ')
DEST_SIZE=$(du -sh "$DEST_BASE" 2>/dev/null | cut -f1)
echo "  Result : $DEST_TOTAL files, $DEST_SIZE in $DEST_BASE/"
echo ""

# Show remaining source files (should be 0 if all moved)
REMAINING=$(find "$BACKUP_ROOT" -maxdepth 2 -name "detection_*.jpg" \
  ! -path "${DEST_BASE}/*" 2>/dev/null | wc -l | tr -d ' ')

if [ "$REMAINING" -eq 0 ]; then
  echo "  Source folders are now empty of detection images."
  echo "  To remove old flat folders (review first!):"
  find "$BACKUP_ROOT" -maxdepth 1 -type d -name "aicamera2_images_*" 2>/dev/null | \
    sed 's/^/    rm -rf /'
else
  echo "  WARNING: $REMAINING files still remain in source (check manually):"
  find "$BACKUP_ROOT" -maxdepth 2 -name "detection_*.jpg" \
    ! -path "${DEST_BASE}/*" 2>/dev/null | head -10
fi
echo "============================================"
