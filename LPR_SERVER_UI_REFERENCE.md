# LPR Server UI — Developer Reference

**Project**: AI Camera Dashboard (PWD Vision Works)  
**Server**: lprserver — Tailscale `100.95.46.128`  
**Live URL**: `http://100.95.46.128/server/`  
**Last updated**: 2026-04-26  
**Phases complete**: A (Foundation) · B (Dashboard + Chart) · C (Camera Management) · D (Detection Management) · E (Analytics Dashboard)

---

## 1. Infrastructure Overview

```
Client Browser
      │
      ▼
 Nginx :80 (lprserver)
 ├── /              → server/landing/index.html  (static landing)
 ├── /server/       → server/frontend-app/dist/  (Vue 3 SPA)
 ├── /server/api/   → backend-api :3000           (NestJS REST)
 └── /ws/           → ws-service :3001            (Socket.IO)
                              │
                    backend-api → PostgreSQL :5432 (aicamera_app)
                    mqtt-service ← aicamera2 MQTT :1883
```

### Server accounts

| User | Purpose | Password |
|------|---------|---------|
| `devuser` | application owner, deploy, npm, build | `admin88366` |
| `lpruser` | PostgreSQL owner | `admin88366` |

### Key paths on lprserver

| Path | Contents |
|------|---------|
| `/home/devuser/aicamera/server/frontend-app/` | Vue source + build |
| `/home/devuser/aicamera/server/frontend-app/dist/` | Built assets served by nginx |
| `/home/devuser/aicamera/server/backend-api/` | NestJS REST API |
| `/home/devuser/aicamera/server/ws-service/` | Socket.IO gateway |
| `/home/devuser/aicamera/server/mqtt-service/` | MQTT subscriber |
| `/home/devuser/aicamera/server/storage/` | Detection images from ws-service |
| `/etc/nginx/sites-available/lprserver` | Nginx config |

---

## 2. Tech Stack

### Frontend

| Package | Version | Role |
|---------|---------|------|
| Vue 3 | `^3.2.13` | UI framework |
| vue-router 4 | `^4.6.4` | SPA routing (history mode) |
| Pinia | `^3.0.4` | State management |
| pinia-plugin-persistedstate | `^4.7.1` | localStorage persistence (opt-in per store) |
| socket.io-client | `^4.8.3` | Socket.IO realtime |
| chart.js | `^4.4.0` | Charting engine |
| vue-chartjs | `^5.0.0` | Vue wrapper for chart.js |
| date-fns | `^3.6.0` | Date utilities (installed, available) |
| @vue/cli-service | `~5.0.0` | Build tool (Webpack, NOT Vite) |

**Build command**: `npm run build`  
**Output**: `dist/` — served by nginx at `/server/`  
**Router base**: auto-detected: `/server/` in production, `/` in dev

### ESLint rules that bite

- `vue/multi-word-component-names` — component `name:` must be ≥ 2 words (`MainDashboard`, not `Dashboard`)
- `vue/no-reserved-keys` — `data()` keys must not start with `_` or `$`
- `no-unused-vars` — Pinia getter arguments must actually be used; drop `state` param if only `this` is needed

---

## 3. Source File Map

