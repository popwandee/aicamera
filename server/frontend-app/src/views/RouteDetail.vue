<template>
  <div class="route-detail">

    <!-- Breadcrumb -->
    <div class="breadcrumb">
      <span class="back-link" @click="$router.push('/routes')">⟶ Routes</span>
      <span class="sep">›</span>
      <span class="crumb-current font-data">{{ routeKey }}</span>
    </div>

    <!-- Loading -->
    <div class="skeleton-card" v-if="store.loading" />

    <!-- Content -->
    <template v-else>

      <!-- Route title -->
      <div class="page-header">
        <div class="route-label">
          <span
            v-for="(cam, i) in routeCameras"
            :key="cam + i"
          ><span class="cam-chip">{{ cam }}</span><span
            v-if="i < routeCameras.length - 1"
            class="arrow-sep"
          > → </span></span>
        </div>
        <div class="page-desc">All vehicles that followed this exact camera sequence</div>
      </div>

      <!-- KPI row -->
      <div class="kpi-row" v-if="routeObj">
        <MetricCard icon="⟶" label="Total Trips"   :value="routeObj.tripCount.toString()"      accent="cyan"  />
        <MetricCard icon="⊙" label="Unique Plates"  :value="routeObj.uniquePlates.toString()"   accent="green" />
        <MetricCard icon="◷" label="Avg Duration"   :value="fmtDuration(routeObj.avgDurationMin)" accent="amber" />
        <MetricCard icon="▣" label="Cameras"        :value="routeObj.cameraCount.toString()"    accent="cyan"  />
      </div>

      <!-- F5: Camera node chain -->
      <div class="panel section-panel" v-if="routeCameras.length > 1">
        <div class="section-head">F5 · Camera Node Chain</div>
        <div class="chain-wrap">
          <svg
            :width="nodeChain.width"
            :height="nodeChain.height"
            :viewBox="`0 0 ${nodeChain.width} ${nodeChain.height}`"
            class="chain-svg"
          >
            <defs>
              <marker id="rd-arrow" viewBox="0 0 8 8" refX="7" refY="4"
                      markerWidth="5" markerHeight="5" orient="auto">
                <path d="M 0 0 L 8 4 L 0 8 z" fill="#00c8ff" />
              </marker>
            </defs>

            <!-- Arrow legs -->
            <g v-for="(arr, i) in nodeChain.arrows" :key="'arr-' + i">
              <line
                :x1="arr.x1" :y1="arr.y"
                :x2="arr.x2 - 5" :y2="arr.y"
                stroke="rgba(0,200,255,0.55)"
                stroke-width="2"
                marker-end="url(#rd-arrow)"
              />
              <text
                :x="arr.midX" :y="arr.y - 10"
                text-anchor="middle"
                font-size="11" font-weight="bold"
                font-family="JetBrains Mono, monospace"
                fill="#00c8ff"
              >{{ arr.count }}</text>
            </g>

            <!-- Camera nodes (over arrows) -->
            <g v-for="node in nodeChain.nodes" :key="node.id">
              <rect
                :x="node.x" :y="node.y"
                width="100" height="44"
                rx="5"
                fill="rgba(8,12,18,0.96)"
                stroke="#00c8ff"
                stroke-width="1.5"
              />
              <text
                :x="node.x + 50" :y="node.y + 17"
                text-anchor="middle"
                font-size="10" font-weight="bold"
                font-family="JetBrains Mono, monospace"
                fill="#00c8ff"
              >{{ shortCam(node.id) }}</text>
              <text
                :x="node.x + 50" :y="node.y + 32"
                text-anchor="middle"
                font-size="8"
                font-family="JetBrains Mono, monospace"
                fill="rgba(120,160,200,0.45)"
              >{{ node.id }}</text>
            </g>
          </svg>
        </div>
      </div>

      <!-- Single-camera route note -->
      <div class="panel section-panel info-panel" v-else-if="routeCameras.length === 1">
        <span class="text-muted">Single-camera route — vehicle seen on </span>
        <span class="cam-chip">{{ routeCameras[0] }}</span>
        <span class="text-muted"> only</span>
      </div>

      <!-- Trips table -->
      <div class="panel section-panel">
        <div class="section-head">
          Trips
          <span class="section-sub">{{ routeTrips.length }} total</span>
        </div>

        <div class="empty-msg text-muted" v-if="!routeTrips.length">
          No trips found for this route key
        </div>

        <table class="data-table" v-else>
          <thead>
            <tr>
              <th>License Plate</th>
              <th>Start</th>
              <th>End</th>
              <th>Duration</th>
              <th>Cameras</th>
              <th>Detections</th>
              <th>View</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="trip in routeTrips" :key="trip.plate + trip.startTs">
              <td><PlateTag :plate="trip.plate" size="sm" /></td>
              <td class="font-data text-secondary">{{ fmtTs(trip.startTs) }}</td>
              <td class="font-data text-secondary">{{ fmtTs(trip.endTs) }}</td>
              <td class="font-data text-amber">{{ fmtDuration(trip.durationMin) }}</td>
              <td class="font-data text-muted">{{ trip.cameraCount }}</td>
              <td class="font-data text-muted">{{ trip.detections }}</td>
              <td>
                <router-link
                  v-if="trip.firstDetId"
                  :to="'/detections/' + trip.firstDetId"
                  class="view-link"
                  @click.stop
                >↗</router-link>
                <span v-else class="text-muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </template>

    <div v-if="store.error" class="error-banner">⚠ {{ store.error }}</div>

  </div>
