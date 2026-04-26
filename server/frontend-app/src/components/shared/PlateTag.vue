<template>
  <span class="plate-tag font-thai" :class="'plate-' + size">
    {{ plate || '—' }}
  </span>
</template>

<script>
export default {
  name: 'PlateTag',
  props: {
    plate: { type: String, default: '' },
    size:  { type: String, default: 'md' }, // sm | md | lg
  },
};
</script>

<style scoped>
.plate-tag {
  display: inline-block;
  background: rgba(0, 200, 255, 0.06);
  border: 1px solid rgba(0, 200, 255, 0.28);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  letter-spacing: 0.06em;
  font-weight: 600;
  white-space: nowrap;
}
.plate-sm { font-size: 11px; padding: 1px 7px; }
.plate-md { font-size: 13px; padding: 3px 10px; }
.plate-lg { font-size: 1.15rem; padding: 6px 16px; letter-spacing: 0.1em; }
</style>
