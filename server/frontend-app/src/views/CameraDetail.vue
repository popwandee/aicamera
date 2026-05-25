<template>
  <div class="camera-detail">
    <!-- Back nav -->
    <div class="breadcrumb">
      <span class="back-link" @click="$router.push('/cameras')">◈ Cameras</span>
      <span class="sep">›</span>
      <span class="crumb-current font-data">{{ camera?.cameraId || id }}</span>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="skeleton-header" />

    <!-- Header card -->
    <div class="header-card panel" v-else-if="camera">
      <div class="header-left">
        <StatusDot :status="statusStr" class="header-dot" />
        <div>
          <div class="cam-title font-display">{{ camera.name || camera.cameraId }}</div>
          <div class="cam-sub font-data">{{ camera.cameraId }}</div>
        </div>
      </div>
      <div class="header-meta">
        <div class="meta-item">
          <span class="meta-label">Location</span>
          <span class="meta-val">{{ camera.locationAddress || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">IP</span>
          <span class="meta-val font-data">{{ camera.ip || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Status</span>
          <span class="meta-val" :class="statusColorClass">{{ statusStr }}</span>
        </div>
        <div class="meta-item" v-if="latestHealth">
          <span class="meta-label">Temp</span>
          <span class="meta-val font-data"
                :class="latestHealth.temperature > 70 ? 'text-amber' : 'text-green'">
            {{ latestHealth.temperature != null ? latestHealth.temperature + '°C' : '—' }}
          </span>
        </div>
        <div class="meta-item" v-if="latestHealth">
          <span class="meta-label">CPU</span>
          <span class="meta-val font-data">
            {{ latestHealth.cpuUsage != null ? latestHealth.cpuUsage + '%' : '—' }}
          </span>
        </div>
      </div>
    </div>

    <ErrorBanner :message="error" @retry="retry" />

    <!-- Tabs -->
    <div class="tab-bar">
      <button v-for="(t, i) in tabs" :key="i"
              class="tab-btn"
              :class="{ active: activeTab === i }"
              @click="activeTab = i">
        {{ t }}
      </button>
    </div>

    <!-- ── Tab 0: Overview ──────────────────────────────────── -->
    <div v-if="activeTab === 0" class="tab-pane">
      <div class="overview-grid" v-if="latestHealth">
        <div class="metric-tile panel">
          <div class="metric-icon">🌡</div>
          <div class="metric-val font-data"
               :class="latestHealth.temperature > 70 ? 'text-amber' : 'text-green'">
            {{ latestHealth.temperature != null ? latestHealth.temperature + '°C' : '—' }}
          </div>
          <div class="metric-label">Temperature</div>
        </div>
        <div class="metric-tile panel">
          <div class="metric-icon">⚡</div>
          <div class="metric-val font-data">
            {{ latestHealth.cpuUsage != null ? latestHealth.cpuUsage + '%' : '—' }}
          </div>
          <div class="metric-label">CPU Usage</div>
        </div>
        <div class="metric-tile panel">
          <div class="metric-icon">◎</div>
          <div class="metric-val font-data">
            {{ latestHealth.memoryUsage != null ? latestHealth.memoryUsage + '%' : '—' }}
          </div>
          <div class="metric-label">Memory Usage</div>
        </div>
        <div class="metric-tile panel">
          <div class="metric-icon">◈</div>
          <div class="metric-val font-data">{{ detections.length }}</div>
          <div class="metric-label">Detections Loaded</div>
        </div>
      </div>
      <p class="text-muted" style="padding:1.5rem 0" v-else>
        No health data received yet.
      </p>
    </div>

    <!-- ── Tab 1: Detections ───────────────────────────────── -->
    <div v-if="activeTab === 1" class="tab-pane">
      <div class="panel detection-table-wrap" v-if="!loadingDetections">
        <table class="data-table" v-if="detections.length">
          <thead>
            <tr>
              <th>Plate</th>
              <th class="col-num">Confidence</th>
              <th class="col-time">Timestamp</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in detections" :key="d.id"
                class="table-row" @click="$router.push('/detections/' + d.id)">
              <td class="font-data font-thai plate-cell">{{ d.licensePlate || '—' }}</td>
              <td class="col-num font-data" :class="confClass(d.confidence)">
                {{ d.confidence ? (parseFloat(d.confidence)*100).toFixed(0) + '%' : '—' }}
              </td>
              <td class="col-time font-data text-muted">{{ fmtTs(d.timestamp) }}</td>
              <td class="has-image font-data text-muted">
                {{ d.imagePath ? '🖼' : '' }}
              </td>
            </tr>
          </tbody>
        </table>
        <p class="text-muted empty-msg" v-else>No detections recorded for this camera.</p>
      </div>
      <div class="panel skeleton-table" v-else>
        <div class="skeleton-row" v-for="n in 5" :key="n" />
      </div>
    </div>

    <!-- ── Tab 2: Health Log ───────────────────────────────── -->
    <div v-if="activeTab === 2" class="tab-pane">
      <!-- Line chart -->
      <div class="chart-panel panel" v-if="healthRecords.length">
        <Line :data="healthChartData" :options="healthChartOptions"
              style="height:220px; max-height:220px" />
      </div>

      <!-- Health table -->
      <div class="panel health-table-wrap" style="margin-top:1rem">
        <table class="data-table" v-if="healthRecords.length">
          <thead>
            <tr>
              <th class="col-time">Time</th>
              <th class="col-num">Temp (°C)</th>
              <th class="col-num">CPU %</th>
              <th class="col-num">Mem %</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in healthRecords" :key="h.id">
              <td class="col-time font-data text-muted">{{ fmtTs(h.createdAt || h.timestamp) }}</td>
              <td class="col-num font-data" :class="h.temperature > 70 ? 'text-amber' : 'text-green'">
                {{ h.temperature != null ? h.temperature : '—' }}
              </td>
              <td class="col-num font-data text-secondary">
                {{ h.cpuUsage != null ? h.cpuUsage : '—' }}
              </td>
              <td class="col-num font-data text-secondary">
                {{ h.memoryUsage != null ? h.memoryUsage : '—' }}
              </td>
              <td>
                <span class="badge" :class="healthBadge(h.status)">
                  {{ h.status || '—' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="text-muted empty-msg" v-else-if="!loadingHealth">No health records found.</p>
        <div class="skeleton-row" v-else />
      </div>
    </div>

    <!-- ── Tab 3: Images ───────────────────────────────────── -->
    <div v-if="activeTab === 3" class="tab-pane">
      <div class="image-grid" v-if="detectionsWithImages.length">
        <div v-for="d in detectionsWithImages" :key="d.id"
             class="image-tile" @click="$router.push('/detections/' + d.id)">
          <img :src="imageUrl(d.id)" class="thumb" :alt="d.licensePlate"
               @error="$event.target.style.display='none'" loading="lazy" />
          <div class="thumb-plate font-data font-thai">{{ d.licensePlate || '—' }}</div>
          <div class="thumb-time font-data text-muted">{{ fmtTs(d.timestamp) }}</div>
        </div>
      </div>
      <p class="text-muted empty-msg" v-else>No images available for this camera.</p>
    </div>
  </div>
</template>

<script>
import {
  Chart as ChartJS, CategoryScale, LinearScale,
  LineElement, PointElement, Tooltip, Legend, Filler,
} from 'chart.js';
import { Line } from 'vue-chartjs';
import StatusDot    from '@/components/shared/StatusDot.vue';
import ErrorBanner  from '@/components/shared/ErrorBanner.vue';
import api from '@/api/index.js';

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend, Filler);

export default {
  name: 'CameraDetail',
  components: { StatusDot, Line, ErrorBanner },
  props: { id: { type: String, required: true } },
  data() {
    return {
      camera:            null,
      detections:        [],
      healthRecords:     [],
      loading:           true,
      loadingDetections: false,
      loadingHealth:     false,
      error:             null,
      activeTab:         0,
      tabs: ['Overview', 'Detections', 'Health Log', 'Images'],
    };
  },
  computed: {
    latestHealth() {
      return this.healthRecords[0] || null;
    },
    statusStr() {
      if (!this.latestHealth) return 'unknown';
      const ts = this.latestHealth.timestamp || this.latestHealth.createdAt;
      const ageMins = ts ? (Date.now() - new Date(ts).getTime()) / 60000 : Infinity;
      if (ageMins > 15) return 'offline';
      const s = (this.latestHealth.status || '').toLowerCase();
      if (s === 'online' || s === 'healthy' || s === 'pass' || s === 'ok') return 'online';
      if (s === 'degraded' || s === 'warning') return 'warning';
      return 'offline';
    },
    statusColorClass() {
      const m = { online: 'text-green', warning: 'text-amber', offline: 'text-red' };
      return m[this.statusStr] || 'text-muted';
    },
    detectionsWithImages() {
      return this.detections.filter(d => d.imagePath);
    },
    healthChartData() {
      const records = [...this.healthRecords].reverse(); // oldest first
      const labels  = records.map(h => this.fmtChartLabel(h.createdAt || h.timestamp));
      return {
        labels,
        datasets: [
          {
            label:           'Temp (°C)',
            data:            records.map(h => h.temperature),
            borderColor:     '#ffab40',
            backgroundColor: 'rgba(255,171,64,0.10)',
            borderWidth:     1.5,
            pointRadius:     2,
            tension:         0.3,
            fill:            false,
            yAxisID:         'yTemp',
          },
          {
            label:           'CPU %',
            data:            records.map(h => h.cpuUsage),
            borderColor:     '#00c8ff',
            backgroundColor: 'rgba(0,200,255,0.08)',
            borderWidth:     1.5,
            pointRadius:     2,
            tension:         0.3,
            fill:            true,
            yAxisID:         'yCpu',
          },
        ],
      };
    },
    healthChartOptions() {
      const gridColor  = 'rgba(0,200,255,0.07)';
      const tickColor  = 'rgba(120,160,200,0.40)';
      const axisBase   = { grid: { color: gridColor }, ticks: { color: tickColor, font: { family: "'JetBrains Mono', monospace", size: 10 } } };
      return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            labels: { color: tickColor, font: { family: "'JetBrains Mono', monospace", size: 10 }, boxWidth: 12 },
          },
          tooltip: {
            backgroundColor: '#0d1520',
            borderColor:     'rgba(0,200,255,0.3)',
            borderWidth:     1,
            titleColor:      '#00c8ff',
            bodyColor:       'rgba(220,240,255,0.8)',
          },
        },
        scales: {
          x: { ...axisBase, ticks: { ...axisBase.ticks, maxTicksLimit: 8 } },
          yTemp: {
            ...axisBase,
            position: 'left',
            title: { display: true, text: '°C', color: '#ffab40', font: { size: 10 } },
          },
          yCpu: {
            ...axisBase,
            position: 'right',
            min: 0, max: 100,
            grid: { drawOnChartArea: false },
            title: { display: true, text: 'CPU %', color: '#00c8ff', font: { size: 10 } },
          },
        },
      };
    },
  },
  mounted() {
    this.loadAll();
  },
  methods: {
    retry() { this.loadAll(); },

    async loadAll() {
      this.loading = true;
      try {
        await Promise.all([
          this.loadCamera(),
          this.loadDetections(),
          this.loadHealth(),
        ]);
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    async loadCamera() {
      this.camera = await api.getCamera(this.id);
    },
    async loadDetections() {
      this.loadingDetections = true;
      try {
        this.detections = await api.getCameraDetections(this.id, 200);
      } finally {
        this.loadingDetections = false;
      }
    },
    async loadHealth() {
      this.loadingHealth = true;
      try {
        this.healthRecords = await api.getCameraHealth({ cameraId: this.id, limit: 100 });
      } finally {
        this.loadingHealth = false;
      }
    },
    confClass(c) {
      const v = parseFloat(c);
      if (v >= 0.9) return 'text-green';
      if (v >= 0.7) return 'text-amber';
      return 'text-red';
    },
    healthBadge(s) {
      const l = (s || '').toLowerCase();
      if (l === 'online' || l === 'healthy' || l === 'pass') return 'badge-green';
      if (l === 'warning' || l === 'degraded') return 'badge-amber';
      if (l === 'offline' || l === 'fail')     return 'badge-red';
      return 'badge-cyan';
    },
    fmtTs(ts) {
      if (!ts) return '—';
      return new Date(ts).toLocaleString('th-TH', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },
    fmtChartLabel(ts) {
      if (!ts) return '';
      const d = new Date(ts);
      return d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });
    },
    imageUrl(detectionId) {
      return api.getDetectionImageUrl(detectionId);
    },
  },
};
</script>

<style scoped>
.camera-detail { max-width: 1100px; }

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 1.25rem;
}
.back-link {
  color: var(--cyan-dim);
  cursor: pointer;
  transition: color var(--transition);
}
.back-link:hover { color: var(--cyan); }
.sep { opacity: 0.4; }
.crumb-current { color: var(--text-secondary); }

/* Skeleton header */
.skeleton-header {
  height: 90px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
  margin-bottom: 1.25rem;
}

/* Header card */
.header-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.5rem;
  margin-bottom: 1.25rem;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 0 0 auto;
}
.header-dot { width: 12px !important; height: 12px !important; }
.cam-title {
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
}
.cam-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

.header-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  flex: 1;
}
.meta-item { display: flex; flex-direction: column; }
.meta-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 2px;
}
.meta-val { font-size: 13px; }

