# คู่มือนักพัฒนา — Server (LPR / AI Camera)

เอกสารนี้สรุปโครงสร้างสถาปัตยกรรม โครงสร้างไฟล์ URL/credentials การ setup และ config การเริ่มระบบ และการแก้ปัญหาส่วน Server เพื่อให้สามารถกลับมาอ่านและพัฒนาต่อยอดได้

---

## 1. โครงสร้างสถาปัตยกรรม (ส่วน Server)

### 1.1 ไดอะแกรมโดยรวม

```mermaid
flowchart TB
  subgraph client [Client]
    Browser[Browser]
    Edge[Edge Client]
  end
  subgraph nginx [Nginx :80]
    Landing["/ → landing"]
    Frontend["/server/ → static"]
    API["/server/api/ → proxy"]
    WS["/ws/ → proxy"]
  end
  subgraph services [Services]
    Backend[backend-api :3000]
    WSService[ws-service :3001]
    MQTTService[mqtt-service]
  end
  subgraph data [Data]
    DB[(PostgreSQL)]
    Storage[storage/]
  end
  Browser --> Landing
  Browser --> Frontend
  Browser --> API
  Browser --> WS
  Edge --> WS
  Edge --> MQTTService
  API --> Backend
  WS --> WSService
  WSService --> Backend
  WSService --> Storage
  Backend --> DB
  Backend --> Storage
```

- **Nginx (port 80):** จุดเข้าเดียวจากภายนอก
  - `location = /` และ `location /` → Landing page จาก `server/landing/`
  - `location /server/` → ไฟล์ static จาก `server/frontend-app/dist/` (Vue SPA)
  - `location /server/api/` → proxy ไป `http://127.0.0.1:3000/server/api/`
  - `location /ws/` → proxy ไป `http://127.0.0.1:3001/ws/` (Socket.IO)
- **backend-api (port 3000):** REST API + TypeORM ต่อ PostgreSQL; global prefix `server/api`
- **ws-service (port 3001):** Socket.IO gateway ที่ path `/ws/` รับข้อมูลจาก Edge แล้วเรียก backend-api (HTTP) และบันทึกภาพที่ `storage/`
- **mqtt-service:** NestJS microservice ต่อ MQTT broker; subscribe topics จาก Edge; บันทึก `camera/+/health` และ `camera/+/status` ลง DB ผ่าน backend-api (cameras + camera_health) สำหรับ Edge Control; topics อื่น log ไฟล์

Config อ้างอิง:
- Nginx: [../nginx-lprserver.conf](../nginx-lprserver.conf)
- Backend: [../backend-api/src/main.ts](../backend-api/src/main.ts) (prefix `server/api`, port 3000)
- ws-service: [../ws-service/src/main.ts](../ws-service/src/main.ts) (port 3001)
- mqtt-service: [../mqtt-service/src/main.ts](../mqtt-service/src/main.ts) (MQTT_URL)

---

## 2. โครงสร้างไฟล์/โฟลเดอร์ส่วน Server

| โฟลเดอร์/ไฟล์ | คำอธิบาย |
|----------------|----------|
| `backend-api/` | NestJS REST API (port 3000), TypeORM ต่อ PostgreSQL, serve static frontend ที่ `/server` เมื่อรันตรง |
| `ws-service/` | NestJS WebSocket service (port 3001), Socket.IO path `/ws/`, รับ events จาก Edge → เรียก backend-api + บันทึกภาพที่ storage |
| `mqtt-service/` | NestJS MQTT microservice, subscribe topics จาก Edge; บันทึก health/status ลง DB ผ่าน backend-api; topics อื่น log อย่างเดียว |
| `frontend-app/` | Vue SPA, build → `dist/`, Nginx serve ที่ `/server/` |
| `database/` | สคริปต์สร้าง DB, schema, grant (schema.sql, init-aicamera-app.sh, grant-lpruser.sql) |
| `landing/` | หน้า Landing (index.html) ที่ `/` |
| `storage/` | โฟลเดอร์เก็บภาพจาก ws-service (และ log ข้อความที่ `receive_message.log` ระดับ server root) |
| `scripts/` | สคริปต์ทดสอบและตรวจสอบ (test_websocket_message.js, verify_services.sh ฯลฯ) |
| `systemd_service/` | systemd units: backend-api.service, websocket.service, mqtt.service |
| `docs/` | เอกสารรวมถึงคู่มือนี้ |

---

## 3. URL และ Credentials

### 3.1 URLs

| ประเภท | URL ตัวอย่าง | หมายเหตุ |
|--------|---------------|----------|
| Landing | `http(s)://<host>/` | ตัวอย่าง host: `localhost:3000` (dev ตรง backend), `lprserver.tail605477.ts.net` (ผ่าน Nginx 80) |
| Frontend (Dashboard) | `http(s)://<host>/server/` | Vue app |
| API base | `http(s)://<host>/server/api` | ใช้เป็น base สำหรับเรียก REST (cameras, detections, camera-health ฯลฯ) |
| WebSocket (Socket.IO) | `http(s)://<host>/ws/` | Path ของ Socket.IO คือ `/ws/` |

เมื่อรัน backend ตรงที่ port 3000 (ไม่มี Nginx): เปิด `http://localhost:3000` จะถูก redirect ไป `/server/` และ API อยู่ที่ `http://localhost:3000/server/api`. WebSocket ที่ localhost:3000 จะไม่ทำงานถ้าไม่มี proxy `/ws/` ไป 3001.

### 3.2 Ports

| บริการ | Port | หมายเหตุ |
|--------|------|----------|
| Nginx | 80 | จุดเข้าเดียวจากภายนอก |
| backend-api | 3000 | ภายในเครื่อง |
| ws-service | 3001 | ภายในเครื่อง, เปิดผ่าน Nginx ที่ `/ws/` เท่านั้น |
| PostgreSQL | 5432 | localhost หรือตาม POSTGRES_HOST |
| MQTT broker | 1883 | ตาม MQTT_URL |

