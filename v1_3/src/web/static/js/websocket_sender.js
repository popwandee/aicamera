/**
 * AI Camera v1.3 - WebSocket Sender Dashboard JavaScript
 * WebSocket sender management and monitoring functionality
 */

// WebSocket Sender Dashboard Manager
const WebSocketSenderManager = {
    socket: null,
    currentPage: 1,
    logsPerPage: 50,
    currentFilter: '',
    statusUpdateInterval: null,
    
    /**
     * Initialize WebSocket sender dashboard
     */
    init: function() {
        console.log('Initializing WebSocket Sender Dashboard...');
        
        this.setupWebSocket();
        this.setupEventHandlers();
        this.loadInitialData();
        this.setupStatusUpdates();
        
        console.log('WebSocket Sender Dashboard initialized');
    },

    /**
     * Setup WebSocket connection for real-time updates
     */
    setupWebSocket: function() {
        if (typeof io !== 'undefined') {
            this.socket = io('/websocket_sender');
            this.setupSocketHandlers();
        } else {
            console.warn('Socket.IO not available');
        }
    },

    /**
     * Setup WebSocket event handlers
     */
    setupSocketHandlers: function() {
        if (!this.socket) return;

        this.socket.on('connect', () => {
            console.log('Connected to WebSocket sender service');
            this.joinRoom();
        });

        this.socket.on('websocket_sender_status_update', (status) => {
            this.updateStatusDisplay(status);
        });

        this.socket.on('websocket_sender_logs_update', (data) => {
            this.updateLogsTable(data);
        });

        this.socket.on('websocket_sender_control_response', (response) => {
            this.handleControlResponse(response);
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from WebSocket sender service');
        });
    },

    /**
     * Join WebSocket sender room for updates
     */
    joinRoom: function() {
        if (this.socket) {
            this.socket.emit('join_websocket_sender_room');
        }
    },

    /**
     * Setup event handlers for UI elements
     */
    setupEventHandlers: function() {
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.refreshData();
        });

        // Control buttons
        document.getElementById('start-btn').addEventListener('click', () => {
            this.startService();
        });

        document.getElementById('stop-btn').addEventListener('click', () => {
            this.stopService();
        });

        document.getElementById('test-connection-btn').addEventListener('click', () => {
            this.testConnection();
        });

        document.getElementById('clear-logs-btn').addEventListener('click', () => {
            this.clearLogs();
        });

        // Log filter
        document.getElementById('log-filter').addEventListener('change', (e) => {
            this.currentFilter = e.target.value;
            this.currentPage = 1;
            this.loadLogs();
        });

        // Pagination buttons
        document.getElementById('prev-page-btn').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadLogs();
            }
        });

        document.getElementById('next-page-btn').addEventListener('click', () => {
            this.currentPage++;
            this.loadLogs();
        });
    },

    /**
     * Load initial data
     */
    loadInitialData: function() {
        this.loadStatus();
        this.loadLogs();
    },

    /**
     * Setup periodic status updates
     */
    setupStatusUpdates: function() {
        // Update status every 10 seconds
        this.statusUpdateInterval = setInterval(() => {
            this.loadStatus();
        }, 10000);
    },

    /**
     * Load WebSocket sender status
     */
    loadStatus: function() {
        AICameraUtils.apiRequest('/websocket-sender/status')
            .then(data => {
                if (data.success) {
                    this.updateStatusDisplay(data.status);
                } else {
                    console.error('Failed to load status:', data.error);
                    this.showError('Failed to load WebSocket sender status');
                }
            })
            .catch(error => {
                console.error('Error loading status:', error);
                this.showError('Error loading WebSocket sender status');
            });
    },

    /**
     * Load WebSocket sender logs
     */
    loadLogs: function() {
        const params = new URLSearchParams({
            page: this.currentPage,
            limit: this.logsPerPage
        });

        if (this.currentFilter) {
            params.append('filter', this.currentFilter);
        }

        AICameraUtils.apiRequest(`/websocket-sender/logs?${params}`)
            .then(data => {
                if (data.success) {
                    this.updateLogsTable(data);
                } else {
                    console.error('Failed to load logs:', data.error);
                    this.showError('Failed to load WebSocket sender logs');
                }
            })
            .catch(error => {
                console.error('Error loading logs:', error);
                this.showError('Error loading WebSocket sender logs');
            });
    },

    /**
     * Update status display
     */
    updateStatusDisplay: function(status) {
        // Connection status
        const connectionIcon = document.getElementById('connection-icon');
        const connectionStatus = document.getElementById('connection-status');
        
        if (status.connected) {
            connectionIcon.className = 'fas fa-plug status-icon connected';
            connectionStatus.textContent = 'Connected';
            connectionStatus.className = 'card-text status-text connected';
        } else {
            connectionIcon.className = 'fas fa-plug status-icon disconnected';
            connectionStatus.textContent = 'Disconnected';
            connectionStatus.className = 'card-text status-text disconnected';
        }

        // Service status
        const serviceIcon = document.getElementById('service-icon');
        const serviceStatus = document.getElementById('service-status');
        
        if (status.running) {
            serviceIcon.className = 'fas fa-play-circle status-icon connected';
            serviceStatus.textContent = 'Running';
            serviceStatus.className = 'card-text status-text connected';
        } else {
            serviceIcon.className = 'fas fa-stop-circle status-icon disconnected';
            serviceStatus.textContent = 'Stopped';
            serviceStatus.className = 'card-text status-text disconnected';
        }

        // Detection sent count
        const detectionIcon = document.getElementById('detection-icon');
        const detectionSent = document.getElementById('detection-sent');
        detectionIcon.className = 'fas fa-chart-line status-icon info';
        detectionSent.textContent = status.total_detections_sent || 0;
        detectionSent.className = 'card-text status-text info';

        // Health sent count
        const healthIcon = document.getElementById('health-icon');
        const healthSent = document.getElementById('health-sent');
        healthIcon.className = 'fas fa-heartbeat status-icon info';
        healthSent.textContent = status.total_health_sent || 0;
        healthSent.className = 'card-text status-text info';

        // Control panel fields
        document.getElementById('server-url').value = status.server_url || 'Not configured';
        document.getElementById('retry-count').value = status.retry_count || 0;
        document.getElementById('aicamera-id').value = status.aicamera_id || 'Not configured';
        document.getElementById('checkpoint-id').value = status.checkpoint_id || 'Not configured';

        // Update button states
        this.updateButtonStates(status);
    },

    /**
     * Update button states based on service status
     */
    updateButtonStates: function(status) {
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        const testBtn = document.getElementById('test-connection-btn');

        if (status.running) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }

        testBtn.disabled = false;
    },

    /**
     * Update logs table
     */
    updateLogsTable: function(data) {
        const tbody = document.getElementById('logs-table-body');
        
        if (!data.logs || data.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center">No logs found</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        
        data.logs.forEach(log => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${this.formatTimestamp(log.timestamp)}</td>
                <td>${this.formatAction(log.action)}</td>
                <td>${log.data_type || '-'}</td>
                <td><span class="status-badge ${this.getStatusBadgeClass(log.status)}">${log.status}</span></td>
                <td>${log.message || '-'}</td>
                <td>${log.record_count || 0}</td>
                <td>${log.aicamera_id || '-'}</td>
                <td>${log.checkpoint_id || '-'}</td>
            `;
            tbody.appendChild(row);
        });

        // Update pagination info
        this.updatePaginationInfo(data);
    },

    /**
     * Update pagination information
     */
    updatePaginationInfo: function(data) {
        const logsInfo = document.getElementById('logs-info');
        const pageInfo = document.getElementById('page-info');
        const prevBtn = document.getElementById('prev-page-btn');
        const nextBtn = document.getElementById('next-page-btn');

        const totalPages = Math.ceil(data.total_logs / this.logsPerPage);
        const startRecord = (this.currentPage - 1) * this.logsPerPage + 1;
        const endRecord = Math.min(this.currentPage * this.logsPerPage, data.total_logs);

        logsInfo.textContent = `Showing ${startRecord}-${endRecord} of ${data.total_logs} logs`;
        pageInfo.textContent = `Page ${this.currentPage} of ${totalPages}`;

        prevBtn.disabled = this.currentPage <= 1;
        nextBtn.disabled = this.currentPage >= totalPages;
    },

    /**
     * Format timestamp for display
     */
    formatTimestamp: function(timestamp) {
        if (!timestamp) return '-';
        const date = new Date(timestamp);
        return date.toLocaleString();
    },

    /**
     * Format action for display
     */
    formatAction: function(action) {
        const actionMap = {
            'send_detection': 'Detection Sending',
            'send_health': 'Health Sending',
            'connection': 'Connection',
            'error': 'Error'
        };
        return actionMap[action] || action;
    },

    /**
     * Get status badge CSS class
     */
    getStatusBadgeClass: function(status) {
        const statusMap = {
            'success': 'success',
            'error': 'error',
            'warning': 'warning',
            'info': 'info',
            'no_data': 'no-data'
        };
        return statusMap[status] || 'info';
    },

    /**
     * Start WebSocket sender service
     */
    startService: function() {
        this.showLoading('Starting WebSocket sender service...');
        
        AICameraUtils.apiRequest('/websocket-sender/start', {
            method: 'POST'
        })
        .then(data => {
            this.hideLoading();
            if (data.success) {
                this.showSuccess('WebSocket sender service started successfully');
                this.loadStatus();
            } else {
                this.showError(data.error || 'Failed to start service');
            }
        })
        .catch(error => {
            this.hideLoading();
            console.error('Error starting service:', error);
            this.showError('Error starting WebSocket sender service');
        });
    },

    /**
     * Stop WebSocket sender service
     */
    stopService: function() {
        this.showLoading('Stopping WebSocket sender service...');
        
        AICameraUtils.apiRequest('/websocket-sender/stop', {
            method: 'POST'
        })
        .then(data => {
            this.hideLoading();
            if (data.success) {
                this.showSuccess('WebSocket sender service stopped successfully');
                this.loadStatus();
            } else {
                this.showError(data.error || 'Failed to stop service');
            }
        })
        .catch(error => {
            this.hideLoading();
            console.error('Error stopping service:', error);
            this.showError('Error stopping WebSocket sender service');
        });
    },

    /**
     * Test WebSocket connection
     */
    testConnection: function() {
        this.showLoading('Testing WebSocket connection...');
        
        AICameraUtils.apiRequest('/websocket-sender/connection-test', {
            method: 'POST'
        })
        .then(data => {
            this.hideLoading();
            if (data.success) {
                this.showSuccess('Connection test successful');
            } else {
                this.showError(data.error || 'Connection test failed');
            }
        })
        .catch(error => {
            this.hideLoading();
            console.error('Error testing connection:', error);
            this.showError('Error testing WebSocket connection');
        });
    },

    /**
     * Clear logs
     */
    clearLogs: function() {
        if (!confirm('Are you sure you want to clear all WebSocket sender logs?')) {
            return;
        }

        this.showLoading('Clearing logs...');
        
        // Note: This endpoint might not exist yet, implement if needed
        AICameraUtils.apiRequest('/websocket-sender/clear-logs', {
            method: 'POST'
        })
        .then(data => {
            this.hideLoading();
            if (data.success) {
                this.showSuccess('Logs cleared successfully');
                this.loadLogs();
            } else {
                this.showError(data.error || 'Failed to clear logs');
            }
        })
        .catch(error => {
            this.hideLoading();
            console.error('Error clearing logs:', error);
            this.showError('Error clearing logs');
        });
    },

    /**
     * Refresh all data
     */
    refreshData: function() {
        this.loadStatus();
        this.loadLogs();
        this.showSuccess('Data refreshed');
    },

    /**
     * Handle control response from WebSocket
     */
    handleControlResponse: function(response) {
        if (response.success) {
            this.showSuccess(response.message || 'Operation completed successfully');
            this.loadStatus();
        } else {
            this.showError(response.error || 'Operation failed');
        }
    },

    /**
     * Show loading state
     */
    showLoading: function(message) {
        AICameraUtils.showToast(message, 'info');
    },

    /**
     * Hide loading state
     */
    hideLoading: function() {
        // Loading state is handled by toast notifications
    },

    /**
     * Show success message
     */
    showSuccess: function(message) {
        AICameraUtils.showToast(message, 'success');
    },

    /**
     * Show error message
     */
    showError: function(message) {
        AICameraUtils.showToast(message, 'error');
    },

    /**
     * Cleanup when leaving page
     */
    cleanup: function() {
        if (this.statusUpdateInterval) {
            clearInterval(this.statusUpdateInterval);
        }
        
        if (this.socket) {
            this.socket.emit('leave_websocket_sender_room');
            this.socket.disconnect();
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    WebSocketSenderManager.init();
    
    window.addEventListener('beforeunload', function() {
        WebSocketSenderManager.cleanup();
    });
    
    console.log('WebSocket Sender Dashboard JavaScript loaded');
});
