/**
 * AI Camera v1.3 - Storage Management JavaScript
 * Handles storage monitoring, cleanup, and configuration management
 */

// Storage Manager state management
const StorageManager = {
    socket: null,
    statusUpdateInterval: null,
    currentStatus: null,
    isMonitoring: false,
    
    /**
     * Initialize storage manager
     */
    init: function() {
        this.initializeWebSocket();
        this.setupEventHandlers();
        this.loadInitialStatus();
        console.log('StorageManager initialized');
    },

    /**
     * Initialize WebSocket connection
     */
    initializeWebSocket: function() {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not available');
            return;
        }
        
        console.log('Initializing WebSocket connection to main namespace');
        this.socket = io();  // Use main namespace instead of /storage
        this.setupSocketHandlers();
        
        // Test connection
        this.socket.on('connect', () => {
            console.log('Storage WebSocket connected successfully');
            AICameraUtils.showToast('Storage service connected', 'success');
        });
        
        this.socket.on('disconnect', () => {
            console.log('Storage WebSocket disconnected');
            AICameraUtils.showToast('Storage service disconnected', 'warning');
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('Storage WebSocket connection error:', error);
            AICameraUtils.showToast('Storage service connection failed', 'error');
        });
    },

    /**
     * Setup WebSocket event handlers
     */
    setupSocketHandlers: function() {
        if (!this.socket) return;

        this.socket.on('connect', () => {
            console.log('Connected to storage service');
            AICameraUtils.addLogMessage('alerts-container', 'Connected to storage service', 'success');
        });

        this.socket.on('storage_status_response', (data) => {
            this.updateStorageStatus(data);
        });

        this.socket.on('storage_analytics_response', (data) => {
            this.updateAnalytics(data);
        });

        this.socket.on('storage_cleanup_response', (data) => {
            this.handleCleanupResponse(data);
        });

        this.socket.on('storage_config_response', (data) => {
            this.handleConfigResponse(data);
        });

        this.socket.on('storage_monitor_response', (data) => {
            this.handleMonitorResponse(data);
        });

        this.socket.on('storage_alerts_response', (data) => {
            this.updateAlerts(data);
        });

        this.socket.on('storage_room_joined', (data) => {
            console.log('Joined storage monitoring room');
        });

        this.socket.on('storage_room_left', (data) => {
            console.log('Left storage monitoring room');
        });
    },

    /**
     * Setup event handlers for UI elements
     */
    setupEventHandlers: function() {
        // Toggle monitoring button
        const toggleBtn = document.getElementById('toggle-monitoring-btn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                this.toggleMonitoring();
            });
        }

        // Manual cleanup button
        const cleanupBtn = document.getElementById('manual-cleanup-btn');
        if (cleanupBtn) {
            cleanupBtn.addEventListener('click', () => {
                this.performManualCleanup();
            });
        }

        // Refresh status button
        const refreshBtn = document.getElementById('refresh-status-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshStatus();
            });
        }

        // Get analytics button
        const analyticsBtn = document.getElementById('get-analytics-btn');
        if (analyticsBtn) {
            analyticsBtn.addEventListener('click', () => {
                this.getAnalytics();
            });
        }

        // Clear alerts button
        const clearAlertsBtn = document.getElementById('clear-alerts-btn');
        if (clearAlertsBtn) {
            clearAlertsBtn.addEventListener('click', () => {
                this.clearAlerts();
            });
        }

        // Configuration form
        const configForm = document.getElementById('storage-config-form');
        if (configForm) {
            configForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.updateConfiguration();
            });
        }
    },

    /**
     * Load initial storage status
     */
    loadInitialStatus: function() {
        console.log('Loading initial storage status...');
        
        // Add loading indicators
        this.showLoadingIndicators();
        
        // Request status with retry mechanism
        this.requestStorageStatusWithRetry();
        this.requestAlerts();
    },

    /**
     * Show loading indicators
     */
    showLoadingIndicators: function() {
        const elements = [
            'disk-usage-text',
            'free-space-gb', 
            'total-files',
            'folder-size-text',
            'sent-files-count',
            'unsent-files-count',
            'files-deleted-count',
            'space-freed-gb'
        ];
        
        elements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = 'Loading...';
            }
        });
    },

    /**
     * Request storage status with retry mechanism
     */
    requestStorageStatusWithRetry: function(retryCount = 0) {
        const maxRetries = 3;
        
        this.requestStorageStatus()
            .catch(error => {
                console.error(`Storage status request failed (attempt ${retryCount + 1}):`, error);
                
                if (retryCount < maxRetries) {
                    console.log(`Retrying in 2 seconds... (${retryCount + 1}/${maxRetries})`);
                    setTimeout(() => {
                        this.requestStorageStatusWithRetry(retryCount + 1);
                    }, 2000);
                } else {
                    console.error('Max retries reached, showing error state');
                    this.showErrorState();
                }
            });
    },

    /**
     * Show error state
     */
    showErrorState: function() {
        const elements = [
            'disk-usage-text',
            'free-space-gb', 
            'total-files',
            'folder-size-text',
            'sent-files-count',
            'unsent-files-count',
            'files-deleted-count',
            'space-freed-gb'
        ];
        
        elements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = 'Error';
                element.className = element.className + ' text-danger';
            }
        });
        
        AICameraUtils.showToast('Failed to load storage status', 'error');
    },

    /**
     * Request storage status via WebSocket
     */
    requestStorageStatus: function() {
        return new Promise((resolve, reject) => {
            if (this.socket) {
                this.socket.emit('storage_status_request');
                
                // Set up one-time listener for response
                const responseHandler = (data) => {
                    this.socket.off('storage_status_response', responseHandler);
                    if (data && data.success) {
                        resolve(data);
                    } else {
                        reject(new Error(data?.error || 'Storage status request failed'));
                    }
                };
                
                this.socket.on('storage_status_response', responseHandler);
                
                // Timeout after 10 seconds
                setTimeout(() => {
                    this.socket.off('storage_status_response', responseHandler);
                    reject(new Error('Storage status request timeout'));
                }, 10000);
                
            } else {
                // Fallback to HTTP API
                this.loadStatusFromAPI()
                    .then(resolve)
                    .catch(reject);
            }
        });
    },

    /**
     * Load status from HTTP API
     */
    loadStatusFromAPI: function() {
        return AICameraUtils.apiRequest('/storage/status')
            .then(data => {
                this.updateStorageStatus(data);
                return data;
            })
            .catch(error => {
                console.error('Failed to load storage status:', error);
                AICameraUtils.addLogMessage('alerts-container', 'Failed to load storage status: ' + error.message, 'error');
                throw error;
            });
    },

    /**
     * Update storage status display
     */
    updateStorageStatus: function(data) {
        console.log('Updating storage status with data:', data);
        
        if (!data || !data.success) {
            console.warn('Invalid storage status data:', data);
            AICameraUtils.showToast('Failed to load storage status: ' + (data?.error || 'Unknown error'), 'error');
            return;
        }

        this.currentStatus = data.data;
        const status = data.data;
        
        console.log('Processing status data:', status);

        // Update disk usage
        this.updateDiskUsage(status.disk_usage);
        
        // Update file counts
        this.updateFileCounts(status.file_counts);
        
        // Update folder stats
        this.updateFolderStats(status.folder_stats);
        
        // Update cleanup stats
        this.updateCleanupStats(status.cleanup_stats);
        
        // Update configuration form
        this.updateConfigurationForm(status.configuration);
        
        // Update monitoring status
        this.updateMonitoringStatus(status.status);
        
        // Update recommendations
        this.updateRecommendations(status);
    },

    /**
     * Update disk usage display
     */
    updateDiskUsage: function(diskUsage) {
        console.log('Updating disk usage with:', diskUsage);
        
        if (!diskUsage) {
            console.warn('No disk usage data provided');
            return;
        }

        const progressBar = document.getElementById('disk-usage-progress');
        const usageText = document.getElementById('disk-usage-text');
        const freeSpaceElement = document.getElementById('free-space-gb');
        
        if (!progressBar || !usageText || !freeSpaceElement) {
            console.warn('Required disk usage elements not found');
            return;
        }

        if (progressBar) {
            const usagePercent = diskUsage.usage_percentage || 0;
            progressBar.style.width = usagePercent + '%';
            progressBar.textContent = usagePercent.toFixed(1) + '%';
            
            // Set color based on usage
            if (usagePercent > 90) {
                progressBar.className = 'progress-bar bg-danger';
            } else if (usagePercent > 75) {
                progressBar.className = 'progress-bar bg-warning';
            } else {
                progressBar.className = 'progress-bar bg-success';
            }
        }

        if (usageText) {
            usageText.textContent = `${diskUsage.used_gb?.toFixed(1) || 0} GB used of ${diskUsage.total_gb?.toFixed(1) || 0} GB`;
        }

        if (freeSpaceElement) {
            freeSpaceElement.textContent = (diskUsage.free_gb || 0).toFixed(1);
        }
    },

    /**
     * Update file counts display
     */
    updateFileCounts: function(fileCounts) {
        console.log('Updating file counts with:', fileCounts);
        
        if (!fileCounts) {
            console.warn('No file counts data provided');
            return;
        }

        const sentFilesElement = document.getElementById('sent-files-count');
        const unsentFilesElement = document.getElementById('unsent-files-count');
        const totalFilesElement = document.getElementById('total-files');
        
        if (!sentFilesElement || !unsentFilesElement || !totalFilesElement) {
            console.warn('Required file count elements not found');
            return;
        }

        if (sentFilesElement) {
            sentFilesElement.textContent = fileCounts.sent_files || 0;
        }

        if (unsentFilesElement) {
            unsentFilesElement.textContent = fileCounts.unsent_files || 0;
        }

        if (totalFilesElement) {
            totalFilesElement.textContent = fileCounts.total_files || 0;
        }
    },

    /**
     * Update folder stats display
     */
    updateFolderStats: function(folderStats) {
        if (!folderStats) return;

        const folderSizeText = document.getElementById('folder-size-text');
        if (folderSizeText) {
            folderSizeText.textContent = `${(folderStats.total_size_mb || 0).toFixed(1)} MB`;
        }
    },

    /**
     * Update cleanup stats display
     */
    updateCleanupStats: function(cleanupStats) {
        if (!cleanupStats) return;

        const filesDeletedElement = document.getElementById('files-deleted-count');
        const spaceFreedElement = document.getElementById('space-freed-gb');

        if (filesDeletedElement) {
            filesDeletedElement.textContent = cleanupStats.total_files_deleted || 0;
        }

        if (spaceFreedElement) {
            spaceFreedElement.textContent = (cleanupStats.disk_space_freed_gb || 0).toFixed(2);
        }
    },

    /**
     * Update configuration form
     */
    updateConfigurationForm: function(config) {
        if (!config) return;

        const minFreeSpaceInput = document.getElementById('min-free-space');
        const retentionDaysInput = document.getElementById('retention-days');
        const batchSizeInput = document.getElementById('batch-size');
        const monitorIntervalInput = document.getElementById('monitor-interval');

        if (minFreeSpaceInput) {
            minFreeSpaceInput.value = config.min_free_space_gb || 10;
        }

        if (retentionDaysInput) {
            retentionDaysInput.value = config.retention_days || 7;
        }

        if (batchSizeInput) {
            batchSizeInput.value = config.batch_size || 100;
        }

        if (monitorIntervalInput) {
            monitorIntervalInput.value = config.monitor_interval || 300;
        }
    },

    /**
     * Update monitoring status display
     */
    updateMonitoringStatus: function(status) {
        console.log('Updating monitoring status with:', status);
        
        if (!status) {
            console.warn('No monitoring status provided');
            return;
        }

        const monitoringStatus = document.getElementById('monitoring-status');
        const monitoringText = document.getElementById('monitoring-text');
        const toggleBtn = document.getElementById('toggle-monitoring-btn');

        this.isMonitoring = status.running || false;
        console.log('Monitoring status:', this.isMonitoring);

        if (monitoringStatus) {
            const statusDot = monitoringStatus.querySelector('.status-dot');
            if (statusDot) {
                statusDot.className = this.isMonitoring ? 'status-dot status-online' : 'status-dot status-offline';
                console.log('Updated status dot class:', statusDot.className);
            }
        }

        if (monitoringText) {
            monitoringText.textContent = this.isMonitoring ? 'Running' : 'Stopped';
            console.log('Updated monitoring text:', monitoringText.textContent);
        }

        if (toggleBtn) {
            toggleBtn.textContent = this.isMonitoring ? 'Stop Monitoring' : 'Start Monitoring';
            toggleBtn.className = this.isMonitoring ? 'btn btn-sm btn-outline-danger mt-2' : 'btn btn-sm btn-outline-primary mt-2';
            console.log('Updated toggle button:', toggleBtn.textContent);
        }
    },

    /**
     * Update recommendations display
     */
    updateRecommendations: function(status) {
        const recommendationsContainer = document.getElementById('recommendations-container');
        if (!recommendationsContainer) return;

        const diskUsage = status.disk_usage;
        const recommendations = [];

        if (diskUsage && diskUsage.free_gb < 5.0) {
            recommendations.push({
                level: 'danger',
                text: `CRITICAL: Very low disk space (${diskUsage.free_gb.toFixed(1)} GB free). Consider immediate cleanup.`
            });
        } else if (diskUsage && diskUsage.free_gb < 10.0) {
            recommendations.push({
                level: 'warning',
                text: `WARNING: Low disk space (${diskUsage.free_gb.toFixed(1)} GB free). Schedule cleanup soon.`
            });
        }

        const folderStats = status.folder_stats;
        if (folderStats && folderStats.total_size_mb > 1000) {
            recommendations.push({
                level: 'info',
                text: 'Consider reducing retention period to save disk space.'
            });
        }

        const fileCounts = status.file_counts;
        if (fileCounts && fileCounts.unsent_files > 100) {
            recommendations.push({
                level: 'warning',
                text: 'High number of unsent files. Check network connectivity.'
            });
        }

        if (recommendations.length === 0) {
            recommendations.push({
                level: 'success',
                text: 'Storage system is healthy. No immediate action required.'
            });
        }

        // Render recommendations
        recommendationsContainer.innerHTML = recommendations.map(rec => `
            <div class="alert alert-${rec.level} alert-dismissible fade show" role="alert">
                <i class="fas fa-lightbulb"></i> ${rec.text}
                <button type="button" class="close" data-dismiss="alert">
                    <span>&times;</span>
                </button>
            </div>
        `).join('');
    },

    /**
     * Toggle monitoring on/off
     */
    toggleMonitoring: function() {
        if (this.isMonitoring) {
            this.stopMonitoring();
        } else {
            this.startMonitoring();
        }
    },

    /**
     * Start monitoring
     */
    startMonitoring: function() {
        if (this.socket) {
            this.socket.emit('storage_monitor_start', { interval: 300 });
        } else {
            AICameraUtils.apiRequest('/storage/monitor/start', {
                method: 'POST',
                body: JSON.stringify({ interval: 300 })
            })
            .then(data => {
                this.handleMonitorResponse(data);
            })
            .catch(error => {
                console.error('Failed to start monitoring:', error);
                AICameraUtils.showToast('Failed to start monitoring: ' + error.message, 'error');
            });
        }
    },

    /**
     * Stop monitoring
     */
    stopMonitoring: function() {
        if (this.socket) {
            this.socket.emit('storage_monitor_stop');
        } else {
            AICameraUtils.apiRequest('/storage/monitor/stop', {
                method: 'POST'
            })
            .then(data => {
                this.handleMonitorResponse(data);
            })
            .catch(error => {
                console.error('Failed to stop monitoring:', error);
                AICameraUtils.showToast('Failed to stop monitoring: ' + error.message, 'error');
            });
        }
    },

    /**
     * Perform manual cleanup
     */
    performManualCleanup: function() {
        const cleanupBtn = document.getElementById('manual-cleanup-btn');
        if (cleanupBtn) {
            cleanupBtn.disabled = true;
            cleanupBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cleaning...';
        }

        if (this.socket) {
            this.socket.emit('storage_cleanup_request');
        } else {
            AICameraUtils.apiRequest('/storage/cleanup', {
                method: 'POST'
            })
            .then(data => {
                this.handleCleanupResponse(data);
            })
            .catch(error => {
                console.error('Failed to perform cleanup:', error);
                AICameraUtils.showToast('Failed to perform cleanup: ' + error.message, 'error');
                this.resetCleanupButton();
            });
        }
    },

    /**
     * Reset cleanup button
     */
    resetCleanupButton: function() {
        const cleanupBtn = document.getElementById('manual-cleanup-btn');
        if (cleanupBtn) {
            cleanupBtn.disabled = false;
            cleanupBtn.innerHTML = '<i class="fas fa-broom"></i> Manual Cleanup';
        }
    },

    /**
     * Refresh status
     */
    refreshStatus: function() {
        this.requestStorageStatus();
        AICameraUtils.showToast('Storage status refreshed', 'info');
    },

    /**
     * Get analytics
     */
    getAnalytics: function() {
        if (this.socket) {
            this.socket.emit('storage_analytics_request', { days: 7 });
        } else {
            AICameraUtils.apiRequest('/storage/analytics?days=7')
                .then(data => {
                    this.updateAnalytics(data);
                })
                .catch(error => {
                    console.error('Failed to get analytics:', error);
                    AICameraUtils.showToast('Failed to get analytics: ' + error.message, 'error');
                });
        }
    },

    /**
     * Update analytics display
     */
    updateAnalytics: function(data) {
        if (!data || !data.success) {
            console.warn('Invalid analytics data:', data);
            return;
        }

        // Update analytics display
        const analytics = data.data;
        console.log('Storage analytics:', analytics);
        
        // You can add more analytics display logic here
        AICameraUtils.showToast('Analytics updated', 'success');
    },

    /**
     * Update configuration
     */
    updateConfiguration: function() {
        const config = {
            min_free_space_gb: parseFloat(document.getElementById('min-free-space').value),
            retention_days: parseInt(document.getElementById('retention-days').value),
            batch_size: parseInt(document.getElementById('batch-size').value),
            monitor_interval: parseInt(document.getElementById('monitor-interval').value)
        };

        if (this.socket) {
            this.socket.emit('storage_config_update', { config: config });
        } else {
            AICameraUtils.apiRequest('/storage/config', {
                method: 'POST',
                body: JSON.stringify(config)
            })
            .then(data => {
                this.handleConfigResponse(data);
            })
            .catch(error => {
                console.error('Failed to update configuration:', error);
                AICameraUtils.showToast('Failed to update configuration: ' + error.message, 'error');
            });
        }
    },

    /**
     * Request alerts
     */
    requestAlerts: function() {
        if (this.socket) {
            this.socket.emit('storage_alerts_request');
        } else {
            AICameraUtils.apiRequest('/storage/alerts')
                .then(data => {
                    this.updateAlerts(data);
                })
                .catch(error => {
                    console.error('Failed to get alerts:', error);
                });
        }
    },

    /**
     * Update alerts display
     */
    updateAlerts: function(data) {
        if (!data || !data.success) {
            console.warn('Invalid alerts data:', data);
            return;
        }

        const alertsContainer = document.getElementById('alerts-container');
        if (!alertsContainer) return;

        const alerts = data.data.alerts || [];
        
        if (alerts.length === 0) {
            alertsContainer.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-info-circle"></i> No alerts at the moment
                </div>
            `;
            return;
        }

        alertsContainer.innerHTML = alerts.map(alert => `
            <div class="alert alert-${alert.level === 'CRITICAL' ? 'danger' : 'warning'} alert-dismissible fade show" role="alert">
                <strong>${alert.level}:</strong> ${alert.message}
                <br><small class="text-muted">${new Date(alert.timestamp).toLocaleString()}</small>
                <button type="button" class="close" data-dismiss="alert">
                    <span>&times;</span>
                </button>
            </div>
        `).join('');
    },

    /**
     * Clear alerts
     */
    clearAlerts: function() {
        if (this.socket) {
            this.socket.emit('storage_alerts_clear');
        } else {
            AICameraUtils.apiRequest('/storage/alerts/clear', {
                method: 'POST'
            })
            .then(data => {
                this.updateAlerts(data);
            })
            .catch(error => {
                console.error('Failed to clear alerts:', error);
                AICameraUtils.showToast('Failed to clear alerts: ' + error.message, 'error');
            });
        }
    },

    /**
     * Handle cleanup response
     */
    handleCleanupResponse: function(data) {
        this.resetCleanupButton();
        
        if (data && data.success) {
            AICameraUtils.showToast(data.message || 'Cleanup completed successfully', 'success');
            this.requestStorageStatus(); // Refresh status
        } else {
            AICameraUtils.showToast(data?.error || 'Cleanup failed', 'error');
        }
    },

    /**
     * Handle configuration response
     */
    handleConfigResponse: function(data) {
        if (data && data.success) {
            AICameraUtils.showToast(data.message || 'Configuration updated successfully', 'success');
        } else {
            AICameraUtils.showToast(data?.error || 'Configuration update failed', 'error');
        }
    },

    /**
     * Handle monitoring response
     */
    handleMonitorResponse: function(data) {
        if (data && data.success) {
            AICameraUtils.showToast(data.message || 'Monitoring operation completed', 'success');
            this.requestStorageStatus(); // Refresh status
        } else {
            AICameraUtils.showToast(data?.error || 'Monitoring operation failed', 'error');
        }
    },

    /**
     * Cleanup when leaving page
     */
    cleanup: function() {
        if (this.statusUpdateInterval) {
            clearInterval(this.statusUpdateInterval);
        }
        
        if (this.socket) {
            this.socket.emit('leave_storage_room');
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    StorageManager.init();
    
    window.addEventListener('beforeunload', function() {
        StorageManager.cleanup();
    });
    
    console.log('Storage JavaScript loaded');
});
