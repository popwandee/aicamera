<template>
  <div class="app-shell" :class="{ 'nav-open': navOpen }">

    <!-- Mobile overlay: click to close sidebar -->
    <div class="nav-overlay" @click="navOpen = false" />

    <Sidebar @close="navOpen = false" />

    <main class="main-content">
      <!-- Mobile top bar (hidden on desktop) -->
      <div class="mobile-topbar">
        <button class="hamburger" @click="navOpen = !navOpen" aria-label="Toggle navigation">
          <span /><span /><span />
        </button>
        <span class="mobile-brand font-display">AICAM</span>
      </div>

      <router-view />
    </main>
  </div>
</template>

<script>
import Sidebar from '@/components/layout/Sidebar.vue';
export default {
  name: 'App',
  components: { Sidebar },
  data() {
    return { navOpen: false };
  },
  watch: {
    $route() { this.navOpen = false; },
  },
};
</script>

<style>
@import '@/assets/design-tokens.css';

/* ── App shell ────────────────────────────────────────────── */
.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg-void);
}

.main-content {
  flex: 1;
  min-width: 0;          /* prevent flex child from overflowing */
  overflow-y: auto;
  min-height: 100vh;
  padding: 1.5rem 1.75rem;
}

/* ── Mobile nav overlay ────────────────────────────────────── */
.nav-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 199;
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
}
.nav-open .nav-overlay { display: block; }

/* ── Mobile sidebar behaviour ──────────────────────────────── */
@media (max-width: 767px) {
  /* Sidebar slides off-screen by default; slides in when nav-open */
  .app-shell .sidebar {
    position: fixed !important;
    top: 0;
    left: 0;
    height: 100vh;
    z-index: 200;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.6);
  }
  .app-shell.nav-open .sidebar {
    transform: translateX(0);
  }
  /* Main takes full width */
  .main-content {
    padding: 0.75rem 1rem 1rem;
  }
}

/* ── Mobile top bar ────────────────────────────────────────── */
.mobile-topbar {
  display: none;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.1rem;
}
.hamburger {
  background: none;
  border: 1px solid var(--border-card);
  border-radius: var(--radius-sm);
  padding: 6px 9px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: border-color var(--transition);
}
.hamburger:hover { border-color: var(--cyan-dim); }
.hamburger span {
  display: block;
  width: 18px;
  height: 2px;
  background: var(--cyan-dim);
  border-radius: 1px;
  transition: background var(--transition);
}
.hamburger:hover span { background: var(--cyan); }
.mobile-brand {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--cyan);
  text-shadow: var(--cyan-glow);
}

@media (max-width: 767px) {
  .mobile-topbar { display: flex; }
}
</style>
