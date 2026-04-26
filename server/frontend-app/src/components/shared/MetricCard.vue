<template>
  <div class="metric-card">
    <div class="metric-icon">{{ icon }}</div>
    <div class="metric-body">
      <div class="metric-value font-data" :class="valueClass">
        <span v-if="loading" class="shimmer">──</span>
        <span v-else>{{ formattedValue }}</span>
      </div>
      <div class="metric-label">{{ label }}</div>
      <div v-if="sub" class="metric-sub">{{ sub }}</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MetricCard',
  props: {
    icon:    { type: String, default: '◈' },
    label:   { type: String, required: true },
    value:   { type: [Number, String], default: null },
    sub:     { type: String, default: '' },
    loading: { type: Boolean, default: false },
    accent:  { type: String, default: 'cyan' }, // cyan|green|amber|red
  },
  computed: {
    valueClass() { return `text-${this.accent}`; },
    formattedValue() {
      if (this.value === null || this.value === undefined) return '–';
      if (typeof this.value === 'number' && this.value >= 1000)
        return this.value.toLocaleString();
      return this.value;
    },
  },
};
</script>

<style scoped>
.metric-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  padding: 1.1rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  box-shadow: var(--shadow-card);
  transition: border-color var(--transition);
}
.metric-card:hover { border-color: var(--border-bright); }
.metric-icon { font-size: 1.6rem; opacity: 0.7; }
.metric-value {
  font-size: 1.8rem;
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.02em;
}
.metric-label {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-top: 4px;
}
.metric-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.shimmer {
  display: inline-block;
  color: var(--text-muted);
  animation: blink 1.2s infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
</style>
