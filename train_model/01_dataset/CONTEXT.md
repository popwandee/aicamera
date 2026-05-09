# CONTEXT — Step 01: Dataset Preparation

**Host:** Mac (local)  
**Goal:** Produce a clean, diverse, correctly-named LP crop dataset ready for training on AGX Xavier.

---

## Current Dataset Status

| Source | Path | Count | Problem |
|--------|------|-------|---------|
| Existing synthetic | `dataset_thai/train/` | 100,010 | Only 8/77 provinces covered |
| Existing synthetic val | `dataset_thai/test/` | 10,010 | Same province imbalance |
| Real LP crops | `lp_crops/` | 194 | Bangkok-dominated, too few |
| Raw aicamera2 frames | `aicamera2_images/` | 32 | Unlabeled — need crop_lp.py |
| Raw aicamera1 frames | `aicamera1_images/` | varies | Unlabeled |

**Root cause of model failure:** Training imbalance → model learned BLANK as safe default.

---

## Strategy: Synthetic-First (No Time for Real Collection)

Generate synthetic plates with `synthetic_lpr_script.py`:

```bash
# Recommended: 5,000 base plates × 3 augmentation copies = 15,000 images
python3 synthetic_lpr_script.py \
  --output-dir ./synthetic_new/ \
  --count 5000 \
  --augment-factor 3 \
  --night-ratio 0.25 \
  --seed 42

# If Thai font not found automatically, specify it:
# macOS built-in:  --font /Library/Fonts/Ayuthaya.ttf
# Ubuntu/Jetson:   --font /usr/share/fonts/truetype/tlwg/Loma.ttf
```

Then combine with existing synthetic data and real crops:

```bash
# Merge all into one training pool
mkdir -p dataset_merged/all
cp dataset_thai/train/*.jpg dataset_merged/all/
cp synthetic_new/*.jpg       dataset_merged/all/
cp lp_crops/*.jpg            dataset_merged/all/

# Check count
ls lp_crops/ | wc -l
ls synthetic_new/ | wc -l
ls test_gen2/ | wc -l

# Split 80/20 (use provided split script or manually)
python3 split_dataset.py --src lp_crops \
                         --train dataset_thai/train \
                         --test   dataset_thai/test \
                         --calib   dataset_thai/calib \
                         --ratio 0.75 0.20 0.05 --seed 42

python3 split_dataset.py --src synthetic_new \
                         --train dataset_thai/train \ 
                         --test   dataset_thai/test \ 
                         --calib   dataset_thai/calib \ 
                         --ratio 0.75 0.20 0.05 --seed 42

python3 split_dataset.py --src test_gen2 \
                         --train dataset_thai/train \ 
                         --test   dataset_thai/test \ 
                         --calib   dataset_thai/calib \ 
                         --ratio 0.75 0.20 0.05 --seed 42
```

---

## Filename Format (CRITICAL — Do Not Change)

```
{consonants}_{digits}{province}_{id:06d}.jpg
```

| Part | Example | Meaning |
|------|---------|---------|
| `consonants` | `กข` | 1–2 Thai consonants from LPR_CHARS |
| `digits` | `1234` | 3–4 digits |
| `province` | `เชียงใหม่` | Short form — must match `province_map.py` exactly |
| `id` | `000001` | Exactly 6 digits, unique across entire dataset |

Examples:
```
กข_1234เชียงใหม่_000001.jpg   →  plate_text = 'กข1234เชียงใหม่'
ก_567ชลบุรี_000002.jpg        →  plate_text = 'ก567ชลบุรี'
```

**Province name format (must match `province_map.py` exactly):**
| Filename form | Note |
|--------------|------|
| `กรุงเทพมหานคร` | Full form — do NOT use `กรุงเทพ` (short) |
| `นครราชสีมา` | |
| `เชียงใหม่` | |

See full list in `../02_train_pth/province_map.py`.

---

## Coverage Targets

| Category | Target count | Reason |
|----------|-------------|--------|
| All 77 provinces | ≥ 100 plates each | Province classifier needs all classes |
| White plates | 65% of total | Standard private vehicle |
| Yellow plates | 20% of total | Commercial / truck |
| Green plates | 10% of total | Government |
| Red plates | 5% of total | Dealer plates |
| Night / dark conditions | 25% of total | Critical for aicamera low-light |
| Perspective distorted | 35% of total | Camera angle variation |
| Blurred | 40% of total | Motion blur at highway speed |

---

## Generating a Calibration NPY for HEF Compile

After generating synthetic data, also produce a `calib.npy` for step 04:

```bash
python3 make_calib_npy.py \
  --src dataset_thai/train \
  --count 1024 \
  --output ../04_compile_onnx_hef/calib.npy
```

Or inline:
```python
import numpy as np, cv2, random
from pathlib import Path

imgs_paths = list(Path('dataset_thai/train').glob('*.jpg'))
random.shuffle(imgs_paths)
imgs = []
for p in imgs_paths[:1024]:
    img = cv2.resize(cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2RGB), (300, 75))
    imgs.append(img.astype(np.float32) / 255.0)

calib = np.stack(imgs).transpose(0, 3, 1, 2)  # (N, 3, 75, 300)
np.save('../04_compile_onnx_hef/calib.npy', calib)
print(f"Saved calib.npy: {calib.shape}")  # (1024, 3, 75, 300)
```

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `synthetic_lpr_script.py` | Main synthetic generator — **run this first** |
| `crop_lp.py` | Interactive tool for cropping real photos (OpenCV UI) |
| `crop_plate_for_test.py` | Quick batch crop without labels (for test frames) |
| `lp_crops/` | 194 real crops (existing, Bangkok-heavy) |
| `dataset_thai/` | 100k existing synthetic (8 provinces only) |
| `aicamera1_images/` | Raw frames from aicamera1 |
| `aicamera2_images/` | Raw frames from aicamera2 |

---

## Quick Verification

After generating, verify your dataset is healthy:

```python
from pathlib import Path
from collections import Counter
import re

src = Path('dataset_merged/train')
provinces = []
for f in src.glob('*.jpg'):
    parts = f.stem.split('_')
    if len(parts) >= 3 and len(parts[-1]) == 6 and parts[-1].isdigit():
        plate_text = ''.join(parts[:-1])
        # extract province: everything after last digit
        m = re.search(r'[^\d]+$', plate_text)
        if m:
            provinces.append(m.group())

c = Counter(provinces)
print(f"Total images: {len(list(src.glob('*.jpg')))}")
print(f"Provinces covered: {len(c)}/77")
print(f"Min per province: {min(c.values())}")
print(f"Max per province: {max(c.values())}")
```

**Accept criteria:** ≥ 77 provinces covered, min ≥ 50 images per province.

---

## Next Step

Once dataset is ready → rsync to agx-tail:

```bash
rsync -avz --progress dataset_thai/ agx@100.100.137.9:/mnt/pwd-data/lpr_dataset/
```

Then proceed to `../02_train_pth/CONTEXT.md`.
