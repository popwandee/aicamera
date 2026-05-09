# SYNTHETIC_THAI_PLATE — บันทึกการพัฒนา Dataset Generator

**วันที่:** 2026-05-09  
**ผู้รับผิดชอบ:** Ken / PWD Vision Works  
**ไฟล์หลัก:** `train_model/01_dataset/synthetic_thai_plate.py`

---

## 1. ที่มาและเป้าหมาย

### บริบท
โปรเจกต์ DualBranchLPRNet ต้องการ dataset ภาพป้ายทะเบียนไทย synthetic จำนวนมาก
(เป้าหมาย ≥ 15,000 ภาพ = 5,000 ป้ายพื้นฐาน × augmentation factor 3)
เพื่อ train โมเดลที่รับรู้ได้ทั้ง:
- **CTC branch:** ตัวอักษร + ตัวเลข (48 chars + 1 BLANK)
- **Province branch:** ชื่อจังหวัด 77 จังหวัด

### ปัญหาของ script เดิม (v1)
| ปัญหา | ผลกระทบ |
|-------|---------|
| ใช้ฟอนต์ Sarabun-Bold | ตัวอักษรไม่เหมือนป้ายจริง |
| อิงกับ template PNG | ต้องมี template ไฟล์ ไม่ยืดหยุ่น |
| ไม่แสดงชื่อจังหวัดบนป้าย | โมเดลขาด context จังหวัด |
| render 1 บรรทัด | ไม่ตรงกับโครงสร้างป้ายจริง |
| รองรับแค่ 8 จังหวัด | prov_acc ต่ำ เพราะ imbalance |

---

## 2. การศึกษาป้ายทะเบียนจริง

### ภาพอ้างอิงที่ใช้
- `train_model/01_dataset/lp_crops/1กย_889กรุงเทพมหานคร_000108.jpg`
- `train_model/01_dataset/lp_crops/4ขฮ_9751กรุงเทพมหานคร_000110.jpg`

### สรุปโครงสร้างป้ายจริง
```
┌────────────────────────────────────────────────┐  ← ขอบดำ 3 px
│                                                │
│      1กย              889                      │  ← ตัวใหญ่มาก ~68% ความสูง
│                                                │
│  ──────────────────────────────────────────   │  ← เส้นแบ่ง (บางบริษัทใช้คลื่น)
│           กรุงเทพมหานคร                        │  ← ชื่อจังหวัด ~20% ความสูง
│                                                │
└────────────────────────────────────────────────┘

สัดส่วน zone แนวนอน:
  [prefix+consonants]  [gap ~18%]  [digits]
  ←      40%        →             ←  42% →
```

### ข้อสังเกตสำคัญจากป้ายจริง
1. **ตัวอักษรใหญ่มาก** — ครอบคลุมเกือบ 70% ของความสูงส่วนบน
2. **พื้นขาวสะอาด** — ไม่มี texture พิเศษ (โลหะสะท้อนแสง simulate ด้วย augmentation)
3. **ฟอนต์ ThangLuang** — ตัวกลม หนา เลข "0" ไม่มีขีดกลาง ตรงกับ DLT standard
4. **gap กลางชัดเจน** — ระหว่างหมวดอักษรและตัวเลข (ป้ายจริง ~18-22% ของความกว้าง)
5. **ชื่อจังหวัดเต็ม** — `กรุงเทพมหานคร` ไม่ใช่ `กรุงเทพ`

---

## 3. การปรับปรุง synthetic_thai_plate.py v4

### ฟอนต์ — ThangLuang (การเปลี่ยนแปลงหลัก)

| ลำดับ | Font | เหตุผล |
|-------|------|--------|
| 1 | `Sarun's ThangLuang.ttf` | จำลองฟอนต์ DLT จริง — แนะนำ |
| 2 | `Sarabun-Bold.ttf` | Thai general-purpose fallback |
| 3 | `Ayuthaya.ttf` | macOS built-in last-resort |

**ที่อยู่ font บน Mac:**
```
/Users/sqh/Library/Fonts/Sarun's ThangLuang.ttf
/Users/sqh/Downloads/Sarun's ThangLuang.ttf
```

