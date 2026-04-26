<template>
  <span class="status-dot" :class="'dot-' + status" :title="title || status">
    <span class="dot-inner" />
  </span>
</template>

<script>
export default {
  name: 'StatusDot',
  props: {
    status: { type: String, default: 'unknown' }, // online|offline|warning|unknown
    title:  { type: String, default: '' },
  },
};
</script>

<style scoped>
.status-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}
.dot-inner {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}
.dot-online .dot-inner {
  background: var(--green);
  box-shadow: 0 0 0 2px rgba(0,230,118,0.25);
  animation: pulse-green 2s infinite;
}
.dot-offline .dot-inner  { background: var(--red); }
.dot-warning .dot-inner  { background: var(--amber); animation: pulse-amber 2s infinite; }
.dot-unknown .dot-inner  { background: var(--text-muted); }

@keyframes pulse-green {
  0%, 100% { box-shadow: 0 0 0 2px rgba(0,230,118,0.25); }
  50%       { box-shadow: 0 0 0 5px rgba(0,230,118,0.08); }
}
@keyframes pulse-amber {
  0%, 100% { box-shadow: 0 0 0 2px rgba(255,171,64,0.25); }
  50%       { box-shadow: 0 0 0 5px rgba(255,171,64,0.08); }
}
</style>
