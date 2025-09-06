import axios from 'axios'

// API configuration
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api'

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for authentication
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('authToken')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Camera Status API
export const cameraStatusAPI = {
  // Get camera status summary
  getSummary: () => api.get('/camera-status/summary'),
  
  // Get all cameras with status
  getCameras: (params = {}) => api.get('/camera-status/cameras', { params }),
  
  // Get specific camera details
  getCamera: (cameraId) => api.get(`/camera-status/cameras/${cameraId}`),
  
  // Get camera status history
  getStatusHistory: (params = {}) => api.get('/camera-status/history', { params }),
  
  // Update camera settings
  updateCamera: (cameraId, data) => api.put(`/camera-status/cameras/${cameraId}`, data),
  
  // Restart camera
  restartCamera: (cameraId) => api.post(`/camera-status/cameras/${cameraId}/restart`),
}

// Network Analysis API
export const networkAnalysisAPI = {
  // Get network summary
  getSummary: () => api.get('/network-analysis/summary'),
  
  // Get all network nodes
  getNodes: (params = {}) => api.get('/network-analysis/nodes', { params }),
  
  // Get specific node details
  getNode: (nodeId) => api.get(`/network-analysis/nodes/${nodeId}`),
  
  // Get network traffic data
  getTrafficData: (params = {}) => api.get('/network-analysis/traffic', { params }),
  
  // Get protocol distribution
  getProtocolDistribution: () => api.get('/network-analysis/protocols'),
  
  // Get network topology
  getTopology: () => api.get('/network-analysis/topology'),
  
  // Update node configuration
  updateNode: (nodeId, data) => api.put(`/network-analysis/nodes/${nodeId}`, data),
}

// Detection Analysis API
export const detectionAnalysisAPI = {
  // Get detection summary
  getSummary: () => api.get('/detection-analysis/summary'),
  
  // Get location-based detections
  getLocationBased: (params = {}) => api.get('/detection-analysis/location', { params }),
  
  // Get time-based detections
  getTimeBased: (params = {}) => api.get('/detection-analysis/time', { params }),
  
  // Get license plate data
  getLicensePlateData: (params = {}) => api.get('/detection-analysis/license-plates', { params }),
  
  // Get detection types distribution
  getDetectionTypes: () => api.get('/detection-analysis/types'),
  
  // Get specific detection details
  getDetection: (detectionId) => api.get(`/detection-analysis/detections/${detectionId}`),
  
  // Search detections
  searchDetections: (params = {}) => api.get('/detection-analysis/search', { params }),
  
  // Export detection data
  exportDetections: (params = {}) => api.get('/detection-analysis/export', { 
    params,
    responseType: 'blob'
  }),
}

// Dashboard API
export const dashboardAPI = {
  // Get dashboard summary
  getSummary: () => api.get('/dashboard/summary'),
  
  // Get real-time metrics
  getMetrics: () => api.get('/dashboard/metrics'),
  
  // Get alerts
  getAlerts: (params = {}) => api.get('/dashboard/alerts', { params }),
  
  // Get system health
  getSystemHealth: () => api.get('/dashboard/health'),
}

// Utility functions
export const apiUtils = {
  // Handle API errors
  handleError: (error) => {
    if (error.response) {
      // Server responded with error status
      return {
        message: error.response.data?.message || 'An error occurred',
        status: error.response.status,
        data: error.response.data
      }
    } else if (error.request) {
      // Request was made but no response received
      return {
        message: 'Network error - please check your connection',
        status: 0
      }
    } else {
      // Something else happened
      return {
        message: error.message || 'An unexpected error occurred',
        status: -1
      }
    }
  },
  
  // Format date for API requests
  formatDate: (date) => {
    return new Date(date).toISOString()
  },
  
  // Build query parameters
  buildQueryParams: (params) => {
    const queryParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        queryParams.append(key, value)
      }
    })
    return queryParams.toString()
  }
}

export default api