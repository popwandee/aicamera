<template>
  <section class="service-status">
    <h2>สถานะการเชื่อมต่อ Services</h2>
    <div class="status-cards">
      <div class="card" :class="apiStatus">
        <span class="label">Backend API</span>
        <span class="value">{{ apiStatus === 'ok' ? 'พร้อม' : apiStatus === 'checking' ? 'กำลังตรวจ...' : 'ไม่พร้อม' }}</span>
      </div>
      <div class="card" :class="wsStatus">
        <span class="label">WebSocket (ws-service)</span>
        <span class="value">{{ wsStatus === 'ok' ? 'เชื่อมต่อแล้ว' : wsStatus === 'checking' ? 'กำลังเชื่อมต่อ...' : 'ไม่เชื่อมต่อ' }}</span>
      </div>
      <div class="card mqtt-info">
        <span class="label">MQTT</span>
        <span class="value">ตรวจที่ server (broker :1883)</span>
      </div>
    </div>
    <p class="hint">อัปเดตเมื่อโหลดหน้า{{ pollInterval ? ' และทุก ' + (pollInterval / 1000) + ' วินาที' : '' }}; WebSocket แสดงสถานะการเชื่อมต่อ ws-service</p>
  </section>
</template>

<script>
import { io } from 'socket.io-client'

export default {
  name: 'ServiceStatus',
  props: {
    pollInterval: { type: Number, default: 0 }
  },
  data () {
    return {
      apiStatus: 'checking',
      wsStatus: 'checking',
      socket: null,
      pollTimer: null
    }
  },
  mounted () {
    this.checkBackendApi()
    this.connectWebSocket()
    if (this.pollInterval > 0) {
      this.pollTimer = setInterval(() => {
        this.checkBackendApi()
        if (this.socket && !this.socket.connected) this.socket.connect()
      }, this.pollInterval)
    }
  },
  beforeUnmount () {
    if (this.socket) this.socket.disconnect()
    if (this.pollTimer) clearInterval(this.pollTimer)
  },
  methods: {
    getApiBase () {
      const base = typeof window !== 'undefined' ? window.location.origin : ''
      return `${base}/server/api`
    },
    async checkBackendApi () {
      try {
        const res = await fetch(this.getApiBase() + '/', { method: 'GET' })
        this.apiStatus = res.ok ? 'ok' : 'error'
      } catch (_) {
        try {
          const res = await fetch(this.getApiBase().replace('/server/api', '') + '/', { method: 'GET' })
          this.apiStatus = res.ok ? 'ok' : 'error'
        } catch (__) {
          this.apiStatus = 'error'
        }
      }
    },
    connectWebSocket () {
      const url = typeof window !== 'undefined' ? window.location.origin : ''
      this.socket = io(url, {
        path: '/ws/',
        transports: ['websocket', 'polling']
      })
      this.socket.on('connect', () => {
        this.wsStatus = 'ok'
      })
      this.socket.on('connect_error', () => {
        this.wsStatus = 'error'
      })
      this.socket.on('disconnect', () => {
        this.wsStatus = 'error'
      })
    }
  }
}
</script>

<style scoped>
.service-status {
  margin: 1.5rem 0;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #dee2e6;
  text-align: left;
}
.service-status h2 {
  margin: 0 0 1rem 0;
  font-size: 1.1rem;
  color: #495057;
}
.status-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}
.card {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid #dee2e6;
  background: #fff;
  min-width: 160px;
}
.card .label {
  display: block;
  font-size: 0.85rem;
  color: #6c757d;
}
.card .value {
  font-weight: 600;
  font-size: 0.95rem;
}
.card.ok { border-color: #28a745; background: #d4edda; }
.card.ok .value { color: #155724; }
.card.error { border-color: #dc3545; background: #f8d7da; }
.card.error .value { color: #721c24; }
.card.checking { border-color: #ffc107; background: #fff3cd; }
.card.checking .value { color: #856404; }
.card.mqtt-info { border-color: #6c757d; background: #e9ecef; }
.card.mqtt-info .value { color: #495057; font-weight: 500; }
.hint {
  margin: 0.75rem 0 0;
  font-size: 0.8rem;
  color: #6c757d;
}
</style>
