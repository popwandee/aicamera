<template>
  <div class="edge-control">
    <h1>Edge AI Dashboard</h1>
    <p class="subtitle">แสดงรายการกล้องและสถานะจาก MQTT (camera/+/health, camera/+/status) ที่บันทึกลงฐานข้อมูล</p>
    <p v-if="loading" class="hint">กำลังโหลด...</p>
    <p v-else-if="error" class="error-msg">{{ error }}</p>
    <div v-else>
      <div class="summary">
        <span class="badge status-green">Active: {{ activeCount }}</span>
        <span class="badge status-yellow">Degraded/Warning: {{ yellowCount }}</span>
        <span class="badge status-red">Inactive: {{ inactiveCount }}</span>
      </div>
      <div class="camera-list">
      <div
        v-for="item in edgeStatusList"
        :key="item.camera.id"
        class="camera-card"
      >
        <span class="status-bulb" :class="statusClass(item)" :title="statusTitle(item)" />
        <div class="camera-info">
          <router-link :to="'/edge_control/camera/' + item.camera.id" class="camera-link">
            {{ item.camera.name || item.camera.cameraId }}
          </router-link>
          <span class="camera-id">{{ item.camera.cameraId }}</span>
          <span v-if="item.latestHealth" class="health-time">{{ formatDate(item.latestHealth.timestamp) }}</span>
        </div>
      </div>
      <p v-if="edgeStatusList.length === 0" class="empty">ยังไม่มีกล้องในระบบ</p>
      </div>
    </div>
  </div>
</template>

<script>
const API_BASE = typeof window !== 'undefined' ? window.location.origin + '/server/api' : '';
const GREEN_MINUTES = 5;
const YELLOW_MINUTES = 15;

export default {
  name: 'EdgeControlPage',
  data () {
    return {
      edgeStatusList: [],
      loading: true,
      error: null
    };
  },
  computed: {
    activeCount () {
      return this.edgeStatusList.filter(item => this.statusClass(item) === 'status-green').length;
    },
    yellowCount () {
      return this.edgeStatusList.filter(item => this.statusClass(item) === 'status-yellow').length;
    },
    inactiveCount () {
      return this.edgeStatusList.filter(item => this.statusClass(item) === 'status-red').length;
    }
  },
  mounted () {
    this.fetchEdgeStatus();
  },
  methods: {
    apiUrl (path) {
      return API_BASE + path;
    },
    async fetchEdgeStatus () {
      this.loading = true;
      this.error = null;
      try {
        const res = await fetch(this.apiUrl('/cameras/edge-status'));
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        this.edgeStatusList = Array.isArray(data) ? data : [];
      } catch (e) {
        this.error = e.message || 'โหลดไม่สำเร็จ';
        this.edgeStatusList = [];
      } finally {
        this.loading = false;
      }
    },
    statusClass (item) {
      const h = item.latestHealth;
      if (!h) return 'status-red';
      const ageMinutes = (Date.now() - new Date(h.timestamp).getTime()) / 60000;
      if (ageMinutes > YELLOW_MINUTES) return 'status-red';
      if (h.status && (h.status.toLowerCase() === 'degraded' || h.status.toLowerCase() === 'error')) return 'status-yellow';
      if (ageMinutes > GREEN_MINUTES) return 'status-yellow';
      return 'status-green';
    },
    statusTitle (item) {
      const h = item.latestHealth;
      if (!h) return 'ไม่ตอบสนอง (ไม่มีข้อมูล)';
      const ageMinutes = (Date.now() - new Date(h.timestamp).getTime()) / 60000;
      if (ageMinutes > YELLOW_MINUTES) return 'ไม่ตอบสนอง (ข้อมูลเก่ากว่า ' + Math.round(ageMinutes) + ' นาที)';
      if (h.status && (h.status.toLowerCase() === 'degraded' || h.status.toLowerCase() === 'error')) return 'มีปัญหา (' + h.status + ')';
      return 'ปกติ';
    },
    formatDate (val) {
      if (!val) return '';
      try {
        const d = new Date(val);
        return isNaN(d.getTime()) ? String(val) : d.toLocaleString();
      } catch {
        return String(val);
      }
    }
  }
};
</script>

<style scoped>
.edge-control { text-align: left; max-width: 900px; margin: 1rem auto; padding: 0 1rem; }
.subtitle { color: #6c757d; margin-bottom: 1.5rem; }
.hint { color: #6c757d; }
.error-msg { color: #dc3545; }
.camera-list { display: flex; flex-direction: column; gap: 0.75rem; }
.camera-card { display: flex; align-items: center; gap: 1rem; padding: 0.75rem 1rem; border: 1px solid #dee2e6; border-radius: 8px; background: #fff; }
.status-bulb { width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; }
.status-green { background: #28a745; }
.status-yellow { background: #ffc107; }
.status-red { background: #dc3545; }
.camera-info { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.5rem; }
.camera-link { font-weight: 600; color: #0d6efd; text-decoration: none; }
.camera-link:hover { text-decoration: underline; }
.camera-id { font-size: 0.9rem; color: #6c757d; }
.health-time { font-size: 0.85rem; color: #6c757d; }
.empty { color: #6c757d; font-style: italic; padding: 1rem; }
.summary { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1rem; }
.summary .badge { padding: 0.35rem 0.75rem; border-radius: 6px; font-weight: 600; font-size: 0.9rem; }
.summary .status-green { background: #d4edda; color: #155724; }
.summary .status-yellow { background: #fff3cd; color: #856404; }
.summary .status-red { background: #f8d7da; color: #721c24; }
</style>