### Layout Constants (300×100 px)
```python
BORDER   = 3    # ขอบรอบป้าย
TOP_PAD  = 4    # ช่องว่างบน
MAIN_H   = 68   # zone ตัวหลัก (เพิ่มจาก 52 → 68 = +31%)
DIV_H    = 2    # เส้นแบ่งบาง (ไม่ใช่คลื่น)
PROV_H   = 18   # zone ชื่อจังหวัด
BOT_PAD  = 2
# รวม: 3+4+68+2+18+2+3 = 100 px ✓

SIDE_PAD    = 5
LEFT_RATIO  = 0.40   # zone prefix+consonants
GAP_RATIO   = 0.18   # ช่องว่างกลาง
RIGHT_RATIO = 0.42   # zone digits
```

### Province List
ใช้ชื่อเต็ม ตรงกับ `train_model/02_train_pth/province_map.py` ครบ 77 จังหวัด:
```python
'กรุงเทพมหานคร'  # index 1 (ชื่อเต็ม — ตรงกับ lp_crops จริง)
'เชียงใหม่'      # index 13
# ... ครบ 77 จังหวัด
```

> **หมายเหตุ:** `scripts/province_map.py` ใช้ชื่อสั้น `'กรุงเทพ'` (สำหรับ edge OCR)
> แต่ `02_train_pth/province_map.py` และ filename จริงใน lp_crops ใช้ `'กรุงเทพมหานคร'`

### Plate Formats (7 รูปแบบ)
```python
(1, 2, 3)  # 1กย 889   — 30%  (Bangkok most common)
(1, 2, 4)  # 1กก 5367  — 25%
(0, 2, 4)  # กข 1234   — 20%
(0, 2, 3)  # กข 123    — 10%
(0, 1, 4)  # ก 1234    —  8%
(1, 1, 4)  # 1ก 5678   —  4%
(2, 0, 4)  # 15 7410   —  3%  government
```

### Plate Types
```python
'white':  ((255,255,255), (10,10,10),  ...)   # 65% รถส่วนบุคคล
'yellow': ((255,204,  0), (10,10,10),  ...)   # 20% รถบรรทุก
'green':  ((0, 105,  55), (245,245,245), ...) # 10% ราชการ
'red':    ((185, 25,  20), (245,245,245), ...) # 5% ป้ายแดง
```

### Augmentations
| Augmentation | Probability | Parameters |
|-------------|-------------|------------|
| Brightness | 70% | ×0.65–1.40 (night: ×0.35–0.75) |
| Contrast | 55% | ×0.60–1.55 |
| Gaussian Blur | 35% | radius 0.2–1.2 |
| Perspective Warp | 25% | skew 1–4% |
| Gaussian Noise | 40% | σ = 3–18 |
| Night mode | 15% | + headlight glare |
| JPEG compression | 40% | quality 40–90 |
| Sharpness | 25% | ×0.4–2.0 |

### Filename Format
```
{prefix+consonants}_{digits+province}_{id:06d}.jpg

ตัวอย่าง:
  1กย_889กรุงเทพมหานคร_000001.jpg  →  plate_text = '1กย889กรุงเทพมหานคร'
  กข_1234เชียงใหม่_000002.jpg      →  plate_text = 'กข1234เชียงใหม่'
  15_7410นครราชสีมา_000003.jpg     →  plate_text = '157410นครราชสีมา'
```

---

## 4. ผลลัพธ์ที่ได้ (ทดสอบ 2026-05-09)

### ตัวอย่างภาพที่สร้างได้

| ป้าย | ประเภท | หมายเหตุ |
|-----|--------|---------|
| `1กย 889 กรุงเทพมหานคร` | white | ตรงกับ lp_crops จริง |
| `4ขฮ 9751 กรุงเทพมหานคร` | white | ตรงกับ lp_crops จริง |
| `กข 1234 เชียงใหม่` | white | รูปแบบ classic 2+4 |
| `15 7410 นครราชสีมา` | yellow | ราชการ/รถบรรทุก |
| `กง 9964 นครนายก` | green | ป้ายเขียว |

