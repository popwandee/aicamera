<template>
  <div class="route-analysis">

    <!-- Page header -->
    <div class="page-header">
      <div class="page-title font-display">
        <span class="page-icon">⟶</span> Route Analysis
      </div>
      <div class="page-desc">
        Vehicle routes computed from detection sequences — 2 h gap splits trips
      </div>
    </div>

    <!-- KPI row -->
    <div class="kpi-row">
      <MetricCard icon="⟶" label="Total Trips"        :value="store.totalTrips.toString()"       accent="cyan"  :loading="store.loading" />
      <MetricCard icon="⊕" label="Multi-Camera Trips" :value="store.multiCameraTrips.toString()"  accent="green" :loading="store.loading" />
      <MetricCard icon="⊙" label="Unique Plates"       :value="store.uniquePlatesTotal.toString()" accent="amber" :loading="store.loading" />
      <MetricCard icon="▣" label="Unique Routes"       :value="store.routes.length.toString()"    accent="cyan"  :loading="store.loading" />
    </div>

    <!-- Filter controls -->
    <div class="panel filter-panel">
      <div class="filter-row">
        <div class="filter-field">
          <label class="filter-label">Min cameras</label>
          <select class="filter-select" v-model.number="store.filterMinCameras">
            <option :value="1">Any</option>
            <option :value="2">≥ 2</option>
            <option :value="3">≥ 3</option>
            <option :value="4">≥ 4</option>
          </select>
        </div>
        <div class="filter-field filter-field-wide">
          <label class="filter-label">Search camera / route</label>
          <input class="filter-input"
                 v-model="searchInput"
                 @input="debouncedSearch"
                 placeholder="e.g. aicamera2…" />
        </div>
        <div class="filter-field">
          <label class="filter-label">Date from</label>
          <input class="filter-input" type="date" v-model="store.filterDateFrom" />
        </div>
        <div class="filter-field">
          <label class="filter-label">Date to</label>
          <input class="filter-input" type="date" v-model="store.filterDateTo" />
        </div>
        <button class="btn" @click="clearFilters">Clear</button>
      </div>
    </div>

    <!-- F3: Camera flow diagram -->
    <div class="panel section-panel">
      <div class="section-head">
        F3 · Camera Flow Diagram
        <span class="section-sub">arc width = trip count · cyan = forward · amber = reverse</span>
      </div>

      <div class="flow-wrap" v-if="!store.loading && svgFlowData.nodes.length">
        <svg
          :width="svgFlowData.width"
          height="240"
          :viewBox="`0 0 ${svgFlowData.width} 240`"
          class="flow-svg"
        >
          <defs>
            <!-- Forward arrow (cyan) -->
            <marker id="ra-fwd" viewBox="0 0 8 8" refX="7" refY="4"
                    markerWidth="5" markerHeight="5" orient="auto">
              <path d="M 0 0 L 8 4 L 0 8 z" fill="#00c8ff" />
            </marker>
            <!-- Backward arrow (amber) -->
            <marker id="ra-bwd" viewBox="0 0 8 8" refX="7" refY="4"
                    markerWidth="5" markerHeight="5" orient="auto">
              <path d="M 0 0 L 8 4 L 0 8 z" fill="#ffab40" />
            </marker>
          </defs>

          <!-- Arcs (drawn behind nodes) -->
          <path
            v-for="arc in svgFlowData.arcs"
            :key="arc.key"
            :d="arc.d"
            :stroke="arc.color"
            :stroke-width="arc.strokeW"
            fill="none"
            stroke-linecap="round"
            :marker-end="arc.forward ? 'url(#ra-fwd)' : 'url(#ra-bwd)'"
          />

          <!-- Arc count labels -->
          <text
            v-for="arc in svgFlowData.arcs"
            :key="'lbl-' + arc.key"
            :x="arc.midX"
            :y="arc.midY"
            text-anchor="middle"
            font-size="11"
            font-family="JetBrains Mono, monospace"
            font-weight="bold"
            :fill="arc.labelColor"
          >{{ arc.count }}</text>

          <!-- Camera nodes (drawn over arcs) -->
          <g v-for="node in svgFlowData.nodes" :key="node.id">
            <circle
              :cx="node.x" cy="140" r="32"
              fill="rgba(8,12,18,0.96)"
              stroke="#00c8ff"
              stroke-width="1.5"
            />
            <text
              :x="node.x" y="136"
              text-anchor="middle"
              font-size="10" font-weight="bold"
              font-family="JetBrains Mono, monospace"
              fill="#00c8ff"
            >{{ shortCam(node.id) }}</text>
            <text
              :x="node.x" y="150"
              text-anchor="middle"
              font-size="9"
              font-family="JetBrains Mono, monospace"
              fill="rgba(160,200,230,0.55)"
            >{{ node.count }}</text>
            <text
              :x="node.x" y="184"
              text-anchor="middle"
              font-size="9"
              font-family="JetBrains Mono, monospace"
              fill="rgba(120,160,200,0.45)"
            >{{ node.id }}</text>
          </g>
        </svg>
      </div>

      <div class="skeleton-chart" style="height:240px" v-else-if="store.loading" />
      <div class="empty-msg text-muted" v-else>
        No route data — fetch detections or adjust filters
      </div>
    </div>

    <!-- Route list table -->
    <div class="panel section-panel">
      <div class="section-head">
        Routes
        <span class="section-sub">{{ store.filteredRoutes.length }} shown</span>
      </div>

      <div class="skeleton-chart" style="height:120px" v-if="store.loading" />

      <div class="empty-msg text-muted" v-else-if="!store.filteredRoutes.length">
        No routes match the current filters
      </div>

      <table class="data-table" v-else>
        <thead>
          <tr>
            <th>Route</th>
            <th>Cams</th>
            <th>Trips</th>
            <th>Plates</th>
            <th>Avg Duration</th>
            <th>Last Seen</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="route in store.filteredRoutes"
            :key="route.routeKey"
            class="clickable-row"
            @click="goRoute(route)"
          >
            <td class="route-key-cell font-data">
              <span
                v-for="(cam, i) in route.cameras"
                :key="cam + i"
              ><span class="cam-chip">{{ cam }}</span><span
                v-if="i < route.cameras.length - 1"
                class="arrow-sep"
              > → </span></span>
            </td>
            <td class="font-data text-muted">{{ route.cameraCount }}</td>
            <td class="font-data text-cyan">{{ route.tripCount }}</td>
            <td class="font-data text-green">{{ route.uniquePlates }}</td>
            <td class="font-data text-secondary">{{ fmtDuration(route.avgDurationMin) }}</td>
            <td class="font-data text-muted">{{ fmtTs(route.lastSeen) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <ErrorBanner :message="store.error" @retry="retry" />

  </div>
</template>

<script>
import MetricCard   from '@/components/shared/MetricCard.vue';
import ErrorBanner  from '@/components/shared/ErrorBanner.vue';
import { useRoutesStore } from '@/stores/routes.store.js';

// Flow diagram layout constants
const PAD      = 100;   // left/right padding
const SPACING  = 160;   // distance between camera node centres
const CY       = 140;   // node centre y
const R        = 32;    // node radius
const OFFSET   = R + 3; // arc start/end offset from node edge

export default {
  name: 'RouteAnalysis',
  components: { MetricCard, ErrorBanner },

  setup() {
    return { store: useRoutesStore() };
  },

  data() {
    return {
      searchInput:   '',
      debounceTimer: null,
    };
  },

  mounted() {
    this.searchInput = this.store.filterSearch;
    if (!this.store.detections.length) {
      this.store.fetchDetections();
    }
  },

  computed: {
    // SVG data for F3 flow diagram
    svgFlowData() {
      const cameras = this.store.allCameraIds;
      const N       = cameras.length;
      if (!N) return { nodes: [], arcs: [], width: 400 };

      // Pre-count detections per camera
      const countMap = {};
      this.store.detections.forEach(d => {
        const cam = d.camera?.cameraId || d.cameraId;
        if (cam) countMap[cam] = (countMap[cam] || 0) + 1;
      });

      // Camera x-positions
      const xOf = {};
      cameras.forEach((cam, i) => { xOf[cam] = PAD + i * SPACING; });

      const nodes = cameras.map(cam => ({
        id:    cam,
        x:     xOf[cam],
        count: countMap[cam] || 0,
      }));

      const transitions = this.store.transitions;
      const maxCount    = Math.max(1, ...transitions.map(t => t.count));

      const arcs = transitions.map(t => {
        const xi = xOf[t.from];
        const xj = xOf[t.to];
        if (xi == null || xj == null || xi === xj) return null;

        const forward = xj > xi;
        // Arc height increases with camera distance
        const arcH = 38 + Math.abs(xj - xi) * 0.14;
        const strokeW = 1.5 + (t.count / maxCount) * 7;

        let d, midX, midY;
        if (forward) {
          const sx = xi + OFFSET, ex = xj - OFFSET;
          const cy1 = CY - arcH;
          d    = `M ${sx} ${CY} C ${sx} ${cy1}, ${ex} ${cy1}, ${ex} ${CY}`;
          midX = (sx + ex) / 2;
          midY = cy1 + 10;
        } else {
          const sx = xi - OFFSET, ex = xj + OFFSET;
          const cy1 = CY + arcH;
          d    = `M ${sx} ${CY} C ${sx} ${cy1}, ${ex} ${cy1}, ${ex} ${CY}`;
          midX = (sx + ex) / 2;
          midY = cy1 - 6;
        }

        return {
          key:        `${t.from}->${t.to}`,
          d,
          midX,
          midY,
          strokeW,
          count:      t.count,
          forward,
          color:      forward ? 'rgba(0,200,255,0.50)' : 'rgba(255,171,64,0.50)',
          labelColor: forward ? '#00c8ff' : '#ffab40',
        };
      }).filter(Boolean);

      const width = PAD * 2 + (N - 1) * SPACING;
      return { nodes, arcs, width };
    },
  },

  methods: {
    retry() { this.store.fetchDetections(); },

    debouncedSearch() {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => {
        this.store.filterSearch = this.searchInput;
      }, 300);
    },

    clearFilters() {
      this.searchInput              = '';
      this.store.filterSearch       = '';
      this.store.filterDateFrom     = '';
      this.store.filterDateTo       = '';
      this.store.filterMinCameras   = 1;
    },

    goRoute(route) {
      this.$router.push({
        name:   'RouteDetail',
        params: { routeKey: route.routeKey },
      });
    },

    shortCam(id) {
      if (!id) return '??';
      const m = id.match(/(\d+)$/);
      if (m && m[1].length <= 2) return 'C' + m[1];
      return id.length > 7 ? id.slice(0, 6) + '…' : id;
    },

    fmtDuration(min) {
      if (!min || min <= 0) return '< 1m';
      if (min < 60) return `${min}m`;
      const h = Math.floor(min / 60);
      const m = min % 60;
      return m > 0 ? `${h}h ${m}m` : `${h}h`;
    },

    fmtTs(ts) {
      if (!ts) return '—';
      return new Date(ts).toLocaleString('th-TH', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
      });
    },
  },
};
</script>

