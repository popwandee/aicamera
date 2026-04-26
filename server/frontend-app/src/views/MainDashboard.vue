<template>
  <div class="dashboard">
    <div class="page-header">
      <div>
        <div class="page-title font-display">◉ Dashboard</div>
        <div class="page-desc">AI Camera System — Live Overview</div>
      </div>
      <div class="live-clock font-data">{{ clock }}</div>
    </div>

    <!-- KPI Row -->
    <div class="kpi-row">
      <MetricCard icon="◈" label="Cameras Online"    :value="kpi.online"      accent="green"  :loading="loading" />
      <MetricCard icon="◎" label="Detections Today"  :value="kpi.today"       accent="cyan"   :loading="loading" />
      <MetricCard icon="⚡" label="Total Detections"  :value="kpi.total"       accent="cyan"   :loading="loading" />
      <MetricCard icon="⊕" label="Health Records"    :value="kpi.health"      accent="amber"  :loading="loading" />
    </div>

    <!-- Camera status grid -->
    <div class="section-title">Camera Status</div>
    <div class="camera-grid" v-if="!loading">
      <div v-for="item in cameras" :key="item.camera.id" class="camera-tile"
           @click="$router.push('/cameras/' + item.camera.id)">
        <StatusDot :status="cameraStatus(item)" class="tile-dot" />
        <div class="tile-name">{{ item.camera.name || item.camera.cameraId }}</div>
        <div class="tile-id font-data">{{ item.camera.cameraId }}</div>
        <div class="tile-health" v-if="item.latestHealth">
          <span class="font-data" :style="{ color: item.latestHealth.temperature > 70 ? 'var(--amber)' : 'var(--green)' }">
            {{ item.latestHealth.temperature ? item.latestHealth.temperature + '°C' : '—' }}
          </span>
          <span class="tile-cpu font-data">CPU {{ item.latestHealth.cpuUsage ? item.latestHealth.cpuUsage + '%' : '—' }}</span>
        </div>
        <div class="tile-health text-muted" v-else>No health data</div>
      </div>
      <p v-if="cameras.length === 0" class="text-muted">No cameras registered.</p>
    </div>
    <div class="skeleton-grid" v-else>
      <div class="skeleton-tile" v-for="n in 3" :key="n" />
    </div>

    <!-- 24h Hourly Chart -->
    <div class="section-title">Detections — Last 24 Hours</div>
    <div class="chart-panel panel">
      <HourlyChart v-if="hourlyData.length" :hourly-data="hourlyData" />
      <div v-else-if="loading" class="skeleton-chart" />
      <div v-else class="chart-empty text-muted">No detections in the last 24 hours.</div>
    </div>

    <!-- Recent detections feed -->
    <div class="section-title" style="margin-top:1.5rem">
      Recent Detections
      <span class="live-badge" v-if="socketOk">● LIVE</span>
    </div>
    <div class="detection-feed panel" v-if="!loading">
      <div v-for="d in recentDetections" :key="d.id" class="feed-row"
           @click="$router.push('/detections/' + d.id)">
        <span class="feed-plate font-data font-thai">{{ d.licensePlate || '—' }}</span>
        <span class="feed-cam text-muted">{{ d.camera?.cameraId || '' }}</span>
        <span class="feed-conf font-data" :class="confClass(d.confidence)">
          {{ d.confidence ? (parseFloat(d.confidence) * 100).toFixed(0) + '%' : '—' }}
        </span>
        <span class="feed-time font-data text-muted">{{ fmtTime(d.timestamp) }}</span>
      </div>
      <p v-if="recentDetections.length === 0" class="text-muted" style="padding:1rem">
        No detections yet.
      </p>
    </div>
    <div v-else class="skeleton-feed panel" />

    <div v-if="error" class="error-banner">⚠ {{ error }}</div>
  </div>
</template>

<script>
import MetricCard   from '@/components/shared/MetricCard.vue';
import StatusDot    from '@/components/shared/StatusDot.vue';
import HourlyChart  from '@/components/charts/HourlyChart.vue';
import api          from '@/api/index.js';
import { useSocket } from '@/composables/useSocket.js';

