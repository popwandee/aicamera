import { defineStore } from 'pinia';
import api from '@/api/index.js';

// Two-hour gap between detections of the same plate → new trip
const TRIP_GAP_MS = 2 * 60 * 60 * 1000;

// Separator that won't appear in camera IDs
const SEP = '|||';

function buildTrips(detections) {
  const byPlate = {};
  detections.forEach(d => {
    if (!d.licensePlate) return;
    if (!byPlate[d.licensePlate]) byPlate[d.licensePlate] = [];
    byPlate[d.licensePlate].push(d);
  });

  const trips = [];
  for (const [plate, dets] of Object.entries(byPlate)) {
    dets.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // Split detections into trips by time gap
    const groups = [[dets[0]]];
    for (let i = 1; i < dets.length; i++) {
      const gap = new Date(dets[i].timestamp) - new Date(dets[i - 1].timestamp);
      if (gap > TRIP_GAP_MS) groups.push([dets[i]]);
      else groups[groups.length - 1].push(dets[i]);
    }

    groups.forEach(group => {
      // De-duplicate consecutive same-camera appearances
      const camSeq = [];
      group.forEach(d => {
        const cam = d.camera?.cameraId || d.cameraId || 'unknown';
        if (camSeq[camSeq.length - 1] !== cam) camSeq.push(cam);
      });
      if (!camSeq.length) return;

      const startTs = new Date(group[0].timestamp);
      const endTs   = new Date(group[group.length - 1].timestamp);
      trips.push({
        plate,
        routeKey:    camSeq.join(' → '),
        cameras:     camSeq,
        cameraCount: camSeq.length,
        detections:  group.length,
        startTs,
        endTs,
        durationMs:  endTs - startTs,
        durationMin: Math.round((endTs - startTs) / 60000),
        firstDetId:  group[0].id,
        lastDetId:   group[group.length - 1].id,
      });
    });
  }
  return trips;
}

export const useRoutesStore = defineStore('routes', {
  state: () => ({
    detections:       [],
    loading:          false,
    error:            null,
    filterMinCameras: 1,
    filterSearch:     '',
    filterDateFrom:   '',
    filterDateTo:     '',
  }),
  persist: false,
  getters: {
    // All trips computed from detections
    trips() {
      return buildTrips(this.detections);
    },

    // Routes aggregated by routeKey, sorted by trip count desc
    routes() {
      const map = {};
      this.trips.forEach(t => {
        if (!map[t.routeKey]) {
          map[t.routeKey] = {
            routeKey:    t.routeKey,
            cameras:     t.cameras,
            cameraCount: t.cameraCount,
            tripCount:   0,
            plateSet:    new Set(),
            totalDur:    0,
            durCount:    0,
            lastSeen:    null,
          };
        }
        const r = map[t.routeKey];
        r.tripCount++;
        r.plateSet.add(t.plate);
        if (t.durationMs > 0) { r.totalDur += t.durationMin; r.durCount++; }
        if (!r.lastSeen || t.endTs > r.lastSeen) r.lastSeen = t.endTs;
      });
      return Object.values(map).map(r => ({
        routeKey:       r.routeKey,
        cameras:        r.cameras,
        cameraCount:    r.cameraCount,
        tripCount:      r.tripCount,
        uniquePlates:   r.plateSet.size,
        avgDurationMin: r.durCount > 0 ? Math.round(r.totalDur / r.durCount) : 0,
        lastSeen:       r.lastSeen,
      })).sort((a, b) => b.tripCount - a.tripCount);
    },

    // Client-side filtered routes list
    filteredRoutes() {
      let list = this.routes;
      if (this.filterMinCameras > 1) {
        list = list.filter(r => r.cameraCount >= this.filterMinCameras);
      }
      if (this.filterSearch.trim()) {
        const s = this.filterSearch.trim().toLowerCase();
        list = list.filter(r => r.routeKey.toLowerCase().includes(s));
      }
      if (this.filterDateFrom) {
        const from = new Date(this.filterDateFrom).getTime();
        list = list.filter(r => r.lastSeen && r.lastSeen.getTime() >= from);
      }
      if (this.filterDateTo) {
        const to = new Date(this.filterDateTo + 'T23:59:59').getTime();
        list = list.filter(r => r.lastSeen && r.lastSeen.getTime() <= to);
      }
      return list;
    },

    // Camera-to-camera transition counts for flow diagram
    transitions() {
      const map = {};
      this.trips.forEach(t => {
        for (let i = 0; i < t.cameras.length - 1; i++) {
          const key = `${t.cameras[i]}${SEP}${t.cameras[i + 1]}`;
          map[key] = (map[key] || 0) + 1;
        }
      });
      return Object.entries(map).map(([key, count]) => {
        const [from, to] = key.split(SEP);
        return { from, to, count };
      }).sort((a, b) => b.count - a.count);
    },

    // Unique camera IDs sorted by avg position in trips (entry cameras first)
    allCameraIds() {
      const posSum = {};
      const posCnt = {};
      this.trips.forEach(t => {
        t.cameras.forEach((cam, i) => {
          posSum[cam] = (posSum[cam] || 0) + i;
          posCnt[cam] = (posCnt[cam] || 0) + 1;
        });
      });
      return Object.keys(posSum).sort(
        (a, b) => posSum[a] / posCnt[a] - posSum[b] / posCnt[b],
      );
    },

    totalTrips()       { return this.trips.length; },
    multiCameraTrips() { return this.trips.filter(t => t.cameraCount > 1).length; },
    uniquePlatesTotal() {
      const set = new Set(this.trips.map(t => t.plate));
      return set.size;
    },
  },
  actions: {
    async fetchDetections() {
      this.loading = true;
      this.error   = null;
      try {
        this.detections = await api.getDetections({
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
  },
});