### 3.3 Credentials และตัวแปร Environment

**ไม่ hardcode รหัสผ่านในเอกสารหรือใน repo.** ใช้เฉพาะตัวแปร environment:

- **Database (backend-api):**
  - `DATABASE_URL` — รูปแบบ `postgresql://USER:PASSWORD@HOST:PORT/DATABASE` (แนะนำใช้กับ `aicamera_app`)
  - หรือแยก: `POSTGRES_HOST`, `POSTGRES_USER` (default `postgres`), `POSTGRES_PASSWORD`, `POSTGRES_PORT` (default 5432), `POSTGRES_DB` (default `aicamera`)
  - User ตามที่ grant ใน [../database/grant-lpruser.sql](../database/grant-lpruser.sql) (เช่น `lpruser`). รหัสผ่านตั้งใน `.env` ของ backend-api เท่านั้น.
  - อ้างอิง: [../backend-api/src/app.module.ts](../backend-api/src/app.module.ts)

- **Backend API (จาก ws-service):**
  - `BACKEND_API_URL` — **ต้องชี้ไปที่ base ของ API รวม path** เช่น `http://localhost:3000/server/api` เพื่อให้ request ไปที่ `/server/api/cameras/register`, `/server/api/detections` ฯลฯ ถูกต้อง (backend ใช้ `setGlobalPrefix('server/api')`).
  - ค่า default ในโค้ดคือ `http://localhost:3000/server/api`; ถ้าไม่ตั้งและ backend รันที่ host อื่น ต้องตั้งให้ตรง.

- **Storage (ws-service):**
  - `STORAGE_ROOT` — path ระดับ server root (default คือ `process.cwd()/..`). ภาพบันทึกที่ `storage/` และ message log ที่ `receive_message.log` ภายใต้ root นี้.

- **MQTT (mqtt-service):**
  - `MQTT_URL` — เช่น `mqtt://localhost:1883` หรือ `mqtt://broker:1883`
  - `MQTT_RECEIVE_LOG` — path ไฟล์ log (default ใต้ server root: `mqtt_receive.log`)
  - ถ้า broker ใช้ username/password ต้องตั้งใน connection options ของ client (อ้างอิง [../mqtt-service/MQTT_CLIENT_GUIDE.md](../mqtt-service/MQTT_CLIENT_GUIDE.md))

ตัวอย่าง env ฝั่ง backend-api ดูที่ [../backend-api/.env.example](../backend-api/.env.example) (ไม่มีรหัสผ่านจริง).

---

## 4. การ Setup และ Config

### 4.1 Database

1. สร้างฐานข้อมูลและรัน schema (รันครั้งเดียว, ต้องมีสิทธิ์ sudo):
   ```bash
   cd /home/devuser/aicamera
   ./server/database/init-aicamera-app.sh
   ```
   หรือรันทีละขั้นตาม [../database/README-aicamera-app.md](../database/README-aicamera-app.md)
2. ตั้งค่า environment ของ backend-api ให้ชี้ไปที่ `aicamera_app`:
   ```bash
   export DATABASE_URL="postgresql://lpruser:YOUR_PASSWORD@localhost:5432/aicamera_app"
   ```
   หรือคัดลอก `.env.example` เป็น `.env` แล้วแก้รหัสผ่าน

**การตั้งค่า DATABASE_URL สำหรับ backend-api (รันด้วย systemd)**  
backend-api โหลด `.env` เองจากโฟลเดอร์ที่รัน (WorkingDirectory) ผ่าน `dotenv` — สร้างไฟล์ `.env` ในโฟลเดอร์ `server/backend-api/` (copy จาก `.env.example`) แล้วใส่ `DATABASE_URL=postgresql://lpruser:<รหัสผ่าน>@localhost:5432/aicamera_app`. หน่วย systemd ใน repo มี `EnvironmentFile=-/home/devuser/aicamera/server/backend-api/.env` ด้วย (ถ้าโหลดได้จะ override ค่าจาก .env). ถ้าไม่ตั้งค่านี้ backend จะ fallback เป็น user `postgres` และมักต่อ DB ไม่ได้ → API คืน 502; ดูวิธีแก้ละเอียดที่ §6.1.

### 4.2 Network (Nginx)

- ใช้ config ตัวอย่าง: [../nginx-lprserver.conf](../nginx-lprserver.conf)
- สิ่งที่สำคัญ:
  - `location /server/api/` ต้องใช้ `proxy_pass http://127.0.0.1:3000/server/api/` (ส่ง path เต็มไป backend)
  - `location /ws/` → `proxy_pass http://127.0.0.1:3001/ws/`
- ติดตั้งและ reload:
  ```bash
  sudo cp /home/devuser/aicamera/server/nginx-lprserver.conf /etc/nginx/sites-available/lprserver
  sudo ln -sf /etc/nginx/sites-available/lprserver /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx
  ```

### 4.3 WebSocket

- ws-service รันที่ port 3001; เปิดสู่ภายนอกผ่าน Nginx ที่ path `/ws/` เท่านั้น (ไม่ expose 3001 โดยตรง)
- ตั้ง `BACKEND_API_URL` (รวม `/server/api`) และ `STORAGE_ROOT` ถ้าไม่ใช้ default
- รูปแบบ topic/payload จาก Edge ดูได้ที่ [../ws-service/WEBSOCKET_CLIENT_GUIDE.md](../ws-service/WEBSOCKET_CLIENT_GUIDE.md)

### 4.4 MQTT

- รัน MQTT broker แยก (ถ้าต้องการ) แล้วตั้ง `MQTT_URL`, `MQTT_RECEIVE_LOG`
- รูปแบบ topic และ payload จาก Edge ดูได้ที่ [../mqtt-service/MQTT_CLIENT_GUIDE.md](../mqtt-service/MQTT_CLIENT_GUIDE.md)

**ให้ Edge เข้าถึง broker ผ่าน Tailscale (lprserver.tail605477.ts.net)**  
Broker ต้องฟังทุก interface (`0.0.0.0`) ไม่ใช่แค่ localhost. ใช้ Mosquitto แล้วตรวจดังนี้:

