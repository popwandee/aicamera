# DualBranchLPRNet — Train-to-Deploy Procedure

**Project:** PWD Vision Works — AI Camera LPR System  
**Model:** DualBranchLPRNet (Thai License Plate Recognition, 77 provinces)  
**Target hardware:** Raspberry Pi 5 + Hailo-8 NPU (`aicamera1`, `aicamera2`)  
**Last updated:** 2026-05-09

---

## Pipeline Overview

```
Mac (dataset)  →  AGX Xavier (train)  →  Mac/AGX (ONNX export)  →  GCP (compile HEF)  →  aicamera1/2 (deploy)
 01_dataset/       02_train_pth/          03_compile_pth_onnx/       04_compile_onnx_hef/   05_test_implement/
```

| Step | Folder | Host | Output |
|------|--------|------|--------|
| 1 | `01_dataset/` | Mac | `dataset_thai/train/` + `test/` |
| 2 | `02_train_pth/` | agx-tail | `best_model.pth` |
| 3 | `03_compile_pth_onnx/` | agx-tail หรือ Mac | `*_fixed_instancenorm.onnx` |
| 4 | `04_compile_onnx_hef/` | GCP (`hailo-compiler`) | `*.hef` |
| 5 | `05_test_implement/` | aicamera1, aicamera2 | Live LPR ✅ |

---

## SSH / Network Access

```bash
# AGX Xavier (training host)
ssh agx@100.100.137.9                              # Tailscale alias: agx-tail

# GCP Hailo compiler VM
gcloud compute ssh hailo-compiler                  # zone: asia-southeast1-a
# Passphrase key: ~/.ssh/google_compute_engine

# aicamera1 (primary deploy target)
ssh camuser@aicamera1.tail605477.ts.net            # 100.126.178.74  pw: admin88366

# aicamera2 (secondary)
ssh camuser@aicamera2.tail605477.ts.net            # 100.110.20.53   pw: admin88366

# lprserver (backend)
ssh lpruser@lprserver.tail605477.ts.net            # 100.95.46.128   pw: admin88366
```

---

## Version Naming Convention

```
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.pth
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.onnx
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD_fixed_instancenorm.onnx
DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.hef
```

ตัวอย่าง: `v20260509`

---

## Step 01 — Dataset Preparation (Mac)

### สร้าง Synthetic Plates

```bash
cd /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/01_dataset/

# สร้างภาพ synthetic ≥ 5,000 รูป ครบ 77 จังหวัด
python3 synthetic_lpr_script.py \
  --output-dir synthetic_plates/ \
  --count 5000 \
  --province-balance

# ตรวจสอบการกระจายจังหวัด
python3 verify.py --dir synthetic_plates/
```

### ตัด Crops จากภาพจริง

```bash
# Interactive crop tool (ใช้ภาพจาก aicamera1/2)
python3 crop_lp.py --input aicamera1_images/ --output lp_crops/
```

### ดาวน์โหลดภาพจาก aicamera

```bash
# rsync ภาพจาก aicamera1 มา Mac
rsync -avz --progress \
  camuser@aicamera1.tail605477.ts.net:/home/camuser/aicamera/test_output/ \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/01_dataset/aicamera1_images/
```

### Split Dataset 80/20

```bash
python3 split_dataset.py \
  --input synthetic_plates/ lp_crops/ \
  --train-out dataset_thai/train/ \
  --val-out   dataset_thai/test/ \
  --ratio 0.8
```

### ส่ง Dataset ไป AGX

```bash
rsync -avz --progress \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/01_dataset/dataset_thai/ \
  agx@100.100.137.9:/mnt/pwd-data/lpr_dataset/

# ตรวจสอบ
ssh agx@100.100.137.9 "ls /mnt/pwd-data/lpr_dataset/train/ | wc -l"
```

---

## Step 02 — Training on AGX Xavier

### ส่งสคริปท์ไป AGX

```bash
rsync -avz \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/02_train_pth/ \
  agx@100.100.137.9:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/
```

### เปิด tmux และ Activate venv

