#!/usr/bin/env bash
# =============================================================================
# deploy_dualbranch_degirum.sh
# Deploy DualBranchDegirumOCR (degirum-only, no hailo_platform) to aicamera1
# Run from your Mac:  bash scripts/deploy_dualbranch_degirum.sh
# =============================================================================
set -e

TARGET="camuser@aicamera1"
REMOTE_DIR="/home/camuser/aicamera"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================================"
echo "  Deploy DualBranchDegirumOCR → $TARGET"
echo "========================================================"

# 1. Stop production service so device is free during test
echo ""
echo "[1/5] Stopping aicamera service..."
ssh "$TARGET" "sudo systemctl stop aicamera_lpr 2>/dev/null && echo '  Service stopped' || echo '  Service was not running'"

# 2. Sync updated source files
echo ""
echo "[2/5] Syncing source files..."
scp "$LOCAL_DIR/test_dual_branch_lpr.py" \
    "$TARGET:$REMOTE_DIR/test_dual_branch_lpr.py"
echo "  ✅ test_dual_branch_lpr.py"

scp "$LOCAL_DIR/edge/src/components/dual_branch_degirum_ocr.py" \
    "$TARGET:$REMOTE_DIR/edge/src/components/dual_branch_degirum_ocr.py"
echo "  ✅ dual_branch_degirum_ocr.py  (NEW — degirum-based OCR)"

scp "$LOCAL_DIR/edge/src/components/dual_branch_lpr_ocr.py" \
    "$TARGET:$REMOTE_DIR/edge/src/components/dual_branch_lpr_ocr.py"
echo "  ✅ dual_branch_lpr_ocr.py  (kept as backup)"

scp "$LOCAL_DIR/edge/src/components/detection_processor.py" \
    "$TARGET:$REMOTE_DIR/edge/src/components/detection_processor.py"
echo "  ✅ detection_processor.py"

scp "$LOCAL_DIR/edge/src/components/parallel_ocr_processor.py" \
    "$TARGET:$REMOTE_DIR/edge/src/components/parallel_ocr_processor.py"
echo "  ✅ parallel_ocr_processor.py"

# 3. Sync DualBranch model files (HEF + degirum JSON config)
MODEL_DIR="DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503"
echo ""
echo "[3/5] Syncing DualBranch model (HEF + JSON config) to aicamera1..."
scp "$LOCAL_DIR/resources/$MODEL_DIR/${MODEL_DIR}_fixed.hef" \
    "$TARGET:$REMOTE_DIR/resources/$MODEL_DIR/${MODEL_DIR}_fixed.hef"
echo "  ✅ ${MODEL_DIR}_fixed.hef  (recompiled — correct [-1,1] calibration)"
scp "$LOCAL_DIR/resources/$MODEL_DIR/${MODEL_DIR}.json" \
    "$TARGET:$REMOTE_DIR/resources/$MODEL_DIR/${MODEL_DIR}.json"
echo "  ✅ ${MODEL_DIR}.json  (InputQuantEn=true, OutputPostprocessType=None)"

# 4. Run pipeline test
echo ""
echo "[4/5] Running pipeline test..."
echo "  Image: edge/captured_images/detection_20260505_063350_100.jpg"
ssh -t "$TARGET" "
  cd $REMOTE_DIR && \
  source edge/venv_hailo/bin/activate && \
  python3 test_dual_branch_lpr.py \
    --image edge/captured_images/detection_20260505_063350_100.jpg \
    --save-crops \
    2>&1 | tee /tmp/pipeline_test_degirum.log
  echo 'Exit code: '\$?
"

# 5. Restart production service
echo ""
echo "[5/5] Restarting aicamera service..."
ssh "$TARGET" "sudo systemctl start aicamera_lpr && echo '  Service restarted' || echo '  Service start failed (check: sudo systemctl status aicamera_lpr)'"

echo ""
echo "========================================================"
echo "  Deploy complete. Check /tmp/pipeline_test_degirum.log"
echo "  on aicamera1 for full output."
echo "========================================================"
