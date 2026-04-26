<template>
  <div class="network">
    <h1>Communication Network</h1>
    <p class="subtitle">Monitor การสื่อสารและสถานะ Edge แบบ Realtime – สถานะ Services และ Edge Active/Inactive</p>

    <ServiceStatus :poll-interval="15000" />

    <section class="live-edge" id="live-edge">
      <h2>Live Edge Status</h2>
      <p class="hint">อัปเดตทุก {{ pollInterval / 1000 }} วินาที</p>
      <div v-if="edgeLoading" class="hint">กำลังโหลด...</div>
      <div v-else class="edge-summary">
        <span class="badge active">Active: {{ activeCount }}</span>
        <span class="badge inactive">Inactive: {{ inactiveCount }}</span>
      </div>
      <div class="edge-list">
        <div
          v-for="item in edgeStatusList"
          :key="item.camera.id"
          class="edge-card"
          :class="edgeCardClass(item)"
        >
          <span class="status-bulb" :class="edgeCardClass(item)" />
          <div class="edge-info">
            <router-link :to="'/edge_control/camera/' + item.camera.id" class="edge-link">
              {{ item.camera.name || item.camera.cameraId }}
            </router-link>
            <span class="camera-id">{{ item.camera.cameraId }}</span>
            <span v-if="item.latestHealth" class="health-time">{{ formatDate(item.latestHealth.timestamp) }}</span>
          </div>
        </div>
        <p v-if="edgeStatusList.length === 0 && !edgeLoading" class="empty">ยังไม่มีกล้องในระบบ</p>
      </div>
    </section>

    <section class="client-info" id="websocket">
      <h2>การเชื่อมต่อสำหรับลูกข่าย (Client)</h2>
      <ul>
        <li id="ws-guide"><strong>WebSocket (Socket.IO)</strong>: URL <code>{{ wsUrl }}</code> — path <code>/ws/</code>, port 80 เท่านั้น. รายละเอียดรูปแบบ events: ดู WEBSOCKET_CLIENT_GUIDE ใน repo (server/ws-service/WEBSOCKET_CLIENT_GUIDE.md)</li>
        <li><strong>REST API</strong>: <code>/server/api/</code> — proxy ไป Backend port 3000</li>
        <li id="mqtt-guide"><strong>MQTT</strong>: Broker ที่ port 1883 (เช่น <code>mqtt://lprserver.tail605477.ts.net:1883</code>) — topics ตาม MQTT_CLIENT_GUIDE ใน repo (server/mqtt-service/MQTT_CLIENT_GUIDE.md)</li>
      </ul>
      <p class="hint">Frontend ไม่รับข้อมูลจาก Edge โดยตรง — Microservices (ws-service, mqtt-service) รับแล้วบันทึกลง DB; หน้านี้แสดงสถานะ Services และ Edge เท่านั้น</p>
    </section>
  </div>
</template>

<script>
import ServiceStatus from '../components/ServiceStatus.vue'

const API_BASE = typeof window !== 'undefined' ? window.location.origin + '/server/api' : ''
const GREEN_MINUTES = 5
const YELLOW_MINUTES = 15

export default {
  name: 'NetworkPage',
  components: { ServiceStatus },
  data () {
    return {
      edgeStatusList: [],
      edgeLoading: true,
      pollInterval: 10000,
      pollTimer: null,
      wsUrl: typeof window !== 'undefined' ? window.location.origin + '/ws/' : ''
    }
  },
  computed: {
    activeCount () {
      return this.edgeStatusList.filter(item => this.edgeCardClass(item) === 'active').length
    },
    inactiveCount () {
      return this.edgeStatusList.filter(item => this.edgeCardClass(item) === 'inactive').length
    }
  },
  mounted () {
    this.fetchEdgeStatus()
    this.pollTimer = setInterval(this.fetchEdgeStatus, this.pollInterval)
  },
  beforeUnmount () {
    if (this.pollTimer) clearInterval(this.pollTimer)
  },
  methods: {
    apiUrl (path) {
      return API_BASE + path
    },
    async fetchEdgeStatus () {
      try {
        const res = await fetch(this.apiUrl('/cameras/edge-status'))
        if (!res.ok) return
        const data = await res.json()
        this.edgeStatusList = Array.isArray(data) ? data : []
      } catch (_) {
        this.edgeStatusList = []
      } finally {
        this.edgeLoading = false
      }
    },
    edgeCardClass (item) {
      const h = item.latestHealth
      if (!h) return 'inactive'
      const ageMinutes = (Date.now() - new Date(h.timestamp).getTime()) / 60000
      if (ageMinutes > YELLOW_MINUTES) return 'inactive'
      if (ageMinutes > GREEN_MINUTES) return 'inactive'
      return 'active'
    },
    formatDate (val) {
      if (!val) return ''
      try {
        const d = new Date(val)
        return isNaN(d.getTime()) ? val : d.toLocaleString()
      } catch {
        return val
      }
    }
  }
}
</script>

<style scoped>
.network { text-align: left; max-width: 720px; margin: 1rem auto; padding: 0 1rem; }
.subtitle { color: #6c757d; margin-bottom: 1.5rem; }
.live-edge { margin-top: 2rem; padding: 1rem; background: #f8f9fa; border-radius: 8px; border: 1px solid #dee2e6; }
.live-edge h2 { font-size: 1rem; margin: 0 0 0.5rem 0; }
.edge-summary { display: flex; gap: 0.75rem; margin-bottom: 0.75rem; }
.badge { padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.9rem; font-weight: 600; }
.badge.active { background: #d4edda; color: #155724; }
.badge.inactive { background: #f8d7da; color: #721c24; }
.edge-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.edge-card { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.75rem; border-radius: 6px; border: 1px solid #dee2e6; background: #fff; }
.edge-card.active { border-color: #28a745; background: #d4edda; }
.edge-card.inactive { border-color: #dc3545; background: #f8d7da; }
.status-bulb { width: 10px; height: 10px; border-radius: 50%; }
.status-bulb.active { background: #28a745; }
.status-bulb.inactive { background: #dc3545; }
.edge-info { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; }
.edge-link { color: #0d6efd; text-decoration: none; font-weight: 500; }
.camera-id { font-size: 0.85rem; color: #6c757d; }
.health-time { font-size: 0.8rem; color: #6c757d; }
.empty { color: #6c757d; font-style: italic; margin: 0.5rem 0; }
.client-info { margin-top: 2rem; padding: 1rem; background: #f8f9fa; border-radius: 8px; border: 1px solid #dee2e6; }
.client-info h2 { font-size: 1rem; margin: 0 0 0.75rem 0; }
.client-info ul { margin: 0; padding-left: 1.25rem; }
.client-info code { background: #e9ecef; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.9em; }
.hint { font-size: 0.85rem; color: #6c757d; margin: 0.35rem 0; }
</style>
