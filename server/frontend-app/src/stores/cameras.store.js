import { defineStore } from 'pinia';
import api from '@/api/index.js';

export const useCamerasStore = defineStore('cameras', {
  state: () => ({
    cameras: [],
    edgeStatus: [],
    loading: false,
    error: null,
  }),
  persist: false,
  getters: {
    onlineCount: (s) => s.edgeStatus.filter(c => {
      const st = (c.latestHealth?.status || '').toLowerCase();
      return st === 'online' || st === 'healthy' || st === 'pass';
    }).length,
  },
  actions: {
    async fetchCameras() {
      this.loading = true;
      try {
        this.cameras = await api.getCameras();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
    async fetchEdgeStatus() {
      this.loading = true;
      try {
        this.edgeStatus = await api.getCamerasEdgeStatus();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    },
  },
});
