/**
 * Health Dashboard JavaScript for AI Camera v1.3
 * 
 * This file contains JavaScript functionality for the health monitoring dashboard
 * including WebSocket communication, data visualization, and user interactions.
 */

// Health Dashboard Utilities
const HealthUtils = {
    /**
     * Format timestamp for display
     */
    formatTimestamp: function(timestamp) {
        if (!timestamp) return 'N/A';
        
        try {
            const date = new Date(timestamp);
            return date.toLocaleString();
        } catch (e) {
            return timestamp;
        }
    },
    
    /**
     * Format uptime from seconds
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
     * Get status color class
     */
    getStatusClass: function(status) {
        switch (status.toLowerCase()) {
            case 'healthy':
            case 'pass':
                return 'status-healthy';
            case 'unhealthy':
            case 'warning':
                return 'status-unhealthy';
            case 'critical':
            case 'fail':
                return 'status-critical';
            default:
                return 'status-unknown';
        }
    },
    
    /**
     * Get progress bar class based on value
     */
    getProgressClass: function(value) {
        if (value >= 90) return 'progress-critical';
        if (value >= 70) return 'progress-unhealthy';
        return 'progress-healthy';
    },
    
    /**
     * Get log level class
     */
    getLogLevelClass: function(level) {
        switch (level) {
            case 'PASS': return 'log-pass';
            case 'FAIL': return 'log-fail';
            case 'WARNING': return 'log-warning';
            default: return 'log-pass';
        }
    },
    
    /**
     * Show notification toast
     */
    showNotification: function(message, type = 'info') {
        if (typeof AICameraUtils !== 'undefined' && AICameraUtils.showToast) {
            AICameraUtils.showToast(message, type);
        } else {
            // Fallback notification
            this.showFallbackNotification(message, type);
        }
    },
    
    /**
     * Fallback notification method
     */
    showFallbackNotification: function(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // Style the notification
        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '15px 20px',
            borderRadius: '8px',
            color: 'white',
            fontWeight: '600',
            zIndex: '9999',
            maxWidth: '300px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            transform: 'translateX(100%)',
            transition: 'transform 0.3s ease'
        });
        
        // Set background color based on type
        switch (type) {
            case 'success':
                notification.style.background = '#4CAF50';
                break;
            case 'error':
                notification.style.background = '#f44336';
                break;
            case 'warning':
                notification.style.background = '#ff9800';
                break;
            default:
                notification.style.background = '#2196F3';
        }
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);
        
        // Remove after 5 seconds
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 5000);
    },
    
    /**
     * Debounce function for performance
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
     * Throttle function for performance
     */
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};

// Health Data Manager
const HealthDataManager = {
    cache: new Map(),
    cacheTimeout: 30000, // 30 seconds
    
    /**
     * Get cached data or fetch new data
     */
    getData: function(key, fetchFunction) {
        const cached = this.cache.get(key);
        const now = Date.now();
        
        if (cached && (now - cached.timestamp) < this.cacheTimeout) {
            return Promise.resolve(cached.data);
        }
        
        return fetchFunction().then(data => {
            this.cache.set(key, {
                data: data,
                timestamp: now
            });
            return data;
        });
    },
    
    /**
     * Clear cache
     */
    clearCache: function(key = null) {
        if (key) {
            this.cache.delete(key);
        } else {
            this.cache.clear();
        }
    },
    
    /**
     * Invalidate cache for specific key
     */
    invalidateCache: function(key) {
        this.cache.delete(key);
    }
};

// Health Chart Manager (for future chart implementations)
const HealthChartManager = {
    charts: new Map(),
    
    /**
     * Create a simple progress chart
     */
    createProgressChart: function(elementId, value, maxValue = 100, options = {}) {
        const element = document.getElementById(elementId);
        if (!element) return null;
        
        const percentage = Math.min((value / maxValue) * 100, 100);
        const color = this.getProgressColor(percentage);
        
        element.innerHTML = `
            <div class="progress-chart">
                <div class="progress-bar">
                    <div class="progress-fill ${color}" style="width: ${percentage}%"></div>
                </div>
                <div class="progress-label">${value} / ${maxValue} (${percentage.toFixed(1)}%)</div>
            </div>
        `;
        
        return {
            update: (newValue) => {
                this.createProgressChart(elementId, newValue, maxValue, options);
            }
        };
    },
    
    /**
     * Get progress color based on percentage
     */
    getProgressColor: function(percentage) {
        if (percentage >= 90) return 'progress-critical';
        if (percentage >= 70) return 'progress-warning';
        return 'progress-healthy';
    },
    
    /**
     * Create a simple gauge chart
     */
    createGaugeChart: function(elementId, value, maxValue = 100, options = {}) {
        const element = document.getElementById(elementId);
        if (!element) return null;
        
        const percentage = Math.min((value / maxValue) * 100, 100);
        const angle = (percentage / 100) * 180; // 180 degrees for semi-circle
        
        element.innerHTML = `
            <div class="gauge-chart">
                <svg width="120" height="60" viewBox="0 0 120 60">
                    <circle cx="60" cy="60" r="50" fill="none" stroke="#e0e0e0" stroke-width="8"/>
                    <circle cx="60" cy="60" r="50" fill="none" stroke="${this.getGaugeColor(percentage)}" 
                            stroke-width="8" stroke-dasharray="${angle * 1.75} 314" 
                            transform="rotate(-90 60 60)"/>
                </svg>
                <div class="gauge-value">${value}</div>
                <div class="gauge-label">${options.label || ''}</div>
            </div>
        `;
        
        return {
            update: (newValue) => {
                this.createGaugeChart(elementId, newValue, maxValue, options);
            }
        };
    },
    
    /**
     * Get gauge color based on percentage
     */
    getGaugeColor: function(percentage) {
        if (percentage >= 90) return '#f44336';
        if (percentage >= 70) return '#ff9800';
        return '#4CAF50';
    }
};

