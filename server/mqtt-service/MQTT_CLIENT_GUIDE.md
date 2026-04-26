# MQTT Client Guide - AI Camera mqtt-service

## Overview

mqtt-service เป็น NestJS microservice ที่เชื่อมต่อ MQTT broker และ subscribe topic จาก Edge Client  
**Client พัฒนาบน Python** — ใช้ library **Eclipse Paho MQTT** (`paho-mqtt`)

## Broker และการเชื่อมต่อ

- **URL**: ตาม `MQTT_URL` ของ server — บนเครื่อง server มักเป็น `mqtt://localhost:1883`  
  Client จากเครื่องอื่นใช้ host ของ server เช่น `mqtt://lprserver.tail605477.ts.net:1883` หรือ IP ภายในเครือข่าย
- **Port**: 1883 (ต้องเปิดใน firewall/Tailscale ถ้า Client อยู่คนละเครื่อง)
- **Authentication**: ถ้า broker ตั้ง username/password ต้องส่งใน connection options ของ Client

## Topics ที่ mqtt-service subscribe (ฝั่ง Server รับข้อมูล)

| Topic | คำอธิบาย |
|-------|----------|
| `camera/{id}/status` | สถานะ camera |
| `camera/{id}/health` | สุขภาพ/การตรวจสอบ camera |
| `camera/{id}/detections` | เหตุการณ์ตรวจจับ |
| `system/events` | เหตุการณ์ระบบ |
| `system/health` | สุขภาพระบบ |

ข้อมูลที่รับจะถูกบันทึกลงไฟล์ log (default: `mqtt_receive.log` ใต้ server root) เพื่อตรวจสอบ และเตรียมเขียนลง DB ในอนาคต

## รูปแบบ Payload

ส่งเป็น JSON ใน MQTT payload เพื่อให้ฝั่ง server ประมวลผลได้สะดวก

**ตัวอย่าง camera/+/status:**
```json
{
  "camera_id": "camera_01",
  "status": "active",
  "timestamp": "2025-02-19T00:00:00.000Z"
}
```

**ตัวอย่าง camera/+/health (สำหรับ Edge AI Dashboard):**
```json
{
  "camera_id": "camera_01",
  "battery_percent": 85,
  "disk_free_gb": 12.5,
  "cpu_percent": 25,
  "memory_percent": 40,
  "temperature_c": 45,
  "uptime_seconds": 86400,
  "location_lat": 13.7563,
  "location_lng": 100.5018,
  "network_connected": true
}
```

**ตัวอย่าง system/events:**
```json
{
  "event": "camera_connected",
  "camera_id": "camera_01",
  "timestamp": "2025-02-19T00:00:00.000Z"
}
```

## ตัวอย่าง Client (Python)

**ติดตั้ง:**
```bash
pip install paho-mqtt
```

**เชื่อมต่อและ Publish:**
```python
import json
import paho.mqtt.client as mqtt

client = mqtt.Client()
# ถ้ามี username/password:
# client.username_pw_set("user", "password")

client.connect("lprserver.tail605477.ts.net", 1883, 60)
# หรือจากเครื่องเดียวกัน: client.connect("localhost", 1883, 60)

# Publish สถานะ camera
payload = json.dumps({
    "camera_id": "camera_01",
    "status": "active",
    "timestamp": "2025-02-19T00:00:00.000Z"
})
client.publish("camera/camera_01/status", payload)

# Publish health (สำหรับ Edge Dashboard)
health = json.dumps({
    "camera_id": "camera_01",
    "battery_percent": 85,
    "disk_free_gb": 12.5,
    "cpu_percent": 25,
    "memory_percent": 40,
    "temperature_c": 45,
    "uptime_seconds": 86400,
    "network_connected": True
})
client.publish("camera/camera_01/health", health)

client.disconnect()
```

## การตรวจสอบฝั่ง Server

1. **Broker**: ตรวจว่า port 1883 ฟังอยู่ (เช่น `ss -tlnp | grep 1883`) และถ้าใช้ Mosquitto: `systemctl status mosquitto`
2. **mqtt-service**: `systemctl status mqtt.service` และตรวจว่าใช้ `MQTT_URL=mqtt://localhost:1883`
3. **Log**: ดูไฟล์ `mqtt_receive.log` (ใต้ server root) ว่ามีบรรทัดจาก topic ที่ publish

## Troubleshooting

- **เชื่อมต่อ broker ไม่ได้**: ตรวจ firewall, Tailscale ACL และว่า broker รันอยู่
- **ฝั่ง server ไม่เห็น message**: ตรวจว่า mqtt-service รันและ subscribe topic ตรงกับที่ Client publish
- **รูปแบบ payload**: ใช้ JSON string ใน `publish(topic, payload)` เพื่อให้ server parse ได้