```
server/frontend-app/src/
│
├── main.js                          Entry point; creates Vue app + Pinia + Router
├── App.vue                          Root shell: flex layout (Sidebar + router-view)
│
├── assets/
│   └── design-tokens.css            Global CSS variables, reset, utility classes
│
├── router/
│   └── index.js                     13 routes (see Section 5)
│
├── api/
│   └── index.js                     All HTTP calls to /server/api (see Section 7)
│
├── composables/
│   └── useSocket.js                 Socket.IO singleton (see Section 8)
│
├── stores/
│   ├── cameras.store.js             Pinia: cameras, edgeStatus, currentCamera — full CRUD
│   ├── detections.store.js          Pinia: filters, fetchFiltered, pagination getters, CSV-ready
│   └── analytics.store.js           Pinia: fetchAll() → analytics[] + detections[2000]; 8 getters (Phase E)
│
├── components/
│   ├── layout/
│   │   └── Sidebar.vue              Fixed 220px left nav (component name: AppSidebar)
│   ├── shared/
│   │   ├── MetricCard.vue           KPI card with icon + value + label
│   │   ├── StatusDot.vue            Colored pulsing dot (online/offline/warning/unknown)
│   │   ├── PlateTag.vue             Styled license plate badge — sm/md/lg (Phase D)
│   │   ├── ConfidenceBar.vue        Horizontal fill bar green/amber/red (Phase D)
│   │   ├── ImageViewer.vue          Full-screen image modal, ESC/click-outside (Phase D)
│   │   └── FilterBar.vue            Filter strip: plate/camera/date/confidence/archived (Phase D)
│   ├── charts/
│   │   └── HourlyChart.vue          24-bucket bar chart (vue-chartjs Bar)
│   └── cameras/
│       └── RegisterCameraModal.vue  Modal form: register a new camera (Phase C)
│
└── views/
    ├── MainDashboard.vue            ✅ Phase B — KPI + camera grid + hourly chart + feed
    ├── CameraList.vue               ✅ Phase C — filterable DataTable + register/delete
    ├── CameraDetail.vue             ✅ Phase C — 4-tab detail + health line chart
    ├── DetectionList.vue            ✅ Phase D — FilterBar + DataTable + pagination + CSV
    ├── DetectionDetail.vue          ✅ Phase D — full record, image viewer, archive toggle
    ├── AnalyticsDashboard.vue       ✅ Phase E — 30-day chart, histogram, heatmap, camera comparison, top plates
    ├── RouteAnalysis.vue            🔲 Phase F — stub
    ├── RouteDetail.vue              🔲 Phase F — stub
    ├── ConvoyDetection.vue          🔲 Phase G — stub
    ├── SystemEvents.vue             🔲 Phase H — stub
    ├── Settings.vue                 🔲 Phase H — stub
    ├── EdgeControl.vue              ✅ legacy (pre-design-system)
    ├── EdgeControlCamera.vue        ✅ legacy (pre-design-system)
    ├── ServerHome.vue               legacy (not routed in new SPA)
    ├── Network.vue                  legacy (not routed)
    └── Developer.vue                legacy (not routed)
```

### Backend API source

```
server/backend-api/src/
├── device/
│   ├── device.controller.ts   All REST routes (single controller)
│   └── device.service.ts      All DB queries (TypeORM repositories + DataSource)
├── entities/
│   ├── camera.entity.ts
│   ├── detection.entity.ts
│   ├── camera-health.entity.ts
│   ├── analytics.entity.ts
│   ├── analytics-event.entity.ts
│   ├── system-event.entity.ts
│   └── visualization.entity.ts
└── main.ts                    Global prefix: server/api, port 3000
```

---

## 4. Design System

### Color palette (`design-tokens.css`)

| Variable | Value | Use |
|----------|-------|-----|
| `--bg-void` | `#080c12` | Page background |
| `--bg-panel` | `#0d1520` | Cards, sidebar, panels |
| `--bg-surface` | `#111c2b` | Elevated surfaces, shimmer base |
| `--bg-hover` | `#162236` | Hover state backgrounds |
| `--border-dim` | `rgba(0,200,255,0.10)` | Subtle dividers |
| `--border-card` | `rgba(0,200,255,0.18)` | Card borders |
| `--border-bright` | `rgba(0,200,255,0.45)` | Hover / active borders |
| `--cyan` | `#00c8ff` | Brand accent, active state |
| `--cyan-dim` | `rgba(0,200,255,0.65)` | Secondary cyan |
| `--cyan-glow` | `0 0 12px rgba(0,200,255,0.35)` | text-shadow / filter glow |
| `--green` | `#00e676` | Online, success |
| `--amber` | `#ffab40` | Warning, temperature alert |
| `--red` | `#ff3d57` | Error, offline |
| `--purple` | `#b388ff` | Optional accent |
| `--text-primary` | `rgba(220,240,255,0.92)` | Body text |
| `--text-secondary` | `rgba(160,200,230,0.60)` | Dimmed text |
| `--text-muted` | `rgba(120,160,200,0.40)` | Labels, section headers |

### Typography

