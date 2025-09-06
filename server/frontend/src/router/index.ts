import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';
import LoginView from '../views/LoginView.vue';
import DashboardView from '../views/DashboardView.vue';
import CamerasView from '../views/CamerasView.vue';
import UserManagementView from '../views/UserManagementView.vue';
import UserProfileView from '../views/UserProfileView.vue';
import MapView from '../components/MapView.vue';

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/dashboard', name: 'dashboard', component: DashboardView },
  { path: '/cameras', name: 'cameras', component: CamerasView },
  { path: '/map', name: 'map', component: MapView },
  { path: '/users', name: 'users', component: UserManagementView, meta: { requiresAdmin: true } },
  { path: '/profile', name: 'profile', component: UserProfileView },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach((to, _from, next) => {
  const isPublic = to.matched.some(r => r.meta.public);
  const requiresAdmin = to.matched.some(r => r.meta.requiresAdmin);
  const token = localStorage.getItem('accessToken');
  
  if (!isPublic && !token) {
    return next({ name: 'login', query: { redirect: to.fullPath } });
  }
  
  if (isPublic && token && to.name === 'login') {
    return next({ name: 'dashboard' });
  }
  
  // Check admin access
  if (requiresAdmin && token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      if (payload.role !== 'admin') {
        alert('Access denied. Admin privileges required.');
        return next({ name: 'dashboard' });
      }
    } catch (error) {
      console.error('Invalid token:', error);
      return next({ name: 'login' });
    }
  }
  
  return next();
});

export default router;
