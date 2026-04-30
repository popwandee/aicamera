# แผนงานระยะต่อไป — AI Camera LPR System

**โครงการ:** AI Camera LPR Research Project  
**ผู้จัดทำ:** PWD Vision Works  
**วันที่:** 2026-04-27  
**สถานะ Phase ปัจจุบัน:** Phase A–I (Dashboard) + Phase 1–6 (Test/Debug) ✅ เสร็จสมบูรณ์  

---

# ส่วนที่ 1: แผนการ Data Backup & Cleanup (Phase 7)

## ที่มาและเหตุผล

จากการทดสอบระบบในช่วงที่ผ่านมา พบว่า:
- ภาพที่บันทึกในฐานข้อมูล **มีทั้งภาพยานพาหนะจริงและภาพ noise** (false detection, object ที่ไม่ใช่ยานพาหนะ)
- ป้ายทะเบียนบางส่วน **อ่านไม่ได้หรืออ่านผิด** เนื่องจากสภาพแสง มุมกล้อง หรือ model limitation
- ข้อมูลในฐานข้อมูลเป็น **ข้อมูลทดสอบ** ไม่เหมาะนำมาใช้เป็น baseline สำหรับการทดสอบจริง

**เป้าหมาย:**
1. Backup ภาพทั้งหมดเพื่อคัดแยก ภาพยานพาหนะจริงนำไปสร้าง dataset สำหรับ train model
2. Clean ข้อมูลทดสอบออกจาก lprserver — Reset เป็น fresh state
3. Clean aicamera2 — ลบ scripts ทดสอบ ไฟล์เก่า ข้อมูลที่ไม่จำเป็น

---

## 1.1 Backup ภาพจาก aicamera2

### วัตถุประสงค์
- เก็บรักษาภาพทุกใบก่อน cleanup
- แยกเป็น 2 กลุ่ม: ยานพาหนะจริง (ใช้ทำ dataset) และ noise (ลบทิ้ง)

### ขั้นตอน

**Step 1: ตรวจสอบภาพที่มีบน aicamera2**
```bash
ssh camuser@100.110.20.53
# ตรวจสอบ path ที่เก็บภาพ
find /home/camuser/aicamera -name "*.jpg" -o -name "*.png" | head -50
du -sh /home/camuser/aicamera/edge/logs/ 2>/dev/null
du -sh /home/camuser/aicamera/edge/manual_capture/ 2>/dev/null
ls /home/camuser/aicamera/edge/src/ 2>/dev/null
```

**Step 2: Backup ภาพทั้งหมดจาก aicamera2 → lprserver → Mac**
```bash
# บน Mac: rsync ภาพจาก aicamera2 (ผ่าน Tailscale)
mkdir -p ~/aicamera_backup/aicamera2_raw_images/$(date +%Y%m%d)
rsync -avz --progress \
  camuser@100.110.20.53:/home/camuser/aicamera/edge/ \
  ~/aicamera_backup/aicamera2_raw_images/$(date +%Y%m%d)/ \
  --include="*.jpg" --include="*.png" --include="*/" \
  --exclude="*"
```

**Step 3: Backup ภาพ detection จาก lprserver storage**
```bash
mkdir -p ~/aicamera_backup/lprserver_storage/$(date +%Y%m%d)
rsync -avz --progress \
  devuser@100.95.46.128:/home/devuser/aicamera/server/storage/ \
  ~/aicamera_backup/lprserver_storage/$(date +%Y%m%d)/
```

**Step 4: Backup database จาก lprserver**
```bash
ssh devuser@100.95.46.128
PGPASSWORD=admin88366 pg_dump -U lpruser -h 127.0.0.1 -p 5432 aicamera_app \
  > /home/devuser/aicamera_backup_$(date +%Y%m%d).sql
# Download มาที่ Mac
scp devuser@100.95.46.128:/home/devuser/aicamera_backup_*.sql ~/aicamera_backup/
```

