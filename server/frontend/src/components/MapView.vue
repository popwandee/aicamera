<template>
  <div class="map-container">
    <!-- Map Header with Controls -->
    <div class="map-header">
      <div class="header-left">
        <h3>Server Map View</h3>
        <div class="map-info">
          <span class="info-item">
            <i class="icon">📹</i>
            {{ cameras.length }} Cameras
          </span>
          <span class="info-item">
            <i class="icon">🎯</i>
            {{ totalDetections }} Detections
          </span>
        </div>
      </div>
      
      <div class="map-controls">
        <!-- Map Layer Controls -->
        <div class="control-group">
          <label>Map Layer:</label>
          <select v-model="selectedLayer" @change="changeMapLayer" class="select">
            <option value="satellite">Satellite</option>
            <option value="street">Street</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </div>
        
        <!-- Data Filter Controls -->
        <div class="control-group">
          <label>Show:</label>
          <div class="checkbox-group">
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="showCameras" 
                @change="updateMapDisplay"
              >
              Cameras
            </label>
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="showDetections" 
                @change="updateMapDisplay"
              >
              Detections
            </label>
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="showTracks" 
                @change="updateMapDisplay"
              >
              Vehicle Tracks
            </label>
          </div>
        </div>
        
        <!-- Camera Status Filter -->
        <div class="control-group">
          <label>Camera Status:</label>
          <select v-model="cameraStatusFilter" @change="updateCameraMarkers" class="select">
            <option value="all">All</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive</option>
            <option value="error">Error</option>
          </select>
        </div>
        
        <!-- Detection Type Filter -->
        <div class="control-group">
          <label>Detection Type:</label>
          <select v-model="detectionTypeFilter" @change="updateDetectionMarkers" class="select">
            <option value="all">All Types</option>
            <option value="vehicle">Vehicles</option>
            <option value="person">Persons</option>
            <option value="object">Objects</option>
          </select>
        </div>
        
        <!-- Action Buttons -->
        <div class="action-buttons">
          <button @click="refreshMap" :disabled="loading" class="btn-secondary">
            <i class="icon">🔄</i>
            {{ loading ? 'Loading...' : 'Refresh' }}
          </button>
          <button @click="fitToBounds" class="btn-secondary">
            <i class="icon">🎯</i>
            Fit to Data
          </button>
          <button @click="toggleFullscreen" class="btn-secondary">
            <i class="icon">⛶</i>
            Fullscreen
          </button>
        </div>
      </div>
    </div>
    
    <!-- Map Content -->
    <div ref="mapContainer" class="map-content" :class="{ fullscreen: isFullscreen }">
      <div v-if="loading" class="loading-overlay">
        <div class="spinner"></div>
        <p>Loading map data...</p>
      </div>
      
      <div v-else-if="error" class="error-message">
        <p>{{ error }}</p>
        <button @click="refreshMap" class="btn-secondary">Retry</button>
      </div>
    </div>
    
    <!-- Map Legend -->
    <div class="map-legend" v-if="!isFullscreen">
      <h4>Legend</h4>
      <div class="legend-items">
        <div class="legend-item">
          <div class="legend-marker camera active"></div>
          <span>Active Camera</span>
        </div>
        <div class="legend-item">
          <div class="legend-marker camera inactive"></div>
          <span>Inactive Camera</span>
        </div>
        <div class="legend-item">
          <div class="legend-marker camera error"></div>
          <span>Error Camera</span>
        </div>
        <div class="legend-item">
          <div class="legend-marker detection vehicle"></div>
          <span>Vehicle Detection</span>
        </div>
        <div class="legend-item">
          <div class="legend-marker detection person"></div>
          <span>Person Detection</span>
        </div>
        <div class="legend-item">
          <div class="legend-track"></div>
          <span>Vehicle Track</span>
        </div>
      </div>
    </div>
    
    <!-- Side Panel for Details -->
    <div class="side-panel" :class="{ open: selectedCamera || selectedDetection }">
      <div class="panel-header">
        <h4>{{ selectedCamera ? 'Camera Details' : 'Detection Details' }}</h4>
        <button @click="closePanel" class="close-btn">×</button>
      </div>
      
      <div class="panel-content" v-if="selectedCamera">
        <div class="detail-section">
          <h5>{{ selectedCamera.name }}</h5>
          <div class="status-badge" :class="selectedCamera.status">
            {{ selectedCamera.status }}
          </div>
        </div>
        
        <div class="detail-grid">
          <div class="detail-item">
            <label>Location:</label>
            <span>{{ selectedCamera.address }}</span>
          </div>
          <div class="detail-item">
            <label>Coordinates:</label>
            <span>{{ selectedCamera.latitude.toFixed(6) }}, {{ selectedCamera.longitude.toFixed(6) }}</span>
          </div>
          <div class="detail-item">
            <label>Type:</label>
            <span>{{ selectedCamera.cameraType }}</span>
          </div>
          <div class="detail-item">
            <label>Resolution:</label>
            <span>{{ selectedCamera.resolution }}</span>
          </div>
          <div class="detail-item">
            <label>FPS:</label>
            <span>{{ selectedCamera.fps }}</span>
          </div>
          <div class="detail-item">
            <label>Detections:</label>
            <span>{{ selectedCamera.detectionCount }}</span>
          </div>
          <div class="detail-item">
            <label>Last Seen:</label>
            <span>{{ formatDate(selectedCamera.lastSeen) }}</span>
          </div>
        </div>
        
        <div class="panel-actions">
          <button @click="viewCameraStream(selectedCamera)" class="btn-primary">
            <i class="icon">📺</i>
            View Stream
          </button>
          <button @click="viewCameraDetections(selectedCamera)" class="btn-secondary">
            <i class="icon">🎯</i>
            View Detections
          </button>
        </div>
      </div>
      
      <div class="panel-content" v-if="selectedDetection">
        <div class="detail-section">
          <h5>{{ selectedDetection.type }} Detection</h5>
          <div class="confidence-badge">
            {{ Math.round(selectedDetection.confidence * 100) }}% Confidence
          </div>
        </div>
        
        <div class="detail-grid">
          <div class="detail-item">
            <label>Camera:</label>
            <span>{{ getCameraName(selectedDetection.cameraId) }}</span>
          </div>
          <div class="detail-item">
            <label>Timestamp:</label>
            <span>{{ formatDate(selectedDetection.timestamp) }}</span>
          </div>
          <div class="detail-item" v-if="selectedDetection.metadata.vehicleType">
            <label>Vehicle Type:</label>
            <span>{{ selectedDetection.metadata.vehicleType }}</span>
          </div>
          <div class="detail-item" v-if="selectedDetection.metadata.color">
            <label>Color:</label>
            <span>{{ selectedDetection.metadata.color }}</span>
          </div>
          <div class="detail-item" v-if="selectedDetection.metadata.licensePlate">
            <label>License Plate:</label>
            <span>{{ selectedDetection.metadata.licensePlate }}</span>
          </div>
          <div class="detail-item" v-if="selectedDetection.metadata.speed">
            <label>Speed:</label>
            <span>{{ selectedDetection.metadata.speed }} mph</span>
          </div>
        </div>
        
        <div class="panel-actions">
          <button @click="viewDetectionImage(selectedDetection)" class="btn-primary">
            <i class="icon">🖼️</i>
            View Image
          </button>
          <button @click="viewDetectionVideo(selectedDetection)" class="btn-secondary">
            <i class="icon">🎥</i>
            View Video
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import L from 'leaflet';
import { mockDataService, type CameraLocation, type Detection, type VehicleTrack } from '../services/mockData.service';

