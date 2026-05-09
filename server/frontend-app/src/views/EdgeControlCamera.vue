<template>
  <div class="edge-control-camera">

    <!-- Breadcrumb -->
    <div class="breadcrumb">
      <router-link to="/edge_control" class="back-link">⟶ Edge AI Dashboard</router-link>
      <span class="sep">›</span>
      <span class="crumb-current font-data">{{ camera ? (camera.name || camera.cameraId) : id }}</span>
    </div>

    <!-- Loading / Error -->
    <div class="skeleton-card" v-if="loadingCamera" />
    <div v-else-if="errorCamera" class="error-banner">⚠ {{ errorCamera }}</div>

    <template v-else-if="camera">

      <!-- Camera header -->
      <div class="page-header">
        <div class="page-title font-display">
          <span class="page-icon">⊛</span>
          {{ camera.name || camera.cameraId }}
        </div>
        <div class="camera-meta">
          <span class="font-data text-muted">{{ camera.cameraId }}</span>
          <span v-if="camera.ipAddress" class="font-data text-secondary">IP: {{ camera.ipAddress }}</span>
          <span v-if="camera.locationAddress" class="text-secondary">{{ camera.locationAddress }}</span>
        </div>
      </div>

      <!-- Health log section -->
      <div class="panel section-panel">
        <div class="section-head">Camera Health Log</div>

        <!-- Toolbar -->
        <div class="toolbar">
          <div class="ctrl-group">
            <label class="ctrl-label">From</label>
            <input type="datetime-local" class="ctrl-input" v-model="filterFrom" />
          </div>
          <div class="ctrl-group">
            <label class="ctrl-label">To</label>
            <input type="datetime-local" class="ctrl-input" v-model="filterTo" />
          </div>
          <div class="ctrl-group">
            <label class="ctrl-label">Limit</label>
            <select class="ctrl-select" v-model.number="limit" @change="fetchHealth">
              <option :value="50">50</option>
              <option :value="100">100</option>
              <option :value="200">200</option>
            </select>
          </div>
          <button class="ctrl-btn" @click="fetchHealth" :disabled="loadingHealth">
            {{ loadingHealth ? '…' : '↺ Refresh' }}
          </button>
        </div>

        <div class="skeleton-card short" v-if="loadingHealth" />
        <div v-else-if="errorHealth" class="error-banner" style="margin-top:0.5rem">⚠ {{ errorHealth }}</div>

        <div class="table-wrap" v-else>
          <table class="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Status</th>
                <th>CPU %</th>
                <th>Memory %</th>
                <th>Temp °C</th>
                <th>Uptime</th>
                <th>Metadata</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="healthLog.length === 0">
                <td colspan="7" class="empty-cell text-muted">No health records</td>
              </tr>
              <tr v-for="row in healthLog" :key="row.id" :class="rowHealthClass(row)">
                <td class="font-data text-secondary ts-cell">{{ formatDate(row.timestamp) }}</td>
                <td>
                  <span :class="['badge', statusBadgeClass(row.status)]">{{ row.status || '—' }}</span>
                </td>
                <td class="font-data" :class="cpuClass(row.cpuUsage)">
                  {{ row.cpuUsage != null ? row.cpuUsage + '%' : '—' }}
                </td>
                <td class="font-data" :class="memClass(row.memoryUsage)">
                  {{ row.memoryUsage != null ? row.memoryUsage + '%' : '—' }}
                </td>
                <td class="font-data" :class="tempClass(row.temperature)">
                  {{ row.temperature != null ? row.temperature : '—' }}
                </td>
                <td class="font-data text-muted">{{ fmtUptime(row.uptimeSeconds) }}</td>
                <td class="meta-cell font-data text-muted">{{ fmtMeta(row.metadata) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </template>

  </div>
</template>

<script>
const API_BASE = typeof window !== 'undefined' ? window.location.origin + '/server/api' : '';

export default {
  name: 'EdgeControlCameraPage',
  props: {
    id: { type: String, required: true },
  },

  data() {
    return {
      camera:        null,
      healthLog:     [],
      loadingCamera: true,
      loadingHealth: true,
      errorCamera:   null,
      errorHealth:   null,
      filterFrom:    '',
      filterTo:      '',
      limit:         100,
    };
  },

  watch: {
    id: {
      immediate: true,
      handler() {
        this.fetchCamera();
        this.fetchHealth();
      },
    },
  },

  methods: {
    async fetchCamera() {
      if (!this.id) return;
      this.loadingCamera = true;
      this.errorCamera   = null;
      try {
        const res  = await fetch(API_BASE + '/cameras/' + this.id);
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        this.camera = data.error ? null : data;
      } catch (e) {
        this.errorCamera = e.message || 'Failed to load camera';
        this.camera = null;
      } finally {
        this.loadingCamera = false;
      }
    },

    async fetchHealth() {
      if (!this.id) return;
      this.loadingHealth = true;
      this.errorHealth   = null;
      try {
        const params = new URLSearchParams();
        params.set('cameraId', this.id);
        params.set('limit', String(this.limit));
        if (this.filterFrom) params.set('from', new Date(this.filterFrom).toISOString());
        if (this.filterTo)   params.set('to',   new Date(this.filterTo).toISOString());
        const res  = await fetch(API_BASE + '/camera-health?' + params.toString());
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        this.healthLog = Array.isArray(data) ? data : [];
      } catch (e) {
        this.errorHealth = e.message || 'Failed to load health log';
        this.healthLog = [];
      } finally {
        this.loadingHealth = false;
      }
    },

    statusBadgeClass(status) {
      const s = (status || '').toLowerCase();
      if (s === 'online' || s === 'ok') return 'badge-green';
      if (s === 'degraded' || s === 'warning') return 'badge-amber';
      if (s === 'error' || s === 'offline') return 'badge-red';
      return 'badge-cyan';
    },

    rowHealthClass(row) {
      const s = (row.status || '').toLowerCase();
      if (s === 'error' || s === 'offline') return 'row-error';
      if (s === 'degraded' || s === 'warning') return 'row-warn';
      return '';
    },

    cpuClass(v)  { if (v == null) return ''; return v > 90 ? 'text-red' : v > 70 ? 'text-amber' : 'text-green'; },
    memClass(v)  { if (v == null) return ''; return v > 90 ? 'text-red' : v > 75 ? 'text-amber' : ''; },
    tempClass(v) { if (v == null) return ''; return v > 80 ? 'text-red' : v > 65 ? 'text-amber' : ''; },

    fmtUptime(secs) {
      if (secs == null) return '—';
      const h = Math.floor(secs / 3600);
      const m = Math.floor((secs % 3600) / 60);
      return h > 0 ? `${h}h ${m}m` : `${m}m`;
    },

    fmtMeta(val) {
      if (val == null) return '';
      const s = typeof val === 'object' ? JSON.stringify(val) : String(val);
      return s.length > 80 ? s.slice(0, 79) + '…' : s;
    },

    formatDate(val) {
      if (!val) return '';
      try {
        const d = new Date(val);
        return isNaN(d.getTime()) ? String(val) : d.toLocaleString('th-TH', {
          month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit', second: '2-digit',
        });
      } catch {
        return String(val);
      }
    },
  },
};
</script>

<style scoped>
.edge-control-camera { max-width: 1100px; }

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 1.25rem;
}
.back-link { color: var(--cyan-dim); text-decoration: none; transition: color var(--transition); }
.back-link:hover { color: var(--cyan); }
.sep { opacity: 0.4; }
.crumb-current { color: var(--text-secondary); }

/* Loading skeleton */
.skeleton-card {
  height: 180px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}
.skeleton-card.short { height: 80px; margin-top: 0.75rem; }
@keyframes shimmer {
  0%   { background-position:  200% 0; }
  100% { background-position: -200% 0; }
}

/* Page header */
.page-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.page-title {
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: 0.07em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 4px;
}
.page-icon { opacity: 0.8; }
.camera-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-size: 12px;
}

