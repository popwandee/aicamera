import { defineStore } from 'pinia';
import api from '@/api/index.js';

const PAGE_SIZE = 50;

export const useDetectionsStore = defineStore('detections', {
  state: () => ({
    items:      [],   // raw server results (up to 500)
    recent:     [],   // for MainDashboard feed
    hourly:     [],   // for MainDashboard chart
    total:      0,
    todayCount: 0,
    page:       0,
    loading:    false,
    error:      null,
    filters: {
      cameraId:      '',
      plateSearch:   '',
      dateFrom:      '',
      dateTo:        '',
      minConfidence: '',
      archived:      false,
    },
  }),
  persist: false,
  getters: {
    // client-side date + confidence filter over server-fetched items
    filtered(state) {
      let list = state.items;
      const f = state.filters;
      if (f.dateFrom) {
        const from = new Date(f.dateFrom).getTime();
        list = list.filter(d => new Date(d.timestamp).getTime() >= from);
      }
      if (f.dateTo) {
        const to = new Date(f.dateTo + 'T23:59:59').getTime();
        list = list.filter(d => new Date(d.timestamp).getTime() <= to);
      }
      if (f.minConfidence) {
        const min = parseFloat(f.minConfidence);
        list = list.filter(d => parseFloat(d.confidence) >= min);
      }
      return list;
    },
    currentPage(state) {
      const start = state.page * PAGE_SIZE;
      return this.filtered.slice(start, start + PAGE_SIZE);
    },
    pageCount() {
      return Math.max(1, Math.ceil(this.filtered.length / PAGE_SIZE));
    },
    hasNext(state) {
      return state.page < this.pageCount - 1;
    },
    hasPrev(state) {
      return state.page > 0;
    },
  },
  actions: {
    async fetchFiltered() {
      this.loading = true;
      this.error   = null;
      this.page    = 0;
      try {
        const f = this.filters;
        this.items = await api.getDetections({
          limit:     500,
          sortBy:    'timestamp',
          sortOrder: 'DESC',
          cameraId:  f.cameraId    || undefined,
          search:    f.plateSearch || undefined,
          archived:  f.archived    || undefined,
        });
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    nextPage()  { if (this.hasNext)  this.page++; },
    prevPage()  { if (this.hasPrev)  this.page--; },
    goToPage(n) { this.page = Math.max(0, Math.min(n, this.pageCount - 1)); },
    setFilter(key, value) {
      this.filters[key] = value;
      this.page = 0;
    },
    resetFilters() {
      this.filters = {
        cameraId: '', plateSearch: '', dateFrom: '',
        dateTo: '', minConfidence: '', archived: false,
      };
      this.page = 0;
    },

    // MainDashboard: recent feed
    async fetchRecent(limit = 20) {
      this.loading = true;
      try {
        const data = await api.getDetections({ limit, sortBy: 'timestamp', sortOrder: 'DESC' });
        this.recent    = data;
        const today    = new Date().toDateString();
        this.todayCount = data.filter(d => new Date(d.timestamp).toDateString() === today).length;
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },

    // MainDashboard: hourly chart
    async fetchHourly() {
      try {
        const data  = await api.getDetections({ limit: 500, sortBy: 'timestamp', sortOrder: 'DESC' });
        this.total  = data.length;
        this.hourly = buildHourlyBuckets(data);
      } catch (e) {
        this.error = e.message;
      }
    },
  },
});

function buildHourlyBuckets(detections) {
  const now     = new Date();
  const buckets = Array(24).fill(0);
  detections.forEach(d => {
    const hoursAgo = Math.floor((now - new Date(d.timestamp)) / 3600000);
    if (hoursAgo >= 0 && hoursAgo < 24) buckets[23 - hoursAgo]++;
  });
  const curHour = now.getHours();
  return buckets.map((count, i) => {
    const h = (curHour - 23 + i + 24) % 24;
    return { label: String(h).padStart(2, '0'), count };
  });
}

export { PAGE_SIZE };