| Variable | Fonts | Use |
|----------|-------|-----|
| `--font-data` | JetBrains Mono → Courier New → monospace | Numbers, IDs, codes, timestamps |
| `--font-ui` | IBM Plex Sans → Segoe UI → sans-serif | Body, labels, nav |
| `--font-display` | Rajdhani → Impact → sans-serif | Page titles, brand name |
| `--font-thai` | Sarabun → Noto Sans Thai → sans-serif | License plate text |

All four loaded from Google Fonts in `public/index.html`.

### Global utility classes

| Class | Effect |
|-------|--------|
| `.font-data/display/thai` | Apply named font families |
| `.text-cyan/green/amber/red/muted` | Color shortcuts |
| `.panel` | Dark card: `bg-panel` + `border-card` + `radius-md` + `shadow-card` |
| `.badge` | Inline pill, monospace font |
| `.badge-cyan/green/amber/red` | Colored badge variants |
| `.btn` | Ghost button (cyan border, transparent bg) |
| `.btn-primary` | Filled button (cyan tinted bg) |

---

## 5. Routes

| Route | Name | Component | Status |
|-------|------|-----------|--------|
| `/` | Dashboard | `MainDashboard` | ✅ Live |
| `/cameras` | Cameras | `CameraList` | ✅ Live (Phase C) |
| `/cameras/:id` | CameraDetail | `CameraDetail` | ✅ Live (Phase C, props: true) |
| `/detections` | Detections | `DetectionList` | ✅ Live (Phase D) |
| `/detections/:id` | DetectionDetail | `DetectionDetail` | ✅ Live (Phase D, props: true) |
| `/analytics` | Analytics | `AnalyticsDashboard` | 🔲 Phase E |
| `/routes` | Routes | `RouteAnalysis` | 🔲 Phase F |
| `/routes/:routeKey` | RouteDetail | `RouteDetail` | 🔲 Phase F |
| `/convoy` | Convoy | `ConvoyDetection` | 🔲 Phase G |
| `/edge_control` | EdgeControl | `EdgeControl` | ✅ Live (legacy) |
| `/edge_control/camera/:id` | EdgeControlCamera | `EdgeControlCamera` | ✅ Live (legacy) |
| `/system` | System | `SystemEvents` | 🔲 Phase H |
| `/settings` | Settings | `Settings` | 🔲 Phase H |

**Nginx SPA fallback**: `try_files $uri $uri/ /server/index.html;` — no `=404` (breaks with `alias`).

**Router history base** — auto-detected at boot:
```javascript
const base = window.location.pathname.startsWith('/server') ? '/server/' : '/';
```

---

## 6. Components

### `App.vue`
Root shell. Flex row: `Sidebar` (fixed 220px) + `<router-view>` (flex-1, scrollable).  
Imports `design-tokens.css` globally.

---

### `Sidebar.vue` (name: `AppSidebar`)

1. Brand — `⬡ AICAM | Control Center`
2. Connection status — `StatusDot` from `useSocket().connected`
3. Nav Monitor: Dashboard · Cameras · Detections
4. Nav Analyse: Analytics · Routes · Convoy
5. Nav System: Edge Control · System Events · Settings
6. Footer — "PWD Vision Works"

---

### `MetricCard.vue`

```
Props: icon, label (required), value, sub, loading, accent ('cyan'|'green'|'amber'|'red')
```

---

### `StatusDot.vue`

```
Props: status ('online'|'offline'|'warning'|'unknown'), title
```
`online` → green pulse · `warning` → amber pulse · `offline` → red static · `unknown` → muted static

---

### `HourlyChart.vue`

```
Props: hourlyData  Array  [{ label: 'HH', count: N }, …]  24 items oldest-first
```
Registers `CategoryScale`, `LinearScale`, `BarElement`, `Tooltip`. Fixed height 180px. Cyan bars, tick every 4 h.

---

### `PlateTag.vue` *(Phase D)*

```
Props:
  plate  String  ''    License plate text (Thai or other)
  size   String  'md'  'sm' | 'md' | 'lg'
```

