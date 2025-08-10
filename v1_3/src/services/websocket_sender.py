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

import asyncio
import websockets
import json
import base64
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from v1_3.src.core.dependency_container import get_service
from v1_3.src.core.utils.logging_config import get_logger
from v1_3.src.core.config import (
    WEBSOCKET_SERVER_URL, SENDER_INTERVAL, HEALTH_SENDER_INTERVAL,
    WEBSOCKET_SENDER_ENABLED, WEBSOCKET_CONNECTION_TIMEOUT, 
    WEBSOCKET_RETRY_INTERVAL, WEBSOCKET_MAX_RETRIES
)

logger = get_logger(__name__)


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
        self.logger = logger or get_logger(__name__)
        self.database_manager = database_manager
        
        # WebSocket connection
        self.websocket = None
        self.connected = False
        self.server_url = WEBSOCKET_SERVER_URL
        
        # Threading
        self.detection_thread = None
        self.health_thread = None
        self.running = False
        self.stop_event = threading.Event()
        
        # Status tracking
        self.last_detection_check = None
        self.last_health_check = None
        self.retry_count = 0
        self.total_detections_sent = 0
        self.total_health_sent = 0
        
        # Configuration
        self.enabled = WEBSOCKET_SENDER_ENABLED
        self.connection_timeout = WEBSOCKET_CONNECTION_TIMEOUT
        self.retry_interval = WEBSOCKET_RETRY_INTERVAL
        self.max_retries = WEBSOCKET_MAX_RETRIES
        
        self.logger.info("WebSocketSender initialized")
    
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
                self.logger.warning("WEBSOCKET_SERVER_URL not configured")
                return False
            
            # Get database manager from DI container if not provided
            if not self.database_manager:
                self.database_manager = get_service('database_manager')
            
            if not self.database_manager:
                self.logger.error("Database manager not available")
                return False
            
            self.logger.info(f"WebSocket sender initialized for server: {self.server_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WebSocket sender: {e}")
            return False
    
    async def connect(self) -> bool:
        """
        Connect to WebSocket server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.connected:
                return True
            
            self.logger.info(f"Connecting to WebSocket server: {self.server_url}")
            
            # Connect with timeout
            self.websocket = await asyncio.wait_for(
                websockets.connect(self.server_url),
                timeout=self.connection_timeout
            )
            
            self.connected = True
            self.retry_count = 0
            
            # Log successful connection
            if self.database_manager:
                self.database_manager.log_websocket_action(
                    action='connect',
                    status='success',
                    message=f'Connected to {self.server_url}'
                )
            
            self.logger.info("WebSocket connection established")
            return True
            
        except Exception as e:
            self.connected = False
            self.retry_count += 1
            
            # Log connection failure
            if self.database_manager:
                self.database_manager.log_websocket_action(
                    action='connect',
                    status='failed',
                    message=f'Connection failed: {str(e)}'
                )
            
            self.logger.error(f"WebSocket connection failed: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """
        Disconnect from WebSocket server.
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
            
            self.connected = False
            self.websocket = None
            
            # Log disconnection
            if self.database_manager:
                self.database_manager.log_websocket_action(
                    action='disconnect',
                    status='success',
                    message='Disconnected from server'
                )
            
            self.logger.info("WebSocket disconnected")
            return True
            
        except Exception as e:
            self.logger.error(f"WebSocket disconnection error: {e}")
            return False
    
    async def send_data(self, data: Dict[str, Any]) -> bool:
        """
        Send data via WebSocket.
        
        Args:
            data: Data to send
            
        Returns:
            bool: True if send successful, False otherwise
        """
        try:
            if not self.connected or not self.websocket:
                if not await self.connect():
                    return False
            
            # Convert data to JSON
            json_data = json.dumps(data, default=str)
            
            # Send data
            await self.websocket.send(json_data)
            
            # Wait for response with timeout
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=10.0
            )
            
            self.logger.debug(f"Server response: {response}")
            return True
            
        except Exception as e:
            self.logger.error(f"WebSocket send error: {e}")
            self.connected = False
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
            
            # Start detection sender thread
            self.detection_thread = threading.Thread(
                target=self._detection_sender_loop,
                name="WebSocket-Detection-Sender",
                daemon=True
            )
            self.detection_thread.start()
            
            # Start health sender thread
            self.health_thread = threading.Thread(
                target=self._health_sender_loop,
                name="WebSocket-Health-Sender",
                daemon=True
            )
            self.health_thread.start()
            
            self.logger.info("WebSocket sender service started")
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
            
            # Disconnect WebSocket
            if self.connected:
                asyncio.run(self.disconnect())
            
            # Wait for threads to finish
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=5.0)
            
            if self.health_thread and self.health_thread.is_alive():
                self.health_thread.join(timeout=5.0)
            
            self.logger.info("WebSocket sender service stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping WebSocket sender: {e}")
    
    def _detection_sender_loop(self):
        """Main loop for detection data sender thread."""
        self.logger.info("Detection sender thread started")
        
        while self.running and not self.stop_event.is_set():
            try:
                self.last_detection_check = datetime.now()
                sent_count = self._send_detection_data()
                
                if sent_count > 0:
                    self.total_detections_sent += sent_count
                    self.logger.info(f"Sent {sent_count} detection records to server")
                
                # Wait for next interval or stop event
                if self.stop_event.wait(SENDER_INTERVAL):
                    break
                    
            except Exception as e:
                self.logger.error(f"Error in detection sender loop: {e}")
                # Wait before retrying
                if self.stop_event.wait(SENDER_INTERVAL):
                    break
        
        self.logger.info("Detection sender thread stopped")
    
    def _health_sender_loop(self):
        """Main loop for health status sender thread."""
        self.logger.info("Health sender thread started")
        
        while self.running and not self.stop_event.is_set():
            try:
                self.last_health_check = datetime.now()
                sent_count = self._send_health_data()
                
                if sent_count > 0:
                    self.total_health_sent += sent_count
                    self.logger.info(f"Sent {sent_count} health records to server")
                
                # Wait for next interval or stop event
                if self.stop_event.wait(HEALTH_SENDER_INTERVAL):
                    break
                    
            except Exception as e:
                self.logger.error(f"Error in health sender loop: {e}")
                # Wait before retrying
                if self.stop_event.wait(HEALTH_SENDER_INTERVAL):
                    break
        
        self.logger.info("Health sender thread stopped")
    
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
                self.database_manager.log_websocket_action(
                    action='send_detection',
                    status='no_data',
                    message='No detection data to send',
                    data_type='detection_results',
                    record_count=0
                )
                return 0
            
            sent_count = 0
            
            for detection in unsent_detections:
                success = asyncio.run(self._send_single_detection(detection))
                
                if success:
                    # Mark as sent in database
                    self.database_manager.mark_detection_result_sent(
                        detection['id'], 
                        'Successfully sent to server'
                    )
                    sent_count += 1
                else:
                    # Log send failure
                    self.database_manager.log_websocket_action(
                        action='send_detection',
                        status='failed',
                        message=f'Failed to send detection ID {detection["id"]}',
                        data_type='detection_results',
                        record_count=1
                    )
            
            if sent_count > 0:
                # Log successful sends
                self.database_manager.log_websocket_action(
                    action='send_detection',
                    status='success',
                    message=f'Successfully sent {sent_count} detection records',
                    data_type='detection_results',
                    record_count=sent_count
                )
            
            return sent_count
            
        except Exception as e:
            self.logger.error(f"Error sending detection data: {e}")
            # Log error
            if self.database_manager:
                self.database_manager.log_websocket_action(
                    action='send_detection',
                    status='failed',
                    message=f'Error sending detection data: {str(e)}',
                    data_type='detection_results'
                )
            return 0
    
    def _send_health_data(self) -> int:
        """
        Send unsent health check data to server.
        
        Returns:
            int: Number of records sent successfully
        """
        if not self.database_manager:
            return 0
        
        try:
            # Get unsent health checks
            unsent_health = self.database_manager.get_unsent_health_checks()
            
            if not unsent_health:
                # Log no data to send
                self.database_manager.log_websocket_action(
                    action='send_health',
                    status='no_data',
                    message='No health data to send',
                    data_type='health_checks',
                    record_count=0
                )
                return 0
            
            sent_count = 0
            
            for health_check in unsent_health:
                success = asyncio.run(self._send_single_health_check(health_check))
                
                if success:
                    # Mark as sent in database
                    self.database_manager.mark_health_check_sent(
                        health_check['id'], 
                        'Successfully sent to server'
                    )
                    sent_count += 1
                else:
                    # Log send failure
                    self.database_manager.log_websocket_action(
                        action='send_health',
                        status='failed',
                        message=f'Failed to send health check ID {health_check["id"]}',
                        data_type='health_checks',
                        record_count=1
                    )
            
            if sent_count > 0:
                # Log successful sends
                self.database_manager.log_websocket_action(
                    action='send_health',
                    status='success',
                    message=f'Successfully sent {sent_count} health check records',
                    data_type='health_checks',
                    record_count=sent_count
                )
            
            return sent_count
            
        except Exception as e:
            self.logger.error(f"Error sending health data: {e}")
            # Log error
            if self.database_manager:
                self.database_manager.log_websocket_action(
                    action='send_health',
                    status='failed',
                    message=f'Error sending health data: {str(e)}',
                    data_type='health_checks'
                )
            return 0
    
    async def _send_single_detection(self, detection: Dict[str, Any]) -> bool:
        """
        Send single detection result to server.
        
        Args:
            detection: Detection result data
            
        Returns:
            bool: True if send successful, False otherwise
        """
        try:
            # Prepare data for sending
            data = {
                'type': 'detection_result',
                'timestamp': detection['timestamp'],
                'vehicles_count': detection['vehicles_count'],
                'plates_count': detection['plates_count'],
                'ocr_results': detection['ocr_results'],
                'vehicle_detections': detection['vehicle_detections'],
                'plate_detections': detection['plate_detections'],
                'processing_time_ms': detection['processing_time_ms'],
                'created_at': detection['created_at']
            }
            
            # Add image data if available
            if detection['annotated_image_path']:
                image_path = Path(detection['annotated_image_path'])
                if image_path.exists():
                    with open(image_path, 'rb') as f:
                        image_data = base64.b64encode(f.read()).decode('utf-8')
                        data['annotated_image'] = image_data
            
            # Add cropped plate images if available
            if detection['cropped_plates_paths']:
                try:
                    plate_paths = json.loads(detection['cropped_plates_paths'])
                    cropped_images = []
                    
                    for path in plate_paths:
                        plate_path = Path(path)
                        if plate_path.exists():
                            with open(plate_path, 'rb') as f:
                                plate_image = base64.b64encode(f.read()).decode('utf-8')
                                cropped_images.append(plate_image)
                    
                    data['cropped_plates'] = cropped_images
                except Exception as e:
                    self.logger.warning(f"Error processing cropped plate images: {e}")
            
            # Send to server
            return await self.send_data(data)
            
        except Exception as e:
            self.logger.error(f"Error preparing detection data for sending: {e}")
            return False
    
    async def _send_single_health_check(self, health_check: Dict[str, Any]) -> bool:
        """
        Send single health check result to server.
        
        Args:
            health_check: Health check data
            
        Returns:
            bool: True if send successful, False otherwise
        """
        try:
            # Prepare data for sending
            data = {
                'type': 'health_check',
                'timestamp': health_check['timestamp'],
                'component': health_check['component'],
                'status': health_check['status'],
                'message': health_check['message'],
                'details': health_check['details'],
                'created_at': health_check['created_at']
            }
            
            # Send to server
            return await self.send_data(data)
            
        except Exception as e:
            self.logger.error(f"Error preparing health check data for sending: {e}")
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
            'connected': self.connected,
            'server_url': self.server_url,
            'retry_count': self.retry_count,
            'total_detections_sent': self.total_detections_sent,
            'total_health_sent': self.total_health_sent,
            'last_detection_check': self.last_detection_check.isoformat() if self.last_detection_check else None,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'detection_thread_alive': self.detection_thread.is_alive() if self.detection_thread else False,
            'health_thread_alive': self.health_thread.is_alive() if self.health_thread else False
        }
    
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
