<template>
  <div class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>Pre-provision Device</h3>
        <button @click="$emit('close')" class="close-btn">&times;</button>
      </div>
      
      <form @submit.prevent="submitForm" class="modal-body">
        <div class="form-group">
          <label for="serialNumber">Serial Number *</label>
          <input
            id="serialNumber"
            v-model="formData.serialNumber"
            type="text"
            required
            placeholder="e.g., CAM001-2024-001"
            class="form-control"
          />
        </div>

        <div class="form-group">
          <label for="deviceModel">Device Model *</label>
          <input
            id="deviceModel"
            v-model="formData.deviceModel"
            type="text"
            required
            placeholder="e.g., AI-CAM-4K-V2"
            class="form-control"
          />
        </div>

        <div class="form-group">
          <label for="name">Camera Name *</label>
          <input
            id="name"
            v-model="formData.name"
            type="text"
            required
            placeholder="e.g., Main Entrance Camera"
            class="form-control"
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="deviceType">Device Type</label>
            <select id="deviceType" v-model="formData.deviceType" class="form-control">
              <option value="camera">Camera</option>
              <option value="sensor">Sensor</option>
              <option value="gateway">Gateway</option>
            </select>
          </div>

          <div class="form-group">
            <label for="ipAddress">IP Address</label>
            <input
              id="ipAddress"
              v-model="formData.ipAddress"
              type="text"
              placeholder="192.168.1.100"
              class="form-control"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="macAddress">MAC Address</label>
          <input
            id="macAddress"
            v-model="formData.macAddress"
            type="text"
            placeholder="00:1B:44:11:3A:B7"
            class="form-control"
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="locationLat">Latitude</label>
            <input
              id="locationLat"
              v-model.number="formData.locationLat"
              type="number"
              step="any"
              placeholder="13.7563"
              class="form-control"
            />
          </div>

          <div class="form-group">
            <label for="locationLng">Longitude</label>
            <input
              id="locationLng"
              v-model.number="formData.locationLng"
              type="number"
              step="any"
              placeholder="100.5018"
              class="form-control"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="locationAddress">Location Address</label>
          <input
            id="locationAddress"
            v-model="formData.locationAddress"
            type="text"
            placeholder="Bangkok, Thailand"
            class="form-control"
          />
        </div>

        <div class="form-group">
          <label for="metadata">Additional Metadata (JSON)</label>
          <textarea
            id="metadata"
            v-model="metadataJson"
            rows="3"
            placeholder='{"installation_date": "2024-01-01", "technician": "John Doe"}'
            class="form-control"
          ></textarea>
          <div v-if="metadataError" class="error-text">{{ metadataError }}</div>
        </div>

        <div class="modal-footer">
          <button type="button" @click="$emit('close')" class="btn btn-secondary">
            Cancel
          </button>
          <button type="submit" :disabled="loading" class="btn btn-success">
            <span v-if="loading">Creating...</span>
            <span v-else>Pre-provision Device</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { deviceRegistrationService } from '../../services/deviceRegistrationService'

const emit = defineEmits(['close', 'success'])

const loading = ref(false)
const metadataJson = ref('')
const metadataError = ref('')

const formData = ref({
  serialNumber: '',
  deviceModel: '',
  name: '',
  deviceType: 'camera',
  ipAddress: '',
  macAddress: '',
  locationLat: undefined as number | undefined,
  locationLng: undefined as number | undefined,
  locationAddress: '',
})

const parsedMetadata = computed(() => {
  if (!metadataJson.value.trim()) return {}
  
  try {
    const parsed = JSON.parse(metadataJson.value)
    metadataError.value = ''
    return parsed
  } catch (error) {
    metadataError.value = 'Invalid JSON format'
    return {}
  }
})

const submitForm = async () => {
  if (metadataError.value) {
    return
  }

  loading.value = true
  
  try {
    const payload = {
      ...formData.value,
      metadata: parsedMetadata.value
    }
    
    // Remove null values
    Object.keys(payload).forEach(key => {
      if (payload[key as keyof typeof payload] === null || payload[key as keyof typeof payload] === '') {
        delete payload[key as keyof typeof payload]
      }
    })

    const result = await deviceRegistrationService.preProvisionDevice(payload)
    
    console.log('Device pre-provisioned successfully:', result)
    
    // Show credentials to admin
    alert(`Device pre-provisioned successfully!\n\nAPI Key: ${result.apiKey}\nJWT Secret: ${result.jwtSecret}\nShared Secret: ${result.sharedSecret}\n\nPlease save these credentials securely and provide them to the device.`)
    
    emit('success', result)
  } catch (error: any) {
    console.error('Pre-provision failed:', error)
    
    const errorMessage = error.response?.data?.message || error.message || 'Failed to pre-provision device'
    alert(`Pre-provision failed: ${errorMessage}`)
  } finally {
    loading.value = false
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
  max-width: 600px;
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

.form-group {
  margin-bottom: 16px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 4px;
  font-weight: 600;
  color: #333;
}

.form-control {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.form-control:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
}

.error-text {
  color: #dc3545;
  font-size: 12px;
  margin-top: 4px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
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

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: #545b62;
}

.btn-success {
  background: #28a745;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #1e7e34;
}
</style>