Renders a styled badge with `font-thai`, cyan border `rgba(0,200,255,0.28)`, background `rgba(0,200,255,0.06)`.  
`lg` size used in `DetectionDetail`; `sm` used in table rows.

---

### `ConfidenceBar.vue` *(Phase D)*

```
Props:
  value      Number|String   0    Raw decimal confidence (0–1), parseFloat() applied internally
  showLabel  Boolean         true Show percentage text beside the bar
```

Bar fill: green `--green` ≥ 90% · amber `--amber` ≥ 70% · red `--red` < 70%.

---

### `ImageViewer.vue` *(Phase D)*

```
Props:
  src      String  required  Image URL
  caption  Object  {}        { plate, confidence, camera, timestamp }

Emits: close
```

Full-screen backdrop modal. Close via: ESC key, click-outside, ✕ button.  
Image fades in on load (`opacity: 0 → 1`). Shows "Image not available" on `@error`.  
Registers `keydown` listener on `document` in `mounted`, removes in `beforeUnmount`.

---

### `FilterBar.vue` *(Phase D)*

```
Props:
  modelValue  Object  Filters object (v-model)
  cameras     Array   [{ id, cameraId, name }] for camera dropdown
  count       Number  Result count shown as "N results"

Emits: update:modelValue, clear
```

Fields:
- **Plate search** — text input, 320 ms debounce before emitting
- **Camera** — select from `cameras` prop; value is camera UUID
- **Date From / To** — `<input type="date">`, styled with calendar icon filter
- **Min Confidence** — select: Any / ≥70% / ≥80% / ≥90% / ≥95%
- **Archived** — checkbox toggle
- **Clear** — emits `clear`, parent resets all filters + re-fetches

---

### `RegisterCameraModal.vue` *(Phase C)*

Fields: `cameraId` (required), `name`, `location`, `ip`.  
Calls `useCamerasStore().registerCamera(data)` → `POST /cameras`.

---

### `CameraList.vue` *(Phase C)*

Filterable DataTable from `useCamerasStore().fetchEdgeStatus()`.  
Columns: Status · Camera ID · Name · Location · IP · Temp · CPU · Mem · Last Seen · Delete.  
Row click → `/cameras/:id`. Register button → `RegisterCameraModal`.

---

### `CameraDetail.vue` *(Phase C)*

`/cameras/:id` — 4 tabs: Overview (metric tiles) · Detections (table) · Health Log (dual-axis line chart + table) · Images (thumbnail grid).  
Health chart: amber temp left axis, cyan CPU right axis (0–100). Uses vue-chartjs `Line`.

---

### `DetectionList.vue` *(Phase D)*

**Route**: `/detections`

- **Store**: `useDetectionsStore().fetchFiltered()` on mount and on any server-side filter change
- **FilterBar**: v-model on `store.filters`; filter changes trigger `fetchFiltered()` (server side) or just re-slice (client side for date/confidence)
- **Live badge**: green ● LIVE from `useSocket().connected`
- **New-detection banner**: amber "+N new — click to refresh" counter, increments on `message_saved` socket event, click re-fetches
- **Table columns**: PlateTag · Camera ID · ConfidenceBar · Timestamp · Image indicator (●) · Archived (⊘)
- **Pagination**: prev/next over `store.currentPage`, shows `page+1 / pageCount`
- **CSV Export**: fetches `store.filtered` (already loaded), builds BOM-prefixed CSV with columns Date, Time, Plate, Camera, Confidence%, Archived, Has Image; triggers browser download `detections-YYYY-MM-DD.csv`

**Filter strategy**:

| Filter field | Where applied |
|-------------|--------------|
| `cameraId` | Server (query param) |
| `plateSearch` | Server (`search` param, ILIKE) |
| `archived` | Server (query param) |
| `dateFrom` / `dateTo` | Client-side on `store.filtered` getter |
| `minConfidence` | Client-side on `store.filtered` getter |

---

### `DetectionDetail.vue` *(Phase D)*

**Route**: `/detections/:id` (prop `id` = detection UUID)

