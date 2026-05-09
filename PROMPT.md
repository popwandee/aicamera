# PROMPT.md — Claude Code Implementation Instructions
> Use this as the starting prompt when opening a Claude Code session for this task.

---

## Your Mission

You are integrating **DualBranchLPRNet** (a custom CTC-based Thai LPR model) into the
aicamera edge project. The model is already compiled as a `.hef` file for Hailo-8.
You must replace the current YOLOv8 character-detection OCR with this new model.

**Read CONTEXT.md and GUARDRAIL.md before touching any code.**

---

## Step-by-Step Tasks

### Step 0 — Safety tag (DO THIS FIRST, once per device)
```bash
# On aicamera1:
cd /home/camuser/aicamera
git tag -a stable-before-dualbranch-lpr \
    -m "Stable: pre-DualBranchLPRNet OCR integration 2026-05-07"
git push origin stable-before-dualbranch-lpr
```

### Step 1 — Verify the new model file is present on device
```bash
ls -la /home/camuser/aicamera/resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503/
# Must see: …_fixed.hef  and  …json
# If missing, rsync from Mac:
#   rsync -av /Users/sqh/Documents/Claude/Projects/AICAMERA/resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503/ \
#         camuser@aicamera1:/home/camuser/aicamera/resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503/
```

### Step 2 — Run hardware test (before any code changes)
```bash
cd /home/camuser/aicamera
source edge/venv_hailo/bin/activate
python3 test_dual_branch_lpr.py --debug
# Expected: all 4 checks pass. If HEF inspection shows tensor names, note them.
# If lpr_logits/province_logits names differ from defaults, update dual_branch_lpr_ocr.py.
```

### Step 3 — Verify/correct the CTC character vocabulary
Open `edge/src/components/dual_branch_lpr_ocr.py` and check `LPR_CHARS` (48 entries).
Compare against your training script's character list. Fix if different.

### Step 4 — Verify/correct the Province vocabulary
Check `THAI_PROVINCES_SORTED` (77 entries) in `dual_branch_lpr_ocr.py`.
Compare against your training province label file. Fix ordering if different.

### Step 5 — Integrate into detection pipeline
The key file changes are already prepared (see modified files in CONTEXT.md).
Apply changes to `detection_processor.py` and `parallel_ocr_processor.py`:

In `detection_processor.py`:
1. Add import: `from edge.src.components.dual_branch_lpr_ocr import DualBranchLPROCR`
2. In `__init__`: add `self.dual_branch_ocr: Optional[DualBranchLPROCR] = None`
3. In `load_models()`: after ThaiLPROCR load, add:
   ```python
   self.dual_branch_ocr = DualBranchLPROCR(logger=self.logger)
   if self.dual_branch_ocr.load():
       self.logger.info("✅ DualBranchLPROCR loaded")
   else:
       self.logger.warning("⚠️  DualBranchLPROCR failed — will use Tesseract only")
       self.dual_branch_ocr = None
   ```
4. In `ParallelOCRProcessor` initialization: pass `dual_branch_ocr=self.dual_branch_ocr`
5. In `cleanup()`: add `if self.dual_branch_ocr: self.dual_branch_ocr.cleanup()`

In `parallel_ocr_processor.py`:
1. Accept `dual_branch_ocr` kwarg in `__init__`
2. In `_hailo_ocr_worker()`: if `dual_branch_ocr` is set, call `dual_branch_ocr.read_plate()`
   instead of the old degirum `hailo_ocr_model` call

### Step 6 — Run integration test
```bash
# On aicamera1, with service stopped:
sudo systemctl stop aicamera_lpr.service
cd /home/camuser/aicamera
source edge/venv_hailo/bin/activate
python3 -m edge.main --test-mode 2>&1 | head -100
# OR: check logs
sudo systemctl start aicamera_lpr.service && sudo journalctl -u aicamera_lpr -f
```

### Step 7 — Validate in production
Point a camera at a Thai LP. Check:
- `ocr_method` field in DB should show `"dualbranch"` or `"hailo"`
- Province field populated for plates with clear province area
- Latency: DualBranchLPRNet should be ≤ 15ms on Hailo-8

---

## Rollback
```bash
git checkout stable-before-dualbranch-lpr
sudo systemctl restart aicamera_lpr.service
```
