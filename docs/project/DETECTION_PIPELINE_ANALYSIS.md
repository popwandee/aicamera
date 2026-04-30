# Detection Pipeline Analysis — AI Camera LPR

**วันที่วิเคราะห์:** 2026-04-28  
**สถานการณ์:** Field Test 30 นาที — ไม่มี detection เลย, stream ไม่ smooth, ภาพ aspect/color ผิดปกติ  
**สถานะ:** 🔴 Critical issues found — ต้องแก้ก่อน field test ครั้งต่อไป  

---

## 🚨 Critical Issues Found (สาเหตุที่ไม่มี detection)

### Issue #1 — DETECTION_INTERVAL = 30.0 วินาที ‼️ (ROOT CAUSE)

```python
# edge/src/core/config.py line 108
DETECTION_INTERVAL = float(os.getenv("DETECTION_INTERVAL", "30.0"))
# "Optimized to 30.0s for performance"
```

**ผลกระทบ:** ระบบ process ภาพเพื่อ detection เพียง **1 ครั้งทุก 30 วินาที**  
รถที่วิ่งผ่านหน้ากล้องด้วยความเร็ว 40 km/h ใช้เวลาอยู่ในเฟรมประมาณ **0.5–2 วินาที**  
→ โอกาสที่รถจะอยู่ในเฟรมพอดีตอน process = น้อยมาก  
**แก้ไข:** ลด DETECTION_INTERVAL เป็น `0.5` หรือ `1.0` วินาที

---

### Issue #2 — CONFIDENCE_THRESHOLD = 0.8 (สูงเกินไป)

```python
# edge/src/core/config.py
CONFIDENCE_THRESHOLD = float(os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.8"))
PLATE_CONFIDENCE_THRESHOLD = float(os.getenv("PLATE_CONFIDENCE_THRESHOLD", "0.6"))
```

**ผลกระทบ:** ต้องการ confidence ≥ 80% สำหรับ vehicle detection  
สภาพแสงกลางแจ้ง, มุมกล้อง, ระยะห่าง อาจทำให้ confidence ต่ำกว่า threshold  
**แก้ไข:** ลดเป็น `0.6`–`0.65` เพื่อทดสอบ

---

### Issue #3 — MAIN_RESOLUTION = 640x640 (Square aspect ratio)

```python
# edge/src/core/config.py
MAIN_RESOLUTION = tuple(map(int, os.getenv("MAIN_RESOLUTION", "640x640").split('x')))
# → (640, 640) — square
LORES_RESOLUTION = tuple(map(int, os.getenv("LORES_RESOLUTION", "640x480").split('x')))
# → (640, 480) — 4:3 (comment says "LPR optimized: 640x640" แต่ค่าจริงเป็น 480)
```

**ผลกระทบ:**  
- Main stream (ใช้ detection): 640×640 → **ภาพถูก letterbox** จากเซ็นเซอร์ IMX708 ที่เป็น 4:3  
  → ภาพ distorted, มีแถบดำ → aspect ratio ไม่ปกติที่เห็น
- Lores stream (ใช้ streaming UI): 640×480 ถูกต้อง แต่ resolution ไม่ match comment

---

### Issue #4 — Color Space ผิดปกติ (RGB vs BGR)

```python
# edge/src/services/video_streaming.py
# Picamera2 ส่งภาพใน RGB888
# แต่ cv2.imencode ต้องการ BGR
# → ถ้า convert ไม่ถูกต้อง สีแดงกับน้ำเงินจะสลับ (ภาพเป็นสีส้ม/ฟ้าผิดปกติ)
_, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
```

**ผลกระทบ:** ภาพใน stream มีสีผิดปกติ (แดง↔น้ำเงิน สลับกัน)  
**ต้องตรวจสอบ:** ว่า frame ถูก convert จาก RGB→BGR ก่อน imencode หรือไม่

---

### Issue #5 — Stream ไม่ smooth (Frame Queue + JPEG Quality)

```python
# video_streaming.py
self.frame_queue = queue.Queue(maxsize=3)  # 3 frame buffer
self.quality = 70  # JPEG quality 70%
self.fps = DEFAULT_FRAMERATE  # = 30 fps (config)
```

**ผลกระทบ:**  
- Frame queue maxsize=3 อาจทำให้ drop frames ถ้า encoding ช้า
- JPEG quality 70 บน Tailscale latency 28ms อาจทำให้ stream กระตุก

---