- **Breadcrumb**: ◎ Detections › {plate}
- **Image panel**: 320×220 px thumbnail; hover shows "🔍 View full" overlay; click opens `ImageViewer`
- **Right panel**: `PlateTag` (lg) + `ConfidenceBar` + meta grid (camera, timestamp, ID, status badge)
- **Archive / Restore**: `PATCH /detections/:id` with `{ archived: true/false }`; optimistic local update
- **Image URL**: `api.getDetectionImageUrl(id)` → `GET /server/api/detections/:id/image`

---

## 7. API Layer (`src/api/index.js`)

Base URL: `window.location.origin + '/server/api'` — never hardcoded.  
Non-2xx → throws `Error("METHOD /path → STATUS")`.

### Cameras

| Method | Call | Endpoint |
|--------|------|----------|
| GET | `api.getCameras()` | `/cameras` |
| GET | `api.getCamerasEdgeStatus()` | `/cameras/edge-status` |
| GET | `api.getCamerasSummary()` | `/cameras/summary` |
| GET | `api.getCamera(id)` | `/cameras/:id` |
| POST | `api.createCamera(data)` | `/cameras` |
| PUT | `api.updateCamera(id, d)` | `/cameras/:id` |
| DELETE | `api.deleteCamera(id)` | `/cameras/:id` |
| POST | `api.registerCamera(data)` | `/cameras/register` |
| GET | `api.getCameraDetections(id, limit)` | `/cameras/:id/detections?limit=N` |

#### `EdgeStatus` object shape
```json
{
  "camera": { "id": "uuid", "cameraId": "aicamera2", "name": "...", "location": "...", "status": "active" },
  "latestHealth": {
    "status": "online", "cpuUsage": 12.5, "memoryUsage": 45.2,
    "temperature": 58.2, "diskUsage": 65.0, "timestamp": "2026-04-25T12:00:00.000Z"
  }
}
```

### Detections

| Method | Call | Endpoint |
|--------|------|----------|
| GET | `api.getDetections(params)` | `/detections?cameraId=&search=&limit=&offset=&sortBy=&sortOrder=&archived=` |
| GET | `api.getDetection(id)` | `/detections/:id` — returns Detection with camera relation |
| PATCH | `api.archiveDetection(id)` | `/detections/:id` body `{archived:true}` |
| PATCH | `api.unarchiveDetection(id)` | `/detections/:id` body `{archived:false}` |
| GET | `api.getDetectionImageUrl(id)` | Returns URL string only — `GET /detections/:id/image` served as stream |

#### `Detection` object shape
```json
{
  "id": "uuid",
  "licensePlate": "กข 1234",
  "confidence": "0.9245",
  "imagePath": "/home/devuser/aicamera/server/storage/aicamera2/2026-04-25/....jpg",
  "timestamp": "2026-04-25T12:05:00.000Z",
  "archived": false,
  "camera": { "id": "uuid", "cameraId": "aicamera2", "name": "Camera 2" }
}
```

**`confidence` is a decimal string** — always `parseFloat(d.confidence)`.  
**`imagePath` is an absolute server filesystem path** — use `getDetectionImageUrl(id)` to serve it, never expose the path directly to the browser.

### Camera Health

`api.getCameraHealth({ cameraId, limit, from, to })` → `GET /camera-health?...`

`from` / `to` are ISO date strings; backend filters on `h.timestamp`.

### Analytics & Events

| Call | Endpoint |
|------|----------|
| `api.getAnalytics()` | `/analytics` |
| `api.getSystemEvents(limit)` | `/system-events?limit=N` |
| `api.getVisualizations()` | `/visualizations` |
| `api.getAnalyticsEvents(limit)` | `/analytics-events?limit=N` |

---

## 8. Socket.IO (`src/composables/useSocket.js`)

Singleton — one connection shared across all components.

```javascript
const { socket, connected } = useSocket();
```

**Config**: URL = `window.location.origin`, path = `/ws/`, transports `['websocket', 'polling']`

| Event | When |
|-------|------|
| `message_saved` | Detection written to DB |
| `camera_registered` | New camera registered |
| `connect` / `disconnect` | Connection state change |

`DetectionList` uses `message_saved` to increment a "N new" counter without auto-refreshing.

---

## 9. State Management (Pinia Stores)