1. **Config:** ใน `/etc/mosquitto/mosquitto.conf` ต้องมี `listener 1883 0.0.0.0`. ไฟล์ใน `conf.d/` (เช่น `aicamera.conf`) อย่า override เป็น `127.0.0.1`.
2. **Process ที่ยึดพอร์ต:** init script ใช้ `CONFFILE=/etc/mosquitto/mosquitto.conf` (ดู `/etc/init.d/mosquitto`). ถ้า `ss -tlnp | grep 1883` ยังแสดง `127.0.0.1:1883` แปลว่ามี process อื่นยึด 1883 อยู่ (หรือรัน Mosquitto ด้วย config อื่น). หยุด service แล้วรัน `ss -tlnp | grep 1883` ถ้ายังมี process อยู่ให้ใช้ `sudo lsof -i :1883` หา PID แล้วจัดการ process นั้น จากนั้น `sudo systemctl restart mosquitto` แล้วตรวจอีกครั้ง — ควรเห็น `0.0.0.0:1883`.
3. **Edge:** บนเครื่อง Edge (เช่น aicamera1) ตั้ง `MQTT_BROKER_HOST=lprserver.tail605477.ts.net` ใน `.env.production` (ไม่ใช้ `localhost`) เพื่อให้เชื่อม broker บน server ผ่าน Tailscale.

### 4.5 Build ให้พร้อมทำงาน

ก่อนรัน service ต้อง build โปรเจกต์ที่ใช้ TypeScript/Node ให้ได้โฟลเดอร์ `dist/` (และ frontend ได้ `dist/` สำหรับ Nginx serve ที่ `/server/`).

**backend-api (จำเป็นสำหรับ API และ Frontend ผ่าน Nginx)**

```bash
cd /home/devuser/aicamera/server/backend-api
npm install
npm run build
```

- ผลลัพธ์อยู่ที่ `dist/` — systemd ใช้ `ExecStart=/usr/bin/node dist/main.js`
- ตั้ง `DATABASE_URL` (หรือแยก POSTGRES_*) ใน environment ของ service หรือ `.env` ก่อนรัน

**ws-service (WebSocket)**

```bash
cd /home/devuser/aicamera/server/ws-service
npm install
npm run build
```

- ผลลัพธ์อยู่ที่ `dist/` — systemd ใช้ `ExecStart=/usr/bin/node dist/main.js`
- ตั้ง `BACKEND_API_URL=http://localhost:3000/server/api` และ `STORAGE_ROOT` (ถ้าไม่ใช้ default) ใน environment

**mqtt-service (MQTT)**

```bash
cd /home/devuser/aicamera/server/mqtt-service
npm install
npm run build
```

- ผลลัพธ์อยู่ที่ `dist/` — systemd ใช้ `ExecStart=/usr/bin/node dist/main.js`
- ตั้ง `MQTT_URL` (และ optional อื่น) ใน environment

**frontend-app (สำหรับ Nginx serve ที่ /server/)**

```bash
cd /home/devuser/aicamera/server/frontend-app
npm install
npm run build
```

- ผลลัพธ์อยู่ที่ `dist/` — Nginx config ต้องชี้ `location /server/` ไปที่ path นี้ (เช่น `alias .../frontend-app/dist/`)
- ไม่มี process แยก; Nginx serve ไฟล์ static จาก `dist/` เท่านั้น

**สรุป:** หลังแก้โค้ด backend-api, ws-service หรือ mqtt-service ต้อง `npm run build` ใหม่แล้ว `sudo systemctl restart <service>`; หลังแก้ frontend ต้อง `npm run build` ใน frontend-app แล้ว reload Nginx ไม่จำเป็น (แค่ refresh หน้าเว็บ ถ้าไม่มี cache แรง).

### 4.6 ตรวจสอบฐานข้อมูลด้วย psql (PostgreSQL)

ใช้คำสั่งต่อไปนี้บน Terminal เพื่อตรวจสอบหลังบ้านว่า DB มีอยู่และมีข้อมูลตรงกับที่ Backend อ่าน (database `aicamera_app`, user `lpruser` ตามที่ใช้ใน `DATABASE_URL`).

**เชื่อมต่อเข้า session psql**

```bash
# เข้า database aicamera_app ด้วย user lpruser (จะถามรหัสผ่าน)
psql -U lpruser -d aicamera_app

# หรือระบุ host/port ถ้าไม่ใช่ localhost
psql -U lpruser -h localhost -p 5432 -d aicamera_app
```

**คำสั่งภายใน psql (หลังเข้าแล้ว)**

| วัตถุประสงค์ | คำสั่ง |
|--------------|--------|
| ดูรายการ database ทั้งหมด | `\l` |
| ดูตารางใน DB ปัจจุบัน | `\dt` |
| ดูโครงสร้างตาราง (เช่น cameras) | `\d cameras` |
| ออกจาก psql | `\q` |

**คำสั่ง SQL ตรวจข้อมูลหลัก (รันใน psql หรือส่งจาก shell ด้วย `-c`)**

```bash
# นับจำนวนแถวในตารางหลัก
psql -U lpruser -d aicamera_app -c "SELECT (SELECT count(*) FROM cameras) AS cameras, (SELECT count(*) FROM detections) AS detections, (SELECT count(*) FROM camera_health) AS camera_health;"

# ดูกล้องล่าสุด (id, camera_id, name)
psql -U lpruser -d aicamera_app -c "SELECT id, camera_id, name, status, created_at FROM cameras ORDER BY created_at DESC LIMIT 5;"

# ดู detection ล่าสุด
psql -U lpruser -d aicamera_app -c "SELECT id, camera_id, timestamp, license_plate, confidence FROM detections ORDER BY timestamp DESC LIMIT 5;"

# ดู camera_health ล่าสุด
psql -U lpruser -d aicamera_app -c "SELECT id, camera_id, timestamp, status, cpu_usage, memory_usage FROM camera_health ORDER BY timestamp DESC LIMIT 5;"
```