## Detection Pipeline — Full Code Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  app.py → create_app() → _initialize_services()                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │  Phase 0: Device Registration      │
         │  registration_manager.start()      │
         └─────────────────┬──────────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │  Phase 2: Core Components          │
         │  - camera_handler (singleton)      │
         │  - detection_processor             │
         │  - database_manager                │
         │  - health_monitor                  │
         └─────────────────┬──────────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │  Phase 3: Core Services            │
         │  camera_manager.initialize()       │
         │    └─ camera_handler.initialize_camera()  │
         │         └─ Picamera2 start         │
         │         └─ configure streams:      │
         │              main: 640x640 (RGB)   │
         │              lores: 640x480 (RGB)  │
         │    └─ AUTO_START_CAMERA = True     │
         │    └─ camera_manager.start()       │
         │    └─ AUTO_START_STREAMING = True  │
         │    └─ camera_handler.start_streaming() │
         └─────────────────┬──────────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │  detection_manager.initialize()    │
         │    └─ detection_processor.load_models() │
         │         ├─ vehicle_model (Hailo)   │
         │         │   yolov8n_relu6_car      │
         │         │   640x640_hailo8_1       │
         │         ├─ lp_detection_model      │
         │         │   yolov8n_relu6_lp       │
         │         │   640x640_hailo8_1       │
         │         └─ lp_ocr_model            │
         │             yolov8n_relu6_lp_ocr   │
         │             256x128_hailo8_1       │
         │    └─ async_ocr_loader (EasyOCR)   │
         │         └─ load in background thread │
         │    └─ AUTO_START_DETECTION = True  │
         │    └─ detection_manager.start_detection() │
         │         └─ _detection_loop() thread │
         └─────────────────┬──────────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │  Phase 4-5: Optional               │
         │  - websocket_sender → lprserver    │
         │  - mqtt_health_sender → MQTT       │
         │  - storage_service                 │
         └────────────────────────────────────┘
```

---

## Detection Loop — ขั้นตอนละเอียด

```
_detection_loop() — runs in separate thread
│
│  [ทุก DETECTION_INTERVAL = 30.0 วินาที] ← ⚠️ ปัญหาหลัก
│
├─ 1. get_service('camera_manager')
├─ 2. _is_camera_ready() → ตรวจสอบ camera.initialized AND camera.streaming
├─ 3. process_frame_from_camera(camera_manager)
│      └─ camera_handler.capture_frame(
│              source="buffer",        ← จาก circular buffer
│              stream_type="main",     ← ใช้ main stream (640x640 RGB)
│              include_metadata=False
│         )
│         → returns numpy array (H, W, 3) RGB format
│
└─ 4. process_frame(frame)
       │
       ├─ Step 1: validate_and_enhance_frame(frame)
       │    ├─ ตรวจสอบ frame shape, dtype
       │    ├─ detect_lighting_condition() → NORMAL/LOW_LIGHT/BRIGHT/NIGHT
       │    └─ apply preprocessing:
       │         ├─ illumination adjustment
       │         ├─ contrast enhancement (CLAHE)
       │         └─ denoise (if low light)
       │
       ├─ Step 2: detect_vehicles(frame)  ← ใช้ frame ต้นฉบับ
       │    ├─ resize_for_model_input() → letterbox 640x640
       │    │    └─ เก็บ mapping_info (scale, pad_x, pad_y)
       │    ├─ vehicle_model.predict(resized_frame)  ← Hailo inference
       │    ├─ filter by confidence >= 0.8  ← ⚠️ threshold สูง
       │    ├─ map bbox กลับสู่ original coordinates
       │    └─ returns vehicle_boxes[], mapping_info
       │    → ถ้าไม่มี vehicles: return None (ข้ามทุกอย่าง)
       │
       ├─ Step 2.5: update_vehicle_tracks() + apply_deduplication_rules()
       │    ├─ TRACKING_ENABLED = True
       │    ├─ IoU matching กับ active_tracks
       │    ├─ track_timeout = 5.0 วินาที
       │    ├─ REENTRY_TIME_THRESHOLD = 30.0 วินาที ← ⚠️ อาจ block re-detect
       │    └─ _should_save_detection() → IoU + time check
       │
       ├─ Step 3: detect_license_plates(frame, vehicle_boxes, mapping_info)
       │    ├─ สำหรับแต่ละ vehicle bbox: crop vehicle region
       │    ├─ lp_detection_model.predict(vehicle_crop) ← Hailo inference
       │    ├─ filter by plate_confidence >= 0.6
       │    ├─ map plate bbox → original frame coordinates
       │    └─ returns plate_boxes[]
       │
       ├─ Step 4: perform_ocr(frame, plate_boxes)
       │    ├─ สำหรับแต่ละ plate bbox: crop plate region
       │    ├─ pre_ocr_processing():
       │    │    ├─ resize plate to 256x128 (letterbox)
       │    │    ├─ contrast enhancement
       │    │    └─ sharpening
       │    ├─ PARALLEL OCR (2 branches):
       │    │    ├─ Branch A: lp_ocr_model (Hailo) → text + confidence
       │    │    └─ Branch B: EasyOCR CPU (Thai + English)
       │    └─ merge: เลือก best result ตาม confidence
       │
       ├─ Step 5: select best frame
       │    └─ weighted score = 0.4×sharpness + 0.3×plate_conf
       │                      + 0.2×area_ratio + 0.1×centeredness
       │
       ├─ Step 6: save_detection_results()
       │    ├─ บันทึก original frame เป็น JPEG quality 85%
       │    ├─ path: IMAGE_SAVE_DIR/captured_images/
       │    └─ draw bounding boxes บน image
       │
       └─ Step 7: store in database (SQLite local)
            ├─ timestamp, vehicles_count, plates_count
            ├─ ocr_results (text, confidence, method)
            ├─ original_image_path
            ├─ vehicle_detections, plate_detections
            └─ coordinate_mapping
            → ส่งต่อไป websocket_sender → lprserver