</template>

<script>
import MetricCard from '@/components/shared/MetricCard.vue';
import PlateTag   from '@/components/shared/PlateTag.vue';
import { useRoutesStore } from '@/stores/routes.store.js';

// Node chain layout constants
const NW  = 100;   // node width
const NH  = 44;    // node height
const GAP = 70;    // gap between nodes (space for arrow)
const PAD = 30;    // left/right padding

export default {
  name: 'RouteDetail',
  components: { MetricCard, PlateTag },
  props: {
    routeKey: { type: String, required: true },
  },

  setup() {
    return { store: useRoutesStore() };
  },

  mounted() {
    if (!this.store.detections.length) {
      this.store.fetchDetections();
    }
  },

  computed: {
    // Camera sequence for this route (derived from routeKey string)
    routeCameras() {
      return this.routeKey.split(' → ').filter(Boolean);
    },

    // Matching route summary object from store
    routeObj() {
      return this.store.routes.find(r => r.routeKey === this.routeKey) || null;
    },

    // Trips that match this routeKey, newest first
    routeTrips() {
      return this.store.trips
        .filter(t => t.routeKey === this.routeKey)
        .sort((a, b) => b.startTs - a.startTs);
    },

    // F5: SVG node chain data
    nodeChain() {
      const cameras = this.routeCameras;
      const N       = cameras.length;
      if (!N) return { nodes: [], arrows: [], width: 300, height: 100 };

      // Count trips on each leg
      const legCounts = {};
      this.routeTrips.forEach(t => {
        for (let i = 0; i < t.cameras.length - 1; i++) {
          const key = `${t.cameras[i]}|||${t.cameras[i + 1]}`;
          legCounts[key] = (legCounts[key] || 0) + 1;
        }
      });

      const CY = PAD + NH / 2;   // node vertical centre
      const totalWidth = PAD * 2 + N * NW + (N - 1) * GAP;

      const nodes = cameras.map((cam, i) => ({
        id: cam,
        x:  PAD + i * (NW + GAP),
        y:  PAD,
      }));

      const arrows = [];
      for (let i = 0; i < N - 1; i++) {
        const x1  = nodes[i].x + NW;
        const x2  = nodes[i + 1].x;
        const key = `${cameras[i]}|||${cameras[i + 1]}`;
        arrows.push({
          x1, x2,
          midX:  (x1 + x2) / 2,
          y:     CY,
          count: legCounts[key] || 0,
        });
      }

      return { nodes, arrows, width: totalWidth, height: NH + PAD * 2 };
    },
  },

  methods: {
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
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },
  },
};
</script>

<style scoped>
.route-detail { max-width: 1100px; }

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 1.25rem;
}
.back-link { color: var(--cyan-dim); cursor: pointer; transition: color var(--transition); }
.back-link:hover { color: var(--cyan); }
.sep { opacity: 0.4; }
.crumb-current { color: var(--text-secondary); max-width: 520px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Loading skeleton */
.skeleton-card {
  height: 340px;
  background: linear-gradient(90deg, var(--bg-panel) 25%, var(--bg-surface) 50%, var(--bg-panel) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Page header */
.page-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.route-label {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  margin-bottom: 6px;
}
.page-desc { font-size: 12px; color: var(--text-secondary); }

/* KPI row */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

/* Panels */
.section-panel { margin-bottom: 1.5rem; }
.info-panel    { padding: 0.9rem 1.25rem; font-size: 13px; }

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

/* Camera chips + arrow */
.cam-chip {
  font-size: 12px;
  font-family: var(--font-data);
  color: var(--cyan-dim);
  background: rgba(0,200,255,0.06);
  border: 1px solid rgba(0,200,255,0.18);
  border-radius: 3px;
  padding: 2px 7px;
}
.arrow-sep { color: var(--text-muted); font-size: 11px; }

/* F5 Node chain */
.chain-wrap { overflow-x: auto; overflow-y: hidden; }
.chain-svg  { display: block; }

/* Trips table */
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

.view-link {
  color: var(--cyan-dim);
  text-decoration: none;
  font-size: 14px;
  font-family: var(--font-data);
  transition: color var(--transition);
}
.view-link:hover { color: var(--cyan); }

/* Misc */
.empty-msg { font-size: 12px; padding: 1rem 0; }
.text-secondary { color: var(--text-secondary); }
.text-amber     { color: var(--amber); }

.error-banner {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: var(--red-dim);
  border: 1px solid rgba(255,61,87,0.3);
  border-radius: var(--radius-md);
  color: var(--red);
  font-size: 13px;
}

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
</style>