---

## 1.2 คัดแยกภาพ (Image Triage)

### เกณฑ์การแยก

| ประเภท | เกณฑ์ | การจัดการ |
|-------|------|---------|
| **ยานพาหนะชัดเจน + ป้ายทะเบียนชัด** | มียานพาหนะ, plate visible, confidence > 0.85 | เก็บไว้ → Dataset A (train/fine-tune) |
| **ยานพาหนะชัดเจน + ป้ายทะเบียนไม่ชัด** | มียานพาหนะ, plate blur/partial | เก็บไว้ → Dataset B (augmentation) |
| **ยานพาหนะไม่ชัด / partial** | ยานพาหนะครึ่งคัน, เบลอมาก | พิจารณา → อาจใช้เป็น negative samples |
| **ไม่ใช่ยานพาหนะ (noise)** | background, สัตว์, คน, object อื่น | **ลบทิ้ง** |
| **ภาพเทสระบบ** | ภาพทดสอบ, ภาพตัวอย่าง, dummy data | **ลบทิ้ง** |

### เครื่องมือช่วยคัดแยก
```bash
# Script ง่ายๆ ดูภาพจาก database metadata
# ดูภาพที่ confidence ต่ำ (likely noise)
PGPASSWORD=admin88366 psql -U lpruser -h 127.0.0.1 -p 5432 aicamera_app \
  -c "SELECT id, licensePlate, confidence, imagePath, timestamp \
      FROM detections \
      WHERE CAST(confidence AS FLOAT) < 0.7 \
      ORDER BY timestamp DESC \
      LIMIT 100;"
```

---

## 1.3 Clean aicamera2

### สิ่งที่ต้อง Clean

**Log Files เก่า:**
```bash
ssh camuser@100.110.20.53
# ดู log ที่มี
ls -lh /home/camuser/aicamera/edge/logs/
# ลบ log เก่ากว่า 7 วัน
find /home/camuser/aicamera/edge/logs/ -name "*.log" -mtime +7 -delete
```

**Test Scripts และไฟล์ทดสอบ:**
```bash
# ตรวจสอบก่อน
ls /home/camuser/aicamera/
ls /home/camuser/aicamera/edge/
# ไฟล์ทดสอบที่ควรลบ (ยืนยันก่อน):
# - test_*.py, test_*.sh
# - *.bak
# - tmp_*, debug_*
find /home/camuser/aicamera -name "test_*.py" -not -path "*/venv*"
find /home/camuser/aicamera -name "*.bak"
```

**ภาพ detection เก่า (หลัง backup แล้ว):**
```bash
# หลังจาก backup แล้วเท่านั้น!
# ดู path ที่เก็บภาพ detection local บน aicamera2
find /home/camuser/aicamera -name "detection_*.jpg" | head -20
# ลบหลัง confirm backup
```

**Disabled services:**
```bash
# ตรวจสอบ
systemctl list-units --state=failed
systemctl status edge_detection.service
# service นี้ถูก disable แล้ว ไม่ต้องทำอะไร
```

---

## 1.4 Clean lprserver Database & Storage

### ⚠️ ทำ Backup ก่อนเสมอ (ดู Step 1.1 ด้านบน)

### Clean Database Tables

