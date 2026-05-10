<template>
  <div class="camera-list">
    <!-- Header -->
    <div class="page-header">
      <div>
        <div class="page-title font-display">◈ Camera Management</div>
        <div class="page-desc">All cameras registered in the system</div>
      </div>
      <button class="btn btn-primary" @click="showModal = true">⊕ Register Camera</button>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <input v-model="search" class="search-input font-data"
             placeholder="Search camera ID, name, location…" />
      <div class="filter-counts">
        <span class="count-badge badge badge-green">{{ onlineCount }} Online</span>
        <span class="count-badge badge badge-cyan">{{ filtered.length }} Total</span>
      </div>
    </div>

    <!-- Table -->
    <div class="table-panel panel" v-if="!loading">
      <table class="data-table">
        <thead>
          <tr>
            <th class="col-status"></th>
            <th>Camera ID</th>
            <th>Name</th>
            <th>Location</th>
            <th>IP</th>
            <th class="col-num">Temp</th>
            <th class="col-num">CPU</th>
            <th class="col-num">Mem</th>
            <th class="col-time">Last Seen</th>
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filtered.length === 0">
            <td colspan="10" class="empty-row">
              {{ search ? 'No cameras match the filter.' : 'No cameras registered.' }}
            </td>
          </tr>
          <tr v-for="item in filtered" :key="item.camera.id"
              class="table-row" @click="goToDetail(item.camera.id)">
            <td class="col-status">
              <StatusDot :status="cameraStatus(item)" />
            </td>
            <td class="font-data cam-id">{{ item.camera.cameraId }}</td>
            <td class="cam-name">{{ item.camera.name || '—' }}</td>
            <td class="text-secondary">{{ item.camera.locationAddress || '—' }}</td>
            <td class="font-data text-muted">{{ item.camera.ipAddress || '—' }}</td>
            <td class="col-num font-data" :class="tempClass(item.latestHealth?.temperature)">
              {{ fmtTemp(item.latestHealth?.temperature) }}
            </td>
            <td class="col-num font-data text-secondary">
              {{ fmtPct(item.latestHealth?.cpuUsage) }}
            </td>
            <td class="col-num font-data text-secondary">
              {{ fmtPct(item.latestHealth?.memoryUsage) }}
            </td>
            <td class="col-time font-data text-muted">
              {{ fmtAgo(item.latestHealth?.createdAt || item.latestHealth?.timestamp) }}
            </td>
            <td class="col-actions" @click.stop>
              <button class="action-btn" title="Delete"
                      @click="confirmDelete(item.camera)">✕</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Skeleton -->
    <div class="table-panel panel skeleton-table" v-else>
      <div class="skeleton-row" v-for="n in 4" :key="n" />
    </div>

    <ErrorBanner :message="error" @retry="retry" />

    <!-- Register modal -->
    <RegisterCameraModal
      v-if="showModal"
      @close="showModal = false"
      @created="onCreated"
    />

    <!-- Delete confirm -->
    <div class="modal-backdrop" v-if="deleteTarget" @click.self="deleteTarget = null">
      <div class="confirm-box panel">
        <div class="confirm-title">Delete Camera?</div>
        <div class="confirm-body">
          Remove <span class="font-data text-cyan">{{ deleteTarget.cameraId }}</span>
          from the system? This does not delete existing detections.
        </div>
        <div class="confirm-actions">
          <button class="btn" @click="deleteTarget = null">Cancel</button>
          <button class="btn btn-danger" :disabled="deleting" @click="doDelete">
            {{ deleting ? 'Deleting…' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import StatusDot           from '@/components/shared/StatusDot.vue';
import RegisterCameraModal from '@/components/cameras/RegisterCameraModal.vue';
import ErrorBanner         from '@/components/shared/ErrorBanner.vue';
import { useCamerasStore } from '@/stores/cameras.store.js';

export default {
  name: 'CameraList',
  components: { StatusDot, RegisterCameraModal, ErrorBanner },
  data() {
    return {
      search:       '',
      showModal:    false,
      deleteTarget: null,
      deleting:     false,
    };
  },
  setup() {
    const store = useCamerasStore();
    return { store };
  },
  computed: {
    loading()     { return this.store.loading; },
    error()       { return this.store.error; },
    onlineCount() { return this.store.onlineCount; },
    filtered() {
      const q = this.search.toLowerCase();
      return this.store.edgeStatus.filter(item => {
        if (!q) return true;
        const { cameraId = '', name = '', locationAddress = '' } = item.camera;
        return (cameraId + name + locationAddress).toLowerCase().includes(q);
      });
    },
  },
  mounted() {
    this.store.fetchEdgeStatus();
  },
  methods: {
    retry() { this.store.fetchEdgeStatus(); },

    cameraStatus(item) {
      if (!item.latestHealth) return 'unknown';
      const ageMins = (Date.now() - new Date(item.latestHealth.timestamp).getTime()) / 60000;
      if (ageMins > 15) return 'offline';
      const s = (item.latestHealth.status || '').toLowerCase();
      if (s === 'online' || s === 'healthy' || s === 'pass' || s === 'ok') return 'online';
      if (s === 'degraded' || s === 'warning') return 'warning';
      return 'offline';
    },
    tempClass(t) {
      if (t == null) return 'text-muted';
      return t > 70 ? 'text-amber' : 'text-green';
    },
    fmtTemp(t)   { return t != null ? t + '°C' : '—'; },
    fmtPct(v)    { return v != null ? v + '%'  : '—'; },
    fmtAgo(ts) {
      if (!ts) return '—';
      const diff = Date.now() - new Date(ts);
      const m = Math.floor(diff / 60000);
      if (m < 1)  return 'just now';
      if (m < 60) return m + 'm ago';
      const h = Math.floor(m / 60);
      if (h < 24) return h + 'h ago';
      return Math.floor(h / 24) + 'd ago';
    },
    goToDetail(id) {
      this.$router.push('/cameras/' + id);
    },
    onCreated() {
      this.store.fetchEdgeStatus();
    },
    confirmDelete(camera) {
      this.deleteTarget = camera;
    },
    async doDelete() {
      this.deleting = true;
      try {
        await this.store.removeCamera(this.deleteTarget.id);
        this.deleteTarget = null;
      } catch (e) {
        this.store.error = e.message;
      } finally {
        this.deleting = false;
      }
    },
  },
};
</script>

<style scoped>
.camera-list { max-width: 1200px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.page-title {
  font-size: 1.6rem; font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--cyan); text-shadow: var(--cyan-glow);
}
.page-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }

/* Filter */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.search-input {
  flex: 1;
  background: var(--bg-panel);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  padding: 7px 12px;
  outline: none;
  transition: border-color var(--transition);
}
.search-input:focus { border-color: var(--border-bright); }
.search-input::placeholder { color: var(--text-muted); }
.filter-counts { display: flex; gap: 0.5rem; }
.count-badge { font-size: 11px; }

/* Table */
.table-panel { padding: 0; overflow-x: auto; }
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th {
  padding: 9px 12px;
  text-align: left;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-dim);
  white-space: nowrap;
}
.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-dim);
  vertical-align: middle;
}
.table-row { cursor: pointer; transition: background var(--transition); }
.table-row:hover { background: var(--bg-hover); }
.table-row:last-child td { border-bottom: none; }

