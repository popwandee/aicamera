import { defineStore } from 'pinia';
import api from '@/api/index.js';

export const useAnalyticsStore = defineStore('analytics', {
  state: () => ({
    analytics:  [],   // Analytics[] from /analytics (per-camera daily rows)
    detections: [],   // Detection[] up to 2000 for client-side aggregation
    loading:    false,
    error:      null,
  }),
  persist: false,
  getters: {
    // [{ date: 'YYYY-MM-DD', count: N }] for last 30 days, oldest-first
    dailyTotals() {
      const map = {};
      for (let i = 29; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        map[d.toISOString().slice(0, 10)] = 0;
      }
      this.analytics.forEach(a => {
        const key = String(a.date).slice(0, 10);
        if (key in map) map[key] += Number(a.totalDetections);
      });
      return Object.entries(map).map(([date, count]) => ({ date, count }));
    },

    // [{ cameraId, name, count }] sorted by count desc
    cameraComparison() {
      const map = {};
      this.analytics.forEach(a => {
        if (!map[a.cameraId]) {
          map[a.cameraId] = {
            cameraId: a.camera?.cameraId || a.cameraId,
            name:     a.camera?.name     || a.camera?.cameraId || a.cameraId,
            count:    0,
          };
        }
        map[a.cameraId].count += Number(a.totalDetections);
      });
      return Object.values(map).sort((a, b) => b.count - a.count);
    },

    // [{ label: '0–10', count }] 10 buckets of 10% each
    confidenceHistogram() {
      const buckets = Array(10).fill(0);
      this.detections.forEach(d => {
        const c = parseFloat(d.confidence);
        if (!isNaN(c)) buckets[Math.min(Math.floor(c * 10), 9)]++;
      });
      return buckets.map((count, i) => ({ label: `${i * 10}–${(i + 1) * 10}`, count }));
    },

    // { cells: number[7][24], dayLabels: string[7] } — last 7 days, oldest-first
    heatmapData() {
      const cells = Array.from({ length: 7 }, () => Array(24).fill(0));
      const today = new Date();
      const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate());
      this.detections.forEach(d => {
        const ts = new Date(d.timestamp);
        const dayStart = new Date(ts.getFullYear(), ts.getMonth(), ts.getDate());
        const daysAgo = Math.round((todayStart - dayStart) / 86400000);
        if (daysAgo < 0 || daysAgo > 6) return;
        cells[6 - daysAgo][ts.getHours()]++;
      });
      const labels = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date(todayStart);
        d.setDate(d.getDate() - i);
        labels.push(d.toLocaleDateString('en', { weekday: 'short', month: 'numeric', day: 'numeric' }));
      }
      return { cells, dayLabels: labels };
    },

    // [{ plate, count }] top 20 by frequency, from loaded detections
    topPlates() {
      const map = {};
      this.detections.forEach(d => {
        if (d.licensePlate) map[d.licensePlate] = (map[d.licensePlate] || 0) + 1;
      });
      return Object.entries(map)
        .map(([plate, count]) => ({ plate, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 20);
    },

    // Lifetime total from analytics (0 if update_daily_analytics never run)
    totalDetections() {
      return this.analytics.reduce((s, a) => s + Number(a.totalDetections), 0);
    },

    uniquePlatesAll() {
      const set = new Set(this.detections.map(d => d.licensePlate).filter(Boolean));
      return set.size;
    },

    avgConfidence() {
      if (!this.detections.length) return 0;
      const sum = this.detections.reduce((s, d) => s + (parseFloat(d.confidence) || 0), 0);
      return sum / this.detections.length;
    },
  },
  actions: {
    async fetchAll() {
      this.loading = true;
      this.error   = null;
      try {
        const [analytics, detections] = await Promise.all([
          api.getAnalytics(),
          api.getDetections({ limit: 2000, sortBy: 'timestamp', sortOrder: 'DESC' }),
        ]);
        this.analytics  = analytics;
        this.detections = detections;
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
  },
});
