<template>
  <div class="system-events">

    <!-- Page header -->
    <div class="page-header">
      <div class="page-title font-display">
        <span class="page-icon">⊟</span> System Events
      </div>
      <div class="page-desc">Server-side event log — camera registrations, detections, errors, and state changes</div>
    </div>

    <!-- Controls -->
    <div class="panel controls-panel">
      <div class="ctrl-row">
        <div class="ctrl-group">
          <label class="ctrl-label">Severity</label>
          <select class="ctrl-select" v-model="filterSeverity">
            <option value="all">All</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
        </div>
        <div class="ctrl-group">
          <label class="ctrl-label">Limit</label>
          <select class="ctrl-select" v-model.number="limit" @change="fetchEvents">
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
            <option :value="500">500</option>
          </select>
        </div>
        <div class="ctrl-group">
          <label class="ctrl-label">Search</label>
          <input
            type="text"
            class="ctrl-input"
            placeholder="filter message…"
            v-model="filterText"
          />
        </div>
        <button class="ctrl-btn" @click="fetchEvents" :disabled="loading">
          {{ loading ? '…' : '↺ Refresh' }}
        </button>
      </div>
    </div>

    <!-- KPI badges -->
    <div class="severity-bar" v-if="!loading && events.length">
      <span class="sev-badge sev-total">
        {{ events.length }} total
      </span>
      <span class="sev-badge sev-info" @click="filterSeverity = 'info'">
        ● {{ infoCnt }} info
      </span>
      <span class="sev-badge sev-warn" @click="filterSeverity = 'warning'">
        ● {{ warnCnt }} warning
      </span>
      <span class="sev-badge sev-error" @click="filterSeverity = 'error'">
        ● {{ errorCnt }} error
      </span>
      <span
        v-if="filterSeverity !== 'all' || filterText"
        class="sev-badge sev-clear"
        @click="clearFilters"
      >✕ clear filters</span>
    </div>

    <!-- Loading skeleton -->
    <div class="skeleton-card" v-if="loading" />

    <template v-else>

      <!-- Empty -->
      <div class="panel section-panel empty-panel" v-if="!filteredEvents.length">
        <span class="text-muted">
          {{ events.length ? 'No events match the current filter.' : 'No system events found.' }}
        </span>
      </div>

      <!-- Events table -->
      <div class="panel section-panel" v-else>
        <div class="section-head">
          Events
          <span class="section-sub">{{ filteredEvents.length }} shown</span>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Severity</th>
                <th>Type</th>
                <th>Source</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ev in filteredEvents" :key="ev.id" :class="rowClass(ev)">
                <td class="font-data text-secondary ts-cell">{{ fmtTs(ev.createdAt || ev.timestamp) }}</td>
                <td>
                  <span :class="['badge', sevBadgeClass(ev)]">{{ sevLabel(ev) }}</span>
                </td>
                <td class="font-data text-muted">{{ ev.eventType || ev.type || '—' }}</td>
                <td class="font-data text-muted">{{ ev.source || ev.service || (ev.camera && ev.camera.cameraId) || '—' }}</td>
                <td class="msg-cell">{{ ev.message || ev.description || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </template>

    <div v-if="error" class="error-banner">⚠ {{ error }}</div>

  </div>
</template>

<script>
import api from '@/api/index.js';

export default {
  name: 'SystemEvents',

  data() {
    return {
      events:         [],
      loading:        false,
      error:          null,
      filterSeverity: 'all',
      filterText:     '',
      limit:          200,
    };
  },

  mounted() {
    this.fetchEvents();
  },

  computed: {
    filteredEvents() {
      let list = this.events;
      if (this.filterSeverity !== 'all') {
        list = list.filter(e => this.sevKey(e) === this.filterSeverity);
      }
      if (this.filterText.trim()) {
        const q = this.filterText.trim().toLowerCase();
        list = list.filter(e =>
          (e.message || e.description || '').toLowerCase().includes(q) ||
          (e.eventType || e.type || '').toLowerCase().includes(q) ||
          (e.source || e.service || '').toLowerCase().includes(q) ||
          (e.camera?.cameraId || '').toLowerCase().includes(q),
        );
      }
      return list;
    },
    infoCnt()  { return this.events.filter(e => this.sevKey(e) === 'info').length; },
    warnCnt()  { return this.events.filter(e => this.sevKey(e) === 'warning').length; },
    errorCnt() { return this.events.filter(e => this.sevKey(e) === 'error').length; },
  },

  methods: {
    async fetchEvents() {
      this.loading = true;
      this.error   = null;
      try {
        const raw = await api.getSystemEvents(this.limit);
        this.events = Array.isArray(raw) ? raw : [];
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },

    clearFilters() {
      this.filterSeverity = 'all';
      this.filterText     = '';
    },

    sevKey(ev) {
      const s = (ev.severity || ev.eventLevel || ev.level || ev.type || 'info').toLowerCase();
      if (s === 'error' || s === 'critical' || s === 'fatal') return 'error';
      if (s === 'warning' || s === 'warn')                    return 'warning';
      return 'info';
    },

    sevLabel(ev) {
      const k = this.sevKey(ev);
      if (k === 'error')   return 'ERROR';
      if (k === 'warning') return 'WARN';
      return 'INFO';
    },

    sevBadgeClass(ev) {
      const k = this.sevKey(ev);
      if (k === 'error')   return 'badge-red';
      if (k === 'warning') return 'badge-amber';
      return 'badge-cyan';
    },

    rowClass(ev) {
      const k = this.sevKey(ev);
      if (k === 'error')   return 'row-error';
      if (k === 'warning') return 'row-warn';
      return '';
    },

    fmtTs(ts) {
      if (!ts) return '—';
      return new Date(ts).toLocaleString('th-TH', {
        month: '2-digit', day: '2-digit', year: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },
  },
};
</script>

<style scoped>
.system-events { max-width: 1100px; }

/* Page header */
.page-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.page-title {
  font-size: 1.6rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.page-icon { opacity: 0.8; }
.page-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }

/* Loading skeleton */
.skeleton-card {
  height: 240px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}
@keyframes shimmer {
  0%   { background-position:  200% 0; }
  100% { background-position: -200% 0; }
}

/* Controls */
.controls-panel { padding: 0.9rem 1.25rem; margin-bottom: 0.75rem; }
.ctrl-row {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 1rem;
}
.ctrl-group { display: flex; flex-direction: column; gap: 4px; }
.ctrl-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}
.ctrl-select,
.ctrl-input {
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
.ctrl-input { min-width: 180px; }
.ctrl-select:focus, .ctrl-input:focus { border-color: var(--cyan-dim); }
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

/* Severity bar */
.severity-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
  font-size: 11px;
}
.sev-badge {
  padding: 2px 9px;
  border-radius: 3px;
  font-family: var(--font-data);
  cursor: pointer;
  transition: opacity var(--transition);
}
.sev-badge:hover { opacity: 0.8; }
.sev-total { background: rgba(120,160,200,0.08); color: var(--text-muted); border: 1px solid var(--border-dim); cursor: default; }
.sev-info  { background: rgba(0,200,255,0.08);  color: var(--cyan);  border: 1px solid rgba(0,200,255,0.2); }
.sev-warn  { background: var(--amber-dim);       color: var(--amber); border: 1px solid rgba(255,171,64,0.3); }
.sev-error { background: var(--red-dim);         color: var(--red);   border: 1px solid rgba(255,61,87,0.3); }
.sev-clear { background: transparent; color: var(--text-muted); border: 1px solid var(--border-dim); }

/* Panels */
.section-panel { margin-bottom: 1.5rem; }
.empty-panel { padding: 1.2rem; font-size: 13px; }
.section-head {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--text-muted);
  margin-bottom: 1rem;
}
.section-sub {
  font-size: 10px;
  font-weight: normal;
  letter-spacing: 0;
  text-transform: none;
  margin-left: 8px;
  opacity: 0.7;
}

/* Table */
.table-wrap  { overflow-x: auto; }
.data-table  { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  text-align: left;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--text-muted);
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-dim);
}
.data-table td {
  padding: 7px 12px;
  border-bottom: 1px solid rgba(0,200,255,0.04);
  color: var(--text-primary);
  vertical-align: top;
}
.data-table tbody tr:last-child td { border-bottom: none; }
.data-table tbody tr:hover td { background: var(--bg-hover); }

.row-error td { border-bottom-color: rgba(255,61,87,0.06); }
.row-warn  td { border-bottom-color: rgba(255,171,64,0.06); }
.row-error:hover td { background: rgba(255,61,87,0.04); }
.row-warn:hover  td { background: rgba(255,171,64,0.04); }

.ts-cell  { white-space: nowrap; }
.msg-cell { max-width: 380px; word-break: break-word; line-height: 1.45; }

/* Misc */
.text-secondary { color: var(--text-secondary); }
.text-muted     { color: var(--text-muted); }

.error-banner {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: var(--red-dim);
  border: 1px solid rgba(255,61,87,0.3);
  border-radius: var(--radius-md);
  color: var(--red);
  font-size: 13px;
}
</style>
