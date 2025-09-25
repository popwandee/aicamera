<template>
  <div id="app" class="min-h-screen bg-gray-100">
    <Suspense>
      <router-view />
    </Suspense>
    
    <!-- Toast notifications will be rendered here -->
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useToast } from 'vue-toastification'
import { useWebSocketStore } from '@/stores/websocket'
import { useDeviceStore } from '@/stores/device'
import { useDetectionStore } from '@/stores/detection'

// Initialize stores
const websocketStore = useWebSocketStore()
const deviceStore = useDeviceStore()
const detectionStore = useDetectionStore()
const toast = useToast()

onMounted(async () => {
  try {
    // Connect to WebSocket
    websocketStore.connect()
    
    // Load initial data
    await Promise.all([
      deviceStore.fetchDevices(),
      detectionStore.fetchRecentDetections(),
    ])
    
    toast.success('Connected to AI Camera System')
  } catch (error) {
    console.error('Failed to initialize application:', error)
    toast.error('Failed to connect to AI Camera System')
  }
})
</script>

<style>
#app {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Custom scrollbar styles */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* Animation classes */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active {
  transition: all 0.3s ease-out;
}

.slide-leave-active {
  transition: all 0.3s cubic-bezier(1, 0.5, 0.8, 1);
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-20px);
  opacity: 0;
}
</style>