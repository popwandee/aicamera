#!/usr/bin/env bash
# ตรวจสอบการทำงานของ services บน LPR Server (แบบ A: Nginx serve frontend static)
set -e

echo "=== LPR Server – ตรวจสอบ Services ==="
echo ""

# 1. Systemd
echo "--- 1. Systemd units ---"
for u in backend-api websocket mqtt; do
  if systemctl is-active --quiet "${u}.service" 2>/dev/null; then
    echo "  [OK] ${u}.service active"
  else
    echo "  [FAIL] ${u}.service not active"
  fi
done
echo "  (Frontend: แบบ A – Nginx serve static จาก dist, ไม่ใช้ frontend.service)"
echo ""

# 2. Ports
echo "--- 2. Ports ---"
for port in 80 3000 3001 1883; do
  if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
    echo "  [OK] port ${port} listening"
  else
    echo "  [--] port ${port} not listening"
  fi
done
echo ""

# 3. Backend API
echo "--- 3. Backend API (3000) ---"
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/ 2>/dev/null || echo "000")
if [ "$code" = "200" ]; then
  echo "  [OK] GET / => 200"
  curl -s http://127.0.0.1:3000/ | head -c 80
  echo ""
else
  echo "  [FAIL] GET / => $code"
fi
echo ""

# 4. WebSocket (ws-service)
echo "--- 4. WebSocket ws-service (3001) ---"
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3001/ 2>/dev/null || echo "000")
if [ "$code" = "200" ]; then
  echo "  [OK] ws-service responds on 3001 (Socket.IO path /ws/)"
else
  echo "  [--] ws-service HTTP $code"
fi
echo ""

# 5. Nginx
echo "--- 5. Nginx (port 80) ---"
for path in "/" "/server/" "/ws/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1${path}" 2>/dev/null || echo "000")
  echo "  ${path} => ${code}"
done
echo "  (ราก / อาจได้ 403 ถ้าไม่มี index หรือใช้ Landing แยก)"
echo ""

# 6. Frontend static (แบบ A)
echo "--- 6. Frontend /server/ (แบบ A: static) ---"
ct=$(curl -sI "http://127.0.0.1/server/" 2>/dev/null | grep -i content-type || true)
if echo "$ct" | grep -qi "text/html"; then
  echo "  [OK] /server/ returns HTML (Vue app)"
else
  echo "  [--] /server/ response: $ct"
fi
echo ""

# 7. MQTT broker
echo "--- 7. MQTT broker (1883) ---"
if ss -tlnp 2>/dev/null | grep -q ":1883 "; then
  echo "  [OK] port 1883 listening (broker)"
else
  echo "  [--] port 1883 not listening"
fi
echo ""

echo "=== สิ้นสุดการตรวจสอบ ==="
