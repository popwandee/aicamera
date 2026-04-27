<template>
  <div class="analytics-view">

    <!-- Page header -->
    <div class="page-header">
      <div class="page-title font-display">
        <span class="page-icon">▦</span> Analytics
      </div>
      <div class="page-desc">30-day trends · confidence distribution · activity heatmap · camera comparison</div>
    </div>

    <!-- KPI row -->
    <div class="kpi-row">
      <MetricCard icon="⟨/⟩" label="Total Detections" :value="totalStr"    accent="cyan"  :loading="store.loading" />
      <MetricCard icon="⊙"   label="Unique Plates"     :value="uniqueStr"   accent="green" :loading="store.loading" />
      <MetricCard icon="◎"   label="Avg Confidence"    :value="avgConfStr"  accent="amber" :loading="store.loading" />
      <MetricCard icon="▣"   label="Active Cameras"    :value="cameraCount" accent="cyan"  :loading="store.loading" />
    </div>

    <!-- E2: 30-day daily bar chart -->
    <div class="panel section-panel">
      <div class="section-head">Daily Detections — Last 30 Days</div>
      <div class="chart-wrap chart-tall" v-if="!store.loading">
        <Bar :data="dailyChartData" :options="dailyOptions" />
      </div>
      <div class="skeleton-chart chart-tall" v-else />
    </div>

    <!-- E3 + E5: confidence histogram + camera comparison -->
    <div class="grid-2col">

      <div class="panel section-panel">
        <div class="section-head">E3 · Confidence Distribution</div>
        <div class="chart-wrap" v-if="!store.loading">
          <Bar :data="histogramChartData" :options="histogramOptions" />
        </div>
        <div class="skeleton-chart" v-else />
      </div>

      <div class="panel section-panel">
        <div class="section-head">E5 · Camera Comparison</div>
        <div class="chart-wrap" v-if="!store.loading && store.cameraComparison.length">
          <Bar :data="cameraChartData" :options="cameraOptions" />
        </div>
        <div class="skeleton-chart" v-else-if="store.loading" />
        <div class="empty-msg text-muted" v-else>
          No camera data — run <code>GET /cameras/analytics/run</code> to populate analytics
        </div>
      </div>

    </div>

    <!-- E4: 7d × 24h activity heatmap -->
    <div class="panel section-panel">
      <div class="section-head">E4 · Activity Heatmap — Last 7 Days × 24 Hours</div>

      <div class="heatmap-wrap" v-if="!store.loading">
        <!-- Hour header row -->
        <div class="hm-row">
          <div class="hm-day-label" />
          <div class="hm-cells">
            <div class="hm-hour" v-for="h in 24" :key="h">
              {{ String(h - 1).padStart(2, '0') }}
            </div>
          </div>
        </div>

        <!-- Day rows -->
        <div class="hm-row" v-for="(label, di) in store.heatmapData.dayLabels" :key="di">
          <div class="hm-day-label font-data">{{ label }}</div>
          <div class="hm-cells">
            <div
              class="hm-cell"
              v-for="(count, hi) in store.heatmapData.cells[di]"
              :key="hi"
              :style="heatmapCellStyle(count)"
              :title="`${label} ${String(hi).padStart(2, '0')}:00 — ${count} detection${count !== 1 ? 's' : ''}`"
            />
          </div>
        </div>

        <!-- Colour legend -->
        <div class="hm-legend">
          <span class="text-muted hm-legend-label">Less</span>
          <div class="hm-legend-bar" />
          <span class="text-muted hm-legend-label">More (max: {{ heatmapMax }})</span>
        </div>
      </div>

      <div class="skeleton-chart" style="height:196px" v-else />
    </div>

    <!-- E6: Top plates table -->
    <div class="panel section-panel">
      <div class="section-head">
        E6 · Top License Plates
        <span class="section-sub">from {{ store.detections.length.toLocaleString() }} loaded records</span>
      </div>

      <div class="skeleton-chart" style="height:120px" v-if="store.loading" />
      <div class="empty-msg text-muted" v-else-if="!store.topPlates.length">No detection records loaded</div>

      <table class="data-table" v-else>
        <thead>
          <tr>
            <th>#</th>
            <th>License Plate</th>
            <th>Detections</th>
            <th>% of Loaded</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in store.topPlates" :key="item.plate">
            <td class="font-data text-muted">{{ idx + 1 }}</td>
            <td><PlateTag :plate="item.plate" size="sm" /></td>
            <td class="font-data text-cyan">{{ item.count }}</td>
            <td class="font-data text-muted">{{ detectionPct(item.count) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>

    <ErrorBanner :message="store.error" @retry="retry" />

  </div>
</template>

<script>
import { Bar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
} from 'chart.js';
import MetricCard   from '@/components/shared/MetricCard.vue';
import PlateTag     from '@/components/shared/PlateTag.vue';
import ErrorBanner  from '@/components/shared/ErrorBanner.vue';
import { useAnalyticsStore } from '@/stores/analytics.store.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip);

const TICK   = { color: '#8899aa', font: { family: 'JetBrains Mono, monospace', size: 9 } };
const GRID   = { color: 'rgba(136,153,170,0.08)' };
const TIP    = {
  backgroundColor: '#0d1520',
  titleColor:      '#00c8ff',
  bodyColor:       '#8899aa',
  borderColor:     'rgba(0,200,255,0.25)',
  borderWidth:     1,
  padding:         8,
};

export default {
  name: 'AnalyticsDashboard',
  components: { Bar, MetricCard, PlateTag, ErrorBanner },

  setup() {
    return { store: useAnalyticsStore() };
  },

  mounted() {
    this.store.fetchAll();
  },

  computed: {
    // ── KPI strings ────────────────────────────────────────────────
    totalStr() {
      // prefer analytics sum; fallback to loaded detections count
      const n = this.store.totalDetections || this.store.detections.length;
      return n.toLocaleString();
    },
    uniqueStr()   { return this.store.uniquePlatesAll.toString(); },
    avgConfStr()  {
      const v = this.store.avgConfidence;
      return v ? (v * 100).toFixed(1) + '%' : '—';
    },
    cameraCount() { return this.store.cameraComparison.length.toString(); },

    // ── Heatmap max (for colour scaling) ───────────────────────────
    heatmapMax() {
      let max = 1;
      this.store.heatmapData.cells.forEach(row => row.forEach(v => { if (v > max) max = v; }));
      return max;
    },

    // ── E2: 30-day daily bar chart ─────────────────────────────────
    dailyChartData() {
      const data = this.store.dailyTotals;
      return {
        labels: data.map(d => d.date.slice(5)), // MM-DD
        datasets: [{
          label: 'Detections',
          data:  data.map(d => d.count),
          backgroundColor:      'rgba(0,200,255,0.18)',
          borderColor:          '#00c8ff',
          borderWidth:          1,
          borderRadius:         3,
          hoverBackgroundColor: 'rgba(0,200,255,0.35)',
        }],
      };
    },
    dailyOptions() {
      return {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { ...TIP } },
        scales: {
          x: { grid: GRID, ticks: { ...TICK, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 } },
          y: { grid: GRID, ticks: { ...TICK, precision: 0 }, beginAtZero: true },
        },
      };
    },

    // ── E3: confidence histogram ────────────────────────────────────
    histogramChartData() {
      const data   = this.store.confidenceHistogram;
      const colors = data.map((_, i) => {
        const mid = (i + 0.5) * 10;
        if (mid >= 90) return { bg: 'rgba(0,230,118,0.30)',  border: '#00e676' };
        if (mid >= 70) return { bg: 'rgba(255,171,64,0.30)', border: '#ffab40' };
        return           { bg: 'rgba(255,61,87,0.30)',  border: '#ff3d57' };
      });
      return {
        labels: data.map(d => d.label + '%'),
        datasets: [{
          label:           'Count',
          data:            data.map(d => d.count),
          backgroundColor: colors.map(c => c.bg),
          borderColor:     colors.map(c => c.border),
          borderWidth:     1,
          borderRadius:    3,
        }],
      };
    },
    histogramOptions() {
      return {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...TIP,
            callbacks: {
              title: (items) => items[0].label + ' confidence',
              label: (item)  => ' ' + item.raw + ' detections',
            },
          },
        },
        scales: {
          x: { grid: GRID, ticks: { ...TICK } },
          y: { grid: GRID, ticks: { ...TICK, precision: 0 }, beginAtZero: true },
        },
      };
    },

    // ── E5: camera comparison (horizontal bar) ──────────────────────
    cameraChartData() {
      const data = this.store.cameraComparison;
      return {
        labels: data.map(c => c.name || c.cameraId),
        datasets: [{
          label:                'Detections',
          data:                 data.map(c => c.count),
          backgroundColor:      'rgba(0,230,118,0.20)',
          borderColor:          '#00e676',
          borderWidth:          1,
          borderRadius:         3,
          hoverBackgroundColor: 'rgba(0,230,118,0.40)',
        }],
      };
    },
    cameraOptions() {
      return {
        responsive: true, maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            ...TIP,
            titleColor:  '#00e676',
            borderColor: 'rgba(0,230,118,0.25)',
            callbacks: {
              label: (item) => ' ' + item.raw + ' detections',
            },
          },
        },
        scales: {
          x: { grid: GRID, ticks: { ...TICK, precision: 0 }, beginAtZero: true },
          y: { grid: GRID, ticks: { color: '#00e676', font: { family: 'JetBrains Mono, monospace', size: 10 } } },
        },
      };
    },
  },

  methods: {
    // E4: heatmap cell inline style based on count vs max
    heatmapCellStyle(count) {
      if (count === 0) {
        return { background: 'rgba(0,200,255,0.03)', border: '1px solid rgba(0,200,255,0.06)' };
      }
      const alpha = (0.08 + (count / this.heatmapMax) * 0.72).toFixed(2);
      return { background: `rgba(0,200,255,${alpha})`, border: '1px solid rgba(0,200,255,0.12)' };
    },

    retry() { this.store.fetchAll(); },

    // E6: % of loaded detections for top-plates table
    detectionPct(count) {
      const total = this.store.detections.length;
      return total ? ((count / total) * 100).toFixed(1) : '0.0';
    },
  },
};
</script>

