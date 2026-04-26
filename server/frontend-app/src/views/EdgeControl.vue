<template>
  <div class="edge-control">

    <!-- Page header -->
    <div class="page-header">
      <div class="page-title font-display">
        <span class="page-icon">⊛</span> Edge AI Dashboard
      </div>
      <div class="page-desc">Live camera status from MQTT health reports (camera/+/health, camera/+/status)</div>
    </div>

    <!-- Loading -->
    <div class="skeleton-card" v-if="loading" />

    <div v-else-if="error" class="error-banner">⚠ {{ error }}</div>

    <template v-else>

      <!-- Summary bar -->
      <div class="summary-bar">
        <span class="badge badge-green">● {{ activeCount }} Online</span>
        <span class="badge badge-amber">● {{ yellowCount }} Degraded</span>
        <span class="badge badge-red">● {{ inactiveCount }} Offline</span>
        <button class="refresh-btn" @click="fetchEdgeStatus">↺ Refresh</button>
      </div>

      <!-- Camera cards -->
      <div class="camera-grid">
        <div
          v-for="item in edgeStatusList"
          :key="item.camera.id"
          class="camera-card panel"
        >
          <span class="status-bulb" :class="statusClass(item)" :title="statusTitle(item)" />
          <div class="camera-info">
            <router-link
              :to="'/edge_control/camera/' + item.camera.id"
              class="camera-link"
            >
              {{ item.camera.name || item.camera.cameraId }}
            </router-link>
            <span class="camera-id font-data">{{ item.camera.cameraId }}</span>
            <span v-if="item.latestHealth" class="health-time font-data">
              {{ formatDate(item.latestHealth.timestamp) }}
            </span>
          </div>
        </div>

        <div class="empty-card" v-if="edgeStatusList.length === 0">
          <span class="text-muted">No cameras registered in the system</span>
        </div>
      </div>

    </template>

  </div>
</template>

<script>
const GREEN_MINUTES  = 5;
const YELLOW_MINUTES = 15;

export default {
  name: 'EdgeControlPage',

  data() {
    return {
      edgeStatusList: [],
      loading: true,
      error:   null,
    };
  },

  computed: {
    activeCount()   { return this.edgeStatusList.filter(i => this.statusClass(i) === 'bulb-green').length; },
    yellowCount()   { return this.edgeStatusList.filter(i => this.statusClass(i) === 'bulb-amber').length; },
    inactiveCount() { return this.edgeStatusList.filter(i => this.statusClass(i) === 'bulb-red').length; },
  },

  mounted() {
    this.fetchEdgeStatus();
  },

  methods: {
    async fetchEdgeStatus() {
      this.loading = true;
      this.error   = null;
      try {
        const res  = await fetch(window.location.origin + '/server/api/cameras/edge-status');
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        this.edgeStatusList = Array.isArray(data) ? data : [];
      } catch (e) {
        this.error = e.message || 'Failed to load edge status';
        this.edgeStatusList = [];
      } finally {
        this.loading = false;
      }
    },

    statusClass(item) {
      const h = item.latestHealth;
      if (!h) return 'bulb-red';
      const ageMins = (Date.now() - new Date(h.timestamp).getTime()) / 60000;
      if (ageMins > YELLOW_MINUTES) return 'bulb-red';
      const s = (h.status || '').toLowerCase();
      if (s === 'degraded' || s === 'error') return 'bulb-amber';
      if (ageMins > GREEN_MINUTES) return 'bulb-amber';
      return 'bulb-green';
    },

    statusTitle(item) {
      const h = item.latestHealth;
      if (!h) return 'No data — camera not responding';
      const ageMins = Math.round((Date.now() - new Date(h.timestamp).getTime()) / 60000);
      if (ageMins > YELLOW_MINUTES) return `Offline — last seen ${ageMins}m ago`;
      const s = (h.status || '').toLowerCase();
      if (s === 'degraded' || s === 'error') return `Degraded (${h.status})`;
      return `Online — ${ageMins}m ago`;
    },

    formatDate(val) {
      if (!val) return '';
      try {
        const d = new Date(val);
        return isNaN(d.getTime()) ? String(val) : d.toLocaleString('th-TH', {
          month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit',
        });
      } catch {
        return String(val);
      }
    },
  },
};
</script>

<style scoped>
.edge-control { max-width: 960px; }

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
  height: 200px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}
@keyframes shimmer {
  0%   { background-position:  200% 0; }
  100% { background-position: -200% 0; }
}

/* Summary bar */
.summary-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 1.25rem;
}
.refresh-btn {
  margin-left: auto;
  background: rgba(0,200,255,0.08);
  border: 1px solid rgba(0,200,255,0.22);
  border-radius: var(--radius-sm);
  color: var(--cyan-dim);
  font-size: 11px;
  padding: 4px 12px;
  cursor: pointer;
  transition: background var(--transition);
}
.refresh-btn:hover { background: rgba(0,200,255,0.14); }

/* Camera grid */
.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}
.camera-card {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.9rem 1.1rem;
  transition: border-color var(--transition);
}
.camera-card:hover { border-color: var(--border-bright); }

/* Status bulb */
.status-bulb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}
.bulb-green {
  background: var(--green);
  box-shadow: 0 0 6px rgba(0,230,118,0.5);
  animation: pulse-green 2.5s infinite;
}
.bulb-amber {
  background: var(--amber);
  box-shadow: 0 0 6px rgba(255,171,64,0.4);
}
.bulb-red {
  background: var(--red);
  box-shadow: 0 0 6px rgba(255,61,87,0.35);
}
@keyframes pulse-green {
  0%, 100% { box-shadow: 0 0 4px rgba(0,230,118,0.4); }
  50%       { box-shadow: 0 0 10px rgba(0,230,118,0.7); }
}

/* Camera info */
.camera-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
}
.camera-link {
  font-size: 13px;
  font-weight: 600;
  color: var(--cyan-dim);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color var(--transition);
}
.camera-link:hover { color: var(--cyan); }
.camera-id   { font-size: 10px; color: var(--text-muted); }
.health-time { font-size: 10px; color: var(--text-muted); }

/* Empty state */
.empty-card {
  grid-column: 1 / -1;
  padding: 1.5rem;
  text-align: center;
  font-size: 13px;
}

/* Error banner */
.error-banner {
  padding: 0.75rem 1rem;
  background: var(--red-dim);
  border: 1px solid rgba(255,61,87,0.3);
  border-radius: var(--radius-md);
  color: var(--red);
  font-size: 13px;
}

/* Misc */
.text-muted { color: var(--text-muted); }
</style>
