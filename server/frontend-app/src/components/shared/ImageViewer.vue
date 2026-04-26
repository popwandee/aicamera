<template>
  <div class="viewer-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <div class="viewer-shell">
      <!-- Close button -->
      <button class="viewer-close" @click="$emit('close')">✕</button>

      <!-- Caption top -->
      <div class="viewer-caption-top" v-if="caption.plate">
        <span class="font-thai plate-text">{{ caption.plate }}</span>
        <span class="conf-text font-data" v-if="caption.confidence">
          {{ caption.confidence }}
        </span>
      </div>

      <!-- Image area -->
      <div class="viewer-img-wrap">
        <img v-if="!imgError"
             :src="src"
             class="viewer-img"
             :class="{ loaded: imgLoaded }"
             @load="imgLoaded = true"
             @error="imgError = true"
             alt="detection image" />
        <div v-if="!imgLoaded && !imgError" class="viewer-loading">Loading…</div>
        <div v-if="imgError" class="viewer-error text-muted">Image not available</div>
      </div>

      <!-- Caption bottom -->
      <div class="viewer-caption-bottom">
        <span class="font-data text-muted" v-if="caption.camera">{{ caption.camera }}</span>
        <span class="font-data text-muted" v-if="caption.timestamp">{{ caption.timestamp }}</span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ImageViewer',
  emits: ['close'],
  props: {
    src: { type: String, required: true },
    caption: {
      type: Object,
      default: () => ({ plate: '', confidence: '', camera: '', timestamp: '' }),
    },
  },
  data() {
    return { imgLoaded: false, imgError: false };
  },
  mounted() {
    document.addEventListener('keydown', this.onKey);
  },
  beforeUnmount() {
    document.removeEventListener('keydown', this.onKey);
  },
  methods: {
    onKey(e) {
      if (e.key === 'Escape') this.$emit('close');
    },
  },
};
</script>

<style scoped>
.viewer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(4, 8, 14, 0.93);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(4px);
}

.viewer-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: min(900px, 96vw);
  max-height: 92vh;
  gap: 0.5rem;
}

.viewer-close {
  position: absolute;
  top: -2.5rem;
  right: 0;
  background: none;
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  padding: 4px 10px;
  transition: color var(--transition), border-color var(--transition);
}
.viewer-close:hover { color: var(--text-primary); border-color: var(--border-bright); }

.viewer-caption-top {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.plate-text {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--cyan);
  letter-spacing: 0.08em;
  text-shadow: var(--cyan-glow);
}
.conf-text { font-size: 13px; color: var(--text-secondary); }

.viewer-img-wrap {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  background: var(--bg-panel);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.viewer-img {
  display: block;
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  opacity: 0;
  transition: opacity 0.3s ease;
}
.viewer-img.loaded { opacity: 1; }
.viewer-loading, .viewer-error {
  padding: 3rem 4rem;
  font-size: 13px;
}

.viewer-caption-bottom {
  display: flex;
  gap: 1.5rem;
  font-size: 12px;
}
</style>
