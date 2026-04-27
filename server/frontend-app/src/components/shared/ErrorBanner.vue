<template>
  <div class="error-banner" v-if="message">
    <span class="err-icon">⚠</span>
    <span class="err-msg">{{ message }}</span>
    <button v-if="retry" class="retry-btn" @click="$emit('retry')">↺ Retry</button>
  </div>
</template>

<script>
export default {
  name: 'ErrorBanner',
  props: {
    message: { type: String, default: '' },
    retry:   { type: Boolean, default: true },
  },
  emits: ['retry'],
};
</script>

<style scoped>
.error-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: var(--red-dim);
  border: 1px solid rgba(255, 61, 87, 0.3);
  border-radius: var(--radius-md);
  color: var(--red);
  font-size: 13px;
}
.err-icon { flex-shrink: 0; }
.err-msg  { flex: 1; }
.retry-btn {
  flex-shrink: 0;
  background: rgba(255, 61, 87, 0.12);
  border: 1px solid rgba(255, 61, 87, 0.35);
  border-radius: var(--radius-sm);
  color: var(--red);
  font-size: 11px;
  font-family: var(--font-ui);
  padding: 4px 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition);
}
.retry-btn:hover { background: rgba(255, 61, 87, 0.22); }
</style>
