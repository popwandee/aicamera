# GUARDRAIL.md — Hard Constraints for DualBranchLPRNet Pipeline

These rules ensure the model remains compatible with **Hailo-8 on Raspberry Pi 5** (aicamera).
Violating any of these will break the pipeline at some stage and require full retraining/recompilation.

---

## 🔴 NEVER Change These Constants

```python
# ── Model output dimensions — frozen forever ──────────────────────────────
LPR_NUM_CLASSES = 49          # 48 LPR chars + 1 BLANK
LPR_BLANK       = 48          # BLANK is LAST index, NOT 0
N_PROVINCES     = 77          # Thai provinces (see province_map.py)

# ── Model input shape ─────────────────────────────────────────────────────
INPUT_H, INPUT_W = 75, 300   # pixels  (NCHW: B × 3 × 75 × 300)

# ── ONNX output shapes ───────────────────────────────────────────────────
# lpr_logits:      (B, 49, 38)  = (B, C, T)   — T=38 time-steps
# province_logits: (B, 77)
# Hailo reorders lpr to (B, 38, 49) = (B, T, C)  after hardware reorder

# ── CTC axis convention ──────────────────────────────────────────────────
# PyTorch CTCLoss expects log-probs of shape (T, B, C)
# Before passing to CTCLoss: lpr_logits.permute(2, 0, 1)  → (38, B, 49)
# For greedy CTC decode from Hailo output (B,38,49): argmax over axis=-1
```

Changing any of these requires:
- Rewriting `lprnet_dual_branch.py`
- Updating `charset.py` and `province_map.py`
- Re-generating the entire dataset
- Recompiling the HEF
- Updating `dual_branch_degirum_ocr.py` on aicamera

**Cost: 1–3 days of work. Do not touch them.**

---

## 🔴 Dataset Filename Format is Strict

```
{part1}_{part2}_{id:06d}.jpg

Rules:
  id        : exactly 6 decimal digits (000001, not 1 or 01)
  part1     : consonants only (Thai consonants from LPR_CHARS)
  part2     : digits + province name concatenated (e.g. 1234เชียงใหม่)
  province  : must match exactly one entry in PROVINCES list in province_map.py
              (short form: 'กรุงเทพ' NOT 'กรุงเทพมหานคร')

Valid:   กข_1234เชียงใหม่_000001.jpg
Valid:   ก_567ชลบุรี_000002.jpg
INVALID: กข1234เชียงใหม่_1.jpg          (no underscore split, short id)
INVALID: กข_1234กรุงเทพมหานคร_000001.jpg (wrong province short-form)
```

The parser in `train_dual_branch.py`:
```python
parts = img_path.stem.split('_')
plate_text = ''.join(parts[:-1])  # joins all parts except the 6-digit id
```

---

## 🔴 Province List — Use Short Forms Only

Must match `02_train_pth/province_map.py` EXACTLY:

```python
# ✅ Correct (short form used in province_map.py)
'กรุงเทพ'          # index 1  — NOT กรุงเทพมหานคร
'นครราชสีมา'       # index 20
'พระนครศรีอยุธยา'  # index 32

# ❌ Wrong — these will classify as UNKNOWN (index -1), breaking province loss
'กรุงเทพมหานคร'
'โคราช'
'อยุธยา'
```

---

## 🔴 Input Normalization — Must Match Between Training and HEF

Training (`train_dual_branch.py`):
```python
transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
# = (pixel/255 - 0.5) / 0.5 = (pixel - 127.5) / 127.5
# Input range: float32 [-1.0, +1.0]
```

HEF model_script.alls bakes this normalization in:
```
normalization([127.5, 127.5, 127.5], [127.5, 127.5, 127.5])
```
This means **HEF accepts raw uint8 RGB [0–255]** and applies normalization on-chip.

**Do NOT change normalization parameters.** A mismatch causes silent accuracy degradation.

---

## 🔴 HEF Must Use `output_activation_quant=False`

```
# model_script.alls (04_compile_onnx_hef/compile_to_hef_v2.py)
model_optimization_config(calibration, batch_size=1, calibset_size=64)
model_optimization_flavor(optimization_level=0, compression_level=0)
set_output_activation_quant(False)    ← THIS LINE IS MANDATORY
```

