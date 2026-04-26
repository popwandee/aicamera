#!/usr/bin/env python3
"""
Communication Configuration for AI Camera Edge Device

This module contains configuration settings for communication services:
- MQTT communication
- SFTP file transfer
- Storage management
- WebSocket communication

Author: AI Camera Team
Version: 2.0.0
"""

import os

# Server Configuration
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:3000')
SERVER_HOST = os.getenv('SERVER_HOST', 'localhost')

# MQTT Configuration
MQTT_ENABLED = os.getenv('MQTT_ENABLED', 'true').lower() == 'true'
MQTT_BROKER_HOST = os.getenv('MQTT_BROKER_HOST', 'localhost')
MQTT_BROKER_PORT = int(os.getenv('MQTT_BROKER_PORT', '1883'))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID', f'aicamera-edge-{os.getenv("DEVICE_ID", "unknown")}')
MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', '60'))
MQTT_QOS = int(os.getenv('MQTT_QOS', '1'))

# MQTT Topics
MQTT_TOPIC_PREFIX = os.getenv('MQTT_TOPIC_PREFIX', 'aicamera')
MQTT_TOPICS = {
    'device_register': f'{MQTT_TOPIC_PREFIX}/device/register',
    'device_heartbeat': f'{MQTT_TOPIC_PREFIX}/device/heartbeat',
    'health_status': f'{MQTT_TOPIC_PREFIX}/device/{{device_id}}/health',
    'detection_data': f'{MQTT_TOPIC_PREFIX}/detection/{{device_id}}/data',
    'detection_response': f'{MQTT_TOPIC_PREFIX}/detection/{{device_id}}/response',
    'image_transfer_request': f'{MQTT_TOPIC_PREFIX}/image/{{device_id}}/request',
    'image_transfer_status': f'{MQTT_TOPIC_PREFIX}/image/{{device_id}}/status',
    'system_command': f'{MQTT_TOPIC_PREFIX}/system/{{device_id}}/command',
    'system_status': f'{MQTT_TOPIC_PREFIX}/system/{{device_id}}/status',
}

# SFTP Configuration  
SERVER_SFTP_ENABLED = os.getenv('SERVER_SFTP_ENABLED', 'true').lower() == 'true'
SERVER_SFTP_HOST = os.getenv('SERVER_SFTP_HOST', 'localhost')
SERVER_SFTP_PORT = int(os.getenv('SERVER_SFTP_PORT', '2222'))
SERVER_SFTP_USERNAME = os.getenv('SERVER_SFTP_USERNAME', 'aicamera')
SERVER_SFTP_PASSWORD = os.getenv('SERVER_SFTP_PASSWORD', 'aicamera123')
SERVER_SFTP_PRIVATE_KEY = os.getenv('SERVER_SFTP_PRIVATE_KEY', '')

# Storage Manager Configuration
STORAGE_MANAGER_ENABLED = os.getenv('STORAGE_MANAGER_ENABLED', 'true').lower() == 'true'
TRANSFER_RETRY_INTERVAL = int(os.getenv('TRANSFER_RETRY_INTERVAL', '60'))  # seconds
MAX_TRANSFER_RETRIES = int(os.getenv('MAX_TRANSFER_RETRIES', '3'))
TRANSFER_BATCH_SIZE = int(os.getenv('TRANSFER_BATCH_SIZE', '5'))

# Image Processing Configuration
IMAGE_COMPRESSION_ENABLED = os.getenv('IMAGE_COMPRESSION_ENABLED', 'true').lower() == 'true'
IMAGE_COMPRESSION_QUALITY = int(os.getenv('IMAGE_COMPRESSION_QUALITY', '85'))
IMAGE_MAX_WIDTH = int(os.getenv('IMAGE_MAX_WIDTH', '1920'))
IMAGE_MAX_HEIGHT = int(os.getenv('IMAGE_MAX_HEIGHT', '1080'))

