<template>
  <div class="map-container">
    <div class="map-header">
      <h3>Map View</h3>
      <div class="map-controls">
        <button @click="refreshAll" :disabled="loading" class="btn-secondary">
          {{ loading ? 'Loading…' : 'Refresh' }}
        </button>
        <select v-model="selectedBase" class="select">
          <option value="satellite">Satellite</option>
          <option value="streets">Streets</option>
        </select>
        <label class="control">
          <input type="checkbox" v-model="showCameras" /> Cameras
        </label>
        <label class="control">
          <input type="checkbox" v-model="showDetections" /> Detections
        </label>
        <select v-model="selectedTimeRange" class="select" :disabled="!showDetections">
          <option value="1h">Last 1h</option>
          <option value="6h">Last 6h</option>
          <option value="24h">Last 24h</option>
        </select>
        <button @click="fitToData" class="btn-secondary">Fit</button>
      </div>
    </div>

    <div class="map-content">
      <div v-if="loading" class="loading-overlay">
        <div class="spinner"></div>
        <p>Loading map data…</p>
      </div>
      <div v-else-if="error" class="error-message">
        <p>{{ error }}</p>
        <button @click="refreshAll" class="btn-secondary">Retry</button>
      </div>
      <div v-else ref="mapContainer" class="leaflet-host"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { communicationService } from '../services';
import type { Camera, Detection } from '../services';

const mapContainer = ref<HTMLElement>();
const map = ref<any>(null);
const loading = ref(false);
const error = ref('');

// Data
const cameras = ref<Camera[]>([]);
const detections = ref<Detection[]>([]);

// Controls
const selectedBase = ref<'satellite' | 'streets'>('satellite');
const selectedTimeRange = ref<'1h' | '6h' | '24h'>('6h');
const showCameras = ref(true);
const showDetections = ref(false);

// Layers
let baseSatellite: any = null;
let baseStreets: any = null;
const cameraLayer: any = L.layerGroup();
const detectionLayer: any = L.layerGroup();

function initMap() {
  if (!mapContainer.value) return;

  // Create map
  map.value = L.map(mapContainer.value, {
    center: [37.773972, -122.431297],
    zoom: 11,
    zoomControl: true,
  });

  // Base layers
  baseSatellite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    {
      attribution: 'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics',
      maxZoom: 19,
    }
  ).addTo(map.value!);

  baseStreets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  });

  // Overlay layers
  cameraLayer.addTo(map.value!);
  detectionLayer.addTo(map.value!);
}

// layers are cleared within render functions

function getTimeWindow() {
  const end = new Date();
  const start = new Date(end);
  if (selectedTimeRange.value === '1h') start.setHours(end.getHours() - 1);
  else if (selectedTimeRange.value === '6h') start.setHours(end.getHours() - 6);
  else start.setHours(end.getHours() - 24);
  return { start: start.toISOString(), end: end.toISOString() };
}

async function loadCameras() {
  cameras.value = await communicationService.getCameras();
}

async function loadDetections() {
  const { start, end } = getTimeWindow();
  detections.value = await communicationService.getDetections({ startDate: start, endDate: end, limit: 500 });
}

function renderCameras() {
  cameraLayer.clearLayers();
  if (!showCameras.value) return;
  for (const cam of cameras.value) {
    if (cam.locationLat == null || cam.locationLng == null) continue;
    const color = cam.status === 'active' ? '#10b981' : cam.status === 'error' ? '#ef4444' : '#6b7280';
    const marker = L.circleMarker([cam.locationLat, cam.locationLng], {
      radius: 7,
      color,
      weight: 2,
      fillColor: color,
      fillOpacity: 0.6,
    }).bindPopup(
      `<div><strong>${cam.name}</strong><br/>Status: ${cam.status}<br/>${cam.locationAddress || ''}</div>`
    );
    marker.addTo(cameraLayer);
  }
}

function renderDetections() {
  detectionLayer.clearLayers();
  if (!showDetections.value) return;
  // Group by license plate to draw tracks
  const plateToPoints = new Map<string, Array<{ lat: number; lng: number; t: string }>>();
  for (const d of detections.value) {
    if (d.locationLat == null || d.locationLng == null) continue;
    const key = d.licensePlate || d.id;
    if (!plateToPoints.has(key)) plateToPoints.set(key, []);
    plateToPoints.get(key)!.push({ lat: d.locationLat, lng: d.locationLng, t: d.timestamp || d.createdAt });
  }
  plateToPoints.forEach(points => points.sort((a, b) => a.t.localeCompare(b.t)));

  plateToPoints.forEach((points, plate) => {
    // Points
    points.forEach(p => {
      L.circleMarker([p.lat, p.lng], {
        radius: 4,
        color: '#3b82f6',
        weight: 1,
        fillColor: '#3b82f6',
        fillOpacity: 0.5,
      }).addTo(detectionLayer);
    });
    // Track line when multiple points
    if (points.length > 1) {
      const latlngs = points.map(p => [p.lat, p.lng]) as [number, number][];
      L.polyline(latlngs, { color: '#2563eb', weight: 2, opacity: 0.8 }).addTo(detectionLayer)
        .bindPopup(`<div>Vehicle: ${plate}<br/>Positions: ${points.length}</div>`);
    }
  });
}

function applyBase() {
  if (!map.value || !baseSatellite || !baseStreets) return;
  if (selectedBase.value === 'satellite') {
    map.value!.addLayer(baseSatellite);
    map.value!.removeLayer(baseStreets);
  } else {
    map.value!.addLayer(baseStreets);
    map.value!.removeLayer(baseSatellite);
  }
}

function fitToData() {
  if (!map.value) return;
  const group: any = new (L as any).FeatureGroup();
  if (showCameras.value) group.addLayer(cameraLayer);
  if (showDetections.value) group.addLayer(detectionLayer);
  try {
    const bounds = group.getBounds();
    if (bounds.isValid()) map.value.fitBounds(bounds.pad(0.1));
  } catch { /* ignore */ }
}

async function refreshAll() {
  loading.value = true;
  error.value = '';
  try {
    const tasks: Array<Promise<any>> = [];
    tasks.push(loadCameras());
    if (showDetections.value) tasks.push(loadDetections());
    await Promise.all(tasks);
    renderCameras();
    renderDetections();
    if (cameras.value.length || detections.value.length) fitToData();
  } catch (e) {
    console.error(e);
    error.value = 'Failed to load map data';
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  initMap();
  applyBase();
  await refreshAll();
});

onBeforeUnmount(() => {
  if (map.value) {
    map.value.remove();
    map.value = null;
  }
});

watch(selectedBase, applyBase);
watch(showCameras, () => {
  renderCameras();
});
watch([showDetections, selectedTimeRange], async () => {
  if (showDetections.value) await loadDetections();
  renderDetections();
});
</script>

<style scoped>
.map-container {
  height: 600px;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  overflow: hidden;
  background: #f9fafb;
}

.map-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: white;
  border-bottom: 1px solid #e5e7eb;
}

.map-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.control {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
}

.map-content {
  height: calc(100% - 70px);
  position: relative;
}

.leaflet-host {
  position: absolute;
  inset: 0;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
  z-index: 10;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f4f6;
  border-top: 4px solid #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.btn-primary, .btn-secondary {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover {
  background: #2563eb;
}

.btn-secondary {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover {
  background: #e5e7eb;
}

.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.select {
  padding: 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
  background: white;
  font-size: 0.875rem;
}
</style>
