#!/usr/bin/env python3
"""
WebSocket Sender Service for AI Camera v1.3

This service handles communication with external WebSocket server,
sending detection results and health status data in separate threads.

Features:
- WebSocket connection management with auto-reconnect
- Detection data sender thread
- Health status sender thread  
- Database integration for tracking sent status
- Logging and status monitoring

Author: AI Camera Team
Version: 1.3
Date: December 2024
"""

import json
import base64
import threading
import time
import logging
import requests
import socketio
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from edge.src.core.dependency_container import get_service
from edge.src.core.utils.logging_config import get_logger
from edge.src.core.config import (
    WEBSOCKET_SERVER_URL, SENDER_INTERVAL,
    WEBSOCKET_SENDER_ENABLED, WEBSOCKET_CONNECTION_TIMEOUT, 
    WEBSOCKET_RETRY_INTERVAL, WEBSOCKET_MAX_RETRIES,
    AICAMERA_ID, CHECKPOINT_ID, CAMERA_NAME, CAMERA_LOCATION, LOCATION_LAT, LOCATION_LON
)

# Use dedicated communication logger to write into edge/logs/unified_comm.log
logger = logging.getLogger('communication')


class WebSocketSender:
    """
    WebSocket Sender Service for external server communication.
    
    This service manages:
    - WebSocket connection to external server
    - Detection data sending thread
    - Health status sending thread
    - Database integration for tracking sent records
    - Connection retry and error handling
    """
    
    def __init__(self, database_manager=None, logger=None):
        """
        Initialize WebSocket Sender Service.
        
        Args:
            database_manager: Database manager instance
            logger: Logger instance
        """
        # Use dedicated 'communication' logger so logs go to unified_comm.log
        self.logger = logger or logging.getLogger('communication')
        self.database_manager = database_manager
        
        # Socket.IO connection
        self.sio = None
        self.connected = False
        self.server_url = WEBSOCKET_SERVER_URL
        
        # Threading
        self.detection_thread = None
        self.running = False
        self.stop_event = threading.Event()
        
        # Status tracking
        self.last_detection_check = None
        self.retry_count = 0
        self.total_detections_sent = 0
        
        # Configuration
        self.enabled = WEBSOCKET_SENDER_ENABLED
        self.connection_timeout = WEBSOCKET_CONNECTION_TIMEOUT
        self.retry_interval = WEBSOCKET_RETRY_INTERVAL
        self.max_retries = WEBSOCKET_MAX_RETRIES

        # AI Camera Identification
        self.aicamera_id = AICAMERA_ID
        self.checkpoint_id = CHECKPOINT_ID
        self.camera_name = CAMERA_NAME or AICAMERA_ID
        self.camera_location = CAMERA_LOCATION
        self.location_lat = LOCATION_LAT
        self.location_lon = LOCATION_LON
        self.logger.info("WebSocketSender Started")
    
    def initialize(self) -> bool:
        """
        Initialize WebSocket sender service.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            if not self.enabled:
                self.logger.info("WebSocket sender is disabled")
                return False
                
            if not self.server_url:
                self.logger.warning("WEBSOCKET_SERVER_URL not configured - service will run in offline mode")
                self.server_url = None  # Set to None to indicate offline mode
            
            # Get database manager from DI container if not provided
            if not self.database_manager:
                self.database_manager = get_service('database_manager')
            
            if not self.database_manager:
                self.logger.error("Database manager not available")
                return False
            
            # Detect server type (WebSocket vs REST API)
            if self.server_url:
                self._detect_server_type()
            
            if self.server_url:
                self.logger.info(f"WebSocket sender initialized for server: {self.server_url}")
            else:
                self.logger.info("WebSocket sender initialized in offline mode (no server URL configured)")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WebSocket sender: {e}")
            return False

    def _detect_server_type(self):
        """
        Detect if server supports Socket.IO or REST API.
        Prioritizes Socket.IO, falls back to REST API.
        """
        try:
            # Store original URL for REST API fallback
            original_url = self.server_url
            
            # Try Socket.IO first
            socketio_url = self.server_url
            if socketio_url.startswith(('http://', 'https://')):
                # Convert HTTP to WebSocket URL for Socket.IO
                if socketio_url.startswith('https://'):
                    socketio_url = socketio_url.replace('https://', 'wss://')
                else:
                    socketio_url = socketio_url.replace('http://', 'ws://')
            
            # Test Socket.IO connection
            if self._test_socketio_connection(socketio_url):
                self.server_url = socketio_url
                self.server_type = 'socketio'
                # self.logger.info(f"Detected Socket.IO server: {self.server_url}")  # INFO: ปิดรายละเอียด
                return
            
            # Fallback to REST API
            if self._test_rest_connection(original_url):
                self.server_url = original_url
                self.server_type = 'rest'
                self.logger.info(f"Falling back to REST API server: {self.server_url}")
                return
            
            # Default to Socket.IO if both tests fail
            self.server_url = socketio_url
            self.server_type = 'socketio'
            self.logger.warning("Connectivity probe failed for both Socket.IO and REST. Defaulting to Socket.IO. If your server is HTTP-only, set WEBSOCKET_SERVER_URL to an http(s) URL or disable the sender.")
                
        except Exception as e:
            self.logger.error(f"Error detecting server type: {e}")
            self.server_type = 'socketio'  # Default to Socket.IO

    def _test_socketio_connection(self, test_url: str = None) -> bool:
        """
        Test if server supports Socket.IO connection.
        
        Args:
            test_url: URL to test (optional, uses self.server_url if not provided)
            
        Returns:
            bool: True if Socket.IO supported, False otherwise
        """
        try:
            if test_url is None:
                test_url = self.server_url
            
            if not test_url.startswith(('ws://', 'wss://')):
                test_url = f"ws://{test_url}"
            
            # Create a temporary Socket.IO client for testing
            import socketio
            test_sio = socketio.Client()
            use_ws_path = "/ws" in (test_url or "")
            # Use wait_timeout (python-socketio); use socketio_path when server uses /ws/
            probe_connect_url = test_url
            probe_path = "socket.io"
            if use_ws_path and test_url:
                probe_connect_url = test_url.split("/ws")[0].rstrip("/") or test_url
                probe_path = "/ws/"
            kwargs = {"wait_timeout": 5}
            if probe_path:
                kwargs["socketio_path"] = probe_path
            test_sio.connect(probe_connect_url, **kwargs)
            ok = test_sio.connected
            if ok:
                test_sio.disconnect()
            return ok
            
        except Exception as e:
            return False

    def _test_rest_connection(self, test_url: str = None) -> bool:
        """
        Test if server supports REST API.
        
        Args:
            test_url: URL to test (optional, uses self.server_url if not provided)
            
        Returns:
            bool: True if REST API supported, False otherwise
        """
        try:
            if test_url is None:
                test_url = self.server_url
            
            if not test_url.startswith(('http://', 'https://')):
                test_url = f"http://{test_url}"
            
            response = requests.get(f"{test_url}/api/statistics", timeout=5)
            return response.status_code == 200
            
        except Exception as e:
            # self.logger.debug(f"REST API test failed: {e}")  # DEBUG: ปิดรายละเอียด
            return False
    
    def connect(self) -> bool:
        """
        Connect to server (Socket.IO or REST API).
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.connected:
                return True
            
            # Check if we have a server URL
            if not self.server_url:
                self.logger.warning("No server URL configured - staying in offline mode")
                return False
            
            # Determine server type if not already detected
            if not hasattr(self, 'server_type'):
                self._detect_server_type()
            
            # Connect based on server type
            if self.server_type == 'rest':
                return self._connect_rest()
            else:
                return self._connect_socketio()
            
        except Exception as e:
            self.connected = False
            self.retry_count += 1
            
            # Log connection failure
            if self.database_manager:
                try:
                    self.database_manager.log_websocket_action(
                        action='connect',
                        status='failed',
                        message=f'Connection failed: {str(e)}'
                    )
                except Exception as db_exc:
                    self.logger.warning(f"Skipped DB log (connect failed): {db_exc}")
            
            self.logger.error(f"Connection failed: {e}")
            return False

    def _connect_socketio(self) -> bool:
        """
        Connect to Socket.IO server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.logger.info("Connecting to Socket.IO")
            
            # Create Socket.IO client
            self.sio = socketio.Client()
            
            # Setup event handlers
            self.sio.on('connect', self._on_connect)
            self.sio.on('disconnect', self._on_disconnect)
            self.sio.on('lpr_response', self._on_lpr_response)
            self.sio.on('error', self._on_error)
            self.sio.on('message_saved', self._on_message_saved)
            self.sio.on('image_saved', self._on_image_saved)
            self.sio.on('message_error', self._on_message_error)
            self.sio.on('image_error', self._on_image_error)
            
            connect_url = self.server_url
            socketio_path = 'socket.io'
            if self.server_url and '/ws' in self.server_url:
                connect_url = self.server_url.split('/ws')[0].rstrip('/') or self.server_url
                socketio_path = '/ws/'
            self.sio.connect(connect_url, socketio_path=socketio_path, wait_timeout=self.connection_timeout)
            # Wait for connection
            if self.sio.connected:
                self.connected = True
                self.retry_count = 0
                
                # Register camera with full metadata so backend can update name/location
                self.sio.emit('camera_register', {
                    'camera_id': self.aicamera_id,
                    'checkpoint_id': self.checkpoint_id,
                    'camera_name': self.camera_name,
                    'camera_location': self.camera_location,
                    'location_lat': self.location_lat,
                    'location_lon': self.location_lon,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Log successful connection
                if self.database_manager:
                    try:
                        self.database_manager.log_websocket_action(
                            action='connect',
                            status='success',
                            message=f'Connected to Socket.IO server {self.server_url}'
                        )
                    except Exception as db_exc:
                        self.logger.info(f"Skipped DB log (connect success): {db_exc}")
                
                self.logger.info("Socket.IO connection established")
                
                # Try to send any pending data after successful connection
                self._send_pending_data()
                
                return True
            else:
                self.logger.error("Socket.IO connection failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Socket.IO connection failed: {e}")
            return False

    def _on_connect(self):
        """Handle Socket.IO connect event"""
        self.logger.info("Socket.IO connected")
        self.connected = True

    def _on_disconnect(self):
        """Handle Socket.IO disconnect event"""
        self.logger.info("Socket.IO disconnected")
        self.connected = False

    def _on_lpr_response(self, data):
        """Handle LPR response from server"""
        # self.logger.info(f"LPR response received: {data}")  # INFO: ไม่บันทึกรายละเอียด payload

    def _on_error(self, data):
        """Handle error from server"""
        self.logger.error(f"Server error: {data}")

    def _on_message_saved(self, data):
        """Handle message_saved response from server (ws-service). Optionally mark detection as sent if server echoes record id."""
        if isinstance(data, dict) and data.get('record_id') is not None and self.database_manager:
            try:
                self.database_manager.mark_detection_result_sent(int(data['record_id']), data.get('message', 'message_saved'))
            except Exception as e:
                self.logger.debug(f"mark_detection from message_saved: {e}")
        self.logger.debug("message_saved received")

    def _on_image_saved(self, data):
        """Handle image_saved response from server (ws-service)."""
        self.logger.debug("image_saved received")

    def _on_message_error(self, data):
        """Handle message_error from server; log and allow retry."""
        self.logger.error(f"Server message_error: {data}")

    def _on_image_error(self, data):
        """Handle image_error from server; log and allow retry."""
        self.logger.error(f"Server image_error: {data}")

    def _send_pending_data(self):
        """
        Send any pending data after successful connection.
        This method tries to send any unsent detection and health data.
        """
        try:
            if not self.connected or not self.server_url:
                return
            
            self.logger.info("Sending pending data after reconnection...")
            
            # Send pending detection data (health is sent via MQTT)
            detection_count = self._send_detection_data()
            if detection_count > 0:
                self.logger.info("Sent pending detection records")
            else:
                self.logger.info("No pending data to send")
                
        except Exception as e:
            self.logger.error(f"Error sending pending data: {e}")

    def disconnect(self) -> bool:
        """
        Disconnect from server (Socket.IO or REST API).
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        try:
            if self.sio and self.sio.connected:
                self.sio.disconnect()
            
            self.connected = False
            self.sio = None
            
            # Log disconnection
            if self.database_manager:
                try:
                    self.database_manager.log_websocket_action(
                        action='disconnect',
                        status='success',
                        message='Disconnected from server'
                    )
                except Exception as db_exc:
                    self.logger.info(f"Skipped DB log (disconnect): {db_exc}")
            
            self.logger.info("Server disconnected")
            return True
            
        except Exception as e:
            self.logger.error(f"Server disconnection error: {e}")
            return False

    def send_data(self, data: Dict[str, Any]) -> bool:
        """
        Send data via Socket.IO or REST API with fallback.
        
        Args:
            data: Data to send
            
        Returns:
            bool: True if send successful, False otherwise
        """
        try:
            if not self.connected:
                if not self.connect():
                    return False
            
            # Try Socket.IO first if that's the current server type
            if self.server_type == 'socketio':
                success = self._send_data_socketio(data)
                if success:
                    return True
                else:
                    # Fallback to REST API if Socket.IO fails
                    self.logger.warning("Socket.IO send failed, trying REST API fallback...")
                    return self._send_data_rest(data)
            else:
                # Try REST API first if that's the current server type
                success = self._send_data_rest(data)
                if success:
                    return True
                else:
                    # Fallback to Socket.IO if REST API fails
                    self.logger.warning("REST API send failed, trying Socket.IO fallback...")
                    return self._send_data_socketio(data)
            
        except Exception as e:
            self.logger.error(f"Send data error: {e}")
            self.connected = False
            return False



    def _connect_rest(self) -> bool:
        """
        Connect to REST API server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.logger.info(f"Connecting to REST API server: {self.server_url}")
            
            # Test REST API connection
            test_url = self.server_url
            if not test_url.startswith(('http://', 'https://')):
                test_url = f"http://{test_url}"
            
            response = requests.get(f"{test_url}/api/statistics", timeout=10)
            
            if response.status_code == 200:
                self.connected = True
                self.retry_count = 0
                
                # Log successful connection
                if self.database_manager:
                    self.database_manager.log_websocket_action(
                        action='connect',
                        status='success',
                        message=f'Connected to REST API {self.server_url}'
                    )
                
                self.logger.info("REST API connection established")
                
                # Try to send any pending data after successful connection
                self._send_pending_data()
                
                return True
            else:
                self.logger.error(f"REST API connection failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"REST API connection failed: {e}")
            return False

    def _send_data_socketio(self, data: Dict[str, Any]) -> bool:
        """
        Send data via Socket.IO.
        
        Args:
            data: Data to send
            
        Returns:
            bool: True if send successful, False otherwise
        """
        try:
            if not self.sio or not self.sio.connected:
                return False
            
            # Add metadata to data
            data['camera_id'] = self.aicamera_id
            data['checkpoint_id'] = self.checkpoint_id
            data['timestamp'] = datetime.now().isoformat()
            
            # Send data via Socket.IO based on data type
            if data.get('type') == 'detection_result':
                message_data = {
                    'content': {
                        'type': 'detection_result',
                        'aicamera_id': data.get('aicamera_id', self.aicamera_id),
                        'checkpoint_id': data.get('checkpoint_id', self.checkpoint_id),
                        'timestamp': data.get('timestamp'),
                        'vehicles_count': data.get('vehicles_count'),
                        'plates_count': data.get('plates_count'),
                        'ocr_results': data.get('ocr_results'),
                        'vehicle_detections': data.get('vehicle_detections'),
                        'plate_detections': data.get('plate_detections'),
                        'processing_time_ms': data.get('processing_time_ms'),
                        'created_at': data.get('created_at'),
                    },
                    'camera_id': self.aicamera_id,
                }
                self.sio.emit('message', message_data)
                if data.get('original_image'):
                    fn = f"detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    image_data = {'data': data['original_image'], 'filename': fn, 'camera_id': self.aicamera_id}
                    self.sio.emit('image', image_data)
            elif data.get('type') == 'test':
                self.sio.emit('ping', data)
            else:
                self.sio.emit('lpr_data', data)
            
            # self.logger.debug(f"Data sent via Socket.IO: {data}")  # DEBUG: ปิดรายละเอียด payload
            return True
            
        except Exception as e:
            self.logger.error(f"Socket.IO send error: {e}")
            return False

    def _send_data_rest(self, data: Dict[str, Any]) -> bool:
        """
        Send data via REST API.
        
        Args:
            data: Data to send
            
        Returns:
            bool: True if send successful, False otherwise
        """
        try:
            # Prepare REST API URL
            api_url = self.server_url
            if not api_url.startswith(('http://', 'https://')):
                api_url = f"http://{api_url}"
            
            # Determine endpoint and method based on data type
            if data.get('type') == 'detection_result':
                endpoint = '/api/statistics'  # Use statistics endpoint for detection data
                method = 'POST'
            elif data.get('type') == 'test':
                endpoint = '/api/statistics'  # Use statistics endpoint for test
                method = 'GET'
            else:
                endpoint = '/api/statistics'  # Default to statistics endpoint
                method = 'POST'
            
            # Send request based on method
            if method == 'GET':
                response = requests.get(
                    f"{api_url}{endpoint}",
                    timeout=30
                )
            else:
                response = requests.post(
                    f"{api_url}{endpoint}",
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
            
            if response.status_code in [200, 201]:
                # self.logger.debug(f"REST API response: {response.text}")  # DEBUG: ปิดรายละเอียด payload
                return True
            else:
                self.logger.error(f"REST API send failed: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"REST API send error: {e}")
            return False
    
    def start(self) -> bool:
        """
        Start WebSocket sender service threads.
        
        Returns:
            bool: True if start successful, False otherwise
        """
        try:
            if self.running:
                self.logger.warning("WebSocket sender already running")
                return True
            
            if not self.initialize():
                return False
            
            self.running = True
            self.stop_event.clear()
            
            # Start detection sender thread (health is sent via MQTT)
            self.detection_thread = threading.Thread(
                target=self._detection_sender_loop,
                name="WebSocket-Detection-Sender",
                daemon=True
            )
            self.detection_thread.start()
            if self.server_url:
                self.connect()
            if self.server_url:
                self.logger.info("WebSocket sender service started (online mode)")
            else:
                self.logger.info("WebSocket sender service started (offline mode)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start WebSocket sender: {e}")
            return False
    
    def stop(self):
        """Stop WebSocket sender service."""
        try:
            self.logger.info("Stopping WebSocket sender service...")
            
            self.running = False
            self.stop_event.set()
            
            # Disconnect Socket.IO
            if self.connected and self.sio:
                try:
                    self.sio.disconnect()
                    self.connected = False
                except Exception as e:
                    self.logger.error(f"Error during Socket.IO disconnection: {e}")
            
            # Wait for detection thread to finish
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=5.0)
            
            self.logger.info("WebSocket sender service stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping WebSocket sender: {e}")
    
    def _detection_sender_loop(self):
        """Main loop for detection data sender thread - OPTIMIZED for reduced resource usage."""
        self.logger.info(f"Detection sender thread started with {SENDER_INTERVAL}s interval (optimized)")
        
        while self.running and not self.stop_event.is_set():
            try:
                self.last_detection_check = datetime.now()
                sent_count = self._send_detection_data()
                
                if sent_count > 0:
                    self.total_detections_sent += sent_count
                    self.logger.info(f"Sent {sent_count} detection records to server")
                
                # Wait for next interval or stop event (longer interval to reduce resource usage)
                if self.stop_event.wait(SENDER_INTERVAL):
                    break
                    
            except Exception as e:
                self.logger.error(f"Error in detection sender loop: {e}")
                # Wait before retrying (longer interval to reduce resource usage)
                if self.stop_event.wait(SENDER_INTERVAL):
                    break
        
        self.logger.info("Detection sender thread stopped")
    
    def _send_detection_data(self) -> int:
        """
        Send unsent detection data to server.
        
        Returns:
            int: Number of records sent successfully
        """
        if not self.database_manager:
            return 0
        
        try:
            # Get unsent detection results
            unsent_detections = self.database_manager.get_unsent_detection_results()
            
            if not unsent_detections:
                # Log no data to send
                try:
                    self.database_manager.log_websocket_action(
                        action='send_detection',
                        status='no_data',
                        message='No detection data to send',
                        data_type='detection_results',
                        record_count=0,
                        aicamera_id=self.aicamera_id,
                        checkpoint_id=self.checkpoint_id
                    )
                except Exception as db_exc:
                    self.logger.info(f"Skipped DB log (no detection data): {db_exc}")
                return 0
            
            # Check if in offline mode
            if not self.server_url:
                # In offline mode, just log that we're processing locally
                try:
                    self.database_manager.log_websocket_action(
                        action='send_detection',
                        status='offline',
                        message=f'Processing {len(unsent_detections)} detection records locally (offline mode)',
                        data_type='detection_results',
                        record_count=len(unsent_detections),
                        aicamera_id=self.aicamera_id,
                        checkpoint_id=self.checkpoint_id
                    )
                except Exception as db_exc:
                    self.logger.info(f"Skipped DB log (offline detection): {db_exc}")
                return len(unsent_detections)
            
            sent_count = 0
            
            for detection in unsent_detections:
                # Use synchronous send method instead of asyncio.run()
                success = self._send_single_detection_sync(detection)
                
                if success:
                    # Mark as sent in database
                    self.database_manager.mark_detection_result_sent(
                        detection['id'], 
                        'Successfully sent to server'
                    )
                    sent_count += 1
                else:
                    # Log send failure
                    try:
                        self.database_manager.log_websocket_action(
                            action='send_detection',
                            status='failed',
                            message=f'Failed to send detection ID {detection["id"]}',
                            data_type='detection_results',
                            record_count=1,
                            aicamera_id=self.aicamera_id,
                            checkpoint_id=self.checkpoint_id
                        )
                    except Exception as db_exc:
                        self.logger.warning(f"Skipped DB log (send_detection failed): {db_exc}")
            
            if sent_count > 0:
                # Log successful sends
                try:
                    self.database_manager.log_websocket_action(
                        action='send_detection',
                        status='success',
                        message=f'Successfully sent {sent_count} detection records',
                        data_type='detection_results',
                        record_count=sent_count,
                        aicamera_id=self.aicamera_id,
                        checkpoint_id=self.checkpoint_id
                    )
                except Exception as db_exc:
                    self.logger.info(f"Skipped DB log (send_detection success): {db_exc}")
            
            return sent_count
            
        except Exception as e:
            self.logger.error(f"Error sending detection data: {e}")
            # Log error
            if self.database_manager:
                try:
                    self.database_manager.log_websocket_action(
                        action='send_detection',
                        status='failed',
                        message=f'Error sending detection data: {str(e)}',
                        data_type='detection_results',
                        aicamera_id=self.aicamera_id,
                        checkpoint_id=self.checkpoint_id
                    )
                except Exception as db_exc:
                    self.logger.warning(f"Skipped DB log (send_detection error): {db_exc}")
            return 0
    
    def _send_single_detection_sync(self, detection: Dict[str, Any]) -> bool:
        """
        Send single detection result to server (synchronous version).
        For Socket.IO: sends event 'message' (metadata) then event 'image' (base64) if image present.
        """
        try:
            data = {
                'type': 'detection_result',
                'aicamera_id': self.aicamera_id,
                'checkpoint_id': self.checkpoint_id,
                'timestamp': detection['timestamp'],
                'vehicles_count': detection['vehicles_count'],
                'plates_count': detection['plates_count'],
                'ocr_results': detection.get('ocr_results'),
                'vehicle_detections': detection.get('vehicle_detections'),
                'plate_detections': detection.get('plate_detections'),
                'processing_time_ms': detection.get('processing_time_ms'),
                'created_at': detection.get('created_at'),
            }
            if detection.get('original_image_path'):
                image_path = Path(detection['original_image_path'])
                if image_path.exists():
                    with open(image_path, 'rb') as f:
                        data['original_image'] = base64.b64encode(f.read()).decode('utf-8')
            if self.server_type == 'rest':
                return self._send_data_rest(data)
            if not self.sio or not self.sio.connected:
                return False
            message_data = {
                'content': {
                    'type': 'detection_result',
                    'aicamera_id': self.aicamera_id,
                    'checkpoint_id': self.checkpoint_id,
                    'timestamp': data['timestamp'],
                    'vehicles_count': data['vehicles_count'],
                    'plates_count': data['plates_count'],
                    'ocr_results': data.get('ocr_results'),
                    'vehicle_detections': data.get('vehicle_detections'),
                    'plate_detections': data.get('plate_detections'),
                    'processing_time_ms': data.get('processing_time_ms'),
                    'created_at': data.get('created_at'),
                },
                'camera_id': self.aicamera_id,
            }
            self.sio.emit('message', message_data)
            if data.get('original_image'):
                fn = f"detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                image_payload = {'data': data['original_image'], 'filename': fn, 'camera_id': self.aicamera_id}
                self.sio.emit('image', image_payload)
            return True
        except Exception as e:
            self.logger.error(f"Error preparing detection data for sending: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get WebSocket sender status.
        
        Returns:
            Dict[str, Any]: Current status information
        """
        return {
            'enabled': self.enabled,
            'running': self.running,
            'connected': self.connected if self.server_url else False,
            'server_url': self.server_url,
            'server_type': getattr(self, 'server_type', 'unknown'),
            'offline_mode': self.server_url is None,
            'aicamera_id': self.aicamera_id,
            'checkpoint_id': self.checkpoint_id,
            'retry_count': self.retry_count,
            'total_detections_sent': self.total_detections_sent,
            'last_detection_check': self.last_detection_check.isoformat() if self.last_detection_check else None,
            'detection_thread_alive': self.detection_thread.is_alive() if self.detection_thread else False,
        }
    
    def switch_to_rest_api(self) -> bool:
        """
        Switch to REST API mode.
        
        Returns:
            bool: True if switch successful, False otherwise
        """
        try:
            if self.server_type == 'rest':
                self.logger.info("Already in REST API mode")
                return True
            
            # Convert WebSocket URL back to HTTP
            rest_url = self.server_url
            if rest_url.startswith('wss://'):
                rest_url = rest_url.replace('wss://', 'https://')
            elif rest_url.startswith('ws://'):
                rest_url = rest_url.replace('ws://', 'http://')
            
            # Test REST API connection
            if self._test_rest_connection(rest_url):
                self.server_url = rest_url
                self.server_type = 'rest'
                self.connected = False  # Force reconnection
                self.logger.info(f"Switched to REST API mode: {self.server_url}")
                return True
            else:
                self.logger.error("Failed to switch to REST API - connection test failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error switching to REST API: {e}")
            return False
    
    def switch_to_socketio(self) -> bool:
        """
        Switch to Socket.IO mode.
        
        Returns:
            bool: True if switch successful, False otherwise
        """
        try:
            if self.server_type == 'socketio':
                self.logger.info("Already in Socket.IO mode")
                return True
            
            # Convert HTTP URL to WebSocket
            socketio_url = self.server_url
            if socketio_url.startswith('https://'):
                socketio_url = socketio_url.replace('https://', 'wss://')
            elif socketio_url.startswith('http://'):
                socketio_url = socketio_url.replace('http://', 'ws://')
            
            # Test Socket.IO connection
            if self._test_socketio_connection(socketio_url):
                self.server_url = socketio_url
                self.server_type = 'socketio'
                self.connected = False  # Force reconnection
                self.logger.info(f"Switched to Socket.IO mode: {self.server_url}")
                return True
            else:
                self.logger.error("Failed to switch to Socket.IO - connection test failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error switching to Socket.IO: {e}")
            return False
    
    def cleanup(self):
        """Cleanup WebSocket sender resources."""
        try:
            self.logger.info("Cleaning up WebSocket sender...")
            self.stop()
            self.logger.info("WebSocket sender cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during WebSocket sender cleanup: {e}")


def create_websocket_sender(database_manager=None, logger=None) -> WebSocketSender:
    """
    Factory function for WebSocket Sender.
    
    Args:
        database_manager: Database manager instance
        logger: Logger instance
        
    Returns:
        WebSocketSender: Configured WebSocket sender instance
    """
    return WebSocketSender(database_manager, logger)