```

---

## Video Streaming Pipeline

```
camera_handler.lores_stream (Picamera2)
│  resolution: 640x480 RGB888
│  fps: 30 (DEFAULT_FRAMERATE)
│
VideoStreamingService._get_stream_frame()
│  Priority 1: camera_handler.capture_frame(source="buffer", stream_type="lores")
│    ├─ Hardware MJPEG: return bytes directly
│    └─ RGB888 array → cv2.imencode('.jpg', frame_bgr, quality=70)
│         ⚠️ frame_bgr — ต้องตรวจ: RGB→BGR conversion ถูกต้อง?
│  Priority 2: last_successful_frame (cache)
│  Priority 3: fallback_frame (static black/pattern image)
│
frame_queue (maxsize=3)
│  → generate_frames() → multipart/x-mixed-replace MJPEG stream
│  → web browser / kiosk display
```

---

## Config Parameters ที่สำคัญ (ค่าปัจจุบัน vs แนะนำ)

| Parameter | ค่าปัจจุบัน | แนะนำสำหรับ Field Test | ผลกระทบ |
|-----------|-----------|---------------------|---------|
| `DETECTION_INTERVAL` | **30.0 s** | **0.5–1.0 s** | 🔴 Root cause ไม่มี detection |
| `CONFIDENCE_THRESHOLD` | **0.8** | **0.6–0.65** | 🟡 อาจ miss vehicles |
| `PLATE_CONFIDENCE_THRESHOLD` | 0.6 | 0.5 | 🟡 ปรับได้ |
| `MAIN_RESOLUTION` | 640×640 | 1280×720 หรือ 640×480 | 🟡 Aspect ratio |
| `LORES_RESOLUTION` | 640×480 | 640×480 ✅ | ✅ ปกติ |
| `DEFAULT_FRAMERATE` | 30 | 15–20 | 🟡 ลดเพื่อ stability |
| `REENTRY_TIME_THRESHOLD` | 30.0 s | 5.0–10.0 s | 🟡 Dedup window |
| `TRACKING_ENABLED` | True | True ✅ | ✅ |
| `IMAGE_SAVE_DIR` | `edge/db/` area | ตรวจ path | 🟡 |

---

## File & Service Map

| Component | ไฟล์ | บทบาท |
|-----------|-----|------|
| **App Entry** | `edge/src/app.py` | Flask app, init sequence |
| **Config** | `edge/src/core/config.py` | ค่าตั้งต้นทั้งหมด |
| **DI Container** | `edge/src/core/dependency_container.py` | Service wiring |
| **CameraHandler** | `edge/src/components/camera_handler.py` | Picamera2 singleton, buffer |
| **CameraManager** | `edge/src/services/camera_manager.py` | High-level camera ops |
| **DetectionProcessor** | `edge/src/components/detection_processor.py` | Hailo models, OCR, tracking |
| **DetectionManager** | `edge/src/services/detection_manager.py` | Detection loop, dedup |
| **VideoStreaming** | `edge/src/services/video_streaming.py` | MJPEG stream to browser |
| **WebSocketSender** | `edge/src/services/websocket_sender.py` | ส่งผลไป lprserver |
| **MQTTHealthSender** | `edge/src/services/mqtt_health_sender.py` | Health via MQTT |
| **DatabaseManager** | `edge/src/components/database_manager.py` | SQLite local storage |
| **AsyncOCRLoader** | `edge/src/components/async_ocr_loader.py` | EasyOCR lazy init |
| **ParallelOCRProcessor** | `edge/src/components/parallel_ocr_processor.py` | Hailo+EasyOCR parallel |

---

## Env Config ที่ต้องแก้ไขก่อน Field Test ครั้งต่อไป

ไฟล์: `/home/camuser/aicamera/edge/installation/.env.production`

```ini
# === CRITICAL FIX ===
DETECTION_INTERVAL=1.0                    # แก้จาก 30.0 → 1.0 วินาที ‼️

# === RECOMMENDED ADJUSTMENTS ===
DETECTION_CONFIDENCE_THRESHOLD=0.65       # แก้จาก 0.8 → 0.65
PLATE_CONFIDENCE_THRESHOLD=0.50           # แก้จาก 0.6 → 0.50
REENTRY_TIME_THRESHOLD=10.0              # แก้จาก 30.0 → 10.0 วินาที

# === RESOLUTION (ตรวจสอบ aspect ratio) ===
MAIN_RESOLUTION=1280x720                  # เปลี่ยนจาก 640x640 (square) → 720p (16:9)
# หรือ
MAIN_RESOLUTION=640x480                   # ตรงกับ lores เพื่อลด letterbox