### `cameras.store.js` — `useCamerasStore`

```
State:   cameras[], edgeStatus[], currentCamera, loading, error
Getter:  onlineCount  (status: online|healthy|pass)
Actions:
  fetchCameras()       → cameras[]
  fetchEdgeStatus()    → edgeStatus[]
  fetchCamera(id)      → currentCamera
  registerCamera(data) → POST /cameras, prepends result
  removeCamera(id)     → DELETE /cameras/:id, filters both arrays
```

### `detections.store.js` — `useDetectionsStore`

```
State:
  items[]      Raw server results (up to 500) from latest fetchFiltered call
  recent[]     For MainDashboard feed (last N)
  hourly[]     For MainDashboard chart (24 buckets)
  total        Number — length of last hourly fetch
  todayCount   Number
  page         Current page index (0-based)
  loading, error
  filters: { cameraId, plateSearch, dateFrom, dateTo, minConfidence, archived }

Getters (all computed from items[]):
  filtered       Apply client-side dateFrom/dateTo/minConfidence on items[]
  currentPage    filtered.slice(page * 50, (page+1) * 50)
  pageCount      ceil(filtered.length / 50)
  hasNext        page < pageCount - 1
  hasPrev        page > 0

Actions:
  fetchFiltered()          Server fetch with cameraId/search/archived; resets page to 0
  nextPage() / prevPage()  Increment/decrement page
  setFilter(key, value)    Update one filter key, reset page
  resetFilters()           Clear all filters, reset page
  fetchRecent(limit=20)    → recent[], todayCount  (MainDashboard)
  fetchHourly()            → hourly[], total        (MainDashboard)
```

**PAGE_SIZE = 50** (exported constant).  
**CSV export** lives in `DetectionList.vue` methods, not the store — it reads `store.filtered` directly.

### `analytics.store.js` — `useAnalyticsStore` *(Phase E)*

```
State:   analytics[], detections[], loading, error

Getters (no state param — all use this):
  dailyTotals          [{ date, count }] last 30 days oldest-first, from analytics[]
  cameraComparison     [{ cameraId, name, count }] per-camera totals sorted desc
  confidenceHistogram  [{ label: '0–10', count }] 10 buckets of 10%
  heatmapData          { cells: number[7][24], dayLabels: string[7] } last 7 days × 24 h
  topPlates            [{ plate, count }] top 20 by frequency from detections[]
  totalDetections      sum of analytics[].totalDetections (0 if analytics never populated)
  uniquePlatesAll      Set size of detections[].licensePlate
  avgConfidence        mean parseFloat(confidence) across detections[]

Actions:
  fetchAll()   Promise.all([api.getAnalytics(), api.getDetections({limit:2000})])
```

**Data note**: `dailyTotals` and `cameraComparison` derive from `/analytics` (populated by
`GET /cameras/analytics/run`). `confidenceHistogram`, `heatmapData`, `topPlates` derive from
the 2000-record detections fetch — always available even if analytics is empty.

---

## 10. `MainDashboard.vue`

**Route**: `/` | Refresh: 10 s interval + `message_saved` | Clock: 1 s

Sections: page header · KPI row (4 MetricCards) · camera status grid · HourlyChart · recent detection feed (20 rows) · error banner.

KPI sources: online count from `edgeStatus`; today/total from 500-record detection fetch; health count from `/camera-health?limit=50`.

---

## 11. `DetectionList.vue` + `DetectionDetail.vue`

See **Section 6** for full component descriptions.

**`DetectionList` data flow**:
```
mount → store.fetchFiltered()
         ↳ GET /detections?limit=500&sortBy=timestamp&sortOrder=DESC[&cameraId=][&search=][&archived=]
         ↳ store.items[] populated
         ↳ store.filtered getter applies date/confidence client-side
         ↳ store.currentPage slices 50 rows for table
```

**`DetectionDetail` data flow**:
```
mount → api.getDetection(id)
         ↳ GET /detections/:id  (includes camera relation)
         ↳ detection object → PlateTag, ConfidenceBar, meta grid, image
```

---

## 12. `CameraList.vue` + `CameraDetail.vue`