### ความเร็ว
- ~150 img/s บน MacBook (M-chip) รวม augmentation
- 5,000 ป้าย × 3 aug = 15,000 ภาพ ≈ 100 วินาที

---

## 5. วิธีใช้งาน

```bash
cd train_model/01_dataset

# สร้าง dataset พื้นฐาน
python3 synthetic_thai_plate.py --count 5000 --augment-factor 3

# บังคับให้ครบทุก 77 จังหวัดเท่าๆ กัน (แนะนำสำหรับ prov_acc)
python3 synthetic_thai_plate.py --count 5000 --province-balance

# ระบุ font เอง
python3 synthetic_thai_plate.py \
    --font "/Users/sqh/Library/Fonts/Sarun's ThangLuang.ttf" \
    --count 5000

# ต่อจาก run ก่อน (ป้องกัน overwrite)
python3 synthetic_thai_plate.py --count 2000 --start-id 15001

# output ไปยัง folder อื่น
python3 synthetic_thai_plate.py --count 5000 --output-dir ./dataset_thai/train
```

---

## 6. แผนการดำเนินการต่อไป

### 6.1 ปรับปรุงรูปแบบป้ายให้สมจริงมากขึ้น

#### ระยะสั้น (ทำได้ทันที)

**[A] เพิ่ม DLT registration stamp**
ป้ายจริงมีวงกลม/สัญลักษณ์กรมขนส่งมุมล่างขวา:
```python
def _draw_dlt_stamp(draw, img_w, img_h, color):
    # วงกลมขนาดเล็ก ~14px มุมล่างขวา
    x0 = img_w - BORDER - SIDE_PAD - 14
    y0 = img_h - BORDER - 3 - 14
    draw.ellipse([x0, y0, x0+14, y0+14], outline=color, width=1)
    draw.text((x0+3, y0+2), 'กข', font=tiny_font, fill=color)
```

**[B] เส้นขอบคู่ (double border)**
ป้ายหลายรุ่นมีเส้นขอบบาง 1px ด้านใน:
```python
draw.rectangle([BORDER+1, BORDER+1, W-BORDER-2, H-BORDER-2],
               outline=border_rgb, width=1)
```

**[C] ปรับ province font size ให้ใหญ่ขึ้น**
ชื่อจังหวัดสั้น (เลย, ตาก) ควรใหญ่กว่าจังหวัดชื่อยาว (พระนครศรีอยุธยา) 
— ปัจจุบัน `_fit_font()` ทำให้อัตโนมัติ แต่ควร set minimum size

**[D] สุ่ม kerning/spacing เล็กน้อย**
ช่องว่างระหว่าง prefix-digit กับ consonant บนป้ายจริงไม่เท่ากัน:
```python
gap_ratio = random.uniform(0.15, 0.22)  # สุ่ม 15-22%
```

#### ระยะกลาง

**[E] Emboss / 3D effect**
ป้ายทะเบียนจริงตัวอักษรนูน (raised) — จำลองด้วย shadow offset:
```python
def draw_emboss(draw, pos, text, font, fill, plate_type):
    # shadow สีอ่อนกว่า offset 1-2px
    shadow = lighten(fill, 0.6) if dark_bg else darken(bg, 0.15)
    draw.text((x+1, y+1), text, font=font, fill=shadow)
    draw.text((x, y),   text, font=font, fill=fill)
```

**[F] Background gradient / metallic sheen**
พื้นป้ายจริงมีความเงาเล็กน้อยบริเวณกลาง:
```python
# gradient แนวตั้งอ่อนๆ — bright center, slightly darker edges
gradient = np.linspace(255, 240, OUT_H).reshape(-1, 1)
```

**[G] เพิ่มป้ายประเภทพิเศษ**
| ประเภท | พื้น | ตัวอักษร | สัดส่วน |
|--------|-----|---------|--------|
| ป้ายกรมศุลกากร | ขาว | น้ำเงิน | ~1% |
| ป้ายทูต | น้ำเงิน | ขาว | ~0.5% |
| ป้ายชั่วคราว | ขาว | แดง | ~1% |

#### ระยะยาว

