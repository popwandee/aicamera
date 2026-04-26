# LPR Server UI — Developer Reference

**Project**: AI Camera Dashboard (PWD Vision Works)  
**Server**: lprserver — Tailscale `100.95.46.128`  
**Live URL**: `http://100.95.46.128/server/`  
**Last updated**: 2026-04-26  
**Phases complete**: A (Foundation) + B (Dashboard + Chart)

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
| date-fns | `^3.6.0` | Date utilities (installed, not yet used) |
| @vue/cli-service | `~5.0.0` | Build tool (Webpack, NOT Vite) |

**Build command**: `npm run build`  
**Output**: `dist/` — served by nginx at `/server/`  
**Router base**: auto-detected: `/server/` in production, `/` in dev

### ESLint rules that bite

- `vue/multi-word-component-names` — all `name:` values in components must be two or more words (e.g. `AppSidebar`, not `Sidebar`)
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
│   ├── cameras.store.js             Pinia: cameras list + edge status
│   └── detections.store.js          Pinia: recent detections + hourly buckets
│
├── components/
│   ├── layout/
│   │   └── Sidebar.vue              Fixed 220px left nav (component name: AppSidebar)
│   ├── shared/
│   │   ├── MetricCard.vue           KPI card with icon + value + label
│   │   └── StatusDot.vue            Colored pulsing dot (online/offline/warning/unknown)
│   └── charts/
│       └── HourlyChart.vue          24-bucket bar chart (vue-chartjs Bar)
│
└── views/
    ├── MainDashboard.vue            ✅ IMPLEMENTED — Phase A+B
    ├── EdgeControl.vue              ✅ IMPLEMENTED — legacy (pre-design-system)
    ├── EdgeControlCamera.vue        ✅ IMPLEMENTED — legacy (pre-design-system)
    ├── CameraList.vue               🔲 STUB — Phase C
    ├── CameraDetail.vue             🔲 STUB — Phase C
    ├── DetectionList.vue            🔲 STUB — Phase D
    ├── DetectionDetail.vue          🔲 STUB — Phase D
    ├── AnalyticsDashboard.vue       🔲 STUB — Phase E
    ├── RouteAnalysis.vue            🔲 STUB — Phase F
    ├── RouteDetail.vue              🔲 STUB — Phase F
    ├── ConvoyDetection.vue          🔲 STUB — Phase G
    ├── SystemEvents.vue             🔲 STUB — Phase H
    ├── Settings.vue                 🔲 STUB — Phase H
    ├── ServerHome.vue               Legacy table view (unused in new router)
    ├── Network.vue                  Legacy (unused in new router)
    └── Developer.vue                Legacy (unused in new router)
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
| `.text-cyan` | Color: `--cyan` |
| `.text-green` | Color: `--green` |
| `.text-amber` | Color: `--amber` |
| `.text-red` | Color: `--red` |
| `.text-muted` | Color: `--text-muted` |
| `.panel` | Dark card: `bg-panel` + `border-card` + `radius-md` + `shadow-card` |
| `.badge` | Inline pill with monospace font |
| `.badge-cyan/green/amber/red` | Colored badge variants |
| `.btn` | Ghost button (cyan border, transparent bg) |
| `.btn-primary` | Filled button (cyan tinted bg) |

---

## 5. Routes

| Route | Name | Component | Status | Notes |
|-------|------|-----------|--------|-------|
| `/` | Dashboard | `MainDashboard` | ✅ Live | KPI + camera grid + hourly chart + feed |
| `/cameras` | Cameras | `CameraList` | 🔲 Stub | Phase C |
| `/cameras/:id` | CameraDetail | `CameraDetail` | 🔲 Stub | Phase C |
| `/detections` | Detections | `DetectionList` | 🔲 Stub | Phase D |
| `/detections/:id` | DetectionDetail | `DetectionDetail` | 🔲 Stub | Phase D |
| `/analytics` | Analytics | `AnalyticsDashboard` | 🔲 Stub | Phase E |
| `/routes` | Routes | `RouteAnalysis` | 🔲 Stub | Phase F |
| `/routes/:routeKey` | RouteDetail | `RouteDetail` | 🔲 Stub | Phase F |
| `/convoy` | Convoy | `ConvoyDetection` | 🔲 Stub | Phase G |
| `/edge_control` | EdgeControl | `EdgeControl` | ✅ Live | Legacy, no design tokens |
| `/edge_control/camera/:id` | EdgeControlCamera | `EdgeControlCamera` | ✅ Live | Legacy |
| `/system` | System | `SystemEvents` | 🔲 Stub | Phase H |
| `/settings` | Settings | `Settings` | 🔲 Stub | Phase H |