Without it: Hailo returns raw uint8 output (values `[78–219]`), NOT dequantized logits.
The OCR decoder sees uint8 as logits → BLANK always wins → `chars = ''` forever.

---

## 🔴 Inference Framework — degirum Only (NOT hailo_platform directly)

All three models on aicamera must use `degirum`:
```python
# ✅ Correct
zoo = degirum.connect(inference_host_address="@local", zoo_url=str(RESOURCES_DIR))
model = zoo.load_model("DualBranchLPRNet_ThaiLP_...")

# ❌ Wrong — causes HAILO_OUT_OF_PHYSICAL_DEVICES conflict
from hailo_platform import VDevice, HailoSchedulingAlgorithm
```

Reason: `hailo_platform` and `degirum` both open the Hailo device exclusively.
Running both simultaneously crashes with `HAILO_OUT_OF_PHYSICAL_DEVICES`.

---

## 🟡 Training — Backbone Learning Rate Must Stay Lower

```python
# train_dual_branch.py — optimizer setup
optimizer = optim.AdamW([
    {'params': backbone_params, 'lr': args.learning_rate * 0.1},  # ResNet18 frozen-ish
    {'params': head_params,     'lr': args.learning_rate},         # heads train fast
], weight_decay=args.weight_decay)
```

Using the same LR for backbone and heads causes catastrophic forgetting of ImageNet features.

---

## 🟡 ONNX Export — Must Fix InstanceNorm Before HEF Compile

```bash
# Step 1: export to ONNX (opset 11 or 12)
# Step 2: MANDATORY fix before compile
python3 fix_instancenorm.py DualBranchLPRNet_v....onnx
# Step 3: validate CPU accuracy
python3 validate_onnx_cpu.py --onnx DualBranchLPRNet_v...._fixed.onnx --crop plate.jpg
```

Hailo DFC 3.33.x **cannot parse InstanceNorm subgraphs** — compilation will fail silently
or produce a non-functional HEF.

---

## 🟡 Calibration Data Quality

Minimum requirements for HEF calibration:
- ≥ 64 images (compile_to_hef_v2.py default)
- **Recommended: 1,000+ real or high-quality synthetic plate crops**
- Must be preprocessed to `float32 [0,1]` shape `(N, 3, 75, 300)` and saved as `.npy`
- **Never use random noise** — produces incorrect quantization ranges

```python
# Generate calib.npy from image folder
import numpy as np, cv2
from pathlib import Path

imgs = []
for p in sorted(Path('calib_images').glob('*.jpg'))[:1024]:
    img = cv2.resize(cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2RGB), (300, 75))
    imgs.append(img.astype(np.float32) / 255.0)

np.save('calib.npy', np.stack(imgs).transpose(0, 3, 1, 2))  # (N,3,75,300)
```

---

## 🟡 Accuracy Gates — Do Not Skip

| Gate | Check | Minimum |
|------|-------|---------|
| After training | `val plate_acc` in training log | ≥ 85% |
| After ONNX export | `validate_onnx_cpu.py` on real crop | `chars ≠ ''` |
| After HEF compile | `test_dual_branch_lpr.py` on aicamera | `chars ≠ ''`, `conf ≥ 0.6` |

---

## Summary Checklist Before Each Stage

```
Before training:
  [ ] dataset filename format verified (6-digit id, underscore split)
  [ ] all provinces use short form matching province_map.py
  [ ] train/val split done (no overlap)
  [ ] LPR_NUM_CLASSES=49, N_PROVINCES=77 unchanged

Before ONNX export:
  [ ] plate_acc ≥ 85% on val set
  [ ] fix_instancenorm.py run on output
  [ ] validate_onnx_cpu.py passes with chars ≠ ''

Before HEF compile:
  [ ] using _fixed.onnx (post fix_instancenorm)
  [ ] calib.npy from real plate images (not random)
  [ ] set_output_activation_quant(False) in model_script.alls

Before deploy to aicamera:
  [ ] .hef file size 1–5 MB (not 0 bytes — compile failure)
  [ ] .json model config updated with new .hef filename
  [ ] edge service stopped before replacing .hef
```
