# LPR Server UI — Developer Reference

**Project**: AI Camera Dashboard (PWD Vision Works)  
**Server**: lprserver — Tailscale `100.95.46.128`  
**Live URL**: `http://100.95.46.128/server/`  
**Last updated**: 2026-04-26  
**Phases complete**: A (Foundation) · B (Dashboard + Chart) · C (Camera Management)

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

- `vue/multi-word-component-names` — all `name:` values must be two+ words (`MainDashboard`, not `Dashboard`)
- `vue/no-reserved-keys` — `data()` keys must not start with `_` or `$`

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
│   └── detections.store.js          Pinia: recent detections + hourly buckets
│
├── components/
│   ├── layout/
│   │   └── Sidebar.vue              Fixed 220px left nav (component name: AppSidebar)
│   ├── shared/
│   │   ├── MetricCard.vue           KPI card with icon + value + label
│   │   └── StatusDot.vue            Colored pulsing dot (online/offline/warning/unknown)
│   ├── charts/
│   │   └── HourlyChart.vue          24-bucket bar chart (vue-chartjs Bar)
│   └── cameras/
│       └── RegisterCameraModal.vue  Modal form: register a new camera (Phase C)
│
└── views/
    ├── MainDashboard.vue            ✅ Phase B — KPI + camera grid + hourly chart + feed
    ├── CameraList.vue               ✅ Phase C — filterable DataTable + register/delete
    ├── CameraDetail.vue             ✅ Phase C — 4-tab detail + health line chart
    ├── DetectionList.vue            🔲 Phase D — stub
    ├── DetectionDetail.vue          🔲 Phase D — stub
    ├── AnalyticsDashboard.vue       🔲 Phase E — stub
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

### Spacing and shape

| Variable | Value |
|----------|-------|
| `--sidebar-w` | `220px` |
| `--radius-sm` | `4px` |
| `--radius-md` | `8px` |
| `--radius-lg` | `12px` |
| `--transition` | `0.18s ease` |

### Global utility classes

| Class | Effect |
|-------|--------|
| `.font-data` | Apply JetBrains Mono |
| `.font-display` | Apply Rajdhani |
| `.font-thai` | Apply Sarabun |
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
| `/detections` | Detections | `DetectionList` | 🔲 Phase D |
| `/detections/:id` | DetectionDetail | `DetectionDetail` | 🔲 Phase D |
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
Imports `design-tokens.css` globally — all pages inherit CSS variables.

---

### `Sidebar.vue` (component name: `AppSidebar`)

Sections:
1. **Brand** — `⬡ AICAM | Control Center` in Rajdhani, cyan glow
2. **Connection status** — `StatusDot` driven by `useSocket().connected`
3. **Nav — Monitor**: Dashboard `/`, Cameras `/cameras`, Detections `/detections`
4. **Nav — Analyse**: Analytics `/analytics`, Routes `/routes`, Convoy `/convoy`
5. **Nav — System**: Edge Control `/edge_control`, System Events `/system`, Settings `/settings`
6. **Footer** — "PWD Vision Works"

Active link: cyan left border + tinted background. `exact-active-class` on Dashboard route only.

---

### `MetricCard.vue`

```
Props:
  icon    String          default '◈'   Unicode symbol
  label   String          required      Uppercase label
  value   Number|String   null          ≥1000 gets toLocaleString()
  sub     String          ''            Secondary line
  loading Boolean         false         Shows blinking shimmer
  accent  String          'cyan'        'cyan'|'green'|'amber'|'red'
```

---

### `StatusDot.vue`

```
Props:
  status  String  'unknown'   'online'|'offline'|'warning'|'unknown'
  title   String  ''          Tooltip text
```

| Status | Color | Animation |
|--------|-------|-----------|
| `online` | `--green` | Pulsing ring, 2s |
| `warning` | `--amber` | Pulsing ring, 2s |
| `offline` | `--red` | Static |
| `unknown` | `--text-muted` | Static |

---

### `HourlyChart.vue`

```
Props:
  hourlyData  Array  []  [{ label: '07', count: 42 }, …]  24 items, oldest first
```

- Registers chart.js: `CategoryScale`, `LinearScale`, `BarElement`, `Tooltip`
- Bars: cyan `#00c8ff`, 18% opacity; X-axis tick every 4th label
- Fixed container height: 180px

---

### `RegisterCameraModal.vue` *(Phase C)*

**File**: `src/components/cameras/RegisterCameraModal.vue`