See **Section 6**. Both fetch independently on mount, handle own loading/error states.

---

## 13. `AnalyticsDashboard.vue` *(Phase E)*

**Route**: `/analytics`

- **Store**: `useAnalyticsStore().fetchAll()` on mount — single `Promise.all` call
- **KPI row**: 4 MetricCards — Total Detections / Unique Plates / Avg Confidence / Active Cameras
- **E2 — 30-day bar chart**: cyan bars, last 30 calendar days, `maxTicksLimit: 10` auto-skips labels
- **E3 — Confidence histogram**: 10 buckets × 10% (0–10% … 90–100%); bars coloured red/amber/green by bucket midpoint
- **E4 — 7d×24h heatmap**: CSS grid (7 rows × 24 cols), cyan opacity scaled against per-render max; hover tooltip shows count; legend bar bottom-left
- **E5 — Camera comparison**: horizontal bar (`indexAxis: 'y'`), green bars, sorted by total desc; shows "No camera data" if `/cameras/analytics/run` not yet called
- **E6 — Top plates table**: rank / PlateTag / count / % of loaded records; sourced from 2000-record detections fetch

**Data flow**:
```
mount → store.fetchAll()
  ├── GET /analytics          → analytics[] (per-camera per-day rows)
  └── GET /detections?limit=2000 → detections[]

computed getters:
  dailyTotals        from analytics[]    → 30-day chart labels+data
  cameraComparison   from analytics[]    → camera bar chart
  confidenceHistogram from detections[]  → histogram
  heatmapData        from detections[]   → 7×24 cells + dayLabels
  topPlates          from detections[]   → top-20 table
```

**Populating analytics**: `GET /server/api/cameras/analytics/run` triggers `update_daily_analytics()` stored procedure. Call this once after data is in DB; it backfills all dates. Without this, 30-day chart and camera comparison show zeros but histogram/heatmap/top-plates still render from raw detections.

---

## 14. `EdgeControl.vue` — Legacy View

**Route**: `/edge_control` — functional, old styling. Status bulbs by health age: <5 min green · 5–15 min yellow · >15 min red. Migrate in Phase H.

---

## 14. Nginx Configuration

**File**: `/etc/nginx/sites-available/lprserver`

```nginx
server {
  listen 80;
  server_name _;

  location = / {
    root /home/devuser/aicamera/server/landing;
    try_files /index.html =404;
  }

  location / {
    root /home/devuser/aicamera/server/landing;
    try_files $uri $uri/ /index.html =404;
  }

  location /server/ {
    alias /home/devuser/aicamera/server/frontend-app/dist/;
    index index.html;
    try_files $uri $uri/ /server/index.html;
    # ⚠ No =404 — with alias, 4-arg try_files treats /server/index.html
    # as a filesystem path, which always fails.
  }

  location /server/api/ {
    proxy_pass http://127.0.0.1:3000/server/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }

  location /ws/ {
    proxy_pass http://127.0.0.1:3001/ws/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }
}
```

**Reload**: `echo 'admin88366' | sudo -S nginx -s reload`

---

## 15. Development Workflow

### Standard cycle (Mac → GitHub → lprserver)

```bash
# 1. Edit source on Mac

# 2. Commit + push
git add <files>
git commit -m "feat: ..."
git push origin main          # origin = popwandee/aicamera.git

# 3a. Deploy frontend only
ssh devuser@100.95.46.128 \
  "cd ~/aicamera && git pull origin main \
   && cd server/frontend-app && npm install && npm run build \
   && echo 'admin88366' | sudo -S nginx -s reload"

# 3b. Deploy backend only (after controller/service changes)
ssh devuser@100.95.46.128 \
  "cd ~/aicamera && git pull origin main \
   && cd server/backend-api && npm run build \
   && sudo systemctl restart backend-api"

# 3c. Both changed — run 3a then 3b
```

### Service management on lprserver

| Service | Start/Restart | Logs |
|---------|--------------|------|
| `backend-api` | `sudo systemctl restart backend-api` | `journalctl -u backend-api -f` |
| `ws-service` | `sudo systemctl restart ws-service` | `journalctl -u ws-service -f` |
| `mqtt-service` | `sudo systemctl restart mqtt-service` | `journalctl -u mqtt-service -f` |
| `nginx` | `sudo systemctl reload nginx` | `/var/log/nginx/error.log` |

