<template>
  <div class="device-registration-list">
    <div class="header">
      <h2>Device Registration Management</h2>
      <div class="actions">
        <button @click="refreshDevices" class="btn btn-primary" :disabled="loading">
          <span v-if="loading">Loading...</span>
          <span v-else>Refresh</span>
        </button>
        <button @click="showPreProvisionModal = true" class="btn btn-success">
          Pre-provision Device
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters">
      <div class="filter-group">
        <label>Status:</label>
        <select v-model="filters.status" @change="filterDevices">
          <option value="">All</option>
          <option value="pending_approval">Pending Approval</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="provisioned">Provisioned</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Type:</label>
        <select v-model="filters.type" @change="filterDevices">
          <option value="">All</option>
          <option value="self_registration">Self Registration</option>
          <option value="pre_provision">Pre-provision</option>
          <option value="admin_approval">Admin Approval</option>
        </select>
      </div>
    </div>

    <!-- Pending Approvals Alert -->
    <div v-if="pendingCount > 0" class="alert alert-warning">
      <strong>{{ pendingCount }}</strong> device(s) pending approval
    </div>

    <!-- Device List -->
    <div class="device-table-container">
      <table class="device-table">
        <thead>
          <tr>
            <th>Serial Number</th>
            <th>Device Model</th>
            <th>IP Address</th>
            <th>Location</th>
            <th>Status</th>
            <th>Type</th>
            <th>Registered</th>
            <th>Last Heartbeat</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="device in filteredDevices" :key="device.id" :class="getDeviceRowClass(device)">
            <td>
              <strong>{{ device.serialNumber }}</strong>
              <div v-if="device.camera" class="camera-info">
                Camera: {{ device.camera.name }}
              </div>
            </td>
            <td>{{ device.deviceModel }}</td>
            <td>{{ device.ipAddress || 'N/A' }}</td>
            <td>
              <div v-if="device.locationAddress">{{ device.locationAddress }}</div>
              <div v-else-if="device.locationLat && device.locationLng">
                {{ device.locationLat.toFixed(4) }}, {{ device.locationLng.toFixed(4) }}
              </div>
              <div v-else>N/A</div>
            </td>
            <td>
              <span :class="getStatusClass(device.registrationStatus)">
                {{ formatStatus(device.registrationStatus) }}
              </span>
            </td>
            <td>
              <span class="registration-type">
                {{ formatRegistrationType(device.registrationType) }}
              </span>
            </td>
            <td>{{ formatDate(device.createdAt) }}</td>
            <td>
              <div v-if="device.lastHeartbeat">
                {{ formatDate(device.lastHeartbeat) }}
                <span :class="getHeartbeatStatusClass(device.lastHeartbeat)">
                  ({{ getHeartbeatStatus(device.lastHeartbeat) }})
                </span>
              </div>
              <span v-else class="text-muted">Never</span>
            </td>
            <td>
              <div class="action-buttons">
                <button 
                  v-if="device.registrationStatus === 'pending_approval'"
                  @click="approveDevice(device)"
                  class="btn btn-sm btn-success"
                  :disabled="loading"
                >
                  Approve
                </button>
                <button 
                  v-if="device.registrationStatus === 'pending_approval'"
                  @click="rejectDevice(device)"
                  class="btn btn-sm btn-danger"
                  :disabled="loading"
                >
                  Reject
                </button>
                <button 
                  @click="viewDeviceDetails(device)"
                  class="btn btn-sm btn-info"
                >
                  Details
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalDevices > limit" class="pagination">
      <button 
        @click="previousPage" 
        :disabled="offset === 0 || loading"
        class="btn btn-sm btn-secondary"
      >
        Previous
      </button>
      <span class="pagination-info">
        {{ offset + 1 }}-{{ Math.min(offset + limit, totalDevices) }} of {{ totalDevices }}
      </span>
      <button 
        @click="nextPage" 
        :disabled="offset + limit >= totalDevices || loading"
        class="btn btn-sm btn-secondary"
      >
        Next
      </button>
    </div>

    <!-- Pre-provision Modal -->
    <PreProvisionModal 
      v-if="showPreProvisionModal"
      @close="showPreProvisionModal = false"
      @success="onPreProvisionSuccess"
    />

    <!-- Device Details Modal -->
    <DeviceDetailsModal 
      v-if="selectedDevice"
      :device="(selectedDevice as any)"
      @close="selectedDevice = null"
      @updated="refreshDevices"
    />

    <!-- Approve Modal -->
    <ApproveDeviceModal 
      v-if="deviceToApprove"
      :device="deviceToApprove"
      @close="deviceToApprove = null"
      @success="onApprovalSuccess"
    />

    <!-- Reject Modal -->
    <RejectDeviceModal 
      v-if="deviceToReject"
      :device="deviceToReject"
      @close="deviceToReject = null"
      @success="onRejectionSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { deviceRegistrationService } from '../../services/deviceRegistrationService'
