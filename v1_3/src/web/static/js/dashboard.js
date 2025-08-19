/**
 * AI Camera v1.3 - Dashboard JavaScript
 * Main dashboard specific functionality
 */

// Dashboard state management
const DashboardManager = {
    statusUpdateInterval: null,
    
    /**
     * Initialize dashboard with modular architecture support
     */
    init: function() {
        console.log('Initializing dashboard with modular architecture...');
        
        // Initialize core functionality
        this.initCoreModules();
        
        // Check and initialize optional modules
        this.checkOptionalModules();
        
        // Set up periodic updates
        this.setupPeriodicUpdates();
        
        console.log('Dashboard initialization completed');
    },

    /**
     * Initialize core modules (always available)
     */
    initCoreModules: function() {
        console.log('Initializing core modules...');
        
        // Initialize WebSocket connection for core modules
        this.initWebSocket();
        
        // Set up core status updates
        this.updateSystemStatusComprehensive();
        
        // Set up core event handlers
        this.setupCoreEventHandlers();
    },

    /**
     * Check and initialize optional modules
     */
    checkOptionalModules: function() {
        console.log('Checking optional modules...');
        
        // Check WebSocket Sender (optional)
        this.checkWebSocketSender();
        
        // Check Storage Manager (optional)
        this.checkStorageManager();
    },

    /**
     * Check if WebSocket Sender is available
     */
    checkWebSocketSender: function() {
        AICameraUtils.apiRequest('/websocket-sender/status')
            .then(data => {
                if (data.success) {
                    console.log('WebSocket Sender is available');
                    this.showOptionalModule('websocket_sender');
                    this.updateWebSocketStatus('sender', data.status);
                } else {
                    console.log('WebSocket Sender not available (optional module)');
                    this.hideOptionalModule('websocket_sender');
                }
            })
            .catch(error => {
                console.log('WebSocket Sender not available (optional module):', error.message);
                this.hideOptionalModule('websocket_sender');
            });
    },

    /**
     * Check if Storage Manager is available
     */
    checkStorageManager: function() {
        AICameraUtils.apiRequest('/storage/status')
            .then(data => {
                if (data.success) {
                    console.log('Storage Manager is available');
                    this.showOptionalModule('storage');
                } else {
                    console.log('Storage Manager not available (optional module)');
                    this.hideOptionalModule('storage');
                }
            })
            .catch(error => {
                console.log('Storage Manager not available (optional module):', error.message);
                this.hideOptionalModule('storage');
            });
    },

    /**
     * Show optional module sections
     */
    showOptionalModule: function(moduleName) {
        switch (moduleName) {
            case 'websocket_sender':
                const serverCommSection = document.getElementById('server-communication-section');
                const serverLogsSection = document.getElementById('server-logs-section');
                if (serverCommSection) serverCommSection.style.display = 'block';
                if (serverLogsSection) serverLogsSection.style.display = 'block';
                break;
            case 'storage':
                // Storage module sections would be shown here if needed
                break;
        }
    },

    /**
     * Hide optional module sections
     */
    hideOptionalModule: function(moduleName) {
        switch (moduleName) {
            case 'websocket_sender':
                const serverCommSection = document.getElementById('server-communication-section');
                const serverLogsSection = document.getElementById('server-logs-section');
                if (serverCommSection) serverCommSection.style.display = 'none';
                if (serverLogsSection) serverLogsSection.style.display = 'none';
                break;
            case 'storage':
                // Storage module sections would be hidden here if needed
                break;
        }
    },

    /**
     * Set up core event handlers
     */
    setupCoreEventHandlers: function() {
        // Core event handlers for camera, detection, health
        // These are always available
    },

    /**
     * Set up periodic updates
     */
    setupPeriodicUpdates: function() {
        // Update core status every 5 seconds
        setInterval(() => {
            this.updateSystemStatusComprehensive();
        }, 5000);
        
        // Update system info every 30 seconds
        setInterval(() => {
            this.updateSystemInfoFromAPI();
        }, 30000);
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
        
        // Setup server connection status updates
        this.updateServerConnectionStatus();
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
            'main-system-uptime', 'feature-camera-status',
            'feature-camera-model', 'feature-camera-resolution', 'feature-camera-fps',
            'system-info-cpu', 'system-info-ram', 'system-info-disk', 'system-info-os', 'system-info-ai-accelerator'
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
        // Update camera status
        console.log('Making camera status API request...');
        AICameraUtils.apiRequest('/camera/status')
            .then(data => {
                if (data.success) {
                    this.updateCameraStatus(data.status);
                    this.updateWebSocketStatus('camera', data.status);
                }
            })
            .catch(error => {
                console.error('Failed to fetch camera status:', error);
                this.updateWebSocketStatus('camera', { error: true });
            });

        // Update detection status
        AICameraUtils.apiRequest('/detection/status')
            .then(data => {
                if (data.success) {
                    this.updateDetectionStatus(data.status);
                    this.updateWebSocketStatus('detection', data.status);
                }
            })
            .catch(error => {
                console.error('Failed to fetch detection status:', error);
                this.updateWebSocketStatus('detection', { error: true });
            });

        // Update system information (fast endpoint)
        AICameraUtils.apiRequest('/health/system-info')
            .then(data => {
                if (data.success) {
                    this.updateSystemInfo(data);
                }
            })
            .catch(error => {
                console.error('Failed to fetch system info:', error);
            });
            
        // Update server connection status
        this.updateServerConnectionStatus();
    },

    /**
     * Update server connection status
     */
    updateServerConnectionStatus: function() {
        AICameraUtils.apiRequest('/websocket-sender/status')
            .then(data => {
                if (data.success) {
                    const status = data.status;
                    const connectionElement = document.getElementById('main-server-connection-status');
                    const connectionText = document.getElementById('main-server-connection-text');
                    const dataSendingElement = document.getElementById('main-data-sending-status');
                    const dataSendingText = document.getElementById('main-data-sending-text');
                    const lastSyncElement = document.getElementById('main-last-sync-time');
                    
                    // Update server connection status
                    if (connectionElement && connectionText) {
                        if (status.connected) {
                            connectionElement.className = 'status-indicator status-online';
                            connectionText.textContent = 'Connected';
                        } else if (status.running) {
                            connectionElement.className = 'status-indicator status-warning';
                            connectionText.textContent = 'Running';
                        } else {
                            connectionElement.className = 'status-indicator status-offline';
                            connectionText.textContent = 'Disconnected';
                        }
                    }
                    
                    // Update data sending status
                    if (dataSendingElement && dataSendingText) {
                        if (status.running && (status.total_detections_sent > 0 || status.total_health_sent > 0)) {
                            dataSendingElement.className = 'status-indicator status-online';
                            dataSendingText.textContent = 'Active';
                        } else if (status.running) {
                            dataSendingElement.className = 'status-indicator status-warning';
                            dataSendingText.textContent = 'Ready';
                        } else {
                            dataSendingElement.className = 'status-indicator status-offline';
                            dataSendingText.textContent = 'Inactive';
                        }
                    }
                    
                    // Update last sync time
                    if (lastSyncElement) {
                        if (status.last_detection_check || status.last_health_check) {
                            const lastCheck = status.last_detection_check || status.last_health_check;
                            const lastCheckTime = new Date(lastCheck);
                            const now = new Date();
                            const diffMs = now - lastCheckTime;
                            const diffMins = Math.floor(diffMs / 60000);
                            
                            if (diffMins < 1) {
                                lastSyncElement.textContent = 'Just now';
                            } else if (diffMins < 60) {
                                lastSyncElement.textContent = `${diffMins} min ago`;
                            } else {
                                const diffHours = Math.floor(diffMins / 60);
                                lastSyncElement.textContent = `${diffHours} hours ago`;
                            }
                        } else {
                            lastSyncElement.textContent = 'Never';
                        }
                    }
                }
            })
            .catch(error => {
                console.error('Failed to fetch server connection status:', error);
                // Update status to show error
                const connectionElement = document.getElementById('main-server-connection-status');
                const connectionText = document.getElementById('main-server-connection-text');
                if (connectionElement && connectionText) {
                    connectionElement.className = 'status-indicator status-offline';
                    connectionText.textContent = 'Error';
                }
            });
    },

    /**
     * Update system status (comprehensive) - Modular Architecture
     */
    updateSystemStatusComprehensive: function() {
        console.log('Updating system status (modular architecture)...');
        
        // === CORE MODULES (Always Available) ===
        // Update health status (comprehensive) - CORE MODULE
        AICameraUtils.apiRequest('/health/system')
            .then(data => {
                if (data.success) {
                    this.updateHealthStatus(data);
                    // Health status is handled by updateHealthStatus, no need for separate WebSocket status
                }
            })
            .catch(error => {
                console.error('Failed to fetch health status:', error);
                // Update system status to show error
                const systemStatusElement = document.getElementById('main-system-status');
                const systemStatusText = document.getElementById('main-system-status-text');
                if (systemStatusElement && systemStatusText) {
                    systemStatusElement.className = 'status-indicator status-offline';
                    systemStatusText.textContent = 'Error';
                }
            });

        // Update streaming status (if available) - CORE MODULE
        this.updateStreamingStatus();

        // === OPTIONAL MODULES (Conditionally Available) ===
        // Update WebSocket sender status - OPTIONAL MODULE
        this.updateWebSocketSenderStatus();

        // Update server logs - OPTIONAL MODULE
        this.updateServerLogsFromAPI();
    },

    /**
     * Update WebSocket status for different components
     */
    updateWebSocketStatus: function(component, status) {
        console.log(`updateWebSocketStatus called for ${component}:`, status);
        
        switch (component) {
            case 'sender':
                // Update server connection status using existing elements
                const connectionElement = document.getElementById('main-server-connection-status');
                const connectionText = document.getElementById('main-server-connection-text');
                
                if (connectionElement && connectionText) {
                    if (status.connected) {
                        connectionElement.className = 'status-indicator status-online';
                        connectionText.textContent = 'Connected';
                    } else if (status.offline_mode) {
                        connectionElement.className = 'status-indicator status-warning';
                        connectionText.textContent = 'Offline Mode';
                    } else if (status.running) {
                        connectionElement.className = 'status-indicator status-warning';
                        connectionText.textContent = 'Running';
                    } else {
                        connectionElement.className = 'status-indicator status-offline';
                        connectionText.textContent = 'Disconnected';
                    }
                } else {
                    console.warn('Server connection status elements not found');
                }
                break;
                
            case 'streaming':
                // Update data sending status using existing elements
                const dataSendingElement = document.getElementById('main-data-sending-status');
                const dataSendingText = document.getElementById('main-data-sending-text');
                
                if (dataSendingElement && dataSendingText) {
                    if (status.active || status.streaming) {
                        dataSendingElement.className = 'status-indicator status-online';
                        dataSendingText.textContent = 'Active';
                    } else if (status.running) {
                        dataSendingElement.className = 'status-indicator status-warning';
                        dataSendingText.textContent = 'Ready';
                    } else {
                        dataSendingElement.className = 'status-indicator status-offline';
                        dataSendingText.textContent = 'Inactive';
                    }
                } else {
                    console.warn('Data sending status elements not found');
                }
                break;
                
            case 'health':
                // Health status is handled by updateHealthStatus function
                console.log('Health status update handled by updateHealthStatus');
                return;
                
            case 'database':
                // Database status is handled by main dashboard status cards
                console.log('Database status update handled by main dashboard');
                return;
                
            default:
                console.log('Unknown WebSocket component:', component);
                return; // Skip unknown components
        }
        
        // Add log message for connection status changes
        if (component === 'sender') {
            const logMessage = status.connected ? 
                'WebSocket sender connected to server' : 
                (status.offline_mode ? 'WebSocket sender in offline mode' : 'WebSocket sender disconnected from server');
            AICameraUtils.addLogMessage('main-server-logs', logMessage, status.connected ? 'success' : 'warning');
        }
    },

    /**
     * Update overall WebSocket communication status
     */
    updateWebSocketCommunicationStatus: function() {
        // This function is now handled by updateServerConnectionStatus()
        // No need for separate websocket-communication-status element
        console.log('WebSocket communication status update handled by server connection status');
    },

    /**
     * Update camera status display
     */
    updateCameraStatus: function(status) {
        console.log('updateCameraStatus called with:', status);
        
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

        // Feature section elements (duplicate IDs fixed)
        const featureResolutionElement = document.getElementById('feature-camera-resolution');
        const featureFpsElement = document.getElementById('feature-camera-fps');
        const featureModelElement = document.getElementById('feature-camera-model');
        
        console.log('Found elements:', {
            resolution: featureResolutionElement,
            fps: featureFpsElement,
            model: featureModelElement
        });
        
        // Get resolution from camera_handler.current_config.main.size or config
        let resolution = null;
        
        console.log('Camera handler config:', status?.camera_handler?.current_config);
        
        // Try to get from current_config first (most accurate)
        if (status && status.camera_handler && status.camera_handler.current_config && status.camera_handler.current_config.main && status.camera_handler.current_config.main.size) {
            const size = status.camera_handler.current_config.main.size;
            resolution = `${size[0]}x${size[1]}`;
            console.log('Resolution from current_config:', resolution);
        }
        // Fallback to config object
        else if (status && status.config && status.config.resolution) {
            resolution = `${status.config.resolution[0]}x${status.config.resolution[1]}`;
            console.log('Resolution from config:', resolution);
        }
        
        // Update feature section
        if (featureResolutionElement) {
            featureResolutionElement.textContent = resolution || 'Unknown';
            console.log('Updated resolution element with:', resolution || 'Unknown');
        }

        // Get FPS from camera_handler.current_config.controls.FrameDurationLimits or config
        let fps = null;
        
        console.log('Camera controls:', status?.camera_handler?.current_config?.controls);
        
        // Try to get from current_config first (most accurate)
        if (status && status.camera_handler && status.camera_handler.current_config && status.camera_handler.current_config.controls && status.camera_handler.current_config.controls.FrameDurationLimits) {
            const frameDuration = status.camera_handler.current_config.controls.FrameDurationLimits[0];
            fps = `${Math.round(1000000 / frameDuration)} FPS`; // Convert microseconds to FPS
            console.log('FPS from current_config:', fps);
        }
        // Fallback to config object
        else if (status && status.config && status.config.framerate) {
            fps = `${status.config.framerate} FPS`;
            console.log('FPS from config:', fps);
        }
        
        // Update feature section
        if (featureFpsElement) {
            featureFpsElement.textContent = fps || 'Unknown';
            console.log('Updated FPS element with:', fps || 'Unknown');
        }

        // Update camera model with fallback
        const cameraModel = (status && status.camera_handler && status.camera_handler.camera_properties && status.camera_handler.camera_properties.Model) || 'Unknown';
        
        console.log('Camera model:', cameraModel);
        
        // Update feature section
        if (featureModelElement) {
            featureModelElement.textContent = cameraModel;
            console.log('Updated model element with:', cameraModel);
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
        const featureStatusElement = document.getElementById('feature-camera-status');
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
     * Update health status display
     */
    updateHealthStatus: function(data) {
        console.log('updateHealthStatus called with:', data);
        
        if (!data || !data.data) {
            console.warn('Invalid health data received');
            return;
        }
        
        const healthData = data.data;
        
        // Update overall system status
        if (healthData.overall_status) {
            const systemStatusElement = document.getElementById('main-system-status');
            const systemStatusText = document.getElementById('main-system-status-text');
            
            if (systemStatusElement && systemStatusText) {
                const status = healthData.overall_status.toLowerCase();
                if (status === 'healthy') {
                    systemStatusElement.className = 'status-indicator status-online';
                    systemStatusText.textContent = 'Healthy';
                } else if (status === 'unhealthy') {
                    systemStatusElement.className = 'status-indicator status-warning';
                    systemStatusText.textContent = 'Unhealthy';
                } else if (status === 'critical') {
                    systemStatusElement.className = 'status-indicator status-offline';
                    systemStatusText.textContent = 'Critical';
                } else {
                    systemStatusElement.className = 'status-indicator status-offline';
                    systemStatusText.textContent = 'Unknown';
                }
            }
        }
        
        // Update component statuses
        if (healthData.components) {
            // Camera status
            if (healthData.components.camera) {
                const cameraStatus = healthData.components.camera;
                const cameraStatusElement = document.getElementById('main-camera-status');
                const cameraStatusText = document.getElementById('main-camera-status-text');
                
                if (cameraStatusElement && cameraStatusText) {
                    const status = cameraStatus.status?.toLowerCase() || 'unknown';
                    if (status === 'healthy') {
                        cameraStatusElement.className = 'status-indicator status-online';
                        cameraStatusText.textContent = 'Online';
                    } else if (status === 'unhealthy') {
                        cameraStatusElement.className = 'status-indicator status-warning';
                        cameraStatusText.textContent = 'Warning';
                    } else {
                        cameraStatusElement.className = 'status-indicator status-offline';
                        cameraStatusText.textContent = 'Offline';
                    }
                }
            }
            
            // Detection status
            if (healthData.components.detection) {
                const detectionStatus = healthData.components.detection;
                const detectionStatusElement = document.getElementById('main-detection-status');
                const detectionStatusText = document.getElementById('main-detection-status-text');
                
                if (detectionStatusElement && detectionStatusText) {
                    const status = detectionStatus.status?.toLowerCase() || 'unknown';
                    if (status === 'healthy') {
                        detectionStatusElement.className = 'status-indicator status-online';
                        detectionStatusText.textContent = 'Active';
                    } else if (status === 'unhealthy') {
                        detectionStatusElement.className = 'status-indicator status-warning';
                        detectionStatusText.textContent = 'Warning';
                    } else {
                        detectionStatusElement.className = 'status-indicator status-offline';
                        detectionStatusText.textContent = 'Inactive';
                    }
                }
            }
            
            // Database status
            if (healthData.components.database) {
                const databaseStatus = healthData.components.database;
                const databaseStatusElement = document.getElementById('main-database-status');
                const databaseStatusText = document.getElementById('main-database-status-text');
                
                if (databaseStatusElement && databaseStatusText) {
                    const status = databaseStatus.status?.toLowerCase() || 'unknown';
                    if (status === 'healthy') {
                        databaseStatusElement.className = 'status-indicator status-online';
                        databaseStatusText.textContent = 'Connected';
                    } else if (status === 'unhealthy') {
                        databaseStatusElement.className = 'status-indicator status-warning';
                        databaseStatusText.textContent = 'Warning';
                    } else {
                        databaseStatusElement.className = 'status-indicator status-offline';
                        databaseStatusText.textContent = 'Disconnected';
                    }
                }
            }
        }
        
        // Update system information
        if (healthData.system) {
            this.updateSystemInfoFromHealth(healthData.system);
        }
        
        // Add health status log
        AICameraUtils.addLogMessage('main-system-log', 
            `Health check completed: ${healthData.overall_status}`, 
            healthData.overall_status === 'healthy' ? 'success' : 'warning');
    },

    /**
     * Update system information from health data
     */
    updateSystemInfoFromHealth: function(systemData) {
        // Update CPU info
        if (systemData.cpu_info) {
            const cpuElement = document.getElementById('system-info-cpu');
            if (cpuElement) {
                const cpuInfo = systemData.cpu_info;
                cpuElement.textContent = `${cpuInfo.model || 'Unknown'} ${cpuInfo.architecture || ''}`;
            }
        }
        
        // Update AI Accelerator info
        if (systemData.ai_accelerator_info) {
            const aiElement = document.getElementById('system-info-ai-accelerator');
            if (aiElement) {
                const aiInfo = systemData.ai_accelerator_info;
                aiElement.textContent = `Device Architecture: ${aiInfo.device_architecture || 'Unknown'}, Firmware: ${aiInfo.firmware_version || 'Unknown'}`;
            }
        }
        
        // Update OS info
        if (systemData.os_info) {
            const osElement = document.getElementById('system-info-os');
            if (osElement) {
                const osInfo = systemData.os_info;
                osElement.textContent = `${osInfo.distribution || 'Unknown'} ${osInfo.distribution_version || ''} (Kernel ${osInfo.kernel_version || 'Unknown'})`;
            }
        }
        
        // Update RAM info
        if (systemData.memory_usage) {
            const ramElement = document.getElementById('system-info-ram');
            if (ramElement) {
                ramElement.textContent = `${systemData.memory_usage.total?.toFixed(2) || 'Unknown'} GB`;
            }
        }
        
        // Update Disk info
        if (systemData.disk_usage) {
            const diskElement = document.getElementById('system-info-disk');
            if (diskElement) {
                diskElement.textContent = `${systemData.disk_usage.total?.toFixed(2) || 'Unknown'} GB`;
            }
        }
    },

    /**
     * Update system information display
     */
    updateSystemInfo: function(data) {
        console.log('Updating system info with data:', data);
        
        if (!data || !data.success) {
            console.warn('Invalid system info data received');
            return;
        }
        
        // Extract system data from the correct path
        const systemData = data.data && data.data.system ? data.data.system : data.data || data;
        
        // Update CPU info
        if (systemData.cpu_info) {
            const cpuElement = document.getElementById('system-info-cpu');
            if (cpuElement) {
                const cpuInfo = systemData.cpu_info;
                cpuElement.textContent = `${cpuInfo.model || 'Unknown'} ${cpuInfo.architecture || ''}`;
            }
        }
        
        // Update AI Accelerator info
        if (systemData.ai_accelerator_info) {
            const aiElement = document.getElementById('system-info-ai-accelerator');
            if (aiElement) {
                const aiInfo = systemData.ai_accelerator_info;
                aiElement.textContent = `Device Architecture: ${aiInfo.device_architecture || 'Unknown'}, Firmware: ${aiInfo.firmware_version || 'Unknown'}`;
            }
        }
        
        // Update OS info
        if (systemData.os_info) {
            const osElement = document.getElementById('system-info-os');
            if (osElement) {
                const osInfo = systemData.os_info;
                osElement.textContent = `${osInfo.distribution || 'Unknown'} ${osInfo.distribution_version || ''} (Kernel ${osInfo.kernel_version || 'Unknown'})`;
            }
        }
        
        // Update RAM info
        if (systemData.memory_usage) {
            const ramElement = document.getElementById('system-info-ram');
            if (ramElement) {
                ramElement.textContent = `${systemData.memory_usage.total?.toFixed(2) || 'Unknown'} GB`;
            }
        }
        
        // Update Disk info
        if (systemData.disk_usage) {
            const diskElement = document.getElementById('system-info-disk');
            if (diskElement) {
                diskElement.textContent = `${systemData.disk_usage.total?.toFixed(2) || 'Unknown'} GB`;
            }
        }
        
        // Update camera info if available
        if (systemData.camera_info) {
            const cameraModelElement = document.getElementById('feature-camera-model');
            const cameraResolutionElement = document.getElementById('feature-camera-resolution');
            const cameraFpsElement = document.getElementById('feature-camera-fps');
            const cameraStatusElement = document.getElementById('feature-camera-status');
            
            if (cameraModelElement && systemData.camera_info.model) {
                cameraModelElement.textContent = systemData.camera_info.model;
            }
            
            if (cameraResolutionElement && systemData.camera_info.resolution) {
                cameraResolutionElement.textContent = `${systemData.camera_info.resolution[0]}x${systemData.camera_info.resolution[1]}`;
            }
            
            if (cameraFpsElement && systemData.camera_info.framerate) {
                cameraFpsElement.textContent = `${systemData.camera_info.framerate} FPS`;
            }
            
            if (cameraStatusElement && systemData.camera_info.status) {
                cameraStatusElement.textContent = systemData.camera_info.status;
            }
        }
        
        // Update system uptime
        if (systemData.uptime) {
            const uptimeElement = document.getElementById('main-system-uptime');
            if (uptimeElement) {
                const uptime = this.formatUptime(systemData.uptime);
                uptimeElement.textContent = uptime;
            }
        }
    },

    /**
     * Format uptime from seconds to human readable format
     */
    formatUptime: function(seconds) {
        if (!seconds || seconds <= 0) return 'N/A';
        
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        if (days > 0) return `${days}d ${hours}h`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
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
            // Check if in offline mode
            if (status.offline_mode) {
                connected = false;
                connectionText = 'Offline Mode';
                dataActive = status.running && (status.detection_thread_alive || status.health_thread_alive);
                dataText = dataActive ? 'Active (Local)' : 'Inactive';
            } else {
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
     * Update server logs from API
     */
    updateServerLogsFromAPI: function() {
        // Get WebSocket sender logs (optional)
        AICameraUtils.apiRequest('/websocket-sender/logs?limit=10')
            .then(data => {
                if (data.success && data.logs) {
                    this.updateServerLogs(data.logs);
                }
            })
            .catch(error => {
                console.log('WebSocket sender logs not available (optional module)');
                // Show message that logs are not available
                const logsContainer = document.getElementById('main-server-logs');
                if (logsContainer) {
                    logsContainer.innerHTML = '<div class="text-muted p-3">WebSocket sender not available (optional module)</div>';
                }
            });
    },

    /**
     * Update server logs display
     */
    updateServerLogs: function(logs) {
        const logsContainer = document.getElementById('main-server-logs');
        if (!logsContainer) {
            console.warn('Server logs container not found');
            return;
        }

        // Clear existing logs
        logsContainer.innerHTML = '';

        if (!logs || logs.length === 0) {
            logsContainer.innerHTML = '<div class="text-muted p-3">No server logs available...</div>';
            return;
        }

        // Add log entries
        logs.forEach(log => {
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            
            const timestamp = new Date(log.timestamp).toLocaleTimeString();
            const statusClass = log.status === 'success' ? 'log-success' : 
                              log.status === 'error' ? 'log-error' : 'log-info';
            
            logEntry.innerHTML = `
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-status ${statusClass}">${log.status}</span>
                <span class="log-message">${log.message}</span>
            `;
            
            logsContainer.appendChild(logEntry);
        });

        // Scroll to bottom
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