```
Emits:
  close     — user cancelled or form submitted successfully
  created   — (camera) new camera object returned from backend

Fields:
  cameraId  String  required  Must match the edge device config
  name      String  optional  Display name
  location  String  optional  Physical location text
  ip        String  optional  Edge device IP
```

Calls `useCamerasStore().registerCamera(data)` → `POST /server/api/cameras`.  
Closes and emits `created` on success; shows inline error on failure.

---

### `CameraList.vue` *(Phase C)*

**Route**: `/cameras`

Features:
- Loads `edgeStatus[]` from `useCamerasStore().fetchEdgeStatus()`
- Live text filter across `cameraId + name + location`
- Count badges: Online (green) + Total (cyan)
- DataTable columns: Status · Camera ID · Name · Location · IP · Temp · CPU · Mem · Last Seen · Delete
- Row click → `/cameras/:id`
- Delete button opens inline confirm modal → `store.removeCamera(id)`
- "Register Camera" button → opens `RegisterCameraModal`

**Camera status logic** (shared with MainDashboard):
```javascript
latestHealth.status: 'online'|'healthy'|'pass' → 'online'
                     'degraded'|'warning'       → 'warning'
                     anything else              → 'offline'
!latestHealth                                   → 'unknown'
```

**Last Seen** format: relative (`just now`, `5m ago`, `2h ago`, `3d ago`)

---

### `CameraDetail.vue` *(Phase C)*

**Route**: `/cameras/:id` (prop `id` = camera UUID)

**Header card**: StatusDot + camera title + meta row (location, IP, status, temp, CPU)  
**Breadcrumb**: ◈ Cameras › {cameraId} — back-navigates to `/cameras`

**Tabs**:

| Tab | Content | Data source |
|-----|---------|-------------|
| Overview | 4 metric tiles: Temp, CPU, Memory, Detection count | `healthRecords[0]` + `detections.length` |
| Detections | Scrollable table: plate, confidence %, timestamp, image indicator | `api.getCameraDetections(id, 200)` |
| Health Log | Dual-axis line chart + health records table | `api.getCameraHealth({ cameraId: id, limit: 100 })` |
| Images | Thumbnail grid of detections that have `imagePath` | filtered from detections array |

**Health line chart** (vue-chartjs `Line`, inline in CameraDetail):
- Registers: `LineElement`, `PointElement`, `Filler` (in addition to globally registered scales)
- Left Y-axis `yTemp`: temperature in °C, amber line `#ffab40`
- Right Y-axis `yCpu`: CPU %, cyan fill `rgba(0,200,255,0.08)`, 0–100 range
- X-axis ticks: `HH:MM` (th-TH locale), max 8 ticks shown
- Data order: oldest-first (healthRecords reversed)

**Image thumbnails**: `api.getDetectionImageUrl(detectionId)` → `GET /server/api/detections/:id/image`  
Broken images hidden via `@error` handler.

---

## 7. API Layer (`src/api/index.js`)

Base URL: `window.location.origin + '/server/api'` — never hardcoded.  
All calls use `fetch`. Non-2xx responses throw `Error("METHOD /path → STATUS")`.

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
| POST | `api.registerCamera(data)` | `/cameras/register` (edge self-registration) |
| GET | `api.getCameraDetections(id, limit)` | `/cameras/:id/detections?limit=N` |
| GET | `api.runAnalytics()` | `/cameras/analytics/run` |

#### `EdgeStatus` object shape
```json
{
  "camera": {
    "id": "uuid",
    "cameraId": "aicamera2",
    "name": "Camera 2",
    "location": "Building A",
    "status": "active"
  },
  "latestHealth": {
    "id": "uuid",
    "cameraId": "uuid",
    "timestamp": "2026-04-25T12:00:00.000Z",
    "status": "online",
    "cpuUsage": 12.5,
    "memoryUsage": 45.2,
    "temperature": 58.2,
    "diskUsage": 65.0,
    "uptimeSeconds": 86400
  }
}
```

### Detections

| Method | Call | Endpoint |
|--------|------|----------|
| GET | `api.getDetections(params)` | `/detections?...` |
| GET | `api.getDetection(id)` | `/detections/:id` |
| PATCH | `api.archiveDetection(id)` | `/detections/:id` `{archived:true}` |
| PATCH | `api.unarchiveDetection(id)` | `/detections/:id` `{archived:false}` |
| GET | `api.getDetectionImageUrl(id)` | returns URL string (not a fetch call) |

**`getDetections` query params** (all optional):

| Param | Notes |
|-------|-------|
| `cameraId` | filter by camera UUID |
| `search` | plate number search |
| `limit` | max records (dashboard uses 500) |
| `offset` | pagination |
| `sortBy` | field name, e.g. `timestamp` |
| `sortOrder` | `ASC` or `DESC` |
| `archived` | boolean |