import PreProvisionModal from './PreProvisionModal.vue'
import DeviceDetailsModal from './DeviceDetailsModal.vue'
import ApproveDeviceModal from './ApproveDeviceModal.vue'
import RejectDeviceModal from './RejectDeviceModal.vue'

interface RegisteredDevice {
  id: string
  serialNumber: string
  deviceModel: string
  deviceType: string
  ipAddress?: string
  macAddress?: string
  locationLat?: number
  locationLng?: number
  locationAddress?: string
  registrationStatus: string
  registrationType: string
  apiKey?: string
  lastHeartbeat?: string
  createdAt: string
  updatedAt: string
  approvedAt?: string
  rejectedAt?: string
  rejectionReason?: string
  camera?: {
    id: string
    name: string
    cameraId: string
    status?: string
  }
  approvedByUser?: {
    id: string
    username: string
    firstName?: string
    lastName?: string
  }
  metadata?: Record<string, any>
}

const devices = ref<RegisteredDevice[]>([])
const filteredDevices = ref<RegisteredDevice[]>([])
const loading = ref(false)
const totalDevices = ref(0)
const limit = ref(20)
const offset = ref(0)

const filters = ref({
  status: '',
  type: ''
})

const showPreProvisionModal = ref(false)
const selectedDevice = ref<RegisteredDevice | null>(null)
const deviceToApprove = ref<RegisteredDevice | null>(null)
const deviceToReject = ref<RegisteredDevice | null>(null)

const pendingCount = computed(() => {
  return devices.value.filter(d => d.registrationStatus === 'pending_approval').length
})

const refreshDevices = async () => {
  loading.value = true
  try {
    const response = await deviceRegistrationService.getAllDevices({
      status: filters.value.status || undefined,
      type: filters.value.type || undefined,
      limit: limit.value,
      offset: offset.value
    })
    
    devices.value = response.devices
    totalDevices.value = response.total
    filterDevices()
  } catch (error) {
    console.error('Failed to load devices:', error)
  } finally {
    loading.value = false
  }
}

const filterDevices = () => {
  filteredDevices.value = devices.value
}

const previousPage = () => {
  if (offset.value > 0) {
    offset.value = Math.max(0, offset.value - limit.value)
    refreshDevices()
  }
}

const nextPage = () => {
  if (offset.value + limit.value < totalDevices.value) {
    offset.value += limit.value
    refreshDevices()
  }
}

const approveDevice = (device: RegisteredDevice) => {
  deviceToApprove.value = device
}

const rejectDevice = (device: RegisteredDevice) => {
  deviceToReject.value = device
}

const viewDeviceDetails = (device: RegisteredDevice) => {
  selectedDevice.value = device
}

const onPreProvisionSuccess = () => {
  showPreProvisionModal.value = false
  refreshDevices()
}

const onApprovalSuccess = () => {
  deviceToApprove.value = null
  refreshDevices()
}

const onRejectionSuccess = () => {
  deviceToReject.value = null
  refreshDevices()
}