```bash
ssh agx@100.100.137.9
tmux new -s train
# หรือ attach ถ้ามีอยู่แล้ว
tmux attach -t train

source ~/hailo_model_zoo/hailo_models/license_plate_recognition/.venv/bin/activate
cd ~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/

# ตรวจ GPU
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Expected: True  Xavier
```

### คำสั่ง Train

```bash
python3 train_dual_branch.py \
  --train_dir /mnt/pwd-data/lpr_dataset/train \
  --test_dir  /mnt/pwd-data/lpr_dataset/test  \
  --max_epochs 150         \
  --train_batch_size 32    \
  --test_batch_size  32    \
  --learning_rate 5e-4     \
  --weight_decay  1e-4     \
  --dropout_rate  0.3      \
  --prov_weight   0.3      \
  --output_dir /mnt/pwd-data/runs/lprnet_dual_v2 \
  --device cuda            \
  --num_workers 4          \
  --es_patience 15

# Detach tmux: Ctrl-B แล้ว D
```

### Monitor Training

```bash
# ดู log แบบ live
tail -f /mnt/pwd-data/runs/lprnet_dual_v2/training.log

# ดูเฉพาะ accuracy
grep "Val Loss" /mnt/pwd-data/runs/lprnet_dual_v2/training.log | tail -20
```

### Accuracy Gates (ผ่านก่อนค่อยไป Step 03)

| Metric | ต้องผ่าน | ถ้าไม่ผ่าน |
|--------|---------|-----------|
| `Plate Acc` | ≥ 85% | เพิ่มข้อมูล หรือ epochs |
| `Char Acc` | ≥ 92% | ตรวจ augmentation |
| `Prov Acc` | ≥ 90% | ตรวจ province balance |

### ดาวน์โหลด Checkpoint มา Mac

```bash
# Best model
scp agx@100.100.137.9:/mnt/pwd-data/runs/lprnet_dual_v2/best_model.pth \
    /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/02_train_pth/production/

# Training stats + logs
scp agx@100.100.137.9:/mnt/pwd-data/runs/lprnet_dual_v2/training_stats.json \
    /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/02_train_pth/production/

scp agx@100.100.137.9:/mnt/pwd-data/runs/lprnet_dual_v2/training.log \
    /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/02_train_pth/production/
```

---

## Step 03 — Export PTH → ONNX (AGX หรือ Mac)

### ส่งสคริปท์ไป AGX ก่อน (ถ้ารันบน AGX)

```bash
rsync -avz \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/export_to_onnx.py \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/fix_instancenorm.py \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/validate_onnx_cpu.py \
  agx@100.100.137.9:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/
```

### 3.1 Export PTH → ONNX

```bash
# บน AGX Xavier
cd ~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/
source ~/.venv/bin/activate   # หรือ path ที่ถูกต้อง

python3 export_to_onnx.py \
  --pth /mnt/pwd-data/runs/lprnet_dual_v2/best_model.pth \
  --output DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v$(date +%Y%m%d).onnx \
  --opset 11

# Expected output:
# Exported: DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.onnx
# ONNX model is valid.
# lpr_logits shape:      (1, 49, 38)
# province_logits shape: (1, 77)
```

> **หมายเหตุ:** `export_to_onnx.py` ใช้ `device='cpu'` เสมอ เพื่อให้ ONNX graph เป็น device-agnostic  
> ห้ามใช้ CUDA สำหรับ ONNX export — จะทำให้ dummy tensor กับ model อยู่คนละ device

### 3.2 Fix InstanceNorm (บังคับ ก่อน HEF compile)

```bash
python3 fix_instancenorm.py \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.onnx

# Output: DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed_instancenorm.onnx
```

ตรวจสอบว่า bypass สำเร็จ:
```bash
python3 -c "
import onnx
m = onnx.load('DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed_instancenorm.onnx')
types = {n.op_type for n in m.graph.node}
assert 'InstanceNormalization' not in types
print('OK — nodes:', len(m.graph.node), ' types:', sorted(types))
"
# Expected: OK — nodes: 49  (ลดจาก 55)
```

### 3.3 Validate บน CPU (Critical Gate)

