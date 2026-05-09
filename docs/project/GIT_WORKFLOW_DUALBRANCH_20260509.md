# Git Workflow: DualBranch LPR — Park & Restore to Stable

**Date:** 2026-05-09  
**Branch:** `main` → `feature/dualbranch-lpr-ocr`  
**Stable tag:** `stable-before-dualbranch-lpr` → `v2.2.1`  
**Devices:** Mac (dev), aicamera1 ✅, aicamera2 ❌ (offline during session)

---

## บริบท (Context)

โปรเจกต์อยู่ระหว่างพัฒนา DualBranchLPRNet บน branch `main` แต่เนื่องจากเวลาจำกัด
จึงจำเป็นต้อง:

1. บันทึกงาน DualBranch ทั้งหมดไปยัง `feature/dualbranch-lpr-ocr`
2. Revert `main` กลับสู่ stable pipeline (Hailo YOLOv8 OCR + Tesseract)
3. Sync กล้องทั้งหมดให้อยู่ที่ stable version เดียวกัน

**Stable point:** commit `858dd71` — ก่อนที่จะเริ่มงาน DualBranch

---

## สถานะ Branch & Tag ก่อนดำเนินการ

```
main (local+remote)  →  820df13  "Add DualBranchLPRNet..."
                         ↑
                     858dd71  "fix(enhancement): silence LensShadingMapMode..."  ← stable point
feature/dualbranch-lpr-ocr  →  6695f8d  "feat: integrate DualBranchLPRNet..."
```

**Staged/Unstaged changes บน main (uncommitted):**
- `edge/src/components/dual_branch_degirum_ocr.py` (modified)
- `edge/src/components/parallel_ocr_processor.py` (modified)
- `scripts/debug_lpr_logits.py` (untracked)
- `train_model/` directory (untracked — dataset, training scripts, compiled models)

---

## ขั้นตอนที่ 1 — บันทึกงาน DualBranch ไปยัง Feature Branch

### 1.1 Stage ไฟล์ทั้งหมด

```bash
# บน Mac ใน project root
git add -u                          # staged modifications + deletions
git add scripts/debug_lpr_logits.py
git add train_model/
```

> **หมายเหตุ:** ต้องแน่ใจว่า exclude ไฟล์ขนาดใหญ่ก่อน commit:
> - `train_model/04_compile_onnx_hef/calib.npy` (264 MB) — เกิน GitHub 100 MB limit
> - `train_model/04_compile_onnx_hef/hailo-compiler/hailo_dataflow_compiler-*.whl` (488 MB)
> - `train_model/04_compile_onnx_hef/hailo-compiler/hailo_env/` (virtual environment)

สร้าง `.gitignore` สำหรับไดเรกทอรีนั้น:

```bash
# train_model/04_compile_onnx_hef/.gitignore
*.npy

# train_model/04_compile_onnx_hef/hailo-compiler/.gitignore
hailo_env/
*.whl
```

### 1.2 Commit บน main เพื่อเก็บงาน

```bash
git commit -m "feat(wip): save DualBranch LPR work before reverting main to stable"
```

### 1.3 Force-push สถานะ main ไปยัง feature branch

```bash
# บันทึก main's DualBranch commits ทั้งหมดไปไว้ใน feature branch
git push origin main:feature/dualbranch-lpr-ocr --force
```

> **ผลลัพธ์:** `feature/dualbranch-lpr-ocr` มีงาน DualBranch ครบทุกอย่าง
> รวมถึง `train_model/` pipeline (dataset → train → onnx → hef)

---

## ขั้นตอนที่ 2 — Reset Main กลับสู่ Stable

### 2.1 สร้าง stable tag

```bash
git tag stable-before-dualbranch-lpr 858dd71
git push origin stable-before-dualbranch-lpr
```

### 2.2 Hard reset main ไปที่ stable point

```bash
git reset --hard stable-before-dualbranch-lpr
```

### 2.3 Force-push main (จำเป็นเพราะ remote มี DualBranch commits)

```bash
git push --force origin main
```

> **คำเตือน:** Force-push เขียนทับ history บน remote `main`
> ทุก device ที่ pull main ไปแล้วต้อง `git reset --hard stable-before-dualbranch-lpr` ด้วย

---

## ขั้นตอนที่ 3 — แก้ไข Stale OCR Comments

ตรวจพบว่า codebase ยังมีการอ้างถึง PaddleOCR/EasyOCR อยู่หลายจุด
ทั้งที่ engine จริงถูกเปลี่ยนเป็น Tesseract 5 แล้ว

### ไฟล์ที่แก้ไข (Backend)

| ไฟล์ | จุดที่แก้ |
|------|-----------|
| `edge/src/components/parallel_ocr_processor.py` | Docstrings, `'method': 'paddleocr'` → `'tesseract'`, return key `'easyocr'` → `'tesseract'`, parameter `easyocr_result` → `tesseract_result` |
| `edge/src/components/detection_processor.py` | Docstrings, variable names `easyocr_*` → `tesseract_*`, status keys `easyocr_available/ready` → `tesseract_available/ready`, `ocr_method = "paddleocr"` → `"tesseract"`, parallel result key `'easyocr'` → `'tesseract'` |