<style scoped>
.analytics-view { max-width: 1200px; }

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

/* KPI row */
/* Section panels */
.section-panel { margin-bottom: 1.5rem; }
.section-head {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--text-muted);
  margin-bottom: 1rem;
}
.section-sub {
  display: inline-block;
  font-size: 10px;
  font-weight: normal;
  letter-spacing: 0;
  text-transform: none;
  color: var(--text-muted);
  margin-left: 8px;
  opacity: 0.7;
}

/* Chart containers */
.chart-wrap       { height: 200px; }
.chart-tall       { height: 240px; }

/* 2-column grid */
.grid-2col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

/* ── Heatmap ─────────────────────────────────────────────── */
.heatmap-wrap { overflow-x: auto; padding-bottom: 4px; }

.hm-row {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-bottom: 2px;
}

.hm-day-label {
  width: 88px;
  min-width: 88px;
  font-size: 9px;
  color: var(--text-muted);
  text-align: right;
  padding-right: 6px;
}

.hm-cells { display: flex; gap: 3px; }

.hm-hour {
  width: 22px;
  min-width: 22px;
  text-align: center;
  font-size: 8px;
  font-family: var(--font-data);
  color: var(--text-muted);
}

.hm-cell {
  width: 22px;
  min-width: 22px;
  height: 22px;
  border-radius: 2px;
  cursor: default;
  transition: transform 0.10s;
}
.hm-cell:hover { transform: scale(1.35); z-index: 1; }