# === CAMERA ===
CAMERA_FPS=15                            # ลดจาก 30 เพื่อ stability
```

---

## สิ่งที่ต้องตรวจสอบเพิ่มเติม (Investigate Later)

### ด้าน Color/Aspect ผิดปกติ
- [ ] ตรวจ `camera_handler.py`: Picamera2 config `format` — ใช้ `RGB888` หรือ `BGR888`?
- [ ] ตรวจ `video_streaming.py`: line ที่ convert frame ก่อน `imencode` — มี `cvtColor(RGB→BGR)` หรือไม่?
- [ ] ตรวจ Picamera2 `ScalerCrop` / `ScalerCropMaximum` — อาจทำให้ aspect ratio เพี้ยน

### ด้าน Detection ไม่ทำงาน
- [ ] ตรวจ log: `journalctl -u aicamera_lpr -n 100` หาข้อความ `Detection loop stopped` หรือ error
- [ ] ตรวจว่า `AUTO_START_DETECTION=True` ใน config จริงหรือไม่
- [ ] ตรวจ `detection_processor.load_models()` สำเร็จหรือไม่ (Hailo init)
- [ ] ตรวจ `_is_camera_ready()` คืนค่า True หรือไม่

### ด้าน Stream ไม่ smooth  
- [ ] ตรวจ CPU usage ขณะ stream (Hailo + EasyOCR + streaming พร้อมกัน)
- [ ] ตรวจ `frame_queue` — เกิด `queue.Full` exception บ่อยหรือไม่
- [ ] ทดลองลด `CAMERA_FPS=15`

---

## Quick Fix Commands (ทำได้ทันที)

```bash
ssh camuser@100.110.20.53

# แก้ config
nano /home/camuser/aicamera/edge/installation/.env.production
# เพิ่ม/แก้:
#   DETECTION_INTERVAL=1.0
#   DETECTION_CONFIDENCE_THRESHOLD=0.65
#   REENTRY_TIME_THRESHOLD=10.0

# Restart service
sudo systemctl restart aicamera_lpr
sleep 3
sudo systemctl status aicamera_lpr

# ดู log realtime
journalctl -u aicamera_lpr -f | grep -E "(Detection|Vehicle|Plate|OCR|Error|interval|DETECTION)"
```

---

## สรุป Root Cause

```
ปัญหา: ไม่มี detection เลยใน 30 นาที
สาเหตุหลัก: DETECTION_INTERVAL = 30.0 วินาที
             → ระบบดูภาพเพื่อหารถเพียง 60 ครั้งใน 30 นาที
             → รถผ่านเร็วกว่า 30 วินาทีมาก → MISS ทุกคัน

ปัญหา: ภาพ aspect ratio และสีผิด
สาเหตุ: MAIN_RESOLUTION=640x640 (square) แต่กล้องเป็น 4:3
         → letterbox padding → ภาพบิดเบี้ยว
         + อาจมี RGB/BGR conversion ไม่ถูกต้อง → สีแดงน้ำเงินสลับ

Fix ทันที: แก้ DETECTION_INTERVAL=1.0 → restart service
```

---

## ✅ Fixes Applied — 2026-04-28

### Fix #1 — RGB→BGR Color Conversion [CODE FIX — COMMITTED]

**ไฟล์:** `edge/src/services/video_streaming.py` บรรทัด 169–172  
**Commit:** `5a94ddc`

```python
# BEFORE (bug — commented out):
#frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
frame_bgr = frame   # ← RGB ส่งตรงเข้า imencode → สีแดง/น้ำเงิน swap

# AFTER (fixed):
# FIX 2026-04-28: was commented out causing red/blue channel swap
frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
```

**Deploy:** `git push` แล้ว `git pull` บน aicamera2 + restart service

---

### Fix #2 — .env.production Parameters [ENV FIX — SCRIPT READY]

**Script:** `scripts/patch_env_aicamera2.sh`  
**รันบน Mac:** `chmod +x scripts/patch_env_aicamera2.sh && ./scripts/patch_env_aicamera2.sh`

| Parameter | Before | After | เหตุผล |
|---|---|---|---|
| `DETECTION_INTERVAL` | `30.0` | `0.5` | รถผ่านใน <2s → ต้อง detect บ่อยกว่านี้ |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.8` | `0.65` | Field condition → ลด threshold |
| `LORES_RESOLUTION` | `640x640` | `640x480` | Fix 4:3 aspect ratio ของ IMX708 |
| `REENTRY_TIME_THRESHOLD` | `30.0` | `10.0` | Allow re-detection ถี่ขึ้น |

---

### Verification Checklist หลัง Deploy

