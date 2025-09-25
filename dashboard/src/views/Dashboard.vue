<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow-sm border-b">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center py-6">
          <div class="flex items-center">
            <h1 class="text-2xl font-bold text-gray-900">AI Camera Dashboard</h1>
          </div>
          <div class="flex items-center space-x-4">
            <div class="flex items-center text-sm text-gray-500">
              <div 
                class="w-3 h-3 rounded-full mr-2"
                :class="websocketConnected ? 'bg-green-500' : 'bg-red-500'"
              ></div>
              {{ websocketConnected ? 'Connected' : 'Disconnected' }}
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
      <!-- Stats Cards -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Total Devices"
          :value="deviceStats.totalDevices"
          :loading="loadingStats"
          icon="DevicePhoneMobileIcon"
          color="blue"
        />
        <StatCard
          title="Online Devices"
          :value="deviceStats.onlineDevices"
          :loading="loadingStats"
          icon="SignalIcon"
          color="green"
        />
        <StatCard
          title="Total Detections"
          :value="detectionStats.totalDetections"
          :loading="loadingStats"
          icon="EyeIcon"
          color="purple"
        />
        <StatCard
          title="Today's Detections"
          :value="detectionStats.detectionsToday"
          :loading="loadingStats"
          icon="CalendarDaysIcon"
          color="orange"
        />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Recent Detections -->
        <div class="bg-white rounded-lg shadow-sm border">
          <div class="p-6 border-b">
            <h2 class="text-lg font-semibold text-gray-900">Recent Detections</h2>
          </div>
          <div class="p-6">
            <DetectionList :detections="recentDetections" :loading="loadingDetections" />
          </div>
        </div>

        <!-- Device Status -->
        <div class="bg-white rounded-lg shadow-sm border">
          <div class="p-6 border-b">
            <h2 class="text-lg font-semibold text-gray-900">Device Status</h2>
          </div>
          <div class="p-6">
            <DeviceList :devices="devices" :loading="loadingDevices" />
          </div>
        </div>
      </div>

      <!-- Charts -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
        <!-- Detection Trends -->
        <div class="bg-white rounded-lg shadow-sm border">
          <div class="p-6 border-b">
            <h2 class="text-lg font-semibold text-gray-900">Detection Trends</h2>
          </div>
          <div class="p-6">
            <DetectionChart :data="detectionChartData" />
          </div>
        </div>

        <!-- Device Types -->
        <div class="bg-white rounded-lg shadow-sm border">
          <div class="p-6 border-b">
            <h2 class="text-lg font-semibold text-gray-900">Device Types</h2>
          </div>
          <div class="p-6">
            <DeviceTypeChart :data="deviceTypeData" />
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useDeviceStore } from '@/stores/device'
import { useDetectionStore } from '@/stores/detection'
import { useWebSocketStore } from '@/stores/websocket'
import StatCard from '@/components/StatCard.vue'
import DetectionList from '@/components/DetectionList.vue'
import DeviceList from '@/components/DeviceList.vue'
import DetectionChart from '@/components/charts/DetectionChart.vue'
import DeviceTypeChart from '@/components/charts/DeviceTypeChart.vue'

// Stores
const deviceStore = useDeviceStore()
const detectionStore = useDetectionStore()
const websocketStore = useWebSocketStore()

// Reactive state
const loadingStats = ref(true)
const loadingDevices = ref(true)
const loadingDetections = ref(true)

// Computed properties
const websocketConnected = computed(() => websocketStore.connected)
const devices = computed(() => deviceStore.devices)
const deviceStats = computed(() => deviceStore.stats)
const recentDetections = computed(() => detectionStore.recentDetections)
const detectionStats = computed(() => detectionStore.stats)
const detectionChartData = computed(() => detectionStore.chartData)
const deviceTypeData = computed(() => deviceStore.deviceTypeData)

onMounted(async () => {
  try {
    // Load all data
    await Promise.all([
      loadDeviceData(),
      loadDetectionData(),
      loadStats()
    ])
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  }
})

async function loadDeviceData() {
  try {
    loadingDevices.value = true
    await deviceStore.fetchDevices()
  } finally {
    loadingDevices.value = false
  }
}

async function loadDetectionData() {
  try {
    loadingDetections.value = true
    await detectionStore.fetchRecentDetections()
  } finally {
    loadingDetections.value = false
  }
}

async function loadStats() {
  try {
    loadingStats.value = true
    await Promise.all([
      deviceStore.fetchStats(),
      detectionStore.fetchStats()
    ])
  } finally {
    loadingStats.value = false
  }
}
</script>