<style scoped>
.route-analysis { max-width: 1200px; }

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

/* Panels */
.section-panel { margin-bottom: 1.5rem; }
.filter-panel  { margin-bottom: 1.5rem; padding: 1rem 1.25rem; }

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
  color: var(--text-muted);
  margin-left: 8px;
  opacity: 0.7;
}

/* Filter row */
.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
}
.filter-field { display: flex; flex-direction: column; gap: 4px; }
.filter-field-wide { flex: 1; min-width: 160px; }
.filter-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}
.filter-input,
.filter-select {
  background: var(--bg-surface);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-data);
  font-size: 12px;
  padding: 5px 8px;
  outline: none;
  transition: border-color var(--transition);
}
.filter-input:focus,
.filter-select:focus { border-color: var(--border-bright); }
.filter-select option { background: var(--bg-panel); }

/* F3 Flow diagram */
.flow-wrap { overflow-x: auto; overflow-y: hidden; }
.flow-svg  { display: block; }

/* Route list table */
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
  padding: 8px 12px;
  border-bottom: 1px solid rgba(0,200,255,0.05);
  color: var(--text-primary);
  vertical-align: middle;
}
.data-table tbody tr:hover td { background: var(--bg-hover); }
.data-table tbody tr:last-child td { border-bottom: none; }
.clickable-row { cursor: pointer; }

/* Route key display */
.route-key-cell { max-width: 420px; }
.cam-chip {
  font-size: 11px;
  color: var(--cyan-dim);
  background: rgba(0,200,255,0.06);
  border: 1px solid rgba(0,200,255,0.18);
  border-radius: 3px;
  padding: 1px 5px;
}
.arrow-sep {
  color: var(--text-muted);
  font-size: 10px;
}

/* Misc */
.skeleton-chart {
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

.empty-msg { font-size: 12px; padding: 1.25rem 0; }

.text-secondary { color: var(--text-secondary); }
</style>