### ไฟล์ที่แก้ไข (Web / Dashboard)

| ไฟล์ | จุดที่แก้ |
|------|-----------|
| `edge/src/web/blueprints/detection.py` | API key `easyocr_available` → `tesseract_available` |
| `edge/src/web/templates/detection/dashboard.html` | Status indicator id+label, success rate label+id |
| `edge/src/web/templates/health/dashboard.html` | Metric card label "EASY OCR" → "TESSERACT OCR", health-check condition |
| `edge/src/web/templates/experiments/singleshot_detection.html` | Mock OCR method label ใน demo data |
| `edge/src/web/static/js/detection.js` | Default state key, `updateModelStatus` call, result key, column header, success rate variable+element id |

> **ข้อสังเกต:** Lines 2310–2363 ใน `detection_processor.py` ยังคงใช้ `easyocr_*` เพราะ
> เป็น legacy fallback path ที่เรียก `async_ocr_loader` (EasyOCR จริง) ไม่ใช่ Tesseract
> จึงเพิ่ม comment ว่า `# Try legacy EasyOCR via async_ocr_loader (last-resort fallback)` แทน

---

## ขั้นตอนที่ 4 — Tag Version และ Sync กล้อง

### 4.1 สร้าง annotated tag v2.2.1

```bash
git tag -a v2.2.1 -m "v2.2.1: Fix stale OCR engine labels (EasyOCR/PaddleOCR → Tesseract)"
git push origin v2.2.1
```

### 4.2 Sync aicamera1

```bash
sshpass -p 'admin88366' ssh -o StrictHostKeyChecking=no camuser@aicamera1 \
  "cd /home/camuser/aicamera && \
   git fetch --tags --force && \
   git reset --hard v2.2.1 && \
   git log --oneline -3 && \
   git describe --tags"
```

**ผลลัพธ์:** `HEAD is now at 32d243e` — `git describe` แสดง `v2.2.1` ✅

### 4.3 Sync aicamera2

```bash
sshpass -p 'admin88366' ssh -o StrictHostKeyChecking=no camuser@aicamera2 \
  "cd /home/camuser/aicamera && \
   git fetch --tags --force && \
   git reset --hard v2.2.1 && \
   git log --oneline -3 && \
   git describe --tags"
```

> **หมายเหตุ:** aicamera2 offline ระหว่าง session (100% packet loss บน Tailscale IP 100.110.20.53)
> ต้องรันคำสั่งนี้ใหม่เมื่อ device กลับมา online

---

## สถานะหลังดำเนินการ

```
main (local+remote)
  858dd71  stable-before-dualbranch-lpr  ← base
  d36750a  fix(comments): PaddleOCR → Tesseract
  32d243e  fix(web): EasyOCR/PaddleOCR → Tesseract in dashboard  ← HEAD = v2.2.1

feature/dualbranch-lpr-ocr (remote)
  858dd71  stable base
  820df13  Add DualBranchLPRNet...        ← committed earlier on main
  a970825  feat(wip): save DualBranch LPR work...  ← all uncommitted work
```

| อุปกรณ์ | Version | สถานะ |
|---------|---------|-------|
| Mac | `v2.2.1` | ✅ |
| aicamera1 | `v2.2.1` | ✅ |
| aicamera2 | — | ❌ offline — ต้อง sync ทีหลัง |

---

## Tag Reference

| Tag | Commit | ความหมาย |
|-----|--------|----------|
| `stable-before-dualbranch-lpr` | `858dd71` | จุดก่อนเริ่มพัฒนา DualBranch |
| `v2.2.1` | `32d243e` | Stable pipeline + Tesseract label fixes |

---

## กลับมาพัฒนา DualBranch

เมื่อพร้อมกลับมาพัฒนา DualBranchLPRNet ต่อ:

```bash
# บน Mac
git checkout feature/dualbranch-lpr-ocr

# ดู state ล่าสุดของ feature branch
git log --oneline -5

# Deploy ทดสอบบน aicamera1
bash scripts/deploy_dualbranch_degirum.sh
```

ดู `CONTEXT.md` สำหรับ debug history และ technical details ของ DualBranchLPRNet

---

## คำสั่ง Quick Reference

```bash
# ตรวจสอบ version บนกล้อง
sshpass -p 'admin88366' ssh camuser@aicamera1 \
  "cd /home/camuser/aicamera && git describe --tags && git log --oneline -1"

# Force-sync กล้องไป tag ใด tag หนึ่ง
TAG=v2.2.1
for HOST in aicamera1 aicamera2; do
  sshpass -p 'admin88366' ssh -o StrictHostKeyChecking=no camuser@$HOST \
    "cd /home/camuser/aicamera && git fetch --tags --force && git reset --hard $TAG && git describe --tags"
done

# ดู tags ทั้งหมด
git tag -l | sort -V

# ดู branch ที่มีอยู่
git branch -a
```
