# CLAUDE.md — Edge Module (aicamera)
> บริบทนี้สำหรับ Claude Code เพื่อเข้าใจ module `/edge` และแนวทางการพัฒนา
> อัปเดต: 2026-05-31

---

## 📌 บทบาทของ Module นี้

Module `/edge` ทำงานบน **Raspberry Pi 5 + Hailo 8 NPU** (aicamera1 / aicamera2)  
หน้าที่หลัก:
1. **ตรวจจับป้ายทะเบียน (LPR)** — ด้วย Hailo NPU + Tesseract OCR ที่ **30 FPS**
2. **ส่งข้อมูลและภาพ** ไปยัง Server ผ่าน WebSocket (Socket.IO) และ MQTT
3. **รายงานสถานะสุขภาพ** ของกล้อง (health, status) ทุก 60 วินาที

---

## 🌐 Network & Connectivity

| ปลายทาง | Protocol | URL / Topic |
|---------|----------|-------------|
| lprserver | Socket.IO | `http://lprserver.tail605477.ts.net/ws/` |
| lprserver MQTT | MQTT | `mqtt://lprserver.tail605477.ts.net:1883` |
| Tailscale VPN | — | ต้องเชื่อมต่อ Tailscale ก่อนเสมอ |

**Tailscale IPs:**
- lprserver: `100.95.46.128`
- aicamera1: `100.126.178.74`
- aicamera2: `100.110.20.53`

---

## 📡 WebSocket Events ที่ส่งไป Server

ใช้ Socket.IO connect ไปที่ `path: '/ws/'`

| Event | เมื่อไร | Payload หลัก |
|-------|---------|-------------|
| `camera_register` | เมื่อ connect ครั้งแรก | `{ camera_id, location, ip_address, ... }` |
| `message` | ตรวจพบป้าย | `{ camera_id, plate_number, confidence, timestamp }` |
| `image` | พร้อมกับ detection | `{ camera_id, detection_id, image_data (base64) }` |
| `health_status` | ทุก 60 วินาที | `{ camera_id, cpu_temp, cpu_usage, memory_usage, ... }` |

> **อ้างอิง payload เต็ม:** `server/ws-service/WEBSOCKET_CLIENT_GUIDE.md`

---

## 📶 MQTT Topics ที่ Publish

| Topic | ความถี่ | Payload |
|-------|---------|---------|
| `camera/{camera_id}/health` | ทุก 60 วิ | `{ cpu_temp, cpu_usage, memory_usage, disk_usage, uptime }` |
| `camera/{camera_id}/status` | เมื่อสถานะเปลี่ยน | `{ status: "online"/"offline", timestamp }` |
| `camera/{camera_id}/detections` | เมื่อตรวจพบ | `{ plate_number, confidence, timestamp }` |

> **อ้างอิง topics เต็ม:** `server/mqtt-service/MQTT_CLIENT_GUIDE.md`

---

## 🗂️ โครงสร้างไฟล์ที่สำคัญ

```
edge/
├── src/
│   ├── components/
│   │   ├── detection_processor.py    # Hailo inference pipeline + OCR orchestration
│   │   ├── ocr_queue_worker.py       # Async OCR Queue Worker (background thread)
│   │   ├── parallel_ocr_processor.py # Hailo OCR + ThaiLPROCR คู่ขนาน (sync fallback)
│   │   ├── thai_lp_ocr.py            # ThaiLPROCR — Tesseract wrapper
│   │   ├── camera_handler.py         # Camera capture @30 FPS, FrameDurationLimits
│   │   ├── health_monitor.py         # System health checks
│   │   └── database_manager.py       # SQLite local detection storage
│   ├── services/
│   │   ├── detection_manager.py      # Top-level service coordinator
│   │   └── websocket_sender.py       # Socket.IO client → lprserver
│   ├── core/
│   │   └── config.py                 # Settings from .env.production
│   └── web/
│       └── blueprints/               # Flask web UI blueprints
├── installation/
│   ├── .env.production               # ⚠️ ACTUAL env file (ไม่ใช่ edge/.env)
│   ├── venv_hailo/                   # Python venv (ใช้อันนี้เท่านั้น)
│   └── setup_env.sh                  # Environment setup
├── scripts/
│   └── setup_logrotate.sh            # Deploy logrotate + journald + cron บน device ใหม่
├── logs/
│   ├── aicamera.log                  # App log (rotated daily 00:01, keep 3)
│   ├── gunicorn_access.log           # Gunicorn access (rotated by logrotate daily, keep 7)
│   └── hailort.log                   # HailoRT library log
└── db/
    └── lpr_data.db                   # SQLite database
```

---

## ⚙️ Environment Variables

**ไฟล์จริง:** `edge/installation/.env.production` (ไม่ใช่ `edge/.env`)