```sql
-- เชื่อมต่อ PostgreSQL
-- PGPASSWORD=admin88366 psql -U lpruser -h 127.0.0.1 -p 5432 aicamera_app

-- 1. ดูสถิติก่อน clean
SELECT 'cameras' as table_name, COUNT(*) FROM cameras
UNION ALL SELECT 'detections', COUNT(*) FROM detections
UNION ALL SELECT 'camera_health', COUNT(*) FROM camera_health
UNION ALL SELECT 'analytics', COUNT(*) FROM analytics
UNION ALL SELECT 'system_events', COUNT(*) FROM system_events
UNION ALL SELECT 'analytics_events', COUNT(*) FROM analytics_events;

-- 2. ลบ detections ทั้งหมด (ข้อมูลทดสอบ)
TRUNCATE TABLE detections CASCADE;

-- 3. ลบ camera_health ทั้งหมด
TRUNCATE TABLE camera_health CASCADE;

-- 4. ลบ analytics (จะ re-run หลัง clean)
TRUNCATE TABLE analytics CASCADE;
TRUNCATE TABLE analytics_events CASCADE;

-- 5. ลบ system_events เก่า
TRUNCATE TABLE system_events CASCADE;

-- 6. ลบ visualizations
TRUNCATE TABLE visualizations CASCADE;

-- 7. Reset cameras — เก็บเฉพาะที่จะใช้จริง
-- ตรวจสอบก่อน:
SELECT id, "cameraId", name, status FROM cameras;
-- ลบ test cameras ที่ไม่ต้องการ:
-- DELETE FROM cameras WHERE "cameraId" NOT IN ('aicamera2'); -- ปรับตามความต้องการ
-- หรือลบทั้งหมดแล้ว re-register:
-- TRUNCATE TABLE cameras CASCADE;

-- 8. ยืนยันหลัง clean
SELECT 'cameras' as table_name, COUNT(*) FROM cameras
UNION ALL SELECT 'detections', COUNT(*) FROM detections
UNION ALL SELECT 'camera_health', COUNT(*) FROM camera_health;
```

### Clean Storage Files

```bash
ssh devuser@100.95.46.128

# ดูขนาด storage
du -sh /home/devuser/aicamera/server/storage/
ls -la /home/devuser/aicamera/server/storage/aicamera2/ | head -20

# หลัง backup แล้ว ลบภาพทดสอบ:
# ⚠️ ยืนยัน backup ก่อน!
# rm -rf /home/devuser/aicamera/server/storage/aicamera2/*

# หรือลบเฉพาะไฟล์เก่า (เก่ากว่า N วัน):
# find /home/devuser/aicamera/server/storage/ -name "*.jpg" -mtime +30 -delete
```

### Clean Backup Files บน lprserver

```bash
# ลบ backup files ที่สร้างระหว่าง test/debug
find /home/devuser/aicamera/server/backend-api/src -name "*.bak" -delete
find /home/devuser/aicamera/server/mqtt-service/src -name "*.bak" -delete
ls /home/devuser/aicamera_backup_*.sql 2>/dev/null  # ดู DB backup
```

### Verification หลัง Clean

```bash
# ตรวจสอบ API หลัง clean
curl http://100.95.46.128/server/api/cameras | python3 -m json.tool
curl http://100.95.46.128/server/api/detections?limit=5 | python3 -m json.tool
# ตรวจสอบ Dashboard
# เปิด browser: http://100.95.46.128/server/
```

---

## 1.5 Dataset Preparation (หลัง cleanup)

### โครงสร้าง Dataset ที่ควรได้

```
aicamera_dataset/
├── vehicles/              ← ภาพยานพาหนะ + ป้ายชัด (Dataset A)
│   ├── car/
│   ├── truck/
│   └── motorcycle/
├── plates/                ← crop ป้ายทะเบียน (Dataset B)
│   ├── readable/          ← อ่านได้ + label
│   └── unreadable/        ← อ่านไม่ได้
├── noise/                 ← false detection (ไม่ใช้ train แต่เก็บ reference)
└── metadata.csv           ← filename, label, confidence, timestamp, camera
```

---
# Step 1 — Configure identity + location + fix duplicate keys
bash scripts/configure_camera.sh aicamera1
# → Will set AICAMERA_ID=1, CHECKPOINT_ID=1, correct SERVER_URL, restart service

# Step 2 — Sync metadata to DB
bash scripts/update_camera_api.sh              # pick aicamera1 from the list
# or with --from-env after configure:
bash scripts/update_camera_api.sh <uuid> --from-env

