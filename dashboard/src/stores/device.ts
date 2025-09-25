import { defineStore } from 'pinia'
import { ref, computed, onMounted } from 'vue'
import { apiService } from '@/services/api'
import { useWebSocketStore } from './websocket'
import type { IEdgeDevice, DeviceStatus } from '@/types'

export interface DeviceStats {
  totalDevices: number
  onlineDevices: number
  offlineDevices: number
  connectingDevices: number
  devicesByType: Record<string, number>
}

export const useDeviceStore = defineStore('device', () => {
  // State
  const devices = ref<IEdgeDevice[]>([])
  const stats = ref<DeviceStats>({
    totalDevices: 0,
    onlineDevices: 0,
    offlineDevices: 0,
    connectingDevices: 0,
    devicesByType: {},
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  // WebSocket store for real-time updates
  const websocketStore = useWebSocketStore()

  // Getters
  const devicesList = computed(() => devices.value)
  const onlineDevices = computed(() => 
    devices.value.filter(device => device.status === 'ONLINE')
  )
  const offlineDevices = computed(() => 
    devices.value.filter(device => device.status === 'OFFLINE')
  )
  const deviceTypeData = computed(() => {
    const typeData = devices.value.reduce((acc, device) => {
      acc[device.type] = (acc[device.type] || 0) + 1
      return acc
    }, {} as Record<string, number>)
    
    return Object.entries(typeData).map(([name, value]) => ({
      name,
      value,
    }))
  })

  // Actions
  async function fetchDevices() {
    try {
      loading.value = true
      error.value = null
      
      const response = await apiService.get('/devices')
      
      if (response.data.success) {
        devices.value = response.data.data
        updateStats()
      } else {
        throw new Error(response.data.message || 'Failed to fetch devices')
      }
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch devices'
      console.error('Failed to fetch devices:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await apiService.get('/devices/stats')
      
      if (response.data.success) {
        stats.value = response.data.data
      }
    } catch (err: any) {
      console.error('Failed to fetch device stats:', err)
    }
  }

  async function getDevice(deviceId: string): Promise<IEdgeDevice | null> {
    try {
      const response = await apiService.get(`/devices/${deviceId}`)
      
      if (response.data.success) {
        return response.data.data
      }
      
      return null
    } catch (err: any) {
      console.error(`Failed to fetch device ${deviceId}:`, err)
      return null
    }
  }

  async function updateDeviceStatus(deviceId: string, status: DeviceStatus) {
    try {
      const response = await apiService.put(`/devices/${deviceId}`, { status })
      
      if (response.data.success) {
        // Update local state
        const deviceIndex = devices.value.findIndex(d => d.deviceId === deviceId)
        if (deviceIndex !== -1) {
          devices.value[deviceIndex] = response.data.data
        }
        updateStats()
      }
    } catch (err: any) {
      console.error(`Failed to update device ${deviceId} status:`, err)
      throw err
    }
  }

  async function registerDevice(deviceData: any) {
    try {
      const response = await apiService.post('/devices/register', deviceData)
      
      if (response.data.success) {
        devices.value.push(response.data.data)
        updateStats()
        return response.data.data
      } else {
        throw new Error(response.data.message || 'Failed to register device')
      }
    } catch (err: any) {
      console.error('Failed to register device:', err)
      throw err
    }
  }

  async function sendConfigToDevice(deviceId: string) {
    try {
      const response = await apiService.post(`/devices/${deviceId}/config/send`)
      
      if (!response.data.success) {
        throw new Error(response.data.message || 'Failed to send config')
      }
    } catch (err: any) {
      console.error(`Failed to send config to device ${deviceId}:`, err)
      throw err
    }
  }

  function updateStats() {
    const totalDevices = devices.value.length
    const onlineDevices = devices.value.filter(d => d.status === 'ONLINE').length
    const offlineDevices = devices.value.filter(d => d.status === 'OFFLINE').length
    const connectingDevices = devices.value.filter(d => d.status === 'CONNECTING').length
    
    const devicesByType = devices.value.reduce((acc, device) => {
      acc[device.type] = (acc[device.type] || 0) + 1
      return acc
    }, {} as Record<string, number>)

    stats.value = {
      totalDevices,
      onlineDevices,
      offlineDevices,
      connectingDevices,
      devicesByType,
    }
  }

  function updateDevice(updatedDevice: IEdgeDevice) {
    const index = devices.value.findIndex(d => d.id === updatedDevice.id)
    if (index !== -1) {
      devices.value[index] = updatedDevice
      updateStats()
    }
  }

  function addDevice(newDevice: IEdgeDevice) {
    const existingIndex = devices.value.findIndex(d => d.id === newDevice.id)
    if (existingIndex === -1) {
      devices.value.push(newDevice)
      updateStats()
    } else {
      devices.value[existingIndex] = newDevice
      updateStats()
    }
  }

  // Setup WebSocket listeners for real-time updates
  function setupWebSocketListeners() {
    websocketStore.onDeviceUpdate((data: any) => {
      if (data.device) {
        updateDevice(data.device)
      }
      
      if (data.deviceId && data.status) {
        const device = devices.value.find(d => d.deviceId === data.deviceId)
        if (device) {
          device.status = data.status
          device.lastSeen = new Date(data.timestamp)
          updateStats()
        }
      }
    })
  }

  // Initialize
  onMounted(() => {
    setupWebSocketListeners()
  })

  return {
    // State
    devices,
    stats,
    loading,
    error,
    
    // Getters
    devicesList,
    onlineDevices,
    offlineDevices,
    deviceTypeData,
    
    // Actions
    fetchDevices,
    fetchStats,
    getDevice,
    updateDeviceStatus,
    registerDevice,
    sendConfigToDevice,
    updateDevice,
    addDevice,
  }
})