**Nginx SPA fallback** — `try_files $uri $uri/ /server/index.html;` (no trailing `=404` — that would make the 4th arg a file check which fails with `alias`).

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

**File**: `src/components/layout/Sidebar.vue`

Sections:
1. **Brand** — `⬡ AICAM | Control Center` in Rajdhani, cyan glow
2. **Connection status** — `StatusDot` driven by `useSocket().connected`; shows "Live" (green pulse) or "Reconnecting…" (red)
3. **Nav — Monitor**: Dashboard `/`, Cameras `/cameras`, Detections `/detections`
4. **Nav — Analyse**: Analytics `/analytics`, Routes `/routes`, Convoy `/convoy`
5. **Nav — System**: Edge Control `/edge_control`, System Events `/system`, Settings `/settings`
6. **Footer** — "PWD Vision Works"

Active link: cyan left border (`border-left: 2px solid var(--cyan)`) + tinted background.  
`exact-active-class` on Dashboard to avoid matching all routes.

---

### `MetricCard.vue`

**File**: `src/components/shared/MetricCard.vue`

```
Props:
  icon    String  default '◈'      Unicode symbol shown large on left
  label   String  required         Uppercase label below value
  value   Number|String  null      Displayed as large number; ≥1000 gets toLocaleString()
  sub     String  ''               Small secondary line
  loading Boolean false            Shows blinking '──' shimmer when true
  accent  String  'cyan'           Value color: 'cyan'|'green'|'amber'|'red'
```

---

### `StatusDot.vue`

**File**: `src/components/shared/StatusDot.vue`

```
Props:
  status  String  'unknown'   'online'|'offline'|'warning'|'unknown'
  title   String  ''          Tooltip text
```

| Status | Dot color | Animation |
|--------|----------|-----------|
| `online` | `--green` | Pulsing green ring, 2s |
| `warning` | `--amber` | Pulsing amber ring, 2s |
| `offline` | `--red` | Static |
| `unknown` | `--text-muted` | Static |

---

### `HourlyChart.vue`

**File**: `src/components/charts/HourlyChart.vue`

```
Props:
  hourlyData  Array  []  Array of { label: '07', count: 42 } — 24 items, oldest first
```

- Registers chart.js: `CategoryScale`, `LinearScale`, `BarElement`, `Tooltip`
- Bars: cyan (`#00c8ff`), 18% opacity fill, 35% on hover
- X-axis: shows every 4th label (every 4 hours) to avoid crowding
- Tooltip: dark panel (`#0d1520` bg) with cyan title, format `"HH:00 — N detections"`
- Fixed container height: 180px

---

## 7. API Layer (`src/api/index.js`)

Base URL: `window.location.origin + '/server/api'` — never hardcoded.  
All calls use `fetch`. Non-2xx responses throw `Error("METHOD /path → STATUS")`.

### Cameras

| Method | Call | Endpoint | Returns |
|--------|------|----------|---------|
| GET | `api.getCameras()` | `/cameras` | `Camera[]` |
| GET | `api.getCamerasEdgeStatus()` | `/cameras/edge-status` | `EdgeStatus[]` |
| GET | `api.getCamerasSummary()` | `/cameras/summary` | summary object |
| GET | `api.getCamera(id)` | `/cameras/:id` | `Camera` |
| POST | `api.createCamera(data)` | `/cameras` | `Camera` |
| PUT | `api.updateCamera(id, d)` | `/cameras/:id` | `Camera` |
| DELETE | `api.deleteCamera(id)` | `/cameras/:id` | — |
| POST | `api.registerCamera(data)` | `/cameras/register` | `Camera` |
| GET | `api.getCameraDetections(id, limit)` | `/cameras/:id/detections?limit=N` | `Detection[]` |
| GET | `api.runAnalytics()` | `/cameras/analytics/run` | result |