# Step 3 — Final readiness check
bash scripts/edge_health_check.sh aicamera1

# Step 4 — Full system verify (both cameras)
bash scripts/verify_system.sh

# ส่วนที่ 2: แผนการทดสอบภาคสนาม 2 ชั่วโมง (Phase 8 — Field Test)

## เป้าหมาย

ทดสอบระบบ AI Camera ในสภาพแวดล้อมจริงบนถนน เป็นเวลา **2 ชั่วโมง** เพื่อ:
- เก็บข้อมูลยานพาหนะจริงสำหรับประเมิน Detection Accuracy และ OCR Accuracy
- ทดสอบความเสถียรของระบบในสภาพแวดล้อมจริง
- เก็บ Dataset คุณภาพสูงสำหรับ fine-tuning model

---

## 2.1 การเตรียมการก่อนทดสอบ (Pre-Test Setup)

### A. การ Configuration กล้อง

**ก่อนออกสนาม — แก้ไขไฟล์ `.env.production` บน aicamera2:**

```bash
ssh camuser@100.110.20.53
nano /home/camuser/aicamera/edge/installation/.env.production
```

**พารามิเตอร์ที่ต้อง config สำหรับการทดสอบแต่ละครั้ง:**

```ini
# ===== CAMERA IDENTITY =====
AICAMERA_ID=2                           # รหัสกล้อง (ไม่เปลี่ยน สำหรับ aicamera2)
CHECKPOINT_ID=2                         # รหัส Checkpoint

# ===== CAMERA METADATA (กำหนดก่อนทดสอบ) =====
CAMERA_NAME=AI Camera ทดสอบ-1           # ชื่อกล้องที่แสดงใน Dashboard
CAMERA_LOCATION=ถนน____ กม.____ ขาเข้า # ชื่อจุดติดตั้ง (อธิบายทิศทาง)
CAMERA_LAT=__.__________                # Latitude (จาก Google Maps)
CAMERA_LNG=__.__________               # Longitude (จาก Google Maps)

# ===== SERVER CONNECTION =====
SERVER_URL=http://100.95.46.128
WEBSOCKET_SERVER_URL=http://100.95.46.128/ws/
MQTT_BROKER_HOST=100.95.46.128
MQTT_BROKER_PORT=1883

# ===== DETECTION CONFIG =====
# ปรับตามสภาพแสงและระยะห่าง
VEHICLE_CONF_THRESHOLD=0.75            # ลด threshold ถ้าตรวจจับได้น้อยเกิน
PLATE_CONF_THRESHOLD=0.60
OCR_CONF_THRESHOLD=0.70

# ===== IMAGE SETTINGS =====
IMAGE_QUALITY=85                       # JPEG quality (85 = balance size/quality)
HEALTH_SENDER_INTERVAL=60              # ส่ง health ทุก 60s (เพิ่ม frequency)
WEBSOCKET_RETRY_INTERVAL=30
```

**อัปเดต Camera metadata ผ่าน API (หลัง register แล้ว):**
```bash
# หา camera UUID ก่อน
curl http://100.95.46.128/server/api/cameras | python3 -m json.tool

# Update metadata
curl -X PUT http://100.95.46.128/server/api/cameras/{UUID} \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AI Camera ทดสอบ-1",
    "location": "ถนน____ กม.____",
    "locationLat": "__.__",
    "locationLng": "___.__"
  }'
```

### B. อุปกรณ์ที่ต้องเตรียม

| อุปกรณ์ | รายละเอียด | ตรวจสอบ |
|--------|-----------|---------|
| Raspberry Pi 5 (aicamera2) | พร้อม Hailo-8, IMX708 | ☐ |
| Power supply | 5V 5A USB-C | ☐ |
| Power bank / UPS | สำรองไฟ 20,000 mAh+ | ☐ |
| Tripod/bracket | สำหรับยึดกล้อง | ☐ |
| Mobile hotspot | สำรองเน็ต Tailscale | ☐ |
| Laptop/tablet | Monitor Dashboard real-time | ☐ |
| กล้องถ่ายรูป/มือถือ | บันทึกหลักฐานการติดตั้ง | ☐ |
| สมุดบันทึก | จดข้อสังเกต, ยานพาหนะที่ผ่านมา | ☐ |

