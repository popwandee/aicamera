<template>
  <div class="convoy-detection">

    <!-- Page header -->
    <div class="page-header">
      <div class="page-title font-display">
        <span class="page-icon">⫸</span> Convoy Detection
      </div>
      <div class="page-desc">Vehicle pairs repeatedly observed together across multiple cameras within the same time window</div>
    </div>

    <!-- Loading skeleton -->
    <div class="skeleton-card" v-if="loading" />

    <template v-else>

      <!-- Controls panel -->
      <div class="panel controls-panel">
        <div class="ctrl-row">
          <div class="ctrl-group">
            <label class="ctrl-label">Time Window</label>
            <select class="ctrl-select" v-model.number="windowMin">
              <option :value="2">2 min</option>
              <option :value="5">5 min</option>
              <option :value="10">10 min</option>
              <option :value="15">15 min</option>
              <option :value="30">30 min</option>
            </select>
          </div>
          <div class="ctrl-group">
            <label class="ctrl-label">Min Cameras</label>
            <select class="ctrl-select" v-model.number="minCameras">
              <option :value="2">≥ 2</option>
              <option :value="3">≥ 3</option>
              <option :value="4">≥ 4</option>
            </select>
          </div>
          <div class="ctrl-group">
            <label class="ctrl-label">From</label>
            <input type="date" class="ctrl-input" v-model="filterDateFrom" />
          </div>
          <div class="ctrl-group">
            <label class="ctrl-label">To</label>
            <input type="date" class="ctrl-input" v-model="filterDateTo" />
          </div>
          <button class="ctrl-btn" @click="clearFilters">Reset</button>
        </div>
      </div>

      <!-- KPI row -->
      <div class="kpi-row">
        <MetricCard icon="⫸" label="Convoys Found"    :value="convoys.length.toString()"    accent="cyan"  />
        <MetricCard icon="◈" label="Vehicles Tracked" :value="uniqueVehicles.toString()"     accent="green" />
        <MetricCard icon="▣" label="Cameras Involved" :value="uniqueCamerasCount.toString()" accent="amber" />
        <MetricCard icon="◷" label="Avg Duration"     :value="fmtDuration(avgDuration)"       accent="cyan"  />
      </div>

      <!-- Empty state -->
      <div class="panel section-panel empty-panel" v-if="!convoys.length">
        <span class="text-muted">No convoys detected with current settings. Try a wider time window or fewer cameras.</span>
      </div>

      <template v-else>

        <!-- Convoy list table -->
        <div class="panel section-panel">
          <div class="section-head">
            Detected Convoys
            <span class="section-sub">{{ convoys.length }} pairs · click row to view timeline</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>Plate Pair</th>
                <th>Cameras</th>
                <th>First Seen</th>
                <th>Last Seen</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="c in convoys"
                :key="c.id"
                :class="['clickable-row', { 'row-selected': selectedId === c.id }]"
                @click="selectedId = selectedId === c.id ? null : c.id"
              >
                <td>
                  <span v-for="p in c.plates" :key="p" class="plate-pill font-data">{{ p }}</span>
                </td>
                <td>
                  <span v-for="cam in c.cameras" :key="cam" class="cam-chip">{{ shortCam(cam) }}</span>
                </td>
                <td class="font-data text-secondary">{{ fmtTs(c.firstSeen) }}</td>
                <td class="font-data text-secondary">{{ fmtTs(c.lastSeen) }}</td>
                <td class="font-data text-amber">{{ fmtDuration(c.durationMin) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Parallel timeline SVG panel -->
        <div class="panel section-panel" v-if="selectedConvoy && convoyTimeline">
          <div class="section-head">
            Parallel Timeline
            <span class="section-sub">{{ selectedConvoy.plates.join(' & ') }}</span>
          </div>
          <div class="timeline-wrap">
            <svg
              :width="convoyTimeline.svgWidth"
              :height="convoyTimeline.svgHeight"
              :viewBox="`0 0 ${convoyTimeline.svgWidth} ${convoyTimeline.svgHeight}`"
              class="timeline-svg"
            >
              <!-- Lane backgrounds -->
              <rect
                v-for="lane in convoyTimeline.lanes"
                :key="'bg-' + lane.plate"
                x="0"
                :y="lane.bgY"
                :width="convoyTimeline.svgWidth"
                :height="lane.bgH"
                :fill="lane.bgFill"
              />

              <!-- Horizontal baselines -->
              <line
                v-for="lane in convoyTimeline.lanes"
                :key="'base-' + lane.plate"
                :x1="lane.baseX1" :y1="lane.laneY"
                :x2="lane.baseX2" :y2="lane.laneY"
                stroke="rgba(0,200,255,0.12)"
                stroke-width="1"
              />

              <!-- Sync lines: co-sighting at same camera within window -->
              <line
                v-for="(sl, si) in convoyTimeline.syncLines"
                :key="'sl-' + si"
                :x1="sl.x" :y1="sl.y1"
                :x2="sl.x" :y2="sl.y2"
                :stroke="sl.color"
                stroke-width="1.5"
                stroke-dasharray="4 3"
                opacity="0.5"
              />

              <!-- Plate labels (right-aligned before timeline) -->
              <text
                v-for="lane in convoyTimeline.lanes"
                :key="'lbl-' + lane.plate"
                :x="lane.labelX"
                :y="lane.labelY"
                text-anchor="end"
                font-size="11"
                font-weight="bold"
                font-family="JetBrains Mono, monospace"
                fill="rgba(0,200,255,0.75)"
              >{{ lane.shortPlate }}</text>

              <!-- Detection dots (colored by camera) -->
              <g v-for="lane in convoyTimeline.lanes" :key="'dots-' + lane.plate">
                <circle
                  v-for="(dot, di) in lane.dots"
                  :key="'d-' + di"
                  :cx="dot.x"
                  :cy="dot.y"
                  r="5"
                  :fill="dot.color"
                  opacity="0.85"
                >
                  <title>{{ dot.cam }} · {{ dot.label }}</title>
                </circle>
              </g>

              <!-- X-axis line -->
              <line
                :x1="convoyTimeline.axisX1"
                :y1="convoyTimeline.axisY"
                :x2="convoyTimeline.axisX2"
                :y2="convoyTimeline.axisY"
                stroke="rgba(0,200,255,0.25)"
                stroke-width="1"
              />

              <!-- X-axis ticks and time labels -->
              <g v-for="(xl, xi) in convoyTimeline.xLabels" :key="'xl-' + xi">
                <line
                  :x1="xl.x" :y1="convoyTimeline.axisY"
                  :x2="xl.x" :y2="convoyTimeline.axisY + 5"
                  stroke="rgba(0,200,255,0.35)"
                  stroke-width="1"
                />
                <text
                  :x="xl.x"
                  :y="convoyTimeline.axisY + 17"
                  text-anchor="middle"
                  font-size="9"
                  font-family="JetBrains Mono, monospace"
                  fill="rgba(120,160,200,0.55)"
                >{{ xl.label }}</text>
              </g>

              <!-- Camera color legend -->
              <g v-for="lg in convoyTimeline.legend" :key="'lg-' + lg.cam">
                <circle :cx="lg.cx" :cy="lg.cy" r="4" :fill="lg.color" />
                <text
                  :x="lg.tx"
                  :y="lg.ty"
                  font-size="9"
                  font-family="JetBrains Mono, monospace"
                  fill="rgba(120,160,200,0.65)"
                >{{ shortCam(lg.cam) }}</text>
              </g>
            </svg>
          </div>
        </div>

      </template>
    </template>

    <div v-if="error" class="error-banner">⚠ {{ error }}</div>

  </div>
</template>

<script>
import MetricCard from '@/components/shared/MetricCard.vue';
import api        from '@/api/index.js';

// Timeline SVG layout
const LABEL_W    = 92;
const TL_W       = 580;
const LANE_H     = 74;
const PAD_TOP    = 20;
const PAD_BOT    = 46;
const CAM_COLORS = ['#00c8ff', '#00e676', '#ffab40', '#b388ff', '#ff3d57', '#80cbc4', '#ff8f00'];

// Sliding-window convoy algorithm.
// Returns pairs of plates that co-appear at ≥ minCameras within windowMs of each other.
function findConvoys(detections, windowMs, minCameras) {
  const byPlate = {};
  const byCam   = {};

  detections.forEach(d => {
    const plate = d.licensePlate;
    if (!plate || plate.toLowerCase() === 'unknown') return;
    const cam = d.camera?.cameraId || d.cameraId || 'unknown';
    const ts  = new Date(d.timestamp).getTime();
    if (isNaN(ts)) return;
    const id = d.id;

    if (!byPlate[plate]) byPlate[plate] = [];
    byPlate[plate].push({ cam, ts, id });

    if (!byCam[cam]) byCam[cam] = [];
    byCam[cam].push({ plate, ts, id });
  });

  Object.values(byCam).forEach(evs => evs.sort((a, b) => a.ts - b.ts));

  // For each camera, use a sliding window to find plate pairs within windowMs
  const pairCams = {};
  for (const [cam, evs] of Object.entries(byCam)) {
    for (let i = 0; i < evs.length; i++) {
      for (let j = i + 1; j < evs.length; j++) {
        if (evs[j].ts - evs[i].ts > windowMs) break;
        if (evs[i].plate === evs[j].plate) continue;
        const key = [evs[i].plate, evs[j].plate].sort().join('|||');
        if (!pairCams[key]) pairCams[key] = new Set();
        pairCams[key].add(cam);
      }
    }
  }

  const convoys = [];
  for (const [key, camSet] of Object.entries(pairCams)) {
    if (camSet.size < minCameras) continue;
    const [p1, p2] = key.split('|||');
    const cameras  = [...camSet].sort();

    const timelines = {};
    const allTs = [];
    [p1, p2].forEach(plate => {
      const evts = (byPlate[plate] || [])
        .filter(e => camSet.has(e.cam))
        .sort((a, b) => a.ts - b.ts);
      timelines[plate] = evts.map(e => ({ cam: e.cam, ts: e.ts, id: e.id }));
      evts.forEach(e => allTs.push(e.ts));
    });

    if (!allTs.length) continue;
    const minTs = Math.min(...allTs);
    const maxTs = Math.max(...allTs);

    convoys.push({
      id:          key,
      plates:      [p1, p2],
      cameras,
      camCount:    camSet.size,
      timelines,
      firstSeen:   new Date(minTs),
      lastSeen:    new Date(maxTs),
      durationMin: Math.round((maxTs - minTs) / 60000),
    });
  }

  return convoys.sort((a, b) => b.camCount - a.camCount || b.firstSeen - a.firstSeen);
}

export default {
  name: 'ConvoyDetection',
  components: { MetricCard },

  data() {
    return {
      rawDetections:  [],
      loading:        false,
      error:          null,
      windowMin:      10,
      minCameras:     2,
      selectedId:     null,
      filterDateFrom: '',
      filterDateTo:   '',
    };
  },

  mounted() {
    this.fetchDetections();
  },

  watch: {
    windowMin()      { this.selectedId = null; },
    minCameras()     { this.selectedId = null; },
    filterDateFrom() { this.selectedId = null; },
    filterDateTo()   { this.selectedId = null; },
  },

  computed: {
    windowMs() {
      return this.windowMin * 60000;
    },

    filteredDetections() {
      let dets = this.rawDetections;
      if (this.filterDateFrom) {
        const from = new Date(this.filterDateFrom + 'T00:00:00').getTime();
        dets = dets.filter(d => new Date(d.timestamp).getTime() >= from);
      }
      if (this.filterDateTo) {
        const to = new Date(this.filterDateTo + 'T23:59:59').getTime();
        dets = dets.filter(d => new Date(d.timestamp).getTime() <= to);
      }
      return dets;
    },

    convoys() {
      return findConvoys(this.filteredDetections, this.windowMs, this.minCameras);
    },

    selectedConvoy() {
      if (!this.selectedId) return null;
      return this.convoys.find(c => c.id === this.selectedId) || null;
    },

    uniqueVehicles() {
      const plates = new Set();
      this.convoys.forEach(c => c.plates.forEach(p => plates.add(p)));
      return plates.size;
    },

    uniqueCamerasCount() {
      const cams = new Set();
      this.convoys.forEach(c => c.cameras.forEach(cam => cams.add(cam)));
      return cams.size;
    },

    avgDuration() {
      if (!this.convoys.length) return 0;
      const total = this.convoys.reduce((s, c) => s + c.durationMin, 0);
      return Math.round(total / this.convoys.length);
    },

    // Fully pre-computed SVG data for the selected convoy's parallel timeline
    convoyTimeline() {
      const c = this.selectedConvoy;
      if (!c) return null;

      const allTs = [];
      c.plates.forEach(p => (c.timelines[p] || []).forEach(e => allTs.push(e.ts)));
      if (!allTs.length) return null;

      const minTs = Math.min(...allTs);
      const maxTs = Math.max(...allTs);
      const span  = Math.max(maxTs - minTs, 60000);

      const camIndex = {};
      c.cameras.forEach((cam, i) => { camIndex[cam] = i; });

      const tsToX = ts => LABEL_W + ((ts - minTs) / span) * TL_W;

      const svgWidth  = LABEL_W + TL_W + 20;
      const axisY     = PAD_TOP + c.plates.length * LANE_H;
      const svgHeight = axisY + PAD_BOT;
      const legendY   = svgHeight - 14;

      const lanes = c.plates.map((plate, li) => {
        const laneY = PAD_TOP + li * LANE_H + LANE_H / 2;
        return {
          plate,
          shortPlate: plate.length > 9 ? plate.slice(0, 8) + '…' : plate,
          laneY,
          bgY:    laneY - LANE_H / 2,
          bgH:    LANE_H,
          bgFill: li % 2 === 0 ? 'rgba(0,200,255,0.025)' : 'rgba(0,0,0,0)',
          labelX: LABEL_W - 6,
          labelY: laneY + 4,
          baseX1: LABEL_W,
          baseX2: LABEL_W + TL_W,
          dots: (c.timelines[plate] || []).map(e => ({
            x:     tsToX(e.ts),
            y:     laneY,
            color: CAM_COLORS[camIndex[e.cam] % CAM_COLORS.length],
            cam:   e.cam,
            label: new Date(e.ts).toLocaleTimeString('th-TH'),
            id:    e.id,
          })),
        };
      });

      // Dashed vertical sync lines where both plates co-appear at the same camera within windowMs
      const syncLines = [];
      if (c.plates.length === 2) {
        const e1s = c.timelines[c.plates[0]] || [];
        const e2s = c.timelines[c.plates[1]] || [];
        e1s.forEach(e1 => {
          e2s.forEach(e2 => {
            if (e1.cam !== e2.cam) return;
            if (Math.abs(e1.ts - e2.ts) > this.windowMs) return;
            syncLines.push({
              x:     tsToX((e1.ts + e2.ts) / 2),
              y1:    lanes[0].laneY,
              y2:    lanes[1].laneY,
              color: CAM_COLORS[camIndex[e1.cam] % CAM_COLORS.length],
            });
          });
        });
      }

      // X-axis: auto-select interval so we get ≤ 8 ticks
      const intervals = [30000, 60000, 120000, 300000, 600000, 1800000, 3600000];
      const iv = intervals.find(i => span / i <= 8) || 3600000;
      const xLabels = [];
      const startTs = Math.ceil(minTs / iv) * iv;
      for (let ts = startTs; ts <= maxTs; ts += iv) {
        xLabels.push({
          x:     tsToX(ts),
          label: new Date(ts).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
        });
      }

      // Camera legend, centered across SVG width
      const legSpacing = Math.min(120, (svgWidth - 20) / c.cameras.length);
      const legStart   = (svgWidth - c.cameras.length * legSpacing) / 2;
      const legend = c.cameras.map((cam, i) => ({
        cam,
        color: CAM_COLORS[i % CAM_COLORS.length],
        cx: legStart + i * legSpacing + 6,
        cy: legendY,
        tx: legStart + i * legSpacing + 15,
        ty: legendY + 4,
      }));

      return {
        lanes, syncLines, xLabels, legend,
        svgWidth, svgHeight, axisY,
        axisX1: LABEL_W,
        axisX2: LABEL_W + TL_W,
      };
    },
  },

  methods: {
    async fetchDetections() {
      this.loading = true;
      this.error   = null;
      try {
        this.rawDetections = await api.getDetections({
          limit:     2000,
          sortBy:    'timestamp',
          sortOrder: 'DESC',
        });
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },

    clearFilters() {
      this.filterDateFrom = '';
      this.filterDateTo   = '';
      this.windowMin      = 10;
      this.minCameras     = 2;
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

    fmtTs(dt) {
      if (!dt) return '—';
      return new Date(dt).toLocaleString('th-TH', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
      });
    },
  },
};
</script>

<style scoped>
.convoy-detection { max-width: 1100px; }

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
  height: 340px;
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
.controls-panel { padding: 0.9rem 1.25rem; margin-bottom: 1rem; }
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
.ctrl-select:focus,
.ctrl-input:focus { border-color: var(--cyan-dim); }
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
.ctrl-btn:hover { background: rgba(0,200,255,0.14); }

/* KPI row */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

/* Section panels */
.section-panel { margin-bottom: 1.5rem; }
.empty-panel { padding: 1.2rem 1.25rem; font-size: 13px; }

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

/* Plate pills */
.plate-pill {
  display: inline-block;
  font-size: 12px;
  color: var(--text-primary);
  background: rgba(0,200,255,0.07);
  border: 1px solid rgba(0,200,255,0.20);
  border-radius: 3px;
  padding: 1px 6px;
  margin-right: 4px;
}

/* Camera chips */
.cam-chip {
  display: inline-block;
  font-size: 11px;
  font-family: var(--font-data);
  color: var(--cyan-dim);
  background: rgba(0,200,255,0.06);
  border: 1px solid rgba(0,200,255,0.18);
  border-radius: 3px;
  padding: 1px 6px;
  margin-right: 3px;
}

/* Convoy table */
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
.data-table tbody tr:last-child td { border-bottom: none; }

.clickable-row { cursor: pointer; }
.clickable-row:hover td { background: var(--bg-hover); }
.row-selected td {
  background: rgba(0,200,255,0.06);
  border-bottom-color: rgba(0,200,255,0.10);
}
.row-selected:hover td { background: rgba(0,200,255,0.09); }

/* Timeline SVG */
.timeline-wrap { overflow-x: auto; overflow-y: hidden; }
.timeline-svg  { display: block; }

/* Misc */
.text-secondary { color: var(--text-secondary); }
.text-amber     { color: var(--amber); }
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
