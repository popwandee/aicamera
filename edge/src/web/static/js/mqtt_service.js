/**
 * AI Camera v2.0 - MQTT Service Dashboard JavaScript
 *
 * Loads MQTT service status and updates connection, broker, and sending summary.
 */

const MqttServiceManager = {
    statusUpdateInterval: null,

    init: function() {
        if (typeof AICameraUtils === 'undefined') {
            console.warn('AICameraUtils not found; using fetch for API');
        }
        this.setupEventHandlers();
        this.loadStatus();
        this.statusUpdateInterval = setInterval(() => this.loadStatus(), 10000);
    },

    setupEventHandlers: function() {
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadStatus());
        }
    },

    apiRequest: function(url) {
        if (typeof AICameraUtils !== 'undefined' && AICameraUtils.apiRequest) {
            return AICameraUtils.apiRequest(url);
        }
        return fetch(url, { credentials: 'same-origin' })
            .then(r => r.ok ? r.json() : r.json().then(j => Promise.reject(new Error(j.error || 'Request failed'))));
    },

    loadStatus: function() {
        this.apiRequest('/mqtt-service/status')
            .then(data => {
                if (data && data.success && data.status) {
                    this.updateDisplay(data.status);
                } else {
                    this.updateDisplay(null);
                }
            })
            .catch(() => this.updateDisplay(null));
    },

    updateDisplay: function(status) {
        const connectionIcon = document.getElementById('connection-icon');
        const connectionStatus = document.getElementById('connection-status');
        const brokerUrlEl = document.getElementById('broker-url');
        const serviceIcon = document.getElementById('service-icon');
        const serviceStatus = document.getElementById('service-status');
        const healthSentCount = document.getElementById('health-sent-count');
        const mqttBrokerUrl = document.getElementById('mqtt-broker-url');
        const mqttDeviceId = document.getElementById('mqtt-device-id');
        const mqttTopicPrefix = document.getElementById('mqtt-topic-prefix');
        const mqttEnabled = document.getElementById('mqtt-enabled');
        const summaryHealthSent = document.getElementById('summary-health-sent');
        const summaryServiceRunning = document.getElementById('summary-service-running');
        const summaryThreadAlive = document.getElementById('summary-thread-alive');

        const setText = (el, text) => { if (el) el.textContent = text; };
        const setValue = (el, text) => { if (el) el.value = text || '-'; };

        if (!status) {
            setText(connectionStatus, 'Unavailable');
            if (connectionIcon) connectionIcon.className = 'fas fa-plug status-icon disconnected';
            setText(brokerUrlEl, '-');
            setText(serviceStatus, 'Unavailable');
            setText(healthSentCount, '0');
            setValue(mqttBrokerUrl, '');
            setValue(mqttDeviceId, '');
            setValue(mqttTopicPrefix, '');
            setValue(mqttEnabled, '');
            setText(summaryHealthSent, '0');
            setText(summaryServiceRunning, '-');
            setText(summaryThreadAlive, '-');
            return;
        }

        const connected = status.connected === true;
        const running = status.running === true;

        if (connectionIcon) {
            connectionIcon.className = connected ? 'fas fa-plug status-icon connected' : 'fas fa-plug status-icon disconnected';
        }
        setText(connectionStatus, connected ? 'Connected' : (running ? 'Disconnected' : 'Not running'));

        const brokerUrl = status.broker_url || 'mqtt://-:-';
        setText(brokerUrlEl, brokerUrl);
        setValue(mqttBrokerUrl, brokerUrl);
        setValue(mqttDeviceId, status.device_id || '-');
        setValue(mqttTopicPrefix, status.topic_prefix || '-');
        setValue(mqttEnabled, status.enabled ? 'Yes' : 'No');

        if (serviceIcon) {
            serviceIcon.className = running ? 'fas fa-play-circle status-icon connected' : 'fas fa-stop-circle status-icon disconnected';
        }
        setText(serviceStatus, running ? 'Running' : 'Stopped');

        const total = status.total_health_sent != null ? status.total_health_sent : 0;
        setText(healthSentCount, String(total));
        setText(summaryHealthSent, String(total));
        setText(summaryServiceRunning, running ? 'Yes' : 'No');
        setText(summaryThreadAlive, status.thread_alive ? 'Yes' : 'No');
    }
};

document.addEventListener('DOMContentLoaded', function() {
    MqttServiceManager.init();
});
