import { defineStore } from 'pinia';
import api from '@/api/index.js';

export const useCamerasStore = defineStore('cameras', {
  state: () => ({
    cameras: [],
    edgeStatus: [],
    currentCamera: null,
    loading: false,
    error: null,
  }),
  persist: false,
  getters: {
    onlineCount: (s) => s.edgeStatus.filter(c => {
      if (!c.latestHealth) return false;
      const ageMins = (Date.now() - new Date(c.latestHealth.timestamp).getTime()) / 60000;
      if (ageMins > 15) return false;
      const st = (c.latestHealth?.status || '').toLowerCase();
      return st === 'online' || st === 'healthy' || st === 'pass' || st === 'ok';
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
    async fetchCamera(id) {
      try {
        this.currentCamera = await api.getCamera(id);
      } catch (e) {
        this.error = e.message;
      }
    },
    async registerCamera(data) {
      const cam = await api.createCamera(data);
      this.cameras.unshift(cam);
      return cam;
    },
    async updateCamera(id, data) {
      const updated = await api.updateCamera(id, data);
      const idx = this.cameras.findIndex(c => c.id === id);
      if (idx !== -1) this.cameras[idx] = updated;
      const edgeIdx = this.edgeStatus.findIndex(c => c.camera.id === id);
      if (edgeIdx !== -1) this.edgeStatus[edgeIdx] = { ...this.edgeStatus[edgeIdx], camera: updated };
      return updated;
    },
    async removeCamera(id) {
      await api.deleteCamera(id);
      this.cameras    = this.cameras.filter(c => c.id !== id);
      this.edgeStatus = this.edgeStatus.filter(c => c.camera.id !== id);
    },
  },
});