ถ้าเชื่อมต่อไม่ได้ (เช่น "password authentication failed") ให้ตรวจว่า user `lpruser` มีอยู่และรหัสผ่านตรงกับที่ใส่ใน `DATABASE_URL` ใน `server/backend-api/.env`. ถ้าไม่มี database `aicamera_app` ให้รัน `server/database/init-aicamera-app.sh` ตาม §4.1.

### 4.7 Schema และ Migration — ข้อกำหนดความสอดคล้อง

**หลักการ:** โครงสร้างตารางใน PostgreSQL ต้องตรงกับ TypeORM entities ใน backend-api (เช่น `server/backend-api/src/entities/*.entity.ts`). ถ้า entity มีคอลัมน์ที่ตารางยังไม่มี API จะ error (เช่น 500, รหัส 42703 column does not exist).

- **DB ใหม่:** ใช้ `schema.sql` ปัจจุบัน (มี `detections.archived`, `detections.archived_at` อยู่แล้ว). รัน `init-aicamera-app.sh` ตาม §4.1 แล้วไม่ต้องรัน migration.
- **DB ที่มีอยู่แล้ว (สร้างก่อนมีคอลัมน์ archived ใน detections):** ต้องรัน migration ที่เกี่ยวข้อง. รายการ migration ที่ใช้ในปัจจุบัน:

| ไฟล์ migration | เพิ่ม/แก้ไข | เมื่อใดต้องรัน |
|----------------|-------------|-----------------|
| `migrations/add_detections_archived.sql` | เพิ่มคอลัมน์ `archived`, `archived_at` ในตาราง `detections` | เมื่อ log backend แสดง **column d.archived does not exist** (รหัส 42703) หรือเมื่อ GET /detections คืน 500 จาก query นี้ |

**คำสั่งรัน migration (ครั้งเดียวต่อ DB):**

```bash
sudo -u postgres psql -d aicamera_app -f /home/devuser/aicamera/server/database/migrations/add_detections_archived.sql
```

จากนั้น `sudo systemctl restart backend-api` (หรือ restart process ที่รัน backend-api).

**Checklist สำหรับ developer ที่รับงานต่อ (หรือ clone repo ใหม่):**

1. ถ้า **สร้าง DB ใหม่** → รัน `./server/database/init-aicamera-app.sh` ตาม §4.1 (schema ปัจจุบันครบแล้ว).
2. ถ้า **ใช้ DB ที่มีอยู่แล้ว** และเกิด 500 จาก GET /detections หรือ log แสดง "column d.archived does not exist" → รัน migration ด้านบน (§4.7, §6.3).
3. หลังเพิ่มคอลัมน์/ตารางใน `schema.sql` หรือใน entity ใหม่ ต้องมี migration ใน `server/database/migrations/` สำหรับ DB ที่มีอยู่แล้ว และบันทึกในคู่มือนี้ (§4.7) และใน `server/database/README-aicamera-app.md` เพื่อไม่ให้เกิด conflict หรือลืมรัน.

---

## 5. เมื่อ Boot server ใหม่ หรือเริ่มระบบ

อ้างอิง [../systemd_service/README.md](../systemd_service/README.md). ลำดับที่แนะนำ:

### 5.1 ตรวจสอบสถานะหลัง Boot

หลังเปิดเครื่อง ตรวจว่า services ที่จำเป็นรันอยู่และ port ถูก listen:

```bash
# สถานะ service
sudo systemctl status nginx backend-api websocket mqtt

# ตรวจ port
ss -tlnp | grep -E ':80|:3000|:3001'
# คาดหวัง: 80 (nginx), 3000 (backend-api), 3001 (websocket)
```

- **Nginx (80):** ต้อง active; ถ้าไม่รัน → `sudo systemctl start nginx`
- **backend-api (3000):** ต้อง active; ถ้าไม่รัน → ตรวจ log `journalctl -u backend-api -n 50` (มักเป็น DATABASE_URL หรือ DB ไม่ขึ้น)
- **websocket (3001):** ต้อง active; ถ้าไม่รัน → ตรวจ `journalctl -u websocket -n 50`
- **mqtt (ไม่มี HTTP port):** ต้อง active ถ้าใช้ MQTT; ตรวจ `journalctl -u mqtt -n 50`

### 5.2 Build ที่จำเป็น (เมื่อโค้ดเปลี่ยนหรือครั้งแรก)

| สิ่งที่แก้ | สิ่งที่ต้องทำ |
|------------|----------------|
| โค้ด backend-api | `cd server/backend-api && npm run build` แล้ว `sudo systemctl restart backend-api` |
| โค้ด ws-service | `cd server/ws-service && npm run build` แล้ว `sudo systemctl restart websocket` |
| โค้ด mqtt-service | `cd server/mqtt-service && npm run build` แล้ว `sudo systemctl restart mqtt` |
| โค้ด frontend-app | `cd server/frontend-app && npm run build` (Nginx serve จาก dist/ ไม่ต้อง restart service) |

ถ้าเพิ่ง clone หรือยังไม่เคย build ให้รัน `npm install` แล้ว `npm run build` ในแต่ละโฟลเดอร์ตาม §4.5

### 5.3 Start services (เมื่อปิดอยู่หรือหลัง Boot)

```bash
# เปิด Nginx (จุดเข้าเดียวจากภายนอก)
sudo systemctl enable nginx
sudo systemctl start nginx

# ติดตั้ง systemd units (ครั้งเดียว)
sudo cp /home/devuser/aicamera/server/systemd_service/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# เปิด backend + ws + mqtt
sudo systemctl enable backend-api websocket mqtt
sudo systemctl start backend-api websocket mqtt
```

- **Frontend:** ไม่มี process แยก; ต้องมีโฟลเดอร์ `server/frontend-app/dist/` (จาก `npm run build`) แล้ว Nginx จะ serve ที่ `/server/` ตาม config

### 5.4 ลำดับการเริ่มทำงาน (สรุป)

