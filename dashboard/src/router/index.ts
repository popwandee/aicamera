import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: 'Dashboard' }
  },
  {
    path: '/devices',
    name: 'Devices',
    component: () => import('@/views/Devices.vue'),
    meta: { title: 'Devices' }
  },
  {
    path: '/devices/:deviceId',
    name: 'DeviceDetail',
    component: () => import('@/views/DeviceDetail.vue'),
    meta: { title: 'Device Details' }
  },
  {
    path: '/detections',
    name: 'Detections',
    component: () => import('@/views/Detections.vue'),
    meta: { title: 'Detections' }
  },
  {
    path: '/detections/:id',
    name: 'DetectionDetail',
    component: () => import('@/views/DetectionDetail.vue'),
    meta: { title: 'Detection Details' }
  },
  {
    path: '/files',
    name: 'Files',
    component: () => import('@/views/Files.vue'),
    meta: { title: 'File Management' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: 'Settings' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: 'Login', requiresAuth: false }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: 'Page Not Found' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard for authentication
router.beforeEach((to, from, next) => {
  const title = to.meta.title as string
  document.title = title ? `${title} - AI Camera` : 'AI Camera'
  
  // Add authentication logic here when implemented
  // For now, allow all routes except login
  if (to.name === 'Login') {
    next()
  } else {
    next()
  }
})

export default router