# CONTEXT — Step 05: Deploy & Test on aicamera

**Host:** aicamera1 (primary) + aicamera2  
**SSH:** `ssh camuser@aicamera1.tail605477.ts.net`  (password: `admin88366`)  
**Goal:** Deploy new `.hef` + validate end-to-end LPR accuracy on real Hailo-8 hardware.

---

## Device Summary

| Device | Hostname | IP | Status |
|--------|----------|----|--------|
| aicamera1 | `aicamera1.tail605477.ts.net` | `100.126.178.74` | Primary test target |
| aicamera2 | `aicamera2.tail605477.ts.net` | `100.110.20.53` | Online — secondary |
| lprserver | `lprserver.tail605477.ts.net` | `100.95.46.128` | Backend |

---

## Step 1 — Copy HEF to aicamera

```bash
# From Mac
scp DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260508.hef \
  camuser@aicamera1.tail605477.ts.net:/home/camuser/aicamera/resources/

# Verify transfer
ssh camuser@aicamera1.tail605477.ts.net \
  "ls -lh /home/camuser/aicamera/resources/*.hef"
```

---

## Step 2 — Update Model JSON Config

```bash
ssh camuser@aicamera1.tail605477.ts.net
cd /home/camuser/aicamera/resources/

# Edit the DualBranch model JSON — update filename only
nano dual_branch_lpr_model.json
```

Only the `"name"` field needs updating:
```json
{
  "name": "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260508",
  "device_type": "HAILO8",
  "input_shape": [1, 3, 75, 300],
  "output_postprocess_type": "None",
  "input_quant_en": true,
  "output_quant_en": false
}
```

`"output_quant_en": false` is critical — must match `set_output_activation_quant(False)` in compile.

---

## Step 3 — Stop Edge Service

```bash
ssh camuser@aicamera1.tail605477.ts.net

# Stop the running edge service
sudo systemctl stop aicamera.service
# or if running as screen/tmux session:
screen -ls   # find session name
screen -X -S <session> quit
```

---

## Step 4 — Run Test Script

```bash
ssh camuser@aicamera1.tail605477.ts.net
cd /home/camuser/aicamera/
source edge/venv_hailo/bin/activate

# Test with a real plate image
python3 train_model/05_test_implement/test_dual_branch_lpr.py \
  --image test_output/plate_crop_0.jpg \
  --debug \
  --save-crops

# Or test with a full frame (runs vehicle detect → LP detect → OCR)
python3 train_model/05_test_implement/test_dual_branch_lpr.py \
  --image /path/to/full_frame.jpg \
  --debug
```

---

## Acceptance Criteria (Pass Gate)

| Check | Expected | Fail Action |
|-------|----------|-------------|
| `chars` | Non-empty Thai consonants + digits | Recheck HEF output_quant setting |
| `conf` | ≥ 0.6 (not NaN) | Calibration may be bad → recompile |
| `prov` | Correct Thai province name | Province classifier issue |
| `prov_conf` | ≥ 0.4 | More province-balanced training data |
| Inference time | < 100ms per plate | Normal for Hailo-8 |

---

## Step 5 — Start Edge Service

```bash
# Once tests pass, restart the service
sudo systemctl start aicamera.service

# Monitor logs
sudo journalctl -u aicamera.service -f
```

---

## What the Test Script Does

`test_dual_branch_lpr.py` mimics the full production pipeline:

```
Full frame (1080p)
  ↓  Vehicle detection  (YOLOv8 → Hailo-8 via degirum)
  ↓  LP detection       (YOLOv8 LP → Hailo-8 via degirum)
  ↓  LP crop            (+15% safe padding)
  ↓  DualBranchDegirumOCR.read_plate()
       ↓  Resize to (75, 300)
       ↓  Hailo-8 inference (DualBranchLPRNet HEF via degirum)
       ↓  _extract_tensors()  →  lpr_tensor (38,49), province_tensor (77,)
       ↓  CTC greedy decode   →  chars
       ↓  Province softmax    →  province + prov_conf
  ↓  Output table + annotated image saved to test_output/
```

---

## Quick Manual Smoke Test (No Full Frame Needed)

If you only have a plate crop image (75×300 or any size — it will be resized):

```bash
ssh camuser@aicamera1.tail605477.ts.net
source /home/camuser/aicamera/edge/venv_hailo/bin/activate

python3 - <<'EOF'
import sys
sys.path.insert(0, '/home/camuser/aicamera')
from edge.src.components.dual_branch_degirum_ocr import DualBranchDegirumOCR
import cv2

ocr = DualBranchDegirumOCR(
    model_name="DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260508",
    zoo_url="/home/camuser/aicamera/resources",
    inference_host_address="@local",
    debug=True,
)

img = cv2.imread('test_plate.jpg')    # any plate crop
result = ocr.read_plate(img)

print(f"chars:     '{result['chars']}'")
print(f"province:  '{result['province']}'")
print(f"conf:       {result['conf']:.3f}")
print(f"prov_conf:  {result['prov_conf']:.3f}")
EOF
```

---

## Deploying to aicamera2

Once aicamera1 passes all tests, replicate to aicamera2:

```bash
scp camuser@aicamera1.tail605477.ts.net:/home/camuser/aicamera/resources/DualBranchLPRNet_ThaiLP_...v20260508.hef \
    camuser@aicamera2.tail605477.ts.net:/home/camuser/aicamera/resources/

ssh camuser@aicamera2.tail605477.ts.net \
  "cp /home/camuser/aicamera/resources/dual_branch_lpr_model.json \
      /home/camuser/aicamera/resources/dual_branch_lpr_model.json.bak && \
   nano /home/camuser/aicamera/resources/dual_branch_lpr_model.json"
# Update name field, then restart service
```

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `test_dual_branch_lpr.py` | Full pipeline test — vehicle → LP → OCR |

---

## Pipeline Complete ✅

```
01_dataset/  →  02_train_pth/  →  03_compile_pth_onnx/  →  04_compile_onnx_hef/  →  05_test_implement/
Mac            agx-tail           Mac or agx-tail            GCP                       aicamera1/2
dataset        best_model.pth     _fixed.onnx                .hef                      live LPR
```

After successful deployment → push `.hef` and updated config to git:

```bash
ssh camuser@aicamera1.tail605477.ts.net
cd /home/camuser/aicamera
git add resources/DualBranchLPRNet_ThaiLP_...v20260508.hef \
        resources/dual_branch_lpr_model.json
git commit -m "feat: deploy DualBranchLPRNet v20260508 — retrained 77 provinces"
git push origin main
```