#### `EdgeStatus` object shape
```json
{
  "camera": {
    "id": "uuid",
    "cameraId": "aicamera2",
    "name": "Camera 2",
    "location": "...",
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
| GET | `api.getDetectionImageUrl(id)` | returns URL string (not a fetch) |

**`getDetections` query params** (all optional):

| Param | Type | Notes |
|-------|------|-------|
| `cameraId` | string | filter by camera UUID |
| `search` | string | plate number search |
| `limit` | number | max records (dashboard uses 500) |
| `offset` | number | pagination |
| `sortBy` | string | field name, e.g. `timestamp` |
| `sortOrder` | string | `ASC` or `DESC` |
| `archived` | boolean | include archived records |

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

**Important**: `confidence` is a decimal string (e.g. `"0.9245"`), not a number. Use `parseFloat()`.

### Camera Health

| Method | Call | Endpoint |
|--------|------|----------|
| GET | `api.getCameraHealth(params)` | `/camera-health?...` |

**`getCameraHealth` query params**: `cameraId`, `limit`, `from` (ISO date), `to` (ISO date)

### Analytics & Events

| Method | Call | Endpoint |
|--------|------|----------|
| GET | `api.getAnalytics()` | `/analytics` |
| GET | `api.getSystemEvents(limit)` | `/system-events?limit=N` |
| GET | `api.getVisualizations()` | `/visualizations` |
| GET | `api.getAnalyticsEvents(limit)` | `/analytics-events?limit=N` |

---

## 8. Socket.IO (`src/composables/useSocket.js`)

Singleton pattern — one connection shared across all components.

```javascript
import { useSocket } from '@/composables/useSocket.js';
const { socket, connected } = useSocket();
// connected: Vue ref<boolean>, reactive
// socket: raw Socket.IO instance
```

**Connection config**:
- URL: `window.location.origin` (no hardcoded IP)
- Path: `/ws/` (nginx proxies to ws-service:3001)
- Transports: `['websocket', 'polling']`
- Reconnection: delay 2s, infinite attempts

**Events from server** (ws-service emits these):

| Event | Payload | When |
|-------|---------|------|
| `message_saved` | `{ cameraId, plate, confidence, timestamp }` | Detection written to DB |
| `camera_registered` | `{ cameraId, ... }` | New camera registered |
| `connect` | — | Socket connected |
| `disconnect` | reason string | Socket lost |

**Usage in `MainDashboard.vue`**:
```javascript
this.socket.on('message_saved',     () => this.loadDetections());
this.socket.on('camera_registered', () => this.loadCameras());
this.socket.on('connect',           () => { this.socketOk = true; });
this.socket.on('disconnect',        () => { this.socketOk = false; });
```

---

## 9. State Management (Pinia Stores)

### `cameras.store.js` — `useCamerasStore`

```
State:
  cameras[]     Camera list (from /cameras)
  edgeStatus[]  Edge status list (from /cameras/edge-status)
  loading       Boolean
  error         String|null

Getters:
  onlineCount   Number of cameras with status online/healthy/pass

Actions:
  fetchCameras()      → populates cameras[]
  fetchEdgeStatus()   → populates edgeStatus[]
```

Currently used only as a shared store; `MainDashboard.vue` fetches directly via `api` instead of the store (Phase C will migrate).

### `detections.store.js` — `useDetectionsStore`

```
State:
  recent[]      Detection[]  (last N detections)
  hourly[]      { label: '07', count: N }[]  (24 buckets)
  total         Number
  todayCount    Number
  loading       Boolean
  error         String|null

