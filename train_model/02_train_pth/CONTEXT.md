# CONTEXT — Step 02: Train Model on AGX Xavier

**Host:** agx-tail — Jetson AGX Xavier (Tailscale: `100.100.137.9`)  
**SSH:** `ssh agx@agx-tail`  (or `ssh agx@100.100.137.9`)  
**Goal:** Train `DualBranchLPRNet` from the prepared dataset and produce `best_model.pth`.

---

## Environment Setup (First Time Only)

```bash
ssh agx@agx-tail

# Check if venv exists
ls ~/hailo_model_zoo/hailo_models/license_plate_recognition/.venv/ 2>/dev/null || echo "need to create venv"

# Create if missing
#python3 -m venv .venv
#source .venv/bin/activate

# Install dependencies (PyTorch for Jetson — use JetPack-compatible wheel)
# pip install torch torchvision tqdm pillow --upgrade
# ถ้าไม่จำเป็นไม่ต้องแก้ไข เพราะต้องลงเวอร์ชั่นที่ใช้ได้กับ AGX Xavier

# Verify GPU
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Expected: True  NVIDIA Jetson AGX Xavier
# Actual result is :
#True Xavier
```

---

## Transfer Dataset from Mac

```bash
# On Mac — rsync dataset to AGX Xavier
rsync -avz --progress \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/01_dataset/dataset_thai/ \
  agx@100.100.137.9:/mnt/pwd-data/lpr_dataset/

# Transfer training scripts (02_train_pth folder)
rsync -avz \
  /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/02_train_pth/ \
  agx@100.100.137.9:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/

# Verify
ssh agx@agx-tail "ls /mnt/pwd-data/lpr_dataset/ | wc -l"
```

---

## Training Command

```bash
tmux ls
tmux attach -t train
ssh sqh@agx-tail
source ~/hailo_model_zoo/hailo_models/license_plate_recognition/.venv/bin/activate
cd ~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/

python3 train_dual_branch.py \
  --train_dir /mnt/pwd-data/lpr_dataset/train \
  --test_dir  /mnt/pwd-data/lpr_dataset/test   \
  --max_epochs 150          \
  --train_batch_size 32     \
  --test_batch_size  32     \
  --learning_rate 5e-4      \
  --weight_decay  1e-4      \
  --dropout_rate  0.3       \
  --prov_weight   0.3       \
  --output_dir /mnt/pwd-data/runs/lprnet_dual_v2 \
  --device cuda             \
  --num_workers 4           \
  --es_patience 15
```

Run inside `tmux` or `screen` so SSH disconnect does not kill training:
```bash
tmux new -s train
# ... run above command ...
# Detach: Ctrl-B then D
# Re-attach: tmux attach -t train

(.venv) agx@ubuntu:~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr$ python3 train_dual_branch.py   --train_dir /mnt/pwd-data/lpr_dataset/train   --test_dir  /mnt/pwd-data/lpr_dataset/test     --max_epochs 150            --train_batch_size 32       --test_batch_size  32       --learning_rate 5e-4        --weight_decay  1e-4        --dropout_rate  0.3        
 --prov_weight   0.3         --output_dir /mnt/pwd-data/runs/lprnet_dual_v2   --device cuda               --num_workers 4             --es_patience 15

```

Device: cuda  |  AMP: enabled

Loading datasets…
  ✓ 111,456 images  [train+aug]  ←  /mnt/pwd-data/lpr_dataset/train
  ✓ 13,137 images  [val]  ←  /mnt/pwd-data/lpr_dataset/test

Initialising model…
Parameters: 933,310

Starting training…

---

## Monitoring Training

```bash
# Tail the log on AGX Xavier
tail -f /mnt/pwd-data/runs/lprnet_dual_v2/training.log

# Or watch accuracy every 5 epochs
grep "Val Loss" /mnt/pwd-data/runs/lprnet_dual_v2/training.log | tail -20
```

Expected progression (healthy training):
```
Epoch   5 | Val Loss: 3.21 | Plate Acc:  8.2% | Char Acc: 41.2% | Prov Acc: 23.1%
Epoch  20 | Val Loss: 1.84 | Plate Acc: 42.5% | Char Acc: 71.4% | Prov Acc: 67.3%
Epoch  50 | Val Loss: 0.92 | Plate Acc: 74.1% | Char Acc: 88.2% | Prov Acc: 85.0%
Epoch  90 | Val Loss: 0.61 | Plate Acc: 88.3% | Char Acc: 93.7% | Prov Acc: 91.4%
```

---

## Accuracy Gates (Must Pass Before ONNX Export)

| Metric | Gate | Action if not met |
|--------|------|-------------------|
| `Plate Acc` | ≥ 85% | More data or more epochs |
| `Char Acc` | ≥ 92% | Check augmentation — may be too aggressive |
| `Prov Acc` | ≥ 90% | Check province distribution — imbalance? |

---

## Common Training Problems

### NaN / Inf Loss
```
⚠  NaN/inf loss at batch 12
```
**Cause:** LR too high, or bad data (wrong filename → missing province).  
**Fix:** Reduce `--learning_rate` to `1e-4`, check dataset with `verify_dataset.py`.

### Province Accuracy Stuck at ~1.3%
**Cause:** Province class imbalance — only a few provinces covered.  
**Fix:** Regenerate with `--province-balance` flag in `synthetic_lpr_script.py`.

### Plate Acc Plateaus at <70%
**Cause:** Training data quality issue.  
**Fix:** Check that augmentations aren't too extreme (blurred chars unreadable at 75px).

### CUDA Out of Memory
**Fix:** Reduce `--train_batch_size` to `16` or `8`.

---

## Retrieving the Best Checkpoint

```bash
# On Mac — download the best model
scp agx@100.100.137.9:/mnt/pwd-data/runs/lprnet_dual_v2/best_model.pth \
    /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/02_train_pth/production/

# Also download training stats
scp agx@100.100.137.9:/mnt/pwd-data/runs/lprnet_dual_v2/training_stats.json \
    /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/02_train_pth/production/

# Also download training logs for report
scp agx@100.100.137.9:/mnt/pwd-data/runs/lprnet_dual_v2/training.log \
    /Users/sqh/Documents/Claude/Projects/AICAMERA/train_model/02_train_pth/production/
```

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `train_dual_branch.py` | Main training script — do not modify architecture |
| `lprnet_dual_branch.py` | Model definition (ResNet18 backbone + CTC + Province) |
| `charset.py` | LPR character set — 48 chars + BLANK=48 |
| `province_map.py` | Province list — 77 entries |

---

## Key Architecture Parameters (DO NOT CHANGE)

```python
# lprnet_dual_branch.py
INPUT_H, INPUT_W   = 75, 300      # model input size
LPR_NUM_CLASSES    = 49           # 48 chars + BLANK
LPR_BLANK          = 48           # blank is LAST index
N_PROVINCES        = 77

# ONNX output (after export):
# lpr_logits:       (B, 49, 38)  = (B, C, T)
# province_logits:  (B, 77)
```

---

## Next Step

After `best_model.pth` is downloaded → proceed to `../03_compile_pth_onnx/CONTEXT.md`.