/* Section panel */
.section-panel { margin-bottom: 1.5rem; }
.section-head {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--text-muted);
  margin-bottom: 0.9rem;
}

/* Toolbar */
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.ctrl-group { display: flex; flex-direction: column; gap: 4px; }
.ctrl-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}
.ctrl-input,
.ctrl-select {
  background: var(--bg-surface);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 12px;
  font-family: var(--font-ui);
  padding: 5px 8px;
  outline: none;
  transition: border-color var(--transition);
}
.ctrl-input:focus, .ctrl-select:focus { border-color: var(--cyan-dim); }
.ctrl-btn {
  background: rgba(0,200,255,0.08);
  border: 1px solid rgba(0,200,255,0.22);
  border-radius: var(--radius-sm);
  color: var(--cyan-dim);
  font-size: 11px;
  padding: 6px 14px;
  cursor: pointer;
  transition: background var(--transition);
}
.ctrl-btn:hover:not(:disabled) { background: rgba(0,200,255,0.14); }
.ctrl-btn:disabled { opacity: 0.45; cursor: default; }

/* Health table */
.table-wrap { overflow-x: auto; }
.data-table  { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  text-align: left;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--text-muted);
  padding: 6px 10px;
  border-bottom: 1px solid var(--border-dim);
}
.data-table td {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(0,200,255,0.04);
  color: var(--text-primary);
  vertical-align: top;
}
.data-table tbody tr:last-child td { border-bottom: none; }
.data-table tbody tr:hover td { background: var(--bg-hover); }

.row-error td { background: rgba(255,61,87,0.03); }
.row-warn  td { background: rgba(255,171,64,0.03); }

.ts-cell   { white-space: nowrap; }
.meta-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-cell { text-align: center; padding: 1.5rem; font-size: 13px; }

/* Error banner */
.error-banner {
  padding: 0.75rem 1rem;
  background: var(--red-dim);
  border: 1px solid rgba(255,61,87,0.3);
  border-radius: var(--radius-md);
  color: var(--red);
  font-size: 13px;
  margin-bottom: 1rem;
}

/* Misc text colors */
.text-secondary { color: var(--text-secondary); }
.text-muted     { color: var(--text-muted); }
.text-red       { color: var(--red); }
.text-amber     { color: var(--amber); }
.text-green     { color: var(--green); }
</style>