```bash
# Server endpoints
WEBSOCKET_SERVER_URL=http://lprserver.tail605477.ts.net/ws/
SERVER_URL=http://lprserver.tail605477.ts.net/server/api
MQTT_BROKER_HOST=lprserver.tail605477.ts.net
MQTT_BROKER_PORT=1883

# Camera identity (ตั้งต่างกันในแต่ละ device)
# CRITICAL: AICAMERA_ID ต้องเป็น integer string "1" หรือ "2" เท่านั้น
AICAMERA_ID=1                    # 1=aicamera1  2=aicamera2
CAMERA_LOCATION="Main Entrance"
CAMERA_IP=100.126.178.74         # aicamera1=100.126.178.74  aicamera2=100.110.20.53

# Camera
CAMERA_FPS=30                    # ⚠️ ต้องตั้งไว้ — ถ้าไม่ตั้ง default=30 แต่ค่านี้ถูก override โดย .env.production

# Hailo model zoo
HEF_MODEL_PATH=@local
MODEL_ZOO_URL=/home/camuser/aicamera/resources

# Intervals (seconds)
HEALTH_SENDER_INTERVAL=60        # health_status WebSocket event
RECONNECT_DELAY=5
```

---

## 🔧 กฎการพัฒนา (Rules for Claude Code)

### ความปลอดภัย
- **ห้าม hardcode** credentials, IP จริง, หรือ camera_id ในโค้ด — ใช้ `.env.production` เสมอ
- `.env.production` ต้องอยู่ใน `.gitignore`

### WebSocket Client
- ต้อง connect ด้วย `path='/ws/'` (มี trailing slash)
- ส่ง `camera_register` ทันทีหลัง connect สำเร็จ
- Implement auto-reconnect ด้วย exponential backoff
- Handle disconnect gracefully — อย่าให้โปรแกรม crash

### MQTT Client
- QoS = 1 สำหรับ health/status topics
- Retain = True สำหรับ `camera/{id}/status`
- แยก connection สำหรับ MQTT และ WebSocket

### LPR / Hailo + Tesseract OCR
- อ่านโมเดลจาก `HEF_MODEL_PATH` เสมอ
- Confidence threshold ตั้งใน config ไม่ใช่ hardcode (vehicle: 0.8, plate: 0.5)
- OCR secondary engine คือ **Tesseract 5** (`ThaiLPROCR`) — ห้ามใช้ EasyOCR (download model ไม่เหมาะ edge) หรือ PaddleOCR (segfault ARM64)
- Thai OCR ชนะ Hailo OCR เฉพาะเมื่อ `validate_thai_plate()` คืน `valid=True` เท่านั้น
- ใช้ `venv_hailo` เสมอ: `edge/installation/venv_hailo/`

### Health Monitor
- `check_model_loading()` ใช้ `http://localhost/detection/status` (nginx port 80) — **ไม่ใช่ port 5000** (gunicorn bind ที่ Unix socket)
- SQLite `connection.commit()` ต้อง wrap ใน try/except — shared connection กับ `check_same_thread=False`

### Camera FPS
- ตั้ง `CAMERA_FPS=30` ใน `edge/installation/.env.production` ทุก device
- `camera_handler.py` ใช้ `FrameDurationLimits = (min_us, min_us)` — min==max เพื่อ fixed FPS
- ห้ามใช้ `min * 2` เพราะ ISP จะ drop เหลือ 15 fps ในแสงน้อย

### Logging
- Log ไฟล์อยู่ที่: `edge/logs/aicamera.log` (ไม่ใช่ `/var/log/aicamera/`)
- Rotate ด้วย `TimedRotatingFileHandler` (00:01 daily, backupCount=3) สำหรับ app logs
- Gunicorn logs rotate ด้วย `/etc/logrotate.d/aicamera` (ระดับ OS)
- ไม่ใช้ `print()` ใน production — ใช้ `logger.debug()` แทน

---

## 🐛 การ Debug ที่ Edge

```bash
# SSH เข้า edge
ssh camuser@aicamera1   # password: admin88366
ssh camuser@aicamera2   # password: admin88366

# ดู log แบบ real-time
tail -f /home/camuser/aicamera/edge/logs/aicamera.log

# ดู log ทั้งหมด (รวม DEBUG) ผ่าน journalctl
sudo journalctl -u aicamera_lpr -f

# ตรวจสอบ detection pipeline
curl http://localhost/detection/status | python3 -m json.tool

# ตรวจสอบ health ทั้งระบบ
curl http://localhost/health/system | python3 -c "
import sys,json; d=json.load(sys.stdin)
print('overall:', d['data']['overall_status'])
for k,v in d['data']['components'].items():
    print(f'  {k}: {v[\"status\"]}')
"

# ตรวจสอบ FPS
curl http://localhost/health/system | python3 -c "
import sys,json; d=json.load(sys.stdin)
cam=d['data']['components']['camera']
print('fps:', cam['average_fps'], '| streaming:', cam['streaming'])
"

# ทดสอบ WebSocket connection
python3 -c "import socketio; sio=socketio.Client(); sio.connect('http://100.95.46.128', socketio_path='/ws/')"

# ทดสอบ MQTT
mosquitto_pub -h 100.95.46.128 -t "camera/1/status" -m '{"status":"online"}'

# ตรวจสอบ Tailscale
tailscale status
tailscale ping lprserver

# ตรวจสอบ disk
df -h /
du -sh /home/camuser/aicamera/edge/logs/
journalctl --disk-usage

# Restart service
sudo systemctl restart aicamera_lpr.service
sudo systemctl status aicamera_lpr.service
```

