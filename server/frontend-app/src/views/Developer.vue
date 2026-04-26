<template>
  <div class="developer">
    <h1>For Developer</h1>
    <p class="subtitle">ข้อมูลและลิงก์สำหรับนักพัฒนา – API, WebSocket, MQTT</p>

    <section class="card">
      <h2>API Base</h2>
      <p>REST API อยู่ที่ prefix <code>{{ apiBase }}</code></p>
      <p class="hint">ใช้เป็น base สำหรับเรียก cameras, detections, camera-health, cameras/edge-status ฯลฯ</p>
      <p v-if="apiStatus" :class="apiStatus">API สถานะ: {{ apiStatus === 'ok' ? 'พร้อม' : 'ไม่พร้อม' }}</p>
    </section>

    <section class="card">
      <h2>WebSocket (Socket.IO)</h2>
      <ul>
        <li><strong>URL:</strong> <code>{{ wsUrl }}</code></li>
        <li><strong>Path:</strong> <code>/ws/</code> (port 80 ผ่าน Nginx)</li>
        <li>Client ใช้ library เช่น <code>python-socketio</code>, <code>socket.io-client</code></li>
      </ul>
      <p><a :href="wsGuideHref" target="_blank" rel="noopener" class="link">WEBSOCKET_CLIENT_GUIDE.md</a> – รูปแบบ events (camera_register, message, image, health_status)</p>
    </section>

    <section class="card">
      <h2>MQTT</h2>
      <ul>
        <li><strong>Broker:</strong> ตาม <code>MQTT_URL</code> (เช่น <code>mqtt://broker:1883</code>)</li>
        <li><strong>Topics ที่บันทึก DB:</strong> <code>camera/+/health</code>, <code>camera/+/status</code></li>
        <li>Topics อื่นรับและ log อย่างเดียว</li>
      </ul>
      <p><a :href="mqttGuideHref" target="_blank" rel="noopener" class="link">MQTT_CLIENT_GUIDE.md</a> – รูปแบบ topic และ payload</p>
    </section>

    <section class="card">
      <h2>Environment (ตัวอย่าง ไม่ใส่รหัสผ่านจริง)</h2>
      <ul class="env-list">
        <li><code>BACKEND_API_URL</code> – ต้องรวม path เช่น <code>http://localhost:3000/server/api</code></li>
        <li><code>DATABASE_URL</code> – postgresql://USER:PASSWORD@HOST/DB</li>
        <li><code>MQTT_URL</code> – mqtt://host:1883</li>
        <li><code>STORAGE_ROOT</code> – path ระดับ server root สำหรับภาพและ log</li>
      </ul>
    </section>
  </div>
</template>

<script>
const API_BASE = typeof window !== 'undefined' ? window.location.origin + '/server/api' : ''

export default {
  name: 'DeveloperPage',
  data () {
    return {
      apiBase: API_BASE,
      apiStatus: null,
      wsGuideHref: '',
      mqttGuideHref: ''
    }
  },
  mounted () {
    this.checkApi()
    if (typeof window !== 'undefined') {
      const base = window.location.origin + (window.location.pathname.startsWith('/server') ? '/server' : '')
      this.wsGuideHref = base + '/network#websocket'
      this.mqttGuideHref = base + '/network#mqtt'
    }
  },
  methods: {
    async checkApi () {
      try {
        const res = await fetch(API_BASE + '/', { method: 'GET' })
        this.apiStatus = res.ok ? 'ok' : 'error'
      } catch (_) {
        this.apiStatus = 'error'
      }
    }
  }
}
</script>

<style scoped>
.developer { max-width: 720px; margin: 0 auto; text-align: left; }
.subtitle { color: #6c757d; margin-bottom: 1.5rem; }
.card {
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
}
.card h2 { font-size: 1rem; margin: 0 0 0.5rem 0; color: #0d6efd; }
.card code { background: #e9ecef; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.9em; }
.card ul { margin: 0.5rem 0; padding-left: 1.25rem; }
.card .hint { font-size: 0.9rem; color: #6c757d; margin-top: 0.25rem; }
.card p.ok { color: #198754; font-weight: 500; }
.card p.error { color: #dc3545; font-weight: 500; }
.env-list { list-style: none; padding-left: 0; }
.env-list li { margin: 0.35rem 0; }
.link { color: #0d6efd; }
</style>