Actions:
  fetchRecent(limit=20)   → populates recent[], todayCount
  fetchHourly()           → populates hourly[], total (fetches 500)
```

**`buildHourlyBuckets` algorithm** (also in `MainDashboard.methods`):
1. Fetch 500 most-recent detections sorted DESC
2. For each detection, compute `hoursAgo = floor((now - timestamp) / 3600000)`
3. If `hoursAgo < 24`, increment `buckets[23 - hoursAgo]`
4. Map 24 buckets to `{ label: 'HH', count }` starting from `currentHour - 23`

---

## 10. `MainDashboard.vue` — Implemented View

**Route**: `/`  
**Data refresh**: every 10 seconds via `setInterval` + Socket.IO `message_saved`  
**Clock**: Bangkok time (`th-TH` locale), updated every 1 second

### Sections

1. **Page header** — title + live clock
2. **KPI row** — 4 `MetricCard` components in `auto-fit minmax(180px, 1fr)` grid
3. **Camera Status grid** — `auto-fill minmax(180px, 1fr)` tiles from `getCamerasEdgeStatus()`, clickable to `/cameras/:id`
4. **Detections — Last 24 Hours** — `HourlyChart` in a `.panel`
5. **Recent Detections feed** — last 20 detections in a 4-column grid row layout, clickable to `/detections/:id`
6. **Error banner** — shown when any API call fails

### KPI card data sources

| Card | Label | Value source | Accent |
|------|-------|-------------|--------|
| ◈ | Cameras Online | Filter `edgeStatus[]` where status = online/healthy/pass | green |
| ◎ | Detections Today | Count detections where `timestamp.toDateString() === today` | cyan |
| ⚡ | Total (24h) | Length of the 500-record fetch batch | cyan |
| ⊕ | Health Records | Length of `/camera-health?limit=50` response | amber |

### Camera tile status logic

```javascript
cameraStatus(item):
  if !item.latestHealth → 'unknown'
  else status = item.latestHealth.status.toLowerCase()
    'online'|'healthy'|'pass' → 'online'
    'degraded'|'warning'      → 'warning'
    else                      → 'offline'
```

### Confidence color classes

| Value | Class | Color |
|-------|-------|-------|
| ≥ 0.90 | `.text-green` | `--green` |
| ≥ 0.70 | `.text-amber` | `--amber` |
| < 0.70 | `.text-red` | `--red` |

---

## 11. `EdgeControl.vue` — Legacy View

**Route**: `/edge_control`  
**Status**: Functional but uses old styling (not design tokens, no sidebar-aware layout).  
Fetches `GET /cameras/edge-status` and renders camera cards with status bulbs (green/yellow/red) based on health timestamp age:
- Green: health reported within 5 minutes  
- Yellow: 5–15 minutes  
- Red: > 15 minutes

**Maintenance note**: Should be migrated to design system in Phase H.

---

## 12. Nginx Configuration

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
    # ⚠ Do NOT add =404 here. With alias, 4-arg try_files treats
    # /server/index.html as a file check (not URI redirect), which fails.
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

**Reload** (requires sudo password): `echo 'admin88366' | sudo -S nginx -s reload`

---

## 13. Development Workflow

### Standard cycle (Mac → GitHub → lprserver)

```bash
# 1. Edit source files on Mac in VSCode
# 2. Commit + push to pwd-vw/aicamera.git
git add <files>
git commit -m "feat: ..."
git push pwd-vw main

# 3. Deploy to lprserver (single SSH command)
sshpass -p 'admin88366' ssh -o PreferredAuthentications=password \
  devuser@100.95.46.128 \
  "cd ~/aicamera && git fetch myorigin && git merge myorigin/main --no-edit \
   && cd server/frontend-app && npm install && npm run build \
   && echo 'admin88366' | sudo -S nginx -s reload"

# 4. (Optional) Keep popwandee/aicamera.git in sync
sshpass -p 'admin88366' ssh -o PreferredAuthentications=password \
  devuser@100.95.46.128 \
  "cd ~/aicamera && git push origin main"
