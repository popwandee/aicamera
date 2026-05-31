<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-box panel">
      <div class="modal-header">
        <span class="modal-title font-display">◈ Edit Camera</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <form @submit.prevent="submit" class="modal-form">
        <div class="field field-readonly">
          <label class="field-label">Camera ID</label>
          <div class="field-static font-data">{{ camera.cameraId }}</div>
        </div>

        <div class="field">
          <label class="field-label">Display Name</label>
          <input v-model="form.name" class="field-input"
                 placeholder="e.g. Main Entrance" autocomplete="off" />
        </div>

        <div class="field">
          <label class="field-label">Location</label>
          <input v-model="form.locationAddress" class="field-input"
                 placeholder="e.g. Building A — Gate 1" autocomplete="off" />
        </div>

        <div class="field">
          <label class="field-label">IP Address</label>
          <input v-model="form.ipAddress" class="field-input font-data"
                 placeholder="e.g. 100.110.20.53" autocomplete="off" />
        </div>

        <div class="field-row">
          <div class="field">
            <label class="field-label">Status</label>
            <select v-model="form.status" class="field-input field-select">
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="maintenance">Maintenance</option>
            </select>
          </div>
          <div class="field">
            <label class="field-label">Image Quality</label>
            <select v-model="form.imageQuality" class="field-input field-select">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
        </div>

        <div class="field-row">
          <div class="field">
            <label class="field-label">Upload Interval (s)</label>
            <input v-model.number="form.uploadInterval" type="number" min="10" max="3600"
                   class="field-input font-data" />
          </div>
          <div class="field field-toggle">
            <label class="field-label">Detection</label>
            <button type="button" class="toggle-btn"
                    :class="form.detectionEnabled ? 'toggle-on' : 'toggle-off'"
                    @click="form.detectionEnabled = !form.detectionEnabled">
              {{ form.detectionEnabled ? 'Enabled' : 'Disabled' }}
            </button>
          </div>
        </div>

        <div v-if="error" class="form-error">⚠ {{ error }}</div>

        <div class="modal-actions">
          <button type="button" class="btn" @click="$emit('close')">Cancel</button>
          <button type="submit" class="btn btn-primary" :disabled="busy">
            {{ busy ? 'Saving…' : 'Save Changes' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { useCamerasStore } from '@/stores/cameras.store.js';

export default {
  name: 'EditCameraModal',
  props: {
    camera: { type: Object, required: true },
  },
  emits: ['close', 'updated'],
  data() {
    return {
      form: {
        name:             this.camera.name            || '',
        locationAddress:  this.camera.locationAddress || '',
        ipAddress:        this.camera.ipAddress       || '',
        status:           this.camera.status          || 'active',
        imageQuality:     this.camera.imageQuality    || 'medium',
        uploadInterval:   this.camera.uploadInterval  ?? 60,
        detectionEnabled: this.camera.detectionEnabled ?? true,
      },
      busy:  false,
      error: null,
    };
  },
  methods: {
    async submit() {
      this.error = null;
      this.busy  = true;
      try {
        const store = useCamerasStore();
        const updated = await store.updateCamera(this.camera.id, {
          name:             this.form.name.trim()            || undefined,
          locationAddress:  this.form.locationAddress.trim() || undefined,
          ipAddress:        this.form.ipAddress.trim()       || undefined,
          status:           this.form.status,
          imageQuality:     this.form.imageQuality,
          uploadInterval:   this.form.uploadInterval,
          detectionEnabled: this.form.detectionEnabled,
        });
        this.$emit('updated', updated);
        this.$emit('close');
      } catch (e) {
        this.error = e.message;
      } finally {
        this.busy = false;
      }
    },
  },
};
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(8, 12, 18, 0.80);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; backdrop-filter: blur(2px);
}
.modal-box { width: 460px; max-width: calc(100vw - 2rem); }

.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 1.5rem;
}
.modal-title {
  font-size: 1.1rem; font-weight: 600; letter-spacing: 0.08em;
  color: var(--cyan); text-shadow: var(--cyan-glow);
}
.close-btn {
  background: none; border: none; color: var(--text-muted);
  cursor: pointer; font-size: 14px; padding: 2px 6px;
  transition: color var(--transition);
}
.close-btn:hover { color: var(--text-primary); }

.modal-form { display: flex; flex-direction: column; gap: 1rem; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }

.field-label {
  font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--text-secondary);
}
.field-static {
  font-size: 13px; color: var(--cyan-dim);
  padding: 7px 0; border-bottom: 1px solid var(--border-dim);
}
.field-input {
  background: var(--bg-surface); border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm); color: var(--text-primary);
  font-size: 13px; padding: 7px 10px; outline: none;
  transition: border-color var(--transition); width: 100%;
}
.field-input:focus { border-color: var(--border-bright); box-shadow: var(--cyan-glow); }
.field-input::placeholder { color: var(--text-muted); }
.field-select { cursor: pointer; }
.field-select option { background: var(--bg-surface); }

.field-toggle { justify-content: flex-start; }
.toggle-btn {
  margin-top: 2px; padding: 6px 14px;
  border-radius: var(--radius-sm); font-size: 12px;
  cursor: pointer; border: 1px solid; transition: all var(--transition);
  letter-spacing: 0.05em; font-weight: 500;
}
.toggle-on  { border-color: rgba(0,255,198,0.4); color: var(--green); background: rgba(0,255,198,0.08); }
.toggle-off { border-color: var(--border-dim);   color: var(--text-muted); background: transparent; }

.form-error {
  padding: 8px 10px; background: var(--red-dim);
  border: 1px solid rgba(255,61,87,0.3); border-radius: var(--radius-sm);
  color: var(--red); font-size: 12px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem; }
</style>
