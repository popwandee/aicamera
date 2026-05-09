# CONTEXT — Step 04: Compile ONNX → HEF on GCP

**Host:** GCP VM with Hailo AI Software Suite Docker (DFC 3.33.x)  
**Input:** `DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD_fixed.onnx`  
**Output:** `DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.hef`  
**Goal:** Compile for Hailo-8 (NOT Hailo-8L) with float32 output and normalization baked in.

See also: `RECOMPILE_GUIDE.md` in this folder for full GCP environment setup.

---

## Critical Requirements (Non-Negotiable)

```
✅ Hardware target: hailo8   (NOT hailo8l — aicamera uses full Hailo-8)
✅ output_activation_quant=False in model_script.alls
✅ Calibration from real plate crops (not random noise)
✅ Input: _fixed.onnx (after fix_instancenorm.py)
✅ Normalization baked in: mean=[127.5,127.5,127.5], std=[127.5,127.5,127.5]
```

---

## GCP Setup (One-Time)

```bash
# Start GCP VM (must have Hailo DFC 3.33.x docker image pre-installed)
gcloud compute instances start hailo-compiler-vm --zone=asia-southeast1-a

# SSH in
gcloud compute ssh hailo-compiler-vm --zone=asia-southeast1-a

# Pull Hailo docker (if not already present)
docker pull hailo_ai_sw_suite_2024-10:latest   # adjust tag to your version

# Run docker with GPU passthrough
docker run -it --rm \
  --device /dev/hailo0 \
  -v $(pwd):/workspace \
  hailo_ai_sw_suite_2024-10 bash
```

---

## Prepare Calibration Data

Calibration quality directly affects quantization accuracy.  
**Must use real plate images** — random noise gives wrong quantization ranges.

```bash
# From Mac: upload calibration images to GCP
gcloud storage cp calib.npy gs://pwd-hailo-models/

# Or generate calib.npy on GCP from synthetic images:
python3 - <<'EOF'
import numpy as np, cv2, random
from pathlib import Path

imgs_paths = sorted(Path('/workspace/calib_images').glob('*.jpg'))
random.shuffle(imgs_paths)
imgs = []
for p in imgs_paths[:1024]:
    img = cv2.resize(cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2RGB), (300, 75))
    imgs.append(img.astype(np.float32) / 255.0)

calib = np.stack(imgs).transpose(0, 3, 1, 2)  # (N, 3, 75, 300)
np.save('/workspace/calib.npy', calib)
print(f"Saved: {calib.shape}  dtype={calib.dtype}  range=[{calib.min():.2f},{calib.max():.2f}]")
# Expected: (1024, 3, 75, 300)  dtype=float32  range=[0.00, 1.00]
EOF
```

---

## Compile Command

```bash
# Inside Docker on GCP
cd /workspace

python3 compile_to_hef_v2.py \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260508_fixed.onnx \
  --calib-npy calib.npy \
  --hw-arch hailo8
```

---

## model_script.alls — What It Must Contain

The compiler script `compile_to_hef_v2.py` writes this automatically.  
**Verify it looks like this before running:**

```
model_optimization_config(calibration, batch_size=1, calibset_size=64)
model_optimization_flavor(optimization_level=0, compression_level=0)
normalization([127.5, 127.5, 127.5], [127.5, 127.5, 127.5])
set_output_activation_quant(False)
```

The `set_output_activation_quant(False)` line is **mandatory**.  
Without it, Hailo returns raw uint8 tensors instead of float32 logits → `chars = ''` always.

---

## Validating the HEF Output

```bash
# Check file exists and is non-zero
ls -lh *.hef
# Expected: 1–5 MB

# Quick Hailo parse test (inside docker)
python3 -c "
from hailo_sdk_client import ClientRunner
r = ClientRunner(hw_arch='hailo8')
r.load_har('DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260508.hef')
print('HEF loaded OK')
print('Input  layers:', [l.name for l in r.get_input_vstream_infos()])
print('Output layers:', [l.name for l in r.get_output_vstream_infos()])
"
```

Expected output layers — two tensors:
```
Output layers: ['DualBranchLPRNet_ThaiLP/lpr_head/...', 'DualBranchLPRNet_ThaiLP/province_head/...']
```

---

## Download HEF to Mac

```bash
# From Mac
gcloud storage cp gs://pwd-hailo-models/DualBranchLPRNet_ThaiLP_...v20260508.hef .

# Or via gcloud compute scp
gcloud compute scp hailo-compiler-vm:/workspace/DualBranchLPRNet_ThaiLP_...v20260508.hef . \
  --zone=asia-southeast1-a
```

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `compile_to_hef_v2.py` | Main compiler script — wraps Hailo DFC `ClientRunner` |
| `RECOMPILE_GUIDE.md` | Full GCP setup, Docker run, troubleshooting guide |
| `hailo-compiler/` | Hailo SDK artifacts from previous compile runs |
| `calib.npy` | Calibration data — regenerate from new dataset if exists |

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `InstanceNormalization not supported` | Forgot fix_instancenorm.py | Run step 03 fix |
| `HEF file is 0 bytes` | Compilation silently failed | Check docker logs, DFC version |
| `HAILO_OUT_OF_PHYSICAL_DEVICES` | hailo_platform conflict on aicamera | Use degirum only |
| `chars = ''` on aicamera | Missing `set_output_activation_quant(False)` | Recompile |
| Province always wrong | Calibration was random noise | Recompile with real crops |

---

## Next Step

After `.hef` is downloaded to Mac → proceed to `../05_test_implement/CONTEXT.md`.

```bash
# Copy hef to aicamera resources folder
scp DualBranchLPRNet_ThaiLP_...v20260508.hef \
  camuser@aicamera1.tail605477.ts.net:/home/camuser/aicamera/resources/
```
