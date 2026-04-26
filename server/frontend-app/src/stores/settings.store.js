import { defineStore } from 'pinia';

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    // Detection
    confThreshold:    50,     // min confidence % highlighted in tables (0–100)
    routeGapMin:      120,    // trip-split gap in minutes (routes.store)
    convoyWindowMin:  10,     // convoy co-occurrence window in minutes
    convoyMinCameras: 2,      // convoy min cameras threshold

    // Display
    rowsPerPage:     25,      // rows per page in Detection List
    dateLocale:      'th-TH', // date/time formatting locale
    refreshInterval: 0,       // 0 = off; otherwise seconds between auto-refresh

    // Alerts
    alertsEnabled: false,     // enable browser Notification API alerts
    alertConfMin:  90,        // alert when plate confidence >= this %
    alertOnConvoy: false,     // alert when new convoy pair detected
  }),

  persist: true,

  getters: {
    confDecimal() { return this.confThreshold / 100; },
    routeGapMs()  { return this.routeGapMin * 60000; },
    convoyWindowMs() { return this.convoyWindowMin * 60000; },
  },

  actions: {
    resetAll() {
      this.$reset();
    },
  },
});
