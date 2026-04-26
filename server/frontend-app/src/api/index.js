const BASE = window.location.origin + '/server/api';

async function req(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(BASE + path, opts);
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}`);
  return res.json();
}

export const api = {
  // Cameras
  getCameras:           () => req('GET', '/cameras'),
  getCamerasEdgeStatus: () => req('GET', '/cameras/edge-status'),
  getCamerasSummary:    () => req('GET', '/cameras/summary'),
  getCamera:       (id) => req('GET', `/cameras/${id}`),
  createCamera:  (data) => req('POST', '/cameras', data),
  updateCamera: (id, d) => req('PUT',  `/cameras/${id}`, d),
  deleteCamera:    (id) => req('DELETE', `/cameras/${id}`),
  registerCamera: (data) => req('POST', '/cameras/register', data),
  getCameraDetections: (id, limit=100) => req('GET', `/cameras/${id}/detections?limit=${limit}`),
  runAnalytics:   () => req('GET', '/cameras/analytics/run'),

  // Detections
  getDetections: (params = {}) => {
    const q = new URLSearchParams();
    if (params.cameraId)   q.set('cameraId',  params.cameraId);
    if (params.search)     q.set('search',    params.search);
    if (params.limit)      q.set('limit',     params.limit);
    if (params.offset)     q.set('offset',    params.offset);
    if (params.sortBy)     q.set('sortBy',    params.sortBy);
    if (params.sortOrder)  q.set('sortOrder', params.sortOrder);
    if (params.archived != null) q.set('archived', params.archived);
    return req('GET', `/detections?${q}`);
  },
  getDetection:     (id) => req('GET', `/detections/${id}`),
  archiveDetection: (id) => req('PATCH', `/detections/${id}`, { archived: true }),
  unarchiveDetection:(id)=> req('PATCH', `/detections/${id}`, { archived: false }),
  getDetectionImageUrl: (id) => `${BASE}/detections/${id}/image`,

  // Camera Health
  getCameraHealth: (params = {}) => {
    const q = new URLSearchParams();
    if (params.cameraId) q.set('cameraId', params.cameraId);
    if (params.limit)    q.set('limit',    params.limit);
    if (params.from)     q.set('from',     params.from);
    if (params.to)       q.set('to',       params.to);
    return req('GET', `/camera-health?${q}`);
  },

  // Analytics & Events
  getAnalytics:     () => req('GET', '/analytics'),
  getSystemEvents:  (limit=200) => req('GET', `/system-events?limit=${limit}`),
  getVisualizations:() => req('GET', '/visualizations'),
  getAnalyticsEvents:(limit=200)=> req('GET', `/analytics-events?limit=${limit}`),
};

export default api;