```bash
# 1. SSH เข้า aicamera2
ssh camuser@100.110.20.53

# 2. ตรวจสอบ service running
sudo systemctl status aicamera_lpr | grep Active

# 3. ดู detection interval ใน log
journalctl -u aicamera_lpr -f | grep -E "(interval|detect|vehicle|Plate)"

# 4. ตรวจสอบ stream URL (เปิดใน browser)
#    http://100.110.20.53:5000/stream
#    → ภาพควรเป็น 4:3, สีปกติ, ไม่มี letterbox

# 5. ทดสอบ detection API
curl http://100.110.20.53:5000/api/v1/detection/status | python3 -m json.tool

# 6. นำรถผ่านหน้ากล้อง → ดูใน log ว่ามี vehicle detected ไหม
```

---

### สถานะ Issues

| Issue | สาเหตุ | Fix | สถานะ |
|---|---|---|---|
| #1 ไม่มี detection | `DETECTION_INTERVAL=30.0` | ลดเป็น `0.5` | 🟡 รอ deploy env |
| #2 confidence สูงเกิน | `CONFIDENCE_THRESHOLD=0.8` | ลดเป็น `0.65` | 🟡 รอ deploy env |
| #3 aspect ratio ผิด | `LORES_RESOLUTION=640x640` | เปลี่ยนเป็น `640x480` | 🟡 รอ deploy env |
| #4 สีผิด RGB/BGR | conversion ถูก comment | restore `cv2.cvtColor` | ✅ Code committed |

**อัปเดตสถานะ:** 2026-04-28 — Code fix committed, ENV fix scripts ready, pending deploy

Log 
(.venv) camuser@aicamera2:~/aicamera $ python edge/scripts/test_image_detection.py --images edge/captured_images/detection_20260428_180250_039.jpg 
2026-04-29 16:47:32,221 [INFO] Starting static image detection test
2026-04-29 16:47:32,221 [INFO] Models: vehicle=yolov8n_relu6_car--640x640_quant_hailort_hailo8_1, plate=yolov8n_relu6_lp--640x640_quant_hailort_hailo8_1, ocr=yolov8n_relu6_lp_ocr--256x128_quant_hailort_hailo8_1
2026-04-29 16:47:32,221 [INFO] Images to process: 1
2026-04-29 16:47:32,221 [INFO] [DETECTION] Starting Detection Processor initialization...
2026-04-29 16:47:32,221 [INFO] 🔍 [DETECTION_PROC] Initializing model instances...
2026-04-29 16:47:32,221 [INFO] 🔍 [DETECTION_PROC] Model instances initialized
2026-04-29 16:47:32,221 [INFO] 🔍 [DETECTION_PROC] Creating AsyncOCRLoader...
2026-04-29 16:47:32,221 [INFO] AsyncOCRLoader initialized
2026-04-29 16:47:32,221 [INFO] 🔍 [DETECTION_PROC] AsyncOCRLoader created successfully
2026-04-29 16:47:32,221 [INFO] 🔍 [DETECTION_PROC] Initializing parallel OCR processor...
2026-04-29 16:47:32,222 [INFO] 🔍 [DETECTION_PROC] Parallel OCR processor initialized
2026-04-29 16:47:32,222 [INFO] 🔍 [DETECTION_PROC] Setting up state tracking...
2026-04-29 16:47:32,222 [INFO] 🔍 [DETECTION_PROC] State tracking initialized
2026-04-29 16:47:32,222 [INFO] DetectionProcessor initialized
2026-04-29 16:47:32,222 [INFO] 🔧 [ENHANCED_DETECTION] Initializing enhanced detection pipeline...
2026-04-29 16:47:32,222 [INFO] 🔧 [ENHANCED_DETECTION] Enhanced detection pipeline initialized successfully
2026-04-29 16:47:32,222 [INFO] 🔧 [DETECTION_PROC] Starting model loading process...
2026-04-29 16:47:32,222 [INFO] 🔧 [DETECTION_PROC] Loading detection models...
2026-04-29 16:47:32,222 [INFO] 🔧 [DETECTION_PROC] Checking model configuration...
2026-04-29 16:47:32,222 [INFO] 🔧 [DETECTION_PROC] Model configuration validated
2026-04-29 16:47:32,222 [INFO] 🔧 [DETECTION_PROC] Configuring HailoRT logging...
✅ Created symlink: /home/camuser/aicamera/hailort.log -> /home/camuser/aicamera/edge/logs/hailort.log
✅ HailoRT logging configured to: /home/camuser/aicamera/edge/logs/hailort.log (with rotation)
2026-04-29 16:47:32,223 [INFO] 🔧 [DETECTION_PROC] HailoRT logging configured
2026-04-29 16:47:32,223 [INFO] 🔧 [DETECTION_PROC] Importing degirum...
2026-04-29 16:47:33,093 [INFO] 🔧 [DETECTION_PROC] ✅ Degirum available for Hailo AI model loading
2026-04-29 16:47:33,093 [INFO] 🔧 [DETECTION_PROC] Loading vehicle detection model...
2026-04-29 16:47:33,093 [INFO] 🔧 [DETECTION_PROC] Loading vehicle detection model: yolov8n_relu6_car--640x640_quant_hailort_hailo8_1
2026-04-29 16:47:33,093 [INFO] Local inference with local zoo from '/home/camuser/aicamera/resources' dir
2026-04-29 16:47:33,953 [INFO] 🔧 [DETECTION_PROC] ✅ Vehicle detection model loaded successfully
2026-04-29 16:47:33,953 [INFO] 🔧 [DETECTION_PROC] Loading license plate detection model...
2026-04-29 16:47:33,953 [INFO] 🔧 [DETECTION_PROC] Loading license plate detection model: yolov8n_relu6_lp--640x640_quant_hailort_hailo8_1
2026-04-29 16:47:33,953 [INFO] Local inference with local zoo from '/home/camuser/aicamera/resources' dir
2026-04-29 16:47:33,984 [INFO] 🔧 [DETECTION_PROC] ✅ License plate detection model loaded successfully
2026-04-29 16:47:33,985 [INFO] 🔧 [DETECTION_PROC] Checking for optional OCR model...
2026-04-29 16:47:33,985 [INFO] 🔧 [DETECTION_PROC] Loading license plate OCR model...
2026-04-29 16:47:33,985 [INFO] 🔧 [DETECTION_PROC] Loading license plate OCR model: yolov8n_relu6_lp_ocr--256x128_quant_hailort_hailo8_1
2026-04-29 16:47:33,985 [INFO] Local inference with local zoo from '/home/camuser/aicamera/resources' dir
2026-04-29 16:47:34,037 [INFO] 🔧 [DETECTION_PROC] ✅ License plate OCR model loaded successfully
2026-04-29 16:47:34,040 [INFO] 🔧 [DETECTION_PROC] Starting asynchronous EasyOCR loading...
2026-04-29 16:47:34,042 [INFO] Loading EasyOCR Reader with languages: ['en', 'th']
2026-04-29 16:47:34,043 [INFO] 🚀 Started asynchronous EasyOCR loading...
2026-04-29 16:47:34,044 [INFO] 🔧 [DETECTION_PROC] ✅ EasyOCR loading started in background
2026-04-29 16:47:34,044 [INFO] 🔧 [DETECTION_PROC] Initializing parallel OCR processor...
2026-04-29 16:47:34,044 [INFO] ✅ Parallel OCR Processor initialized
2026-04-29 16:47:34,044 [INFO] 🔧 [DETECTION_PROC] ✅ Parallel OCR processor initialized
2026-04-29 16:47:34,044 [INFO] 🔧 [DETECTION_PROC] Model loading process completed successfully
2026-04-29 16:47:34,044 [INFO] Detection models loaded successfully
2026-04-29 16:47:34,044 [INFO] Processing image: /home/camuser/aicamera/edge/captured_images/detection_20260428_180250_039.jpg
2026-04-29 16:47:34,154 [WARNING] Vehicle detection error: Failed to perform model 'yolov8n_relu6_car--640x640_quant_hailort_hailo8_1' inference: [ERROR]Functionality is not supported
License does not allow usage of runtime agent 'HAILORT': Token is not installed: /home/camuser/.local/share/DeGirum/pysdk_cloud_token.json
dg_task_runner.cpp: 104 [DG::CoreTaskRunner::processorCreate]

