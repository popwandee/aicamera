<template>
  <div class="p-6">
    <header class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-semibold">Dashboard</h1>
      <div class="flex items-center gap-3">
        <span v-if="auth.user">Hello, {{ auth.user.username }} ({{ auth.user.role }})</span>
        <router-link to="/users" class="btn-secondary" v-if="auth.user?.role === 'admin'">User Management</router-link>
        <router-link to="/profile" class="btn-secondary">Profile</router-link>
        <button class="btn" @click="onLogout">Logout</button>
      </div>
    </header>
    <section class="space-y-4">
      <div class="card">Welcome to the AI Camera dashboard.</div>
      
      <div class="dashboard-grid">
        <div class="dashboard-card" @click="navigateTo('/cameras')">
          <h3>📹 Cameras</h3>
          <p>Manage camera devices and configurations</p>
        </div>
        
        <div class="dashboard-card" @click="navigateTo('/map')">
          <h3>🗺️ Map View</h3>
          <p>Interactive map with camera locations and detections</p>
        </div>
        
        <div class="dashboard-card" @click="navigateTo('/detections')">
          <h3>🚗 Detections</h3>
          <p>View license plate detection results</p>
        </div>
        
        <div class="dashboard-card" @click="navigateTo('/users')" v-if="auth.user?.role === 'admin'">
          <h3>👥 User Management</h3>
          <p>Manage users, roles, and permissions</p>
        </div>
        
        <div class="dashboard-card" @click="navigateTo('/analytics')">
          <h3>📊 Analytics</h3>
          <p>View system analytics and reports</p>
        </div>
        
        <div class="dashboard-card" @click="navigateTo('/visualizations')">
          <h3>📈 Visualizations</h3>
          <p>Create and manage data visualizations</p>
        </div>
      </div>
      
      <ServiceStatus />
    </section>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';
import ServiceStatus from '../components/ServiceStatus.vue';

const auth = useAuthStore();
const router = useRouter();

async function onLogout() {
  await auth.logout();
  window.location.href = '/login';
}

function navigateTo(path: string) {
  router.push(path);
}
</script>

<style scoped>
.card { 
  border: 1px solid #ccc; 
  border-radius: 0.5rem; 
  padding: 1rem; 
}
.btn { 
  background-color: #374151; 
  color: white; 
  border-radius: 0.5rem; 
  padding: 0.5rem 0.75rem; 
  border: none;
  cursor: pointer;
}

.btn-secondary {
  background-color: #6b7280;
  color: white;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: none;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
  font-size: 0.875rem;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}

.dashboard-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.dashboard-card:hover {
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.dashboard-card h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.25rem;
  color: #374151;
}

.dashboard-card p {
  margin: 0;
  color: #6b7280;
  font-size: 0.875rem;
}
</style>
