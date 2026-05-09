# CONTEXT — DualBranchLPRNet Retraining Pipeline

**Project:** PWD Vision Works — AI Camera LPR System  
**Model:** DualBranchLPRNet (Thai License Plate Recognition)  
**Target hardware:** Raspberry Pi 5 + Hailo-8 NPU (`aicamera1`, `aicamera2`)  
**Pipeline host:** Mac (prep) → AGX Xavier / agx-tail (train) → GCP (compile) → aicamera (deploy)

---

## Why We Are Retraining

The previous HEF was compiled from a model trained on 194 real LP crops, all dominated by Bangkok (กรุงเทพ) plates. Diagnostic result on hardware:

```
Hailo uint8 output:  LPR values [78–219], Province values [185–188]
After dequant:       BLANK logit = +9.50  vs  char logits ≈ −23.18
ONNX CPU test:       plate-like input → CTC: ''  (all BLANK, confidence 92%)
ROOT CAUSE:          Insufficient diversity — model learned BLANK as safe default
```

**The fix requires two parallel changes:**
1. Retrain with ≥5,000 diverse images (all 77 provinces, multiple conditions)
2. Recompile HEF with `output_activation_quant=False` so Hailo returns float32, not uint8

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  01_dataset/                                                             │
│  Mac — generate / collect / label LP crops                              │
│    synthetic_lpr_script.py  →  synthetic_plates/  (5,000–20,000 imgs)  │
│    crop_lp.py               →  lp_crops/         (real photos)         │
│    Merge + split 80/20 train/val                                        │
└────────────────────────┬────────────────────────────────────────────────┘
                         │  rsync to agx-tail
┌────────────────────────▼────────────────────────────────────────────────┐
│  02_train_pth/                                                           │
│  agx-tail  (Jetson AGX Xavier, 100.100.137.9)                           │
│    train_dual_branch.py  →  best_model.pth                              │
│    Target: plate_acc ≥ 85%,  char_acc ≥ 92%,  prov_acc ≥ 90%          │
└────────────────────────┬────────────────────────────────────────────────┘
                         │  scp best_model.pth to Mac
┌────────────────────────▼────────────────────────────────────────────────┐
│  03_compile_pth_onnx/                                                    │
│  agx-tail OR Mac (PyTorch export)                                        │
│    export_to_onnx.py        →  DualBranchLPRNet_vYYYYMMDD.onnx         │
│    fix_instancenorm.py      →  ..._fixed.onnx                           │
│    validate_onnx_cpu.py     →  verify chars ≠ '' before compiling       │
└────────────────────────┬────────────────────────────────────────────────┘
                         │  upload to GCP
┌────────────────────────▼────────────────────────────────────────────────┐
│  04_compile_onnx_hef/                                                    │
│  GCP VM — Hailo DFC 3.33.x docker                                       │
│    compile_to_hef_v2.py     →  DualBranchLPRNet_vYYYYMMDD.hef          │
│    MUST: output_activation_quant=False  in model_script.alls            │
└────────────────────────┬────────────────────────────────────────────────┘
                         │  scp .hef to aicamera1/2
┌────────────────────────▼────────────────────────────────────────────────┐
│  05_test_implement/                                                       │
│  aicamera1.tail605477.ts.net  (100.126.178.74)                          │
│  aicamera2.tail605477.ts.net  (100.110.20.53)                           │
│    test_dual_branch_lpr.py  →  validate end-to-end accuracy             │
│    Update resources/ .hef + .json                                       │
│    Restart edge service                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Model Architecture Summary

| Parameter | Value |
|---|---|
| Model | DualBranchLPRNet (ResNet18 backbone truncated at layer2) |
| Input | `(B, 3, 75, 300)` float32, normalized `[-1, 1]` |
| HEF input | uint8 `[0, 255]` — normalization baked in via model_script |
| Branch 1 | CTC head → `(B, 49, 38)` = `(B, C, T)` in ONNX |
| Branch 2 | Province classifier → `(B, 77)` |
| BLANK index | `48` (last index, NOT 0) |
| LPR charset | 48 chars: digits `0-9` (idx 0–9) + Thai consonants (idx 10–47) |
| Province count | 77 (see `province_map.py`) |
| Hailo output shape | `(B, 38, 49)` after hardware reorder (T-first) |

---

## Network / SSH Access

```bash
# AGX Xavier (training)
ssh agx@agx-tail             # HostName 100.100.137.9 (Tailscale)
# or
ssh agx@100.100.137.9

# aicamera1 (primary test target)
ssh camuser@aicamera1.tail605477.ts.net   # 100.126.178.74
# password: admin88366

# aicamera2 (currently online)
ssh camuser@aicamera2.tail605477.ts.net   # 100.110.20.53

# lprserver (backend)
ssh devuser@lprserver.tail605477.ts.net   # 100.95.46.128
```

---

## Current Dataset Status

| Dataset | Location | Count | Notes |
|---|---|---|---|
| Existing synthetic | `01_dataset/dataset_thai/train/` | 100,010 | Only 8 provinces covered |
| Existing synthetic (val) | `01_dataset/dataset_thai/test/` | 10,010 | Same limitation |
| Real LP crops | `01_dataset/lp_crops/` | 194 | Bangkok-dominated |
| aicamera2 captures | `01_dataset/aicamera2_images/` | 32 | Raw (not labeled) |
| aicamera1 captures | `01_dataset/aicamera1_images/` | varies | Raw (not labeled) |

**Priority:** Generate ≥5,000 synthetic plates covering all 77 provinces + augmentation variations.

---

## Key Files in This Pipeline

```
train_model/
├── CLAUDE.md                          ← AI assistant instructions
├── GUARDRAIL.md                       ← Hard constraints (DO NOT violate)
├── CONTEXT.md                         ← This file
│
├── 01_dataset/
│   ├── CONTEXT.md                     ← Dataset prep instructions
│   ├── synthetic_lpr_script.py        ← Synthetic plate generator (NEW)
│   ├── crop_lp.py                     ← Interactive real-photo crop tool
│   └── lp_crops/                      ← 194 real crops (Bangkok-heavy)
│
├── 02_train_pth/
│   ├── CONTEXT.md                     ← Training instructions
│   ├── train_dual_branch.py           ← Main training script
│   ├── lprnet_dual_branch.py          ← Model definition
│   ├── charset.py                     ← LPR character set
│   └── province_map.py               ← Province list (77)
│
├── 03_compile_pth_onnx/
│   ├── CONTEXT.md                     ← ONNX export instructions
│   ├── fix_instancenorm.py            ← Removes InstanceNorm subgraphs
│   └── validate_onnx_cpu.py           ← CPU validation (MUST pass before HEF)
│
├── 04_compile_onnx_hef/
│   ├── CONTEXT.md                     ← GCP HEF compile instructions
│   ├── compile_to_hef_v2.py           ← Hailo DFC compiler script
│   └── RECOMPILE_GUIDE.md            ← Detailed GCP setup guide
│
└── 05_test_implement/
    ├── CONTEXT.md                     ← Deploy and test instructions
    └── test_dual_branch_lpr.py        ← End-to-end pipeline test
```

---

## Version Naming Convention

All model artifacts must include date in the filename:

```
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.pth
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.onnx
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD_fixed.onnx
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.hef
```

Example for today: `v20260508`
