/**
 * AI Camera v1.3 - Base JavaScript Functions
 * Common utilities and functions shared across all dashboards
 */

// Global utilities
const AICameraUtils = {
    /**
     * Format timestamp to locale string
     */
    formatTimestamp: function(timestamp) {
        if (!timestamp) return '-';
        return new Date(timestamp).toLocaleString();
    },

    /**
     * Format time duration in seconds to human readable format
     */
    formatDuration: function(seconds) {
        if (!seconds) return '0s';
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return minutes > 0 ? `${minutes}m ${secs}s` : `${secs}s`;
    },

    /**
     * Update status indicator element
     */
    updateStatusIndicator: function(elementId, isOnline, statusText) {
        const element = document.getElementById(elementId);
        if (element) {
            element.className = `status-indicator ${isOnline ? 'status-online' : 'status-offline'}`;
        }
        
        const textElement = document.getElementById(elementId + '-text');
        if (textElement) {
            textElement.textContent = statusText || (isOnline ? 'Online' : 'Offline');
        }
    },

    /**
     * Add log message to log container
     */
    addLogMessage: function(containerId, message, type = 'info') {
        const container = document.getElementById(containerId);
        if (!container) return;

        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        logEntry.innerHTML = `[${timestamp}] ${message}`;
        
        container.appendChild(logEntry);
        container.scrollTop = container.scrollHeight;
        
        // Keep only last 100 messages
        while (container.children.length > 100) {
            container.removeChild(container.firstChild);
        }
    },

    /**
     * Show toast notification
     */
    showToast: function(message, type = 'info') {
        // Create toast if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '1050';
            document.body.appendChild(toastContainer);
        }

        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div class="toast" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="fas fa-camera text-primary me-2"></i>
                    <strong class="me-auto">AI Camera</strong>
                    <small class="text-muted">${new Date().toLocaleTimeString()}</small>
                    <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} text-white">
                    ${message}
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        const toast = new bootstrap.Toast(document.getElementById(toastId));
        toast.show();

        // Remove toast element after it's hidden
        document.getElementById(toastId).addEventListener('hidden.bs.toast', function() {
            this.remove();
        });
    },

    /**
     * Debounce function to limit API calls
     */
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Make API request with error handling
     */
    apiRequest: function(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        };

        const finalOptions = { ...defaultOptions, ...options };
        
        return fetch(url, finalOptions)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                // Check if response is JSON
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return response.json();
                } else {
                    // If not JSON, get text and try to parse as JSON
                    return response.text().then(text => {
                        try {
                            return JSON.parse(text);
                        } catch (parseError) {
                            console.error('Response is not valid JSON:', text.substring(0, 200));
                            throw new Error('Invalid JSON response from server');
                        }
                    });
                }
            })
            .catch(error => {
                console.error('API request failed:', url, error);
                // Don't show toast for every failed request to avoid spam
                // this.showToast(`Request failed: ${error.message}`, 'error');
                throw error;
            });
    }
};

// Global WebSocket manager
const WebSocketManager = {
    socket: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    connectionTimeout: 10000, // 10 seconds timeout

    /**
     * Initialize WebSocket connection
     */
    init: function(namespace = '/') {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not loaded, WebSocket functionality disabled');
            return;
        }

        // Configure Socket.IO with timeout and reconnection settings
        this.socket = io(namespace, {
            timeout: this.connectionTimeout,
            reconnection: true,
            reconnectionAttempts: this.maxReconnectAttempts,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            maxReconnectionAttempts: this.maxReconnectAttempts
        });
        
        this.setupEventHandlers();
    },

    /**
     * Setup common WebSocket event handlers
     */
    setupEventHandlers: function() {
        if (!this.socket) return;

        this.socket.on('connect', () => {
            console.log('WebSocket connected successfully');
            AICameraUtils.showToast('Connected to server', 'success');
            this.reconnectAttempts = 0;
            
            // Update connection status in main dashboard
            const connectionElement = document.getElementById('main-server-connection-status');
            const connectionText = document.getElementById('main-server-connection-text');
            if (connectionElement) {
                connectionElement.className = 'status-indicator status-online';
            }
            if (connectionText) {
                connectionText.textContent = 'Connected';
            }
            
            // Add log message
            AICameraUtils.addLogMessage('main-server-logs', 'WebSocket connection established', 'success');
        });

        this.socket.on('disconnect', (reason) => {
            console.log('WebSocket disconnected:', reason);
            AICameraUtils.showToast('Disconnected from server: ' + reason, 'warning');
            
            // Update connection status in main dashboard
            const connectionElement = document.getElementById('main-server-connection-status');
            const connectionText = document.getElementById('main-server-connection-text');
            if (connectionElement) {
                connectionElement.className = 'status-indicator status-offline';
            }
            if (connectionText) {
                connectionText.textContent = 'Disconnected';
            }
            
            // Add log message
            AICameraUtils.addLogMessage('main-server-logs', 'WebSocket disconnected: ' + reason, 'warning');
        });

        this.socket.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
            AICameraUtils.showToast('Connection error: ' + error.message, 'error');
            
            // Update connection status in main dashboard
            const connectionElement = document.getElementById('main-server-connection-status');
            const connectionText = document.getElementById('main-server-connection-text');
            if (connectionElement) {
                connectionElement.className = 'status-indicator status-offline';
            }
            if (connectionText) {
                connectionText.textContent = 'Connection Error';
            }
            
            // Add log message
            AICameraUtils.addLogMessage('main-server-logs', 'WebSocket connection error: ' + error.message, 'error');
            
            this.handleReconnect();
        });

        this.socket.on('reconnect_attempt', (attemptNumber) => {
            console.log(`WebSocket reconnection attempt ${attemptNumber}/${this.maxReconnectAttempts}`);
            AICameraUtils.addLogMessage('main-server-logs', `Reconnection attempt ${attemptNumber}/${this.maxReconnectAttempts}`, 'info');
        });

        this.socket.on('reconnect_failed', () => {
            console.error('WebSocket reconnection failed after all attempts');
            AICameraUtils.showToast('Connection failed after all attempts. Please refresh the page.', 'error');
            AICameraUtils.addLogMessage('main-server-logs', 'WebSocket reconnection failed after all attempts', 'error');
        });
    },

    /**
     * Handle reconnection logic
     */
    handleReconnect: function() {
        this.reconnectAttempts++;
        if (this.reconnectAttempts <= this.maxReconnectAttempts) {
            const delay = Math.pow(2, this.reconnectAttempts) * 1000; // Exponential backoff
            setTimeout(() => {
                console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                this.socket.connect();
            }, delay);
        } else {
            AICameraUtils.showToast('Connection failed. Please refresh the page.', 'error');
        }
    },

    /**
     * Emit event with error handling
     */
    emit: function(event, data) {
        if (this.socket && this.socket.connected) {
            this.socket.emit(event, data);
        } else {
            console.warn('WebSocket not connected, cannot emit event:', event);
            AICameraUtils.showToast('Not connected to server', 'warning');
        }
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Add smooth scrolling to anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    console.log('AI Camera v1.3 - Base JavaScript loaded');
});
