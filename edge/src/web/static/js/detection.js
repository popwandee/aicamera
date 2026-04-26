/**
 * AI Camera v2.0 - Unified Detection Dashboard JavaScript
 * 
 * Combined detection control, monitoring, and results functionality.
 * 
 * @author AI Camera Team
 * @version 2.0
 * @since 2025-08-23
 */

// Unified Detection Manager
const DetectionManager = {
    socket: null,
    statusUpdateInterval: null,
    detectionRunning: false,
    lastStatusUpdate: null,
    
    // Detection Results Manager properties
    currentPage: 1,
    perPage: 20,
    totalPages: 0,
    totalResults: 0,
    currentSort: { by: 'created_at', order: 'desc' },
    currentFilters: {
        search: '',
        dateFrom: '',
        dateTo: '',
        hasVehicles: '',
        hasPlates: ''
    },
    isLoading: false,
    selectionMode: false,
    selectedResults: new Set(),
    currentResults: [],
    
    /**
     * Initialize unified detection dashboard
     */
    init: function() {
        this.initializeWebSocket();
        this.setupEventHandlers();
        this.setupFormHandlers();
        this.setupResultsEventHandlers();
        this.setupComprehensiveOutputToggle();
        this.startPeriodicUpdates();
        this.loadResults();
        this.loadStatistics();
        this.loadConfiguration();
        this.initializeFormWithCurrentValues();
        console.log('Unified Detection Manager initialized');
    },

    /**
     * Initialize WebSocket connection
     */
    initializeWebSocket: function() {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not available');
            return;
        }

        if (!window.useSocketIO) {
            this.socket = null;
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
            // Also fetch DB-backed statistics on connect
            this.loadStatistics();
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.addLogMessage('Disconnected from server', 'warning');
        });

        this.socket.on('detection_status_update', (data) => {
            if (data && data.detection_status) {
                this.updateDetectionStatus(data.detection_status);
            } else if (data && data.success && data.detection_status) {
                this.updateDetectionStatus(data.detection_status);
            } else if (data && typeof data === 'object' && (('service_running' in data) || ('detection_processor_status' in data))) {
                // Some emitters send the status object directly without wrapping
                this.updateDetectionStatus(data);
            } else if (data && data.status && typeof data.status === 'object') {
                // Fallback for alternative key naming
                this.updateDetectionStatus(data.status);
            } else {
                console.error('Invalid detection status update:', data);
            }
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
     * Setup event handlers for detection control
     */
    setupEventHandlers: function() {
        // Control buttons
        const startBtn = document.getElementById('start-detection');
        const stopBtn = document.getElementById('stop-detection');
        const processBtn = document.getElementById('process-frame');

        if (startBtn) startBtn.addEventListener('click', () => this.controlDetection('start'));
        if (stopBtn) stopBtn.addEventListener('click', () => this.controlDetection('stop'));
        if (processBtn) processBtn.addEventListener('click', () => this.processFrame());
    },

    /**
     * Setup event handlers for detection results
     */
    setupResultsEventHandlers: function() {
        // Setup modal event handlers
        this.setupModalEventHandlers();
        // Refresh button
        const refreshBtn = document.getElementById('refresh-results-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadResults();
                this.addLogMessage('Refreshing detection results...', 'info');
            });
        }

        // Export button
        const exportBtn = document.getElementById('export-results-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.showExportModal();
            });
        }

        // Clear filters button
        const clearFiltersBtn = document.getElementById('clear-filters-btn');
        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => {
                this.clearFilters();
            });
        }

        // Filters form submit handler
        const filtersForm = document.getElementById('filters-form');
        if (filtersForm) {
            filtersForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.applyFilters();
            });
        }

        // Search input - support Enter key and debounce
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            let searchTimeout;
            
            // Enter key handler - apply filters immediately
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    clearTimeout(searchTimeout);
                    this.applyFilters();
                }
            });
            
            // Input handler with debounce (optional auto-apply)
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                // Don't auto-apply on input, wait for Enter or Submit button
            });
        }

        // Date filters - remove auto-apply, wait for form submit
        const dateFrom = document.getElementById('date-from');
        if (dateFrom) {
            dateFrom.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.applyFilters();
                }
            });
        }

        const dateTo = document.getElementById('date-to');
        if (dateTo) {
            dateTo.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.applyFilters();
                }
            });
        }

        // Vehicle filter - remove auto-apply, wait for form submit
        const hasVehicles = document.getElementById('has-vehicles');
        if (hasVehicles) {
            hasVehicles.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.applyFilters();
                }
            });
        }

        // Plates filter - remove auto-apply, wait for form submit
        const hasPlates = document.getElementById('has-plates');
        if (hasPlates) {
            hasPlates.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.applyFilters();
                }
            });
        }

        // Per page selector
        const perPageSelect = document.getElementById('per-page-select');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', (e) => {
                this.perPage = parseInt(e.target.value);
                this.currentPage = 1;
                this.loadResults();
            });
        }

        // Export confirmation
        const confirmExportBtn = document.getElementById('confirm-export-btn');
        if (confirmExportBtn) {
            confirmExportBtn.addEventListener('click', () => {
                this.exportResults();
            });
        }

        // Sortable table headers
        document.querySelectorAll('.sortable').forEach(header => {
            header.addEventListener('click', (e) => {
                const sortBy = e.currentTarget.dataset.sort;
                this.handleSort(sortBy);
            });
        });

        // Selection toggle button
        const toggleSelectionBtn = document.getElementById('toggle-selection-btn');
        if (toggleSelectionBtn) {
            toggleSelectionBtn.addEventListener('click', () => {
                this.toggleSelectionMode();
            });
        }

        // Bulk delete button
        const deleteSelectedBtn = document.getElementById('delete-selected-btn');
        if (deleteSelectedBtn) {
            deleteSelectedBtn.addEventListener('click', () => {
                this.deleteSelectedResults();
            });
        }

        // Selection checkboxes
        const resultsTableBody = document.getElementById('results-table-body');
        if (resultsTableBody) {
            resultsTableBody.addEventListener('change', (e) => {
                if (e.target && e.target.classList && e.target.classList.contains('result-select-checkbox')) {
                    const resultId = e.target.dataset.resultId;
                    this.handleSelectionChange(resultId, e.target.checked);
                }
            });

            resultsTableBody.addEventListener('click', (e) => {
                const target = e.target;
                if (!(target instanceof Element)) return;
                if (!this.selectionMode) return;
                if (target.closest('.actions-cell')) return;
                if (target.classList.contains('result-select-checkbox') || target.closest('.result-select-checkbox')) return;
                const row = target.closest('tr[data-result-id]');
                if (!row) return;
                const checkbox = row.querySelector('.result-select-checkbox');
                if (!checkbox || checkbox.disabled) return;
                checkbox.checked = !checkbox.checked;
                this.handleSelectionChange(row.dataset.resultId, checkbox.checked);
            });
        }

        // Select All checkbox in header
        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                this.handleSelectAllChange(e.target.checked);
            });
        }
    },

    /**
     * Setup modal event handlers
     */
    setupModalEventHandlers: function() {
        const detailModal = document.getElementById('detail-modal');
        if (detailModal) {
            // Handle modal hidden event
            detailModal.addEventListener('hidden.bs.modal', () => {
                // Clear modal content
                const modalBody = document.getElementById('detail-modal-body');
                if (modalBody) {
                    modalBody.innerHTML = '';
                }
                
                // Clear modal instance
                this.currentDetailModal = null;
                
                // Ensure dashboard remains active
                console.log('Detail modal closed, dashboard remains active');
            });
            
            // Handle modal shown event
            detailModal.addEventListener('shown.bs.modal', () => {
                console.log('Detail modal opened');
            });
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
     * Start periodic status updates - OPTIMIZED for reduced resource usage
     */
    startPeriodicUpdates: function() {
        // Update immediately
        this.requestStatusUpdate();
        
        // Setup periodic updates every 30 seconds (increased from 5 seconds for reduced resource usage)
        this.statusUpdateInterval = setInterval(() => {
            this.requestStatusUpdate();
            this.loadStatistics();
        }, 30000);
        
        // Removed automatic loading of recent results - only load when needed for specific functions
        
        // Add initial log message
        this.addLogMessage('Detection dashboard initialized (optimized)', 'info');
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
                if (data && data.success && data.detection_status) {
                    this.updateDetectionStatus(data.detection_status);
                } else {
                    console.error('Invalid status response:', data);
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
                if (data && data.success && data.statistics) {
                    this.updateStatistics(data.statistics);
                } else {
                    console.error('Invalid statistics response:', data);
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
        const intervalBadge = document.getElementById('detection-interval-badge');
        const intervalInput = document.getElementById('detection-interval-input');
        
        if (intervalBadge) {
            intervalBadge.textContent = `${interval}s`;
            console.log('Updated interval badge:', intervalBadge.textContent);
        }
        if (intervalInput) {
            intervalInput.value = interval;
            console.log('Updated interval input:', intervalInput.value);
        }
        
        // Update model status indicators and names
        this.updateModelStatus('vehicle-model-status', processorStatus.vehicle_model_available, processorStatus.vehicle_model_name);
        this.updateModelStatus('lp-detection-model-status', processorStatus.lp_detection_model_available, processorStatus.lp_detection_model_name);
        this.updateModelStatus('lp-ocr-model-status', processorStatus.lp_ocr_model_available, processorStatus.lp_ocr_model_name);
        this.updateModelStatus('easyocr-status', processorStatus.easyocr_available, processorStatus.easyocr_available ? 'EasyOCR' : '');
        
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

        // Update performance analytics panel using latest status
        this.updatePerformanceAnalytics();
        // Also update quality metrics so bars reflect current stats
        this.updateQualityMetrics();
    },

    /**
     * Update model status indicator
     */
    updateModelStatus: function(elementId, isLoaded, modelName) {
        const element = document.getElementById(elementId);
        if (element) {
            element.className = `model-status ${isLoaded ? 'loaded' : 'not-loaded'}`;
            if (modelName && typeof modelName === 'string') {
                element.title = modelName;
                element.setAttribute('data-model-name', modelName);
                // Also render text next to the indicator if the DOM structure allows
                const label = element.nextElementSibling;
                if (label && label.tagName === 'SPAN' && !label.dataset.modelInjected) {
                    label.innerHTML = `${label.textContent} <small class="text-muted">(${modelName})</small>`;
                    label.dataset.modelInjected = 'true';
                }
            }
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
        // Update main statistics cards
        const statMappings = [
            { key: 'total_detections', elementId: 'total-detections', default: 0 },
            { key: 'total_vehicles', elementId: 'total-vehicles', default: 0 },
            { key: 'total_plates', elementId: 'total-plates', default: 0 },
            { key: 'avg_processing_time_ms', elementId: 'avg-processing-time', default: 0, suffix: 'ms', format: (val) => `${val.toFixed(1)}ms` },
            { key: 'current_fps', elementId: 'current-fps', default: 0, format: (val) => val.toFixed(1) },
            { key: 'detection_errors', elementId: 'detection-errors', default: 0 }
        ];

        statMappings.forEach(({ key, elementId, default: defaultValue, suffix = '', format }) => {
            const element = document.getElementById(elementId);
            if (element) {
                const value = stats[key] || defaultValue;
                if (format) {
                    element.textContent = format(value);
                } else {
                    element.textContent = `${value}${suffix}`;
                }
            }
        });
        
        // Update last detection timestamp
        const lastDetectionElement = document.getElementById('last-detection');
        if (lastDetectionElement) {
            if (stats.last_detection) {
                const date = new Date(stats.last_detection);
                lastDetectionElement.textContent = date.toLocaleString();
            } else {
                lastDetectionElement.textContent = 'None';
            }
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
        console.log('Loading recent detection results...');
        AICameraUtils.apiRequest('/detection/results')
            .then(data => {
                console.log('Recent results response:', data);
                if (data.success) {
                    // Take only the first 10 results for recent display
                    const recentResults = data.results.slice(0, 10);
                    this.displayRecentResults(recentResults);
                } else {
                    throw new Error(data.error || 'Failed to load results');
                }
            })
            .catch(error => {
                console.error('Error loading recent results:', error);
                this.addLogMessage('Failed to load recent results: ' + error.message, 'error');
            });
    },

    /**
     * Load detection results with pagination and filters
     */
    loadResults: function() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoadingState();
        
        // Always read per_page from the dropdown so it matches the selected value (fixes 20/50/100 showing only 13)
        const perPageSelect = document.getElementById('per-page-select');
        if (perPageSelect) {
            const value = parseInt(perPageSelect.value, 10);
            if (Number.isInteger(value) && value >= 1 && value <= 200) {
                this.perPage = value;
            }
        }
        
        const params = new URLSearchParams({
            page: this.currentPage,
            per_page: this.perPage,
            sort_by: this.currentSort.by,
            sort_order: this.currentSort.order
        });
        
        // Add filters
        if (this.currentFilters.search) params.append('search', this.currentFilters.search);
        if (this.currentFilters.dateFrom) params.append('date_from', this.currentFilters.dateFrom);
        if (this.currentFilters.dateTo) params.append('date_to', this.currentFilters.dateTo);
        if (this.currentFilters.hasVehicles) params.append('has_vehicles', this.currentFilters.hasVehicles);
        if (this.currentFilters.hasPlates) params.append('has_plates', this.currentFilters.hasPlates);
        
        console.log('Loading detection results...');
        AICameraUtils.apiRequest(`/detection/results?${params.toString()}`)
            .then(data => {
                console.log('Results response:', data);
                if (data.success) {
                    // Use server-side pagination data directly
                    this.totalPages = data.total_pages || Math.ceil((data.total || 0) / this.perPage);
                    
                    console.log('Server pagination data:', {
                        total: data.total,
                        total_pages: data.total_pages,
                        current_page: data.page,
                        per_page: data.per_page,
                        results_count: data.results ? data.results.length : 0
                    });
                    
                    this.displayResults({
                        results: data.results || [],
                        total: data.total || 0,
                        count: data.results ? data.results.length : 0,
                        total_pages: data.total_pages || Math.ceil((data.total || 0) / this.perPage)
                    });
                } else {
                    throw new Error(data.error || 'Failed to load results');
                }
            })
            .catch(error => {
                console.error('Error loading results:', error);
                this.showErrorState(error.message);
            })
            .finally(() => {
                this.isLoading = false;
            });
    },

    /**
     * Load statistics
     */
    loadStatistics: function() {
        AICameraUtils.apiRequest('/detection/statistics')
            .then(data => {
                if (data.success) {
                    // Update cards with DB-backed stats
                    const s = data.statistics || {};
                    this.updateElement('vehicles-detected', s.total_vehicles || 0);
                    this.updateElement('plates-detected-count', s.total_plates || 0);
                    this.updateElement('successful-ocr-count', s.successful_ocr || 0);
                    this.updateElement('plate-detection-rate', (s.plate_detection_rate_percent || 0) + '%');
                    this.updateElement('ocr-success-rate', (s.ocr_success_rate_percent || 0) + '%');
                    this.updateElement('processing-efficiency', (s.avg_processing_time_ms || 0) + 'ms');

                    // Also update detailed statistics panel if present
                    this.updateStatisticsDisplay({
                        total_detections: s.total_detections || 0,
                        total_vehicles: s.total_vehicles || 0,
                        total_plates: s.total_plates || 0,
                        avg_processing_time_ms: s.avg_processing_time_ms || 0,
                        detection_errors: 0,
                        last_detection: s.last_detection || null,
                        current_fps: 0
                    });
                }
            })
            .catch(() => {
                // Fallback: derive metrics from /detection/status when /detection/statistics is unavailable
                AICameraUtils.apiRequest('/detection/status')
                    .then(data => {
                        const status = (data && data.detection_status) ? data.detection_status : (data || {});
                        const statistics = status.statistics || {};
                        const totalVehicles = statistics.total_vehicles_detected || 0;
                        const totalPlates = statistics.total_plates_detected || 0;
                        const successfulOcr = statistics.successful_ocr || 0;
                        const plateRate = totalVehicles > 0 ? ((totalPlates / totalVehicles) * 100).toFixed(1) : '0';
                        const ocrRate = totalPlates > 0 ? ((successfulOcr / totalPlates) * 100).toFixed(1) : '0';
                        const avgProcessing = (statistics.avg_processing_time_ms !== undefined)
                            ? statistics.avg_processing_time_ms
                            : ((statistics.processing_time_avg || 0) * 1000);

                        this.updateElement('vehicles-detected', totalVehicles);
                        this.updateElement('plates-detected-count', totalPlates);
                        this.updateElement('successful-ocr-count', successfulOcr);
                        this.updateElement('plate-detection-rate', plateRate + '%');
                        this.updateElement('ocr-success-rate', ocrRate + '%');
                        this.updateElement('processing-efficiency', (avgProcessing || 0) + 'ms');

                        // Update performance analytics too
                        this.lastStatusUpdate = status;
                        this.updatePerformanceAnalytics();
                    })
                    .catch(() => {
                        // Leave as-is if both endpoints fail
                    });
            });
    },

    /**
     * Display detection results
     */
    displayResults: function(data) {
        const { results, count, total, total_pages } = data;
        
        // Store total results for pagination
        this.totalResults = total || count || results.length;

        this.currentResults = Array.isArray(results) ? results : [];
        
        if (this.selectionMode) {
            this.pruneSelectionToCurrentResults();
        } else if (this.selectedResults.size > 0) {
            this.selectedResults.clear();
        }
        
        // Update total pages if provided from server
        if (total_pages !== undefined) {
            this.totalPages = total_pages;
        }
        
        this.updateResultsCount(this.totalResults);
        this.renderResultsTable(this.currentResults);
        this.renderPagination();
        this.updateSelectionUI();
        
        if (!results || results.length === 0) {
            this.showEmptyState();
        } else {
            this.hideEmptyState();
        }
        
        this.hideLoadingState();
        this.hideErrorState();
    },

    /**
     * Render results table
     */
    renderResultsTable: function(results) {
        const tbody = document.getElementById('results-table-body');
        const table = document.getElementById('results-table');
        if (!tbody) return;
        
        if (table) {
            table.classList.toggle('selection-enabled', this.selectionMode);
        }

        tbody.innerHTML = '';
        
        // Ensure we render ALL results, not limited
        const resultsToRender = Array.isArray(results) ? results : [];
        
        resultsToRender.forEach((result, index) => {
            const vehiclesDisplay = this.formatVehicleCell(result);
            const platesDisplay = this.formatPlatesForTable(result.plate_detections);
            const row = document.createElement('tr');
            const resultId = result && result.id !== undefined && result.id !== null ? String(result.id) : '';
            const isSelected = this.selectedResults.has(resultId);
            const checkboxDisabled = !this.selectionMode || !resultId;
            row.dataset.resultId = resultId;
            if (isSelected) {
                row.classList.add('selected-row');
            }
            row.innerHTML = `
                <td class="selection-cell text-center">
                    <input type="checkbox"
                        class="form-check-input result-select-checkbox"
                        data-result-id="${resultId}"
                        ${checkboxDisabled ? 'disabled' : ''}
                        ${isSelected ? 'checked' : ''}>
                </td>
                <td>${result.id || 'N/A'}</td>
                <td>${AICameraUtils.formatTimestamp(result.timestamp || result.created_at)}</td>
                <td>${vehiclesDisplay}</td>
                <td>${platesDisplay}</td>
                <td>${this.formatOcrResults(result.ocr_results, true)}</td>
                <td class="actions-cell">
                    <button class="btn btn-sm btn-outline-primary" onclick="DetectionManager.showDetail(${result.id || 0})">
                        <i class="fas fa-eye"></i> View
                    </button>
                    <button class="btn btn-sm btn-outline-danger ms-1" onclick="DetectionManager.confirmDelete(${result.id || 0})">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });

        this.updateSelectAllCheckbox();
    },

    /**
     * Format OCR results for display
     * when showConfidence=true, renders: "OCR- <text> (<xx>%)"
     */
    formatOcrResults: function(ocrResults, showConfidence = false) {
        if (!ocrResults || ocrResults.length === 0) {
            return '<span class="text-muted">No OCR results</span>';
        }

        return ocrResults.map((ocr, index) => {
            const text = ocr.text || `#${index + 1}`;
            if (!showConfidence) {
                return `<span class="badge bg-success me-1">${text}</span>`;
            }
            const conf = this.normalizeConfidence(ocr.confidence || ocr.score || ocr.ocr_confidence);
            const confText = conf !== null ? `${conf}%` : '-';
            return `<span class="badge bg-success me-1">OCR- ${text} (${confText})</span>`;
        }).join('');
    },

    /**
     * Compose vehicle cell with thumbnail + badges
     */
    formatVehicleCell: function(result) {
        const badges = this.formatVehiclesForTable(result.vehicle_detections);
        const imageUrl = this.resolveImageUrl(result.original_image_path);
        const imageMarkup = imageUrl
            ? `<img src="${imageUrl}" alt="Vehicle" class="vehicle-thumb" loading="lazy">`
            : `<div class="vehicle-thumb placeholder"><i class="fas fa-car-side"></i></div>`;
        
        return `
            <div class="vehicle-table-cell">
                ${imageMarkup}
                <div class="vehicle-info">${badges}</div>
            </div>
        `;
    },

    /**
     * Format vehicles list for table: "Vehicle i (<xx>%)"
     */
    formatVehiclesForTable: function(vehicleDetections) {
        if (Array.isArray(vehicleDetections) && vehicleDetections.length > 0) {
            return vehicleDetections.map((det, idx) => {
                const conf = this.normalizeConfidence(det.confidence || det.score || det.conf);
                const confText = conf !== null ? `${conf}%` : '-';
                return `<span class=\"badge bg-primary me-1\">Vehicle ${idx + 1} (${confText})</span>`;
            }).join('');
        }
        return '<span class="text-muted">0</span>';
    },

    /**
     * Format plates list for table: "Plate i (<xx>%)"
     */
    formatPlatesForTable: function(plateDetections) {
        if (Array.isArray(plateDetections) && plateDetections.length > 0) {
            return plateDetections.map((det, idx) => {
                const conf = this.normalizeConfidence(det.confidence || det.score || det.ocr_confidence);
                const confText = conf !== null ? `${conf}%` : '-';
                return `<span class=\"badge bg-warning text-dark me-1\">Plate ${idx + 1} (${confText})</span>`;
            }).join('');
        }
        return '<span class="text-muted">0</span>';
    },

    /**
     * Normalize confidence to integer percent [0-100]; returns null if unknown
     */
    normalizeConfidence: function(value) {
        if (value === undefined || value === null || isNaN(value)) return null;
        let v = Number(value);
        // If value seems to be 0-1, scale to percent
        if (v <= 1) v = v * 100;
        v = Math.max(0, Math.min(100, v));
        return Math.round(v);
    },

    /**
     * Confirm deletion of a detection result
     */
    confirmDelete: function(resultId) {
        if (!resultId) return;
        const confirmed = window.confirm(`Delete detection result #${resultId}? This will remove the record and related images.`);
        if (!confirmed) return;
        this.deleteDetectionResult(resultId);
    },

    /**
     * Delete detection result via API
     */
    deleteDetectionResult: function(resultId, options = {}) {
        if (!resultId) return Promise.resolve();
        const { suppressReload = false, suppressAlerts = false } = options;
        this.addLogMessage(`Deleting detection result #${resultId}...`, 'info');
        return this.performDeleteRequest(resultId)
            .then(data => {
                if (data.success) {
                    this.addLogMessage(`Detection result #${resultId} deleted`, 'success');
                    if (!suppressReload) {
                        this.loadResults();
                    }
                    return data;
                } else {
                    const errorMessage = data.error || 'Unknown error';
                    throw new Error(errorMessage);
                }
            })
            .catch(error => {
                console.error('Error deleting detection result:', error);
                if (!suppressAlerts) {
                    window.alert(`Failed to delete detection result #${resultId}: ${error.message}`);
                }
                throw error;
            });
    },

    performDeleteRequest: function(resultId) {
        return AICameraUtils.apiRequest(`/detection/results/${resultId}`, {
            method: 'DELETE'
        });
    },

    toggleSelectionMode: function() {
        this.selectionMode = !this.selectionMode;
        if (!this.selectionMode) {
            this.clearSelection();
        }
        this.updateSelectionUI();
        this.renderResultsTable(this.currentResults || []);
    },

    updateSelectionUI: function() {
        const toggleBtn = document.getElementById('toggle-selection-btn');
        const deleteBtn = document.getElementById('delete-selected-btn');
        const countBadge = document.getElementById('selection-count-badge');
        const isDeleting = deleteBtn && deleteBtn.dataset.deleting === 'true';

        if (toggleBtn) {
            toggleBtn.innerHTML = this.selectionMode
                ? '<i class="fas fa-times me-1"></i>Cancel Select'
                : '<i class="fas fa-check-square me-1"></i>Select';
            toggleBtn.classList.toggle('btn-outline-primary', this.selectionMode);
            toggleBtn.classList.toggle('btn-outline-secondary', !this.selectionMode);
        }

        if (deleteBtn) {
            deleteBtn.classList.toggle('d-none', !this.selectionMode);
            deleteBtn.disabled = !this.selectionMode || this.selectedResults.size === 0 || isDeleting;
        }

        if (countBadge) {
            countBadge.textContent = this.selectedResults.size;
        }

        this.updateSelectAllCheckbox();
    },

    handleSelectionChange: function(resultId, isChecked) {
        if (!this.selectionMode || !resultId) return;
        if (isChecked) {
            this.selectedResults.add(String(resultId));
        } else {
            this.selectedResults.delete(String(resultId));
        }
        const row = document.querySelector(`#results-table-body tr[data-result-id="${resultId}"]`);
        if (row) {
            row.classList.toggle('selected-row', isChecked);
        }
        this.updateSelectionUI();
        this.updateSelectAllCheckbox();
    },

    clearSelection: function() {
        this.selectedResults.clear();
        document.querySelectorAll('#results-table-body tr').forEach(row => row.classList.remove('selected-row'));
        document.querySelectorAll('.result-select-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        this.updateSelectionUI();
        this.updateSelectAllCheckbox();
    },

    /**
     * Handle Select All checkbox in table header (select/deselect all on current page)
     */
    handleSelectAllChange: function(isChecked) {
        if (!this.selectionMode) return;

        const checkboxes = document.querySelectorAll('.result-select-checkbox:not(:disabled)');
        checkboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
            const resultId = checkbox.dataset.resultId;
            if (resultId) {
                if (isChecked) {
                    this.selectedResults.add(resultId);
                } else {
                    this.selectedResults.delete(resultId);
                }
            }
        });

        document.querySelectorAll('#results-table-body tr').forEach(row => {
            const checkbox = row.querySelector('.result-select-checkbox');
            if (checkbox && !checkbox.disabled) {
                row.classList.toggle('selected-row', isChecked);
            }
        });

        this.updateSelectionUI();
        this.updateSelectAllCheckbox();
    },

    /**
     * Sync header "Select All" checkbox state with row checkboxes (checked / unchecked / indeterminate)
     */
    updateSelectAllCheckbox: function() {
        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        if (!selectAllCheckbox) return;

        const checkboxes = document.querySelectorAll('.result-select-checkbox:not(:disabled)');
        if (checkboxes.length === 0) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = false;
            return;
        }

        const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        if (checkedCount === 0) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = false;
        } else if (checkedCount === checkboxes.length) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = true;
        } else {
            selectAllCheckbox.indeterminate = true;
            selectAllCheckbox.checked = false;
        }
    },

    pruneSelectionToCurrentResults: function() {
        if (!Array.isArray(this.currentResults) || this.currentResults.length === 0) return;
        const validIds = new Set(
            this.currentResults
                .map(result => (result && result.id !== undefined && result.id !== null) ? String(result.id) : null)
                .filter(id => id !== null)
        );
        this.selectedResults.forEach(id => {
            if (!validIds.has(id)) {
                this.selectedResults.delete(id);
            }
        });
    },

    deleteSelectedResults: function() {
        if (!this.selectionMode || this.selectedResults.size === 0) return;
        const ids = Array.from(this.selectedResults);
        const confirmed = window.confirm(`Delete ${ids.length} selected detection result(s)? This will remove the records and related images.`);
        if (!confirmed) return;

        const deleteBtn = document.getElementById('delete-selected-btn');
        let originalButtonContent = '';
        if (deleteBtn) {
            originalButtonContent = deleteBtn.innerHTML;
            deleteBtn.disabled = true;
            deleteBtn.dataset.deleting = 'true';
            deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Deleting...';
        }

        // Delete sequentially to avoid SQLite lock / concurrent write issues on the server
        const deleteSequentially = async () => {
            let successCount = 0;
            let failureCount = 0;
            for (const id of ids) {
                try {
                    await this.deleteDetectionResult(id, { suppressReload: true, suppressAlerts: true });
                    successCount++;
                } catch (e) {
                    failureCount++;
                    console.warn('Bulk delete: failed for id', id, e);
                }
            }
            if (successCount > 0) {
                this.addLogMessage(`Deleted ${successCount} detection result(s)`, failureCount === 0 ? 'success' : 'warning');
            }
            if (failureCount > 0) {
                this.addLogMessage(`${failureCount} detection result(s) failed to delete`, 'error');
                window.alert(`${failureCount} detection record(s) could not be deleted. Check logs for details.`);
            }
        };

        deleteSequentially()
            .catch(error => {
                console.error('Bulk delete error:', error);
                window.alert('Bulk delete failed: ' + error.message);
            })
            .finally(() => {
                if (deleteBtn) {
                    deleteBtn.dataset.deleting = 'false';
                    deleteBtn.innerHTML = originalButtonContent;
                }
                this.clearSelection();
                this.loadResults();
            });
    },




    /**
     * Handle sorting
     */
    handleSort: function(sortBy) {
        if (this.currentSort.by === sortBy) {
            this.currentSort.order = this.currentSort.order === 'asc' ? 'desc' : 'asc';
        } else {
            this.currentSort.by = sortBy;
            this.currentSort.order = 'desc';
        }
        
        this.updateSortIcons();
        this.loadResults();
    },

    /**
     * Update sort icons
     */
    updateSortIcons: function() {
        document.querySelectorAll('.sortable').forEach(header => {
            const icon = header.querySelector('.sort-icon');
            const sortBy = header.dataset.sort;
            
            if (sortBy === this.currentSort.by) {
                icon.className = `fas fa-sort-${this.currentSort.order === 'asc' ? 'up' : 'down'} sort-icon`;
            } else {
                icon.className = 'fas fa-sort sort-icon';
            }
        });
    },

    /**
     * Apply filters from form inputs
     */
    applyFilters: function() {
        // Read values from form inputs
        const searchInput = document.getElementById('search-input');
        const dateFrom = document.getElementById('date-from');
        const dateTo = document.getElementById('date-to');
        const hasVehicles = document.getElementById('has-vehicles');
        const hasPlates = document.getElementById('has-plates');
        
        // Update current filters
        this.currentFilters = {
            search: searchInput ? searchInput.value.trim() : '',
            dateFrom: dateFrom ? dateFrom.value : '',
            dateTo: dateTo ? dateTo.value : '',
            hasVehicles: hasVehicles ? hasVehicles.value : '',
            hasPlates: hasPlates ? hasPlates.value : ''
        };
        
        // Reset to first page when applying filters
        this.currentPage = 1;
        
        // Load results with new filters
        this.loadResults();
        
        // Log filter application
        if (this.addLogMessage) {
            this.addLogMessage('Filters applied', 'info');
        }
    },

    clearFilters: function() {
        this.currentFilters = {
            search: '',
            dateFrom: '',
            dateTo: '',
            hasVehicles: '',
            hasPlates: ''
        };
        
        // Reset form inputs
        const searchInput = document.getElementById('search-input');
        if (searchInput) searchInput.value = '';
        
        const dateFrom = document.getElementById('date-from');
        if (dateFrom) dateFrom.value = '';
        
        const dateTo = document.getElementById('date-to');
        if (dateTo) dateTo.value = '';
        
        const hasVehicles = document.getElementById('has-vehicles');
        if (hasVehicles) hasVehicles.value = '';
        
        const hasPlates = document.getElementById('has-plates');
        if (hasPlates) hasPlates.value = '';
        
        this.currentPage = 1;
        this.loadResults();
    },

    /**
     * Show export modal
     */
    showExportModal: function() {
        const modal = new bootstrap.Modal(document.getElementById('export-modal'));
        modal.show();
    },

    /**
     * Export results
     */
    exportResults: function() {
        const format = document.getElementById('export-format').value;
        
        const params = new URLSearchParams({
            format: format,
            sort_by: this.currentSort.by,
            sort_order: this.currentSort.order
        });
        
        // Add filters
        if (this.currentFilters.search) params.append('search', this.currentFilters.search);
        if (this.currentFilters.dateFrom) params.append('date_from', this.currentFilters.dateFrom);
        if (this.currentFilters.dateTo) params.append('date_to', this.currentFilters.dateTo);
        if (this.currentFilters.hasVehicles) params.append('has_vehicles', this.currentFilters.hasVehicles);
        if (this.currentFilters.hasPlates) params.append('has_plates', this.currentFilters.hasPlates);
        
        const url = `/detection_results/api/export?${params.toString()}`;
        
        // Create download link
        const link = document.createElement('a');
        link.href = url;
        link.download = `detection_results_${new Date().toISOString().split('T')[0]}.${format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('export-modal'));
        modal.hide();
        
        AICameraUtils.showToast('Export started', 'success');
    },

    /**
     * Update statistics display
     */
    updateStatisticsDisplay: function(stats) {
        // Update main statistics cards
        const elements = {
            'total-detections': stats.total_detections || 0,
            'total-vehicles': stats.total_vehicles || 0,
            'total-plates': stats.total_plates || 0,
            'avg-processing-time': `${(stats.avg_processing_time_ms || 0).toFixed(1)}ms`,
            'current-fps': (stats.current_fps || 0).toFixed(1),
            'detection-errors': stats.detection_errors || 0
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
        
        // Update last detection timestamp
        const lastDetectionElement = document.getElementById('last-detection');
        if (lastDetectionElement) {
            if (stats.last_detection) {
                const date = new Date(stats.last_detection);
                lastDetectionElement.textContent = date.toLocaleString();
            } else {
                lastDetectionElement.textContent = 'None';
            }
        }
    },

    /**
     * Show loading state
     */
    showLoadingState: function() {
        const loadingSpinner = document.getElementById('loading-spinner');
        const resultsTable = document.getElementById('results-table-container');
        const emptyState = document.getElementById('empty-state');
        const errorState = document.getElementById('error-state');
        
        if (loadingSpinner) loadingSpinner.style.display = 'block';
        if (resultsTable) resultsTable.style.display = 'none';
        if (emptyState) emptyState.style.display = 'none';
        if (errorState) errorState.style.display = 'none';
    },

    /**
     * Hide loading state
     */
    hideLoadingState: function() {
        const loadingSpinner = document.getElementById('loading-spinner');
        const resultsTable = document.getElementById('results-table-container');
        
        if (loadingSpinner) loadingSpinner.style.display = 'none';
        if (resultsTable) {
            resultsTable.style.display = 'block';
            // Ensure table container and table are fully visible
            resultsTable.style.maxHeight = 'none';
            resultsTable.style.overflow = 'visible';
            const tableResponsive = resultsTable.querySelector('.table-responsive');
            if (tableResponsive) {
                tableResponsive.style.maxHeight = 'none';
                tableResponsive.style.overflow = 'visible';
            }
            
            // Fix: Remove max-height and overflow from parent card-body
            const cardBody = resultsTable.closest('.card-body');
            if (cardBody) {
                cardBody.style.maxHeight = 'none';
                cardBody.style.overflow = 'visible';
            }
        }
    },

    /**
     * Show empty state
     */
    showEmptyState: function() {
        const emptyState = document.getElementById('empty-state');
        const resultsTable = document.getElementById('results-table-container');
        
        if (emptyState) emptyState.style.display = 'block';
        if (resultsTable) resultsTable.style.display = 'none';
    },

    /**
     * Hide empty state
     */
    hideEmptyState: function() {
        const emptyState = document.getElementById('empty-state');
        if (emptyState) emptyState.style.display = 'none';
    },

    /**
     * Show error state
     */
    showErrorState: function(message) {
        const errorState = document.getElementById('error-state');
        const errorMessage = document.getElementById('error-message');
        const loadingSpinner = document.getElementById('loading-spinner');
        
        if (errorState) errorState.style.display = 'block';
        if (errorMessage) errorMessage.textContent = message;
        if (loadingSpinner) loadingSpinner.style.display = 'none';
    },

    /**
     * Hide error state
     */
    hideErrorState: function() {
        const errorState = document.getElementById('error-state');
        if (errorState) errorState.style.display = 'none';
    },

    /**
     * Update results count
     */
    updateResultsCount: function(total) {
        const countElement = document.getElementById('results-count');
        if (countElement) {
            countElement.textContent = `${total} results`;
        }
    },

    /**
     * Update pagination info
     */
    updatePaginationInfo: function(pagination) {
        const infoElement = document.getElementById('pagination-info');
        if (infoElement) {
            const start = (pagination.page - 1) * pagination.per_page + 1;
            const end = Math.min(start + pagination.per_page - 1, pagination.total);
            infoElement.textContent = `Showing ${start}-${end} of ${pagination.total} results`;
        }
    },

    /**
     * Render pagination
     */
    renderPagination: function() {
        const nav = document.getElementById('pagination-nav');
        const container = document.getElementById('pagination-container');
        
        if (!nav || !container) return;
        
        // Always show pagination container
        container.style.display = 'block';
        nav.innerHTML = '';
        
        // Show pagination info
        this.updatePaginationInfo({
            page: this.currentPage,
            per_page: this.perPage,
            total: this.totalResults || 0
        });
        
        // Debug logging
        console.log('Pagination Debug:', {
            totalPages: this.totalPages,
            currentPage: this.currentPage,
            totalResults: this.totalResults,
            perPage: this.perPage
        });
        
        // Only show navigation buttons if there are multiple pages
        if (this.totalPages <= 1) {
            console.log('Not showing pagination buttons: totalPages <= 1');
            return;
        }
        
        console.log('Showing pagination buttons for', this.totalPages, 'pages');
        
        // Previous button
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${this.currentPage === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `
            <button class="page-link" onclick="DetectionManager.goToPage(${this.currentPage - 1})" ${this.currentPage === 1 ? 'disabled' : ''}>
                <i class="fas fa-chevron-left"></i> Previous
            </button>
        `;
        nav.appendChild(prevLi);
        
        // Page numbers
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(this.totalPages, this.currentPage + 2);
        
        // Add first page if not in range
        if (startPage > 1) {
            const firstLi = document.createElement('li');
            firstLi.className = 'page-item';
            firstLi.innerHTML = `
                <button class="page-link" onclick="DetectionManager.goToPage(1)">1</button>
            `;
            nav.appendChild(firstLi);
            
            if (startPage > 2) {
                const ellipsisLi = document.createElement('li');
                ellipsisLi.className = 'page-item disabled';
                ellipsisLi.innerHTML = `<span class="page-link">...</span>`;
                nav.appendChild(ellipsisLi);
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === this.currentPage ? 'active' : ''}`;
            li.innerHTML = `
                <button class="page-link" onclick="DetectionManager.goToPage(${i})">${i}</button>
            `;
            nav.appendChild(li);
        }
        
        // Add last page if not in range
        if (endPage < this.totalPages) {
            if (endPage < this.totalPages - 1) {
                const ellipsisLi = document.createElement('li');
                ellipsisLi.className = 'page-item disabled';
                ellipsisLi.innerHTML = `<span class="page-link">...</span>`;
                nav.appendChild(ellipsisLi);
            }
            
            const lastLi = document.createElement('li');
            lastLi.className = 'page-item';
            lastLi.innerHTML = `
                <button class="page-link" onclick="DetectionManager.goToPage(${this.totalPages})">${this.totalPages}</button>
            `;
            nav.appendChild(lastLi);
        }
        
        // Next button
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${this.currentPage === this.totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = `
            <button class="page-link" onclick="DetectionManager.goToPage(${this.currentPage + 1})" ${this.currentPage === this.totalPages ? 'disabled' : ''}>
                Next <i class="fas fa-chevron-right"></i>
            </button>
        `;
        nav.appendChild(nextLi);
    },

    /**
     * Go to specific page
     */
    goToPage: function(page) {
        console.log('goToPage called:', {
            requestedPage: page,
            currentPage: this.currentPage,
            totalPages: this.totalPages,
            isValid: page >= 1 && page <= this.totalPages && page !== this.currentPage
        });
        
        if (page >= 1 && page <= this.totalPages && page !== this.currentPage) {
            this.currentPage = page;
            this.loadResults();
        }
    },

    /**
     * Filter results based on current filters
     */
    filterResults: function(results) {
        let filtered = results;
        
        // Search filter
        if (this.currentFilters.search) {
            const searchTerm = this.currentFilters.search.toLowerCase();
            filtered = filtered.filter(result => {
                const ocrText = result.ocr_text || '';
                const timestamp = result.timestamp || '';
                return ocrText.toLowerCase().includes(searchTerm) || 
                       timestamp.toLowerCase().includes(searchTerm);
            });
        }
        
        // Date filters
        if (this.currentFilters.dateFrom) {
            filtered = filtered.filter(result => {
                const resultDate = new Date(result.timestamp || result.created_at);
                const fromDate = new Date(this.currentFilters.dateFrom);
                return resultDate >= fromDate;
            });
        }
        
        if (this.currentFilters.dateTo) {
            filtered = filtered.filter(result => {
                const resultDate = new Date(result.timestamp || result.created_at);
                const toDate = new Date(this.currentFilters.dateTo);
                toDate.setHours(23, 59, 59); // End of day
                return resultDate <= toDate;
            });
        }
        
        // Vehicle filter
        if (this.currentFilters.hasVehicles) {
            const hasVehicles = this.currentFilters.hasVehicles === 'true';
            filtered = filtered.filter(result => {
                const hasVehiclesResult = (result.vehicles_count || 0) > 0;
                return hasVehiclesResult === hasVehicles;
            });
        }
        
        // Plates filter
        if (this.currentFilters.hasPlates) {
            const hasPlates = this.currentFilters.hasPlates === 'true';
            filtered = filtered.filter(result => {
                const hasPlatesResult = (result.plates_count || 0) > 0;
                return hasPlatesResult === hasPlates;
            });
        }
        
        return filtered;
    },

    /**
     * Paginate results
     */
    paginateResults: function(results) {
        const startIndex = (this.currentPage - 1) * this.perPage;
        const endIndex = startIndex + this.perPage;
        this.totalPages = Math.ceil(results.length / this.perPage);
        return results.slice(startIndex, endIndex);
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
            const hasDetections = (result.vehicles_count || 0) > 0;
            resultDiv.className = `detection-result ${hasDetections ? 'success' : 'no-detection'}`;
            
            resultDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <small class="text-muted">${AICameraUtils.formatTimestamp(result.timestamp || result.created_at)}</small>
                    <div class="badge bg-${hasDetections ? 'success' : 'warning'}">
                        ${result.vehicles_count || 0} vehicles, ${result.plates_count || 0} plates
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
     * Load detection configuration from API
     */
    loadConfiguration: function() {
        AICameraUtils.apiRequest('/detection/config')
            .then(data => {
                if (data && data.success && data.config) {
                    this.updateConfigForm(data.config);
                } else {
                    console.error('Invalid config response:', data);
                }
            })
            .catch(error => {
                console.error('Failed to load configuration:', error);
                this.addLogMessage('Failed to load configuration: ' + error.message, 'error');
            });
    },

    /**
     * Update configuration form with data from API
     */
    updateConfigForm: function(config) {
        const intervalInput = document.getElementById('detection-interval-input');
        const vehicleConfElement = document.getElementById('vehicle-confidence');
        const plateConfElement = document.getElementById('plate-confidence');
        const autoStartElement = document.getElementById('auto-start-setting');
        
        if (intervalInput) intervalInput.value = config.detection_interval || 0.1;
        if (vehicleConfElement) vehicleConfElement.value = config.vehicle_confidence || 0.5;
        if (plateConfElement) plateConfElement.value = config.plate_confidence || 0.3;
        if (autoStartElement) autoStartElement.checked = config.auto_start || false;
    },

    /**
     * Initialize form with current values from status badges
     */
    initializeFormWithCurrentValues: function() {
        // Get current values from status badges
        const intervalBadge = document.getElementById('detection-interval-badge');
        const vehicleConfSpan = document.querySelector('#vehicle-confidence');
        const plateConfSpan = document.querySelector('#plate-confidence');
        
        // Get form inputs
        const intervalInput = document.getElementById('detection-interval-input');
        const vehicleConfInput = document.getElementById('vehicle-confidence');
        const plateConfInput = document.getElementById('plate-confidence');
        
        // Verify elements exist
        console.log('Detection interval elements check:', {
            intervalBadge: !!intervalBadge,
            intervalInput: !!intervalInput,
            vehicleConfSpan: !!vehicleConfSpan,
            vehicleConfInput: !!vehicleConfInput,
            plateConfSpan: !!plateConfSpan,
            plateConfInput: !!plateConfInput
        });
        
        // Set default values from current status
        if (intervalBadge && intervalInput) {
            const intervalText = intervalBadge.textContent;
            const intervalValue = parseFloat(intervalText.replace('s', ''));
            if (!isNaN(intervalValue)) {
                intervalInput.value = intervalValue;
                console.log('Initialized interval input with value:', intervalValue);
            }
        }
        
        if (vehicleConfSpan && vehicleConfInput) {
            const vehicleConfValue = parseFloat(vehicleConfSpan.textContent);
            if (!isNaN(vehicleConfValue)) {
                vehicleConfInput.value = vehicleConfValue;
            }
        }
        
        if (plateConfSpan && plateConfInput) {
            const plateConfValue = parseFloat(plateConfSpan.textContent);
            if (!isNaN(plateConfValue)) {
                plateConfInput.value = plateConfValue;
            }
        }
    },

    /**
     * Handle configuration form submission
     */
    handleConfigSubmit: function(e) {
        e.preventDefault();
        
        // Get form elements with null checks
        const intervalInput = document.getElementById('detection-interval-input');
        const vehicleConfInput = document.getElementById('vehicle-confidence');
        const plateConfInput = document.getElementById('plate-confidence');
        const autoStartElement = document.getElementById('auto-start-setting');
        
        // Check if elements exist
        if (!intervalInput || !vehicleConfInput || !plateConfInput) {
            this.addLogMessage('Configuration form elements not found', 'error');
            return;
        }
        
        const interval = parseFloat(intervalInput.value);
        const vehicleConf = parseFloat(vehicleConfInput.value);
        const plateConf = parseFloat(plateConfInput.value);
        const autoStart = autoStartElement ? autoStartElement.checked : false;
        
        // Validate input values
        if (isNaN(interval) || interval < 0.1 || interval > 1000.0) {
            this.addLogMessage('Invalid detection interval value. Must be between 0.1 and 1000.0', 'error');
            return;
        }
        
        if (isNaN(vehicleConf) || vehicleConf < 0.1 || vehicleConf > 1.0) {
            this.addLogMessage('Invalid vehicle confidence value. Must be between 0.1 and 1.0', 'error');
            return;
        }
        
        if (isNaN(plateConf) || plateConf < 0.1 || plateConf > 1.0) {
            this.addLogMessage('Invalid plate confidence value. Must be between 0.1 and 1.0', 'error');
            return;
        }
        
        console.log('Submitting configuration:', { interval, vehicleConf, plateConf, autoStart });
        
        // Show restart warning
        const restartConfirmed = confirm(
            `การอัพเดตการตั้งค่าจะต้องรีสตาร์ทระบบ\n\n` +
            `ค่าที่จะอัพเดต:\n` +
            `- Detection Interval: ${interval}s\n` +
            `- Vehicle Confidence: ${vehicleConf}\n` +
            `- Plate Confidence: ${plateConf}\n\n` +
            `คุณต้องการดำเนินการต่อหรือไม่?`
        );
        
        if (!restartConfirmed) {
            this.addLogMessage('Configuration update cancelled by user', 'info');
            return;
        }
        
        // Show loading state
        this.addLogMessage('กำลังอัพเดตการตั้งค่าและรีสตาร์ทระบบ...', 'info');
        AICameraUtils.showToast('Updating configuration and restarting service...', 'info');
        
        AICameraUtils.apiRequest('/detection/update-config', {
            method: 'POST',
            body: JSON.stringify({
                detection_interval: interval,
                vehicle_confidence: vehicleConf,
                plate_confidence: plateConf,
                auto_start: autoStart
            })
        })
        .then(data => {
            if (data.success) {
                this.addLogMessage(`Configuration updated successfully. Service restarting...`, 'success');
                AICameraUtils.showToast('Configuration updated! Service restarting...', 'success');
                
                // Show restart progress
                this.showRestartProgress();
                
                // Start polling for service status
                this.pollServiceStatus();
            } else {
                throw new Error(data.error || 'Configuration update failed');
            }
        })
        .catch(error => {
            this.addLogMessage('Failed to update configuration: ' + error.message, 'error');
            AICameraUtils.showToast('Configuration update failed', 'error');
        });
    },

    /**
     * Show restart progress
     */
    showRestartProgress: function() {
        // Create or update progress indicator
        let progressContainer = document.getElementById('restart-progress');
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.id = 'restart-progress';
            progressContainer.className = 'alert alert-info mt-3';
            progressContainer.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm me-2" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div>
                        <strong>กำลังรีสตาร์ทระบบ...</strong>
                        <div class="small text-muted">กรุณารอสักครู่ ระบบจะกลับมาใช้งานได้ในไม่ช้า</div>
                    </div>
                </div>
            `;
            
            // Insert after the form
            const form = document.getElementById('detection-config-form');
            if (form && form.parentNode) {
                form.parentNode.insertBefore(progressContainer, form.nextSibling);
            }
        }
    },

    /**
     * Hide restart progress
     */
    hideRestartProgress: function() {
        const progressContainer = document.getElementById('restart-progress');
        if (progressContainer) {
            progressContainer.remove();
        }
    },

    /**
     * Poll service status after restart
     */
    pollServiceStatus: function() {
        let attempts = 0;
        const maxAttempts = 30; // 30 seconds
        const pollInterval = 1000; // 1 second
        
        const poll = () => {
            attempts++;
            
            AICameraUtils.apiRequest('/detection/status')
                .then(data => {
                    if (data && data.success && data.detection_status) {
                        // Service is back online
                        this.hideRestartProgress();
                        this.updateDetectionStatus(data.detection_status);
                        this.addLogMessage('Service restarted successfully!', 'success');
                        AICameraUtils.showToast('Service restarted successfully!', 'success');
                        return;
                    }
                    
                    if (attempts >= maxAttempts) {
                        this.hideRestartProgress();
                        this.addLogMessage('Service restart timeout. Please check manually.', 'warning');
                        AICameraUtils.showToast('Service restart timeout', 'warning');
                        return;
                    }
                    
                    // Continue polling
                    setTimeout(poll, pollInterval);
                })
                .catch(error => {
                    if (attempts >= maxAttempts) {
                        this.hideRestartProgress();
                        this.addLogMessage('Service restart failed: ' + error.message, 'error');
                        AICameraUtils.showToast('Service restart failed', 'error');
                        return;
                    }
                    
                    // Continue polling even on error (service might be restarting)
                    setTimeout(poll, pollInterval);
                });
        };
        
        // Start polling
        setTimeout(poll, pollInterval);
    },

    /**
     * Clear all filters
     */
    clearFilters: function() {
        this.currentFilters = {};
        this.currentPage = 1;
        
        // Clear form inputs
        const searchInput = document.getElementById('search-input');
        const dateFrom = document.getElementById('date-from');
        const dateTo = document.getElementById('date-to');
        const hasVehicles = document.getElementById('has-vehicles');
        const hasPlates = document.getElementById('has-plates');
        
        if (searchInput) searchInput.value = '';
        if (dateFrom) dateFrom.value = '';
        if (dateTo) dateTo.value = '';
        if (hasVehicles) hasVehicles.value = '';
        if (hasPlates) hasPlates.value = '';
        
        this.loadResults();
        this.addLogMessage('Filters cleared', 'info');
    },

    /**
     * Show export modal
     */
    showExportModal: function() {
        const modal = new bootstrap.Modal(document.getElementById('export-modal'));
        modal.show();
    },

    /**
     * Export results
     */
    exportResults: function() {
        const format = document.getElementById('export-format').value;
        this.addLogMessage(`Exporting results as ${format.toUpperCase()}...`, 'info');
        
        // For now, just show a message
        AICameraUtils.showToast(`Export functionality will be implemented soon`, 'info');
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('export-modal'));
        if (modal) modal.hide();
    },

    /**
     * Handle sorting
     */
    handleSort: function(sortBy) {
        if (this.currentSort.by === sortBy) {
            this.currentSort.order = this.currentSort.order === 'asc' ? 'desc' : 'asc';
        } else {
            this.currentSort.by = sortBy;
            this.currentSort.order = 'asc';
        }
        
        this.loadResults();
    },

    /**
     * Cleanup when leaving page
     */
    cleanup: function() {
        if (this.statusUpdateInterval) {
            clearInterval(this.statusUpdateInterval);
        }
    },

  /**
 * Show detail modal for a specific result
 */
showDetail: function(resultId) {
        // Store current modal instance
        this.currentDetailModal = new bootstrap.Modal(document.getElementById('detail-modal'));
        const modalBody = document.getElementById('detail-modal-body');
        const modal = document.getElementById('detail-modal');
        
        // Store current focus for restoration
        this.previousFocus = document.activeElement;
        
        // Show loading in modal
        modalBody.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="mt-2">Loading detection details...</div>
            </div>
        `;
        
        // Show modal
        this.currentDetailModal.show();
        
        // Add event listeners for proper focus management
        modal.addEventListener('shown.bs.modal', () => {
            // Focus on first focusable element when modal opens
            const firstFocusable = modal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (firstFocusable) {
                firstFocusable.focus();
            }
        });
        
        modal.addEventListener('hidden.bs.modal', () => {
            // Restore focus when modal closes
            if (this.previousFocus && typeof this.previousFocus.focus === 'function') {
                this.previousFocus.focus();
            }
        });

        // Load detailed data from specific detection endpoint
        AICameraUtils.apiRequest(`/detection/results/${resultId}`)
        .then(data => {
            if (data && data.success) {
                this.displayDetailModal(data.result);
            } else {
                modalBody.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Error loading details: ${data?.error || 'Unknown error'}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading detail:', error);
            modalBody.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Network error occurred while loading details.
                </div>
            `;
        });
},

/**
 * Display detail modal content
 */
displayDetailModal: function(result) {
    const modalBody = document.getElementById('detail-modal-body');
    const vehicleConfidence = this.calculateDetectionConfidence(result.vehicle_detections);
    const plateConfidence = this.calculateDetectionConfidence(result.plate_detections);
    
    modalBody.innerHTML = `
        <!-- OCR Results Section - Emphasized -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card border-primary">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0"><i class="fas fa-id-card me-2"></i>License Plate Recognition (LPR) Results</h5>
                    </div>
                    <div class="card-body">
                        ${this.formatOcrResultsForDetail(result)}
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Image Preview Section - Emphasized -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card border-success">
                    <div class="card-header bg-success text-white">
                        <h5 class="mb-0"><i class="fas fa-image me-2"></i>Detection Image Preview</h5>
                    </div>
                    <div class="card-body">
                        ${this.formatImagePreview(result)}
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Metadata Section - Normal -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0"><i class="fas fa-info-circle me-2"></i>Detection Metadata</h6>
                    </div>
                    <div class="card-body">
        <div class="row">
            <div class="col-md-6">
                                <table class="table table-sm table-borderless">
                                    <tr><td><strong>Detection ID:</strong></td><td>#${result.id}</td></tr>
                                    <tr><td><strong>Timestamp:</strong></td><td>${AICameraUtils.formatTimestamp(result.timestamp || result.created_at)}</td></tr>
                                    <tr><td><strong>Processing Time:</strong></td><td>${result.processing_time_ms || 0}ms</td></tr>
                </table>
            </div>
            <div class="col-md-6">
                                <table class="table table-sm table-borderless">
                                    <tr><td><strong>Vehicles Detected:</strong></td><td><span class="badge bg-info">${result.vehicles_count || 0}</span> <small class="text-muted ms-1">(${vehicleConfidence}%)</small></td></tr>
                                    <tr><td><strong>License Plates:</strong></td><td><span class="badge bg-warning">${result.plates_count || 0}</span> <small class="text-muted ms-1">(${plateConfidence}%)</small></td></tr>
                                    <tr><td><strong>OCR Confidence:</strong></td><td><span class="badge bg-success">${this.calculateAverageConfidence(result.ocr_results)}%</span></td></tr>
                                </table>
            </div>
        </div>
            </div>
                </div>
            </div>
        </div>
    `;
    
    // After injecting HTML, initialize any canvases inside the detail modal
    try {
        this.renderPendingCanvases(modalBody);
    } catch (e) {
        console.error('Error initializing canvases after render:', e);
    }
},

/**
 * Format OCR results for detail view - Enhanced
 */
formatOcrResultsForDetail: function(result) {
    const ocrResults = result.ocr_results || [];
    const hailoResults = result.hailo_ocr_results || result.hailoOcrResults || [];
    const easyResults = result.easyocr_results || result.easyOcrResults || [];
    const plateDetections = result.plate_detections || [];
    
    if (ocrResults.length > 0) {
        return `
            <div class="row">
                ${ocrResults.map((ocr, index) => `
                    <div class="col-md-6 mb-3">
                        <div class="card h-100 border-${this.getConfidenceColor(ocr.confidence)}">
                            <div class="card-header bg-${this.getConfidenceColor(ocr.confidence)} text-white">
                                <div class="d-flex justify-content-between align-items-center">
                                    <h6 class="mb-0">Plate #${index + 1}</h6>
                                    <span class="badge bg-light text-dark">${(ocr.confidence * 100).toFixed(1)}%</span>
                                </div>
                            </div>
                            <div class="card-body text-center">
                                <div class="ocr-text-display mb-3">
                                    <h4 class="text-primary font-weight-bold">${ocr.text}</h4>
                                </div>
                                <div class="ocr-details">
                                    <small class="text-muted">
                                        <i class="fas fa-language me-1"></i>Language: ${ocr.language === 'th' ? 'Thai' : 'English'}
                                    </small>
                                    <br>
                                    <small class="text-muted">
                                      <i class="fas fa-brain me-1"></i>Method: ${ocr.ocr_method ? ocr.ocr_method.toUpperCase() : 'Unknown'}
                                    </small>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    if (plateDetections.length > 0) {
        const plateConfidence = this.calculateDetectionConfidence(plateDetections);
        return `
            <div class="alert alert-info">
                <div class="d-flex align-items-center mb-2">
                    <i class="fas fa-info-circle fa-lg me-2"></i>
                    <strong>License plate detected (${plateConfidence}% confidence)</strong>
                </div>
                <p class="text-muted mb-3">Plate detection succeeded, but OCR text was not finalized. Latest OCR engine outputs:</p>
                <div class="row">
                    <div class="col-md-6">
                        <h6 class="text-primary">Hailo OCR</h6>
                        ${this.formatOcrEngineResults(hailoResults)}
                    </div>
                    <div class="col-md-6">
                        <h6 class="text-success">EasyOCR</h6>
                        ${this.formatOcrEngineResults(easyResults)}
                    </div>
                </div>
            </div>
        `;
    }
    
    return `
        <div class="text-center py-4">
            <i class="fas fa-exclamation-triangle fa-3x text-muted mb-3"></i>
            <h6 class="text-muted">No License Plates Detected</h6>
            <p class="text-muted">No OCR results available for this detection.</p>
        </div>
    `;
},

/**
 * Format OCR engine outputs for display
 */
formatOcrEngineResults: function(engineResults) {
    if (!engineResults || engineResults.length === 0) {
        return `<span class="text-muted">No OCR output captured.</span>`;
    }
    
    return engineResults.map((entry, index) => {
        const text = entry?.text || 'N/A';
        const confidence = this.normalizeConfidence(entry?.confidence);
        const success = entry?.success !== false;
        const statusBadge = success
            ? `<span class="badge bg-success ms-2">Success</span>`
            : `<span class="badge bg-danger ms-2">Failed</span>`;
        
        return `
            <div class="border rounded p-2 mb-2">
                <div class="d-flex justify-content-between">
                    <strong>Attempt #${index + 1}</strong>
                    ${statusBadge}
                </div>
                <div class="mt-2">
                    <div><span class="text-muted">Text:</span> ${text}</div>
                    <small class="text-muted"><i class="fas fa-crosshairs me-1"></i>Confidence: ${confidence}%</small>
                </div>
            </div>
        `;
    }).join('');
},

/**
 * Normalize confidence to percentage string
 */
normalizeConfidence: function(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return '0.0';
    }
    
    let percent = value;
    if (percent <= 1) {
        percent *= 100;
    }
    percent = Math.min(Math.max(percent, 0), 100);
    return percent.toFixed(1);
},

/**
 * Format image preview for detail modal - Optimized for disk space
 * Only original image stored, bounding boxes drawn dynamically
 */
formatImagePreview: function(result) {
    const images = [];
    const imageUrls = [];
    
    // Only original image is stored - generate visualization dynamically
    if (result.original_image_path && result.original_image_path !== 'None' && result.original_image_path !== 'null' && result.original_image_path.trim() !== '') {
        const originalUrl = this.resolveImageUrl(result.original_image_path);
        
        // Original image
        images.push({
            type: 'original',
            path: result.original_image_path,
            title: 'Original Captured Image',
            icon: 'fas fa-camera',
            color: 'info',
            description: 'Raw image captured from camera',
            url: originalUrl
        });
        
        // Vehicle detection visualization (drawn dynamically)
        if (result.vehicle_detections && result.vehicle_detections.length > 0) {
            images.push({
                type: 'vehicle_visualization',
                path: result.original_image_path,
                title: 'Vehicle Detection Visualization',
                icon: 'fas fa-car',
                color: 'primary',
                description: 'Original image with vehicle bounding boxes (drawn dynamically)',
                url: originalUrl,
                vehicle_boxes: result.vehicle_detections
            });
        }
        
        // Plate detection visualization (drawn dynamically)
        if (result.plate_detections && result.plate_detections.length > 0) {
            images.push({
                type: 'plate_visualization',
                path: result.original_image_path,
                title: 'License Plate Detection Visualization',
                icon: 'fas fa-id-card',
                color: 'success',
                description: 'Original image with plate bounding boxes & OCR (drawn dynamically)',
                url: originalUrl,
                plate_boxes: result.plate_detections,
                ocr_results: result.ocr_results
            });
        }
        
        // Add to URL list
        imageUrls.push({
            type: 'Original Image',
            path: result.original_image_path,
            url: originalUrl
        });
    }
    
    // Create image URLs summary
    const imageUrlsSection = this.createImageUrlsSection(imageUrls);
    
    if (images.length === 0) {
        return `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                <strong>No Images Available</strong><br>
                <small class="text-muted">
                    Original: ${result.original_image_path || 'Not available'}<br>
                    Vehicle Detection: ${result.vehicle_detected_image_path || 'Not available'}<br>
                    Plate Detection: ${result.plate_image_path || 'Not available'}<br>
                    Cropped Plates: ${result.cropped_plates_paths?.length || 0} available
                </small>
            </div>
            ${imageUrlsSection}
        `;
    }
    
    // Create responsive grid layout
    let imageGrid = '';
    images.forEach((image, index) => {
        const colClass = images.length === 1 ? 'col-12' : 
                       images.length === 2 ? 'col-md-6' : 
                       images.length === 3 ? 'col-md-4' : 'col-md-6 col-lg-3';
        
        imageGrid += `
            <div class="${colClass} mb-3">
                <div class="card h-100 border-${image.color}">
                    <div class="card-header bg-${image.color} text-white">
                        <div class="d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">
                                <i class="${image.icon} me-2"></i>${image.title}
                            </h6>
                            <button class="btn btn-sm btn-light" onclick="DetectionManager.copyImageUrl('${image.url}')" title="Copy URL">
                                <i class="fas fa-link"></i>
                            </button>
                        </div>
                    </div>
                    <div class="card-body text-center p-2">
                        ${this.renderImageWithBoundingBoxes(image)}
                    </div>
                    <div class="card-footer">
                        <div class="text-center">
                            <small class="text-muted">${image.description}</small>
                        </div>
                        <div class="mt-2">
                            <small class="text-muted d-block text-truncate" title="${image.path}">
                                <i class="fas fa-file me-1"></i>${image.path}
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    return `
        <div class="row">
            ${imageGrid}
        </div>
        <div class="mt-3">
            <small class="text-muted">
                <i class="fas fa-info-circle me-1"></i>
                Showing ${images.length} of ${this.getTotalImageCount(result)} available images
            </small>
        </div>
        ${imageUrlsSection}
    `;
},

/**
 * Create image URLs section for easy access
 */
createImageUrlsSection: function(imageUrls) {
    if (imageUrls.length === 0) return '';
    
    const urlList = imageUrls.map(img => `
        <div class="d-flex justify-content-between align-items-center py-1">
            <div>
                <strong>${img.type}:</strong>
                <small class="text-muted ms-2">${img.path}</small>
            </div>
            <div>
                <button class="btn btn-sm btn-outline-primary" onclick="DetectionManager.copyImageUrl('${img.url}')" title="Copy URL">
                    <i class="fas fa-copy"></i>
                </button>
                <button class="btn btn-sm btn-outline-success" onclick="DetectionManager.openImageModal('${img.url}', '${img.type}')" title="Open Image">
                    <i class="fas fa-external-link-alt"></i>
                </button>
            </div>
        </div>
    `).join('');
    
    return `
        <div class="row mt-4">
            <div class="col-12">
                <div class="card border-secondary">
                    <div class="card-header bg-secondary text-white">
                        <h6 class="mb-0">
                            <i class="fas fa-link me-2"></i>Image URLs from Database Record
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-8">
                                ${urlList}
                            </div>
                            <div class="col-md-4">
                                <div class="alert alert-info">
                                    <h6><i class="fas fa-info-circle me-2"></i>Quick Actions</h6>
                                    <button class="btn btn-sm btn-outline-primary w-100 mb-2" onclick="DetectionManager.copyAllImageUrls()">
                                        <i class="fas fa-copy me-1"></i>Copy All URLs
                                    </button>
                                    <button class="btn btn-sm btn-outline-success w-100" onclick="DetectionManager.downloadAllImages()">
                                        <i class="fas fa-download me-1"></i>Download Image
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
},
    
    /**
     * Get total image count for a result
     */
    getTotalImageCount: function(result) {
        let count = 0;
        if (result.original_image_path && result.original_image_path !== 'None') count++;
        if (result.vehicle_detected_image_path && result.vehicle_detected_image_path !== 'None') count++;
        if (result.plate_image_path && result.plate_image_path !== 'None') count++;
        if (result.cropped_plates_paths && result.cropped_plates_paths.length > 0) {
            count += result.cropped_plates_paths.filter(path => path && path !== 'None').length;
        }
        return count;
    },

/**
 * Get confidence color based on confidence level
 */
getConfidenceColor: function(confidence) {
    if (confidence >= 0.9) return 'success';
    if (confidence >= 0.7) return 'warning';
    return 'danger';
},

/**
 * Calculate average confidence from bounding box detections
 */
calculateDetectionConfidence: function(detections) {
    if (!detections || detections.length === 0) return '0.0';
    
    const confidenceValues = detections
        .map(det => {
            if (!det) return null;
            const candidates = [det.confidence, det.score, det.probability, det.conf];
            for (const candidate of candidates) {
                if (typeof candidate === 'number' && !Number.isNaN(candidate)) {
                    return candidate;
                }
                if (typeof candidate === 'string') {
                    const parsed = parseFloat(candidate);
                    if (!Number.isNaN(parsed)) {
                        return parsed;
                    }
                }
            }
            return null;
        })
        .filter(value => typeof value === 'number' && !Number.isNaN(value));
    
    if (!confidenceValues.length) {
        return '0.0';
    }
    
    const average = confidenceValues.reduce((sum, value) => sum + value, 0) / confidenceValues.length;
    let percent = average;
    
    if (percent <= 1) {
        percent *= 100;
    }
    
    percent = Math.min(Math.max(percent, 0), 100);
    return percent.toFixed(1);
},

/**
 * Calculate average confidence from OCR results
 */
calculateAverageConfidence: function(ocrResults) {
    if (!ocrResults || ocrResults.length === 0) return 0;
    const total = ocrResults.reduce((sum, ocr) => sum + ocr.confidence, 0);
    return (total / ocrResults.length * 100).toFixed(1);
},

/**
 * Setup comprehensive output display toggle
 */
setupComprehensiveOutputToggle: function() {
    const toggle = document.getElementById('output-display-toggle');
    const content = document.getElementById('comprehensive-output-content');
    
    if (toggle && content) {
        // Ensure content is visible on page load if toggle is checked
        if (toggle.checked) {
            content.style.display = 'block';
            this.refreshComprehensiveData();
        }
        
        toggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                content.style.display = 'block';
                this.refreshComprehensiveData();
            } else {
                content.style.display = 'none';
            }
        });
    }
},

/**
 * Refresh comprehensive data
 */
refreshComprehensiveData: function() {
    this.updateRealTimeMetrics();
    this.updatePerformanceAnalytics();
    this.updateQualityMetrics();
    // Removed calls to non-existent functions
},

/**
 * Update real-time detection metrics
 */
updateRealTimeMetrics: function() {
    const status = this.lastStatusUpdate || {};
    const statistics = status.statistics || status; // support both nested and flat
    
    // Calculate rates from statistics
    const totalFrames = statistics.total_frames_processed || 0;
    const totalVehicles = statistics.total_vehicles_detected || 0;
    const totalPlates = statistics.total_plates_detected || 0;
    const successfulOcr = statistics.successful_ocr || 0;
    
    const vehicleRate = totalFrames > 0 ? ((totalVehicles / totalFrames) * 100).toFixed(1) : '0';
    const plateRate = totalVehicles > 0 ? ((totalPlates / totalVehicles) * 100).toFixed(1) : '0';
    const ocrRate = totalPlates > 0 ? ((successfulOcr / totalPlates) * 100).toFixed(1) : '0';
    const avgProcessing = (statistics.avg_processing_time_ms !== undefined)
        ? statistics.avg_processing_time_ms
        : ((statistics.processing_time_avg || 0) * 1000);
    
    // Update display: counts and rates
    this.updateElement('vehicles-detected', totalVehicles);
    this.updateElement('plates-detected-count', totalPlates);
    this.updateElement('successful-ocr-count', successfulOcr);
    this.updateElement('plate-detection-rate', plateRate + '%');
    this.updateElement('ocr-success-rate', ocrRate + '%');
    this.updateElement('processing-efficiency', avgProcessing + 'ms');
},

/**
 * Update performance analytics
 */
updatePerformanceAnalytics: function() {
    const status = this.lastStatusUpdate || {};
    const statistics = status.statistics || {};
    
    // Derive FPS from detection interval if current_fps not present
    const interval = status.detection_interval || 0;
    const derivedFps = interval > 0 ? (1 / interval) : 0;
    const fps = (typeof status.current_fps === 'number' ? status.current_fps : 0) || derivedFps;
    const totalFrames = statistics.total_frames_processed || 0;
    const errors = statistics.failed_detections || 0;
    
    // OCR method comparison (optional fields)
    const hailoSuccess = status.hailo_ocr_success_rate || 0;
    const easyocrSuccess = status.easyocr_success_rate || 0;
    const bestMethod = hailoSuccess > easyocrSuccess ? 'Hailo' : 'EasyOCR';
    
    this.updateElement('detection-throughput', fps.toFixed(1) + ' FPS');
    this.updateElement('total-frames-processed', totalFrames);
    this.updateElement('detection-errors-count', errors);
    this.updateElement('hailo-ocr-success', hailoSuccess + '%');
    this.updateElement('easyocr-success', easyocrSuccess + '%');
    this.updateElement('best-ocr-method', bestMethod);
},

/**
 * Update quality metrics
 */
updateQualityMetrics: function() {
    const stats = this.lastStatusUpdate || {};
    
    // Detection accuracy based on confidence
    const detectionAccuracy = stats.detection_accuracy || 0;
    const ocrAccuracy = stats.ocr_accuracy || 0;
    const systemReliability = stats.system_reliability || 0;
    
    // Update progress bars with dynamic colors and percentage values
    this.updateQualityProgressBar('detection-accuracy-bar', 'detection-accuracy-value', detectionAccuracy, 'detection');
    this.updateQualityProgressBar('ocr-accuracy-bar', 'ocr-accuracy-value', ocrAccuracy, 'ocr');
    this.updateQualityProgressBar('system-reliability-bar', 'system-reliability-value', systemReliability, 'reliability');
},

/**
 * Update operational insights
 */
updateOperationalInsights: function() {
    const stats = this.lastStatusUpdate || {};
    
    // Peak detection times
    const peakTimes = stats.peak_detection_times || [];
    const peakTimesElement = document.getElementById('peak-detection-times');
    if (peakTimesElement) {
        if (peakTimes.length > 0) {
            peakTimesElement.innerHTML = peakTimes.map(time => 
                `<div class="badge bg-primary me-1">${time}</div>`
    ).join('');
        } else {
            peakTimesElement.innerHTML = '<p class="text-muted">No peak detection data available</p>';
        }
    }
    
    // Resource utilization
    this.updateElement('cpu-usage', stats.cpu_usage || 'N/A');
    this.updateElement('memory-usage', stats.memory_usage || 'N/A');
    this.updateElement('storage-used', stats.storage_used || 'N/A');
},

/**
 * Update image analysis
 */
updateImageAnalysis: function() {
    // Count images from recent results
    this.loadRecentResults().then(results => {
        let originalCount = 0;
        let vehicleDetectionCount = 0;
        let plateDetectionCount = 0;
        let croppedCount = 0;
        
        results.forEach(result => {
            if (result.original_image_path) originalCount++;
            if (result.vehicle_detected_image_path) vehicleDetectionCount++;
            if (result.plate_image_path) plateDetectionCount++;
            if (result.cropped_plates_paths && result.cropped_plates_paths.length > 0) {
                croppedCount += result.cropped_plates_paths.length;
            }
        });
        
        this.updateElement('original-images-count', originalCount);
        this.updateElement('vehicle-detection-count', vehicleDetectionCount);
        this.updateElement('plate-detection-count', plateDetectionCount);
        this.updateElement('cropped-plates-count', croppedCount);
    });
},

/**
 * Update element by ID
 */
updateElement: function(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    }
},

/**
 * Update progress bar
 */
updateProgressBar: function(elementId, percentage) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.width = percentage + '%';
        element.setAttribute('aria-valuenow', percentage);
    }
},

/**
 * Update quality progress bar with dynamic colors and percentage display
 */
updateQualityProgressBar: function(barId, valueId, percentage, metricType) {
    const barElement = document.getElementById(barId);
    const valueElement = document.getElementById(valueId);
    
    if (barElement && valueElement) {
        // Update progress bar width
        barElement.style.width = percentage + '%';
        barElement.setAttribute('aria-valuenow', percentage);
        
        // Update percentage value display
        valueElement.textContent = percentage + '%';
        
        // Set dynamic colors based on metric type and performance
        let barColor = '';
        let textColor = '';
        
        if (metricType === 'detection') {
            if (percentage >= 80) {
                barColor = 'bg-success';      // Green for excellent
                textColor = 'text-success';
            } else if (percentage >= 60) {
                barColor = 'bg-warning';      // Yellow for good
                textColor = 'text-warning';
            } else if (percentage >= 40) {
                barColor = 'bg-info';         // Blue for fair
                textColor = 'text-info';
            } else {
                barColor = 'bg-danger';       // Red for poor
                textColor = 'text-danger';
            }
        } else if (metricType === 'ocr') {
            if (percentage >= 90) {
                barColor = 'bg-success';      // Green for excellent
                textColor = 'text-success';
            } else if (percentage >= 75) {
                barColor = 'bg-warning';      // Yellow for good
                textColor = 'text-warning';
            } else if (percentage >= 50) {
                barColor = 'bg-info';         // Blue for fair
                textColor = 'text-info';
            } else {
                barColor = 'bg-danger';       // Red for poor
                textColor = 'text-danger';
            }
        } else if (metricType === 'reliability') {
            if (percentage >= 95) {
                barColor = 'bg-success';      // Green for excellent
                textColor = 'text-success';
            } else if (percentage >= 85) {
                barColor = 'bg-warning';      // Yellow for good
                textColor = 'text-warning';
            } else if (percentage >= 70) {
                barColor = 'bg-info';         // Blue for fair
                textColor = 'text-info';
            } else {
                barColor = 'bg-danger';       // Red for poor
                textColor = 'text-danger';
            }
        }
        
        // Apply colors
        barElement.className = `progress-bar ${barColor}`;
        valueElement.className = `h5 fw-bold ${textColor}`;
    }
},

/**
 * Export comprehensive report
 */
exportComprehensiveReport: function() {
    const report = {
        timestamp: new Date().toISOString(),
        realTimeMetrics: {
            vehicleDetectionRate: document.getElementById('vehicle-detection-rate')?.textContent,
            plateDetectionRate: document.getElementById('plate-detection-rate')?.textContent,
            ocrSuccessRate: document.getElementById('ocr-success-rate')?.textContent,
            processingEfficiency: document.getElementById('processing-efficiency')?.textContent
        },
        performanceAnalytics: {
            detectionThroughput: document.getElementById('detection-throughput')?.textContent,
            totalFramesProcessed: document.getElementById('total-frames-processed')?.textContent,
            detectionErrors: document.getElementById('detection-errors-count')?.textContent
        },
        imageAnalysis: {
            annotatedImages: document.getElementById('annotated-images-count')?.textContent,
            originalImages: document.getElementById('original-images-count')?.textContent,
            croppedPlates: document.getElementById('cropped-plates-count')?.textContent
        }
    };
    
    // Create download link
    const dataStr = JSON.stringify(report, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `detection_comprehensive_report_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
},

/**
 * Copy image URL to clipboard
 */
copyImageUrl: function(url) {
    navigator.clipboard.writeText(window.location.origin + url).then(() => {
        AICameraUtils.showToast('Image URL copied to clipboard', 'success');
    }).catch(() => {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = window.location.origin + url;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        AICameraUtils.showToast('Image URL copied to clipboard', 'success');
    });
},

/**
 * Copy all image URLs to clipboard
 */
copyAllImageUrls: function() {
    const imageUrls = [];
    const urlElements = document.querySelectorAll('[onclick*="copyImageUrl"]');
    
    urlElements.forEach(element => {
        const onclick = element.getAttribute('onclick');
        const match = onclick.match(/copyImageUrl\('([^']+)'/);
        if (match) {
            imageUrls.push(window.location.origin + match[1]);
        }
    });
    
    if (imageUrls.length > 0) {
        navigator.clipboard.writeText(imageUrls.join('\n')).then(() => {
            AICameraUtils.showToast(`${imageUrls.length} image URLs copied to clipboard`, 'success');
        }).catch(() => {
            // Fallback
            const textArea = document.createElement('textarea');
            textArea.value = imageUrls.join('\n');
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            AICameraUtils.showToast(`${imageUrls.length} image URLs copied to clipboard`, 'success');
        });
    } else {
        AICameraUtils.showToast('No image URLs found', 'warning');
    }
},

/**
 * Open image in modal for full-size view
 */
openImageModal: function(imageUrl, title) {
    // Create modal if it doesn't exist
    let imageModal = document.getElementById('image-viewer-modal');
    if (!imageModal) {
        imageModal = document.createElement('div');
        imageModal.className = 'modal fade';
        imageModal.id = 'image-viewer-modal';
        imageModal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-image me-2"></i>${title}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img src="" class="img-fluid" alt="Full size image" id="full-size-image">
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="DetectionManager.downloadImage()">
                            <i class="fas fa-download me-1"></i>Download
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(imageModal);
    }
    
    // Update image source
    const img = imageModal.querySelector('#full-size-image');
    img.src = imageUrl;
    img.alt = title;
    
    // Store current image info for download
    this.currentImageInfo = { url: imageUrl, title: title };
    
    // Show modal
    const modal = new bootstrap.Modal(imageModal);
    modal.show();
},

/**
 * Open canvas content in modal for full-size view
 */
openCanvasModal: function(canvasId, title) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        AICameraUtils.showToast('Canvas not found', 'error');
        return;
    }
    
    // Convert canvas to data URL
    const dataUrl = canvas.toDataURL('image/png');
    
    // Create modal if it doesn't exist
    let imageModal = document.getElementById('image-viewer-modal');
    if (!imageModal) {
        imageModal = document.createElement('div');
        imageModal.className = 'modal fade';
        imageModal.id = 'image-viewer-modal';
        imageModal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-image me-2"></i>${title}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img src="" class="img-fluid" alt="Full size image" id="full-size-image">
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="DetectionManager.downloadImage()">
                            <i class="fas fa-download me-1"></i>Download
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(imageModal);
    }
    
    // Update image source with canvas data URL
    const img = imageModal.querySelector('#full-size-image');
    img.src = dataUrl;
    img.alt = title;
    
    // Store current image info for download
    this.currentImageInfo = { url: dataUrl, title: title };
    
    // Show modal
    const modal = new bootstrap.Modal(imageModal);
    modal.show();
},

/**
 * Download current image from modal
 */
downloadImage: function() {
    if (!this.currentImageInfo) {
        AICameraUtils.showToast('No image selected for download', 'warning');
        return;
    }
    
    const link = document.createElement('a');
    link.href = this.currentImageInfo.url;
    
    // Determine file extension based on URL type
    let extension = '.jpg';
    if (this.currentImageInfo.url.startsWith('data:image/png')) {
        extension = '.png';
    }
    
    link.download = this.currentImageInfo.title.replace(/[^a-z0-9]/gi, '_').toLowerCase() + extension;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    AICameraUtils.showToast('Image download started', 'success');
},

/**
 * Download all images from current detection result
 */
downloadAllImages: function() {
    const imageUrls = [];
    const urlElements = document.querySelectorAll('[onclick*="copyImageUrl"]');
    
    urlElements.forEach(element => {
        const onclick = element.getAttribute('onclick');
        const match = onclick.match(/copyImageUrl\('([^']+)'/);
        if (match) {
            imageUrls.push(match[1]);
        }
    });
    
    if (imageUrls.length === 0) {
        AICameraUtils.showToast('No images found to download', 'warning');
        return;
    }
    
    // Download each image
    imageUrls.forEach((url, index) => {
        setTimeout(() => {
            const link = document.createElement('a');
            link.href = url;
            link.download = `detection_image_${index + 1}_${new Date().toISOString().split('T')[0]}.jpg`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }, index * 500); // Stagger downloads
    });
    
    AICameraUtils.showToast(`Downloading ${imageUrls.length} images...`, 'info');
},

/**
 * Resolve image URL from various stored path formats
 * - Supports absolute URLs, absolute paths, and legacy relative paths
 */
resolveImageUrl: function(rawPath) {
    if (!rawPath || typeof rawPath !== 'string') return '';
    const path = rawPath.trim();

    // 1) Already a full URL
    if (/^https?:\/\//i.test(path)) return path;

    // 2) If already an absolute nginx-served path
    if (path.startsWith('/captured_images/')) return path;

    // 3) Common stored variants → normalize to /captured_images/
    if (path.startsWith('captured_images/')) return `/captured_images/${path.substring('captured_images/'.length)}`;

    // 4) Legacy prefixes we have seen in DB (best-effort mapping)
    //    detection_results/2025.../*.jpg → assume files live in captured_images with same basename
    if (path.startsWith('detection_results/')) {
        const base = path.split('/').pop();
        return `/captured_images/${base}`;
    }

    // 5) Absolute filesystem path pointing inside edge/captured_images
    if (path.includes('/captured_images/')) {
        const idx = path.indexOf('/captured_images/');
        return path.substring(idx);
    }

    // 6) Fallback: treat as a basename under captured_images
    return `/captured_images/${path.replace(/^\//, '')}`;
},

/**
 * Render image with dynamic bounding boxes
 */
renderImageWithBoundingBoxes: function(image) {
    if (image.type === 'original') {
        // Original image - no bounding boxes
        return `
            <img src="${image.url}" 
                 class="img-fluid rounded" 
                 style="max-height: 200px; object-fit: contain; cursor: pointer;"
                 alt="${image.title}"
                 onclick="DetectionManager.openImageModal('${image.url}', '${image.title}')"
                 onerror="this.parentElement.innerHTML='<div class=\\'text-muted\\'><i class=\\'fas fa-image fa-2x mb-2\\'></i><br>Image not found<br><small>${image.path} → ${image.url}</small></div>'">
        `;
    } else if (image.type === 'vehicle_visualization' || image.type === 'plate_visualization') {
        // Image with bounding boxes - use canvas for dynamic rendering
        const canvasId = `canvas-${image.type}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const boxes = image.type === 'vehicle_visualization' ? image.vehicle_boxes : image.plate_boxes;
        const ocrResults = image.ocr_results || [];
        
        // Store data for canvas rendering
        this.canvasData = this.canvasData || {};
        this.canvasData[canvasId] = {
            imageUrl: image.url,
            boxes: boxes,
            ocrResults: ocrResults,
            type: image.type
        };
        
        return `
            <div class="position-relative">
                <canvas id="${canvasId}" 
                        class="img-fluid rounded" 
                        style="max-height: 200px; object-fit: contain; cursor: pointer;"
                        onclick="DetectionManager.openCanvasModal('${canvasId}', '${image.title}')">
                </canvas>
                <div class="position-absolute top-0 start-0 p-2">
                    <span class="badge bg-${image.type === 'vehicle_visualization' ? 'primary' : 'success'}">
                        ${boxes.length} ${image.type === 'vehicle_visualization' ? 'Vehicle' : 'Plate'}${boxes.length !== 1 ? 's' : ''}
                    </span>
                </div>
            </div>
        `;
    }
    
    // Fallback for unknown types
    return `
        <img src="${image.url}" 
             class="img-fluid rounded" 
             style="max-height: 200px; object-fit: contain; cursor: pointer;"
             alt="${image.title}"
             onclick="DetectionManager.openImageModal('${image.url}', '${image.title}')"
             onerror="this.parentElement.innerHTML='<div class=\\'text-muted\\'><i class=\\'fas fa-image fa-2x mb-2\\'></i><br>Image not found<br><small>${image.path} → ${image.url}</small></div>'">
    `;
},

/**
 * Render all pending canvases within a container by using stored canvasData
 * This ensures canvases render even when HTML is injected via innerHTML
 */
renderPendingCanvases: function(container) {
    if (!container) return;
    this.canvasData = this.canvasData || {};
    const canvases = container.querySelectorAll('canvas[id^="canvas-"]');
    canvases.forEach((canvas) => {
        const data = this.canvasData[canvas.id];
        if (!data || !data.imageUrl) return;
        const img = new Image();
        img.onload = () => {
            try {
                this.drawBoundingBoxes(canvas, img, data.boxes || [], data.ocrResults || [], data.type || 'vehicle_visualization');
            } catch (e) {
                console.error('Error drawing bounding boxes for', canvas.id, e);
            }
        };
        img.onerror = () => {
            console.error('Failed to load image for canvas', canvas.id, data.imageUrl);
            if (canvas.parentElement) {
                canvas.parentElement.innerHTML = '<div class="text-muted"><i class="fas fa-exclamation-triangle fa-2x mb-2"></i><br>Image failed to load<br><small>' + (data.imageUrl || '') + '</small></div>';
            }
        };
        // Start loading
        img.src = data.imageUrl;
    });
},

/**
 * Draw bounding boxes on canvas
 */
drawBoundingBoxes: function(canvas, img, boxes, ocrResults, type) {
    const ctx = canvas.getContext('2d');
    
    console.log('drawBoundingBoxes called:', {
        canvasId: canvas.id,
        imgSize: img.width + 'x' + img.height,
        boxesCount: boxes.length,
        type: type
    });
    
    // Set canvas size to match image
    canvas.width = img.width;
    canvas.height = img.height;
    
    // Draw the original image
    ctx.drawImage(img, 0, 0);
    
    // Draw bounding boxes
    boxes.forEach((box, index) => {
        let x, y, width, height;
        
        // Handle different bbox formats
        if (box.bbox && Array.isArray(box.bbox)) {
            // Format: bbox: [x1, y1, x2, y2]
            x = box.bbox[0];
            y = box.bbox[1];
            width = box.bbox[2] - x;
            height = box.bbox[3] - y;
        } else if (box.x !== undefined && box.y !== undefined) {
            // Format: {x, y, width, height}
            x = box.x;
            y = box.y;
            width = box.width || 0;
            height = box.height || 0;
        } else if (box.x1 !== undefined && box.y1 !== undefined) {
            // Format: {x1, y1, x2, y2}
            x = box.x1;
            y = box.y1;
            width = (box.x2 || 0) - x;
            height = (box.y2 || 0) - y;
        } else {
            // Fallback
            x = 0;
            y = 0;
            width = 0;
            height = 0;
        }
        
        // Box color based on type
        const color = type === 'vehicle_visualization' ? '#007bff' : '#28a745';
        const lineWidth = 2;
        
        // Draw rectangle
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.strokeRect(x, y, width, height);
        
        // Draw label background
        const label = type === 'vehicle_visualization' ? `Vehicle ${index + 1}` : 
                     (ocrResults[index] ? ocrResults[index].text : `Plate ${index + 1}`);
        
        ctx.font = '12px Arial';
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 20, ctx.measureText(label).width + 10, 20);
        
        // Draw label text
        ctx.fillStyle = 'white';
        ctx.fillText(label, x + 5, y - 5);
        
        // Draw confidence if available
        if (ocrResults[index] && ocrResults[index].confidence) {
            const confText = `${(ocrResults[index].confidence * 100).toFixed(1)}%`;
            ctx.fillStyle = color;
            ctx.fillRect(x + width - ctx.measureText(confText).width - 10, y + height, ctx.measureText(confText).width + 10, 20);
            ctx.fillStyle = 'white';
            ctx.fillText(confText, x + width - ctx.measureText(confText).width - 5, y + height + 15);
        }
    });
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