1. **Nginx (port 80)** — เริ่มก่อนหรือพร้อมเครือข่าย
2. **PostgreSQL** — ต้องรันอยู่ก่อน backend-api (backend ต่อ DB ตอน start)
3. **backend-api, websocket, mqtt** — เริ่มหลัง network (และ DB) พร้อม
4. **Frontend** — ไม่มี service; ใช้ไฟล์จาก `frontend-app/dist/` ผ่าน Nginx

---

## 6. การแก้ปัญหาที่อาจเกิดขึ้น

| อาการ | สาเหตุที่พบบ่อย | วิธีตรวจ/แก้ |
|--------|------------------|----------------|
| **502 Bad Gateway** หรือ API status ไม่พร้อม, ทุกตารางใน /server/ แสดง Bad Gateway | (ก) backend-api ต่อ DB ไม่ได้ (password authentication failed) (ข) backend-api รันแล้วแต่ Nginx ไม่ได้ proxy ไป 3000 | (ก) ดู §6.1 — ตั้ง `DATABASE_URL` ใน `.env` แล้ว restart (ข) ดู §6.2 — ตรวจ Nginx config และ curl ทดสอบ backend |
| **Backend-api รันปกติ (active) แต่ Frontend ยัง Bad Gateway** | Nginx ใช้ config ที่ไม่มีหรือผิด `location /server/api/` หรือ path/alias ผิด | ดู §6.2 — ตรวจ site ที่ enable, ต้องมี `location /server/api/` และ `proxy_pass http://127.0.0.1:3000/server/api/` แล้ว reload nginx |
| API แสดง Not Found เมื่อเข้าผ่าน Nginx (เช่น lprserver) | Nginx ส่ง path ไม่ครบไป backend | ตรวจ `proxy_pass` สำหรับ `/server/api/` ต้องเป็น `http://127.0.0.1:3000/server/api/` (มี path `/server/api/` ด้วย) |
| WebSocket ไม่เชื่อมต่อที่ localhost:3000 | ไม่มี proxy `/ws/` เมื่อรัน backend อย่างเดียว | ใช้ Nginx proxy `/ws/` ไป 3001 หรือทดสอบ ws-service ที่ port 3001 โดยตรง |
| ข้อมูลจาก DB ไม่แสดงใน Dashboard | backend-api ไม่รัน หรือ DATABASE_URL ผิด หรือ Nginx proxy ผิด | ตรวจว่า backend-api รันและ `DATABASE_URL` ถูกต้อง; ตรวจ Nginx ตามข้อแรก |
| ws-service เรียก backend ไม่ถึง (404) | BACKEND_API_URL ไม่มี path `/server/api` | ตั้ง `BACKEND_API_URL=http://localhost:3000/server/api` (หรือ host จริงที่ backend รัน) |
| ภาพ detection ไม่โหลด | backend อ่านไฟล์จาก `detection.imagePath` ไม่ได้ | ให้ backend กับ ws-service ใช้ filesystem เดียวกัน (หรือ shared storage) สำหรับ `storage/` |
| **Detection แสดง Internal Server Error (500)** | (ก) Backend รับ request ไม่ถึงหรือ path ผิด (ข) Query/DB error ใน GET /detections (ค) ตาราง/ view ไม่มีหรือ schema ไม่ตรง | ดู §6.3 — ตรวจ log backend, Nginx proxy `/server/api/`, และ schema ตาราง `detections` |
| **Error ใน log: column d.archived does not exist (รหัส 42703)** | ตาราง `detections` ถูกสร้างจาก schema เก่าที่ยังไม่มีคอลัมน์ `archived`, `archived_at` | รัน migration ตาม §4.7 และ §6.3: `sudo -u postgres psql -d aicamera_app -f server/database/migrations/add_detections_archived.sql` แล้ว restart backend-api |
| MQTT ได้แค่ log ไม่เห็นใน Dashboard | mqtt-service ยังไม่เขียนลง DB | ปัจจุบันออกแบบให้ log อย่างเดียว; ดูแผนพัฒนาต่อ MQTT → DB ด้านล่าง |

### 6.3 แก้ Detection แสดง Internal Server Error (500)

เมื่อหน้า `/server/` ในส่วน **Detections** แสดงข้อความโหลดไม่สำเร็จหรือ "Internal Server Error" แปลว่า `GET /server/api/detections` คืนสถานะ 500.

**ขั้นตอนตรวจและแก้:**

1. **ตรวจว่า request ถึง backend และ path ถูก:**  
   บนเครื่อง server รัน `curl -s -w "\n%{http_code}" "http://127.0.0.1:3000/server/api/detections?limit=10"`. ถ้าได้ 500 แปลว่าปัญหาอยู่ที่ backend (ไม่ใช่ Nginx). ถ้าได้ 502 หรือ connection refused ดู §6.1, §6.2.

2. **ดู log ของ backend-api** เพื่อดู exception จริง:  
   `journalctl -u backend-api -n 50 --no-pager` หรือ `npm run start` แล้วเรียก API อีกครั้ง แล้วดู stack trace ใน console.

   **สาเหตุที่พบบ่อยและวิธีแก้:**

   | ข้อความใน log (หรือรหัส) | สาเหตุ | วิธีแก้ |
   |---------------------------|--------|--------|
   | **column d.archived does not exist** หรือ PostgreSQL error code **42703** (undefined_column) | ตาราง `detections` ยังไม่มีคอลัมน์ `archived`, `archived_at` (DB สร้างจาก schema เก่า หรือยังไม่รัน migration) | รัน migration ครั้งเดียว: `sudo -u postgres psql -d aicamera_app -f /home/devuser/aicamera/server/database/migrations/add_detections_archived.sql` จากนั้น `sudo systemctl restart backend-api` (ดู §4.7) |
   | ต่อ DB ไม่ได้ (เช่น password authentication failed) | `DATABASE_URL` ผิด หรือ DB ไม่ขึ้น | แก้ตาม §6.1 |
   | ตาราง `detections` หรือ view ไม่มี | ยังไม่รัน schema หรือรันไม่ครบ | รัน `server/database/init-aicamera-app.sh` หรือรัน schema.sql + grant-lpruser.sql ตาม §4.1; ถ้า DB มีอยู่แล้วแต่ขาดคอลัมน์ให้รัน migrations ตาม §4.7 |
   | Query parameter (sortBy/sortOrder) ผิดรูปแบบ | TypeORM สร้าง SQL ผิด | โค้ดล่าสุด validate แล้ว; อัปเดต backend-api หรือส่งเฉพาะ `sortBy=timestamp`, `sortOrder=DESC` |

