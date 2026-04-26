# แผนตรวจสอบ Microservices และ Landing Page (lprserver)

## 1. สรุป Microservices บนเครื่อง Server

| Service | Port/Transport | หน้าที่ | ไฟล์ systemd | สถานะการเชื่อมต่อจาก Client |
|--------|----------------|--------|----------------|------------------------------|
| **backend-api** | HTTP 3000 | REST API, อ่าน/เขียนข้อมูลจาก DB, Device/Auth | `backend-api.service` | ✅ ผ่าน nginx: `/server/api/` → 3000 |
| **ws-service** | HTTP+WS 3001 (Socket.IO) | รับข้อความ/ภาพจากลูกข่ายผ่าน WebSocket | `websocket.service` | ✅ ผ่าน nginx: `/ws/` → 3001 (แนะนำใช้ path นี้แทนตรง port) |
| **mqtt-service** | MQTT (broker:1883) | Microservice แบบ MQTT ไม่มี HTTP port | `mqtt.service` | N/A (เชื่อมต่อกับ broker ภายในเครือข่าย) |
| **Dashboard** | HTTP 5000 | แสดงสถานะ Services / เครือข่าย (ต้องมี app รันบน 5000) | (นอก repo หรือแยก service) | ✅ ผ่าน nginx: `/dashboard/` → 5000 |

### หมายเหตุ
- **backend-api**: ไม่มี `setGlobalPrefix('api')` ดังนั้น route อยู่ที่ root (เช่น `/`, `/device/...`). Nginx ใช้ `/server/api/` → `http://127.0.0.1:3000/api/` ดังนั้น backend ควรตั้ง prefix `api` หรือ nginx ต้อง proxy เป็น `/server/api/` → `http://127.0.0.1:3000/` แล้ว rewrite path ตามต้องการ.
- **ws-service**: ใช้ path `/ws/` บน gateway แล้ว; client ควรเชื่อมต่อผ่าน `http://lprserver.tail605477.ts.net/ws/` (ไม่ต้องเปิด port 3001 ภายนอก).
- **mqtt-service**: ใช้เฉพาะ MQTT ต่อ broker; ไม่มี endpoint HTTP ให้ client เข้ามาโดยตรง.

---

## 2. จุดที่อาจขัดแย้งหรือทำให้ Client เชื่อมต่อไม่ได้

1. **Path ไม่ตรงกัน**
   - Backend API: ถ้า Nest ใช้ prefix `api` แล้ว nginx ส่งไปที่ `3000/api/` ถูกต้อง. ถ้า Nest ไม่มี prefix แต่ nginx ใช้ `/server/api/` → `3000/api/` จะ 404 ได้.
   - WebSocket: client ใช้ `ws://host:3001` โดยตรงอาจถูก firewall/Tailscale บล็อก; ควรใช้ `http://host/ws/` ผ่าน nginx.

2. **Dashboard (port 5000)**
   - Nginx proxy `/dashboard/` ไปที่ localhost:5000. ถ้าไม่มี process รันที่ 5000 จะ 502. ต้องมี dashboard app (เช่น analytics-dashboard หรือ service อื่น) รันบนเครื่องนี้.

3. **CORS / CSP**
   - Nginx ตั้ง CSP ให้แล้ว; ถ้า dashboard หรือ server ฝั่ง frontend เรียก cross-origin ต้องไม่ขัดกับ CSP.

4. **Redirect ไม่สมบูรณ์**
   - ก่อนแก้: มีแค่ `/server` → `/server/`. ยังไม่มี `/dashboard` → `/dashboard/` และ `/ws` → `/ws/`.

---

## 3. ข้อเสนอแนะในการปรับปรุง

1. **รวมการเข้าใช้งานผ่าน nginx ให้เป็น path เดียว**
   - ใช้ `/server/`, `/dashboard/`, `/ws/` เป็นหลัก.
   - เพิ่ม redirect ถาวร: `/server` → `/server/`, `/dashboard` → `/dashboard/`, `/ws` → `/ws/`.

2. **แยกบทบาท /server (Frontend)**
   - **/server/** = แสดงผลข้อมูลจากฐานข้อมูลเท่านั้น (อ่านจาก backend-api ที่ `/server/api/`).
   - ตัดส่วนที่เกี่ยวกับการสื่อสารกับลูกข่าย (WebSocket/MQTT) ออก; ให้ **ws-service** และ **mqtt-service** จัดการรับข้อมูลจากลูกข่าย แล้วเขียนลง DB หรือส่งต่อให้ backend-api ตามที่ออกแบบ.

3. **Dashboard**
   - **/dashboard/** = ใช้ดูสถานะของ Services และการสื่อสารเครือข่ายบนเครื่องนี้ (เช่น backend-api, ws-service, mqtt, nginx).
   - ตรวจสอบให้มี process รันที่ port 5000 และมี systemd/service ถ้าต้องการให้รันถาวร.

4. **Landing page (root)**
   - หน้าแรกของ `lprserver.tail605477.ts.net` ใช้เป็น Landing อธิบายสถาปัตยกรรมและวิธีการทำงานของระบบ.
   - มีเมนู/ลิงก์:
     - ไป **/server/** = นำข้อมูลจากฐานข้อมูลมาแสดงผล.
     - ไป **/dashboard/** = ดูสถานะ Services / เครือข่าย.

5. **Backend API prefix**
   - ยืนยันว่า NestJS backend ใช้ path อย่างไร (มีหรือไม่มี `/api`). ถ้าใช้ `/api` แล้ว nginx `/server/api/` → `3000/api/` ถูกต้อง. ถ้าไม่ใช้ ให้เพิ่ม `app.setGlobalPrefix('api')` ใน backend หรือปรับ nginx ให้ส่ง path ให้ตรงกับ backend.

---

## 4. สิ่งที่ทำแล้ว / จะทำในขั้นตอนถัดไป

- [x] จัดทำแผนและเอกสารตรวจสอบ microservices (ไฟล์นี้).
- [x] เพิ่ม nginx redirect: `/dashboard` → `/dashboard/`, `/ws` → `/ws/` (และคง `/server` → `/server/`).
- [x] สร้าง Landing page (static HTML) ที่ `server/landing/index.html` สำหรับ root; มีเมนูลิงก์ไปยัง `/server/`, `/dashboard/`.
- [x] กำหนด scope ของ /server: แสดงผลจาก DB เท่านั้น, ตัดส่วนสื่อสารลูกข่าย; ดู `server/frontend-app/SCOPE_DATABASE_ONLY.md`.
- [ ] ปรับปรุง frontend-app ตาม scope (ลบ/ไม่เพิ่มการเชื่อมต่อลูกข่ายโดยตรง).
- [ ] ตรวจสอบและแก้ไข backend-api path (prefix) ให้สอดคล้องกับ nginx ถ้าจำเป็น.

---

## 5. โครงสร้าง URL หลังปรับปรุง

| URL | การใช้งาน |
|-----|------------|
| `http://lprserver.tail605477.ts.net/` | Landing page (สถาปัตยกรรม + ลิงก์) |
| `http://lprserver.tail605477.ts.net/server` หรือ `/server/` | แอปแสดงข้อมูลจาก DB (frontend-app) |
| `http://lprserver.tail605477.ts.net/dashboard` หรือ `/dashboard/` | Dashboard สถานะ Services/เครือข่าย |
| `http://lprserver.tail605477.ts.net/ws` หรือ `/ws/` | WebSocket (Socket.IO) สำหรับลูกข่าย |

ทุก path ใช้ทั้งแบบมีและไม่มี slash ด้านท้าย โดย redirect ไปที่แบบมี slash.
