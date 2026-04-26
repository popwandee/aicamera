#!/usr/bin/env bash
# ทดสอบการรับส่งข้อมูลผ่าน MQTT (ข้อ 9)
# ต้อง restart mqtt.service หลังเพิ่ม topic handlers: sudo systemctl restart mqtt.service
# รัน: ./scripts/test_mqtt_publish.sh

set -e
SERVER_ROOT="${SERVER_ROOT:-/home/devuser/aicamera/server}"
LOG_FILE="${SERVER_ROOT}/mqtt_receive.log"
TOPIC="${1:-system/health}"
PAYLOAD="${2:-{\"test\":true,\"source\":\"verify_script\"}}"

echo "Publishing to $TOPIC: $PAYLOAD"
mosquitto_pub -h 127.0.0.1 -t "$TOPIC" -m "$PAYLOAD" 2>/dev/null || { echo "mosquitto_pub failed (broker down?)"; exit 1; }
sleep 1
if [ -f "$LOG_FILE" ]; then
  echo "Last lines of $LOG_FILE:"
  tail -3 "$LOG_FILE"
else
  echo "Log file not found. Ensure mqtt.service was restarted after adding handlers."
fi