```

### Git remotes

| Machine | Remote name | URL | Push rights |
|---------|------------|-----|------------|
| Mac | `origin` | `popwandee/aicamera.git` | ❌ read-only |
| Mac | `pwd-vw` | `pwd-vw/aicamera.git` | ✅ push here |
| lprserver | `origin` | `popwandee/aicamera.git` | ✅ push here |
| lprserver | `myorigin` | `pwd-vw/aicamera.git` | ✅ pull from here |
| aicamera2 | `origin` | `popwandee/aicamera.git` (token in URL) | ✅ |

### Build output sizes (Phase B)

| File | Size | Gzipped |
|------|------|---------|
| `js/chunk-vendors.*.js` | 368 KB | 127 KB |
| `js/app.*.js` | 32 KB | 9 KB |
| `css/app.*.css` | 20 KB | 3.6 KB |

---

## 14. Known Issues and Gotchas

| Issue | Root cause | Fix applied |
|-------|-----------|------------|
| `PATCH /detections/image-path` returns 400 | NestJS route `/:id` was before `/image-path`; `ParseUUIDPipe` rejected `image-path` as invalid UUID | Moved `/image-path` route above `/:id` in `device.controller.ts` |
| `camera_health` columns all NULL after MQTT | Edge sends `cpu_usage`, `cpu_temp`, `memory_usage`; backend expected `cpu_percent`, `temperature_c` | Added fallback: `payload.cpu_percent ?? payload.cpu_usage` in `mqtt-service/backend-api.service.ts` |
| `/server/edge_control` returned 404 | `try_files $uri $uri/ /server/index.html =404` — 4-arg form with `alias` makes 3rd arg a file check | Removed `=404`, leaving 3 args |
| Vue build fails — `vue/multi-word-component-names` | Component `name:` must be ≥ 2 words | Always name components `AppSidebar`, `MainDashboard`, not `Sidebar` |
| Vue build fails — `vue/no-reserved-keys` | `data()` keys prefixed `_` or `$` are reserved | Use `clockTimer`, not `_clockTimer` |
| Image-detection timestamp linking | Edge filenames use Bangkok local time (no `Z`); server parses as local → correct | No code fix needed; design is intentional |
| `kpi.total` shows max 500 | `getDetections` fetch is capped at limit=500 | Accepted; a real count endpoint would fix this for large datasets |

---

## 15. Phase Roadmap

| Phase | View(s) | Key features | Status |
|-------|---------|-------------|--------|
| A | Foundation | Design tokens, Sidebar, MetricCard, StatusDot, router, App shell, all stub views | ✅ Done |
| B | MainDashboard | 24h hourly bar chart, Pinia stores, chart.js | ✅ Done |
| C | CameraList, CameraDetail | DataTable, Register Camera modal, 4-tab detail, cameras.store | 🔲 Next |
| D | DetectionList, DetectionDetail | FilterBar, ImageViewer, PlateTag, ConfidenceBar, CSV export, detections.store | 🔲 |
| E | AnalyticsDashboard | 30-day bar chart, confidence histogram, 7d×24h heatmap, camera comparison | 🔲 |
| F | RouteAnalysis, RouteDetail | Client-side route algorithm, routes.store | 🔲 |
| G | ConvoyDetection | Sliding-window convoy algorithm, parallel timeline SVG | 🔲 |
| H | Settings, SystemEvents | 4-tab settings (localStorage), apply design tokens to EdgeControl | 🔲 |
| I | All | Responsive layout, loading skeletons everywhere, error states + retry | 🔲 |

### Dependencies still to install (Phase C–I)

```bash
cd server/frontend-app
npm install leaflet @vue/leaflet   # Phase F (route maps) — optional
```

`date-fns` (^3.6.0) is already installed.

### Stores still to create

| File | Used by phase |
|------|-------------|
| `src/stores/analytics.store.js` | Phase E |
| `src/stores/routes.store.js` | Phase F |
| `src/stores/settings.store.js` | Phase H |
