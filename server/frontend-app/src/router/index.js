import { createRouter, createWebHistory } from 'vue-router';

import MainDashboard      from '@/views/MainDashboard.vue';
import CameraList         from '@/views/CameraList.vue';
import CameraDetail       from '@/views/CameraDetail.vue';
import DetectionList      from '@/views/DetectionList.vue';
import DetectionDetail    from '@/views/DetectionDetail.vue';
import AnalyticsDashboard from '@/views/AnalyticsDashboard.vue';
import RouteAnalysis      from '@/views/RouteAnalysis.vue';
import RouteDetail        from '@/views/RouteDetail.vue';
import ConvoyDetection    from '@/views/ConvoyDetection.vue';
import EdgeControl        from '@/views/EdgeControl.vue';
import EdgeControlCamera  from '@/views/EdgeControlCamera.vue';
import SystemEvents       from '@/views/SystemEvents.vue';
import Settings           from '@/views/Settings.vue';

const base = (typeof window !== 'undefined' && window.location.pathname.startsWith('/server'))
  ? '/server/'
  : '/';

const routes = [
  { path: '/',                    name: 'Dashboard',      component: MainDashboard,      meta: { title: 'Dashboard' } },
  { path: '/cameras',             name: 'Cameras',        component: CameraList,         meta: { title: 'Cameras' } },
  { path: '/cameras/:id',         name: 'CameraDetail',   component: CameraDetail,       meta: { title: 'Camera Detail' }, props: true },
  { path: '/detections',          name: 'Detections',     component: DetectionList,      meta: { title: 'Detections' } },
  { path: '/detections/:id',      name: 'DetectionDetail',component: DetectionDetail,    meta: { title: 'Detection Detail' }, props: true },
  { path: '/analytics',           name: 'Analytics',      component: AnalyticsDashboard, meta: { title: 'Analytics' } },
  { path: '/routes',              name: 'Routes',         component: RouteAnalysis,      meta: { title: 'Route Analysis' } },
  { path: '/routes/:routeKey',    name: 'RouteDetail',    component: RouteDetail,        meta: { title: 'Route Detail' }, props: true },
  { path: '/convoy',              name: 'Convoy',         component: ConvoyDetection,    meta: { title: 'Convoy Detection' } },
  { path: '/edge_control',        name: 'EdgeControl',    component: EdgeControl,        meta: { title: 'Edge Control' } },
  { path: '/edge_control/camera/:id', name: 'EdgeControlCamera', component: EdgeControlCamera, meta: { title: 'Camera Detail' }, props: true },
  { path: '/system',              name: 'System',         component: SystemEvents,       meta: { title: 'System Events' } },
  { path: '/settings',            name: 'Settings',       component: Settings,           meta: { title: 'Settings' } },
];

const router = createRouter({
  history: createWebHistory(base),
  routes,
});

router.afterEach((to) => {
  if (to.meta?.title && typeof document !== 'undefined') {
    document.title = to.meta.title + ' — AI Camera';
  }
});

export default router;