### C. การตรวจสอบระบบก่อนออกสนาม

```bash
# บน lprserver — ตรวจสอบ services ทั้งหมด
ssh devuser@100.95.46.128
systemctl status backend-api websocket mqtt mosquitto nginx postgresql@15-main
# ควรได้ active (running) ทั้งหมด

# ทดสอบ API
curl http://localhost:3000/server/api/cameras
# ควรได้ JSON response

# บน aicamera2 — ตรวจสอบ service
ssh camuser@100.110.20.53
systemctl status aicamera_lpr
# ควรได้ active (running)

# ทดสอบ Tailscale connectivity
ping -c 3 100.95.46.128
# latency ควร < 100ms
```

---

## 2.2 การดำเนินการทดสอบภาคสนาม (On-site 2 Hours)

### Timeline ตารางเวลา

| เวลา | กิจกรรม | ผู้รับผิดชอบ |
|-----|---------|-----------|
| T-30 นาที | เดินทางถึงพื้นที่, สำรวจจุดติดตั้ง | ทีมทั้งหมด |
| T-20 นาที | ติดตั้ง tripod, ปรับมุมกล้อง | ช่างเทคนิค |
| T-15 นาที | เปิด power, รอ boot (~2 นาที) | ช่างเทคนิค |
| T-10 นาที | SSH เข้า aicamera2, ตรวจสอบ service | ผู้พัฒนา |
| T-5 นาที | เปิด Dashboard บน laptop | ผู้พัฒนา |
| T-0 | **เริ่มบันทึก** — จับเวลา 2 ชั่วโมง | ทั้งหมด |
| T+30 min | ตรวจสอบ Dashboard: detections สะสม | ผู้ดูแล |
| T+60 min | Mid-test review: ปรับ threshold ถ้าจำเป็น | ผู้พัฒนา |
| T+90 min | ตรวจสอบ storage, CPU temp | ผู้ดูแล |
| T+120 min | **สิ้นสุดการทดสอบ** | ทั้งหมด |
| T+130 min | Download CSV, สรุปข้อมูล, ถอนอุปกรณ์ | ทั้งหมด |

### การตรวจสอบระหว่างทดสอบ

**Real-time monitoring บน Dashboard:**
```
http://100.95.46.128/server/   ← Main Dashboard
http://100.95.46.128/server/detections  ← Detection list (live)
http://100.95.46.128/server/cameras     ← Camera health
```

**สิ่งที่ต้อง observe และจดบันทึก:**
- จำนวนยานพาหนะที่ผ่านมาจริง (นับด้วยตาหรือ counter)
- จำนวน detections ที่บันทึกได้ (จาก Dashboard)
- ป้ายทะเบียนที่อ่านได้ถูก / ผิด (สุ่มตรวจ 5-10 คัน)
- สภาพแสง (แดด, เมฆ, กลางวัน)
- ระยะห่างของยานพาหนะจากกล้อง
- ปัญหาที่พบ (กล้องหลุด, service crash, latency สูง)

**Monitor aicamera2 health:**
```bash
# ดู CPU temp, usage บน dashboard หรือ SSH
watch -n 5 "vcgencmd measure_temp && top -bn1 | grep 'Cpu(s)'"
```

### การ Calibrate ระหว่างทดสอบ (ถ้าจำเป็น)

```bash
# ถ้า false detection สูง — เพิ่ม threshold
ssh camuser@100.110.20.53
nano /home/camuser/aicamera/edge/installation/.env.production
# VEHICLE_CONF_THRESHOLD=0.80  (เพิ่มจาก 0.75)
sudo systemctl restart aicamera_lpr

# ถ้า miss detection สูง — ลด threshold
# VEHICLE_CONF_THRESHOLD=0.65
```

