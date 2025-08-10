/**
 * AI Camera v1.3 - Dashboard JavaScript
 * Main dashboard specific functionality
 */

// Dashboard state management
const DashboardManager = {
    statusUpdateInterval: null,
    
    /**
     * Initialize dashboard
     */
    init: function() {
        // Add initial log message
        AICameraUtils.addLogMessage('main-system-log', 'AI Camera Dashboard initialized', 'success');
        AICameraUtils.addLogMessage('main-system-log', 'Loading system status...', 'info');
        
        this.setupWebSocket();
        this.setupStatusUpdates();
        this.loadInitialStatus();
        console.log('Dashboard Manager initialized');
    },

    /**
     * Setup WebSocket connection for real-time updates
     */
    setupWebSocket: function() {
        if (typeof io !== 'undefined') {
            WebSocketManager.init();
            if (WebSocketManager.socket) {
                WebSocketManager.socket.on('camera_status_update', (status) => {
                    this.updateCameraStatus(status);
                });
                
                WebSocketManager.socket.on('detection_status_update', (status) => {
                    this.updateDetectionStatus(status);
                });
            }
        }
    },

    /**
     * Setup periodic status updates
     */
    setupStatusUpdates: function() {
        // Update status immediately
        this.updateSystemStatus();
        
        // Setup periodic updates every 5 seconds
        this.statusUpdateInterval = setInterval(() => {
            this.updateSystemStatus();
        }, 5000);
    },

    /**
     * Load initial system status
     */
    loadInitialStatus: function() {
        // Set initial loading states
        const elements = [
            'main-camera-model', 'main-camera-resolution', 'main-camera-fps',
            'main-camera-detail-status', 'main-system-uptime', 'main-camera-feature-status',
            'feature-camera-model', 'feature-camera-resolution', 'feature-camera-fps'
        ];
        
        elements.forEach(id => {
            const element = document.getElementById(id);
            if (element && element.textContent === 'Loading...') {
                element.textContent = 'Loading...';
            }
        });
        
        this.updateSystemStatus();
    },

    /**
     * Update system status
     */
    updateSystemStatus: function() {
        AICameraUtils.addLogMessage('main-system-log', 'Updating system status...', 'info');
        
        // Update camera status
        AICameraUtils.apiRequest('/camera/status')
            .then(data => {
                if (data && data.success) {
                    this.updateCameraStatus(data.status);
                } else {
                    this.updateCameraStatus(null);
                }
            })
            .catch(error => {
                console.error('Camera API request failed:', error);
                console.warn('Camera status not available:', error.message);
                // Set default offline status with proper structure
                this.updateCameraStatus({
                    streaming: false, 
                    initialized: false,
                    config: null,
                    camera_handler: null,
                    uptime: 0
                });
                AICameraUtils.addLogMessage('main-system-log', 'Failed to get camera status: ' + error.message, 'error');
            });

        // Update detection status
        AICameraUtils.apiRequest('/detection/status')
            .then(data => {
                if (data && data.success) {
                    this.updateDetectionStatus(data.status);
                }
            })
            .catch(error => {
                console.warn('Detection status not available:', error.message);
                // Set default inactive status
                this.updateDetectionStatus({service_running: false});
                AICameraUtils.addLogMessage('main-system-log', 'Failed to get detection status: ' + error.message, 'error');
            });

        // Update system health
        AICameraUtils.apiRequest('/health/system')
            .then(data => {
                if (data && data.success) {
                    this.updateSystemHealth(data);
                }
            })
            .catch(error => {
                console.warn('Health status not available:', error.message);
                // Set default healthy status
                this.updateSystemHealth({data: {overall_status: 'unknown', components: {}}});
                AICameraUtils.addLogMessage('main-system-log', 'Failed to get system health: ' + error.message, 'error');
            });

        // Update WebSocket sender status
        this.updateServerStatus();
    },

    /**
     * Update camera status display
     */
    updateCameraStatus: function(status) {
        let cameraOnline = false;
        let statusText = 'Offline';

        if (status && status.streaming) {
            cameraOnline = true;
            statusText = 'Online';
            AICameraUtils.addLogMessage('main-system-log', 'Camera is streaming', 'success');
        } else if (status && status.initialized) {
            statusText = 'Ready';
            AICameraUtils.addLogMessage('main-system-log', 'Camera initialized but not streaming', 'info');
        } else {
            AICameraUtils.addLogMessage('main-system-log', 'Camera not available', 'warning');
        }

        AICameraUtils.updateStatusIndicator('main-camera-status', cameraOnline, statusText);

        // Update camera information with fallback values
        const resolutionElement = document.getElementById('main-camera-resolution');
        const fpsElement = document.getElementById('main-camera-fps');
        const modelElement = document.getElementById('main-camera-model');
        
        // Feature section elements (duplicate IDs fixed)
        const featureResolutionElement = document.getElementById('feature-camera-resolution');
        const featureFpsElement = document.getElementById('feature-camera-fps');
        const featureModelElement = document.getElementById('feature-camera-model');
        
        // Get resolution from camera_handler.current_config.main.size or config
        if (resolutionElement) {
            let resolution = null;
            
            // Try to get from current_config first (most accurate)
            if (status && status.camera_handler && status.camera_handler.current_config && status.camera_handler.current_config.main && status.camera_handler.current_config.main.size) {
                const size = status.camera_handler.current_config.main.size;
                resolution = `${size[0]}x${size[1]}`;
            }
            // Fallback to config object
            else if (status && status.config && status.config.resolution) {
                resolution = `${status.config.resolution[0]}x${status.config.resolution[1]}`;
            }
            
            resolutionElement.textContent = resolution || 'Unknown';
            // Update feature section as well
            if (featureResolutionElement) {
                featureResolutionElement.textContent = resolution || 'Unknown';
            }
        }

        // Get FPS from camera_handler.current_config.controls.FrameDurationLimits or config
        if (fpsElement) {
            let fps = null;
            
            // Try to get from current_config first (most accurate)
            if (status && status.camera_handler && status.camera_handler.current_config && status.camera_handler.current_config.controls && status.camera_handler.current_config.controls.FrameDurationLimits) {
                const frameDuration = status.camera_handler.current_config.controls.FrameDurationLimits[0];
                fps = `${Math.round(1000000 / frameDuration)} FPS`; // Convert microseconds to FPS
            }
            // Fallback to config object
            else if (status && status.config && status.config.framerate) {
                fps = `${status.config.framerate} FPS`;
            }
            
            fpsElement.textContent = fps || 'Unknown';
            // Update feature section as well
            if (featureFpsElement) {
                featureFpsElement.textContent = fps || 'Unknown';
            }
        }

        // Update camera model with fallback
        const cameraModel = (status && status.camera_handler && status.camera_handler.camera_properties && status.camera_handler.camera_properties.Model) || 'Unknown';
        
        if (modelElement) {
            modelElement.textContent = cameraModel;
        }
        // Update feature section as well
        if (featureModelElement) {
            featureModelElement.textContent = cameraModel;
        }

        // Update detailed status
        const detailStatusElement = document.getElementById('main-camera-detail-status');
        if (detailStatusElement) {
            if (status && status.streaming) {
                detailStatusElement.textContent = 'Streaming';
            } else if (status && status.initialized) {
                detailStatusElement.textContent = 'Initialized';
            } else {
                detailStatusElement.textContent = 'Not initialized';
            }
        }

        // Update uptime with fallback
        const uptimeElement = document.getElementById('main-system-uptime');
        if (uptimeElement) {
            if (status && status.uptime) {
                uptimeElement.textContent = AICameraUtils.formatDuration(status.uptime);
            } else {
                uptimeElement.textContent = 'Unknown';
            }
        }

        // Update feature status (duplicate element in features section)
        const featureStatusElement = document.getElementById('main-camera-feature-status');
        if (featureStatusElement) {
            if (status && status.streaming) {
                featureStatusElement.textContent = 'Streaming';
            } else if (status && status.initialized) {
                featureStatusElement.textContent = 'Initialized';
            } else {
                featureStatusElement.textContent = 'Not initialized';
            }
        }
    },

    /**
     * Update detection status display
     */
    updateDetectionStatus: function(status) {
        const detectionActive = status && status.service_running || false;
        AICameraUtils.updateStatusIndicator('main-detection-status', detectionActive, 
            detectionActive ? 'Active' : 'Inactive');
        
        // Add log message for detection status
        if (detectionActive) {
            AICameraUtils.addLogMessage('main-system-log', 'AI Detection service is running', 'success');
        } else {
            AICameraUtils.addLogMessage('main-system-log', 'AI Detection service is stopped', 'info');
        }
    },

    /**
     * Update system health display
     */
    updateSystemHealth: function(healthData) {
        console.log('Updating system health with data:', healthData);
        
        // Extract health data from new format
        const health = healthData.data || healthData;
        const overallStatus = health.overall_status || 'unknown';
        const components = health.components || {};
        
        // Determine system health based on overall status
        const systemHealthy = overallStatus === 'healthy';
        const systemStatusText = overallStatus.charAt(0).toUpperCase() + overallStatus.slice(1);
        
        AICameraUtils.updateStatusIndicator('main-system-status', systemHealthy, systemStatusText);

        // Database status from components
        const databaseComponent = components.database || {};
        const databaseHealthy = databaseComponent.status === 'healthy';
        const databaseStatusText = databaseComponent.status ? 
            databaseComponent.status.charAt(0).toUpperCase() + databaseComponent.status.slice(1) : 
            'Unknown';
            
        AICameraUtils.updateStatusIndicator('main-database-status', databaseHealthy, databaseStatusText);
        
        // Update detailed database status
        const databaseDetailElement = document.getElementById('main-database-detail-status');
        if (databaseDetailElement) {
            databaseDetailElement.textContent = databaseStatusText;
        }
        
        // Log system health status
        if (overallStatus === 'healthy') {
            AICameraUtils.addLogMessage('main-system-log', 'System health: ' + systemStatusText, 'success');
        } else {
            AICameraUtils.addLogMessage('main-system-log', 'System health: ' + systemStatusText, 'warning');
        }
    },

    /**
     * Update server connection status
     */
    updateServerStatus: function() {
        // Get WebSocket sender status
        AICameraUtils.apiRequest('/websocket-sender/status')
            .then(data => {
                if (data && data.success) {
                    this.updateServerConnectionDisplay(data.status);
                } else {
                    this.updateServerConnectionDisplay(null);
                }
            })
            .catch(error => {
                console.warn('WebSocket sender status not available:', error.message);
                this.updateServerConnectionDisplay(null);
            });

        // Get server communication logs
        AICameraUtils.apiRequest('/websocket-sender/logs?limit=10')
            .then(data => {
                if (data && data.success) {
                    this.updateServerLogs(data.logs);
                }
            })
            .catch(error => {
                console.warn('WebSocket sender logs not available:', error.message);
            });
    },

    /**
     * Update server connection status display
     */
    updateServerConnectionDisplay: function(status) {
        let connected = false;
        let connectionText = 'Disconnected';
        let dataActive = false;
        let dataText = 'Inactive';
        let lastSync = 'Never';

        if (status) {
            // Server connection status
            if (status.connected) {
                connected = true;
                connectionText = 'Connected';
            }

            // Data sending status
            if (status.running && (status.detection_thread_alive || status.health_thread_alive)) {
                dataActive = true;
                dataText = 'Active';
            }

            // Last sync time
            if (status.last_detection_check || status.last_health_check) {
                const lastDetectionCheck = status.last_detection_check ? new Date(status.last_detection_check) : null;
                const lastHealthCheck = status.last_health_check ? new Date(status.last_health_check) : null;
                
                let latestSync = null;
                if (lastDetectionCheck && lastHealthCheck) {
                    latestSync = lastDetectionCheck > lastHealthCheck ? lastDetectionCheck : lastHealthCheck;
                } else if (lastDetectionCheck) {
                    latestSync = lastDetectionCheck;
                } else if (lastHealthCheck) {
                    latestSync = lastHealthCheck;
                }
                
                if (latestSync) {
                    lastSync = latestSync.toLocaleString();
                }
            }
        }

        // Update UI elements
        AICameraUtils.updateStatusIndicator('main-server-connection-status', connected, connectionText);
        AICameraUtils.updateStatusIndicator('main-data-sending-status', dataActive, dataText);
        
        const lastSyncElement = document.getElementById('main-last-sync-time');
        if (lastSyncElement) {
            lastSyncElement.textContent = lastSync;
        }
    },

    /**
     * Update server communication logs display
     */
    updateServerLogs: function(logs) {
        const logsContainer = document.getElementById('main-server-logs');
        if (!logsContainer) return;

        // Clear existing logs
        logsContainer.innerHTML = '';

        if (!logs || logs.length === 0) {
            logsContainer.innerHTML = '<div class="text-muted p-3">No server communication logs available</div>';
            return;
        }

        // Add logs
        logs.forEach(log => {
            const logElement = document.createElement('div');
            logElement.className = 'log-entry p-2 border-bottom';
            
            // Determine log type class
            let logClass = 'text-muted';
            if (log.status === 'success') {
                logClass = 'text-success';
            } else if (log.status === 'failed') {
                logClass = 'text-danger';
            } else if (log.status === 'no_data') {
                logClass = 'text-info';
            }

            // Format message
            let message = '';
            if (log.status === 'no_data') {
                message = `${log.timestamp}: no data to send`;
            } else if (log.status === 'success' && log.action === 'send_detection') {
                message = `${log.timestamp}: send lpr detection completed (${log.record_count} records)`;
            } else if (log.status === 'success' && log.action === 'send_health') {
                message = `${log.timestamp}: send health status completed (${log.record_count} records)`;
            } else {
                message = `${log.timestamp}: ${log.message || log.action}`;
            }

            logElement.innerHTML = `<small class="${logClass}">${message}</small>`;
            logsContainer.appendChild(logElement);
        });

        // Auto-scroll to bottom
        logsContainer.scrollTop = logsContainer.scrollHeight;
    },

    /**
     * Cleanup when leaving page
     */
    cleanup: function() {
        if (this.statusUpdateInterval) {
            clearInterval(this.statusUpdateInterval);
        }
    }
};