// Health Export Manager
const HealthExportManager = {
    /**
     * Export health data as JSON
     */
    exportAsJSON: function(data, filename = 'health-data.json') {
        const jsonString = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },
    
    /**
     * Export health data as CSV
     */
    exportAsCSV: function(data, filename = 'health-data.csv') {
        if (!data || !data.health || !data.health.components) {
            HealthUtils.showNotification('No data to export', 'error');
            return;
        }
        
        let csv = 'Component,Status,Details\n';
        
        Object.keys(data.health.components).forEach(component => {
            const comp = data.health.components[component];
            csv += `${component},${comp.status},${JSON.stringify(comp)}\n`;
        });
        
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },
    
    /**
     * Print health dashboard
     */
    printDashboard: function() {
        window.print();
    }
};

// Health Analytics
const HealthAnalytics = {
    /**
     * Calculate health score
     */
    calculateHealthScore: function(components) {
        if (!components) return 0;
        
        const totalComponents = Object.keys(components).length;
        if (totalComponents === 0) return 0;
        
        let healthyCount = 0;
        Object.values(components).forEach(component => {
            if (component.status === 'healthy') {
                healthyCount++;
            }
        });
        
        return Math.round((healthyCount / totalComponents) * 100);
    },
    
    /**
     * Get component statistics
     */
    getComponentStats: function(components) {
        if (!components) return {};
        
        const stats = {
            total: Object.keys(components).length,
            healthy: 0,
            warning: 0,
            critical: 0,
            unknown: 0
        };
        
        Object.values(components).forEach(component => {
            const status = component.status || 'unknown';
            stats[status]++;
        });
        
        return stats;
    },
    
    /**
     * Get trend analysis (placeholder for future implementation)
     */
    getTrendAnalysis: function(historicalData) {
        // This would analyze historical health data to show trends
        // Implementation would depend on historical data structure
        return {
            trend: 'stable',
            recommendation: 'System health is stable',
            alerts: []
        };
    }
};

// Health Dashboard Event Handlers
const HealthEventHandlers = {
    /**
     * Handle window resize
     */
    handleResize: HealthUtils.debounce(function() {
        // Recalculate layouts if needed
        const cards = document.querySelectorAll('.health-card');
        cards.forEach(card => {
            card.classList.add('fade-in');
        });
    }, 250),
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyPress: function(event) {
        // Ctrl/Cmd + R to refresh
        if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
            event.preventDefault();
            refreshData();
        }
        
        // Ctrl/Cmd + H to run health check
        if ((event.ctrlKey || event.metaKey) && event.key === 'h') {
            event.preventDefault();
            runHealthCheck();
        }
    },
    
    /**
     * Handle visibility change
     */
    handleVisibilityChange: function() {
        if (!document.hidden) {
            // Page became visible, refresh data
            HealthDataManager.clearCache();
            if (typeof HealthDashboard !== 'undefined') {
                HealthDashboard.loadInitialData();
            }
        }
    }
};

// Initialize event handlers when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners
    window.addEventListener('resize', HealthEventHandlers.handleResize);
    document.addEventListener('keydown', HealthEventHandlers.handleKeyPress);
    document.addEventListener('visibilitychange', HealthEventHandlers.handleVisibilityChange);
    
    // Add keyboard shortcuts help
    const helpText = `
        Keyboard Shortcuts:
        - Ctrl/Cmd + R: Refresh data
        - Ctrl/Cmd + H: Run health check
    `;
    
    console.log('Health Dashboard JavaScript loaded');
    console.log(helpText);
});

// Export utilities for global access
window.HealthUtils = HealthUtils;
window.HealthDataManager = HealthDataManager;
window.HealthChartManager = HealthChartManager;
window.HealthExportManager = HealthExportManager;
window.HealthAnalytics = HealthAnalytics;