---

## 2.3 การสรุปและเก็บข้อมูลหลังทดสอบ (Post-Test)

**Export ข้อมูลจาก Dashboard:**
1. เปิด `/server/detections`
2. กด **CSV Export** → ดาวน์โหลดไฟล์ `detections-YYYY-MM-DD.csv`
3. บันทึก URL screenshot ของ Analytics Dashboard

**Backup ภาพจาก lprserver:**
```bash
rsync -avz devuser@100.95.46.128:/home/devuser/aicamera/server/storage/aicamera2/ \
  ~/field_test_$(date +%Y%m%d)/images/
```

**บันทึกสรุปการทดสอบ:**
```markdown
# Field Test Log — YYYY-MM-DD

## สภาพแวดล้อม
- สถานที่: ____
- เวลาเริ่ม: __ น.  เวลาสิ้นสุด: __ น.
- สภาพแสง: แดดจ้า / เมฆมาก / ร่ม
- ปริมาณการจราจร: หนาแน่น / ปานกลาง / เบาบาง
- ระยะห่างกล้อง-ถนน: ___ เมตร
- มุมกล้อง: ___ องศา

## ผลการทดสอบ
- ยานพาหนะผ่านมาทั้งหมด (นับ): ___
- Detections ที่บันทึกได้: ___
- ป้ายทะเบียนที่อ่านได้: ___
- ป้ายทะเบียนที่อ่านถูกต้อง (สุ่มตรวจ): ___/___

## ปัญหาที่พบ
- ____
```

---

# ส่วนที่ 3: แผนการทดสอบ ประเมินผล และปรับปรุง (Phase 9)

## 3.1 Metrics ที่จะวัด

### A. Detection Accuracy

| Metric | สูตรคำนวณ | เป้าหมาย |
|-------|---------|---------|
| **Vehicle Detection Rate** | (Detections ใน DB) / (ยานพาหนะจริงที่ผ่านมา) × 100% | ≥ 80% |
| **False Positive Rate** | (Non-vehicle detected) / (Total detections) × 100% | ≤ 10% |
| **Duplicate Rate** | (ยานพาหนะคันเดียวกัน บันทึกซ้ำ) / (Total detections) × 100% | ≤ 5% |

**วิธีวัด:**
- Ground truth: นับยานพาหนะจริงระหว่างทดสอบ
- นำ detection count จาก Dashboard มาเปรียบเทียบ
- สุ่มตรวจภาพ 20-30 ใบ ว่าเป็นยานพาหนะจริง

### B. OCR Accuracy

| Metric | สูตรคำนวณ | เป้าหมาย |
|-------|---------|---------|
| **Plate Detection Rate** | (Detections with plate) / (Total detections) × 100% | ≥ 70% |
| **OCR Accuracy (Character)** | (ตัวอักษรถูกต้อง) / (ตัวอักษรทั้งหมด) × 100% | ≥ 85% |
| **OCR Accuracy (Full Plate)** | (ป้ายที่อ่านได้ถูก 100%) / (ป้ายที่อ่านได้) × 100% | ≥ 70% |
| **Average Confidence** | mean(confidence) ของ detections ที่มีป้าย | ≥ 0.80 |

**วิธีวัด:**
- จาก CSV export: confidence column
- สุ่มตรวจ plate text กับป้ายจริงในภาพ (ImageViewer บน Dashboard)
- ใช้ Analytics Dashboard → Top Plates ดูความถี่ป้ายทะเบียน

### C. Network & System Performance