// Import Leaflet CSS
import 'leaflet/dist/leaflet.css';

// Fix for default markers in Leaflet with Vite
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Reactive data
const mapContainer = ref<HTMLElement>();
const loading = ref(false);
const error = ref('');
const cameras = ref<CameraLocation[]>([]);
const detections = ref<Detection[]>([]);
const vehicleTracks = ref<VehicleTrack[]>([]);
const selectedCamera = ref<CameraLocation | null>(null);
const selectedDetection = ref<Detection | null>(null);
const isFullscreen = ref(false);

// Map controls
const selectedLayer = ref('satellite');
const showCameras = ref(true);
const showDetections = ref(true);
const showTracks = ref(true);
const cameraStatusFilter = ref('all');
const detectionTypeFilter = ref('all');

// Map instance
let map: L.Map | null = null;
let cameraMarkers: L.Marker[] = [];
let detectionMarkers: L.Marker[] = [];
let trackPolylines: L.Polyline[] = [];

// Computed properties
const totalDetections = computed(() => detections.value.length);

const filteredCameras = computed(() => {
  if (cameraStatusFilter.value === 'all') return cameras.value;
  return cameras.value.filter(c => c.status === cameraStatusFilter.value);
});

const filteredDetections = computed(() => {
  if (detectionTypeFilter.value === 'all') return detections.value;
  return detections.value.filter(d => d.type === detectionTypeFilter.value);
});

