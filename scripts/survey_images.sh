#!/bin/bash
# survey_images.sh — Survey detection images on lprserver storage
# Phase 7: Data Backup & Cleanup
# Usage: bash scripts/survey_images.sh

LPRSERVER_HOST="devuser@100.95.46.128"
STORAGE_PATH="/home/devuser/aicamera/server/storage"

if ! command -v sshpass &>/dev/null; then
  echo "ERROR: sshpass not installed. Run: brew install sshpass"
  exit 1
fi

SSHPASS="sshpass -p admin88366"

echo "============================================"
echo "Image Survey Report — $(date '+%Y-%m-%d %H:%M:%S')"
echo "Source: $LPRSERVER_HOST:$STORAGE_PATH"
echo "============================================"

$SSHPASS ssh "$LPRSERVER_HOST" bash -s <<'REMOTE'
STORAGE_PATH="/home/devuser/aicamera/server/storage"

echo ""
echo "[Total Images]"
TOTAL=$(find "$STORAGE_PATH" -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$STORAGE_PATH" 2>/dev/null | cut -f1)
echo "  Files: $TOTAL"
echo "  Size : $TOTAL_SIZE"

echo ""
echo "[Date Distribution]"
find "$STORAGE_PATH" -name "*.jpg" -o -name "*.png" 2>/dev/null | \
  xargs -I{} stat -c "%y" {} 2>/dev/null | \
  cut -d' ' -f1 | sort | uniq -c | \
  awk '{printf "  %s: %d files\n", $2, $1}'

echo ""
echo "[Newest 10 Files]"
find "$STORAGE_PATH" -name "*.jpg" -o -name "*.png" 2>/dev/null | \
  xargs ls -lt 2>/dev/null | head -11 | tail -10 | \
  awk '{printf "  %s %s %s\n", $6, $7, $9}'

echo ""
echo "[Oldest 10 Files]"
find "$STORAGE_PATH" -name "*.jpg" -o -name "*.png" 2>/dev/null | \
  xargs ls -ltr 2>/dev/null | head -11 | tail -10 | \
  awk '{printf "  %s %s %s\n", $6, $7, $9}'

echo ""
echo "[Subdirectory Breakdown]"
find "$STORAGE_PATH" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | while read dir; do
  COUNT=$(find "$dir" -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l)
  SIZE=$(du -sh "$dir" 2>/dev/null | cut -f1)
  echo "  $(basename $dir): $COUNT files, $SIZE"
done
REMOTE

echo ""
echo "============================================"
echo "Survey complete."
