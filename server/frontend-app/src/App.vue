<template>
  <div class="app-shell">
    <Sidebar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script>
import Sidebar from '@/components/layout/Sidebar.vue';
export default {
  name: 'App',
  components: { Sidebar },
};
</script>

<style>
@import '@/assets/design-tokens.css';

.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg-void);
}
.main-content {
  flex: 1;
  overflow-y: auto;
  min-height: 100vh;
  padding: 1.5rem 1.75rem;
}
</style>
