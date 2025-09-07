<template>
  <div class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>Device Details</h3>
        <button @click="$emit('close')" class="close-btn">&times;</button>
      </div>
      
      <div class="modal-body">
        <div class="device-details">
          <!-- Basic Information -->
          <div class="detail-section">
            <h4>Basic Information</h4>
            <div class="detail-grid">
              <div class="detail-item">
                <label>Serial Number:</label>
                <span class="value">{{ device.serialNumber }}</span>
              </div>
              <div class="detail-item">
                <label>Device Model:</label>
                <span class="value">{{ device.deviceModel }}</span>
              </div>
              <div class="detail-item">
                <label>Device Type:</label>
                <span class="value">{{ device.deviceType }}</span>
              </div>
              <div class="detail-item">
                <label>Registration Status:</label>
                <span :class="getStatusClass(device.registrationStatus)">
                  {{ formatStatus(device.registrationStatus) }}
                </span>
              </div>
              <div class="detail-item">
                <label>Registration Type:</label>
                <span class="value">{{ formatRegistrationType(device.registrationType) }}</span>
              </div>
            </div>
          </div>

          <!-- Network Information -->
          <div class="detail-section">
            <h4>Network Information</h4>
            <div class="detail-grid">
              <div class="detail-item">
                <label>IP Address:</label>
                <span class="value">{{ device.ipAddress || 'N/A' }}</span>
              </div>
              <div class="detail-item">
                <label>MAC Address:</label>
                <span class="value">{{ device.macAddress || 'N/A' }}</span>
              </div>
              <div class="detail-item">
                <label>Last Heartbeat:</label>
                <span v-if="device.lastHeartbeat" class="value">
                  {{ formatDate(device.lastHeartbeat) }}
                  <span :class="getHeartbeatStatusClass(device.lastHeartbeat)">
                    ({{ getHeartbeatStatus(device.lastHeartbeat) }})
                  </span>
                </span>
                <span v-else class="value text-muted">Never</span>
              </div>
            </div>
          </div>

          <!-- Location Information -->
          <div class="detail-section">
            <h4>Location Information</h4>
            <div class="detail-grid">
              <div class="detail-item">
                <label>Address:</label>
                <span class="value">{{ device.locationAddress || 'N/A' }}</span>
              </div>
              <div class="detail-item">
                <label>Coordinates:</label>
                <span v-if="device.locationLat && device.locationLng" class="value">
                  {{ device.locationLat.toFixed(6) }}, {{ device.locationLng.toFixed(6) }}
                </span>
                <span v-else class="value">N/A</span>
              </div>
            </div>
          </div>

          <!-- Camera Information -->
          <div v-if="device.camera" class="detail-section">
            <h4>Camera Information</h4>
            <div class="detail-grid">
              <div class="detail-item">
                <label>Camera Name:</label>
                <span class="value">{{ device.camera.name }}</span>
              </div>
              <div class="detail-item">
                <label>Camera ID:</label>
                <span class="value">{{ device.camera.cameraId }}</span>
              </div>
              <div class="detail-item">
                <label>Camera Status:</label>
                <span :class="getCameraStatusClass(device.camera.status)">
                  {{ formatStatus(device.camera.status) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Registration Timeline -->
          <div class="detail-section">
            <h4>Registration Timeline</h4>
            <div class="timeline">
              <div class="timeline-item">
                <div class="timeline-marker"></div>
                <div class="timeline-content">
                  <strong>Registered</strong>
                  <div class="timeline-date">{{ formatDate(device.createdAt) }}</div>
                </div>
              </div>
              
              <div v-if="device.approvedAt" class="timeline-item">
                <div class="timeline-marker approved"></div>
                <div class="timeline-content">
                  <strong>Approved</strong>
                  <div class="timeline-date">{{ formatDate(device.approvedAt) }}</div>
                  <div v-if="device.approvedByUser" class="timeline-user">
                    by {{ formatUserName(device.approvedByUser) }}
                  </div>
                </div>
              </div>
              
              <div v-if="device.rejectedAt" class="timeline-item">
                <div class="timeline-marker rejected"></div>
                <div class="timeline-content">
                  <strong>Rejected</strong>
                  <div class="timeline-date">{{ formatDate(device.rejectedAt) }}</div>
                  <div v-if="device.rejectedByUser" class="timeline-user">
                    by {{ formatUserName(device.rejectedByUser) }}
                  </div>
                  <div v-if="device.rejectionReason" class="rejection-reason">
                    Reason: {{ device.rejectionReason }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Security Information -->
          <div v-if="device.apiKey" class="detail-section">
            <h4>Security Information</h4>
            <div class="security-info">
              <div class="security-item">
                <label>API Key:</label>
                <div class="credential-display">
                  <span v-if="showCredentials" class="credential">{{ device.apiKey }}</span>
                  <span v-else class="credential-hidden">••••••••••••••••••••••••••••••••</span>
                  <button @click="toggleCredentials" class="btn-toggle">
                    {{ showCredentials ? 'Hide' : 'Show' }}
                  </button>
                </div>
              </div>
              
              <div v-if="device.jwtSecret" class="security-item">
                <label>JWT Secret:</label>
                <div class="credential-display">
                  <span v-if="showCredentials" class="credential">{{ device.jwtSecret }}</span>
                  <span v-else class="credential-hidden">••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••</span>
                </div>
              </div>
              
              <div v-if="device.sharedSecret" class="security-item">
                <label>Shared Secret:</label>
                <div class="credential-display">
                  <span v-if="showCredentials" class="credential">{{ device.sharedSecret }}</span>
                  <span v-else class="credential-hidden">••••••••••••••••••••••••••••••••••••••••••••••••</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Metadata -->
          <div v-if="device.metadata && Object.keys(device.metadata).length > 0" class="detail-section">
            <h4>Additional Metadata</h4>
            <div class="metadata-display">
              <pre>{{ JSON.stringify(device.metadata, null, 2) }}</pre>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="$emit('close')" class="btn btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface User {
  id: string
  username: string
  firstName?: string
  lastName?: string
}

interface Camera {
  id: string
  name: string
  cameraId: string
  status?: string
}

interface Device {
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
  jwtSecret?: string
  sharedSecret?: string
  metadata?: Record<string, any>
  lastHeartbeat?: string
  createdAt: string
  updatedAt: string
  approvedAt?: string
  rejectedAt?: string
  rejectionReason?: string
  camera?: Camera
  approvedByUser?: User
  rejectedByUser?: User
}

defineProps<{
  device: Device
}>()

defineEmits(['close', 'updated'])

const showCredentials = ref(false)

const toggleCredentials = () => {
  showCredentials.value = !showCredentials.value
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

const getCameraStatusClass = (status?: string) => {
  const classes = {
    'active': 'status-active',
    'inactive': 'status-inactive',
    'maintenance': 'status-maintenance'
  }
  const key = (status || 'inactive') as keyof typeof classes
  return `status-badge ${classes[key] || 'status-unknown'}`
}

const formatStatus = (status: string | undefined) => {
  const s = status || 'unknown'
  return s.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatRegistrationType = (type: string) => {
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}

const formatUserName = (user: User) => {
  if (user.firstName && user.lastName) {
    return `${user.firstName} ${user.lastName} (${user.username})`
  }
  return user.username
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
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #000;
}

.modal-body {
  padding: 20px;
}

.detail-section {
  margin-bottom: 30px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.detail-section h4 {
  margin: 0 0 16px 0;
  color: #333;
  font-size: 1.1em;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
}

.detail-item label {
  font-weight: 600;
  color: #666;
  font-size: 0.9em;
  margin-bottom: 4px;
}

.detail-item .value {
  color: #333;
  word-break: break-all;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: 600;
  text-transform: uppercase;
  display: inline-block;
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

.status-maintenance {
  background: #fff3cd;
  color: #856404;
}

.heartbeat-online {
  color: #28a745;
  font-weight: 600;
}

.heartbeat-recent {
  color: #ffc107;
  font-weight: 600;
}

.heartbeat-offline {
  color: #dc3545;
  font-weight: 600;
}

.text-muted {
  color: #6c757d;
}

.timeline {
  position: relative;
  padding-left: 30px;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #dee2e6;
}

.timeline-item {
  position: relative;
  margin-bottom: 20px;
}

.timeline-marker {
  position: absolute;
  left: -23px;
  top: 0;
  width: 16px;
  height: 16px;
  background: #6c757d;
  border-radius: 50%;
  border: 3px solid white;
}

.timeline-marker.approved {
  background: #28a745;
}

.timeline-marker.rejected {
  background: #dc3545;
}

.timeline-content strong {
  color: #333;
}

.timeline-date {
  color: #6c757d;
  font-size: 0.9em;
  margin-top: 2px;
}

.timeline-user {
  color: #007bff;
  font-size: 0.9em;
  margin-top: 2px;
}

.rejection-reason {
  color: #dc3545;
  font-size: 0.9em;
  margin-top: 4px;
  font-style: italic;
}

.security-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.security-item label {
  font-weight: 600;
  color: #666;
  font-size: 0.9em;
  margin-bottom: 4px;
  display: block;
}

.credential-display {
  display: flex;
  align-items: center;
  gap: 10px;
  background: white;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.credential {
  font-family: monospace;
  font-size: 0.9em;
  flex: 1;
  word-break: break-all;
}

.credential-hidden {
  font-family: monospace;
  font-size: 0.9em;
  flex: 1;
}

.btn-toggle {
  background: #007bff;
  color: white;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  cursor: pointer;
}

.btn-toggle:hover {
  background: #0056b3;
}

.metadata-display {
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow-x: auto;
}

.metadata-display pre {
  margin: 0;
  padding: 16px;
  font-size: 0.9em;
  color: #333;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 20px;
  border-top: 1px solid #eee;
  margin-top: 20px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #545b62;
}

@media (max-width: 768px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>