<template>
  <div class="edge-control-camera">
    <router-link to="/edge_control" class="back-link">← กลับไปรายการกล้อง</router-link>
    <h1>รายละเอียดกล้อง</h1>
    <p v-if="loadingCamera" class="hint">กำลังโหลด...</p>
    <p v-else-if="errorCamera" class="error-msg">{{ errorCamera }}</p>
    <template v-else-if="camera">
      <section class="camera-detail">
        <h2>{{ camera.name || camera.cameraId }}</h2>
        <p class="camera-id">รหัส: {{ camera.cameraId }}</p>
        <p v-if="camera.locationAddress" class="location">{{ camera.locationAddress }}</p>
      </section>
      <section class="health-log">
        <h2>Log สถานะ (Camera Health)</h2>
        <div class="log-toolbar">
          <label>ช่วงเวลา (จาก)</label>
          <input v-model="filterFrom" type="datetime-local" class="date-input" />
          <label>ถึง</label>
          <input v-model="filterTo" type="datetime-local" class="date-input" />
          <label>จำนวน</label>
          <select v-model="limit" class="limit-select" @change="fetchHealth">
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </select>
          <button type="button" class="btn-refresh" @click="fetchHealth">โหลดใหม่</button>
        </div>
        <p v-if="loadingHealth" class="hint">กำลังโหลด...</p>
        <p v-else-if="errorHealth" class="error-msg">{{ errorHealth }}</p>
        <div v-else class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>timestamp</th>
                <th>status</th>
                <th>cpuUsage</th>
                <th>memoryUsage</th>
                <th>temperature</th>
                <th>uptimeSeconds</th>
                <th>metadata</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in healthLog" :key="row.id">
                <td>{{ formatDate(row.timestamp) }}</td>
                <td>{{ row.status }}</td>
                <td>{{ row.cpuUsage != null ? row.cpuUsage : '—' }}</td>
                <td>{{ row.memoryUsage != null ? row.memoryUsage : '—' }}</td>
                <td>{{ row.temperature != null ? row.temperature : '—' }}</td>
                <td>{{ row.uptimeSeconds != null ? row.uptimeSeconds : '—' }}</td>
                <td class="cell">{{ formatCell(row.metadata) }}</td>
              </tr>
              <tr v-if="healthLog.length === 0">
                <td colspan="7" class="empty">ไม่มี log</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script>
const API_BASE = typeof window !== 'undefined' ? window.location.origin + '/server/api' : '';

export default {
  name: 'EdgeControlCameraPage',
  props: {
    id: { type: String, required: true }
  },
  data () {
    return {
      camera: null,
      healthLog: [],
      loadingCamera: true,
      loadingHealth: true,
      errorCamera: null,
      errorHealth: null,
      filterFrom: '',
      filterTo: '',
      limit: 100
    };
  },
  watch: {
    id: {
      immediate: true,
      handler () {
        this.fetchCamera();
        this.fetchHealth();
      }
    }
  },
  methods: {
    apiUrl (path) {
      return API_BASE + path;
    },
    async fetchCamera () {
      if (!this.id) return;
      this.loadingCamera = true;
      this.errorCamera = null;
      try {
        const res = await fetch(this.apiUrl('/cameras/' + this.id));
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        this.camera = data.error ? null : data;
      } catch (e) {
        this.errorCamera = e.message || 'โหลดไม่สำเร็จ';
        this.camera = null;
      } finally {
        this.loadingCamera = false;
      }
    },
    async fetchHealth () {
      if (!this.id) return;
      this.loadingHealth = true;
      this.errorHealth = null;
      try {
        const params = new URLSearchParams();
        params.set('cameraId', this.id);
        params.set('limit', String(this.limit));
        if (this.filterFrom) params.set('from', new Date(this.filterFrom).toISOString());
        if (this.filterTo) params.set('to', new Date(this.filterTo).toISOString());
        const res = await fetch(this.apiUrl('/camera-health?' + params.toString()));
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        this.healthLog = Array.isArray(data) ? data : [];
      } catch (e) {
        this.errorHealth = e.message || 'โหลดไม่สำเร็จ';
        this.healthLog = [];
      } finally {
        this.loadingHealth = false;
      }
    },
    formatDate (val) {
      if (val == null) return '';
      try {
        const d = new Date(val);
        return isNaN(d.getTime()) ? String(val) : d.toLocaleString();
      } catch {
        return String(val);
      }
    },
    formatCell (val) {
      if (val == null) return '';
      if (typeof val === 'object') return JSON.stringify(val).slice(0, 80) + (JSON.stringify(val).length > 80 ? '…' : '');
      return String(val);
    }
  }
};
</script>

<style scoped>
.edge-control-camera { text-align: left; max-width: 100%; margin: 1rem auto; padding: 0 1rem; }
.back-link { display: inline-block; margin-bottom: 1rem; color: #0d6efd; text-decoration: none; }
.back-link:hover { text-decoration: underline; }
.hint { color: #6c757d; }
.error-msg { color: #dc3545; }
.camera-detail { margin-bottom: 2rem; }
.camera-detail h2 { margin-bottom: 0.25rem; }
.camera-id { color: #6c757d; font-size: 0.95rem; }
.location { font-size: 0.9rem; color: #495057; }
.health-log h2 { font-size: 1.1rem; margin-bottom: 0.75rem; }
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.data-table th, .data-table td { border: 1px solid #dee2e6; padding: 0.4rem 0.6rem; text-align: left; }
.data-table th { background: #f8f9fa; font-weight: 600; }
.data-table .cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
.data-table .empty { color: #6c757d; font-style: italic; text-align: center; }
.log-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; }
.log-toolbar label { font-size: 0.9rem; color: #495057; }
.date-input { padding: 0.35rem 0.5rem; border: 1px solid #dee2e6; border-radius: 4px; }
.limit-select { padding: 0.35rem 0.5rem; border: 1px solid #dee2e6; border-radius: 4px; }
.btn-refresh { padding: 0.35rem 0.75rem; background: #0d6efd; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.btn-refresh:hover { background: #0a58ca; }
</style>