| Metric | วิธีวัด | เป้าหมาย |
|-------|-------|---------|
| **WebSocket Latency** | เวลา detect → บันทึกใน DB | ≤ 2 วินาที |
| **MQTT Latency (Health)** | เวลา push → ปรากฏใน Dashboard | ≤ 10 วินาที |
| **Service Uptime** | worker crash count / ชั่วโมง | 0 crashes/2h |
| **CPU Temperature** | vcgencmd measure_temp | ≤ 70°C |
| **CPU Usage** | top / Dashboard Edge Control | ≤ 85% |
| **Memory Usage** | free -h / Dashboard | ≤ 80% |
| **Storage Growth** | du ก่อนและหลัง | ≤ 500 MB/2h |
| **Tailscale Latency** | ping lprserver | ≤ 100ms |

### D. UX & Configuration Ease

| รายการประเมิน | เกณฑ์ | คะแนน (1-5) |
|-------------|------|-----------|
| ความง่ายในการ config `.env.production` | เข้าใจง่าย ไม่มี ambiguity | /5 |
| ความเร็วในการ deploy (ตั้งแต่ boot → ส่งข้อมูล) | < 5 นาที | /5 |
| ความชัดเจนของ Dashboard | เข้าใจได้ทันที ไม่ต้องอธิบาย | /5 |
| การ monitor real-time | สมบูรณ์ ครบถ้วน | /5 |
| การ export ข้อมูล (CSV) | ใช้งานได้ทันที | /5 |

---

## 3.2 เครื่องมือประเมินผล

### Dashboard Analytics ที่ใช้

| หน้า | ข้อมูลที่ดู |
|-----|---------|
| `/server/analytics` | Total detections, Avg confidence, 30-day chart, Heatmap |
| `/server/detections` | รายการ, CSV export, filter by confidence |
| `/server/cameras` | Health metrics: CPU, Temp, Memory |
| `/server/routes` | เส้นทางยานพาหนะ (ถ้ามี multi-camera) |

### SQL Queries สำหรับวิเคราะห์ผล

```sql
-- สรุปผลการทดสอบ
SELECT
  COUNT(*) AS total_detections,
  COUNT(CASE WHEN CAST(confidence AS FLOAT) >= 0.8 THEN 1 END) AS high_confidence,
  COUNT(CASE WHEN "licensePlate" IS NOT NULL AND "licensePlate" != '' THEN 1 END) AS with_plate,
  ROUND(AVG(CAST(confidence AS FLOAT))::numeric, 4) AS avg_confidence,
  MIN(timestamp) AS first_detection,
  MAX(timestamp) AS last_detection,
  EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp)))/60 AS duration_minutes
FROM detections
WHERE timestamp >= NOW() - INTERVAL '3 hours';

-- Distribution of confidence
SELECT
  CASE
    WHEN CAST(confidence AS FLOAT) >= 0.9 THEN '90-100%'
    WHEN CAST(confidence AS FLOAT) >= 0.8 THEN '80-90%'
    WHEN CAST(confidence AS FLOAT) >= 0.7 THEN '70-80%'
    ELSE '< 70%'
  END AS confidence_range,
  COUNT(*) AS count
FROM detections
GROUP BY confidence_range
ORDER BY confidence_range DESC;

-- Top license plates (duplicate check)
SELECT "licensePlate", COUNT(*) AS frequency
FROM detections
WHERE "licensePlate" IS NOT NULL AND "licensePlate" != ''
GROUP BY "licensePlate"
ORDER BY frequency DESC
LIMIT 20;
```

---

## 3.3 แนวทางการปรับปรุงหลังทดสอบ

### ถ้า Vehicle Detection Rate < 80%

- ลด `VEHICLE_CONF_THRESHOLD` (เช่น 0.75 → 0.65)
- ตรวจสอบ motion detection threshold
- ปรับมุมกล้องหรือระยะห่าง
- พิจารณาเพิ่ม preprocessing (contrast enhancement)

### ถ้า False Positive Rate > 10%

- เพิ่ม `VEHICLE_CONF_THRESHOLD` (เช่น 0.75 → 0.85)
- ปรับปรุง ROI (Region of Interest) ให้แคบลง
- เพิ่ม temporal filtering (ห้ามบันทึกถ้า track duration < X ms)