// Map initialization
const initializeMap = async () => {
  if (!mapContainer.value) return;
  
  try {
    // Create map with satellite view
    map = L.map(mapContainer.value, {
      center: [37.7749, -122.4194], // San Francisco coordinates
      zoom: 15,
      zoomControl: true,
      attributionControl: true
    });

    // Add satellite tile layer
    const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    });

    const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });

    const hybridLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    });

    // Add default layer
    satelliteLayer.addTo(map);

    // Store layers for switching
    (map as any).layers = {
      satellite: satelliteLayer,
      street: streetLayer,
      hybrid: hybridLayer
    };

    // Add layer control
    L.control.layers({
      'Satellite': satelliteLayer,
      'Street': streetLayer,
      'Hybrid': hybridLayer
    }).addTo(map);

    // Load initial data
    await loadMapData();
    
  } catch (err) {
    console.error('Map initialization error:', err);
    error.value = 'Failed to initialize map';
  }
};

// Load map data
const loadMapData = async () => {
  loading.value = true;
  error.value = '';
  
  try {
    const [camerasData, detectionsData, tracksData] = await Promise.all([
      mockDataService.getCameras(),
      mockDataService.getDetections(),
      mockDataService.getVehicleTracks()
    ]);
    
    cameras.value = camerasData;
    detections.value = detectionsData;
    vehicleTracks.value = tracksData;
    
    // Update map display
    updateMapDisplay();
    
  } catch (err) {
    error.value = 'Failed to load map data';
    console.error('Map data loading error:', err);
  } finally {
    loading.value = false;
  }
};

// Update map display based on current filters
const updateMapDisplay = () => {
  if (!map) return;
  
  updateCameraMarkers();
  updateDetectionMarkers();
  updateTrackPolylines();
};

// Update camera markers
const updateCameraMarkers = () => {
  if (!map) return;
  
  // Clear existing camera markers
  cameraMarkers.forEach(marker => map!.removeLayer(marker));
  cameraMarkers = [];
  
  if (!showCameras.value) return;
  
  const filtered = filteredCameras.value;
  
  filtered.forEach(camera => {
    const marker = createCameraMarker(camera);
    marker.addTo(map!);
    cameraMarkers.push(marker);
  });
};