/* Tabs */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-dim);
  margin-bottom: 1.25rem;
}
.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 12px;
  letter-spacing: 0.06em;
  padding: 8px 18px;
  transition: color var(--transition), border-color var(--transition);
  margin-bottom: -1px;
}
.tab-btn:hover  { color: var(--text-secondary); }
.tab-btn.active { color: var(--cyan); border-bottom-color: var(--cyan); }

/* Overview grid */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
}
.metric-tile { text-align: center; padding: 1.25rem 1rem; }
.metric-icon { font-size: 1.25rem; margin-bottom: 0.5rem; }
.metric-val  { font-size: 1.5rem; font-weight: 700; margin-bottom: 4px; }
.metric-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }

/* Table (shared) */
.detection-table-wrap, .health-table-wrap { padding: 0; overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  padding: 8px 12px;
  text-align: left;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-dim);
}
.data-table td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--border-dim);
  vertical-align: middle;
}
.table-row { cursor: pointer; transition: background var(--transition); }
.table-row:hover { background: var(--bg-hover); }
.table-row:last-child td { border-bottom: none; }
.col-num  { text-align: right; width: 80px; }
.col-time { text-align: right; width: 110px; }
.plate-cell { font-weight: 500; }
.has-image { text-align: center; width: 32px; }
.empty-msg { padding: 2rem 1rem; text-align: center; font-size: 13px; }

/* Chart */
.chart-panel { padding: 1rem 1.25rem; }

/* Image grid */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.75rem;
}
.image-tile {
  background: var(--bg-panel);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  transition: border-color var(--transition);
}
.image-tile:hover { border-color: var(--border-bright); }
.thumb {
  width: 100%;
  height: 110px;
  object-fit: cover;
  display: block;
  background: var(--bg-surface);
}
.thumb-plate { font-size: 12px; font-weight: 500; padding: 6px 8px 2px; }
.thumb-time  { font-size: 10px; padding: 0 8px 6px; }

/* Skeletons */
.skeleton-table { padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.skeleton-row {
  height: 36px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

</style>