**[H] Render จากภาพป้ายจริง + GAN refinement**
ใช้ภาพ lp_crops จริงเป็น texture base แทน solid color
เพื่อให้ CNN ได้เห็น imperfections จริง

**[I] Multi-scale rendering**
สร้างในหลาย resolution แล้ว resize ลง 300×75
เพื่อจำลองการถ่ายจากระยะต่างๆ:
```python
RENDER_SCALES = [1.0, 1.5, 2.0, 3.0]
scale = random.choice(RENDER_SCALES)
img = render_at_scale(scale).resize((300, 75), LANCZOS)
```

**[J] Dirty/aged plate simulation**
ป้ายเก่า มีรอยสกปรก รอยขีดข่วน:
```python
def add_dirt(img, intensity=0.3):
    # random polygon blotches + scratch lines
    ...
```

### 6.2 เพิ่มปริมาณ dataset

**เป้าหมายสำหรับ training รอบต่อไป:**
```
ป้าย synthetic  : 50,000 พื้นฐาน × 3 aug = 150,000 ภาพ
ป้าย real crop  : ~500 จาก lp_crops (ปัจจุบัน) → เป้า 2,000
อัตราส่วน       : synthetic 95% + real 5%
province balance: ใช้ --province-balance เพื่อให้ทุกจังหวัดมีอย่างน้อย 300 ภาพ
```

### 6.3 Pipeline validation ก่อน train

```bash
# 1. สร้าง dataset
python3 synthetic_thai_plate.py --count 5000 --province-balance \
    --output-dir ../../02_train_pth/dataset_thai/train

# 2. ตรวจสอบ filename format
python3 verify.py --dir ../../02_train_pth/dataset_thai/train

# 3. split train/val (80/20)
python3 split_dataset.py --src ../../02_train_pth/dataset_thai/train

# 4. เริ่ม train บน AGX Xavier
ssh sqh@100.100.137.9
cd ~/hailo_model_zoo/hailo_models/license_plate_recognition/train_lpr/
python3 train_dual_branch.py --epochs 100 --lr 1e-3
```

---

## 7. ข้อจำกัดและข้อควรระวัง

### ข้อจำกัดปัจจุบัน
1. **Font dependency** — ต้องติดตั้ง ThangLuang บนทุก host ที่ run script
   - Mac: ✅ มีอยู่แล้วที่ `~/Library/Fonts/`
   - AGX Xavier: ต้อง copy ไปวางก่อน run
   - GCP: ต้อง install ใน Docker image

2. **Province imbalance** — default sampling เน้นกรุงเทพ/ปริมณฑล
   ใช้ `--province-balance` เสมอถ้าต้องการ `prov_acc` สูง

3. **ไม่มีป้าย 2 แถว (จังหวัด + เลขซีเรียล)** — ป้ายรูปแบบนี้ยังไม่รองรับ

### Frozen constants (ห้ามเปลี่ยน — GUARDRAIL.md)
```python
LPR_NUM_CLASSES = 49      # 48 chars + 1 BLANK
LPR_BLANK       = 48      # BLANK อยู่ที่ index สุดท้าย
N_PROVINCES     = 77
INPUT_H, INPUT_W = 75, 300
```

---

## 8. Files ที่เกี่ยวข้อง

| File | บทบาท |
|------|-------|
| `train_model/01_dataset/synthetic_thai_plate.py` | **Script หลักที่พัฒนาในวันนี้** |
| `train_model/01_dataset/synthetic_lpr_script.py` | Script v3 (ทางเลือก — มีฟีเจอร์ CLI ครบกว่า) |
| `train_model/02_train_pth/province_map.py` | Province list (77 จังหวัด ชื่อเต็ม) — truth |
| `train_model/01_dataset/lp_crops/` | ภาพป้ายจริงสำหรับ reference และ calibration |
| `train_model/GUARDRAIL.md` | Constraints ที่ห้ามแก้ |
| `train_model/CLAUDE.md` | คำอธิบาย pipeline ทั้งหมด |

---

*บันทึกโดย Claude Code (claude-sonnet-4-6) — 2026-05-09*
