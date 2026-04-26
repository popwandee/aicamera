# การทดสอบ E2E และ Debug — Edge → Server → บันทึก → แสดงบน Frontend

เอกสารนี้อธิบายขั้นตอนทดสอบการรับส่งข้อมูลจาก Edge ถึง Server จนบันทึกลง DB และแสดงบน frontend-app พร้อมแนวทาง Debug ฝั่ง Server และฝั่ง Edge (ให้ User ดำเนินการ)

---

## 1. สถานการณ์ทดสอบ (E2E)

| ลำดับ | ขั้นตอน | ฝั่ง Edge | ฝั่ง Server | ตรวจสอบผล |
|------|---------|-----------|-------------|------------|
| 1 | ลงทะเบียนกล้อง | ส่ง event `camera_register` หลังเชื่อมต่อ Socket.IO | ws-service รับ → เรียก backend-api POST `/server/api/cameras/register` | กล้องโผล่ใน **Edge Control** (`/server/edge_control`) และ **Network** (Live Edge Status) |
| 2 | ส่งผล detection (metadata) | ส่ง event `message` ด้วย `content.type === 'detection_result'` | ws-service รับ → เรียก backend-api สร้าง detection (+ ผูก image ถ้ามี) | รายการโผล่ใน **Detection Dashboard** (`/server/`) ตาราง Detections |
| 3 | ส่งภาพ | ส่ง event `image` (base64 + filename + camera_id) | ws-service บันทึกภาพที่ storage + อัปเดต detection.imagePath ผ่าน backend | ภาพแสดงใน Detection Dashboard (Images จาก Detections) และลิงก์ "ดูภาพ" ในตาราง |
| 4 | ส่งสถานะสุขภาพ | ส่ง event `health_status` | ws-service รับ → เรียก backend-api POST camera-health | **Edge Control** แสดงสถานะ green/yellow/red; หน้ารายละเอียดกล้องแสดง log Camera Health |

รูปแบบ payload จาก Edge ดูที่ `.cursor/plan.md` หรือ `server/ws-service/WEBSOCKET_CLIENT_GUIDE.md`

---

## 2. Debug ฝั่ง Server (ทีมพัฒนา)

### 2.1 ตรวจสอบ Services

```bash
systemctl status backend-api websocket mqtt
ss -tlnp | grep -E '3000|3001'
```

- backend-api ต้อง listen port 3000
- ws-service (websocket) ต้อง listen port 3001

### 2.2 ตรวจสอบ Nginx

- `location /server/api/` ต้องใช้ `proxy_pass http://127.0.0.1:3000/server/api/` (path เต็ม)
- `location /ws/` ต้อง proxy ไป `http://127.0.0.1:3001/ws/`

```bash
sudo nginx -t
# ดู config ที่โหลด
grep -A2 "server/api\|/ws/" /etc/nginx/sites-enabled/*
```

### 2.3 ตรวจสอบ ws-service

- **BACKEND_API_URL** ต้องรวม path: `http://localhost:3000/server/api` (ไม่ใช่แค่ `http://localhost:3000`)
- ดู log: `journalctl -u websocket.service -f`
- ตรวจว่า ws-service เรียก backend-api ได้: ดู log ว่ามี 404 หรือไม่

### 2.4 ตรวจสอบ Storage

- backend-api กับ ws-service ต้องใช้ **filesystem เดียวกัน** สำหรับโฟลเดอร์เก็บภาพ (เช่น `server/storage/`)
- ถ้า `GET /server/api/detections/:id/image` ไม่โหลดภาพ ได้ตรวจว่า `detection.imagePath` ชี้ไปที่ path ที่ backend อ่านได้

### 2.5 ตรวจสอบ DB

- หลัง Edge ส่ง camera_register → ตาราง `cameras` ต้องมีแถวใหม่
- หลังส่ง message (detection_result) → ตาราง `detections` มีแถวใหม่
- หลังส่ง health_status → ตาราง `camera_health` มีแถวใหม่

```bash
# ตัวอย่าง (ใช้ psql หรือ client อื่น)
psql -U lpruser -d aicamera_app -c "SELECT id, camera_id, name FROM cameras ORDER BY created_at DESC LIMIT 5;"
psql -U lpruser -d aicamera_app -c "SELECT id, camera_id, timestamp, license_plate FROM detections ORDER BY timestamp DESC LIMIT 5;"
```

---

## 3. ขั้นตอนฝั่ง Edge (แจ้ง User ดำเนินการ)

1. **เชื่อมต่อ WebSocket** ที่ `http://lprserver.tail605477.ts.net/ws/` (path `/ws/`) ด้วย Socket.IO client (เช่น Python `python-socketio`).
2. **ส่ง events ตามลำดับ:**
   - หลัง connect: ส่ง `camera_register` (camera_id, checkpoint_id, timestamp).
   - เมื่อมีผล detection: ส่ง `message` ด้วย content.type `detection_result` ตามรูปแบบใน WEBSOCKET_CLIENT_GUIDE.
   - ถ้ามีรูป: ส่ง `image` (data base64, filename, camera_id).
   - เป็นระยะ: ส่ง `health_status` (type, aicamera_id, status, timestamp ฯลฯ).
3. **ตรวจ log ฝั่ง Edge** ว่าส่งสำเร็จและไม่มี error; ตรวจ response events จาก server (`message_saved`, `image_saved`, `message_error`, `image_error`).
4. **ตรวจผลบน Server:** เปิด `/server/` (Detection Dashboard), `/server/edge_control` (Edge Control), `/server/network` (Live Edge Status) ว่าข้อมูลและภาพโผล่ตรงกับที่ส่ง

---

## 4. สรุปผลการทดสอบ (Template)

เมื่อทดสอบเสร็จแล้ว กรอกสรุปในส่วนนี้หรือในเอกสารแยก:

| สถานการณ์ | วันที่ทดสอบ | ผล (สำเร็จ/ล้มเหลว) | หมายเหตุ / จุดที่ Debug |
|------------|-------------|----------------------|---------------------------|
| 1. camera_register | | | |
| 2. message (detection_result) | | | |
| 3. image | | | |
| 4. health_status | | | |

**คำแนะนำการทดสอบซ้ำ:** รัน Services ตามลำดับ (Nginx → backend-api → websocket → mqtt); ตรวจ BACKEND_API_URL และ storage path; ฝั่ง Edge ใช้ URL ผ่าน Nginx เท่านั้น (ไม่เปิด port 3001 ภายนอก).

---

## 5. อ้างอิง

- [DEVELOPER_HANDBOOK.md](DEVELOPER_HANDBOOK.md) — สถาปัตยกรรม, URL, แก้ปัญหา
- [../ws-service/WEBSOCKET_CLIENT_GUIDE.md](../ws-service/WEBSOCKET_CLIENT_GUIDE.md) — รูปแบบ events และตัวอย่าง Client
- [../mqtt-service/MQTT_CLIENT_GUIDE.md](../mqtt-service/MQTT_CLIENT_GUIDE.md) — MQTT topics (สำหรับ health/status ที่แสดงใน Edge Control)
- `.cursor/plan.md` — Payload samples จาก Edge