3. **ตรวจ Nginx:** ถ้าเรียกผ่าน host จริง (เช่น `http://lprserver.tail605477.ts.net/server/api/detections`) แล้วได้ 500 ให้เรียกตรงที่ `http://127.0.0.1:3000/server/api/detections` บนเครื่อง server. ถ้าที่ localhost ได้ 200 แปลว่า Nginx ส่ง request ไป backend แล้ว แต่ backend อาจได้ request คนละแบบ (เช่น path ถูกตัด). ตรวจ `proxy_pass` ต้องเป็น `http://127.0.0.1:3000/server/api/` (มี path `/server/api/` ด้วย).

4. **หลังแก้:** รีสตาร์ท backend-api แล้วลองเปิดหน้า Detection อีกครั้ง.

### 6.1 แก้ 502 Bad Gateway / password authentication failed (backend-api)

ถ้า `systemctl status backend-api` แสดงข้อความ **password authentication failed** แปลว่า backend-api ต่อ PostgreSQL ไม่ได้เพราะ user/password หรือ database name ไม่ตรงกับที่ตั้งใน PostgreSQL.

**ขั้นตอนแก้:**

1. **สร้างไฟล์ `.env` ในโฟลเดอร์ backend-api** (ถ้ายังไม่มี):
   ```bash
   cd /home/devuser/aicamera/server/backend-api
   cp .env.example .env
   ```

2. **แก้ `.env`** — ใส่ค่าเชื่อมต่อ DB จริง (ใช้ user ที่มีสิทธิ์ต่อ DB `aicamera_app` ตามที่ grant ไว้):
   ```bash
   # ตัวอย่าง (แทน YOUR_PASSWORD ด้วยรหัสผ่านจริงของ lpruser)
   DATABASE_URL=postgresql://lpruser:YOUR_PASSWORD@localhost:5432/aicamera_app
   ```
   ถ้าใช้ user อื่นหรือ host/port อื่น ให้แก้ให้ตรงกับ PostgreSQL ของเครื่องนี้.

3. **ให้ systemd โหลด `.env`** — หน่วย backend-api ต้องมี `EnvironmentFile=-/home/devuser/aicamera/server/backend-api/.env`. ถ้าใช้ unit จาก repo [../systemd_service/backend-api.service](../systemd_service/backend-api.service) จะมีบรรทัดนี้แล้ว. ถ้าเคย copy ไป `/etc/systemd/system/` ตั้งแต่ก่อน ให้ copy ใหม่แล้ว daemon-reload:
   ```bash
   sudo cp /home/devuser/aicamera/server/systemd_service/backend-api.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

4. **Restart backend-api:**
   ```bash
   sudo systemctl restart backend-api
   ```

5. **ตรวจสอบว่าไม่มี error:**
   ```bash
   sudo systemctl status backend-api
   journalctl -u backend-api -n 30 --no-pager
   ```
   ถ้ายังมี "password authentication failed" ให้ตรวจว่า user ใน PostgreSQL กับรหัสผ่านใน `DATABASE_URL` ตรงกัน และมี DB `aicamera_app` (รัน schema ตาม [../database/README-aicamera-app.md](../database/README-aicamera-app.md) ถ้ายังไม่เคยสร้าง).

   **ถ้า log แสดง "password authentication failed for user \"postgres\""** แปลว่าแอปไม่ได้ใช้ `DATABASE_URL` จาก `.env` (จึง fallback เป็น user `postgres`). backend-api โหลด `.env` เองจากโฟลเดอร์ที่รัน (WorkingDirectory) ผ่าน `dotenv` — ให้ตรวจว่าใน `server/backend-api/.env` มีบรรทัด **ไม่ถูก comment** ว่า `DATABASE_URL=postgresql://lpruser:รหัสผ่าน@localhost:5432/aicamera_app` (ไม่มีช่องว่างหน้า/หลัง `=`, ชื่อตัวแปรต้องเป็น `DATABASE_URL`). แก้แล้ว `sudo systemctl restart backend-api`.

### 6.2 Backend-api รันปกติ แต่ Frontend ยัง Bad Gateway

ถ้า `systemctl status backend-api` แสดง **active (running)** แต่หน้าเว็บที่ `/server/`, `/server/developer`, `/server/network`, `/server/edge_control` ยังขึ้น Bad Gateway หรือ API status ไม่พร้อม แสดงว่า Nginx ไม่ได้ส่ง request ไปยัง backend ที่ port 3000 ถูกต้อง (มักเป็นเพราะ **site ที่ Nginx ใช้อยู่ไม่มีหรือผิด `location /server/api/`**).

**ขั้นตอนตรวจและแก้:**

