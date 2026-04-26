#!/usr/bin/env node
/**
 * ทดสอบส่ง detection_result ผ่าน WebSocket (ผ่าน Nginx :80 /ws/)
 *
 * ใช้ตรวจสอบ workflow:
 * Edge -> ws-service -> backend-api -> PostgreSQL -> Dashboard (/server/)
 *
 * รันจากโฟลเดอร์ server:
 *   node scripts/test_websocket_detection_result.js
 *
 * ตัวแปรปรับค่าได้:
 *   WS_URL=http://127.0.0.1
 *   CAMERA_ID=2
 *   CHECKPOINT_ID=2
 *   PLATE=TEST123
 */
const path = require('path');
const io = require(path.join(__dirname, '../ws-service/node_modules/socket.io-client'));

const baseUrl = process.env.WS_URL || 'http://127.0.0.1';
const cameraId = process.env.CAMERA_ID || '2';
const checkpointId = process.env.CHECKPOINT_ID || cameraId;
const plate = process.env.PLATE || 'TEST123';

const url = `${baseUrl}/`;
const opts = { path: '/ws/', transports: ['websocket', 'polling'] };

console.log('Connecting to', url, 'path:', opts.path);
const socket = io(url, opts);

socket.on('connect', () => {
  console.log('Connected:', socket.id);
  socket.emit('message', {
    camera_id: cameraId,
    type: 'detection_result',
    aicamera_id: cameraId,
    checkpoint_id: checkpointId,
    timestamp: new Date().toISOString(),
    vehicles_count: 1,
    plates_count: 1,
    ocr_results: [{ text: plate, confidence: 0.9 }],
    vehicle_detections: [],
    plate_detections: [],
    processing_time_ms: 12,
  });
});

socket.on('message_saved', (data) => {
  console.log('message_saved:', data);
  socket.disconnect();
  process.exit(0);
});

socket.on('message_error', (data) => {
  console.error('message_error:', data);
  socket.disconnect();
  process.exit(1);
});

socket.on('connect_error', (err) => {
  console.error('connect_error:', err.message);
  process.exit(1);
});

setTimeout(() => {
  console.error('Timeout waiting for message_saved');
  socket.disconnect();
  process.exit(1);
}, 12000);