// Create camera marker
const createCameraMarker = (camera: CameraLocation): L.Marker => {
  const icon = createCameraIcon(camera.status);
  const marker = L.marker([camera.latitude, camera.longitude], { icon });
  
  const popupContent = `
    <div class="camera-popup">
      <h4>${camera.name}</h4>
      <p><strong>Status:</strong> <span class="status-${camera.status}">${camera.status}</span></p>
      <p><strong>Type:</strong> ${camera.cameraType}</p>
      <p><strong>Detections:</strong> ${camera.detectionCount}</p>
      <p><strong>Last Seen:</strong> ${formatDate(camera.lastSeen)}</p>
      <button onclick="window.selectCameraFromMap('${camera.id}')" class="popup-btn">View Details</button>
    </div>
  `;
  
  marker.bindPopup(popupContent);
  
  marker.on('click', () => {
    selectedCamera.value = camera;
    selectedDetection.value = null;
  });
  
  return marker;
};

// Create camera icon based on status
const createCameraIcon = (status: string): L.DivIcon => {
  const colors = {
    active: '#10b981',
    inactive: '#6b7280',
    error: '#ef4444',
    maintenance: '#f59e0b'
  };
  
  const color = colors[status as keyof typeof colors] || '#6b7280';
  
  return L.divIcon({
    className: 'custom-camera-marker',
    html: `
      <div style="
        background-color: ${color};
        width: 20px;
        height: 20px;
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
        color: white;
      ">📹</div>
    `,
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  });
};

// Update detection markers
const updateDetectionMarkers = () => {
  if (!map) return;
  
  // Clear existing detection markers
  detectionMarkers.forEach(marker => map!.removeLayer(marker));
  detectionMarkers = [];
  
  if (!showDetections.value) return;
  
  const filtered = filteredDetections.value;
  
  filtered.forEach(detection => {
    const marker = createDetectionMarker(detection);
    marker.addTo(map!);
    detectionMarkers.push(marker);
  });
};

// Create detection marker
const createDetectionMarker = (detection: Detection): L.Marker => {
  const icon = createDetectionIcon(detection.type, detection.confidence);
  const marker = L.marker([detection.location.latitude, detection.location.longitude], { icon });
  
  const popupContent = `
    <div class="detection-popup">
      <h4>${detection.type} Detection</h4>
      <p><strong>Confidence:</strong> ${Math.round(detection.confidence * 100)}%</p>
      <p><strong>Camera:</strong> ${getCameraName(detection.cameraId)}</p>
      <p><strong>Time:</strong> ${formatDate(detection.timestamp)}</p>
      ${detection.metadata.vehicleType ? `<p><strong>Vehicle:</strong> ${detection.metadata.vehicleType}</p>` : ''}
      ${detection.metadata.color ? `<p><strong>Color:</strong> ${detection.metadata.color}</p>` : ''}
      <button onclick="window.selectDetectionFromMap('${detection.id}')" class="popup-btn">View Details</button>
    </div>
  `;
  
  marker.bindPopup(popupContent);
  
  marker.on('click', () => {
    selectedDetection.value = detection;
    selectedCamera.value = null;
  });
  
  return marker;
};

// Create detection icon
const createDetectionIcon = (type: string, confidence: number): L.DivIcon => {
  const colors = {
    vehicle: '#3b82f6',
    person: '#10b981',
    object: '#f59e0b'
  };
  
  const color = colors[type as keyof typeof colors] || '#6b7280';
  const size = Math.max(8, Math.min(16, confidence * 16));
  
  return L.divIcon({
    className: 'custom-detection-marker',
    html: `
      <div style="
        background-color: ${color};
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        border: 2px solid white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      "></div>
    `,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2]
  });
};

