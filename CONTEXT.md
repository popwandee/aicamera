# CONTEXT.md — DualBranchLPRNet Integration for aicamera
> Context Engineering document for Claude Code sessions on this project.  
> Last updated: 2026-05-07  
> Status: **IN DEBUG** — degirum loads OK, inference UINT8 type error fixed, pending retest

---

## Project Purpose
Edge AI license-plate recognition (LPR) running on Raspberry Pi 5 + Hailo-8 NPU.
We are integrating **DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503**
— a custom-trained two-branch CTC model for Thai plates — as the new primary OCR engine,
replacing the previous YOLOv8 character-detection OCR model.

## Repository
- GitHub: https://github.com/popwandee/aicamera.git
- Working devices: aicamera1 (100.126.178.74), aicamera2 (100.110.20.53)
- SSH: `ssh camuser@aicamera1` password: admin88366

## Stable Tag (created before this work started)
```bash
git tag stable-before-dualbranch-lpr
```
Revert if needed: `git checkout stable-before-dualbranch-lpr`

---

## Architecture Decision: All-degirum (NO hailo_platform)

**Critical**: `hailo_platform.VDevice` and degirum use DIFFERENT HAL layers.
They CANNOT coexist in the same process:
- If hailo_platform opens first → degirum gets `HAILO_DEVICE_IN_USE`
- If degirum opens first → hailo_platform gets `HAILO_OUT_OF_PHYSICAL_DEVICES` (device physically
  disappears after degirum use — not just "busy")

**Solution adopted**: Use degirum for ALL models. One shared device handle. No hailo_platform.

```
Camera Frame
  │
  ▼
DetectionProcessor.process_enhanced_pipeline()
  │
  ├─► detect_vehicles()       — dg.load_model("yolov8n_relu6_car")        via degirum/@local
  ├─► detect_license_plates() — dg.load_model("yolov8n_relu6_lp")         via degirum/@local
  │
  └─► DualBranchDegirumOCR.read_plate()
            — dg.load_model("DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503")
            — same degirum/@local, same Hailo device, no conflict
```

`dual_branch_lpr_ocr.py` (hailo_platform-based) is kept on disk as backup but is NOT used.

---

## DualBranchLPRNet Model Facts

| Property | Value |
|----------|-------|
| HEF file | `resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260503/…_fixed.hef` |
| Compiled with quantization | **YES** — Hailo input type = UINT8 |
| Input to degirum | (75, 300, 3) **uint8 RGB** HWC — no batch dim |
| degirum JSON InputQuantEn | **true** (Hailo handles uint8→float dequant on-chip) |
| degirum JSON InputType | **OMITTED** — "NPArray" is not a valid value in this degirum version |
| Output 1 (conv13) | shape (1, 38, 49) — CTC logits, 38 timesteps, 49 classes |
| Output 2 (fc1) | shape (77,) — province logits |

### CTC Vocabulary — LPR_CHARS (48 printable chars, from charset.py CHARS[:48])
```python
LPR_CHARS = [
    '0','1','2','3','4','5','6','7','8','9',          # indices 0-9
    'ก','ข','ค','ฆ','ง','จ','ฉ','ช',                 # 10-17
    'ซ','ญ','ฎ','ฐ','ณ','ด','ต','ถ',                 # 18-25
    'ท','ธ','น','บ','ป','ผ','ฝ','พ',                 # 26-33
    'ฟ','ภ','ม','ย','ร','ล','ว','ศ',                 # 34-41
    'ษ','ส','ห','ฬ','อ','ฮ',                         # 42-47
]
CTC_BLANK_IDX = 48   # blank is LAST — NOT index 0
LPR_NUM_CLASSES = 49
```
⚠️  CTC blank is index **48** (= len(LPR_CHARS)), not 0. A common mistake.

### Province Vocabulary (77 classes, from province_map.py)
```python
PROVINCES = [
    'กระบี่','กรุงเทพ','กาญจนบุรี', ...  # exact training order
]
# Uses SHORT form: 'กรุงเทพ' NOT 'กรุงเทพมหานคร'
```
Full list is in `edge/src/components/dual_branch_degirum_ocr.py`.

### Preprocessing (CORRECT — confirmed by Hailo error)
```python
# HEF compiled WITH quantization → input must be uint8
# Hailo's on-chip dequant maps [0,255] → [-1,1] using baked scale/zero_point
def preprocess_for_lprnet(plate_bgr):
    rgb    = cv2.cvtColor(plate_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (300, 75), interpolation=cv2.INTER_LINEAR)
    return resized  # (75, 300, 3) uint8
```
**Do NOT** pre-normalize to float32 [-1,1] — the HEF does this internally.