Quick API smoke test after backend restart:
```bash
curl http://localhost:3000/server/api/cameras
curl http://localhost:3000/server/api/detections?limit=1
curl http://localhost:3000/server/api/detections/<uuid>
```

### Git remotes (all machines unified)

| Machine | Remote | URL | Push rights |
|---------|--------|-----|------------|
| Mac | `origin` | `popwandee/aicamera.git` | ✅ |
| lprserver | `origin` | `popwandee/aicamera.git` | ✅ |
| lprserver | `myorigin` | `pwd-vw/aicamera.git` | leftover — harmless |
| aicamera2 | `origin` | `popwandee/aicamera.git` | ✅ |

---

## 16. Known Issues and Gotchas

| Issue | Root cause | Fix applied |
|-------|-----------|------------|
| `GET /detections/:id` returned 404 | Controller had `/:id/image` and list but no single-record GET | Added `@Get('detections/:id')` before the list route in `device.controller.ts` |
| `DetectionDetail` showed `camera: undefined` | `findDetectionById` in service didn't join `relations: ['camera']` | Added `relations: ['camera']` to `findDetectionById` |
| `PATCH /detections/image-path` returned 400 | NestJS `/:id` was before `/image-path`; `ParseUUIDPipe` rejected the literal string | Moved `/image-path` route above `/:id` |
| `camera_health` columns NULL after MQTT | Edge sends `cpu_usage`/`cpu_temp`; backend expected different names | Fallback: `payload.cpu_percent ?? payload.cpu_usage` in mqtt-service |
| `/server/edge_control` returned 404 | `try_files` 4-arg with `alias` treats 3rd arg as a file path | Removed `=404`, now 3-arg form |
| Vue build — `no-unused-vars` in Pinia getter | Pinia `pageCount(state)` declared `state` but only used `this` | Removed unused param: `pageCount()` |
| Vue build — multi-word component names | ESLint requires ≥ 2 words | Always: `DetectionList`, not `Detections` |
| `kpi.total` shows max 500 | `getDetections` capped at `limit=500` | Accepted; a real `COUNT` endpoint would fix for large datasets |
| Health record timestamp field name | Backend uses `createdAt` or `timestamp` depending on path | Both accessed: `h.createdAt \|\| h.timestamp` |
| `confidence` is a string, not number | TypeORM stores DECIMAL as string | Always `parseFloat(d.confidence)` before comparison |

---

## 17. Phase Roadmap

| Phase | View(s) | Key features | Status |
|-------|---------|-------------|--------|
| A | Foundation | Design tokens, Sidebar, MetricCard, StatusDot, router, App shell | ✅ Done |
| B | MainDashboard | 24h hourly bar chart, Pinia stores, chart.js | ✅ Done |
| C | CameraList, CameraDetail, RegisterCameraModal | DataTable, register/delete, 4-tab detail, health line chart | ✅ Done |
| D | DetectionList, DetectionDetail, 4 shared components | FilterBar, PlateTag, ConfidenceBar, ImageViewer, CSV export, archive toggle | ✅ Done |
| E | AnalyticsDashboard | 30-day bar chart, confidence histogram, 7d×24h heatmap, camera comparison, top plates | ✅ Done |
| F | RouteAnalysis, RouteDetail | Client-side route algorithm, routes.store | 🔲 Next |
| G | ConvoyDetection | Sliding-window convoy algorithm, parallel timeline SVG | 🔲 |
| H | Settings, SystemEvents | 4-tab settings (localStorage), migrate EdgeControl to design tokens | 🔲 |
| I | All | Responsive layout, error states + retry everywhere | 🔲 |

### Stores still to create

| File | Phase |
|------|-------|
| `src/stores/routes.store.js` | F |
| `src/stores/settings.store.js` | H |

### Dependencies still to install

```bash
npm install leaflet @vue/leaflet   # Phase F (route maps) — optional
```

`date-fns` (^3.6.0) is already installed.
