/**
 * AI Camera v1.3 - Camera Dashboard JavaScript
 * Camera control and monitoring functionality
 */

// Camera dashboard state management
const CameraManager = {
    socket: null,
    
    /**
     * Initialize camera dashboard
     */
    init: function() {
        this.initializeWebSocket();
        this.setupEventHandlers();
        this.setupFormHandlers();
        console.log('Camera Manager initialized');
    },

    /**
     * Initialize WebSocket connection for camera namespace
     */
    initializeWebSocket: function() {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not available');
            return;
        }

        this.socket = io('/camera');
        this.setupSocketHandlers();
    },

    /**
     * Setup WebSocket event handlers
     */
    setupSocketHandlers: function() {
        if (!this.socket) return;

        this.socket.on('connect', () => {
            console.log('Connected to camera service');
            AICameraUtils.addLogMessage('log-container', 'Connected to camera service', 'success');
            this.socket.emit('camera_status_request');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from camera service');
            AICameraUtils.addLogMessage('log-container', 'Disconnected from camera service', 'error');
        });

        this.socket.on('camera_status_update', (status) => {
            this.updateCameraStatus(status);
            if (status.config) {
                this.updateConfigForm(status.config);
            }
        });

        this.socket.on('camera_control_response', (response) => {
            this.handleControlResponse(response);
        });

        this.socket.on('camera_config_response', (response) => {
            this.handleConfigResponse(response);
        });
    },

    /**
     * Setup event handlers for control buttons
     */
    setupEventHandlers: function() {
        // Control buttons
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        const restartBtn = document.getElementById('restart-btn');
        const captureBtn = document.getElementById('capture-btn');

        if (startBtn) startBtn.addEventListener('click', () => this.sendCommand('start'));
        if (stopBtn) stopBtn.addEventListener('click', () => this.sendCommand('stop'));
        if (restartBtn) restartBtn.addEventListener('click', () => this.sendCommand('restart'));
        if (captureBtn) captureBtn.addEventListener('click', () => this.sendCommand('capture'));

        // Video feed error handling
        const videoFeed = document.getElementById('video-feed');
        if (videoFeed) {
            videoFeed.addEventListener('error', () => {
                AICameraUtils.addLogMessage('log-container', 'Video feed error - camera may be offline', 'error');
            });

            videoFeed.addEventListener('load', () => {
                AICameraUtils.addLogMessage('log-container', 'Video feed loaded successfully', 'success');
            });
        }
    },

    /**
     * Setup form handlers for configuration
     */
    setupFormHandlers: function() {
        // Configuration form
        const configForm = document.getElementById('config-form');
        if (configForm) {
            configForm.addEventListener('submit', (e) => this.handleConfigSubmit(e));
        }

        // Range sliders
        this.setupRangeSliders();
    },

    /**
     * Setup range sliders with live updates
     */
    setupRangeSliders: function() {
        const sliders = [
            { slider: 'framerate', display: 'framerate-value' },
            { slider: 'brightness', display: 'brightness-value' },
            { slider: 'contrast', display: 'contrast-value' },
            { slider: 'saturation', display: 'saturation-value' }
        ];

        sliders.forEach(({ slider, display }) => {
            const sliderElement = document.getElementById(slider);
            const displayElement = document.getElementById(display);
            
            if (sliderElement && displayElement) {
                sliderElement.addEventListener('input', () => {
                    displayElement.textContent = sliderElement.value;
                });
            }
        });
    },

    /**
     * Send camera command
     */
    sendCommand: function(command) {
        if (!this.socket || !this.socket.connected) {
            AICameraUtils.showToast('Not connected to camera service', 'warning');
            return;
        }

        this.socket.emit('camera_control', { command: command });
        AICameraUtils.addLogMessage('log-container', `Sending ${command} command...`, 'info');
    },

    /**
     * Handle control response
     */
    handleControlResponse: function(response) {
        const message = response.success ? 
            (response.message || 'Command executed successfully') :
            (response.error || response.message || 'Command failed');
        
        AICameraUtils.addLogMessage('log-container', `Camera control: ${message}`, 
            response.success ? 'success' : 'error');
        
        if (response.success) {
            AICameraUtils.showToast(message, 'success');
        } else {
            AICameraUtils.showToast(message, 'error');
        }
    },

    /**
     * Handle configuration response
     */
    handleConfigResponse: function(response) {
        const message = response.success ? 
            (response.message || 'Configuration updated successfully') :
            (response.error || 'Configuration update failed');
        
        AICameraUtils.addLogMessage('log-container', `Configuration: ${message}`, 
            response.success ? 'success' : 'error');
        
        AICameraUtils.showToast(message, response.success ? 'success' : 'error');
    },

    /**
     * Update camera status display
     */
    updateCameraStatus: function(status) {
        // Update status indicator
        let statusClass = 'status-offline';
        let statusText = 'Offline';

        if (status.streaming) {
            statusClass = 'status-online';
            statusText = 'Online';
        } else if (status.initialized) {
            statusClass = 'status-warning';
            statusText = 'Ready';
        }

        const statusIndicator = document.getElementById('camera-status');
        const statusTextElement = document.getElementById('camera-status-text');
        
        if (statusIndicator) statusIndicator.className = `status-indicator ${statusClass}`;
        if (statusTextElement) statusTextElement.textContent = statusText;

        // Update detailed status content
        this.updateStatusContent(status);
    },

    /**
     * Update detailed status content
     */
    updateStatusContent: function(status) {
        const statusContent = document.getElementById('status-content');
        if (!statusContent) return;

        // Extract metadata information
        const metadata = status.metadata || {};
        const cameraProps = metadata.camera_properties || {};
        const currentConfig = metadata.current_config || {};
        const mainConfig = currentConfig.main || {};
        
        // Get resolution from metadata
        let resolution = 'Unknown';
        if (mainConfig.size && Array.isArray(mainConfig.size)) {
            resolution = `${mainConfig.size[0]}x${mainConfig.size[1]}`;
        } else if (status.config && status.config.resolution) {
            resolution = `${status.config.resolution[0]}x${status.config.resolution[1]}`;
        }
        
        // Get sensor model from metadata
        let sensorModel = 'Unknown';
        if (cameraProps && cameraProps.Model) {
            sensorModel = cameraProps.Model;
        }
        
        // Get framerate from metadata
        let framerate = 'Unknown';
        if (mainConfig.controls && mainConfig.controls.FrameDurationLimits) {
            const frameDuration = mainConfig.controls.FrameDurationLimits[0];
            framerate = `${Math.round(1000000 / frameDuration)} FPS`;
        } else if (status.config && status.config.framerate) {
            framerate = `${status.config.framerate} FPS`;
        }

        const statusHtml = `
            <div class="row">
                <div class="col-6">
                    <small class="text-muted">Initialized:</small><br>
                    <strong>${status.initialized ? 'Yes' : 'No'}</strong>
                </div>
                <div class="col-6">
                    <small class="text-muted">Streaming:</small><br>
                    <strong>${status.streaming ? 'Yes' : 'No'}</strong>
                </div>
            </div>
            <hr>
            <div class="row">
                <div class="col-6">
                    <small class="text-muted">Resolution:</small><br>
                    <strong>${resolution}</strong>
                </div>
                <div class="col-6">
                    <small class="text-muted">Frame Rate:</small><br>
                    <strong>${framerate}</strong>
                </div>
            </div>
            ${status.uptime ? `
                <hr>
                <div class="row">
                    <div class="col-12">
                        <small class="text-muted">Uptime:</small><br>
                        <strong>${AICameraUtils.formatDuration(status.uptime)}</strong>
                    </div>
                </div>
            ` : ''}
            ${sensorModel !== 'Unknown' ? `
                <hr>
                <div class="row">
                    <div class="col-12">
                        <small class="text-muted">Sensor Model:</small><br>
                        <strong>${sensorModel}</strong>
                    </div>
                </div>
            ` : ''}
        `;
        
        statusContent.innerHTML = statusHtml;
    },

    /**
     * Update configuration form with current values
     */
    updateConfigForm: function(config) {
        if (config.resolution) {
            const resolutionSelect = document.getElementById('resolution');
            if (resolutionSelect) {
                resolutionSelect.value = `(${config.resolution[0]}, ${config.resolution[1]})`;
            }
        }

        const configMappings = [
            { key: 'framerate', elementId: 'framerate', displayId: 'framerate-value' },
            { key: 'brightness', elementId: 'brightness', displayId: 'brightness-value' },
            { key: 'contrast', elementId: 'contrast', displayId: 'contrast-value' },
            { key: 'saturation', elementId: 'saturation', displayId: 'saturation-value' },
            { key: 'awb_mode', elementId: 'awb_mode' }
        ];

        configMappings.forEach(({ key, elementId, displayId }) => {
            if (config[key] !== undefined) {
                const element = document.getElementById(elementId);
                if (element) {
                    element.value = config[key];
                    
                    if (displayId) {
                        const displayElement = document.getElementById(displayId);
                        if (displayElement) {
                            displayElement.textContent = config[key];
                        }
                    }
                }
            }
        });
    },

    /**
     * Handle configuration form submission
     */
    handleConfigSubmit: function(e) {
        e.preventDefault();
        
        if (!this.socket || !this.socket.connected) {
            AICameraUtils.showToast('Not connected to camera service', 'warning');
            return;
        }

        const formData = new FormData(e.target);
        const config = {};
        
        for (let [key, value] of formData.entries()) {
            if (key === 'resolution') {
                // Parse resolution string
                const match = value.match(/\((\d+),\s*(\d+)\)/);
                if (match) {
                    config.resolution = [parseInt(match[1]), parseInt(match[2])];
                }
            } else if (['framerate', 'brightness', 'contrast', 'saturation'].includes(key)) {
                config[key] = parseFloat(value);
            } else {
                config[key] = value;
            }
        }
        
        this.socket.emit('camera_config_update', { config: config });
        AICameraUtils.addLogMessage('log-container', 'Updating camera configuration...', 'info');
    },

    /**
     * Request status update
     */
    requestStatusUpdate: function() {
        if (this.socket && this.socket.connected) {
            this.socket.emit('camera_status_request');
        } else {
            // Fallback to HTTP API if WebSocket not available
            this.requestStatusViaHTTP();
        }
    },

    /**
     * Request status via HTTP API (fallback)
     */
    requestStatusViaHTTP: function() {
        AICameraUtils.apiRequest('/camera/status')
            .then(data => {
                if (data && data.success) {
                    this.updateCameraStatus(data.status);
                    if (data.status.config) {
                        this.updateConfigForm(data.status.config);
                    }
                }
            })
            .catch(error => {
                console.warn('Camera status not available:', error.message);
                AICameraUtils.addLogMessage('log-container', 'Camera service not available', 'warning');
                // Set default offline status
                this.updateCameraStatus({streaming: false, initialized: false});
            });
    }
};

// Initialize camera manager when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    CameraManager.init();
    
    // Initial log message
    AICameraUtils.addLogMessage('log-container', 'Camera dashboard loaded', 'info');
    AICameraUtils.addLogMessage('log-container', 'Connecting to camera service...', 'info');
    
    // Request initial status after a short delay
    setTimeout(() => {
        CameraManager.requestStatusUpdate();
    }, 1000);
    
    console.log('Camera Dashboard JavaScript loaded');
});