.hm-legend {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  margin-left: 94px;
}
.hm-legend-label { font-size: 9px; }
.hm-legend-bar {
  width: 130px;
  height: 10px;
  border-radius: 2px;
  background: linear-gradient(to right, rgba(0,200,255,0.05), rgba(0,200,255,0.80));
}

/* ── Skeleton ────────────────────────────────────────────── */
.skeleton-chart {
  height: 200px;
  background: linear-gradient(
    90deg,
    var(--bg-panel) 25%,
    var(--bg-surface) 50%,
    var(--bg-panel) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Top plates table ────────────────────────────────────── */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
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
  border-bottom: 1px solid rgba(0,200,255,0.05);
  color: var(--text-primary);
}
.data-table tbody tr:hover td { background: var(--bg-hover); }
.data-table tbody tr:last-child td { border-bottom: none; }

/* ── Misc ────────────────────────────────────────────────── */
.empty-msg { font-size: 12px; padding: 1.25rem 0; }
.empty-msg code {
  font-family: var(--font-data);
  font-size: 11px;
  color: var(--cyan-dim);
  background: rgba(0,200,255,0.06);
  padding: 1px 5px;
  border-radius: 3px;
}

@media (max-width: 760px) {
  .grid-2col { grid-template-columns: 1fr; }
}
</style>
