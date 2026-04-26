<template>
  <div class="settings-view">

    <!-- Page header -->
    <div class="page-header">
      <div class="page-title font-display">
        <span class="page-icon">⚙</span> Settings
      </div>
      <div class="page-desc">Detection thresholds, display preferences, and alert configuration</div>
    </div>

    <!-- Tab bar -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { 'tab-active': activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span> {{ tab.label }}
      </button>
    </div>

    <!-- Tab 1: Detection -->
    <div class="panel tab-panel" v-show="activeTab === 'detection'">
      <div class="section-head">Detection &amp; Analysis</div>

      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Confidence Threshold</div>
          <div class="setting-desc">Plates below this confidence % are dimmed in tables</div>
        </div>
        <div class="setting-ctrl">
          <div class="slider-wrap">
            <input
              type="range" min="0" max="100" step="5"
              v-model.number="store.confThreshold"
              class="slider"
            />
            <span class="slider-val font-data">{{ store.confThreshold }}%</span>
          </div>
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Route Trip Gap</div>
          <div class="setting-desc">Detections of the same plate separated by more than this gap are split into separate trips</div>
        </div>
        <div class="setting-ctrl">
          <select class="ctrl-select" v-model.number="store.routeGapMin">
            <option :value="30">30 min</option>
            <option :value="60">1 hour</option>
            <option :value="120">2 hours</option>
            <option :value="240">4 hours</option>
            <option :value="480">8 hours</option>
          </select>
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Convoy Time Window</div>
          <div class="setting-desc">Time window used to detect co-appearing vehicles at the same camera</div>
        </div>
        <div class="setting-ctrl">
          <select class="ctrl-select" v-model.number="store.convoyWindowMin">
            <option :value="2">2 min</option>
            <option :value="5">5 min</option>
            <option :value="10">10 min</option>
            <option :value="15">15 min</option>
            <option :value="30">30 min</option>
          </select>
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Convoy Min Cameras</div>
          <div class="setting-desc">Minimum number of cameras a plate pair must share to be classified as a convoy</div>
        </div>
        <div class="setting-ctrl">
          <select class="ctrl-select" v-model.number="store.convoyMinCameras">
            <option :value="2">2 cameras</option>
            <option :value="3">3 cameras</option>
            <option :value="4">4 cameras</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Tab 2: Display -->
    <div class="panel tab-panel" v-show="activeTab === 'display'">
      <div class="section-head">Display &amp; Interface</div>

      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Rows per Page</div>
          <div class="setting-desc">Default page size in the Detection List table</div>
        </div>
        <div class="setting-ctrl">
          <select class="ctrl-select" v-model.number="store.rowsPerPage">
            <option :value="10">10</option>
            <option :value="25">25</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Date Format</div>
          <div class="setting-desc">Locale used for all timestamps across the dashboard</div>
        </div>
        <div class="setting-ctrl">
          <select class="ctrl-select" v-model="store.dateLocale">
            <option value="th-TH">Thai (TH)</option>
            <option value="en-US">English (US)</option>
            <option value="en-GB">English (GB)</option>
          </select>
          <div class="preview font-data">{{ datePreview }}</div>
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Auto-Refresh Interval</div>
          <div class="setting-desc">How often live views (Dashboard, System Events) poll for new data</div>
        </div>
        <div class="setting-ctrl">
          <select class="ctrl-select" v-model.number="store.refreshInterval">
            <option :value="0">Off</option>
            <option :value="30">30 seconds</option>
            <option :value="60">1 minute</option>
            <option :value="300">5 minutes</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Tab 3: Alerts -->
    <div class="panel tab-panel" v-show="activeTab === 'alerts'">
      <div class="section-head">Alert Configuration</div>

      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Browser Alerts</div>
          <div class="setting-desc">Enable browser Notification API for real-time alerts (requires permission)</div>
        </div>
        <div class="setting-ctrl">
          <label class="toggle">
            <input type="checkbox" v-model="store.alertsEnabled" @change="requestPermission" />
            <span class="toggle-track">
              <span class="toggle-thumb" />
            </span>
            <span class="toggle-label">{{ store.alertsEnabled ? 'Enabled' : 'Disabled' }}</span>
          </label>
        </div>
      </div>

      <div class="setting-row" :class="{ 'row-dimmed': !store.alertsEnabled }">
        <div class="setting-info">
          <div class="setting-label">Confidence Alert Threshold</div>
          <div class="setting-desc">Alert when a detection's confidence exceeds this value</div>
        </div>
        <div class="setting-ctrl">
          <div class="slider-wrap">
            <input
              type="range" min="50" max="100" step="5"
              v-model.number="store.alertConfMin"
              class="slider"
              :disabled="!store.alertsEnabled"
            />
            <span class="slider-val font-data">{{ store.alertConfMin }}%</span>
          </div>
        </div>
      </div>

      <div class="setting-row" :class="{ 'row-dimmed': !store.alertsEnabled }">
        <div class="setting-info">
          <div class="setting-label">Convoy Alerts</div>
          <div class="setting-desc">Notify when a new convoy pair is detected in Convoy Detection view</div>
        </div>
        <div class="setting-ctrl">
          <label class="toggle">
            <input type="checkbox" v-model="store.alertOnConvoy" :disabled="!store.alertsEnabled" />
            <span class="toggle-track">
              <span class="toggle-thumb" />
            </span>
            <span class="toggle-label">{{ store.alertOnConvoy ? 'Enabled' : 'Disabled' }}</span>
          </label>
        </div>
      </div>

      <div class="perm-banner" v-if="permState === 'denied'">
        ⚠ Browser notifications are blocked. Allow them in your browser's site settings.
      </div>
    </div>

    <!-- Tab 4: About -->
    <div class="panel tab-panel" v-show="activeTab === 'about'">
      <div class="section-head">System Information</div>

      <div class="info-grid">
        <div class="info-item">
          <div class="info-label">Application</div>
          <div class="info-val font-data">AI Camera Dashboard</div>
        </div>
        <div class="info-item">
          <div class="info-label">Project</div>
          <div class="info-val font-data">PWD Vision Works</div>
        </div>
        <div class="info-item">
          <div class="info-label">API Base</div>
          <div class="info-val font-data text-muted">{{ apiBase }}</div>
        </div>
        <div class="info-item">
          <div class="info-label">Current URL</div>
          <div class="info-val font-data text-muted">{{ currentUrl }}</div>
        </div>
        <div class="info-item">
          <div class="info-label">Build</div>
          <div class="info-val font-data text-muted">Phase H · 2026</div>
        </div>
        <div class="info-item">
          <div class="info-label">Tech Stack</div>
          <div class="info-val font-data text-muted">Vue 3 · Pinia · Chart.js · NestJS · PostgreSQL</div>
        </div>
      </div>

      <div class="divider" />

      <div class="section-head" style="margin-top: 0;">Reset</div>
      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">Reset All Settings</div>
          <div class="setting-desc">Restore all settings to their default values (stored in localStorage)</div>
        </div>
        <div class="setting-ctrl">
          <button class="btn-danger" @click="confirmReset">
            Reset to Defaults
          </button>
        </div>
      </div>
      <div class="reset-confirm" v-if="showResetConfirm">
        <span class="text-muted">Are you sure?</span>
        <button class="btn-confirm" @click="doReset">Yes, reset</button>
        <button class="btn-cancel" @click="showResetConfirm = false">Cancel</button>
      </div>
    </div>

    <!-- Saved toast -->
    <transition name="toast">
      <div class="toast" v-if="toastVisible">✓ Settings saved</div>
    </transition>

  </div>
</template>

<script>
import { useSettingsStore } from '@/stores/settings.store.js';

const TABS = [
  { id: 'detection', label: 'Detection', icon: '◈' },
  { id: 'display',   label: 'Display',   icon: '▣' },
  { id: 'alerts',    label: 'Alerts',    icon: '◉' },
  { id: 'about',     label: 'About',     icon: '⊙' },
];

export default {
  name: 'AppSettings',

  setup() {
    return { store: useSettingsStore() };
  },

  data() {
    return {
      activeTab:       'detection',
      tabs:            TABS,
      permState:       'default',
      showResetConfirm: false,
      toastVisible:    false,
      toastTimer:      null,
    };
  },

  mounted() {
    if ('Notification' in window) {
      this.permState = Notification.permission;
    }
    // Watch store for any change to show save toast
    this.$watch(
      () => JSON.stringify(this.store.$state),
      () => this.showToast(),
      { deep: false },
    );
  },

  computed: {
    datePreview() {
      return new Date().toLocaleString(this.store.dateLocale, {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },
    apiBase() {
      return typeof window !== 'undefined'
        ? window.location.origin + '/server/api'
        : '/server/api';
    },
    currentUrl() {
      return typeof window !== 'undefined' ? window.location.origin : '';
    },
  },

  methods: {
    async requestPermission() {
      if (!this.store.alertsEnabled) return;
      if (!('Notification' in window)) return;
      if (Notification.permission !== 'granted') {
        const result = await Notification.requestPermission();
        this.permState = result;
        if (result !== 'granted') {
          this.store.alertsEnabled = false;
        }
      }
    },

    confirmReset() {
      this.showResetConfirm = true;
    },

    doReset() {
      this.store.resetAll();
      this.showResetConfirm = false;
    },

    showToast() {
      clearTimeout(this.toastTimer);
      this.toastVisible = true;
      this.toastTimer = setTimeout(() => { this.toastVisible = false; }, 1800);
    },
  },
};
</script>

<style scoped>
.settings-view { max-width: 820px; }

/* Page header */
.page-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.page-title {
  font-size: 1.6rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.page-icon { opacity: 0.8; }
.page-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 1rem;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 18px;
  background: var(--bg-panel);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  font-family: var(--font-ui);
  cursor: pointer;
  transition: all var(--transition);
}
.tab-btn:hover { color: var(--text-primary); border-color: var(--border-card); }
.tab-active {
  color: var(--cyan) !important;
  border-color: var(--border-card) !important;
  border-bottom-color: var(--bg-panel) !important;
  background: var(--bg-panel) !important;
}
.tab-icon { font-size: 12px; opacity: 0.8; }

/* Tab panel */
.tab-panel { border-radius: 0 var(--radius-md) var(--radius-md) var(--radius-md); }

.section-head {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: var(--text-muted);
  margin-bottom: 1.25rem;
}

/* Setting row */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border-dim);
  transition: opacity var(--transition);
}
.setting-row:last-child { border-bottom: none; }
.row-dimmed { opacity: 0.38; pointer-events: none; }

.setting-info { flex: 1; min-width: 0; }
.setting-label { font-size: 13px; color: var(--text-primary); font-weight: 500; margin-bottom: 3px; }
.setting-desc  { font-size: 11px; color: var(--text-muted); line-height: 1.5; }

.setting-ctrl { flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }

/* Select control */
.ctrl-select {
  background: var(--bg-surface);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 12px;
  font-family: var(--font-ui);
  padding: 5px 10px;
  outline: none;
  min-width: 130px;
  transition: border-color var(--transition);
}
.ctrl-select:focus { border-color: var(--cyan-dim); }

/* Slider */
.slider-wrap { display: flex; align-items: center; gap: 10px; }
.slider {
  -webkit-appearance: none;
  appearance: none;
  width: 140px;
  height: 4px;
  background: var(--bg-surface);
  border: 1px solid var(--border-card);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--cyan);
  cursor: pointer;
  box-shadow: 0 0 6px rgba(0,200,255,0.4);
}
.slider:disabled::-webkit-slider-thumb { background: var(--text-muted); box-shadow: none; }
.slider-val { font-size: 12px; color: var(--cyan-dim); min-width: 36px; text-align: right; }

