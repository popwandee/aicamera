# ผลการตรวจสอบ Backend และ Database (ข้อ 2)

## สรุปผล (อัปเดตล่าสุด)

- **Backend API**: ตอบสนองได้ — `GET http://127.0.0.1:3000/` คืน `200` และข้อความ "Hello World!"
- **Database**: มี schema ที่ `server/database/schema.sql` (PostgreSQL). **backend-api มีการเชื่อมต่อฐานข้อมูลแล้ว** ผ่าน TypeORM — ใช้ env `DATABASE_URL` หรือ `POSTGRES_*`; `synchronize: false`; มี entities ตรงกับ schema และ REST endpoints สำหรับ cameras, detections, camera_health, camera_summary, update_daily_analytics. รายละเอียดผลการดำเนินการอยู่ที่ [server/docs/BACKEND_POSTGRESQL_PROGRESS.md](server/docs/BACKEND_POSTGRESQL_PROGRESS.md).

## รายละเอียด

### Backend (NestJS, port 3000)

- Systemd: `backend-api.service` active
- Port 3000 ฟังอยู่
- Nginx proxy: `/server/api/` → `http://127.0.0.1:3000/`
- โมดูล: AuthModule, DeviceModule; TypeORM เชื่อมต่อ PostgreSQL; DeviceService ให้บริการ CRUD cameras, detections, camera_health และเรียก view/function

### Database

- Config: ใช้จากภายในเครื่องเท่านั้น (ไม่ expose DB ออกภายนอก); ตั้งค่าใน env ตาม `server/backend-api/.env.example`
- REST ที่เกี่ยวข้อง: `GET/POST /cameras`, `GET/POST /detections`, `GET /cameras/summary`, `GET /camera-health`, `POST /camera-health` ฯลฯ (path ผ่าน Nginx เป็น `/server/api/...`)

## การตรวจสอบที่ใช้

- รัน `server/scripts/verify_services.sh` — ข้อ 3 Backend API (3000) ได้ [OK] GET / => 200
- เมื่อตั้งค่า DB แล้ว: ทดสอบ `GET /server/api/cameras` (หรือ `GET http://127.0.0.1:3000/cameras`) เพื่อยืนยันการเชื่อมต่อและดึงข้อมูล
