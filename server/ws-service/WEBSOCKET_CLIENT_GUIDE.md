# WebSocket Client Guide - AI Camera ws-service

## Overview

WebSocket service รองรับการรับข้อความและภาพจาก client ผ่าน Socket.IO protocol  
**Client พัฒนาบน Python** — ใช้ library `python-socketio`

## Connection

**การเชื่อมต่อใช้ผ่าน Nginx port 80 เท่านั้น** — ไม่เปิด port 3001 ภายนอก (firewall/Tailscale ไม่ expose 3001)

- **URL:** `http://lprserver.tail605477.ts.net/ws/` (Socket.IO client)
- **Port:** 80 (ผ่าน Nginx proxy)
- **Path:** `/ws/`
- **ข้อดี:** ไม่ต้องเปิด port 3001 ใน firewall/Tailscale, เสถียรและปลอดภัยกว่า

## Events ที่รองรับ

### 1. ส่งข้อความ (message)

Client ส่ง event `message` พร้อมข้อความ (string หรือ object ที่มี field `content`)

**ตัวอย่าง (string):**
```python
sio.emit('message', 'Hello from client')
```

**ตัวอย่าง (object):**
```python
sio.emit('message', {'content': 'Detection result', 'camera_id': 'cam01'})
```

**ผลลัพธ์ (ทั่วไป):** บันทึกในไฟล์ `receive_message.log` ที่โฟลเดอร์ server root

#### 1.1 ส่งผลตรวจจับ (detection_result) เพื่อบันทึกลงฐานข้อมูล

ถ้าข้อความมีรูปแบบเป็น `type: "detection_result"` จะถูก ws-service ส่งต่อไป backend-api เพื่อบันทึกลงฐานข้อมูล (ตาราง `cameras`, `detections`) ซึ่งหน้า Dashboard ที่ `/server/` จะดึงข้อมูลจาก DB มาแสดง

**ตัวอย่าง (object detection_result):**

```python
sio.emit('message', {
    # camera_id ใช้เป็นตัวตั้งต้นสำหรับ register กล้อง (cameras.camera_id)
    'camera_id': '2',
    'type': 'detection_result',
    'aicamera_id': '2',
    'checkpoint_id': '2',
    'timestamp': '2026-03-05T08:00:00.000Z',
    'vehicles_count': 1,
    'plates_count': 1,
    # ocr_results อาจเป็น array หรือ JSON string ก็ได้
    'ocr_results': [{'text': 'TEST123', 'confidence': 0.90}],
    # optional
    'vehicle_detections': [],
    'plate_detections': [],
    'processing_time_ms': 12
})
```

---

### 2. ส่งภาพ (image)

Client ส่ง event `image` พร้อม base64 image data

**รูปแบบข้อมูล:**
```python
{
    'data': str,        # base64 encoded image (หรือ data URL เช่น data:image/jpeg;base64,...)
    'filename': str,    # optional ชื่อไฟล์ เช่น "detection_001.jpg"
    'camera_id': str    # optional รหัส camera สำหรับจัดเก็บใน subfolder
}
```

**ตัวอย่าง:**
```python
# จาก base64 string
sio.emit('image', {
    'data': base64_string,
    'filename': 'capture_001.jpg',
    'camera_id': 'camera_01'
})

# จาก data URL
sio.emit('image', {
    'data': 'data:image/jpeg;base64,/9j/4AAQSkZJRg...'
})
```

**ผลลัพธ์:** บันทึกในโฟลเดอร์ `storage/` (หรือ `storage/{camera_id}/` ถ้ามี camera_id)

## Response Events

- `message_saved` / `image_saved` - สำเร็จ
- `message_error` / `image_error` - ล้มเหลว

## Paths บน Server

| รายการ | Path (default) |
|--------|----------------|
| ภาพ | `/home/devuser/aicamera/server/storage/` |
| Log ข้อความ | `/home/devuser/aicamera/server/receive_message.log` |

กำหนด `STORAGE_ROOT` ใน environment เพื่อเปลี่ยน path หลัก

## ตัวอย่าง Client (Python)

**ติดตั้ง:**
```bash
pip install python-socketio[client]
```

**เชื่อมต่อผ่าน Nginx (port 80) — วิธีเดียวที่รองรับ**
```python
import socketio

sio = socketio.Client()

# ใช้ path: '/ws/' เพื่อให้ nginx proxy ไปที่ ws-service
sio.connect('http://lprserver.tail605477.ts.net/ws/', socketio_path='/ws/')

# ส่งข้อความ
sio.emit('message', 'Hello from Python')
sio.emit('message', {'content': 'Detection result', 'camera_id': 'cam01'})

# ส่งภาพ
sio.emit('image', {
    'data': base64_image,
    'filename': 'det.jpg',
    'camera_id': 'camera_01'
})

# ฟัง response
@sio.event
def message_saved(data):
    print('Message saved:', data)

@sio.event
def image_saved(data):
    print('Image saved:', data)

@sio.event
def message_error(data):
    print('Message error:', data)

@sio.event
def image_error(data):
    print('Image error:', data)

# เมื่อเสร็จ
sio.disconnect()
```

**ตัวอย่างแบบ async (ถ้าต้องการ):**
```python
import socketio

sio = socketio.AsyncClient()

async def main():
    await sio.connect('http://lprserver.tail605477.ts.net/ws/', socketio_path='/ws/')
    await sio.emit('message', 'Hello from Python')
    await sio.emit('image', {'data': base64_image, 'filename': 'det.jpg'})
    await sio.disconnect()

# ใช้ asyncio.run(main()) หรือ run ใน event loop
```

## Troubleshooting

### การเชื่อมต่อล้มเหลว

1. **ตรวจสอบว่า ws-service ทำงาน:**
   ```bash
   systemctl status websocket.service
   ```

2. **ตรวจสอบ Nginx config:**
   - ต้องมี proxy `/ws/` → `http://127.0.0.1:3001` (หรือ upstream ที่ชี้ไป ws-service)
   - ไม่ต้องเปิด port 3001 ภายนอก

3. **ตรวจสอบ Nginx logs:**
   ```bash
   sudo tail -f /var/log/nginx/error.log
   sudo tail -f /var/log/nginx/access.log
   ```

4. **ทดสอบเชื่อมต่อจากเครื่อง server (ผ่าน Nginx):**
   ```bash
   curl -i http://127.0.0.1/ws/
   # ควรได้ response จาก Socket.IO (อาจเป็น 400 หรือ handshake ขึ้นกับ path)
   ```

5. **ถ้าใช้ Tailscale:** ใช้ URL ผ่าน Nginx (`http://lprserver.tail605477.ts.net/ws/`) เท่านั้น — ไม่ต้องเปิด port 3001 ใน ACL