const getDeviceRowClass = (device: RegisteredDevice) => {
  return {
    'device-row': true,
    'device-pending': device.registrationStatus === 'pending_approval',
    'device-approved': device.registrationStatus === 'approved' || device.registrationStatus === 'active',
    'device-rejected': device.registrationStatus === 'rejected',
    'device-offline': isDeviceOffline(device)
  }
}

const getStatusClass = (status: string) => {
  const classes = {
    'pending_approval': 'status-pending',
    'approved': 'status-approved',
    'rejected': 'status-rejected',
    'provisioned': 'status-provisioned',
    'active': 'status-active',
    'inactive': 'status-inactive'
  }
  return `status-badge ${classes[status as keyof typeof classes] || 'status-unknown'}`
}

const formatStatus = (status: string) => {
  return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatRegistrationType = (type: string) => {
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}

const getHeartbeatStatus = (lastHeartbeat: string) => {
  const now = new Date()
  const heartbeatDate = new Date(lastHeartbeat)
  const diffMinutes = (now.getTime() - heartbeatDate.getTime()) / (1000 * 60)
  
  if (diffMinutes < 5) return 'Online'
  if (diffMinutes < 30) return 'Recent'
  return 'Offline'
}

const getHeartbeatStatusClass = (lastHeartbeat: string) => {
  const status = getHeartbeatStatus(lastHeartbeat)
  return {
    'heartbeat-online': status === 'Online',
    'heartbeat-recent': status === 'Recent',
    'heartbeat-offline': status === 'Offline'
  }
}

const isDeviceOffline = (device: RegisteredDevice) => {
  if (!device.lastHeartbeat) return true
  return getHeartbeatStatus(device.lastHeartbeat) === 'Offline'
}

onMounted(() => {
  refreshDevices()
})
</script>

<style scoped>
.device-registration-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  gap: 10px;
}

.filters {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.filter-group label {
  font-weight: 600;
  font-size: 0.9em;
}

.filter-group select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.alert {
  padding: 12px 16px;
  margin-bottom: 20px;
  border-radius: 4px;
}

.alert-warning {
  background-color: #fff3cd;
  border-color: #ffecb5;
  color: #856404;
}

.device-table-container {
  overflow-x: auto;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.device-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}

.device-table th,
.device-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.device-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #495057;
}

.device-row.device-pending {
  background-color: #fff3cd;
}

.device-row.device-approved {
  background-color: #d1edff;
}

.device-row.device-rejected {
  background-color: #f8d7da;
}

.device-row.device-offline {
  opacity: 0.7;
}

.camera-info {
  font-size: 0.85em;
  color: #6c757d;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: 600;
  text-transform: uppercase;
}

.status-pending {
  background: #fff3cd;
  color: #856404;
}

.status-approved {
  background: #d1ecf1;
  color: #0c5460;
}

.status-rejected {
  background: #f8d7da;
  color: #721c24;
}

.status-provisioned {
  background: #d4edda;
  color: #155724;
}

.status-active {
  background: #d1ecf1;
  color: #0c5460;
}

.status-inactive {
  background: #e2e3e5;
  color: #383d41;
}

.registration-type {
  font-size: 0.85em;
  color: #6c757d;
  font-style: italic;
}

.action-buttons {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

.heartbeat-online {
  color: #28a745;
}

.heartbeat-recent {
  color: #ffc107;
}

.heartbeat-offline {
  color: #dc3545;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 15px;
  margin-top: 20px;
}

.pagination-info {
  font-size: 0.9em;
  color: #6c757d;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9em;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-success {
  background: #28a745;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #1e7e34;
}

.btn-danger {
  background: #dc3545;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #c82333;
}

.btn-info {
  background: #17a2b8;
  color: white;
}

.btn-info:hover:not(:disabled) {
  background: #138496;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: #545b62;
}

.btn-sm {
  padding: 4px 8px;
  font-size: 0.8em;
}

.text-muted {
  color: #6c757d;
}
</style>