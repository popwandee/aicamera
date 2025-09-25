import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { io, Socket } from 'socket.io-client'
import { useToast } from 'vue-toastification'

export const useWebSocketStore = defineStore('websocket', () => {
  // State
  const socket = ref<Socket | null>(null)
  const connected = ref(false)
  const reconnecting = ref(false)
  const connectionError = ref<string | null>(null)

  // Toast for notifications
  const toast = useToast()

  // Getters
  const isConnected = computed(() => connected.value)
  const isReconnecting = computed(() => reconnecting.value)

  // Actions
  function connect() {
    if (socket.value?.connected) {
      return
    }

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:3002'
    
    socket.value = io(`${wsUrl}/detection`, {
      autoConnect: true,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
      timeout: 20000,
    })

    setupEventListeners()
  }

  function disconnect() {
    if (socket.value) {
      socket.value.disconnect()
      socket.value = null
    }
    connected.value = false
    reconnecting.value = false
  }

  function setupEventListeners() {
    if (!socket.value) return

    // Connection events
    socket.value.on('connect', () => {
      connected.value = true
      reconnecting.value = false
      connectionError.value = null
      console.log('Connected to WebSocket server')
      
      // Join dashboard room
      socket.value?.emit('join_dashboard', { userType: 'dashboard' })
    })

    socket.value.on('disconnect', (reason) => {
      connected.value = false
      console.log('Disconnected from WebSocket server:', reason)
      
      if (reason === 'io server disconnect') {
        // Server disconnected, need to reconnect manually
        setTimeout(() => socket.value?.connect(), 1000)
      }
    })

    socket.value.on('reconnect', () => {
      reconnecting.value = false
      toast.success('Reconnected to server')
    })

    socket.value.on('reconnect_attempt', () => {
      reconnecting.value = true
    })

    socket.value.on('connect_error', (error) => {
      connectionError.value = error.message
      console.error('WebSocket connection error:', error)
    })

    // Dashboard events
    socket.value.on('dashboard_joined', (data) => {
      console.log('Successfully joined dashboard:', data)
    })

    socket.value.on('recent_detections', (data) => {
      // Handle recent detections data
      console.log('Received recent detections:', data)
    })

    socket.value.on('dashboard_detection_update', (data) => {
      // Handle new detection updates
      console.log('New detection update:', data)
      toast.info(`New detection from ${data.deviceId}`)
      
      // Emit event for other components to listen
      emitDetectionUpdate(data)
    })

    socket.value.on('dashboard_device_update', (data) => {
      // Handle device status updates
      console.log('Device status update:', data)
      
      // Emit event for other components to listen
      emitDeviceUpdate(data)
    })

    socket.value.on('dashboard_stats_update', (data) => {
      // Handle stats updates
      console.log('Stats update:', data)
      
      // Emit event for other components to listen
      emitStatsUpdate(data)
    })

    socket.value.on('error', (error) => {
      console.error('WebSocket error:', error)
      toast.error(`WebSocket error: ${error.message}`)
    })
  }

  // Custom event emitters for communication with other stores
  const detectionUpdateCallbacks = ref<Array<(data: any) => void>>([])
  const deviceUpdateCallbacks = ref<Array<(data: any) => void>>([])
  const statsUpdateCallbacks = ref<Array<(data: any) => void>>([])

  function onDetectionUpdate(callback: (data: any) => void) {
    detectionUpdateCallbacks.value.push(callback)
  }

  function onDeviceUpdate(callback: (data: any) => void) {
    deviceUpdateCallbacks.value.push(callback)
  }

  function onStatsUpdate(callback: (data: any) => void) {
    statsUpdateCallbacks.value.push(callback)
  }

  function emitDetectionUpdate(data: any) {
    detectionUpdateCallbacks.value.forEach(callback => callback(data))
  }

  function emitDeviceUpdate(data: any) {
    deviceUpdateCallbacks.value.forEach(callback => callback(data))
  }

  function emitStatsUpdate(data: any) {
    statsUpdateCallbacks.value.forEach(callback => callback(data))
  }

  // Utility functions
  function emit(event: string, data?: any) {
    if (socket.value?.connected) {
      socket.value.emit(event, data)
    } else {
      console.warn('Cannot emit event: WebSocket not connected')
    }
  }

  function getConnectionInfo() {
    return {
      connected: connected.value,
      reconnecting: reconnecting.value,
      error: connectionError.value,
      socketId: socket.value?.id,
    }
  }

  return {
    // State
    connected,
    reconnecting,
    connectionError,
    
    // Getters
    isConnected,
    isReconnecting,
    
    // Actions
    connect,
    disconnect,
    emit,
    getConnectionInfo,
    
    // Event listeners
    onDetectionUpdate,
    onDeviceUpdate,
    onStatsUpdate,
  }
})