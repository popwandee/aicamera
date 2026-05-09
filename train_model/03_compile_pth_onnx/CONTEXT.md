# CONTEXT — Step 03: Export PTH → ONNX

**Host:** agx-tail (100.100.137.9) OR Mac (if PyTorch installed)  
**Input:** `best_model.pth` from step 02  
**Output:** `DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD_fixed.onnx`  
**Goal:** Produce a Hailo-compatible ONNX file and validate on CPU before compiling to HEF.

---

## Step-by-Step

### 1. Export PTH → ONNX

Run on agx-tail (PyTorch + GPU present) or Mac (CPU export is fine):

```bash
# On Mac or agx-tail
source ~/hailo_model_zoo/hailo_models/license_plate_recognition/.venv/bin/activate    # or wherever PyTorch is installed
cd /path/to/train_model/02_train_pth/production

python3 export_to_onnx.py \
  --pth best_model.pth \
  --output DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v$(date +%Y%m%d).onnx \
  --opset 11
```
กรณีที่ต้องการรันบน AGX Xavier ต้องอัพโหลดสคริปท์ก่อน
```bash
% rsync -avz \
> /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/export_to_onnx.py \
> /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/fix_instancenorm.py \
> /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/validate_onnx_cpu.py \
> agx@100.100.137.9:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/

python3 export_to_onnx.py \
  --pth /mnt/pwd-data/runs/lprnet_dual_v2/best_model.pth \
  --output DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v$(date +%Y%m%d).onnx \
  --opset 11
```

If `export_to_onnx.py` does not exist yet, use this inline export:

```python
#!/usr/bin/env python3
"""export_to_onnx.py — Export DualBranchLPRNet PTH to ONNX (opset 11)"""
import sys, argparse, torch
from datetime import datetime
from pathlib import Path

from lprnet_dual_branch import DualBranchLPRNet

parser = argparse.ArgumentParser()
parser.add_argument('--pth',    default='/mnt/pwd-data/runs/lprnet_dual_v2/best_model.pth')
parser.add_argument('--output', default=f'DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v{datetime.now().strftime("%Y%m%d")}.onnx')
parser.add_argument('--opset',  type=int, default=11)
args = parser.parse_args()

PTH_PATH = args.pth
ONNX_OUT = args.output
OPSET    = args.opset

# Use CPU for ONNX export — keeps the graph device-agnostic
device = 'cpu'
model  = DualBranchLPRNet().to(device)
state  = torch.load(PTH_PATH, map_location=device)
# Handle checkpoint dict (train_dual_branch.py saves full checkpoint)
if 'model_state_dict' in state:
    state = state['model_state_dict']
model.load_state_dict(state)
model.eval()

dummy = torch.zeros(1, 3, 75, 300, device=device)  # (B, C, H, W)

with torch.no_grad():
    torch.onnx.export(
        model, dummy, ONNX_OUT,
        opset_version=OPSET,
        input_names=['input'],
        output_names=['lpr_logits', 'province_logits'],
        dynamic_axes={'input': {0: 'batch'}},
        do_constant_folding=True,
    )

print(f"Exported: {ONNX_OUT}")

# Quick sanity check
import onnx
m = onnx.load(ONNX_OUT)
onnx.checker.check_model(m)
print("ONNX model is valid.")

# Print output shapes
import onnxruntime as ort
sess   = ort.InferenceSession(ONNX_OUT, providers=['CPUExecutionProvider'])
inputs = {sess.get_inputs()[0].name: dummy.numpy()}
outs   = sess.run(None, inputs)
print(f"lpr_logits shape:      {outs[0].shape}")   # expect (1, 49, 38)
print(f"province_logits shape: {outs[1].shape}")   # expect (1, 77)
```

### 2. Fix InstanceNorm (MANDATORY before HEF compile)

```bash
python3 fix_instancenorm.py \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.onnx

# Output: DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260508_fixed.onnx
```

**Why:** Hailo DFC 3.33.x cannot parse InstanceNorm subgraphs. This step substitutes them
with BatchNorm equivalents that Hailo can compile.

Verify the fix succeeded:
```bash
python3 -c "
import onnx
m = onnx.load('DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260508_fixed.onnx')
types = {n.op_type for n in m.graph.node}
print('Node types in fixed model:', sorted(types))
assert 'InstanceNormalization' not in types, 'InstanceNorm still present!'
print('OK — no InstanceNorm nodes.')
"
```

### 3. Validate on CPU (CRITICAL GATE)

```bash
# Requires: pip install onnxruntime opencv-python
python3 validate_onnx_cpu.py --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v202
60509_fixed.onnx --test-synthetic
```
ONNX model: DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx

ONNX inputs:  [('input', ['batch', 3, 75, 300], 'tensor(float)')]
ONNX outputs: [('lpr_logits', ['Convlpr_logits_dim_0', 49, 38], 'tensor(float)'), ('province_logits', ['Gemmprovince_logits_dim_0', 77], 'tensor(float)')]
Input: synthetic random-noise crop (75×300 RGB)

