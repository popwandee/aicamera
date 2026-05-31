# CONTEXT.md — Edge LPR Pipeline Architecture
> อัปเดต: 2026-05-31 | ผู้เขียน: PWD Vision Works

---

## 1. สถานะปัจจุบัน (Current Pipeline State)

### 1.1 สถาปัตยกรรม (Async Producer-Consumer — DEPLOYED)

```
[Camera Frame @30 FPS]
      │
      ▼
[Hailo: Vehicle Detection]  ← yolov8n_relu6_car--640x640  (~14-20ms/frame)
      │  confidence ≥ 0.8
      ▼
[Hailo: Plate Detection]    ← yolov8n_relu6_lp--640x640
      │
      ▼
[Vehicle Tracking / IoU]    ← assign track_id ด้วย IoU matching
      │
      ▼
[Quality Gate]              ← _check_plate_quality() — ขนาด/aspect/blur/brightness
      │
      ▼
[OCR Queue Gatekeeper]      ← _should_submit_for_ocr(): dup-track / quality check
      │  put_nowait() — NON-BLOCKING
      ▼
[ocr_queue: Queue(maxsize=10)]
      │
      ▼
[OCR Worker Thread]         ← OcrQueueWorker — background thread
  ├── Hailo OCR             ← yolov8n_relu6_lp_ocr--256x128
  └── ThaiLPROCR (Tesseract)← tha+eng, PSM 11
      │
      ▼
[poll_ocr_results() — non-blocking]
      │
      ▼
[Save SQLite / WebSocket / MQTT]
```

**Main detection thread ไม่ถูก block** — OCR รันใน background thread แยกต่างหาก

### 1.2 ไฟล์ที่เกี่ยวข้อง

| ไฟล์ | บทบาท | สถานะ |
|------|--------|--------|
| `src/components/detection_processor.py` | Pipeline หลัก, Tracking, OCR Orchestration | ✅ |
| `src/components/parallel_ocr_processor.py` | Hailo+Tesseract รันคู่ขนาน (sync fallback) | ✅ |
| `src/components/ocr_queue_worker.py` | Async OCR Queue Worker thread | ✅ DEPLOYED |
| `src/components/thai_lp_ocr.py` | ThaiLPROCR — Tesseract wrapper | ✅ |
| `src/components/camera_handler.py` | Camera capture @30 FPS, FrameDurationLimits | ✅ |
| `src/components/health_monitor.py` | System health checks, DB logging | ✅ |
| `src/components/database_manager.py` | SQLite local detection storage | ✅ |
| `src/services/detection_manager.py` | Top-level service coordinator | ✅ |
| `src/services/websocket_sender.py` | Socket.IO client → lprserver | ✅ |

### 1.3 สิ่งที่มีอยู่แล้ว (ไม่ต้องทำซ้ำ)

| ฟีเจอร์ | ตำแหน่ง | หมายเหตุ |
|---------|---------|----------|
| Laplacian blur check | `_check_plate_quality()` | threshold = 30 * area_factor |
| Size threshold | `_check_plate_quality()` | min_w=80px, min_h=24px |
| Aspect ratio check | `_check_plate_quality()` | 1.5–6.0 |
| Vehicle IoU Tracking | `update_vehicle_tracks()` | assign track_id |
| Frame scoring | `_calculate_frame_score()` | sharpness+conf+area+center |
| Best frame per track | `VehicleTrack.best_frame_data` | อัปเดตทุก frame |
| Deduplication | `apply_deduplication_rules()` | ป้องกันรถคันเดิมซ้ำ |
| Brightness/Contrast check | `_check_plate_quality()` | mean < 30 หรือ > 240 reject |
| OCR Queue Worker | `ocr_queue_worker.py` | 1 worker thread, maxsize=10 |

### 1.4 สถิติ Detection Pipeline (จากตัวจริง)

| ตัวชี้วัด | aicamera1 | aicamera2 |
|----------|-----------|-----------|
| Camera FPS | 30.01 | 29.98 |
| Hailo inference time | ~14 ms/frame | ~31 ms/frame |
| Vehicle model | yolov8n_relu6_car--640x640 | yolov8n_relu6_car--640x640 |
| LP detection model | yolov8n_relu6_lp--640x640 | yolov8n_relu6_lp--640x640 |
| LP OCR model | yolov8n_relu6_lp_ocr--256x128 | yolov8n_relu6_lp_ocr--256x128 |
| Tesseract | available (tha+eng) | available (tha+eng) |
| Vehicle confidence threshold | 0.8 | 0.8 |

---

## 2. ปัญหาที่แก้ไขแล้ว (Resolved)

### ✅ OCR Block Main Thread → RESOLVED (2026-05-24)
`perform_ocr()` เดิม block main thread สูงสุด 10 วินาที  
แก้โดยย้าย OCR ไปใน `OcrQueueWorker` background thread ด้วย `queue.Queue(maxsize=10)`

