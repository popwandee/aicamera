# Systemd units สำหรับ LPR Server

## Services

- **backend-api.service** — NestJS Backend API (port 3000)
- **websocket.service** — WebSocket ws-service (port 3001, ภายในเครื่อง)
- **mqtt.service** — MQTT microservice (เชื่อมต่อ broker localhost:1883)

## Frontend 

Frontend ใช้  Nginx serve ไฟล์ static จาก `server/frontend-app/dist` ที่ path `/server/`  
**ไม่ใช้** unit แยก (ไม่มี frontend.service) — หลัง `npm run build` ใน frontend-app แล้วให้ Nginx ชี้ `location /server/` ไปที่โฟลเดอร์ `dist`

---

## ลำดับการเริ่มทำงานหลัง Boot

หลังเปิดเครื่อง ให้บริการเริ่มตามลำดับดังนี้:

### 1. Nginx (port 80)

- Nginx ควรเริ่มก่อนหรือพร้อมกับเครือข่าย (มักมี `After=network.target` อยู่แล้ว)
- ใช้ config ที่ **location /** ชี้ไปที่ **Landing page**: โฟลเดอร์ `server/landing/` (ไฟล์ `index.html`)
- ใช้ config ตัวอย่าง: [../nginx-lprserver.conf](../nginx-lprserver.conf)

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
# หรือให้ boot เริ่มให้เอง
```

### 2. Backend (systemd)

เริ่มตามลำดับใดก็ได้ (หรือพร้อมกัน) — แต่ควรให้ **หลัง network พร้อม**:

1. **backend-api.service** — REST API (3000)
2. **websocket.service** — WebSocket (3001)
3. **mqtt.service** — MQTT client ต่อ broker

```bash
sudo systemctl enable backend-api.service websocket.service mqtt.service
sudo systemctl start backend-api.service websocket.service mqtt.service
```

หรือให้ systemd เริ่มให้หลัง boot (จาก `enable` ด้านบน)

### 3. Frontend (แบบไม่มี service)

- **ไม่มีการรัน process แยก** สำหรับ frontend
- Nginx serve ไฟล์จาก `frontend-app/dist` ที่ path `/server/`
- ก่อน deploy ต้อง **build frontend** แล้ว Nginx จะส่งไฟล์จาก `dist` ให้เอง

```bash
cd /home/devuser/aicamera/server/frontend-app
npm run build
# ไฟล์ใน dist/ จะถูก Nginx serve ที่ /server/
```

หลัง boot: ถ้า Nginx และ backend services ถูก enable ไว้แล้ว ระบบจะเริ่มให้ครบโดยอัตโนมัติ; frontend แค่ต้องมีโฟลเดอร์ `dist` (จาก `npm run build`) ให้ Nginx ชี้ไป

---

## Nginx: ตั้ง location / เป็น Landing

ใช้ config ตัวอย่างใน repo:

```bash
sudo cp /home/devuser/aicamera/server/nginx-lprserver.conf /etc/nginx/sites-available/lprserver
sudo ln -sf /etc/nginx/sites-available/lprserver /etc/nginx/sites-enabled/
# ลบหรือปิด default ถ้าทับ
sudo nginx -t && sudo systemctl reload nginx
```

ใน [nginx-lprserver.conf](../nginx-lprserver.conf):

- **`location /`** → root ชี้ไปที่ `server/landing/` → แสดง **index.html** (Landing page)
- **`location /server/`** → alias ชี้ไปที่ `server/frontend-app/dist/` (Vue app)
- **`location /server/api/`** → proxy ไป backend-api (3000)
- **`location /ws/`** → proxy ไป ws-service (3001)

---

## การติดตั้ง systemd units

```bash
sudo cp backend-api.service websocket.service mqtt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable backend-api.service websocket.service mqtt.service
sudo systemctl start backend-api.service websocket.service mqtt.service
```