.col-status  { width: 28px; padding-left: 16px !important; }
.col-num     { text-align: right; width: 70px; }
.col-time    { text-align: right; width: 90px; }
.col-actions { width: 36px; text-align: center; }

.cam-id   { color: var(--cyan-dim); font-weight: 500; }
.cam-name { font-weight: 500; }
.text-secondary { color: var(--text-secondary); }

.empty-row {
  text-align: center;
  color: var(--text-muted);
  padding: 2.5rem 1rem !important;
  font-size: 13px;
}

.action-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 11px;
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  transition: color var(--transition), background var(--transition);
}
.action-btn:hover { color: var(--red); background: var(--red-dim); }

/* Skeleton */
.skeleton-table { padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.skeleton-row {
  height: 40px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

/* Delete confirm modal */
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(8,12,18,0.80);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; backdrop-filter: blur(2px);
}
.confirm-box { width: 380px; max-width: calc(100vw - 2rem); }
.confirm-title {
  font-size: 1rem; font-weight: 600;
  color: var(--red); margin-bottom: 0.75rem;
}
.confirm-body { font-size: 13px; color: var(--text-secondary); margin-bottom: 1.25rem; line-height: 1.6; }
.confirm-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
.btn-danger {
  border-color: rgba(255,61,87,0.5);
  color: var(--red);
}
.btn-danger:hover { background: var(--red-dim); }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

</style>