### ✅ health_monitor ใช้ localhost:5000 → RESOLVED (2026-05-31)
`check_model_loading()` พยายาม connect `localhost:5000` แต่ gunicorn bind ที่ Unix socket  
แก้เป็น `http://localhost/detection/status` (nginx port 80)  
**ผล:** `overall_status` จาก "warning" กลับเป็น "healthy"

### ✅ Camera FPS ค้างที่ 15 แทน 30 → RESOLVED (2026-05-31)
**ปัญหา 1:** `edge/installation/.env.production` มี `CAMERA_FPS=15` ทับค่า default  
**ปัญหา 2:** `camera_handler.py` ตั้ง `frame_duration_max_us = min * 2` อนุญาต ISP ลด fps เหลือ 15 ในแสงน้อย  
แก้: `CAMERA_FPS=30` ใน `.env.production` + `frame_duration_max_us = frame_duration_min_us` (fixed 30 fps)

### ✅ SQLite "cannot commit - no transaction is active" → RESOLVED (2026-05-31)
`health_monitor._log_result()` ใช้ shared SQLite connection กับ `check_same_thread=False`  
หลาย thread race กัน → commit() ล้มเหลว  
แก้: wrap `connection.commit()` ใน try/except

### ✅ total_processed counter ค้างที่ 0 → RESOLVED (2026-05-31)
`processing_stats['total_processed']` initialized แต่ไม่เคย increment  
แก้: เพิ่ม `self.processing_stats['total_processed'] += 1` ใน `detect_vehicles()`

### ✅ WebSocket 500 errors ทุก 60 วิ → RESOLVED (2026-05-31)
lprserver `cameras` table ขาดคอลัมน์ `ip_address`  
TypeORM SELECT cameras ทำ JOIN แล้ว column ไม่มี → 500  
แก้: `ALTER TABLE cameras ADD COLUMN ip_address varchar(45) NULL`

---

## 3. Disk & Log Management (2026-05-31)

ทั้ง 2 กล้องได้รับการตั้งค่าต่อไปนี้:

### `/etc/logrotate.d/aicamera`
- `gunicorn_access.log`, `gunicorn_error.log` — rotate daily, keep 7, compress, USR1 signal
- `hailort.log`, `hailort.1.log` — rotate weekly, keep 2, copytruncate

### `/etc/systemd/journald.conf.d/aicamera-size.conf`
```
SystemMaxUse=200M
RuntimeMaxUse=50M
```

### `/etc/cron.d/aicamera-cleanup`
- 03:00 ทุกวัน: ลบ `/tmp/chromium-kiosk/BrowserMetrics/` ที่เก่ากว่า 1 วัน
- 03:30 ทุกอาทิตย์: เก็บ `hailort_backup_*.log` ไว้แค่ 3 ไฟล์ล่าสุด

### สคริปต์ deploy
`edge/scripts/setup_logrotate.sh` — ใช้รันบน device ใหม่เพื่อตั้งค่าทั้งหมดข้างต้น

---

## 4. Decision Log (บันทึกเหตุผลการตัดสินใจ)

| วันที่ | การตัดสินใจ | เหตุผล |
|--------|------------|--------|
| 2026-05-24 | ใช้ `threading.Thread` สำหรับ OCR Worker | Tesseract เป็น subprocess (I/O bound) → threading เพียงพอ ไม่ต้องใช้ multiprocessing |
| 2026-05-24 | `queue.Queue(maxsize=10)` drop mode | ป้องกัน memory flood; ป้ายที่ missed จะถูก retry ในรอบถัดไป |
| 2026-05-24 | คง `ParallelOCRProcessor` ไว้ | ใช้ใน sync/experiment mode; ไม่รื้อโค้ดที่ทำงานได้ |
| 2026-05-24 | ไม่ใช้ ByteTrack/SORT เต็มรูปแบบ | IoU tracking ที่มีใน `VehicleTrack` เพียงพอ; ByteTrack เพิ่ม complexity โดยไม่จำเป็น |
| 2026-05-31 | `FrameDurationLimits` min==max (fixed FPS) | ต้องการ 30 fps คงที่สำหรับ LPR; ISP compensate low-light ด้วย gain แทน shutter time |
| 2026-05-31 | Tesseract แทน EasyOCR/PaddleOCR | PaddleOCR segfault บน ARM64; EasyOCR ต้อง download โมเดลขนาดใหญ่ ไม่เหมาะ edge |
| 2026-05-31 | logrotate ระดับ OS แทน Python handler | gunicorn เขียน log ตรงไปยังไฟล์ Python `TimedRotatingFileHandler` ใช้ไม่ได้กับ gunicorn |