# File Transfer Configuration
DELETE_AFTER_TRANSFER = os.getenv('DELETE_AFTER_TRANSFER', 'false').lower() == 'true'
KEEP_TRANSFER_HISTORY_DAYS = int(os.getenv('KEEP_TRANSFER_HISTORY_DAYS', '7'))
CLEANUP_COMPLETED_TRANSFERS_DAYS = int(os.getenv('CLEANUP_COMPLETED_TRANSFERS_DAYS', '30'))

# Rsync Configuration
RSYNC_ENABLED = os.getenv('RSYNC_ENABLED', 'false').lower() == 'true'
RSYNC_OPTIONS = os.getenv('RSYNC_OPTIONS', '-avz --progress').split()
RSYNC_EXCLUDE_PATTERNS = os.getenv('RSYNC_EXCLUDE_PATTERNS', '*.tmp,*.temp').split(',')

# Device Identification
DEVICE_ID = os.getenv('DEVICE_ID', 'aicamera-edge-001')
DEVICE_MODEL = os.getenv('DEVICE_MODEL', 'AI-CAM-EDGE-V2')
DEVICE_LOCATION = os.getenv('DEVICE_LOCATION', 'Unknown Location')

# Communication Intervals
HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '60'))  # seconds
STATUS_REPORT_INTERVAL = int(os.getenv('STATUS_REPORT_INTERVAL', '300'))  # seconds
TRANSFER_CHECK_INTERVAL = int(os.getenv('TRANSFER_CHECK_INTERVAL', '30'))  # seconds

# Security Configuration
USE_TLS = os.getenv('USE_TLS', 'false').lower() == 'true'
VERIFY_SSL = os.getenv('VERIFY_SSL', 'true').lower() == 'true'
API_KEY_HEADER = os.getenv('API_KEY_HEADER', 'X-API-Key')
DEVICE_SERIAL_HEADER = os.getenv('DEVICE_SERIAL_HEADER', 'X-Device-Serial')

# Paths Configuration (relative to edge directory)
CAPTURED_IMAGES_PATH = os.getenv('CAPTURED_IMAGES_PATH', 'captured_images')
TEMP_STORAGE_PATH = os.getenv('TEMP_STORAGE_PATH', 'temp')
LOGS_PATH = os.getenv('LOGS_PATH', 'logs')

# Server Image Storage Path (for rsync)
SERVER_IMAGE_STORAGE_PATH = os.getenv('SERVER_IMAGE_STORAGE_PATH', '/server/image_storage')

def get_mqtt_topic(topic_name: str, device_id: str = None) -> str:
    """Get formatted MQTT topic"""
    if device_id is None:
        device_id = DEVICE_ID
    
    topic = MQTT_TOPICS.get(topic_name, '')
    return topic.format(device_id=device_id)

def get_sftp_config() -> dict:
    """Get SFTP configuration dictionary"""
    config = {
        'host': SERVER_SFTP_HOST,
        'port': SERVER_SFTP_PORT,
        'username': SERVER_SFTP_USERNAME,
        'timeout': 30,
    }
    
    if SERVER_SFTP_PASSWORD:
        config['password'] = SERVER_SFTP_PASSWORD
    
    if SERVER_SFTP_PRIVATE_KEY and os.path.exists(SERVER_SFTP_PRIVATE_KEY):
        config['private_key'] = SERVER_SFTP_PRIVATE_KEY
    
    return config

def get_device_info() -> dict:
    """Get device information for registration"""
    import socket
    import uuid
    
    # Get network info
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
    except:
        ip_address = "127.0.0.1"
    
    # Get MAC address
    try:
        mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                               for elements in range(0, 2*6, 2)][::-1])
    except:
        mac_address = "00:00:00:00:00:00"
    
    return {
        'device_id': DEVICE_ID,
        'device_model': DEVICE_MODEL,
        'ip_address': ip_address,
        'mac_address': mac_address,
        'location': DEVICE_LOCATION,
        'hostname': socket.gethostname(),
    }