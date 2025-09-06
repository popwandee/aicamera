// Sample data for analytics dashboard

export const cameraStatusData = {
  summary: {
    total: 156,
    online: 142,
    offline: 8,
    warning: 6,
    lastUpdated: new Date().toISOString()
  },
  cameras: [
    {
      id: 'CAM-001',
      name: 'Main Entrance Camera',
      location: 'Building A - Main Entrance',
      status: 'online',
      lastSeen: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
      resolution: '4K',
      fps: 30,
      bandwidth: '15.2 Mbps',
      temperature: 42,
      uptime: '99.8%'
    },
    {
      id: 'CAM-002',
      name: 'Parking Lot Camera',
      location: 'Building A - Parking Lot',
      status: 'online',
      lastSeen: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
      resolution: '1080p',
      fps: 25,
      bandwidth: '8.7 Mbps',
      temperature: 38,
      uptime: '99.5%'
    },
    {
      id: 'CAM-003',
      name: 'Lobby Camera',
      location: 'Building B - Lobby',
      status: 'warning',
      lastSeen: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      resolution: '1080p',
      fps: 15,
      bandwidth: '4.2 Mbps',
      temperature: 55,
      uptime: '95.2%'
    },
    {
      id: 'CAM-004',
      name: 'Emergency Exit Camera',
      location: 'Building C - Emergency Exit',
      status: 'offline',
      lastSeen: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      resolution: '720p',
      fps: 0,
      bandwidth: '0 Mbps',
      temperature: 0,
      uptime: '0%'
    },
    {
      id: 'CAM-005',
      name: 'Rooftop Camera',
      location: 'Building A - Rooftop',
      status: 'online',
      lastSeen: new Date(Date.now() - 30 * 1000).toISOString(),
      resolution: '4K',
      fps: 30,
      bandwidth: '18.5 Mbps',
      temperature: 35,
      uptime: '99.9%'
    }
  ],
  statusHistory: [
    { date: '2024-01-01', online: 150, offline: 4, warning: 2 },
    { date: '2024-01-02', online: 148, offline: 6, warning: 2 },
    { date: '2024-01-03', online: 152, offline: 2, warning: 2 },
    { date: '2024-01-04', online: 145, offline: 8, warning: 3 },
    { date: '2024-01-05', online: 142, offline: 8, warning: 6 }
  ]
}

export const networkAnalysisData = {
  summary: {
    totalNodes: 45,
    activeConnections: 38,
    bandwidthUtilization: 68.5,
    latency: 12.3,
    packetLoss: 0.2
  },
  nodes: [
    {
      id: 'NODE-001',
      name: 'Core Switch 1',
      type: 'switch',
      status: 'online',
      ip: '192.168.1.1',
      connections: 12,
      bandwidth: '1 Gbps',
      utilization: 45.2,
      lastSeen: new Date(Date.now() - 1 * 60 * 1000).toISOString()
    },
    {
      id: 'NODE-002',
      name: 'Edge Router 1',
      type: 'router',
      status: 'online',
      ip: '192.168.1.2',
      connections: 8,
      bandwidth: '100 Mbps',
      utilization: 78.5,
      lastSeen: new Date(Date.now() - 2 * 60 * 1000).toISOString()
    },
    {
      id: 'NODE-003',
      name: 'Camera Hub 1',
      type: 'hub',
      status: 'warning',
      ip: '192.168.1.10',
      connections: 15,
      bandwidth: '500 Mbps',
      utilization: 92.1,
      lastSeen: new Date(Date.now() - 5 * 60 * 1000).toISOString()
    },
    {
      id: 'NODE-004',
      name: 'Backup Server',
      type: 'server',
      status: 'offline',
      ip: '192.168.1.20',
      connections: 0,
      bandwidth: '0 Mbps',
      utilization: 0,
      lastSeen: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString()
    }
  ],
  trafficData: [
    { time: '00:00', inbound: 120, outbound: 95 },
    { time: '04:00', inbound: 85, outbound: 70 },
    { time: '08:00', inbound: 250, outbound: 180 },
    { time: '12:00', inbound: 320, outbound: 240 },
    { time: '16:00', inbound: 280, outbound: 200 },
    { time: '20:00', inbound: 150, outbound: 120 }
  ],
  protocolDistribution: [
    { protocol: 'HTTP/HTTPS', percentage: 45.2, color: '#3b82f6' },
    { protocol: 'RTSP', percentage: 28.7, color: '#10b981' },
    { protocol: 'TCP', percentage: 15.3, color: '#f59e0b' },
    { protocol: 'UDP', percentage: 8.1, color: '#ef4444' },
    { protocol: 'Other', percentage: 2.7, color: '#6b7280' }
  ]
}