Input: shape=(1, 3, 75, 300)  dtype=float32
  pixel range: [-1.0000, 1.0000]

============================================================
  ONNX CPU INFERENCE RESULTS (ground truth / no quantization)
============================================================

  Output[0] name='lpr_logits'  raw_shape=(1, 49, 38)  squeezed=(49, 38)  dtype=float32
    min=-761.0559  max=134.4764  mean=-18.1743

  Output[1] name='province_logits'  raw_shape=(1, 77)  squeezed=(77,)  dtype=float32
    min=-47.1473  max=-25.3586  mean=-36.9746
    → Identified as Province tensor (77,)
ERROR: Could not identify LPR tensor in ONNX output

  Province: 'สุราษฎร์ธานี' (conf=0.3554)
  Top-5:
    [67] สุราษฎร์ธานี        : 0.3554
    [13] เชียงใหม่           : 0.3291
    [28] ปทุมธานี            : 0.1294
    [75] อุทัยธานี           : 0.0514
    [29] ประจวบคีรีขันธ์     : 0.0449

============================================================
  INTERPRETATION:
============================================================

#### ทดสอบด้วยป้้ายจริง
```bash
python3 validate_onnx_cpu.py \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx \
  --crop 1กก_5367กรุงเทพมหานคร_000102.jpg 
```

**MUST see:** `chars = 'กข1234'` (or similar) — NOT `chars = ''`

If `chars = ''` → model is still not recognizing characters → do NOT compile to HEF.
Go back to step 02 and investigate: more data, different augmentation, more epochs.

---

## ONNX Output Shape Reference

```
lpr_logits:      (batch=1, C=49, T=38)   ← (B, C, T) — note C-first
province_logits: (batch=1, 77)

ONNX → PyTorch CTC:
  lpr_logits.permute(2, 0, 1)  →  (T=38, B=1, C=49)  ← required by CTCLoss

ONNX → Hailo reorder (automatic on-chip):
  Hailo outputs (B=1, T=38, C=49)  ← T-first after hardware reorder

Decoding from Hailo output:
  argmax(axis=-1)  →  (B, T)  →  CTC collapse  →  char indices  →  LPR_CHARS
```

---

## Validate Script Quick Test (No Real Plate)

```bash
# Use a synthetic plate image
python3 validate_onnx_cpu.py \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx  \
  --test-synthetic

# This generates a white plate "กข 1234 กรุงเทพ" and runs inference
# Expected: chars contains recognizable Thai chars, province 'กรุงเทพ'
```

---

## Output Files

```
03_compile_pth_onnx/
├── best_model.pth                                             ← from step 02
├── training_stats.json                                        ← training history
├── DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.onnx
├── DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD_fixed.onnx   ← SEND TO GCP
├── fix_instancenorm.py
└── validate_onnx_cpu.py
```

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `fix_instancenorm.py` | Removes InstanceNorm subgraphs incompatible with Hailo DFC |
| `validate_onnx_cpu.py` | Run ONNX on CPU — validate chars ≠ '' before compiling |

---

## Next Step

Transfer `_fixed.onnx` to GCP, then proceed to `../04_compile_onnx_hef/CONTEXT.md`.

```bash
# Download to Mac
scp agx@100.100.137.9:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.onnx \
    /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/production/

# Upload to GCP (example — adjust bucket name)
gcloud storage cp \
  DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx  \
  gs://pwd-hailo-models/

gcloud compute scp Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/production/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx hailo-compiler:~
```
sqh@SqHs-MacBook-Pro production % gcloud compute ssh hailo-compiler
Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine': 
Welcome to Ubuntu 22.04.5 LTS (GNU/Linux 6.8.0-1053-gcp x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

 System information as of Fri May  8 22:02:23 UTC 2026

  System load:  0.16               Processes:             129
  Usage of /:   24.3% of 48.27GB   Users logged in:       0
  Memory usage: 4%                 IPv4 address for ens4: 10.128.0.2
  Swap usage:   0%

 * Strictly confined Kubernetes makes edge and IoT secure. Learn how MicroK8s
   just raised the bar for easy, resilient and secure K8s cluster deployment.

   https://ubuntu.com/engage/secure-kubernetes-at-the-edge

Expanded Security Maintenance for Applications is not enabled.

3 updates can be applied immediately.
To see these additional updates run: apt list --upgradable

21 additional security updates can be applied with ESM Apps.
Learn more about enabling ESM Apps service at https://ubuntu.com/esm

New release '24.04.4 LTS' available.
Run 'do-release-upgrade' to upgrade to it.


*** System restart required ***
Last login: Fri May  8 01:09:50 2026 from 49.228.246.162
admin_pwdvisionworks_com@hailo-compiler:~$ ls
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed.onnx  dualbranch  hailo-compiler  snap