```bash
# ติดตั้ง dependencies (ครั้งแรก)
pip install onnxruntime pillow

# ทดสอบด้วย synthetic crop ก่อน (ตรวจว่า shapes ถูก)
python3 validate_onnx_cpu.py \
  --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed_instancenorm.onnx \
  --test-synthetic

# ทดสอบด้วย val set จริง (gate จริง)
for f in $(ls /mnt/pwd-data/lpr_dataset/val/ | shuf | head -5); do
  echo "=== $f ==="
  python3 validate_onnx_cpu.py \
    --onnx DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed_instancenorm.onnx \
    --crop /mnt/pwd-data/lpr_dataset/val/$f 2>/dev/null \
    | grep -E "CTC DECODE|Province:|pixel range"
done
```

**ผ่านถ้า:** `CTC DECODE: 'กข1234'` (ตัวอักษรตรงกับชื่อไฟล์)  
**ไม่ผ่านถ้า:** `CTC DECODE: ''` → กลับไป Step 02

### 3.4 ดาวน์โหลด ONNX มา Mac

```bash
scp agx@100.100.137.9:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed_instancenorm.onnx \
    /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/production/
```

---

## Step 04 — Compile ONNX → HEF (GCP)

### 4.1 Upload ONNX + Calib ไป GCP

```bash
# วิธีที่ 1: gcloud compute scp (ง่ายกว่า)
gcloud compute scp \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/production/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed_instancenorm.onnx \
  hailo-compiler:~ \
  --zone=asia-southeast1-a

# วิธีที่ 2: gcloud storage (ผ่าน GCS bucket)
gcloud storage cp \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/03_compile_pth_onnx/production/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed_instancenorm.onnx \
  gs://pwd-hailo-models/

# Upload calib data (ต้องใช้ real plate crops ไม่ใช่ random noise)
gcloud compute scp \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/04_compile_onnx_hef/calib.npy \
  hailo-compiler:~ \
  --zone=asia-southeast1-a
```

### 4.2 SSH เข้า GCP

```bash
gcloud compute ssh hailo-compiler
# Enter passphrase for key '/Users/sqh/.ssh/google_compute_engine':

# ตรวจสอบไฟล์
ls -lh ~/DualBranchLPRNet*.onnx ~/calib.npy
```

### 4.3 Activate Hailo Environment และ Compile

```bash
# บน GCP hailo-compiler VM
cd ~/hailo-compiler
source hailo_env/bin/activate

python3 compile_to_hef_v2.py \
  --onnx ~/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509_fixed_instancenorm.onnx \
  --calib-npy ~/calib.npy \
  --hw-arch hailo8

# Expected output:
# [hailo] Compiling ...
# [hailo] Saved: DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.hef
# HEF size: ~1-4 MB
```

### model_script.alls ที่ต้องมี (สำคัญมาก)

```
model_optimization_config(calibration, batch_size=1, calibset_size=64)
model_optimization_flavor(optimization_level=0, compression_level=0)
normalization([127.5, 127.5, 127.5], [127.5, 127.5, 127.5])
set_output_activation_quant(False)
```

> `set_output_activation_quant(False)` **บังคับ** — ถ้าขาดบรรทัดนี้ Hailo จะ return uint8 แทน float32 → `chars = ''` ทุกกรณี

### 4.4 ดาวน์โหลด HEF มา Mac

```bash
# จาก Mac
gcloud compute scp \
  hailo-compiler:~/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.hef \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/resources/ \
  --zone=asia-southeast1-a

# ตรวจขนาด (ต้อง 1-5 MB)
ls -lh /Users/sqh/Documents/Claude/Projects/AICAMERA/resources/*.hef
```

---

## Step 05 — Deploy & Test (aicamera1/2)

### 5.1 Copy HEF ไป aicamera1

```bash
scp /Users/sqh/Documents/Claude/Projects/AICAMERA/resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.hef \
  camuser@aicamera1.tail605477.ts.net:/home/camuser/aicamera/resources/

# ตรวจสอบ
ssh camuser@aicamera1.tail605477.ts.net "ls -lh /home/camuser/aicamera/resources/*.hef"
```

### 5.2 Update Model JSON

```bash
ssh camuser@aicamera1.tail605477.ts.net
nano /home/camuser/aicamera/resources/dual_branch_lpr_model.json
```