export const detectionAnalysisData = {
  summary: {
    totalDetections: 1247,
    todayDetections: 89,
    activeAlerts: 12,
    accuracy: 94.2
  },
  locationBased: [
    {
      location: 'Main Entrance',
      detections: 234,
      alerts: 3,
      accuracy: 96.1,
      coordinates: { lat: 40.7128, lng: -74.0060 }
    },
    {
      location: 'Parking Lot',
      detections: 189,
      alerts: 5,
      accuracy: 92.8,
      coordinates: { lat: 40.7130, lng: -74.0058 }
    },
    {
      location: 'Lobby',
      detections: 156,
      alerts: 2,
      accuracy: 95.5,
      coordinates: { lat: 40.7126, lng: -74.0062 }
    },
    {
      location: 'Emergency Exit',
      detections: 78,
      alerts: 1,
      accuracy: 98.7,
      coordinates: { lat: 40.7124, lng: -74.0056 }
    },
    {
      location: 'Rooftop',
      detections: 45,
      alerts: 1,
      accuracy: 97.8,
      coordinates: { lat: 40.7132, lng: -74.0064 }
    }
  ],
  timeBased: [
    { hour: '00:00', detections: 12, alerts: 1 },
    { hour: '02:00', detections: 8, alerts: 0 },
    { hour: '04:00', detections: 5, alerts: 0 },
    { hour: '06:00', detections: 15, alerts: 1 },
    { hour: '08:00', detections: 45, alerts: 2 },
    { hour: '10:00', detections: 67, alerts: 3 },
    { hour: '12:00', detections: 89, alerts: 4 },
    { hour: '14:00', detections: 78, alerts: 2 },
    { hour: '16:00', detections: 92, alerts: 3 },
    { hour: '18:00', detections: 56, alerts: 2 },
    { hour: '20:00', detections: 34, alerts: 1 },
    { hour: '22:00', detections: 23, alerts: 1 }
  ],
  licensePlateData: [
    {
      plate: 'ABC-1234',
      detections: 15,
      firstSeen: '2024-01-01T08:30:00Z',
      lastSeen: '2024-01-05T17:45:00Z',
      locations: ['Main Entrance', 'Parking Lot'],
      status: 'authorized'
    },
    {
      plate: 'XYZ-5678',
      detections: 8,
      firstSeen: '2024-01-03T14:20:00Z',
      lastSeen: '2024-01-05T16:30:00Z',
      locations: ['Main Entrance'],
      status: 'unauthorized'
    },
    {
      plate: 'DEF-9012',
      detections: 23,
      firstSeen: '2024-01-01T09:15:00Z',
      lastSeen: '2024-01-05T18:00:00Z',
      locations: ['Main Entrance', 'Parking Lot', 'Lobby'],
      status: 'authorized'
    },
    {
      plate: 'GHI-3456',
      detections: 3,
      firstSeen: '2024-01-04T11:45:00Z',
      lastSeen: '2024-01-04T12:15:00Z',
      locations: ['Emergency Exit'],
      status: 'suspicious'
    }
  ],
  detectionTypes: [
    { type: 'Person', count: 456, percentage: 36.6 },
    { type: 'Vehicle', count: 389, percentage: 31.2 },
    { type: 'License Plate', count: 234, percentage: 18.8 },
    { type: 'Object', count: 123, percentage: 9.9 },
    { type: 'Face', count: 45, percentage: 3.6 }
  ]
}

export const dashboardSummary = {
  totalCameras: cameraStatusData.summary.total,
  onlineCameras: cameraStatusData.summary.online,
  networkNodes: networkAnalysisData.summary.totalNodes,
  totalDetections: detectionAnalysisData.summary.totalDetections,
  systemHealth: 94.2,
  lastUpdate: new Date().toISOString()
}