export default {
  name: 'MainDashboard',
  components: { MetricCard, StatusDot, HourlyChart },
  data() {
    return {
      cameras: [],
      recentDetections: [],
      hourlyData: [],
      kpi: { online: 0, today: 0, total: 0, health: 0 },
      clock: '',
      loading: true,
      error: null,
      socketOk: false,
      clockTimer: null,
      refreshTimer: null,
    };
  },
  setup() {
    const { socket, connected } = useSocket();
    return { socket, connected };
  },
  mounted() {
    this.loadAll();
    this.updateClock();
    this.clockTimer   = setInterval(this.updateClock, 1000);
    this.refreshTimer = setInterval(this.loadDetections, 10000);
    this.socketOk = this.connected;

    this.socket.on('message_saved',    () => this.loadDetections());
    this.socket.on('camera_registered',() => this.loadCameras());
    this.socket.on('connect',          () => { this.socketOk = true; });
    this.socket.on('disconnect',       () => { this.socketOk = false; });
  },
  beforeUnmount() {
    clearInterval(this.clockTimer);
    clearInterval(this.refreshTimer);
  },
  methods: {
    async loadAll() {
      this.loading = true;
      try {
        await Promise.all([this.loadCameras(), this.loadDetections(), this.loadHealth()]);
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    async loadCameras() {
      this.cameras = await api.getCamerasEdgeStatus();
      this.kpi.online = this.cameras.filter(c => this.cameraStatus(c) === 'online').length;
    },
    async loadDetections() {
      const batch = await api.getDetections({ limit: 500, sortBy: 'timestamp', sortOrder: 'DESC' });
      this.recentDetections = batch.slice(0, 20);
      this.kpi.total = batch.length;
      const today = new Date().toDateString();
      this.kpi.today = batch.filter(d => new Date(d.timestamp).toDateString() === today).length;
      this.hourlyData = this.buildHourlyData(batch);
    },
    buildHourlyData(detections) {
      const now = new Date();
      const buckets = Array(24).fill(0);
      detections.forEach(d => {
        const diff = now - new Date(d.timestamp);
        const hoursAgo = Math.floor(diff / 3600000);
        if (hoursAgo >= 0 && hoursAgo < 24) buckets[23 - hoursAgo]++;
      });
      const curHour = now.getHours();
      return buckets.map((count, i) => {
        const h = (curHour - 23 + i + 24) % 24;
        return { label: String(h).padStart(2, '0'), count };
      });
    },
    async loadHealth() {
      const h = await api.getCameraHealth({ limit: 50 });
      this.kpi.health = h.length;
    },
    cameraStatus(item) {
      if (!item.latestHealth) return 'unknown';
      const s = (item.latestHealth.status || '').toLowerCase();
      if (s === 'online' || s === 'healthy' || s === 'pass') return 'online';
      if (s === 'degraded' || s === 'warning') return 'warning';
      return 'offline';
    },
    confClass(c) {
      const v = parseFloat(c);
      if (v >= 0.9) return 'text-green';
      if (v >= 0.7) return 'text-amber';
      return 'text-red';
    },
    fmtTime(ts) {
      if (!ts) return '';
      const d = new Date(ts);
      return d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    },
    updateClock() {
      this.clock = new Date().toLocaleString('th-TH', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
      });
    },
  },
};
</script>

<style scoped>
.dashboard { max-width: 1200px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.page-title {
  font-size: 1.6rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
}
.page-desc { font-size: 12px; color: var(--text-secondary); margin-top: 3px; }
.live-clock {
  font-size: 1.1rem;
  color: var(--cyan-dim);
  letter-spacing: 0.08em;
}

/* KPI */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1.75rem;
}

/* Camera grid */
.section-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
  margin-top: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.live-badge {
  font-size: 10px;
  color: var(--green);
  animation: blink 2s infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.4} }

.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
.camera-tile {
  background: var(--bg-panel);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  padding: 0.9rem 1rem;
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
}
.camera-tile:hover { border-color: var(--border-bright); background: var(--bg-hover); }
.tile-dot { margin-bottom: 0.5rem; }
.tile-name { font-weight: 500; font-size: 13px; }
.tile-id { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.tile-health {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.5rem;
  font-size: 11px;
}
.tile-cpu { color: var(--text-secondary); }

/* Chart */
.chart-panel { padding: 1rem 1.25rem; }
.chart-empty { padding: 2rem 0; text-align: center; font-size: 13px; }
.skeleton-chart {
  height: 180px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}

/* Feed */
.detection-feed { padding: 0; overflow: hidden; }
.feed-row {
  display: grid;
  grid-template-columns: 160px 1fr 60px 80px;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 1rem;
  border-bottom: 1px solid var(--border-dim);
  cursor: pointer;
  transition: background var(--transition);
}
.feed-row:last-child { border-bottom: none; }
.feed-row:hover { background: var(--bg-hover); }
.feed-plate { font-size: 13px; font-weight: 500; }
.feed-cam { font-size: 11px; }
.feed-conf { font-size: 12px; text-align: right; }
.feed-time { font-size: 11px; text-align: right; }

/* Skeletons */
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
.skeleton-tile {
  height: 100px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}
.skeleton-feed {
  height: 200px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

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
