/**
 * AI Camera v1.3 - Detection Dashboard JavaScript
 * Detection control and monitoring functionality
 */

// Detection dashboard state management
const DetectionManager = {
    socket: null,
    statusUpdateInterval: null,
    detectionRunning: false,
    lastStatusUpdate: null,
    
    /**
     * Initialize detection dashboard
     */
    init: function() {
        this.initializeWebSocket();
        this.setupEventHandlers();
        this.setupFormHandlers();
        this.startPeriodicUpdates();
        console.log('Detection Manager initialized');
    },

    /**
     * Initialize WebSocket connection
     */
    initializeWebSocket: function() {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not available');
            return;
        }

        this.socket = io();
        this.setupSocketHandlers();
    },

    /**
     * Setup WebSocket event handlers
     */
    setupSocketHandlers: function() {
        if (!this.socket) return;

        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.addLogMessage('Connected to server', 'info');
            this.socket.emit('join_detection_room');
            this.requestStatusUpdate();
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.addLogMessage('Disconnected from server', 'warning');
        });

        this.socket.on('detection_status_update', (status) => {
            this.updateDetectionStatus(status);
        });

        this.socket.on('detection_control_response', (response) => {
            this.handleControlResponse(response);
        });

        this.socket.on('detection_statistics_update', (stats) => {
            this.updateStatistics(stats);
        });

        this.socket.on('detection_status_error', (error) => {
            this.addLogMessage('Status error: ' + error.error, 'error');
        });
    },

    /**
     * Setup event handlers
     */
    setupEventHandlers: function() {
        // Control buttons
        const startBtn = document.getElementById('start-detection');
        const stopBtn = document.getElementById('stop-detection');
        const processBtn = document.getElementById('process-frame');

        if (startBtn) startBtn.addEventListener('click', () => this.controlDetection('start'));
        if (stopBtn) stopBtn.addEventListener('click', () => this.controlDetection('stop'));
        if (processBtn) processBtn.addEventListener('click', () => this.processFrame());

        // Refresh button for recent results
        const refreshBtn = document.getElementById('refresh-results-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadRecentResults());
        }
    },

    /**
     * Setup form handlers
     */
    setupFormHandlers: function() {
        const configForm = document.getElementById('detection-config-form');
        if (configForm) {
            configForm.addEventListener('submit', (e) => this.handleConfigSubmit(e));
        }
    },

    /**
     * Start periodic status updates
     */
    startPeriodicUpdates: function() {
        // Update immediately
        this.requestStatusUpdate();
        
        // Setup periodic updates every 5 seconds
        this.statusUpdateInterval = setInterval(() => {
            this.requestStatusUpdate();
        }, 5000);
        
        // Load recent results after 1 second
        setTimeout(() => this.loadRecentResults(), 1000);
        
        // Add initial log message
        this.addLogMessage('Detection dashboard initialized', 'info');
        this.addLogMessage('Connecting to detection service...', 'info');
    },

    /**
     * Control detection service
     */
    controlDetection: function(command) {
        const button = document.getElementById(command === 'start' ? 'start-detection' : 'stop-detection');
        if (button) button.disabled = true;
        
        if (!this.socket || !this.socket.connected) {
            AICameraUtils.showToast('Not connected to server', 'warning');
            if (button) button.disabled = false;
            return;
        }
        
        this.socket.emit('detection_control', { command: command });
        this.addLogMessage(`Sending ${command} command...`, 'info');
    },

    /**
     * Process single frame
     */
    processFrame: function() {
        const button = document.getElementById('process-frame');
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        }
        
        if (!this.socket || !this.socket.connected) {
            AICameraUtils.showToast('Not connected to server', 'warning');
            this.resetProcessButton();
            return;
        }
        
        this.socket.emit('detection_control', { command: 'process_frame' });
        this.addLogMessage('Processing single frame...', 'info');
        
        setTimeout(() => this.resetProcessButton(), 3000);
    },

    /**
     * Reset process frame button
     */
    resetProcessButton: function() {
        const button = document.getElementById('process-frame');
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-camera"></i> Process Frame';
        }
    },

    /**
     * Handle control response
     */
    handleControlResponse: function(response) {
        const { command, success, message, error } = response;
        
        if (success) {
            this.addLogMessage(`${command} successful: ${message}`, 'success');
            AICameraUtils.showToast(`${command} successful`, 'success');
        } else {
            this.addLogMessage(`${command} failed: ${error || message}`, 'error');
            AICameraUtils.showToast(`${command} failed: ${error || message}`, 'error');
        }
        
        // Re-enable buttons
        const startBtn = document.getElementById('start-detection');
        const stopBtn = document.getElementById('stop-detection');
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = false;
        
        // Request updated status
        this.requestStatusUpdate();
    },

    /**
     * Request status update
     */
    requestStatusUpdate: function() {
        if (this.socket && this.socket.connected) {
            this.socket.emit('detection_status_request');
            this.socket.emit('detection_statistics_request');
        } else {
            // Fallback to HTTP API if WebSocket not available
            this.requestStatusViaHTTP();
        }
    },

    /**
     * Request status via HTTP API (fallback)
     */
    requestStatusViaHTTP: function() {
        AICameraUtils.apiRequest('/detection/status')
            .then(data => {
                if (data && data.success) {
                    this.updateDetectionStatus(data.status);
                }
            })
            .catch(error => {
                console.warn('Detection status not available:', error.message);
                        // Set default status according to variable_management.md standards
        this.updateDetectionStatus({
            service_running: false,
            detection_processor_status: {
                models_loaded: false,
                vehicle_model_available: false,
                lp_detection_model_available: false,
                lp_ocr_model_available: false,
                easyocr_available: false
            },
            detection_interval: 0.1,
            confidence_threshold: 0.5
        });
            });

        AICameraUtils.apiRequest('/detection/statistics')
            .then(data => {
                if (data && data.success) {
                    this.updateStatistics(data.statistics);
                }
            })
            .catch(error => {
                console.warn('Detection statistics not available:', error.message);
                // Set default statistics
                this.updateStatistics({
                    total_frames_processed: 0,
                    total_vehicles_detected: 0,
                    total_plates_detected: 0,
                    successful_ocr: 0,
                    detection_rate_percent: 0,
                    avg_processing_time_ms: 0
                });
            });
    },

    /**
     * Update detection status display
     */
    updateDetectionStatus: function(status) {
        this.lastStatusUpdate = status;
        
        // Update service status
        const serviceRunning = status.service_running || false;
        this.detectionRunning = serviceRunning;
        
        const serviceStatusElement = document.getElementById('service-status');
        if (serviceStatusElement) {
            serviceStatusElement.textContent = serviceRunning ? 'Running' : 'Stopped';
            serviceStatusElement.className = `badge ${serviceRunning ? 'bg-success' : 'bg-secondary'}`;
        }
        
        // Update service status card
        const statusCard = document.getElementById('service-status-card');
        if (statusCard) {
            statusCard.className = `card status-card ${serviceRunning ? 'active' : ''}`;
        }
        
        // Update models status
        const processorStatus = status.detection_processor_status || {};
        const modelsLoaded = processorStatus.models_loaded || false;
        
        const modelsStatusElement = document.getElementById('models-status');
        if (modelsStatusElement) {
            modelsStatusElement.textContent = modelsLoaded ? 'Loaded' : 'Not Loaded';
            modelsStatusElement.className = `badge ${modelsLoaded ? 'bg-success' : 'bg-danger'}`;
        }
        
        // Update detection interval with fallback
        const interval = status.detection_interval || 0.1;
        const intervalElement = document.getElementById('detection-interval');
        const intervalSetting = document.getElementById('interval-setting');
        if (intervalElement) intervalElement.textContent = `${interval}s`;
        if (intervalSetting) intervalSetting.value = interval;
        
        // Update model status indicators
        this.updateModelStatus('vehicle-model-status', processorStatus.vehicle_model_available);
        this.updateModelStatus('lp-detection-model-status', processorStatus.lp_detection_model_available);
        this.updateModelStatus('lp-ocr-model-status', processorStatus.lp_ocr_model_available);
        this.updateModelStatus('easyocr-status', processorStatus.easyocr_available);
        
        // Update detection configuration display with fallbacks
        const resolution = processorStatus.detection_resolution || [640, 640];
        const resolutionElement = document.getElementById('detection-resolution');
        if (resolutionElement) resolutionElement.textContent = `${resolution[0]}x${resolution[1]}`;
        
        const vehicleConfElement = document.getElementById('vehicle-confidence');
        if (vehicleConfElement) vehicleConfElement.textContent = processorStatus.confidence_threshold || 0.5;
        
        const plateConfElement = document.getElementById('plate-confidence');
        if (plateConfElement) plateConfElement.textContent = processorStatus.plate_confidence_threshold || 0.3;
        
        // Update button states
        this.updateButtonStates(serviceRunning, modelsLoaded);
    },

    /**
     * Update model status indicator
     */
    updateModelStatus: function(elementId, isLoaded) {
        const element = document.getElementById(elementId);
        if (element) {
            element.className = `model-status ${isLoaded ? 'loaded' : 'not-loaded'}`;
        }
    },

    /**
     * Update button states
     */
    updateButtonStates: function(serviceRunning, modelsLoaded) {
        const startBtn = document.getElementById('start-detection');
        const stopBtn = document.getElementById('stop-detection');
        const processBtn = document.getElementById('process-frame');
        
        if (startBtn) startBtn.disabled = serviceRunning || !modelsLoaded;
        if (stopBtn) stopBtn.disabled = !serviceRunning;
        if (processBtn) processBtn.disabled = !modelsLoaded;
    },

    /**
     * Update statistics display
     */
    updateStatistics: function(stats) {
        const statMappings = [
            { key: 'total_frames_processed', elementId: 'stat-frames', default: 0 },
            { key: 'total_vehicles_detected', elementId: 'stat-vehicles', default: 0 },
            { key: 'total_plates_detected', elementId: 'stat-plates', default: 0 },
            { key: 'successful_ocr', elementId: 'stat-ocr', default: 0 },
            { key: 'detection_rate_percent', elementId: 'stat-rate', default: 0, suffix: '%' },
            { key: 'avg_processing_time_ms', elementId: 'stat-time', default: 0, suffix: 'ms' }
        ];

        statMappings.forEach(({ key, elementId, default: defaultValue, suffix = '' }) => {
            const element = document.getElementById(elementId);
            if (element) {
                element.textContent = `${stats[key] || defaultValue}${suffix}`;
            }
        });
        
        // Update timestamps
        const startedAtElement = document.getElementById('started-at');
        const lastDetectionElement = document.getElementById('last-detection');
        
        if (startedAtElement) {
            startedAtElement.textContent = stats.started_at ? 
                AICameraUtils.formatTimestamp(stats.started_at) : '-';
        }
        
        if (lastDetectionElement) {
            lastDetectionElement.textContent = stats.last_detection ? 
                AICameraUtils.formatTimestamp(stats.last_detection) : '-';
        }
    },

    /**
     * Add log message
     */
    addLogMessage: function(message, type = 'info') {
        AICameraUtils.addLogMessage('detection-log', message, type);
    },

    /**
     * Load recent detection results
     */
    loadRecentResults: function() {
        AICameraUtils.apiRequest('/detection/results/recent')
            .then(data => {
                if (data.success) {
                    this.displayRecentResults(data.results);
                } else {
                    throw new Error(data.error || 'Failed to load results');
                }
            })
            .catch(error => {
                this.addLogMessage('Failed to load recent results: ' + error.message, 'error');
            });
    },

    /**
     * Display recent detection results
     */
    displayRecentResults: function(results) {
        const container = document.getElementById('recent-results');
        if (!container) return;
        
        if (!results || results.length === 0) {
            container.innerHTML = '<p class="text-muted text-center">No detection results available</p>';
            return;
        }
        
        container.innerHTML = '';
        
        results.slice(0, 10).forEach(result => {
            const resultDiv = document.createElement('div');
            const hasDetections = result.vehicles_count > 0;
            resultDiv.className = `detection-result ${hasDetections ? 'success' : 'no-detection'}`;
            
            resultDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <small class="text-muted">${AICameraUtils.formatTimestamp(result.timestamp)}</small>
                    <div class="badge bg-${hasDetections ? 'success' : 'warning'}">
                        ${result.vehicles_count} vehicles, ${result.plates_count} plates
                    </div>
                </div>
                ${result.ocr_results && result.ocr_results.length > 0 ? 
                    `<div class="small"><strong>License Plates:</strong> ${result.ocr_results.map(ocr => ocr.text).join(', ')}</div>` : 
                    '<div class="small text-muted">No license plates detected</div>'
                }
            `;
            
            container.appendChild(resultDiv);
        });
    },

    /**
     * Handle configuration form submission
     */
    handleConfigSubmit: function(e) {
        e.preventDefault();
        
        const interval = parseFloat(document.getElementById('interval-setting').value);
        const autoStart = document.getElementById('auto-start-setting').checked;
        
        AICameraUtils.apiRequest('/detection/config', {
            method: 'POST',
            body: JSON.stringify({
                detection_interval: interval,
                auto_start: autoStart
            })
        })
        .then(data => {
            if (data.success) {
                this.addLogMessage('Configuration updated successfully', 'success');
                AICameraUtils.showToast('Configuration updated', 'success');
                this.requestStatusUpdate();
            } else {
                throw new Error(data.error || 'Configuration update failed');
            }
        })
        .catch(error => {
            this.addLogMessage('Failed to update configuration: ' + error.message, 'error');
        });
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

// Initialize detection manager when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    DetectionManager.init();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        DetectionManager.cleanup();
    });
    
    console.log('Detection Dashboard JavaScript loaded');
});