2026-04-29 16:47:34,154 [INFO]   Vehicles detected: 0
2026-04-29 16:47:34,154 [INFO]   License plates detected: 0
2026-04-29 16:47:34,154 [INFO] Static image detection test completed
2026-04-29 16:47:42,230 [WARNING] Neither CUDA nor MPS are available - defaulting to CPU. Note: This module is much faster with a GPU.
2026-04-29 16:47:48,926 [INFO] ✅ EasyOCR loaded successfully in 6.70 seconds
2026-04-29 16:47:48,927 [ERROR] Error during cleanup: cannot join current thread
(.venv) camuser@aicamera2:~/aicamera $ sudo systemctl status aicamera_lpr.service
● aicamera_lpr.service - AI Camera v2.0.0 Flask Application
     Loaded: loaded (/etc/systemd/system/aicamera_lpr.service; enabled; preset: enabled)
     Active: active (running) since Tue 2026-04-28 18:17:23 +07; 22h ago
    Process: 886 ExecStartPre=/bin/bash -lc source /home/camuser/aicamera/edge/installation/venv_hailo/bin/activate && /home/camuser/aicamera/ed>
   Main PID: 914 (gunicorn: maste)
     Status: "Gunicorn arbiter booted"
      Tasks: 316 (limit: 19364)
        CPU: 5min 38.330s
     CGroup: /system.slice/aicamera_lpr.service
             ├─ 914 "gunicorn: master [aicamera_lpr]"
             └─1163 "gunicorn: worker [aicamera_lpr]"