แก้เฉพาะ `"name"`:
```json
{
  "name": "DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509",
  "device_type": "HAILO8",
  "input_shape": [1, 3, 75, 300],
  "output_postprocess_type": "None",
  "input_quant_en": true,
  "output_quant_en": false
}
```

### 5.3 Stop Service และ Test

```bash
ssh camuser@aicamera1.tail605477.ts.net
sudo systemctl stop aicamera.service

cd /home/camuser/aicamera/
source edge/venv_hailo/bin/activate

# Quick smoke test
python3 - <<'EOF'
import sys
sys.path.insert(0, '/home/camuser/aicamera')
from edge.src.components.dual_branch_degirum_ocr import DualBranchDegirumOCR
import cv2

ocr = DualBranchDegirumOCR(
    model_name="DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509",
    zoo_url="/home/camuser/aicamera/resources",
    inference_host_address="@local",
    debug=True,
)
img = cv2.imread('test_output/plate_crop_0.jpg')
result = ocr.read_plate(img)
print(f"chars:    '{result['chars']}'")
print(f"province: '{result['province']}'")
print(f"conf:      {result['conf']:.3f}")
EOF

# Full pipeline test
python3 train_model/05_test_implement/test_dual_branch_lpr.py \
  --image test_output/plate_crop_0.jpg \
  --debug --save-crops
```

### Acceptance Criteria

| Check | ต้องผ่าน |
|-------|---------|
| `chars` | ไม่ว่าง (มีพยัญชนะ + ตัวเลข) |
| `conf` | ≥ 0.6 (ไม่ใช่ NaN) |
| `province` | จังหวัดที่ถูกต้อง |
| `prov_conf` | ≥ 0.4 |

### 5.4 Restart Service

```bash
sudo systemctl start aicamera.service
sudo journalctl -u aicamera.service -f
```

### 5.5 Deploy ไป aicamera2

```bash
# Copy HEF ระหว่าง camera (ไม่ต้องผ่าน Mac)
scp camuser@aicamera1.tail605477.ts.net:/home/camuser/aicamera/resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.hef \
    camuser@aicamera2.tail605477.ts.net:/home/camuser/aicamera/resources/

# Update JSON และ restart บน aicamera2
ssh camuser@aicamera2.tail605477.ts.net
nano /home/camuser/aicamera/resources/dual_branch_lpr_model.json
sudo systemctl restart aicamera.service
```

---

## Step 06 — Git Commit

```bash
# บน aicamera1 หลัง test ผ่าน
ssh camuser@aicamera1.tail605477.ts.net
cd /home/camuser/aicamera
git add resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.hef \
        resources/DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_v20260509.json
git commit -m "feat: deploy DualBranchLPRNet v20260509 — retrained 77 provinces"
git push origin feature/dualbranch-lpr-ocr

# บน Mac — push scripts ที่แก้ไข
cd /Users/sqh/Documents/Claude/Projects/AICAMERA
git add train_model/03_compile_pth_onnx/
git commit -m "feat(train): update ONNX export and InstanceNorm fix scripts"
git push origin feature/dualbranch-lpr-ocr
```

---

## Known Errors & Fixes (2026-05-09)

| Error | สาเหตุ | วิธีแก้ |
|-------|--------|---------|
| `Expected all tensors to be on the same device` (export_to_onnx.py) | dummy tensor อยู่ CPU แต่ model อยู่ CUDA | ใช้ `device='cpu'` สำหรับ ONNX export เสมอ |
| `ImportError: libGL.so.1` (validate_onnx_cpu.py) | `opencv-python` ต้องการ display บน headless server | เปลี่ยนใช้ `pillow` (PIL) แทน cv2 |
| `TypeError: 'NoneType' object is not subscriptable` (Hailo DFC) | `ReduceMean` nodes จาก fix_instancenorm v3 — Hailo ไม่รู้ input format | ใช้ bypass approach (v4) แทน decomposition — ลบ subgraph ทิ้ง ไม่ใช้ ReduceMean |
| `DG_FLT does not match Hailo input type DG_UINT8` | `InputQuantEn=false` ใน degirum JSON | ตั้ง `InputQuantEn: true` และ preprocess ส่ง uint8 |
| `chars = ''` บน aicamera | `set_output_activation_quant` ขาด | Recompile HEF พร้อมบรรทัดนั้น |
| Province accuracy ≈ 1/77 (near-uniform) | Province imbalance ในข้อมูล | เพิ่มข้อมูลให้ครบทุกจังหวัด, ตรวจ `--prov_weight` |
| pixel range `[-1.0, -0.608]` (validation) | ภาพมืดมาก (calib set มีภาพกลางคืน) | ใช้ val set ทดสอบ ไม่ใช้ calib set |

