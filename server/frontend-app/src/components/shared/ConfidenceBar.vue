<template>
  <div class="conf-wrap">
    <div class="conf-track">
      <div class="conf-fill" :class="colorClass" :style="{ width: pct + '%' }" />
    </div>
    <span v-if="showLabel" class="conf-label font-data" :class="colorClass">
      {{ pct }}%
    </span>
  </div>
</template>

<script>
export default {
  name: 'ConfidenceBar',
  props: {
    value:     { type: [Number, String], default: 0 },
    showLabel: { type: Boolean,          default: true },
  },
  computed: {
    pct() {
      const v = parseFloat(this.value);
      return isNaN(v) ? 0 : Math.round(v * 100);
    },
    colorClass() {
      if (this.pct >= 90) return 'c-green';
      if (this.pct >= 70) return 'c-amber';
      return 'c-red';
    },
  },
};
</script>

<style scoped>
.conf-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 80px;
}
.conf-track {
  flex: 1;
  height: 4px;
  background: rgba(120,160,200,0.12);
  border-radius: 2px;
  overflow: hidden;
}
.conf-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}
.conf-label { font-size: 11px; width: 34px; text-align: right; flex-shrink: 0; }

.c-green .conf-fill, .c-green { color: var(--green);  }
.c-amber .conf-fill, .c-amber { color: var(--amber);  }
.c-red   .conf-fill, .c-red   { color: var(--red);    }

.conf-fill.c-green { background: var(--green); }
.conf-fill.c-amber { background: var(--amber); }
.conf-fill.c-red   { background: var(--red);   }
</style>