### Output Tensor Identification (by SHAPE, not name)
```python
if arr.ndim == 3:                        # (1, 38, 49) → LPR CTC logits
    lpr_logits = arr
elif arr.ndim == 1 and arr.shape[0] == 77:   # (77,) → Province logits
    prov_logits = arr
```
Output tensor names ('conv13', 'fc1') do NOT contain expected keywords. Use shape only.

---

## Key Files

| File | Role | Status |
|------|------|--------|
| `edge/src/components/dual_branch_degirum_ocr.py` | **PRIMARY OCR engine** — degirum-based | Active |
| `edge/src/components/dual_branch_lpr_ocr.py` | hailo_platform-based backup | Inactive (device conflict) |
| `edge/src/components/detection_processor.py` | Imports DualBranchDegirumOCR | Updated |
| `edge/src/components/parallel_ocr_processor.py` | Comments updated | Updated |
| `test_dual_branch_lpr.py` | Full pipeline test: detect→crop→OCR | Updated |
| `resources/DualBranchLPRNet_.../...json` | degirum config (InputQuantEn=true) | Updated |
| `scripts/deploy_dualbranch_degirum.sh` | Sync + test on aicamera1 | Active |

---

## degirum JSON Config (current, correct)
```json
{
    "ConfigVersion": 6,
    "Checksum": "847cc6d5...",
    "DEVICE": [{"DeviceType": "HAILO8", "RuntimeAgent": "HAILORT",
                 "SupportedDeviceTypes": "HAILORT/HAILO8"}],
    "PRE_PROCESS": [{"InputN":1,"InputH":75,"InputW":300,"InputC":3,
                     "InputQuantEn": true}],
    "MODEL_PARAMETERS": [{"ModelPath": "...fixed.hef"}],
    "POST_PROCESS": [{"OutputPostprocessType": "None"}]
}
```
`InputType` is **omitted** — "NPArray" is unknown in this degirum version.  
`InputQuantEn: true` — degirum passes uint8 to Hailo; Hailo dequantizes on-chip.

---

## Debug History (errors solved, in order)

| # | Error | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | CTC output = 'พ' only | CTC_BLANK_IDX=0 (wrong) | Set to 48 (= len(LPR_CHARS)) |
| 2 | Wrong tensor mapping | Searched tensor names ('prov') | Shape-based detection instead |
| 3 | Wrong vocab | Guessed ordering | Copied exact from charset.py + province_map.py |
| 4 | activate() deprecated | ROUND_ROBIN scheduler | Removed `with ng.activate()` |
| 5 | HAILO_DEVICE_IN_USE | hailo_platform before degirum | Degirum first, hailo_platform after |
| 6 | HAILO_OUT_OF_PHYSICAL_DEVICES | Two HAL layers in same process | Eliminated hailo_platform entirely |
| 7 | `Unknown InputType: NPArray` | Invalid field in degirum JSON | Removed InputType field |
| 8 | `DG_FLT does not match UINT8` | HEF compiled with quant, we sent float32 | InputQuantEn=true + uint8 input |

---

## Current Status (as of 2026-05-07 17:13)
- ✅ Steps 1a, 2, 3 pass: degirum loads vehicle + LP detection models, detects 1 car + 1 plate
- ✅ Step 1b passes: DualBranchDegirumOCR.load() succeeds
- ❌ Step 4 OCR fails: `DG_FLT does not match Hailo input type DG_UINT8`
- 🔧 Fix applied: `InputQuantEn: true` + `preprocess_for_lprnet()` returns uint8 (not float32)
- ⏳ **Needs retest**: run `bash scripts/deploy_dualbranch_degirum.sh` on Mac

## Next Steps After Retest
1. If OCR now runs → check if `_extract_tensors()` picks up the right arrays
   - If `_log_result_structure()` fires → copy the attribute dump from the log and fix `_extract_tensors()`
2. If new error → read it and fix
3. Once test passes → push to git + deploy to aicamera2

---

## Environment
- Python venv: `edge/venv_hailo` — always `source edge/venv_hailo/bin/activate`
- degirum, hailo_platform both installed in venv_hailo
- Run tests from `/home/camuser/aicamera/` (project root)
- Test output: `/home/camuser/aicamera/test_output/`
- Logs: `/home/camuser/aicamera/edge/logs/` and `/tmp/pipeline_test_degirum.log`