Apr 29 16:56:55 aicamera2 aicamera_lpr[1163]: ✅ Created symlink: /home/camuser/aicamera/hailort.log -> /home/camuser/aicamera/edge/logs/hailort>
Apr 29 16:56:55 aicamera2 aicamera_lpr[1163]: ✅ HailoRT logging configured to: /home/camuser/aicamera/edge/logs/hailort.log (with rotation)
Apr 29 16:56:55 aicamera2 aicamera_lpr[1163]: ERROR HAILO_STREAM_ABORT detected — Hailo VDMA ring is in aborted state. Scheduling model reinitia>
Apr 29 16:56:59 aicamera2 aicamera_lpr[1163]: WARNING Vehicle detection model not loaded: models_loaded=False, vehicle_model=False (logged 87 ti>
Apr 29 16:57:05 aicamera2 aicamera_lpr[1163]: ✅ Created symlink: /home/camuser/aicamera/hailort.log -> /home/camuser/aicamera/edge/logs/hailort>
Apr 29 16:57:05 aicamera2 aicamera_lpr[1163]: ✅ HailoRT logging configured to: /home/camuser/aicamera/edge/logs/hailort.log (with rotation)
Apr 29 16:57:05 aicamera2 aicamera_lpr[1163]: ERROR HAILO_STREAM_ABORT detected — Hailo VDMA ring is in aborted state. Scheduling model reinitia>
Apr 29 16:57:15 aicamera2 aicamera_lpr[1163]: ✅ Created symlink: /home/camuser/aicamera/hailort.log -> /home/camuser/aicamera/edge/logs/hailort>
Apr 29 16:57:15 aicamera2 aicamera_lpr[1163]: ✅ HailoRT logging configured to: /home/camuser/aicamera/edge/logs/hailort.log (with rotation)
Apr 29 16:57:15 aicamera2 aicamera_lpr[1163]: ERROR HAILO_STREAM_ABORT detected — Hailo VDMA ring is in aborted state. Scheduling model reinitia>

(.venv) camuser@aicamera2:~/aicamera $ find /home/camuser -name "pysdk_cloud_token.json" 2>/dev/null
(.venv) camuser@aicamera2:~/aicamera $ find /root -name "pysdk_cloud_token.json" 2>/dev/null
(.venv) camuser@aicamera2:~/aicamera $ cd ..
(.venv) camuser@aicamera2:~ $ find /root -name "pysdk_cloud_token.json" 2>/dev/null
(.venv) camuser@aicamera2:~ $ cd aicamera
(.venv) camuser@aicamera2:~/aicamera $ ls -la /home/camuser/.local/share/DeGirum/
total 12
drwxrwxrwx  3 camuser camuser 4096 Jun  4  2025 .
drwxr-xr-x 12 camuser camuser 4096 Apr 25 22:39 ..
drwxrwxrwx  2 camuser camuser 4096 Apr 29 16:47 traces
(.venv) camuser@aicamera2:~/aicamera $ deactivate
camuser@aicamera2:~/aicamera $ souce venv_hailo/bin/activate
bash: souce: command not found
camuser@aicamera2:~/aicamera $ source edge/venv_hailo/bin/activate
(venv_hailo) camuser@aicamera2:~/aicamera $ python edge/scripts/test_image_detection.py --images edge/captured_images/detection_20260428_180250_039.jpg 
2026-04-29 17:03:31,028 [INFO] Starting static image detection test
2026-04-29 17:03:31,028 [INFO] Models: vehicle=yolov8n_relu6_car--640x640_quant_hailort_hailo8_1, plate=yolov8n_relu6_lp--640x640_quant_hailort_hailo8_1, ocr=yolov8n_relu6_lp_ocr--256x128_quant_hailort_hailo8_1
2026-04-29 17:03:31,028 [INFO] Images to process: 1
2026-04-29 17:03:31,028 [INFO] [DETECTION] Starting Detection Processor initialization...
2026-04-29 17:03:31,028 [INFO] 🔍 [DETECTION_PROC] Initializing model instances...
2026-04-29 17:03:31,028 [INFO] 🔍 [DETECTION_PROC] Model instances initialized
2026-04-29 17:03:31,028 [INFO] 🔍 [DETECTION_PROC] Creating AsyncOCRLoader...
2026-04-29 17:03:31,028 [INFO] AsyncOCRLoader initialized
2026-04-29 17:03:31,028 [INFO] 🔍 [DETECTION_PROC] AsyncOCRLoader created successfully
2026-04-29 17:03:31,028 [INFO] 🔍 [DETECTION_PROC] Initializing parallel OCR processor...
2026-04-29 17:03:31,028 [INFO] 🔍 [DETECTION_PROC] Parallel OCR processor initialized
2026-04-29 17:03:31,028 [INFO] 🔍 [DETECTION_PROC] Setting up state tracking...
2026-04-29 17:03:31,028 [INFO] 🔍 [DETECTION_PROC] State tracking initialized
2026-04-29 17:03:31,028 [INFO] DetectionProcessor initialized
2026-04-29 17:03:31,028 [INFO] 🔧 [ENHANCED_DETECTION] Initializing enhanced detection pipeline...
2026-04-29 17:03:31,028 [INFO] 🔧 [ENHANCED_DETECTION] Enhanced detection pipeline initialized successfully
2026-04-29 17:03:31,028 [INFO] 🔧 [DETECTION_PROC] Starting model loading process...
2026-04-29 17:03:31,028 [INFO] 🔧 [DETECTION_PROC] Loading detection models...
2026-04-29 17:03:31,028 [INFO] 🔧 [DETECTION_PROC] Checking model configuration...
2026-04-29 17:03:31,028 [INFO] 🔧 [DETECTION_PROC] Model configuration validated
2026-04-29 17:03:31,028 [INFO] 🔧 [DETECTION_PROC] Configuring HailoRT logging...
✅ Created symlink: /home/camuser/aicamera/hailort.log -> /home/camuser/aicamera/edge/logs/hailort.log
✅ HailoRT logging configured to: /home/camuser/aicamera/edge/logs/hailort.log (with rotation)
2026-04-29 17:03:31,029 [INFO] 🔧 [DETECTION_PROC] HailoRT logging configured
2026-04-29 17:03:31,029 [INFO] 🔧 [DETECTION_PROC] Importing degirum...
2026-04-29 17:03:31,860 [INFO] 🔧 [DETECTION_PROC] ✅ Degirum available for Hailo AI model loading
2026-04-29 17:03:31,860 [INFO] 🔧 [DETECTION_PROC] Loading vehicle detection model...
2026-04-29 17:03:31,861 [INFO] 🔧 [DETECTION_PROC] Loading vehicle detection model: yolov8n_relu6_car--640x640_quant_hailort_hailo8_1
2026-04-29 17:03:31,861 [INFO] Local inference with local zoo from '/home/camuser/aicamera/resources' dir
2026-04-29 17:03:32,625 [INFO] 🔧 [DETECTION_PROC] ✅ Vehicle detection model loaded successfully
2026-04-29 17:03:32,625 [INFO] 🔧 [DETECTION_PROC] Loading license plate detection model...
2026-04-29 17:03:32,625 [INFO] 🔧 [DETECTION_PROC] Loading license plate detection model: yolov8n_relu6_lp--640x640_quant_hailort_hailo8_1
2026-04-29 17:03:32,625 [INFO] Local inference with local zoo from '/home/camuser/aicamera/resources' dir
2026-04-29 17:03:32,668 [INFO] 🔧 [DETECTION_PROC] ✅ License plate detection model loaded successfully
2026-04-29 17:03:32,669 [INFO] 🔧 [DETECTION_PROC] Checking for optional OCR model...
2026-04-29 17:03:32,669 [INFO] 🔧 [DETECTION_PROC] Loading license plate OCR model...
2026-04-29 17:03:32,669 [INFO] 🔧 [DETECTION_PROC] Loading license plate OCR model: yolov8n_relu6_lp_ocr--256x128_quant_hailort_hailo8_1
2026-04-29 17:03:32,669 [INFO] Local inference with local zoo from '/home/camuser/aicamera/resources' dir
2026-04-29 17:03:32,697 [INFO] 🔧 [DETECTION_PROC] ✅ License plate OCR model loaded successfully
2026-04-29 17:03:32,697 [INFO] 🔧 [DETECTION_PROC] Starting asynchronous EasyOCR loading...
2026-04-29 17:03:32,697 [INFO] Loading EasyOCR Reader with languages: ['en', 'th']
2026-04-29 17:03:32,697 [INFO] 🚀 Started asynchronous EasyOCR loading...
2026-04-29 17:03:32,697 [INFO] 🔧 [DETECTION_PROC] ✅ EasyOCR loading started in background
2026-04-29 17:03:32,698 [INFO] 🔧 [DETECTION_PROC] Initializing parallel OCR processor...
2026-04-29 17:03:32,698 [INFO] ✅ Parallel OCR Processor initialized
2026-04-29 17:03:32,698 [INFO] 🔧 [DETECTION_PROC] ✅ Parallel OCR processor initialized
2026-04-29 17:03:32,698 [INFO] 🔧 [DETECTION_PROC] Model loading process completed successfully
2026-04-29 17:03:32,698 [INFO] Detection models loaded successfully
2026-04-29 17:03:32,699 [INFO] Processing image: /home/camuser/aicamera/edge/captured_images/detection_20260428_180250_039.jpg
2026-04-29 17:03:36,672 [INFO] 🚗 Vehicles detected: 1 (filtered from 1)
2026-04-29 17:03:36,672 [INFO]   Vehicles detected: 1
2026-04-29 17:03:37,930 [INFO]   License plates detected: 1
2026-04-29 17:03:39,349 [INFO]   OCR results: 0
2026-04-29 17:03:39,350 [INFO] Static image detection test completed
2026-04-29 17:03:41,320 [WARNING] Neither CUDA nor MPS are available - defaulting to CPU. Note: This module is much faster with a GPU.
2026-04-29 17:03:47,651 [INFO] ✅ EasyOCR loaded successfully in 6.33 seconds
2026-04-29 17:03:47,651 [ERROR] Error during cleanup: cannot join current thread