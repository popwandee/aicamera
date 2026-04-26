<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-box panel">
      <div class="modal-header">
        <span class="modal-title font-display">⊕ Register Camera</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <form @submit.prevent="submit" class="modal-form">
        <div class="field">
          <label class="field-label">Camera ID <span class="required">*</span></label>
          <input v-model="form.cameraId" class="field-input font-data"
                 placeholder="e.g. CAM001" required autocomplete="off" />
          <span class="field-hint">Unique device identifier — must match the edge device config</span>
        </div>

        <div class="field">
          <label class="field-label">Display Name</label>
          <input v-model="form.name" class="field-input"
                 placeholder="e.g. Main Entrance" />
        </div>

        <div class="field">
          <label class="field-label">Location</label>
          <input v-model="form.location" class="field-input"
                 placeholder="e.g. Building A — Gate 1" />
        </div>

        <div class="field">
          <label class="field-label">IP Address</label>
          <input v-model="form.ip" class="field-input font-data"
                 placeholder="e.g. 192.168.1.100" />
        </div>

        <div v-if="error" class="form-error">⚠ {{ error }}</div>

        <div class="modal-actions">
          <button type="button" class="btn" @click="$emit('close')">Cancel</button>
          <button type="submit" class="btn btn-primary" :disabled="busy">
            <span v-if="busy">Registering…</span>
            <span v-else>Register</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { useCamerasStore } from '@/stores/cameras.store.js';

export default {
  name: 'RegisterCameraModal',
  emits: ['close', 'created'],
  data() {
    return {
      form: { cameraId: '', name: '', location: '', ip: '' },
      busy: false,
      error: null,
    };
  },
  methods: {
    async submit() {
      this.error = null;
      this.busy  = true;
      try {
        const store = useCamerasStore();
        const cam = await store.registerCamera({
          cameraId: this.form.cameraId.trim(),
          name:     this.form.name.trim()     || undefined,
          location: this.form.location.trim() || undefined,
          ip:       this.form.ip.trim()       || undefined,
          status:   'offline',
        });
        this.$emit('created', cam);
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
  position: fixed;
  inset: 0;
  background: rgba(8, 12, 18, 0.80);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.modal-box {
  width: 440px;
  max-width: calc(100vw - 2rem);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.modal-title {
  font-size: 1.1rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  transition: color var(--transition);
}
.close-btn:hover { color: var(--text-primary); }

.modal-form { display: flex; flex-direction: column; gap: 1rem; }

.field { display: flex; flex-direction: column; gap: 4px; }

.field-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-secondary);
}

.required { color: var(--red); margin-left: 2px; }

.field-input {
  background: var(--bg-surface);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  padding: 7px 10px;
  outline: none;
  transition: border-color var(--transition);
  width: 100%;
}
.field-input:focus { border-color: var(--border-bright); box-shadow: var(--cyan-glow); }
.field-input::placeholder { color: var(--text-muted); }

.field-hint { font-size: 11px; color: var(--text-muted); }

.form-error {
  padding: 8px 10px;
  background: var(--red-dim);
  border: 1px solid rgba(255,61,87,0.3);
  border-radius: var(--radius-sm);
  color: var(--red);
  font-size: 12px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}
</style>