/* Date preview */
.preview { font-size: 10px; color: var(--text-muted); margin-top: 2px; }

/* Toggle switch */
.toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; user-select: none; }
.toggle input { display: none; }
.toggle-track {
  position: relative;
  width: 38px;
  height: 20px;
  background: var(--bg-surface);
  border: 1px solid var(--border-card);
  border-radius: 10px;
  transition: background var(--transition), border-color var(--transition);
  flex-shrink: 0;
}
.toggle input:checked + .toggle-track {
  background: rgba(0,200,255,0.18);
  border-color: var(--cyan-dim);
}
.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: left var(--transition), background var(--transition);
}
.toggle input:checked ~ .toggle-track .toggle-thumb {
  left: 20px;
  background: var(--cyan);
}
/* Fix: thumb is inside track, so the checked selector must target sibling track */
.toggle input:checked + .toggle-track > .toggle-thumb {
  left: 20px;
  background: var(--cyan);
}
.toggle-label { font-size: 12px; color: var(--text-secondary); min-width: 56px; }

/* Permission banner */
.perm-banner {
  margin-top: 1rem;
  padding: 0.65rem 1rem;
  background: var(--amber-dim);
  border: 1px solid rgba(255,171,64,0.3);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--amber);
}

/* Info grid (About tab) */
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
.info-item { display: flex; flex-direction: column; gap: 3px; }
.info-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); }
.info-val { font-size: 12px; color: var(--text-primary); }

