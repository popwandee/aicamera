<template>
  <div class="view-container">
    <div class="page-header">
      <div class="page-title font-display">
        <span class="page-icon">⫸</span> Convoy Detection
      </div>
      <div class="page-desc">Groups of vehicles travelling together</div>
    </div>
    <div class="phase-badge">Phase G — Coming Soon</div>
  </div>
</template>

<script>
export default { name: 'ConvoyDetection' };
</script>

<style scoped>
.view-container { padding: 0; }
.page-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.page-title {
  font-size: 1.6rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.page-icon { opacity: 0.8; }
.page-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.phase-badge {
  display: inline-block;
  padding: 8px 18px;
  background: rgba(0,200,255,0.06);
  border: 1px dashed rgba(0,200,255,0.25);
  border-radius: var(--radius-md);
  color: var(--text-muted);
  font-size: 12px;
  letter-spacing: 0.06em;
}
</style>
