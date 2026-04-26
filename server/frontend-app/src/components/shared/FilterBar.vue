<template>
  <div class="filter-bar panel">
    <!-- Plate search -->
    <div class="filter-group filter-wide">
      <label class="filter-label">Plate</label>
      <input
        class="filter-input font-thai"
        :value="modelValue.plateSearch"
        placeholder="Search plate…"
        @input="debounce('plateSearch', $event.target.value)"
      />
    </div>

    <!-- Camera select -->
    <div class="filter-group">
      <label class="filter-label">Camera</label>
      <select class="filter-select" :value="modelValue.cameraId"
              @change="emit('cameraId', $event.target.value)">
        <option value="">All cameras</option>
        <option v-for="c in cameras" :key="c.id" :value="c.id">
          {{ c.name || c.cameraId }}
        </option>
      </select>
    </div>

    <!-- Date from -->
    <div class="filter-group">
      <label class="filter-label">From</label>
      <input type="date" class="filter-input font-data"
             :value="modelValue.dateFrom"
             @change="emit('dateFrom', $event.target.value)" />
    </div>

    <!-- Date to -->
    <div class="filter-group">
      <label class="filter-label">To</label>
      <input type="date" class="filter-input font-data"
             :value="modelValue.dateTo"
             @change="emit('dateTo', $event.target.value)" />
    </div>

    <!-- Min confidence -->
    <div class="filter-group">
      <label class="filter-label">Min Conf.</label>
      <select class="filter-select font-data"
              :value="modelValue.minConfidence"
              @change="emit('minConfidence', $event.target.value)">
        <option value="">Any</option>
        <option value="0.7">≥ 70%</option>
        <option value="0.8">≥ 80%</option>
        <option value="0.9">≥ 90%</option>
        <option value="0.95">≥ 95%</option>
      </select>
    </div>

    <!-- Archived toggle -->
    <div class="filter-group filter-check">
      <label class="check-label">
        <input type="checkbox"
               :checked="modelValue.archived"
               @change="emit('archived', $event.target.checked)" />
        <span>Archived</span>
      </label>
    </div>

    <!-- Result count + clear -->
    <div class="filter-actions">
      <span class="result-count font-data">{{ count.toLocaleString() }} result{{ count !== 1 ? 's' : '' }}</span>
      <button class="clear-btn" @click="$emit('clear')" title="Clear all filters">✕ Clear</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FilterBar',
  emits: ['update:modelValue', 'clear', 'search'],
  props: {
    modelValue: {
      type: Object,
      default: () => ({
        cameraId: '', plateSearch: '', dateFrom: '',
        dateTo: '', minConfidence: '', archived: false,
      }),
    },
    cameras: { type: Array,  default: () => [] },
    count:   { type: Number, default: 0 },
  },
  data() {
    return { debounceTimer: null };
  },
  methods: {
    emit(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value });
    },
    debounce(key, value) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.emit(key, value), 320);
    },
  },
};
</script>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  margin-bottom: 1rem;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 110px;
}
.filter-wide { min-width: 180px; flex: 1; }

.filter-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--text-muted);
}

.filter-input, .filter-select {
  background: var(--bg-surface);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-ui);
  font-size: 12px;
  padding: 5px 8px;
  outline: none;
  transition: border-color var(--transition);
  height: 30px;
  width: 100%;
}
.filter-input:focus, .filter-select:focus { border-color: var(--border-bright); }
.filter-input::placeholder { color: var(--text-muted); }
.filter-select option { background: var(--bg-panel); }

/* Date input calendar icon color */
input[type="date"]::-webkit-calendar-picker-indicator {
  filter: invert(0.5) sepia(1) saturate(2) hue-rotate(160deg);
  cursor: pointer;
}

.filter-check { justify-content: flex-end; padding-bottom: 2px; }
.check-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
}
.check-label input { accent-color: var(--cyan); width: 13px; height: 13px; }

.filter-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-left: auto;
  padding-bottom: 1px;
}

.result-count {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.clear-btn {
  background: none;
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 11px;
  padding: 4px 9px;
  transition: color var(--transition), border-color var(--transition);
  white-space: nowrap;
}
.clear-btn:hover { color: var(--red); border-color: rgba(255,61,87,0.4); }
</style>
