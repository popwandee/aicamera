<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <span class="brand-hex">⬡</span>
      <div>
        <div class="brand-name font-display">AICAM</div>
        <div class="brand-sub">Control Center</div>
      </div>
    </div>

    <div class="conn-status">
      <StatusDot :status="connected ? 'online' : 'offline'" />
      <span class="conn-label">{{ connected ? 'Live' : 'Reconnecting…' }}</span>
    </div>

    <nav class="sidebar-nav">
      <div class="nav-section-label">Monitor</div>
      <router-link to="/"           class="nav-item" exact-active-class="nav-active">
        <span class="nav-icon">◉</span> Dashboard
      </router-link>
      <router-link to="/cameras"    class="nav-item" active-class="nav-active">
        <span class="nav-icon">◈</span> Cameras
      </router-link>
      <router-link to="/detections" class="nav-item" active-class="nav-active">
        <span class="nav-icon">◎</span> Detections
      </router-link>

      <div class="nav-section-label">Analyse</div>
      <router-link to="/analytics"  class="nav-item" active-class="nav-active">
        <span class="nav-icon">▦</span> Analytics
      </router-link>
      <router-link to="/routes"     class="nav-item" active-class="nav-active">
        <span class="nav-icon">⟶</span> Routes
      </router-link>
      <router-link to="/convoy"     class="nav-item" active-class="nav-active">
        <span class="nav-icon">⫸</span> Convoy
      </router-link>

      <div class="nav-section-label">System</div>
      <router-link to="/edge_control" class="nav-item" active-class="nav-active">
        <span class="nav-icon">◧</span> Edge Control
      </router-link>
      <router-link to="/system"     class="nav-item" active-class="nav-active">
        <span class="nav-icon">⊟</span> System Events
      </router-link>
      <router-link to="/settings"   class="nav-item" active-class="nav-active">
        <span class="nav-icon">⚙</span> Settings
      </router-link>
    </nav>

    <div class="sidebar-footer">
      <span class="footer-text">PWD Vision Works</span>
    </div>
  </aside>
</template>

<script>
import StatusDot from '@/components/shared/StatusDot.vue';
import { useSocket } from '@/composables/useSocket.js';

export default {
  name: 'AppSidebar',
  components: { StatusDot },
  setup() {
    const { connected } = useSocket();
    return { connected };
  },
};
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  min-height: 100vh;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-dim);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}

/* Brand */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 1.2rem 1rem 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.brand-hex {
  font-size: 1.8rem;
  color: var(--cyan);
  filter: drop-shadow(var(--cyan-glow));
  line-height: 1;
}
.brand-name {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
}
.brand-sub {
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

/* Connection status */
.conn-status {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0.55rem 1rem;
  border-bottom: 1px solid var(--border-dim);
}
.conn-label { font-size: 11px; color: var(--text-secondary); font-family: var(--font-data); }

/* Navigation */
.sidebar-nav { flex: 1; padding: 0.5rem 0; }

.nav-section-label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--text-muted);
  padding: 0.9rem 1rem 0.3rem;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0.55rem 1rem;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  transition: background var(--transition), color var(--transition);
  border-left: 2px solid transparent;
}
.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.nav-active {
  color: var(--cyan) !important;
  background: rgba(0,200,255,0.07);
  border-left-color: var(--cyan);
}
.nav-icon {
  font-size: 12px;
  width: 16px;
  text-align: center;
  opacity: 0.8;
}

/* Footer */
.sidebar-footer {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-dim);
}
.footer-text { font-size: 10px; color: var(--text-muted); letter-spacing: 0.08em; }
</style>
