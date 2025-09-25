import { defineStore } from 'pinia'
import { ref, computed, onMounted } from 'vue'
import { apiService } from '@/services/api'
import { useWebSocketStore } from './websocket'
import type { IDetection, DetectionType } from '@/types'

export interface DetectionStats {
  totalDetections: number
  detectionsToday: number
  detectionsThisWeek: number
  detectionsThisMonth: number
  detectionsByType: Record<DetectionType, number>
  detectionsByDevice: Record<string, number>
  averageConfidence: number
}

export const useDetectionStore = defineStore('detection', () => {
  // State
  const detections = ref<IDetection[]>([])
  const recentDetections = ref<IDetection[]>([])
  const stats = ref<DetectionStats>({
    totalDetections: 0,
    detectionsToday: 0,
    detectionsThisWeek: 0,
    detectionsThisMonth: 0,
    detectionsByType: {} as Record<DetectionType, number>,
    detectionsByDevice: {},
    averageConfidence: 0,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  // WebSocket store for real-time updates
  const websocketStore = useWebSocketStore()

  // Getters
  const detectionsList = computed(() => detections.value)
  const recentDetectionsList = computed(() => recentDetections.value)
  const chartData = computed(() => {
    // Transform detection data for charts
    const last7Days = Array.from({ length: 7 }, (_, i) => {
      const date = new Date()
      date.setDate(date.getDate() - i)
      return date.toISOString().split('T')[0]
    }).reverse()

    const detectionsByDate = last7Days.map(date => {
      const count = recentDetections.value.filter(detection => 
        detection.createdAt.startsWith(date)
      ).length
      return {
        date,
        count,
      }
    })

    return {
      labels: last7Days.map(date => new Date(date).toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
      })),
      datasets: [{
        label: 'Detections',
        data: detectionsByDate.map(item => item.count),
        borderColor: 'rgb(99, 102, 241)',
        backgroundColor: 'rgba(99, 102, 241, 0.1)',
        tension: 0.4,
      }]
    }
  })

  // Actions
  async function fetchDetections(filters: any = {}) {
    try {
      loading.value = true
      error.value = null
      
      const params = new URLSearchParams(filters).toString()
      const response = await apiService.get(`/detections?${params}`)
      
      if (response.data.success) {
        detections.value = response.data.data
      } else {
        throw new Error(response.data.message || 'Failed to fetch detections')
      }
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch detections'
      console.error('Failed to fetch detections:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchRecentDetections(limit = 10) {
    try {
      const response = await apiService.get(`/detections/recent?limit=${limit}`)
      
      if (response.data.success) {
        recentDetections.value = response.data.data
      }
    } catch (err: any) {
      console.error('Failed to fetch recent detections:', err)
    }
  }

  async function fetchStats(deviceId?: string, startDate?: string, endDate?: string) {
    try {
      const params = new URLSearchParams()
      if (deviceId) params.append('deviceId', deviceId)
      if (startDate) params.append('startDate', startDate)
      if (endDate) params.append('endDate', endDate)
      
      const response = await apiService.get(`/detections/stats?${params.toString()}`)
      
      if (response.data.success) {
        stats.value = response.data.data
      }
    } catch (err: any) {
      console.error('Failed to fetch detection stats:', err)
    }
  }

  async function getDetection(id: string): Promise<IDetection | null> {
    try {
      const response = await apiService.get(`/detections/${id}`)
      
      if (response.data.success) {
        return response.data.data
      }
      
      return null
    } catch (err: any) {
      console.error(`Failed to fetch detection ${id}:`, err)
      return null
    }
  }

  async function createManualDetection(detectionData: any) {
    try {
      const response = await apiService.post('/detections/manual', detectionData)
      
      if (response.data.success) {
        // Add to recent detections
        recentDetections.value.unshift(response.data.data)
        // Keep only the last 20 recent detections
        if (recentDetections.value.length > 20) {
          recentDetections.value = recentDetections.value.slice(0, 20)
        }
        return response.data.data
      } else {
        throw new Error(response.data.message || 'Failed to create detection')
      }
    } catch (err: any) {
      console.error('Failed to create manual detection:', err)
      throw err
    }
  }

  function addDetection(newDetection: IDetection) {
    // Add to recent detections at the beginning
    recentDetections.value.unshift(newDetection)
    
    // Keep only the last 20 recent detections
    if (recentDetections.value.length > 20) {
      recentDetections.value = recentDetections.value.slice(0, 20)
    }

    // Update stats
    stats.value.totalDetections += 1
    
    // Check if it's today's detection
    const today = new Date().toISOString().split('T')[0]
    if (newDetection.createdAt.startsWith(today)) {
      stats.value.detectionsToday += 1
    }

    // Update detection by type
    if (!stats.value.detectionsByType[newDetection.type]) {
      stats.value.detectionsByType[newDetection.type] = 0
    }
    stats.value.detectionsByType[newDetection.type] += 1

    // Update detection by device
    const deviceId = newDetection.device?.deviceId || newDetection.deviceId
    if (deviceId) {
      if (!stats.value.detectionsByDevice[deviceId]) {
        stats.value.detectionsByDevice[deviceId] = 0
      }
      stats.value.detectionsByDevice[deviceId] += 1
    }
  }

  // Setup WebSocket listeners for real-time updates
  function setupWebSocketListeners() {
    websocketStore.onDetectionUpdate((data: any) => {
      if (data.detection) {
        addDetection(data.detection)
      }
      
      if (data.detections && Array.isArray(data.detections)) {
        // Handle bulk detections
        data.detections.forEach((detection: IDetection) => {
          addDetection(detection)
        })
      }
    })
  }

  // Utility functions
  function getDetectionsByType(type: DetectionType) {
    return recentDetections.value.filter(detection => detection.type === type)
  }

  function getDetectionsByDevice(deviceId: string) {
    return recentDetections.value.filter(detection => 
      detection.device?.deviceId === deviceId || detection.deviceId === deviceId
    )
  }

  function getDetectionsByDateRange(startDate: Date, endDate: Date) {
    return recentDetections.value.filter(detection => {
      const detectionDate = new Date(detection.createdAt)
      return detectionDate >= startDate && detectionDate <= endDate
    })
  }

  // Initialize
  onMounted(() => {
    setupWebSocketListeners()
  })

  return {
    // State
    detections,
    recentDetections,
    stats,
    loading,
    error,
    
    // Getters
    detectionsList,
    recentDetectionsList,
    chartData,
    
    // Actions
    fetchDetections,
    fetchRecentDetections,
    fetchStats,
    getDetection,
    createManualDetection,
    addDetection,
    getDetectionsByType,
    getDetectionsByDevice,
    getDetectionsByDateRange,
  }
})