---

## Model Architecture Reference

| Parameter | Value |
|-----------|-------|
| Backbone | ResNet18 (truncated at layer2) |
| Input | `(B, 3, 75, 300)` float32, normalized `[-1, 1]` |
| HEF input | `uint8 [0,255]` — normalization baked in via model_script |
| Branch 1 (CTC) | `(B, 49, 38)` = `(B, C, T)` ใน ONNX |
| Branch 2 (Province) | `(B, 77)` |
| BLANK index | `48` (index สุดท้าย ไม่ใช่ index 0) |
| Charset | 48 chars: digits `0-9` (idx 0–9) + พยัญชนะไทย (idx 10–47) |
| Hailo output shape | `(B, 38, 49)` หลัง hardware reorder (T-first) |

### ONNX Output Shape และการ Decode

```python
# ONNX output: (1, 49, 38) = (B, C, T)
# Hailo output: (1, 38, 49) = (B, T, C)  ← Hailo reorder อัตโนมัติ

# CTC decode จาก ONNX (ต้อง transpose):
lpr_logits = outs[0]           # (1, 49, 38)
lpr_tc = lpr_logits[0].T      # (38, 49) = (T, C)
best = np.argmax(lpr_tc, axis=-1)   # (38,)

# CTC decode จาก Hailo (ไม่ต้อง transpose):
lpr_logits = hailo_out         # (1, 38, 49) = (B, T, C)
best = np.argmax(lpr_logits[0], axis=-1)  # (38,)
```

---

## File Naming Reference

| ประเภทไฟล์ | Format | ตัวอย่าง |
|-----------|--------|---------|
| Dataset images | `{consonants}_{digits}{province}_{id:06d}.jpg` | `กข_1234กรุงเทพมหานคร_000001.jpg` |
| PTH checkpoint | `DualBranchLPRNet_ThaiLP_3x75x300_CTC48-Prov77_vYYYYMMDD.pth` | `...v20260509.pth` |
| ONNX (raw) | `...vYYYYMMDD.onnx` | `...v20260509.onnx` |
| ONNX (fixed) | `...vYYYYMMDD_fixed_instancenorm.onnx` | `...v20260509_fixed_instancenorm.onnx` |
| HEF | `...vYYYYMMDD.hef` | `...v20260509.hef` |

> **สำคัญ:** Province ใช้ชื่อเต็ม `กรุงเทพมหานคร` เสมอ ห้ามใช้ `กรุงเทพ`

---

## Key Scripts Quick Reference

| Script | Host | คำสั่ง |
|--------|------|--------|
| `01_dataset/synthetic_lpr_script.py` | Mac | `python3 synthetic_lpr_script.py --count 5000 --province-balance` |
| `02_train_pth/train_dual_branch.py` | AGX | `python3 train_dual_branch.py --train_dir ... --max_epochs 150` |
| `03_compile_pth_onnx/export_to_onnx.py` | AGX | `python3 export_to_onnx.py --pth best_model.pth --output ...$(date +%Y%m%d).onnx` |
| `03_compile_pth_onnx/fix_instancenorm.py` | AGX | `python3 fix_instancenorm.py --onnx model.onnx` |
| `03_compile_pth_onnx/validate_onnx_cpu.py` | AGX | `python3 validate_onnx_cpu.py --onnx model_fixed.onnx --crop plate.jpg` |
| `04_compile_onnx_hef/compile_to_hef_v2.py` | GCP | `python3 compile_to_hef_v2.py --onnx model_fixed.onnx --calib-npy calib.npy --hw-arch hailo8` |
| `05_test_implement/test_dual_branch_lpr.py` | aicamera | `python3 test_dual_branch_lpr.py --image plate.jpg --debug` |