#### `Detection` object shape
```json
{
  "id": "uuid",
  "licensePlate": "กข 1234",
  "confidence": "0.9245",
  "imagePath": "/storage/aicamera2/2026-04-25/...",
  "timestamp": "2026-04-25T12:05:00.000Z",
  "archived": false,
  "camera": { "id": "uuid", "cameraId": "aicamera2" }
}
```

**Important**: `confidence` is a decimal string (e.g. `"0.9245"`), not a number. Always `parseFloat()`.

### Camera Health

| Method | Call | Endpoint |
|--------|------|----------|
| GET | `api.getCameraHealth(params)` | `/camera-health?cameraId=&limit=&from=&to=` |

### Analytics & Events

| Method | Endpoint |
|--------|----------|
| `api.getAnalytics()` | `/analytics` |
| `api.getSystemEvents(limit)` | `/system-events?limit=N` |
| `api.getVisualizations()` | `/visualizations` |
| `api.getAnalyticsEvents(limit)` | `/analytics-events?limit=N` |

---

## 8. Socket.IO (`src/composables/useSocket.js`)

Singleton — one connection shared across all components.

```javascript
const { socket, connected } = useSocket();
// connected: Vue ref<boolean>
// socket: raw Socket.IO instance
```

**Connection config**: URL = `window.location.origin`, path = `/ws/`, transports = `['websocket', 'polling']`

**Events from server**:

| Event | When |
|-------|------|
| `message_saved` | Detection written to DB |
| `camera_registered` | New camera registered |
| `connect` / `disconnect` | Socket state change |

---

## 9. State Management (Pinia Stores)

### `cameras.store.js` — `useCamerasStore`

```
State:
  cameras[]       Camera[] — from GET /cameras
  edgeStatus[]    EdgeStatus[] — from GET /cameras/edge-status
  currentCamera   Camera|null — single camera from GET /cameras/:id
  loading         Boolean
  error           String|null

Getters:
  onlineCount     cameras with status online/healthy/pass

Actions:
  fetchCameras()          → populates cameras[]
  fetchEdgeStatus()       → populates edgeStatus[]  ← used by CameraList
  fetchCamera(id)         → populates currentCamera
  registerCamera(data)    → POST /cameras, prepends to cameras[]
  removeCamera(id)        → DELETE /cameras/:id, filters from cameras[] + edgeStatus[]
```

### `detections.store.js` — `useDetectionsStore`

```
State:
  recent[]      Detection[]
  hourly[]      { label: 'HH', count: N }[]  — 24 buckets
  total         Number
  todayCount    Number
  loading       Boolean
  error         String|null

Actions:
  fetchRecent(limit=20)   → recent[], todayCount
  fetchHourly()           → hourly[], total  (fetches 500 records)
```

**`buildHourlyBuckets` algorithm**:
1. Fetch 500 most-recent detections sorted DESC
2. `hoursAgo = floor((now - timestamp) / 3600000)`
3. If `hoursAgo < 24`, increment `buckets[23 - hoursAgo]`
4. Map to `{ label: 'HH', count }` starting from `currentHour - 23`

---

## 10. `MainDashboard.vue`

**Route**: `/` | Refresh: 10 s interval + `message_saved` socket event | Clock: 1 s interval

Sections:
1. **Page header** — title + live clock (th-TH locale)
2. **KPI row** — 4 `MetricCard` in `auto-fit minmax(180px, 1fr)`
3. **Camera Status grid** — tiles from `getCamerasEdgeStatus()`, click → `/cameras/:id`
4. **Detections — Last 24 Hours** — `HourlyChart` bar chart
5. **Recent Detections feed** — last 20 detections, 4-column grid row, click → `/detections/:id`
6. **Error banner** — shown on any API failure

KPI sources: online count from `edgeStatus`, today/total from 500-record detection fetch, health count from health endpoint.

**Confidence color**: ≥0.90 green · ≥0.70 amber · <0.70 red

---

## 11. `CameraList.vue` + `CameraDetail.vue`

See **Section 6** for full component descriptions. Both views fetch independently (no store pre-load required) and handle their own loading/error states.

**`CameraDetail` data loading** (parallel on mount):
```javascript
Promise.all([loadCamera(), loadDetections(), loadHealth()])
```

---

## 12. `EdgeControl.vue` — Legacy View

**Route**: `/edge_control` — functional but uses old styling (not design tokens).  
Status bulbs based on health timestamp age: green < 5 min · yellow 5–15 min · red > 15 min.  
Migrate to design system in Phase H.