.divider { border: none; border-top: 1px solid var(--border-dim); margin: 1.25rem 0 1rem; }

/* Reset buttons */
.btn-danger {
  background: rgba(255,61,87,0.08);
  border: 1px solid rgba(255,61,87,0.3);
  border-radius: var(--radius-sm);
  color: var(--red);
  font-size: 12px;
  padding: 6px 14px;
  cursor: pointer;
  transition: background var(--transition);
}
.btn-danger:hover { background: rgba(255,61,87,0.14); }

.reset-confirm {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 0.75rem;
  font-size: 12px;
}
.btn-confirm {
  background: rgba(255,61,87,0.15);
  border: 1px solid rgba(255,61,87,0.35);
  border-radius: var(--radius-sm);
  color: var(--red);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
}
.btn-cancel {
  background: transparent;
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
}

/* Save toast */
.toast {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: var(--bg-panel);
  border: 1px solid rgba(0,230,118,0.35);
  border-radius: var(--radius-md);
  color: var(--green);
  font-size: 12px;
  padding: 8px 16px;
  box-shadow: var(--shadow-card);
  z-index: 9999;
}
.toast-enter-active, .toast-leave-active { transition: opacity 0.25s, transform 0.25s; }
.toast-enter-from { opacity: 0; transform: translateY(8px); }
.toast-leave-to   { opacity: 0; transform: translateY(8px); }

/* Misc */
.text-muted { color: var(--text-muted); }
</style>