1. **ตรวจว่า backend รับ request บนเครื่อง server ได้จริง:**
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/server/api/
   ```
   คาดหวังได้ 200 หรือ 301/302 (ไม่ใช่ 000 หรือ connection refused). ถ้าได้ 000 หรือ connection refused แปลว่า backend ไม่ listen ที่ 3000 — ตรวจ `ss -tlnp | grep 3000` และ log ของ backend-api.

2. **ตรวจว่า Nginx ใช้ config ไหนและมี proxy `/server/api/` หรือไม่:**
   ```bash
   ls -la /etc/nginx/sites-enabled/
   grep -A5 'location /server/api' /etc/nginx/sites-enabled/*
   ```
   ต้องมีบล็อก `location /server/api/` และภายในมี `proxy_pass http://127.0.0.1:3000/server/api/;`. ถ้าไม่มีหรือชี้ไป port อื่น แก้ config ที่ใช้ (เช่น [../nginx-lprserver.conf](../nginx-lprserver.conf)) แล้ว copy ไป site ที่ enable:
   ```bash
   sudo cp /home/devuser/aicamera/server/nginx-lprserver.conf /etc/nginx/sites-available/lprserver
   sudo ln -sf /etc/nginx/sites-available/lprserver /etc/nginx/sites-enabled/
   # ลบ symlink ของ config เก่าที่ไม่ต้องการ (ถ้ามีหลาย site)
   sudo nginx -t && sudo systemctl reload nginx
   ```

3. **ตรวจว่า Frontend ถูก serve จากโฟลเดอร์ที่ถูกต้อง:** ต้องมี `location /server/` ชี้ไป `server/frontend-app/dist/` (ใน config ใช้ `alias .../frontend-app/dist/;`). ถ้า path ผิด หน้า `/server/` อาจโหลดได้แต่เรียก `/server/api/` ไม่ถึง — แก้ตาม config ตัวอย่างแล้ว reload nginx.

4. **ทดสอบจาก browser หรือ curl ผ่าน Nginx:** บนเครื่อง server รัน `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/server/api/` (หรือใช้ host จริงที่เข้าเว็บ). คาดหวัง 200 หรือ 3xx ไม่ใช่ 502. ถ้ายัง 502 แปลว่า Nginx ยังไม่ส่งไป backend — ดู error log: `sudo tail -20 /var/log/nginx/error.log`.

**สรุป:** ให้ site ที่ Nginx enable มีทั้ง `location /server/` (alias ไป frontend dist) และ `location /server/api/` (proxy ไป `http://127.0.0.1:3000/server/api/`) ตรงกับ [../nginx-lprserver.conf](../nginx-lprserver.conf) แล้ว reload nginx.

---

## 7. สรุป Data Flow และสถานะความพร้อม

### 7.1 ไดอะแกรม Data Flow

```mermaid
flowchart LR
  subgraph edge [Edge]
    EdgeClient[Edge Client]
  end
  subgraph server [Server]
    WS[ws-service:3001]
    MQTT[mqtt-service]
    Backend[backend-api:3000]
    DB[(PostgreSQL)]
    Storage[storage/]
    Frontend[Frontend /server/]
  end
  EdgeClient -->|Socket.IO /ws/| WS
  EdgeClient -->|MQTT topics| MQTT
  WS -->|HTTP REST| Backend
  WS --> Storage
  Backend --> DB
  Backend -->|read image| Storage
  Frontend -->|/server/api| Backend
```

### 7.2 สถานะตามช่องทาง

| ช่องทาง | การรับข้อมูล | การบันทึก DB | การเก็บภาพ/storage | การแสดงผล Frontend |
|--------|----------------|-------------|---------------------|----------------------|
| **WebSocket** | สมบูรณ์: events.gateway.ts รับ `camera_register`, `message`, `image`, `health_status` | สมบูรณ์: ผ่าน BackendApiService เรียก backend-api → PostgreSQL | สมบูรณ์: StorageService บันทึกภาพที่ `storage/` และ log ที่ `receive_message.log` | สมบูรณ์: backend-api serve cameras, detections, detections/:id/image; ServerHome.vue ดึงแสดง |
| **MQTT** | สมบูรณ์: subscribe camera/+/status, health, detections, system/events, system/health | **camera/+/health และ camera/+/status:** mqtt-service เรียก BackendApiService → backend-api → cameras + camera_health; topics อื่นยัง log อย่างเดียว | ไม่มี | camera_health จาก MQTT แสดงใน **Edge Control** (`/server/edge_control`, `/server/edge_control/camera/:id`) ผ่าน API `GET /server/api/cameras/edge-status` |

**สรุป:** Flow ผ่าน WebSocket สมบูรณ์ (Edge → ws-service → backend-api → DB + storage → frontend). Flow ผ่าน MQTT สำหรับ health/status สมบูรณ์ (Edge → mqtt-service → backend-api → DB) และแสดงใน Edge Control; topics อื่นยังรับและ log เท่านั้น.

### 7.3 คำแนะนำการทดสอบจาก Edge

- **WebSocket:** ใช้ [../ws-service/WEBSOCKET_CLIENT_GUIDE.md](../ws-service/WEBSOCKET_CLIENT_GUIDE.md)
  - เชื่อมต่อที่ `http(s)://<server>/ws/`
  - ส่ง `camera_register`, `message` (รวม `content.type === 'detection_result'`), `image`, `health_status` ตามรูปแบบที่ gateway รองรับ
  - ตรวจจาก UI ว่า camera / detection / health โผล่และภาพจาก `/server/api/detections/:id/image` แสดงได้
- **MQTT:** ใช้ [../mqtt-service/MQTT_CLIENT_GUIDE.md](../mqtt-service/MQTT_CLIENT_GUIDE.md)
  - Publish ไป topic `camera/<id>/status`, `camera/<id>/health` → mqtt-service จะลงทะเบียน camera และ POST camera-health ไป backend-api; ตรวจจาก **Edge Control** (`/server/edge_control`) ว่ากล้องและสถานะโผล่ และจาก log `mqtt_receive.log`
  - Topics อื่น (detections, system/events, system/health) ยังรับและ log อย่างเดียว

**หมายเหตุ:** ภาพจาก detection ต้องให้ backend กับ ws-service ใช้ storage ร่วมกัน (path เดียวกันหรือ shared volume) เพื่อให้ `GET /server/api/detections/:id/image` อ่านไฟล์ได้

**การทดสอบ E2E และ Debug:** ดู [E2E_TEST_AND_DEBUG.md](E2E_TEST_AND_DEBUG.md) — สถานการณ์ทดสอบ Edge → Server → บันทึก → แสดงบน frontend, ขั้นตอน Debug ฝั่ง Server, ขั้นตอนฝั่ง Edge (แจ้ง User), และ template สรุปผล

---

## 8. MQTT → DB (สถานะ)

- **ทำแล้ว:** `camera/+/health` และ `camera/+/status` — mqtt-service เรียก BackendApiService (HTTP) ไป backend-api เพื่อลงทะเบียน camera และ POST camera-health; แสดงใน Edge Control (`/server/edge_control`). backend-api มี Cron ลบ `camera_health` อายุเกิน 30 วัน (`CameraHealthCleanupService`, รันทุกวันเที่ยงคืน).
- **ยังไม่ทำ:** topics อื่น (เช่น `camera/+/detections`, `system/events`, `system/health`) ยังรับและ log อย่างเดียว; ถ้าต้องการให้เขียน DB ให้แมป payload กับ endpoint ที่มีอยู่ (detections, system-events ฯลฯ) แล้วเพิ่ม handler ใน mqtt-service คล้าย health/status.

---

## 9. ข้อกำหนดเทคนิคและความสอดคล้อง (Technical constraints)

ส่วนนี้บันทึกข้อกำหนดและวิธีการที่ใช้ในปัจจุบัน เพื่อป้องกันการเปลี่ยนไปใช้เทคนิคหรือค่าที่ขัดแย้งโดยไม่ตั้งใจ และให้ developer ที่รับงานต่อ (อาจไม่ได้พัฒนาต่อเนื่อง) ใช้ต่อยอดได้โดยไม่ conflict.

### 9.1 Database และ Schema

| ข้อกำหนด | ค่า/วิธีการที่ใช้ | หมายเหตุ |
|----------|-------------------|----------|
| โครงสร้างตาราง | ต้องตรงกับ TypeORM entities ใน `server/backend-api/src/entities/` | ถ้าเพิ่มคอลัมน์ใน entity ต้องมีคอลัมน์ใน DB (รัน schema ใหม่หรือ migration). ถ้าไม่ตรง จะเกิด error เช่น 42703 column does not exist → ดู §4.7, §6.3 |
| ตาราง detections | มีคอลัมน์ `archived` (BOOLEAN DEFAULT false), `archived_at` (TIMESTAMP WITH TIME ZONE) | ใช้สำหรับ soft delete/archive ใน Frontend. DB ที่สร้างจาก schema เก่าต้องรัน `migrations/add_detections_archived.sql` |
| Migration | เก็บใน `server/database/migrations/` และบันทึกใน §4.7 และ `server/database/README-aicamera-app.md` | เมื่อเพิ่มคอลัมน์/ตารางใน schema หรือ entity ต้องมี migration สำหรับ DB ที่มีอยู่แล้ว |

### 9.2 API และ Nginx

| ข้อกำหนด | ค่า/วิธีการที่ใช้ | หมายเหตุ |
|----------|-------------------|----------|
| Backend API prefix | `server/api` (setGlobalPrefix ใน backend-api main.ts) | Nginx ต้องส่ง path เต็ม: `proxy_pass http://127.0.0.1:3000/server/api/` ไม่ใช่แค่ origin |
| BACKEND_API_URL (ws-service) | ต้องลงท้ายด้วย `/server/api` | เช่น `http://localhost:3000/server/api` เพื่อให้ request ไปที่ /detections, /cameras/register ฯลฯ ถูก path |
| Frontend API base | `window.location.origin + '/server/api'` | ไม่ hardcode host; ใช้ origin เดียวกับหน้าเว็บ |

### 9.3 Storage และภาพ Detection

| ข้อกำหนด | ค่า/วิธีการที่ใช้ | หมายเหตุ |
|----------|-------------------|----------|
| เก็บภาพ detection | backend-api และ ws-service ต้องใช้ filesystem (หรือ shared volume) เดียวกันสำหรับ `storage/` | เพื่อให้ `GET /server/api/detections/:id/image` อ่านไฟล์จาก `detection.imagePath` ได้ |

### 9.4 บันทึกปัญหาและการแก้ไข (เพื่อไม่ให้เกิดซ้ำ)

| ปัญหา (อาการ / ข้อความใน log) | สาเหตุ | วิธีแก้ (สรุป) | อ้างอิงในคู่มือ |
|--------------------------------|--------|----------------|------------------|
| Detection แสดง Internal Server Error (500); log: **column d.archived does not exist** (PostgreSQL 42703) | ตาราง `detections` ยังไม่มีคอลัมน์ `archived`, `archived_at` | รัน `sudo -u postgres psql -d aicamera_app -f .../migrations/add_detections_archived.sql` แล้ว restart backend-api | §4.7, §6.3, ตารางอาการ §6 |

---

## 10. หมายเหตุเอกสาร

- **Backend TypeORM:** การ integrate backend-api กับ PostgreSQL (entities, DeviceModule, REST ครบ) ดำเนินการแล้ว; รายละเอียดตาม schema ใน `server/database/schema.sql` และ README ใน `server/database/`.
- **Frontend ตาราง + Seed:** ServerHome.vue แสดงทุกตารางพร้อม fallback columns เมื่อว่าง; ข้อมูลตัวอย่างใช้ `server/database/seed-sample-data.sql` (รันหลัง schema).
- **Detections Archive:** ตาราง `detections` รองรับคอลัมน์ `archived`, `archived_at` (soft delete). **ถ้า DB มีอยู่แล้วและยังไม่มีคอลัมน์นี้** ให้รัน `server/database/migrations/add_detections_archived.sql` (ดู §4.7, §6.3); schema ใหม่ (schema.sql) มีคอลัมน์นี้แล้ว.
- **E2E และ Debug:** [E2E_TEST_AND_DEBUG.md](E2E_TEST_AND_DEBUG.md).
- เอกสารเดิม `BACKEND_POSTGRESQL_PROGRESS.md` และ `PLAN_FRONTEND_TABLES_AND_SEED_DATA.md` ยุบรวม/ลบเพื่อลดความซ้ำซ้อน — สรุปอยู่ในคู่มือนี้และ PROJECT_CONTEXT.md
