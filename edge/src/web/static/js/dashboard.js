/**
 * AI Camera v2.0 - Dashboard JavaScript
 * 
 * Main dashboard specific functionality.
 * 
 * @author AI Camera Team
 * @version 2.0
 * @since 2025-08-23
 */

// Dashboard state management
const DashboardManager = {
    statusUpdateInterval: null,
    socket: null,
    lastCameraStatus: null, // Track last camera status to prevent conflicts
    
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
        
        // Always show server communication sections
        this.showServerCommunicationSections();
        
        // Set up core status updates with immediate loading
        this.updateSystemStatusComprehensive();
        
        // Set up core event handlers
        this.setupCoreEventHandlers();
        
        // Force immediate detection status update for instant display
        setTimeout(() => {
            this.updateDetectionStatusFromAPI();
        }, 100);
    },

    /**
     * Initialize WebSocket connection for core dashboard functionality
     */
    initWebSocket: function() {
        console.log('Initializing WebSocket connection for dashboard...');
        
        // Check if WebSocket is configured/enabled
        // If running in offline mode or WebSocket not configured, skip gracefully
        if (typeof io === 'undefined') {
            console.log('WebSocket not available - running in offline mode with polling updates');
            return;
        }
        
        // Try to establish WebSocket connection
        try {
            this.socket = io('/dashboard');
            this.setupDashboardSocketHandlers();
        } catch (error) {
            console.log('WebSocket connection failed - running in offline mode:', error.message);
            // Continue with polling-based updates
        }
    },

    /**
     * Setup WebSocket event handlers for dashboard
     */
    setupDashboardSocketHandlers: function() {
        if (!this.socket) return;

        this.socket.on('connect', () => {
            console.log('Connected to dashboard WebSocket service');
            this.joinDashboardRoom();
        });

        this.socket.on('dashboard_status_update', (status) => {
            this.updateSystemStatusComprehensive();
        });

        this.socket.on('dashboard_alert', (alert) => {
            AICameraUtils.showToast(alert.message, alert.type || 'info');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from dashboard WebSocket service - continuing with polling');
        });

        this.socket.on('connect_error', (error) => {
            console.log('WebSocket connection error - running in offline mode with polling');
        });
    },

    /**
     * Join dashboard WebSocket room for updates
     */
    joinDashboardRoom: function() {
        if (this.socket) {
            this.socket.emit('join_dashboard_room');
        }
    },

    /**
     * Check and initialize optional modules (DEPRECATED - using individual service updates)
     */
    checkOptionalModules: function() {
        console.log('checkOptionalModules is deprecated - using individual service updates instead');
        // This function is deprecated to prevent conflicts with individual service updates
    },

    /**
     * Check if WebSocket Sender is available (DEPRECATED)
     */
    checkWebSocketSender: function() {
        console.log('checkWebSocketSender is deprecated - using updateWebSocketSenderStatus instead');
    },

    /**
     * Check if Storage Manager is available (DEPRECATED)
     */
    checkStorageManager: function() {
        console.log('checkStorageManager is deprecated - using updateStorageStatusFromAPI instead');
    },

    /**
     * Check if Health Monitor is available (DEPRECATED)
     */
    checkHealthMonitor: function() {
        console.log('checkHealthMonitor is deprecated - using updateHealthStatus instead');
    },

    /**
     * Check if Experiments is available (DEPRECATED)
     */
    checkExperiments: function() {
        console.log('checkExperiments is deprecated - using updateExperimentsStatusFromAPI instead');
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
     * Always show server communication sections
     */
    showServerCommunicationSections: function() {
        const serverCommSection = document.getElementById('server-communication-section');
        const serverLogsSection = document.getElementById('server-logs-section');
        if (serverCommSection) serverCommSection.style.display = 'block';
        if (serverLogsSection) serverLogsSection.style.display = 'block';
    },

    /**
     * Update optional service status in hero section
     */
    updateOptionalServiceStatus: function(serviceName, status, text) {
        const statusElement = document.getElementById(`main-${serviceName}-status`);
        const statusText = document.getElementById(`main-${serviceName}-status-text`);
        
        if (statusElement && statusText) {
            // Remove all status classes
            statusElement.className = 'status-indicator';
            
            // Add appropriate status class
            if (status === 'online') {
                statusElement.classList.add('status-online');
            } else if (status === 'offline') {
                statusElement.classList.add('status-offline');
            } else if (status === 'warning') {
                statusElement.classList.add('status-warning');
            }
            
            statusText.textContent = text;
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
        // Update streaming status (if available) - CORE MODULE
        this.updateStreamingStatus();
    },

    /**
     * Set up periodic updates - OPTIMIZED for reduced resource usage
     */
    setupPeriodicUpdates: function() {
        // Update core status every 60 seconds (increased from 10 seconds for reduced resource usage)
        setInterval(() => {
            this.updateSystemStatusComprehensive();
        }, 60000);
        
        // Update detection status more frequently (every 10 seconds) for real-time display
        setInterval(() => {
            this.updateDetectionStatusFromAPI();
        }, 60000);
        
        // Update system info every 300 seconds (increased from 60 seconds for reduced resource usage)
        setInterval(() => {
            this.updateSystemInfoFromAPI();
        }, 300000);
    },

    /**
     * Update system info from API (FIXED - was missing)
     */
    updateSystemInfoFromAPI: function() {
        // Only update if system info section exists
        const systemInfoSection = document.getElementById('system-info-section');
        if (!systemInfoSection) {
            return;
        }
        
        AICameraUtils.apiRequest('/system/info')
            .then(data => {
                if (data && data.success) {
                    this.updateSystemInfoDisplay(data.info);
                }
            })
            .catch(error => {
                console.log('System info update failed (optional):', error.message);
                // Don't show error for optional system info updates
            });
    },

    /**
     * Update system info display
     */
    updateSystemInfoDisplay: function(info) {
        if (!info) return;
        
        // Update system info elements if they exist
        const elements = {
            'system-uptime': info.uptime,
            'system-load': info.load_average,
            'system-memory': info.memory_usage,
            'system-cpu': info.cpu_usage,
            'system-temperature': info.temperature
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element && value !== undefined) {
                element.textContent = value;
            }
        });
    },

    /**
     * Setup WebSocket connection for real-time updates (DEPRECATED - using initWebSocket instead)
     */
    setupWebSocket: function() {
        console.log('setupWebSocket is deprecated - using initWebSocket instead');
        // This function is deprecated to prevent conflicts with initWebSocket
    },

    /**
     * Setup periodic status updates (DEPRECATED - using setupPeriodicUpdates instead)
     */
    setupStatusUpdates: function() {
        console.log('setupStatusUpdates is deprecated - using setupPeriodicUpdates instead');
        // This function is deprecated to prevent conflicts with setupPeriodicUpdates
    },

    /**
     * Load initial system status (DEPRECATED - using updateSystemStatusComprehensive instead)
     */
    loadInitialStatus: function() {
        console.log('loadInitialStatus is deprecated - using updateSystemStatusComprehensive instead');
        // This function is deprecated to prevent conflicts with updateSystemStatusComprehensive
    },

    /**
     * Update system status (DEPRECATED - using updateSystemStatusComprehensive instead)
     */
    updateSystemStatus: function() {
        console.log('updateSystemStatus is deprecated - using updateSystemStatusComprehensive instead');
        // This function is deprecated to prevent conflicts with updateSystemStatusComprehensive
    },

    /**
     * Update server connection status
     */
    /**
     * Update Server Connection card from WebSocket (Socket.IO) status only.
     */
    updateServerConnectionStatus: function() {
        AICameraUtils.apiRequest('/websocket-sender/status')
            .then(data => {
                if (data.success) {
                    const status = data.status;
                    const connectionElement = document.getElementById('main-server-connection-status');
                    const connectionText = document.getElementById('main-server-connection-text');
                    const lastSyncElement = document.getElementById('main-last-sync-time');
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
                const connectionElement = document.getElementById('main-server-connection-status');
                const connectionText = document.getElementById('main-server-connection-text');
                if (connectionElement && connectionText) {
                    connectionElement.className = 'status-indicator status-offline';
                    connectionText.textContent = 'Error';
                }
            });
    },

    /**
     * Update Data Sending card from MQTT service status only.
     */
    updateMqttStatus: function() {
        AICameraUtils.apiRequest('/mqtt-service/status')
            .then(data => {
                if (data && data.success && data.status) {
                    const status = data.status;
                    const el = document.getElementById('main-data-sending-status');
                    const textEl = document.getElementById('main-data-sending-text');
                    if (el && textEl) {
                        if (status.connected && status.running) {
                            el.className = 'status-indicator status-online';
                            textEl.textContent = status.total_health_sent > 0 ? 'Active' : 'Connected';
                        } else if (status.running) {
                            el.className = 'status-indicator status-warning';
                            textEl.textContent = 'Connecting';
                        } else if (status.enabled) {
                            el.className = 'status-indicator status-offline';
                            textEl.textContent = 'Inactive';
                        } else {
                            el.className = 'status-indicator status-offline';
                            textEl.textContent = 'Disabled';
                        }
                    }
                }
            })
            .catch(error => {
                console.log('MQTT service not available (optional):', error.message);
                const el = document.getElementById('main-data-sending-status');
                const textEl = document.getElementById('main-data-sending-text');
                if (el && textEl) {
                    el.className = 'status-indicator status-offline';
                    textEl.textContent = 'Unavailable';
                }
            });
    },
    /**
     * Update camera status from API
     */
    updateCameraStatusFromAPI: function() {
        console.log('Updating camera status from API...');
        
        AICameraUtils.apiRequest('/camera/status')
            .then(data => {
                if (data.success) {
                    this.updateCameraStatus(data.status);
                } else {
                    console.log('Camera status not available');
                    // Update camera status to show offline
                    this.clearCameraStatus();
                }
            })
            .catch(error => {
                console.log('Failed to fetch camera status:', error.message);
                // Update camera status to show offline
                this.clearCameraStatus();
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
                }
            })
            .catch(error => {
                console.log('Health service not available - running in offline mode:', error.message);
                // Update system status to show offline mode instead of error
                const systemStatusElement = document.getElementById('main-system-status');
                const systemStatusText = document.getElementById('main-system-status-text');
                if (systemStatusElement && systemStatusText) {
                    systemStatusElement.className = 'status-indicator status-warning';
                    systemStatusText.textContent = 'Offline Mode';
                }
            });

        // Update camera status - CORE MODULE (Camera Service)
        this.updateCameraStatusFromAPI();

        // Update detection status - CORE MODULE (Detection Service)
        this.updateDetectionStatusFromAPI();

        // === OPTIONAL MODULES (Conditionally Available) ===
        // Update WebSocket sender status - Server Connection card (WebSocket only)
        this.updateWebSocketSenderStatus();

        // Update MQTT service status - Data Sending card (MQTT only)
        this.updateMqttStatus();

        // Update storage status - OPTIONAL MODULE (Storage Service)
        this.updateStorageStatusFromAPI();

        // Update experiments status - OPTIONAL MODULE (Experiments Service)
        this.updateExperimentsStatusFromAPI();

        // Update server logs - OPTIONAL MODULE (WebSocket Service)
        this.updateServerLogsFromAPI();
    },

    /**
     * Update detection status from API (Detection Service)
     */
    updateDetectionStatusFromAPI: function() {
        console.log('Updating detection status from API...');
        
        AICameraUtils.apiRequest('/detection/status')
            .then(data => {
                if (data.success) {
                    this.updateDetectionStatus(data.detection_status);
                } else {
                    console.log('Detection status not available');
                    const detectionStatusElement = document.getElementById('main-detection-status');
                    const detectionStatusText = document.getElementById('main-detection-status-text');
                    if (detectionStatusElement && detectionStatusText) {
                        detectionStatusElement.className = 'status-indicator status-offline';
                        detectionStatusText.textContent = 'Inactive';
                    }
                }
            })
            .catch(error => {
                console.log('Failed to fetch detection status:', error.message);
                const detectionStatusElement = document.getElementById('main-detection-status');
                const detectionStatusText = document.getElementById('main-detection-status-text');
                if (detectionStatusElement && detectionStatusText) {
                    detectionStatusElement.className = 'status-indicator status-offline';
                    detectionStatusText.textContent = 'Inactive';
                }
            });
    },

    /**
     * Update storage status from API (Storage Service)
     */
    updateStorageStatusFromAPI: function() {
        console.log('Updating storage status from API...');
        
        AICameraUtils.apiRequest('/storage/status')
            .then(data => {
                if (data.success) {
                    this.updateOptionalServiceStatus('storage', 'online', 'Available');
                } else {
                    console.log('Storage service not available (optional module)');
                    this.updateOptionalServiceStatus('storage', 'offline', 'Offline');
                }
            })
            .catch(error => {
                console.log('Storage service not available (optional module):', error.message);
                this.updateOptionalServiceStatus('storage', 'offline', 'Offline');
            });
    },

    /**
     * Update experiments status from API (Experiments Service)
     */
    updateExperimentsStatusFromAPI: function() {
        // Check if experiments section exists before making API call
        const experimentsSection = document.getElementById('experiments-section');
        if (!experimentsSection) {
            return;
        }
        
        console.log('Updating experiments status from API...');
        
        AICameraUtils.apiRequest('/experiments/status')
            .then(data => {
                if (data.success) {
                    this.updateOptionalServiceStatus('experiment', 'online', 'Available');
                } else {
                    console.log('Experiments service not available (optional module)');
                    this.updateOptionalServiceStatus('experiment', 'offline', 'Offline');
                }
            })
            .catch(error => {
                // Handle 404 gracefully - experiments service is optional
                if (error.message && error.message.includes('404')) {
                    console.log('Experiments service not available (optional module):', error.message);
                    // Hide experiments section if service is not available
                    if (experimentsSection) {
                        experimentsSection.style.display = 'none';
                    }
                } else {
                    console.log('Experiments service not available (optional module):', error.message);
                    this.updateOptionalServiceStatus('experiment', 'offline', 'Offline');
                }
            });
    },

    /**
     * Update WebSocket sender status (WebSocket Service)
     */
    updateWebSocketSenderStatus: function() {
        console.log('Updating WebSocket sender status...');
        
        AICameraUtils.apiRequest('/websocket-sender/status')
            .then(data => {
                if (data.success) {
                    this.updateOptionalServiceStatus('websocket', 'online', 'Available');
                    this.updateServerConnectionDisplay(data.status);
                } else {
                    console.log('WebSocket sender not available (optional module)');
                    this.updateOptionalServiceStatus('websocket', 'offline', 'Offline');
                }
            })
            .catch(error => {
                console.log('WebSocket sender not available (optional module):', error.message);
                this.updateOptionalServiceStatus('websocket', 'offline', 'Offline');
            });
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
                        connectionText.textContent = 'Disconnected';
                    } else {
                        connectionElement.className = 'status-indicator status-offline';
                        connectionText.textContent = 'Not Running';
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
            let logMessage = '';
            if (status.connected) {
                logMessage = 'WebSocket sender connected to server';
            } else if (status.offline_mode) {
                logMessage = 'WebSocket sender in offline mode';
            } else if (status.running) {
                logMessage = 'WebSocket sender running but disconnected from server';
            } else {
                logMessage = 'WebSocket sender not running';
            }
            
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
     * Update streaming status (DEPRECATED - handled by camera service)
     */
    updateStreamingStatus: function() {
        console.log('updateStreamingStatus is deprecated - handled by camera service');
        // This function is deprecated - streaming status is now handled by camera service
    },

    /**
     * Check if camera status is available and valid
     */
    isCameraStatusAvailable: function() {
        return this.lastCameraStatus !== null && this.lastCameraStatus !== undefined;
    },

    /**
     * Clear camera status when camera is not available
     */
    clearCameraStatus: function() {
        this.lastCameraStatus = null;
        AICameraUtils.updateStatusIndicator('main-camera-status', false, 'Offline');
    },

    /**
     * Update camera status display
     */
    updateCameraStatus: function(status) {
        console.log('updateCameraStatus called with:', status);
        
        // Store the last camera status to prevent health status from overriding
        this.lastCameraStatus = status;
        
        let cameraOnline = false;
        let statusText = 'Offline';

        if (status && status.streaming) {
            cameraOnline = true;
            statusText = 'Online';
            AICameraUtils.addLogMessage('main-system-log', 'Camera is streaming', 'success');
        } else if (status && status.initialized) {
            statusText = 'Ready';
            AICameraUtils.addLogMessage('main-system-log', 'Camera initialized but not streaming', 'info');
        } else if (status && status.error) {
            statusText = 'Error';
            AICameraUtils.addLogMessage('main-system-log', `Camera error: ${status.error}`, 'warning');
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
        console.log('Updating detection status with:', status);
        
        // Check if detection service is running
        const detectionActive = status && status.service_running || false;
        
        // Check if models are loaded
        const processorStatus = status.detection_processor_status || {};
        const modelsLoaded = processorStatus.models_loaded || false;
        
        // Determine overall detection status
        let statusText = 'Inactive';
        let statusClass = 'status-offline';
        
        if (detectionActive && modelsLoaded) {
            statusText = 'Active';
            statusClass = 'status-online';
        } else if (detectionActive && !modelsLoaded) {
            statusText = 'Warning';
            statusClass = 'status-warning';
        } else {
            statusText = 'Inactive';
            statusClass = 'status-offline';
        }
        
        // Update the status indicator
        const detectionStatusElement = document.getElementById('main-detection-status');
        const detectionStatusText = document.getElementById('main-detection-status-text');
        
        if (detectionStatusElement && detectionStatusText) {
            detectionStatusElement.className = `status-indicator ${statusClass}`;
            detectionStatusText.textContent = statusText;
        }
        
        // Add log message for detection status
        if (detectionActive && modelsLoaded) {
            AICameraUtils.addLogMessage('main-system-log', 'AI Detection service is running with models loaded', 'success');
        } else if (detectionActive && !modelsLoaded) {
            AICameraUtils.addLogMessage('main-system-log', 'AI Detection service is running but models not loaded', 'warning');
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
        
        // Update health monitor status in hero section
        this.updateHealthMonitorStatus(healthData);
        
        // Update component statuses
        if (healthData.components) {
            // Camera status - Only update if we don't have more specific camera data
            // This prevents health status from overriding detailed camera status
            if (healthData.components.camera && !this.isCameraStatusAvailable()) {
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
            
            // Detection status - REMOVED: Now handled by direct API call in updateDetectionStatusFromAPI()
            // This prevents health monitoring from overriding real-time detection status
            
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
     * Update health monitor status in hero section
     */
    updateHealthMonitorStatus: function(healthData) {
        const healthStatusElement = document.getElementById('main-health-status');
        const healthStatusText = document.getElementById('main-health-status-text');
        const healthStatusDetail = document.getElementById('main-health-status-text-detail');
        
        if (healthStatusElement && healthStatusText && healthStatusDetail) {
            const overallStatus = healthData.overall_status?.toLowerCase() || 'unknown';
            
            // Update status indicator
            if (overallStatus === 'healthy') {
                healthStatusElement.className = 'status-indicator status-online';
                healthStatusText.textContent = 'Online';
                healthStatusDetail.textContent = 'ตรวจสอบทุก 60 วินาที';
            } else if (overallStatus === 'unhealthy') {
                healthStatusElement.className = 'status-indicator status-warning';
                healthStatusText.textContent = 'Warning';
                this.updateHealthStatusDetail(healthData, healthStatusDetail);
            } else if (overallStatus === 'unknown' || !healthData.overall_status) {
                // Show checking status when status is unknown or not yet loaded
                healthStatusElement.className = 'status-indicator status-checking';
                healthStatusText.textContent = 'Checking';
                healthStatusDetail.textContent = 'กำลังตรวจสอบสถานะ...';
            } else {
                healthStatusElement.className = 'status-indicator status-offline';
                healthStatusText.textContent = 'Offline';
                this.updateHealthStatusDetail(healthData, healthStatusDetail);
            }
        }
    },

    /**
     * Update health status detail text based on status and components
     */
    updateHealthStatusDetail: function(healthData, healthStatusDetail) {
        let detailText = 'Not Running';
        
        if (healthData.components) {
            const components = healthData.components;
            
            // Check camera issues (highest priority)
            if (components.camera && components.camera.status !== 'healthy') {
                if (!components.camera.initialized) {
                    detailText = 'Camera not initialized';
                } else if (!components.camera.streaming) {
                    detailText = 'Camera not streaming';
                }
            }
            // Check detection issues
            else if (components.detection && components.detection.status !== 'healthy') {
                if (!components.detection.models_loaded) {
                    detailText = 'AI models not loaded';
                } else if (!components.detection.detection_active) {
                    detailText = 'Detection not active';
                }
            }
            // Check database issues
            else if (components.database && components.database.status !== 'healthy') {
                if (!components.database.connected) {
                    detailText = 'Database disconnected';
                }
            }
            // Check system issues
            else if (components.system && components.system.status !== 'healthy') {
                detailText = 'System resources critical';
            }
            // If all components seem healthy but overall status is not
            else if (healthData.overall_status && healthData.overall_status.toLowerCase() !== 'healthy') {
                detailText = 'Service unavailable';
            }
        }
        
        healthStatusDetail.textContent = detailText;
    },

    /**
     * Add reason for health monitor offline status (DEPRECATED - replaced by updateHealthStatusDetail)
     */
    addHealthOfflineReason: function(healthData) {
        // This function is deprecated in favor of updateHealthStatusDetail
        // Keeping for backward compatibility but no longer used
        console.log('addHealthOfflineReason is deprecated - using updateHealthStatusDetail instead');
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
    /**
     * Update Server Connection and Last Sync display from WebSocket status only (Data Sending is from MQTT).
     */
    updateServerConnectionDisplay: function(status) {
        let connected = false;
        let connectionText = 'Not Running';
        let lastSync = 'Never';

        if (status) {
            if (status.offline_mode) {
                connected = false;
                connectionText = 'Offline Mode';
            } else {
                if (status.connected) {
                    connected = true;
                    connectionText = 'Connected';
                } else if (status.running) {
                    connected = false;
                    connectionText = 'Disconnected';
                } else {
                    connected = false;
                    connectionText = 'Not Running';
                }
            }
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

        AICameraUtils.updateStatusIndicator('main-server-connection-status', connected, connectionText);
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
        
        // Cleanup WebSocket connection (if exists)
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
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