// Update track polylines
const updateTrackPolylines = () => {
  if (!map) return;
  
  // Clear existing polylines
  trackPolylines.forEach(polyline => map!.removeLayer(polyline));
  trackPolylines = [];
  
  if (!showTracks.value) return;
  
  vehicleTracks.value.forEach(track => {
    if (track.detections.length > 1) {
      const coordinates = track.detections.map(d => [d.location.latitude, d.location.longitude]);
      const polyline = L.polyline(coordinates, {
        color: '#ef4444',
        weight: 3,
        opacity: 0.8
      });
      
      polyline.bindPopup(`
        <div class="track-popup">
          <h4>Vehicle Track</h4>
          <p><strong>Vehicle ID:</strong> ${track.vehicleId}</p>
          <p><strong>Detections:</strong> ${track.detections.length}</p>
          <p><strong>Distance:</strong> ${track.totalDistance.toFixed(2)} km</p>
          <p><strong>Avg Speed:</strong> ${track.averageSpeed.toFixed(1)} mph</p>
        </div>
      `);
      
      polyline.addTo(map!);
      trackPolylines.push(polyline);
    }
  });
};

// Map control functions
const changeMapLayer = () => {
  if (!map) return;
  
  // Remove all layers
  Object.values((map as any).layers).forEach((layer: any) => {
    map!.removeLayer(layer);
  });
  
  // Add selected layer
  const selectedLayerObj = (map as any).layers[selectedLayer.value];
  if (selectedLayerObj) {
    selectedLayerObj.addTo(map);
  }
};

const fitToBounds = () => {
  if (!map) return;
  
  const bounds = L.latLngBounds();
  
  // Add camera bounds
  if (showCameras.value && filteredCameras.value.length > 0) {
    filteredCameras.value.forEach(camera => {
      bounds.extend([camera.latitude, camera.longitude]);
    });
  }
  
  // Add detection bounds
  if (showDetections.value && filteredDetections.value.length > 0) {
    filteredDetections.value.forEach(detection => {
      bounds.extend([detection.location.latitude, detection.location.longitude]);
    });
  }
  
  if (!bounds.isValid()) return;
  
  map.fitBounds(bounds, { padding: [20, 20] });
};

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value;
  nextTick(() => {
    if (map) {
      map.invalidateSize();
    }
  });
};

const refreshMap = () => {
  loadMapData();
};

// Panel functions
const closePanel = () => {
  selectedCamera.value = null;
  selectedDetection.value = null;
};

// Utility functions
const getCameraName = (cameraId: string): string => {
  const camera = cameras.value.find(c => c.id === cameraId);
  return camera ? camera.name : 'Unknown Camera';
};

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleString();
};

// Action functions
const viewCameraStream = (camera: CameraLocation) => {
  console.log('View camera stream:', camera.id);
  // Implement camera stream viewing
};

const viewCameraDetections = (camera: CameraLocation) => {
  console.log('View camera detections:', camera.id);
  // Implement camera detections viewing
};

const viewDetectionImage = (detection: Detection) => {
  console.log('View detection image:', detection.id);
  // Implement detection image viewing
};

const viewDetectionVideo = (detection: Detection) => {
  console.log('View detection video:', detection.id);
  // Implement detection video viewing
};

// Global functions for popup buttons
(window as any).selectCameraFromMap = (cameraId: string) => {
  const camera = cameras.value.find(c => c.id === cameraId);
  if (camera) {
    selectedCamera.value = camera;
    selectedDetection.value = null;
  }
};

(window as any).selectDetectionFromMap = (detectionId: string) => {
  const detection = detections.value.find(d => d.id === detectionId);
  if (detection) {
    selectedDetection.value = detection;
    selectedCamera.value = null;
  }
};

// Lifecycle
onMounted(async () => {
  await nextTick();
  await initializeMap();
});

onUnmounted(() => {
  if (map) {
    map.remove();
  }
});

// Watchers
watch([showCameras, showDetections, showTracks], () => {
  updateMapDisplay();
});

watch(cameraStatusFilter, () => {
  updateCameraMarkers();
});

watch(detectionTypeFilter, () => {
  updateDetectionMarkers();
});
</script>

<style scoped>
.map-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f9fafb;
  position: relative;
}

.map-container.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
}

.map-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1rem;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
  gap: 2rem;
}

.header-left h3 {
  margin: 0 0 0.5rem 0;
  color: #1f2937;
  font-size: 1.5rem;
  font-weight: 600;
}