---

## 🔗 ความสัมพันธ์กับ Module อื่น

```
[edge @30fps] ──WebSocket──▶ [server/ws-service] ──HTTP──▶ [server/backend-api] ──▶ PostgreSQL
[edge]        ──MQTT──────▶ [server/mqtt-service] ──HTTP──▶ [server/backend-api] ──▶ PostgreSQL
                                                                  ▲
[server/frontend-app] ──HTTP GET /server/api/ ─────────────────▶┘
```

> **สำคัญ:** ws-service ไม่ต่อ DB โดยตรง — เรียกผ่าน backend-api เท่านั้น

---

## 📚 เอกสารอ้างอิง

| เอกสาร | ตำแหน่ง |
|--------|---------|
| Pipeline architecture & decisions | `edge/CONTEXT.md` |
| WebSocket payload guide | `server/ws-service/WEBSOCKET_CLIENT_GUIDE.md` |
| MQTT topics guide | `server/mqtt-service/MQTT_CLIENT_GUIDE.md` |
| Developer Handbook | `server/docs/DEVELOPER_HANDBOOK.md` |

---

## 🔍 OCR Pipeline (Deployed — 2026-05-31)

### สถาปัตยกรรม (Async Queue — PRODUCTION)

| Stage | Model / Engine | เวลา |
|-------|---------------|------|
| Vehicle detection | `yolov8n_relu6_car--640x640` (Hailo via degirum) | ~14-31 ms/frame |
| Plate detection | `yolov8n_relu6_lp--640x640` (Hailo via degirum) | fast |
| Hailo OCR | `yolov8n_relu6_lp_ocr--256x128` (Hailo via degirum) | background |
| Thai OCR | `ThaiLPROCR` (Tesseract 5, `tha+eng`, PSM 11) | background |

OCR ทั้งหมดรันใน **background thread** ผ่าน `OcrQueueWorker` — main thread ไม่ถูก block

Thai OCR ชนะ **เฉพาะเมื่อ** `validate_thai_plate()` คืน `valid=True` เท่านั้น

### ไฟล์ OCR หลัก

| ไฟล์ | บทบาท |
|------|------|
| `src/components/ocr_queue_worker.py` | Background OCR thread, queue management |
| `src/components/thai_lp_ocr.py` | `ThaiLPROCR` — Tesseract wrapper, province matching |
| `src/components/parallel_ocr_processor.py` | Sync fallback (experiment/debug mode) |
| `src/components/detection_processor.py` | Orchestrates OCR queue submission |

### Device setup (ทั้ง 2 กล้อง — ทำแล้ว)

```bash
sudo apt install tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng
sudo wget -O /usr/share/tesseract-ocr/5/tessdata/tha.traineddata \
  https://github.com/tesseract-ocr/tessdata_best/raw/main/tha.traineddata
# ใน venv_hailo:
pip install pytesseract
```

### Key implementation notes

- **PSM 11** (sparse text) — ดีที่สุดสำหรับป้ายไทย; PSM 6/7 miss เพราะ border noise
- `validate_thai_plate()` ใช้ `re.search()` (ไม่ใช่ `.match()`) — PSM 11 มี noise prefix
- Province matching strip vowels ล่าง (`ุ ู ิ ี ั ็`) ก่อนเปรียบเทียบ — Tesseract มักตัดออก
- Plate crop upscale ถึง 300px height ก่อน Tesseract (LSTM ต้องการ high-res)
- `ThaiLPROCR.__init__` รับ `logger=` keyword

### Deployment status

| กล้อง | สถานะ | FPS | Health |
|-------|--------|-----|--------|
| aicamera1 | ✅ Running | 30.01 | healthy |
| aicamera2 | ✅ Running | 29.98 | healthy |

---

## 🖥️ System Health & Disk Management

### logrotate (`/etc/logrotate.d/aicamera`)
- `gunicorn_access/error.log` — daily, keep 7, compress, USR1 signal to gunicorn
- `hailort.log` — weekly, keep 2, copytruncate
- Deploy script: `bash edge/scripts/setup_logrotate.sh`

### journald limit (`/etc/systemd/journald.conf.d/aicamera-size.conf`)
```
SystemMaxUse=200M
RuntimeMaxUse=50M
```

### cron (`/etc/cron.d/aicamera-cleanup`)
- 03:00 daily: ลบ `/tmp/chromium-kiosk/BrowserMetrics/` เก่ากว่า 1 วัน
- 03:30 Sunday: เก็บ `hailort_backup_*.log` ไว้ 3 ไฟล์ล่าสุด

> **สาเหตุ:** Chromium kiosk สะสม BrowserMetrics ใน /tmp ไม่จำกัด — พบ 26 GB บน aicamera1 จนดิสก์เต็ม 100%
