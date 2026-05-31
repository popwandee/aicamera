<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-box panel">
      <div class="modal-header">
        <span class="modal-title font-display">◎ Edit Detection</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <form @submit.prevent="submit" class="modal-form">
        <!-- Read-only meta -->
        <div class="meta-row">
          <div class="meta-chip font-data">{{ detection.camera?.cameraId || '—' }}</div>
          <div class="meta-chip font-data">{{ fmtTs(detection.timestamp) }}</div>
          <div class="meta-chip font-data text-muted">{{ shortId }}</div>
        </div>

        <div class="field">
          <label class="field-label">License Plate <span class="required">*</span></label>
          <input v-model="form.licensePlate" class="field-input font-thai font-data"
                 placeholder="e.g. กข 1234 กรุงเทพมหานคร"
                 required autocomplete="off" />
        </div>

        <div class="field-row">
          <div class="field">
            <label class="field-label">Status</label>
            <select v-model="form.status" class="field-input field-select">
              <option value="pending">Pending</option>
              <option value="processed">Processed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div class="field field-toggle">
            <label class="field-label">Archived</label>
            <button type="button" class="toggle-btn"
                    :class="form.archived ? 'toggle-amber' : 'toggle-dim'"
                    @click="form.archived = !form.archived">
              {{ form.archived ? 'Archived' : 'Active' }}
            </button>
          </div>
        </div>

        <div class="section-label">Vehicle Info <span class="optional">(optional)</span></div>

        <div class="field-row">
          <div class="field">
            <label class="field-label">Type</label>
            <select v-model="form.vehicleType" class="field-input field-select">
              <option value="">—</option>
              <option value="car">Car</option>
              <option value="truck">Truck</option>
              <option value="motorcycle">Motorcycle</option>
              <option value="bus">Bus</option>
              <option value="van">Van</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div class="field">
            <label class="field-label">Color</label>
            <input v-model="form.vehicleColor" class="field-input"
                   placeholder="e.g. White" autocomplete="off" />
          </div>
        </div>

        <div class="field-row">
          <div class="field">
            <label class="field-label">Make</label>
            <input v-model="form.vehicleMake" class="field-input"
                   placeholder="e.g. Toyota" autocomplete="off" />
          </div>
          <div class="field">
            <label class="field-label">Model</label>
            <input v-model="form.vehicleModel" class="field-input"
                   placeholder="e.g. Camry" autocomplete="off" />
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
import { useDetectionsStore } from '@/stores/detections.store.js';

export default {
  name: 'EditDetectionModal',
  props: {
    detection: { type: Object, required: true },
  },
  emits: ['close', 'updated'],
  data() {
    return {
      form: {
        licensePlate: this.detection.licensePlate || '',
        status:       this.detection.status       || 'pending',
        archived:     this.detection.archived     ?? false,
        vehicleType:  this.detection.vehicleType  || '',
        vehicleColor: this.detection.vehicleColor || '',
        vehicleMake:  this.detection.vehicleMake  || '',
        vehicleModel: this.detection.vehicleModel || '',
      },
      busy:  false,
      error: null,
    };
  },
  computed: {
    shortId() {
      return this.detection.id ? this.detection.id.slice(0, 8) + '…' : '';
    },
  },
  methods: {
    fmtTs(ts) {
      if (!ts) return '—';
      return new Date(ts).toLocaleString('th-TH', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },
    async submit() {
      this.error = null;
      this.busy  = true;
      try {
        const store = useDetectionsStore();
        const payload = {
          licensePlate: this.form.licensePlate.trim(),
          status:       this.form.status,
          archived:     this.form.archived,
          vehicleType:  this.form.vehicleType  || null,
          vehicleColor: this.form.vehicleColor.trim() || null,
          vehicleMake:  this.form.vehicleMake.trim()  || null,
          vehicleModel: this.form.vehicleModel.trim() || null,
        };
        const updated = await store.editDetection(this.detection.id, payload);
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
  background: rgba(8, 12, 18, 0.82);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; backdrop-filter: blur(2px);
}
.modal-box { width: 480px; max-width: calc(100vw - 2rem); }

.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 1.25rem;
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

.modal-form { display: flex; flex-direction: column; gap: 0.9rem; }

.meta-row {
  display: flex; gap: 0.5rem; flex-wrap: wrap;
  margin-bottom: 0.25rem;
}
.meta-chip {
  font-size: 11px; color: var(--text-muted);
  background: var(--bg-surface);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  padding: 3px 8px;
}

.field { display: flex; flex-direction: column; gap: 4px; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }

.field-label {
  font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--text-secondary);
}
.required { color: var(--red); margin-left: 2px; }

.section-label {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--text-muted); border-top: 1px solid var(--border-dim);
  padding-top: 0.75rem; margin-top: 0.1rem;
}
.optional { text-transform: none; letter-spacing: 0; color: var(--text-muted); font-size: 10px; }

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
.toggle-amber { border-color: rgba(255,171,64,0.45); color: var(--amber); background: rgba(255,171,64,0.08); }
.toggle-dim   { border-color: var(--border-dim); color: var(--text-muted); background: transparent; }

.form-error {
  padding: 8px 10px; background: var(--red-dim);
  border: 1px solid rgba(255,61,87,0.3); border-radius: var(--radius-sm);
  color: var(--red); font-size: 12px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.25rem; }
</style>
