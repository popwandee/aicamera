# Database aicamera_app (Edge WebSocket + MQTT)

ฐานข้อมูล `aicamera_app` ใช้รองรับข้อมูลจาก Edge ผ่าน WebSocket และ MQTT ต้องสร้างและรัน schema ด้วย superuser (postgres) จากนั้น grant สิทธิ์ให้ `lpruser` ใช้กับ backend-api

## สร้างฐานข้อมูลและรัน schema (รันครั้งเดียว)

ต้องมีสิทธิ์ sudo เพื่อรันคำสั่งเป็น user `postgres`:

```bash
cd /home/devuser/aicamera
./server/database/init-aicamera-app.sh
```

หรือรันทีละขั้นด้วยตัวเอง:

```bash
# 1. สร้าง database
sudo -u postgres psql -c "CREATE DATABASE aicamera_app OWNER postgres ENCODING 'UTF8';"

# 2. รัน schema
sudo -u postgres psql -d aicamera_app -f /home/devuser/aicamera/server/database/schema.sql

# 3. Grant สิทธิ์ให้ lpruser
sudo -u postgres psql -d aicamera_app -f /home/devuser/aicamera/server/database/grant-lpruser.sql
```

## ตั้งค่า backend-api

ตั้งค่า environment ให้ชี้ไปที่ `aicamera_app`:

```bash
export DATABASE_URL="postgresql://lpruser:YOUR_PASSWORD@localhost:5432/aicamera_app"
```

หรือคัดลอก `server/backend-api/.env.example` เป็น `.env` แล้วแก้รหัสผ่าน จากนั้นรัน backend-api

## ข้อมูลตัวอย่าง (Seed)

หลังรัน schema และ grant แล้ว ถ้าต้องการใส่ข้อมูลตัวอย่างเพื่อออกแบบ UI หรือทดสอบ แสดงผลทุกตารางใน Dashboard:

```bash
sudo -u postgres psql -d aicamera_app -f /home/devuser/aicamera/server/database/seed-sample-data.sql
```

ไฟล์ `seed-sample-data.sql` จะใส่ข้อมูลตัวอย่างในตาราง cameras (ถ้ายังไม่มี), detections, analytics, camera_health, system_events, visualizations, analytics_events โดยอ้างอิง cameras ที่มีอยู่แล้ว

## Migration (ตารางที่มีอยู่แล้ว)

ถ้าสร้าง DB มาก่อนที่ schema จะมีคอลัมน์ `archived` / `archived_at` ในตาราง `detections` หรือเมื่อเกิดอาการดังนี้:

- **GET /server/api/detections คืน 500** และใน log ของ backend-api มีข้อความ **column d.archived does not exist** (PostgreSQL error code 42703)

ให้รัน migration ครั้งเดียว:

```bash
sudo -u postgres psql -d aicamera_app -f /home/devuser/aicamera/server/database/migrations/add_detections_archived.sql
```

จากนั้นรีสตาร์ท backend-api: `sudo systemctl restart backend-api` (หรือ restart process ที่รัน backend-api)

- Schema ปัจจุบัน (schema.sql) มีคอลัมน์นี้แล้ว — ถ้าสร้าง DB ใหม่ด้วย `init-aicamera-app.sh` ไม่ต้องรัน migration
- รายละเอียดเพิ่มเติมและ checklist สำหรับ developer ที่รับงานต่อ: ดู [DEVELOPER_HANDBOOK.md](../docs/DEVELOPER_HANDBOOK.md) §4.7 และ §6.3

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | คำอธิบาย |
|------|----------|
| schema.sql | โครงสร้างตาราง, enum, view, function (รองรับ WebSocket + MQTT) |
| grant-lpruser.sql | GRANT สิทธิ์ให้ lpruser (รันหลัง schema ด้วย postgres) |
| init-aicamera-app.sh | สคริปต์รวม: สร้าง DB + รัน schema + รัน grant (ต้อง sudo) |
| seed-sample-data.sql | ข้อมูลตัวอย่างสำหรับทุกตาราง (รันหลัง schema; ใช้สำหรับออกแบบ UI และทดสอบ) |
| migrations/add_detections_archived.sql | เพิ่มคอลัมน์ archived, archived_at ใน detections (สำหรับ DB ที่มีอยู่แล้ว) |



. หยุด process ที่ใช้พอร์ต 3000 แล้วรัน backend ใหม่ (แนะนำ)
ดูว่า process ไหนใช้พอร์ต 3000:
ss -tlnp | grep 3000
หรือ

```bash
sudo lsof -i :3000

```
หยุด process นั้น:
ถ้าเป็น backend-api ตัวเก่า: หา PID จากคำสั่งด้านบน แล้ว kill <PID>
หรือถ้ารันด้วย systemd: sudo systemctl stop backend-api (หรือชื่อ service จริง)
จากนั้นรัน backend ใหม่:

```bash
export DATABASE_URL="postgresql://lpruser:YOUR_PASSWORD@localhost:5432/aicamera_app"
```

Run Backend
```bash
cd /home/devuser/aicamera/server/backend-api && npm run start
```
. Backend-api (port 3000)
ติดตั้ง @nestjs/serve-static และตั้งค่าให้เสิร์ฟ frontend จาก ../frontend-app/dist ที่ path /server (ไฟล์จาก app.module.ts)
ตั้ง global prefix เป็น server/api ใน main.ts ดังนั้น API อยู่ที่ http://localhost:3000/server/api/cameras, /server/api/detections ฯลฯ
Redirect จาก / ไป /server/ เพื่อให้เปิด http://localhost:3000 แล้วไปที่หน้า dashboard โดยอัตโนมัติ
2. Frontend
Build แล้ว ใช้ publicPath /server/ อยู่แล้ว และใช้ API base เป็น origin + '/server/api' ดังนั้นเมื่อเปิดผ่าน port 3000 จะเรียก API ถูกที่โดยไม่ต้องแก้ frontend
วิธีใช้งาน
ให้มี frontend build :
```bash
   cd /home/devuser/aicamera/server/frontend-app && npm run build
```
รัน backend-api (จากโฟลเดอร์ server/backend-api เพื่อให้ process.cwd() ชี้ไปที่ถูกที่):
```bash
   cd /home/devuser/aicamera/server/backend-api && npm run start
```
เปิดในเบราว์เซอร์
เปิด http://localhost:3000 จะถูก redirect ไป http://localhost:3000/server/
หรือเปิดตรง http://localhost:3000/server/
จะเห็น Detection Dashboard พร้อม:
สถานะ Backend API / WebSocket
ส่วน Images (จาก detections ที่มี image_path)
ตาราง: Cameras, Detections, Camera Health, Analytics, System Events, Visualizations, Analytics Events (ทุกคอลัมน์และ record ที่ API ส่งกลับ)
หมายเหตุ: Backend ต้องรันจาก server/backend-api เพื่อให้ path ../frontend-app/dist ชี้ไปที่โฟลเดอร์ build ของ Vue จริง ถ้ารันจากที่อื่นอาจต้องปรับ frontendDist ใน app.module.ts