import { defineStore } from 'pinia';
import api from '@/api/index.js';

export const useDetectionsStore = defineStore('detections', {
  state: () => ({
    recent: [],
    hourly: [],
    total: 0,
    todayCount: 0,
    loading: false,
    error: null,
  }),
  persist: false,
  actions: {
    async fetchRecent(limit = 20) {
      this.loading = true;
      try {
        const data = await api.getDetections({ limit, sortBy: 'timestamp', sortOrder: 'DESC' });
        this.recent = data;
        const today = new Date().toDateString();
        this.todayCount = data.filter(d => new Date(d.timestamp).toDateString() === today).length;
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    async fetchHourly() {
      try {
        const data = await api.getDetections({ limit: 500, sortBy: 'timestamp', sortOrder: 'DESC' });
        this.total = data.length;
        this.hourly = buildHourlyBuckets(data);
      } catch (e) {
        this.error = e.message;
      }
    },
  },
});

function buildHourlyBuckets(detections) {
  const now = new Date();
  const buckets = Array(24).fill(0);
  detections.forEach(d => {
    const diff = now - new Date(d.timestamp);
    const hoursAgo = Math.floor(diff / 3600000);
    if (hoursAgo >= 0 && hoursAgo < 24) {
      buckets[23 - hoursAgo]++;
    }
  });
  const curHour = now.getHours();
  return buckets.map((count, i) => {
    const h = (curHour - 23 + i + 24) % 24;
    return { label: String(h).padStart(2, '0'), count };
  });
}
