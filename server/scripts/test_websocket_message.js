#!/usr/bin/env node
/**
 * ทดสอบการส่ง message ผ่าน WebSocket ผ่าน Nginx port 80 (ข้อ 6)
 * รันจากโฟลเดอร์ server: node scripts/test_websocket_message.js
 * ต้องมี ws-service ติดตั้งแล้ว (ใช้ socket.io-client จาก ws-service/node_modules)
 */
const path = require('path');
const io = require(path.join(__dirname, '../ws-service/node_modules/socket.io-client'));

const baseUrl = process.env.WS_URL || 'http://127.0.0.1';
const url = `${baseUrl}/`;
const opts = { path: '/ws/', transports: ['websocket', 'polling'] };

console.log('Connecting to', url, 'path:', opts.path);

const socket = io(url, opts);

socket.on('connect', () => {
  console.log('Connected:', socket.id);
  socket.emit('message', { content: 'Test message from verify script ' + new Date().toISOString() });
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
}, 10000);