---

## 13. Nginx Configuration

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
    # ⚠ No =404 here — with alias, 4-arg try_files treats /server/index.html
    # as a file path check (not a URI redirect), which always fails.
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

## 14. Development Workflow

### Standard cycle (Mac → GitHub → lprserver)

```bash
# 1. Edit source on Mac in VSCode

# 2. Commit + push to popwandee/aicamera.git
git add <files>
git commit -m "feat: ..."
git push origin main          # origin = popwandee/aicamera.git

# 3. Deploy to lprserver
sshpass -p 'admin88366' ssh -o PreferredAuthentications=password \
  devuser@100.95.46.128 \
  "cd ~/aicamera && git pull origin main \
   && cd server/frontend-app && npm install && npm run build \
   && echo 'admin88366' | sudo -S nginx -s reload"
```

### Git remotes (current state — all machines unified)

| Machine | Remote | URL | Push rights |
|---------|--------|-----|------------|
| Mac | `origin` | `popwandee/aicamera.git` | ✅ (popwandee token via macOS Keychain) |
| lprserver | `origin` | `popwandee/aicamera.git` | ✅ |
| lprserver | `myorigin` | `pwd-vw/aicamera.git` | leftover — harmless, can remove |
| aicamera2 | `origin` | `popwandee/aicamera.git` | ✅ |

All three machines are on `main`. The canonical remote is `popwandee/aicamera.git`.

### Build output sizes (Phase C)

| File | Size | Gzipped |
|------|------|---------|
| `js/chunk-vendors.*.js` | ~370 KB | ~128 KB |
| `js/app.*.js` | ~40 KB | ~11 KB |
| `css/app.*.css` | ~22 KB | ~4 KB |

---

## 15. Known Issues and Gotchas

| Issue | Root cause | Fix applied |
|-------|-----------|------------|
| `PATCH /detections/image-path` returns 400 | NestJS `/:id` before `/image-path`; `ParseUUIDPipe` rejected `image-path` | Moved `/image-path` route above `/:id` |
| `camera_health` columns all NULL after MQTT | Edge sends `cpu_usage`/`cpu_temp`; backend expected different names | Fallback: `payload.cpu_percent ?? payload.cpu_usage` in mqtt-service |
| `/server/edge_control` returned 404 | `try_files` 4-arg form with `alias` makes 3rd arg a file check | Removed `=404`, now 3-arg form |
| Vue build fails — multi-word component names | Component `name:` must be ≥ 2 words | Always: `MainDashboard`, `CameraList`, not `Dashboard` |
| Vue build fails — reserved keys | `data()` keys prefixed `_` or `$` reserved | Use `clockTimer`, not `_clockTimer` |
| `kpi.total` shows max 500 | `getDetections` capped at `limit=500` | Accepted; backend count endpoint would fix for large datasets |
| Health chart `createdAt` vs `timestamp` | Backend may use either field name for health record timestamps | Both accessed: `h.createdAt \|\| h.timestamp` |

---

## 16. Phase Roadmap

| Phase | View(s) | Key features | Status |
|-------|---------|-------------|--------|
| A | Foundation | Design tokens, Sidebar, MetricCard, StatusDot, router, App shell, all stub views | ✅ Done |
| B | MainDashboard | 24h hourly bar chart, Pinia stores, chart.js | ✅ Done |
| C | CameraList, CameraDetail, RegisterCameraModal | DataTable, register/delete, 4-tab detail, health line chart, cameras.store | ✅ Done |
| D | DetectionList, DetectionDetail | FilterBar, ImageViewer, PlateTag, ConfidenceBar, CSV export | 🔲 Next |
| E | AnalyticsDashboard | 30-day bar chart, confidence histogram, 7d×24h heatmap | 🔲 |
| F | RouteAnalysis, RouteDetail | Client-side route algorithm, routes.store | 🔲 |
| G | ConvoyDetection | Sliding-window convoy algorithm, parallel timeline SVG | 🔲 |
| H | Settings, SystemEvents | 4-tab settings (localStorage), migrate EdgeControl to design tokens | 🔲 |
| I | All | Responsive layout, error states + retry everywhere | 🔲 |

### Stores still to create

| File | Phase |
|------|-------|
| `src/stores/analytics.store.js` | E |
| `src/stores/routes.store.js` | F |
| `src/stores/settings.store.js` | H |

### Dependencies still to install

```bash
npm install leaflet @vue/leaflet   # Phase F (route maps) — optional
```

`date-fns` (^3.6.0) is already installed and available.