### ถ้า OCR Accuracy < 70%

- ปรับ pre-OCR image processing (contrast, sharpening)
- ลองเปลี่ยน OCR model
- เพิ่ม resolution ของ plate crop
- Collect ภาพที่ OCR ผิดสำหรับ fine-tuning

### ถ้า Worker SIGSEGV บ่อย (> 1 ครั้ง/2h)

- ลด batch size
- จำกัด Hailo memory allocation
- อัปเดต Hailo firmware
- พิจารณาลด inference frequency

### ถ้า CPU Temperature > 70°C

- ติดตั้ง heatsink หรือ fan
- ลด inference frequency
- Throttle camera fps

---

## 3.4 Dataset Preparation สำหรับ Model Fine-tuning

### Pipeline หลังเก็บ Dataset จากภาคสนาม

```
1. Export detections CSV + Download images
       ↓
2. Label Studio หรือ manual labeling
   - Vehicle bbox (x,y,w,h) ในภาพ original
   - Plate bbox
   - Plate text (ground truth)
   - Quality: clear/partial/unclear
       ↓
3. ตรวจสอบและแก้ไข OCR errors
   - เปรียบเทียบ system output vs. ground truth
       ↓
4. Split: train/val/test (70/15/15)
       ↓
5. Format conversion:
   - YOLO format (vehicle + plate detection)
   - Classification format (OCR ground truth)
       ↓
6. Fine-tune on Hailo-compatible format
   - ใช้ Hailo Model Zoo หรือ custom training
```

---

## 3.5 แผนทดสอบหลายรอบ (Iterative Testing)

| รอบ | เป้าหมาย | สิ่งที่เปลี่ยน |
|----|---------|-----------|
| **รอบ 1** (2h) | Baseline measurement | Config เริ่มต้น |
| **รอบ 2** (2h) | Threshold optimization | ปรับ conf threshold ตามผล รอบ 1 |
| **รอบ 3** (2h) | Multi-condition test | เวลากลางคืน หรือสภาพแสงต่าง |
| **รอบ 4** (4h) | Stability test | Full deployment, monitor stability |
| **รอบ 5** (8h+) | Production pilot | หลัง fine-tune model |

---

## สรุป Checklist ก่อนเริ่มแต่ละ Phase

### ✅ Phase 7 (Cleanup) — Checklist
- [ ] Backup ภาพ aicamera2 → Mac
- [ ] Backup storage lprserver → Mac
- [ ] Backup database lprserver → .sql file
- [ ] ตรวจสอบ backup integrity
- [ ] Clean detections, camera_health, analytics, system_events
- [ ] Clean storage files (หลัง backup confirm)
- [ ] Clean log files เก่าบน aicamera2
- [ ] ลบ test scripts บน aicamera2 (ระวัง!)
- [ ] Verify: API ยังทำงาน, Dashboard ยังโหลดได้

### ✅ Phase 8 (Field Test) — Checklist
- [ ] Config `.env.production` ครบ (ID, name, location, lat/lng)
- [ ] Restart aicamera_lpr service หลัง config
- [ ] ตรวจสอบ lprserver services ทั้งหมด active
- [ ] เตรียมอุปกรณ์ครบ (power, tripod, laptop)
- [ ] เปิด Dashboard ก่อนออกสนาม
- [ ] มีสมุดบันทึก/form สำหรับ ground truth
- [ ] กำหนด stop time ชัดเจน

### ✅ Phase 9 (Evaluation) — Checklist
- [ ] Export CSV จาก Dashboard
- [ ] Backup ภาพ field test จาก lprserver
- [ ] รวบรวม ground truth (ยานพาหนะจริง นับ manual)
- [ ] คำนวณ metrics ตาม 3.1
- [ ] สรุป improvements ที่จะทำ
- [ ] วางแผนรอบทดสอบถัดไป
