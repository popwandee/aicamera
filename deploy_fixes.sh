#!/usr/bin/env bash
# Deploy OCR quality fixes to aicamera2
# Fixes: safe padding, Laplacian-post-CLAHE, queue_wait, Tesseract timeout
# Run from your Mac: bash ~/Documents/Claude/Projects/AICAMERA/deploy_fixes.sh

set -e
HOST="camuser@100.110.20.53"
PASS="admin88366"
LOCAL_BASE="$(cd "$(dirname "$0")" && pwd)"
FILES=(
  "edge/src/components/detection_processor.py"
  "edge/src/components/ocr_queue_worker.py"
  "edge/src/components/thai_lp_ocr.py"
)

echo "=== Finding remote project root ==="
REMOTE_BASE=$(sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$HOST" \
  "find ~ -name 'detection_processor.py' -path '*/components/*' 2>/dev/null | head -1 | sed 's|/edge/.*||'")
if [ -z "$REMOTE_BASE" ]; then
  echo "ERROR: Could not find project root on $HOST"; exit 1
fi
echo "Remote root: $REMOTE_BASE"

echo ""
echo "=== Backing up and uploading files ==="
for F in "${FILES[@]}"; do
  REMOTE_PATH="$REMOTE_BASE/$F"
  LOCAL_PATH="$LOCAL_BASE/$F"
  BACKUP="$REMOTE_PATH.bak.$(date +%Y%m%d%H%M%S)"
  sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$HOST" "cp $REMOTE_PATH $BACKUP 2>/dev/null || true"
  sshpass -p "$PASS" scp -o StrictHostKeyChecking=no "$LOCAL_PATH" "$HOST:$REMOTE_PATH"
  echo "  ✓ $F"
done

echo ""
echo "=== Restarting aicamera service ==="
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$HOST" \
  "cd $REMOTE_BASE && (sudo systemctl restart aicamera 2>/dev/null || pkill -f 'python.*main' 2>/dev/null || true) && echo 'Service restart OK'"

echo ""
echo "=== Tailing log for 20s (Ctrl+C to stop) ==="
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$HOST" \
  "journalctl -u aicamera -f -n 5 2>/dev/null || tail -f \$HOME/aicamera/logs/\$(date +%Y%m%d)/*.log 2>/dev/null" &
TAILPID=$!
sleep 20
kill $TAILPID 2>/dev/null

echo ""
echo "=== Deploy complete. Watch for these log tokens: ==="
echo "  [PLATE_CROP]        raw=XXxYY padded=XXxYY ar=2.xx lap=XXX"
echo "  [PLATE_CROP_SKIP]   ... ar<1.5, likely false positive"  
echo "  [OCR_RESULT]        queue_wait=XXXms (ค่าบวก, ไม่ลบอีก)"
echo "  [OCR_RESULT]        tesseract=XXXms (<=2000ms)"