// Quick action handlers
function handleQuickAction(action) {
    switch(action) {
        case 'camera-control':
            window.location.href = '/camera';
            break;
        case 'capture-image':
            captureImage();
            break;
        case 'system-health':
            window.location.href = '/health';
            break;
        case 'ai-detection':
            window.location.href = '/detection';
            break;
        default:
            console.warn('Unknown quick action:', action);
    }
}

/**
 * Capture image function
 */
function captureImage() {
    const button = event.target.closest('.quick-action-btn');
    const originalText = button.innerHTML;
    
    // Show loading state
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i><br><strong>Capturing...</strong><br><small>Please wait</small>';
    button.disabled = true;

    AICameraUtils.apiRequest('/camera/capture', { method: 'POST' })
        .then(data => {
            if (data.success) {
                AICameraUtils.showToast('Image captured successfully!', 'success');
            } else {
                throw new Error(data.error || 'Capture failed');
            }
        })
        .catch(error => {
            AICameraUtils.showToast(`Capture failed: ${error.message}`, 'error');
        })
        .finally(() => {
            // Restore button state
            button.innerHTML = originalText;
            button.disabled = false;
        });
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard JavaScript: DOM loaded, initializing...');
    
    DashboardManager.init();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        DashboardManager.cleanup();
    });
    
    console.log('Dashboard JavaScript: Initialization complete');
});