.map-info {
  display: flex;
  gap: 1rem;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.map-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-start;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 120px;
}

.control-group label {
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  margin: 0;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
}

.map-content {
  flex: 1;
  position: relative;
  min-height: 0;
}

.map-content.fullscreen {
  height: calc(100vh - 120px);
}

.loading-overlay, .error-message {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.95);
  z-index: 100;
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

.map-legend {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  z-index: 10;
  min-width: 200px;
}

.map-legend h4 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #1f2937;
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #6b7280;
}

.legend-marker {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}

.legend-marker.camera.active {
  background-color: #10b981;
}

.legend-marker.camera.inactive {
  background-color: #6b7280;
}

.legend-marker.camera.error {
  background-color: #ef4444;
}

.legend-marker.detection.vehicle {
  background-color: #3b82f6;
}

.legend-marker.detection.person {
  background-color: #10b981;
}

.legend-track {
  width: 20px;
  height: 3px;
  background-color: #ef4444;
  border-radius: 2px;
}

.side-panel {
  position: absolute;
  top: 0;
  right: -400px;
  width: 400px;
  height: 100%;
  background: white;
  border-left: 1px solid #e5e7eb;
  box-shadow: -4px 0 6px -1px rgba(0, 0, 0, 0.1);
  transition: right 0.3s ease;
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.side-panel.open {
  right: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
}

.panel-header h4 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #1f2937;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #6b7280;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #374151;
}

.panel-content {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

.detail-section {
  margin-bottom: 1.5rem;
}

.detail-section h5 {
  margin: 0 0 0.5rem 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.status-badge.active {
  background-color: #dcfce7;
  color: #166534;
}

.status-badge.inactive {
  background-color: #f3f4f6;
  color: #374151;
}

.status-badge.error {
  background-color: #fee2e2;
  color: #991b1b;
}

.status-badge.maintenance {
  background-color: #fef3c7;
  color: #92400e;
}

.confidence-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
  background-color: #dbeafe;
  color: #1e40af;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  margin: 1.5rem 0;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.detail-item label {
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-item span {
  font-size: 0.875rem;
  color: #1f2937;
}

.panel-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

.btn-primary, .btn-secondary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s;
  text-decoration: none;
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
  border-radius: 0.375rem;
  background: white;
  font-size: 0.875rem;
  color: #374151;
}

.select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Leaflet popup styles */
:deep(.leaflet-popup-content-wrapper) {
  border-radius: 0.5rem;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

:deep(.leaflet-popup-content) {
  margin: 0.75rem;
  font-size: 0.875rem;
}

:deep(.camera-popup h4),
:deep(.detection-popup h4),
:deep(.track-popup h4) {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
}

:deep(.camera-popup p),
:deep(.detection-popup p),
:deep(.track-popup p) {
  margin: 0.25rem 0;
  color: #6b7280;
}

:deep(.status-active) {
  color: #10b981;
  font-weight: 500;
}

:deep(.status-inactive) {
  color: #6b7280;
  font-weight: 500;
}

:deep(.status-error) {
  color: #ef4444;
  font-weight: 500;
}

:deep(.popup-btn) {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 500;
}

:deep(.popup-btn:hover) {
  background: #2563eb;
}

/* Responsive design */
@media (max-width: 1024px) {
  .map-header {
    flex-direction: column;
    align-items: stretch;
    gap: 1rem;
  }
  
  .map-controls {
    justify-content: space-between;
  }
  
  .side-panel {
    width: 100%;
    right: -100%;
  }
}

@media (max-width: 768px) {
  .map-controls {
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .control-group {
    min-width: auto;
  }
  
  .action-buttons {
    flex-wrap: wrap;
  }
  
  .map-legend {
    position: relative;
    top: auto;
    right: auto;
    margin: 1rem;
    width: auto;
  }
}
</style>
