#!/usr/bin/env python3
"""
Camera Manager Service for AI Camera v2

This service manages camera operations using CameraHandler component
and provides high-level camera management functionality.

Features:
- Camera initialization and lifecycle management
- Video streaming for web interface
- Frame capture for inference pipeline
- Camera status monitoring and health checks
- Configuration management
- Error handling and recovery
- Auto-start capability
- Metadata tracking (NEW)

Author: AI Camera Team
Version: 2.0
Date: August 7, 2025
"""

import logging
import threading
import time
from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np
import os
import cv2

from edge.src.core.utils.logging_config import get_logger
from edge.src.components.camera_handler import make_json_serializable
from edge.src.core.config import AUTO_START_CAMERA, AUTO_START_STREAMING, STARTUP_DELAY

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Picamera2 control constants (libcamera values – no import needed at runtime
# because we pass these as plain ints through camera_handler.update_configuration)
# ---------------------------------------------------------------------------
# AfMode
_AF_MODE_MANUAL     = 0
_AF_MODE_AUTO       = 1
_AF_MODE_CONTINUOUS = 2   # Continuous Autofocus – best for moving vehicles
 
# AfSpeed
_AF_SPEED_NORMAL = 0
_AF_SPEED_FAST   = 1      # Faster AF convergence
 
# AeMeteringMode
_AE_METERING_CENTRE_WEIGHTED = 0   # Good default for road-centre LPR
 
# AeExposureMode
_AE_EXPOSURE_NORMAL = 0
_AE_EXPOSURE_SPORT  = 1   # Prefers shorter shutter → less motion blur on plates

class CameraManager:
    """
    Camera Manager Service for high-level camera operations.
    
    This service provides:
    - Camera initialization and startup
    - Video streaming management
    - Configuration management
    - Status monitoring
    - Auto-start functionality (NEW)
    - Metadata tracking (NEW)
    - LPR-optimised ISP auto-control setup (REFACTORED)
    
    Thread-safe: Uses CameraHandler's singleton pattern for safe camera access
    """
    
    def __init__(self, camera_handler, logger=None):
        self.camera_handler = camera_handler
        self.logger = logger or get_logger(__name__)
        self.auto_start_enabled = AUTO_START_CAMERA  # Auto-start from config
        self.auto_streaming_enabled = AUTO_START_STREAMING  # Auto-streaming from config
        self.startup_time = None
        
        # Metadata tracking (NEW) - Event-based only
        self.last_metadata = {}
        self.last_metadata_update = None
        
        # Manual capture directory (NEW)
        self.manual_capture_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'manual_capture')
        os.makedirs(self.manual_capture_dir, exist_ok=True)
        self.logger.info(f"Manual capture directory: {self.manual_capture_dir}")
    
    # ------------------------------------------------------------------
    # ISP Auto-Control helpers  (REFACTORED)
    # ------------------------------------------------------------------
 
    def _apply_lpr_auto_controls(self) -> bool:
        """
        Apply a minimal, LPR-optimised control set that hands image tuning
        back to the camera's 3A (Auto-Exposure, Auto-White-Balance, AutoFocus)
        algorithms.
 
        Called once after the camera has started streaming.  All values are
        passed through camera_handler.update_configuration() so the existing
        reconfiguration path is fully preserved.
 
        What we set and WHY:
          AeEnable=True           Re-enable AE in case any prior code disabled it.
          AwbEnable=True          Re-enable AWB; fixes colour casts from manual
                                  ColourGains that were set previously.
          AeMeteringMode=0        CentreWeighted – weights exposure toward the
                                  road/lane where plates appear.
          AeExposureMode=1        Sport mode – ISP biases toward shorter shutter
                                  speeds, reducing motion blur on moving plates
                                  while keeping everything else automatic.
          AfMode=2                Continuous AF – CM3 tracks focus in real time.
          AfSpeed=1               Fast AF convergence for vehicles entering frame.
 
        Returns:
            bool: True if controls applied successfully, False otherwise.
        """
        lpr_controls = {
            "controls": {
                # --- Auto Exposure & Gain ---
                "AeEnable": True,
                "AeMeteringMode": _AE_METERING_CENTRE_WEIGHTED,
                "AeExposureMode": _AE_EXPOSURE_SPORT,   # short shutter → less blur
 
                # --- Auto White Balance ---
                "AwbEnable": True,
 
                # --- Continuous Autofocus (CM3 lens) ---
                "AfMode": _AF_MODE_CONTINUOUS,
                "AfSpeed": _AF_SPEED_FAST,
            }
        }
 
        self.logger.info(
            "📷 [CAMERA_MANAGER] Applying LPR auto-controls: "
            "AE=auto/sport, AWB=auto, AF=continuous/fast"
        )
 
        try:
            success = self.camera_handler.update_configuration(lpr_controls)
            if success:
                self.logger.info(
                    "✅ [CAMERA_MANAGER] LPR auto-controls applied successfully – "
                    "ISP is now managing exposure, white-balance and focus."
                )
            else:
                self.logger.warning(
                    "⚠️  [CAMERA_MANAGER] update_configuration returned False "
                    "when applying LPR auto-controls."
                )
            return success
        except Exception as e:
            self.logger.error(
                f"❌ [CAMERA_MANAGER] Error applying LPR auto-controls: {e}"
            )
            return False
 
    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
        
    def initialize(self):
        """
        Initialize camera manager with auto-start capability.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        self.logger.debug(f"🔧 [CAMERA_MANAGER] initialize called")
        
        try:
            self.logger.info("🔧 [CAMERA_MANAGER] Initializing Camera Manager...")
            
            # Initialize camera handler with robust initialization
            if self.camera_handler:
                self.logger.debug(f"🔧 [CAMERA_MANAGER] initialize: calling camera_handler.initialize_camera()")
                success = self.camera_handler.initialize_camera()
                self.logger.debug(f"🔧 [CAMERA_MANAGER] initialize: camera_handler.initialize_camera() returned: {success}")
                
                if success:
                    self.logger.info("🔧 [CAMERA_MANAGER] Camera handler initialized successfully")
                    
                    # Check if camera is in fallback mode
                    self.logger.debug(f"🔧 [CAMERA_MANAGER] initialize: checking camera status")
                    camera_status = self.camera_handler.get_camera_status()
                    self.logger.debug(f"🔧 [CAMERA_MANAGER] initialize: camera_status: {camera_status}")
                    
                    if not camera_status['camera_ready']:
                        self.logger.info("🔧 [CAMERA_MANAGER] Camera handler initialized in fallback mode - ready for dynamic connection")
                        self.logger.info("🔧 [CAMERA_MANAGER] Camera manager will work normally but camera operations will be limited")
                        
                        # Auto-start camera if enabled (will work when camera becomes available)
                        if self.auto_start_enabled:
                            self.logger.info("🔧 [CAMERA_MANAGER] Auto-start enabled - will start camera when hardware becomes available")
                            return self._auto_start_camera_fallback()
                        else:
                            self.logger.info("🔧 [CAMERA_MANAGER] Auto-start disabled - camera ready for manual start when hardware available")
                            return True
                    else:
                        # Camera is ready - proceed with normal auto-start
                        if self.auto_start_enabled:
                            self.logger.info("🔧 [CAMERA_MANAGER] Auto-start enabled - starting camera automatically")
                            return self._auto_start_camera()
                        else:
                            self.logger.info("🔧 [CAMERA_MANAGER] Auto-start disabled - camera ready for manual start")
                            return True
                else:
                    self.logger.error("🔧 [CAMERA_MANAGER] Failed to initialize camera handler")
                    return False
            else:
                self.logger.error("🔧 [CAMERA_MANAGER] Camera handler not available")
                return False
                
        except Exception as e:
            self.logger.error(f"🔧 [CAMERA_MANAGER] Error initializing camera manager: {e}")
            return False
    
    def _auto_start_camera(self):
        """
        Auto-start camera functionality with streaming.
        
        Returns:
            bool: True if auto-start successful, False otherwise
        """
        try:
            self.logger.info("🚀 Starting auto-start sequence...")
            
            # Start camera
            if self.start():
                self.logger.info("✅ Camera auto-started successfully")
                self.startup_time = datetime.now()
                
                # Auto-start streaming if enabled
                if self.auto_streaming_enabled:
                    self.logger.info("🎥 Auto-streaming enabled - camera should be streaming now")
                    
                    # Verify streaming status
                    if self.camera_handler and self.camera_handler.streaming:
                        self.logger.info("✅ Camera streaming confirmed active")
                    else:
                        self.logger.warning("⚠️  Camera not streaming after auto-start")
                
                self.logger.info("🎯 === AUTO START CAMERA ABOUT TO RETURN TRUE ===")
                return True
            else:
                self.logger.error("❌ Failed to auto-start camera")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error in auto-start: {e}")
            return False
    
    def _auto_start_camera_fallback(self):
        """
        Auto-start camera in fallback mode - will attempt connection when hardware becomes available.
        
        Returns:
            bool: True if fallback mode started successfully, False otherwise
        """
        try:
            self.logger.info("🚀 Starting camera auto-start in fallback mode...")
            
            # Start a background thread to monitor camera availability
            self._fallback_monitor_thread = threading.Thread(
                target=self._monitor_camera_availability,
                name="CameraAvailabilityMonitor",
                daemon=True
            )
            self._fallback_monitor_thread.start()
            
            self.logger.info("✅ Camera availability monitor started - will connect when hardware becomes available")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error starting camera fallback mode: {e}")
            return False
    
    def _monitor_camera_availability(self):
        """
        Monitor camera availability and attempt connection when ready.
        """
        self.logger.info("🔍 Camera availability monitor started")
        
        while True:
            try:
                # Check if camera is now available
                camera_status = self.camera_handler.get_camera_status()
                
                if camera_status['camera_ready']:
                    self.logger.info("📷 Camera is now available - attempting to connect")
                    
                    # Try to connect to camera
                    if self.camera_handler.try_connect_camera():
                        self.logger.info("✅ Camera connected successfully - starting streaming")
                        
                        # Start streaming
                        if self.auto_streaming_enabled:
                            self.start_streaming()
                        
                        # Update startup time
                        self.startup_time = datetime.now()
                        
                        self.logger.info("🎉 Camera auto-start completed successfully")
                        break
                    else:
                        self.logger.warning("⚠️  Failed to connect to camera - will retry")
                
                # Wait before next check
                time.sleep(5.0)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"❌ Error in camera availability monitor: {e}")
                time.sleep(10.0)  # Wait longer on error
    # ------------------------------------------------------------------
    # Start / Stop / Restart
    # ------------------------------------------------------------------
    
    def start(self):
        """
        Start camera streaming and apply LPR-optimised ISP auto-controls.
 
        The auto-controls call replaces all previous hardcoded ISP overrides
        (manual ExposureTime, AnalogueGain, DigitalGain, ColourGains,
        manual focus step sequences) that caused stuttering, blur, and
        colour distortion.
 
        Returns:
            bool: True if camera started successfully, False otherwise
        """
        try:
            if not self.camera_handler:
                self.logger.error("Camera handler not available")
                return False
            
            success = self.camera_handler.start_camera()
            if success:
                self.startup_time = datetime.now()
                self.logger.info("Camera started successfully")
                
                # Skip metadata update during initialization to prevent hanging
                self.logger.info("📊 Skipping metadata update during initialization to prevent hang")
                # --------------------------------------------------------
                # REFACTORED: Apply LPR auto-controls once after start.
                # The ISP is already running at this point so the controls
                # are accepted without a full stop/configure/start cycle.
                # --------------------------------------------------------
                self._apply_lpr_auto_controls()
                return True
            else:
                self.logger.error("Failed to start camera")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting camera: {e}")
            return False
    
    def stop(self):
        """
        Stop camera streaming.
        
        Returns:
            bool: True if camera stopped successfully, False otherwise
        """
        try:
            if not self.camera_handler:
                self.logger.error("Camera handler not available")
                return False
            

            
            success = self.camera_handler.stop_camera()
            if success:
                self.logger.info("Camera stopped successfully")
                return True
            else:
                self.logger.error("Failed to stop camera")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping camera: {e}")
            return False
    
    def restart(self):
        """
        Restart camera.
        
        Returns:
            bool: True if camera restarted successfully, False otherwise
        """
        try:
            self.logger.info("Restarting camera...")
            self.stop()
            time.sleep(1)  # Brief pause
            return self.start()
        except Exception as e:
            self.logger.error(f"Error restarting camera: {e}")
            return False
    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def _update_metadata(self):
        """
        Update camera metadata from camera handler.
        Called after camera starts or configuration changes.
        """
        try:
            if self.camera_handler and self.camera_handler.streaming:
                metadata = self.camera_handler.get_metadata()
                if metadata:
                    self.last_metadata = metadata
                    self.last_metadata_update = datetime.now()
                    self.logger.info("Camera metadata updated successfully")
                else:
                    self.logger.warning("No metadata available from camera")
            else:
                self.logger.debug("Camera not streaming, skipping metadata update")
        except Exception as e:
            self.logger.warning(f"Error updating metadata: {e}")
    
    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    
    def reconfigure_camera_safely(self, new_config: Dict[str, Any]) -> bool:
        """
        Safely reconfigure camera by stopping, adjusting config, and restarting.
        This prevents conflicts during detection processing.

        NOTE: Do NOT pass manual ISP overrides (ExposureTime, AnalogueGain,
        DigitalGain, ColourGains) via new_config. Those fight the ISP and
        cause stuttering / colour distortion. Use only structural parameters
        (resolution, format, buffer_count, etc.) here.

        Args:
            new_config: New camera configuration parameters
            
        Returns:
            bool: True if reconfiguration successful, False otherwise
        """
        self.logger.info("🔄 [CAMERA_MANAGER] Starting safe camera reconfiguration...")
        
        try:
            if not self.camera_handler:
                self.logger.error("🔄 [CAMERA_MANAGER] Camera handler not available")
                return False
            
            # Use camera handler's safe reconfiguration method
            success = self.camera_handler.reconfigure_camera_safely(new_config)
            
            if success:
                self.logger.info("🔄 [CAMERA_MANAGER] ✅ Safe camera reconfiguration completed successfully")
                 # Re-apply LPR auto-controls after a structural reconfigure,
                # because reconfigure triggers a stop/start cycle which may
                # reset runtime controls to libcamera defaults.
                self._apply_lpr_auto_controls()
                self.camera_status = self.camera_handler.get_camera_status()
            else:
                self.logger.error("🔄 [CAMERA_MANAGER] Safe camera reconfiguration failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"🔄 [CAMERA_MANAGER] Safe reconfiguration error: {e}")
            return False
    # ------------------------------------------------------------------
    # Status & Health
    # ------------------------------------------------------------------
    def get_status(self):
        """
        Get comprehensive camera status.
        
        Returns:
            dict: Camera status information including metadata
        """
        self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status called")
        
        try:
            if not self.camera_handler:
                error_status = {
                    'initialized': False,
                    'streaming': False,
                    'error': 'Camera handler not available'
                }
                self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status: camera_handler not available, returning: {error_status}")
                return error_status
            
            # Get camera handler status
            self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status: calling camera_handler.get_camera_status()")
            camera_status = self.camera_handler.get_camera_status()
            self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status: camera_handler.get_camera_status() returned: {camera_status}")
            
            # Get configuration
            self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status: calling get_configuration()")
            config = self.get_configuration()
            self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status: get_configuration() returned: {config}")
            
            # Add manager-specific status
            status = {
                'initialized': camera_status.get('initialized', False),
                'streaming': camera_status.get('streaming', False),
                'auto_start_enabled': self.auto_start_enabled,
                'auto_streaming_enabled': getattr(self, 'auto_streaming_enabled', False),
                'uptime': None,
                'frame_count': camera_status.get('frame_count', 0),
                'average_fps': camera_status.get('average_fps', 0),
                'config': config,  # Use the corrected configuration
                'metadata': make_json_serializable(self.last_metadata),  # Add metadata to status
                'camera_handler': camera_status,
                'frame_buffer_ready': self.camera_handler.is_frame_buffer_ready() if self.camera_handler else False
            }
            
            # Calculate uptime
            if self.startup_time:
                uptime = (datetime.now() - self.startup_time).total_seconds()
                status['uptime'] = uptime
                self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status: calculated uptime: {uptime}")
            
            self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status: returning status: {status}")
            return status
            
        except Exception as e:
            self.logger.error(f"🔧 [CAMERA_MANAGER] Error getting camera status: {e}")
            error_status = {
                'initialized': False,
                'streaming': False,
                'error': str(e)
            }
            self.logger.debug(f"🔧 [CAMERA_MANAGER] get_status: returning error status: {error_status}")
            return error_status
    
    def update_configuration(self, config):
        """
        Update camera configuration.
        
        Args:
            config (dict): New configuration settings
            
        Returns:
            dict: Response with success status and message
        """
        try:
            if not self.camera_handler:
                return {
                    'success': False,
                    'error': 'Camera handler not available'
                }
            
            # Update configuration in camera handler
            success = self.camera_handler.update_configuration(config)
            
            if success:
                # Update metadata after configuration change (NEW)
                self._update_metadata()
                
                self.logger.info("Camera configuration updated successfully")
                return {
                    'success': True,
                    'message': 'Configuration updated successfully'
                }
            else:
                self.logger.error("Failed to update camera configuration")
                return {
                    'success': False,
                    'error': 'Failed to update configuration'
                }
                
        except Exception as e:
            self.logger.error(f"Error updating configuration: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def health_check(self):
        """
        Perform health check on camera system.
        
        Returns:
            dict: Health status information
        """
        self.logger.debug(f"🔧 [CAMERA_MANAGER] health_check called")
        
        try:
            self.logger.debug(f"🔧 [CAMERA_MANAGER] health_check: calling get_status()")
            status = self.get_status()
            self.logger.debug(f"🔧 [CAMERA_MANAGER] health_check: get_status() returned: {status}")
            
            health = {
                'status': 'healthy' if status.get('initialized', False) else 'unhealthy',
                'camera_initialized': status.get('initialized', False),
                'streaming_active': status.get('streaming', False),
                'auto_start_enabled': status.get('auto_start_enabled', False),
                'uptime': status.get('uptime', 0),
                'frame_count': status.get('frame_count', 0),
                'average_fps': status.get('average_fps', 0),
                'metadata': status.get('metadata', {}),  # Include metadata in health check
                'timestamp': datetime.now().isoformat()
            }
            
            if not status.get('initialized', False):
                health['status'] = 'unhealthy'
                health['error'] = status.get('error', 'Camera not initialized')
            
            self.logger.debug(f"🔧 [CAMERA_MANAGER] health_check: returning health status: {health}")
            return health
            
        except Exception as e:
            self.logger.error(f"🔧 [CAMERA_MANAGER] Error in health check: {e}")
            error_health = {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            self.logger.debug(f"🔧 [CAMERA_MANAGER] health_check: returning error health: {error_health}")
            return error_health
    # ------------------------------------------------------------------
    # Settings / Config accessors
    # ------------------------------------------------------------------
    def get_available_settings(self):
        """
        Get available camera settings.
        
        Returns:
            dict: Available camera settings
        """
        try:
            if self.camera_handler:
                config = self.camera_handler.get_configuration()
                # Extract the actual configuration data
                if 'current_config' in config:
                    return config['current_config']
                else:
                    return config
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Error getting available settings: {e}")
            return {}
    
    def get_configuration(self):
        """
        Get current camera configuration.
        
        Returns:
            dict: Current configuration
        """
        try:
            if self.camera_handler:
                config = self.camera_handler.get_configuration()
                # Return the configuration in the format expected by the frontend
                if 'current_config' in config:
                    return config['current_config']
                else:
                    return config
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Error getting configuration: {e}")
            return {}
    # ------------------------------------------------------------------
    # Stream / Frame helpers
    # ------------------------------------------------------------------
    def ensure_camera_streaming(self):
        """
        Ensure camera is initialized and streaming.
        
        Returns:
            bool: True if camera is streaming, False otherwise
        """
        try:
            if not self.camera_handler:
                self.logger.error("Camera handler not available")
                return False
            
            # Check if camera is initialized
            if not self.camera_handler.initialized:
                self.logger.info("Camera not initialized, initializing...")
                if not self.camera_handler.initialize_camera():
                    self.logger.error("Failed to initialize camera")
                    return False
            
            # Check if camera is streaming
            if not self.camera_handler.streaming:
                self.logger.info("Camera not streaming, starting...")
                if not self.camera_handler.start_camera():
                    self.logger.error("Failed to start camera")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error ensuring camera streaming: {e}")
            return False
    
    def capture_frame(self):
        """
        Capture a single frame from the camera for detection processing.
        Uses unified camera handler method with buffer source for thread-safe access.
        
        Returns:
            numpy.ndarray or None: Camera frame as numpy array, None if capture failed
        """
        self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_frame called")
        
        try:
            if not self.camera_handler or not self.camera_handler.initialized:
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_frame failed: camera_handler={self.camera_handler is not None}, initialized={self.camera_handler.initialized if self.camera_handler else False}")
                return None
            
            # Check if frame buffer is ready
            if not self.camera_handler.is_frame_buffer_ready():
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_frame failed: frame buffer not ready")
                return None
            
            self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_frame: calling camera_handler.capture_frame(source='buffer')")
            
            # Use unified camera handler method with buffer source
            frame_data = self.camera_handler.capture_frame(source="buffer", stream_type="main", include_metadata=False)
            
            self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_frame: camera_handler returned frame_data type: {type(frame_data)}")
            
            if isinstance(frame_data, dict):
                self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_frame: frame data keys: {list(frame_data.keys())}")
                if 'frame' in frame_data:
                    frame = frame_data['frame']
                    self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_frame: extracted frame shape: {frame.shape if hasattr(frame, 'shape') else 'No shape'}")
                    return frame
                else:
                    self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_frame: frame data dict does not contain 'frame' key")
                    return None
            elif isinstance(frame_data, np.ndarray):
                self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_frame: frame data is numpy array, shape: {frame_data.shape}")
                return frame_data
            else:
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_frame: invalid frame data type: {type(frame_data)}")
                return None
                
        except Exception as e:
            self.logger.error(f"🔧 [CAMERA_MANAGER] capture_frame error: {e}")
            return None
    


    def capture_image(self) -> Optional[Dict[str, Any]]:
        """
        Capture and save a single image to manual_capture directory.
        Uses unified camera handler method with direct source for high-quality capture.
        
        Returns:
            Dict[str, Any] or None: Capture result with file path and metadata, None if failed
        """
        self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_image called")
        
        try:
            if not self.camera_handler or not self.camera_handler.initialized:
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_image failed: camera_handler={self.camera_handler is not None}, initialized={self.camera_handler.initialized if self.camera_handler else False}")
                return None
            
            # Check if frame buffer is ready
            if not self.camera_handler.is_frame_buffer_ready():
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_image failed: frame buffer not ready")
                return None
            
            self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_image: calling camera_handler.capture_frame(source='direct', stream_type='main', include_metadata=True)")
            
            # Use unified camera handler method with direct source for high quality
            frame_data = self.camera_handler.capture_frame(source="direct", stream_type="main", include_metadata=True)
            
            if frame_data is None:
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_image: no frame data available for capture")
                return None
            
            self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_image: camera_handler returned frame_data type: {type(frame_data)}")
            
            # Extract frame from frame_data
            frame = None
            if isinstance(frame_data, dict) and 'frame' in frame_data:
                frame = frame_data['frame']
                self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_image: extracted frame from dict, shape: {frame.shape if hasattr(frame, 'shape') else 'No shape'}")
            elif isinstance(frame_data, np.ndarray):
                frame = frame_data
                self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_image: frame_data is numpy array, shape: {frame.shape}")
            else:
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_image: invalid frame data format: {type(frame_data)}")
                return None
            
            if frame is None or not isinstance(frame, np.ndarray):
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_image: frame is None or not a numpy array")
                return None
            
            if frame.size == 0 or len(frame.shape) != 3:
                self.logger.warning(f"🔧 [CAMERA_MANAGER] capture_image: invalid frame shape: {frame.shape}")
                return None
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            filename = f"manual_capture_{timestamp}.jpg"
            filepath = os.path.join(self.manual_capture_dir, filename)
            
            # Ensure directory exists
            os.makedirs(self.manual_capture_dir, exist_ok=True)
            
            self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_image: saving image to {filepath}")
            
            # Save image with high quality
            success = cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            if not success:
                self.logger.error(f"🔧 [CAMERA_MANAGER] capture_image: failed to save image to {filepath}")
                return None
            
            # Get file size
            file_size = os.path.getsize(filepath)
            
            # Get frame dimensions
            height, width = frame.shape[:2]
            
            self.logger.info(f"🔧 [CAMERA_MANAGER] capture_image: image captured successfully: {filepath} ({width}x{height}, {file_size} bytes)")
            
            result = {
                'success': True,
                'saved_path': filepath,
                'filename': filename,
                'size': file_size,
                'dimensions': f"{width}x{height}",
                'timestamp': timestamp,
                'timestamp_iso': datetime.now().isoformat()
            }
            
            self.logger.debug(f"🔧 [CAMERA_MANAGER] capture_image: returning result: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"🔧 [CAMERA_MANAGER] capture_image error: {e}")
            return None
    
    def get_stream_generator(self):
        """
        Get video stream generator for web interface.
        
        Returns:
            generator: Video stream generator
        """
        try:
            if not self.camera_handler:
                self.logger.error("Camera handler not available for streaming")
                return None
            
            return self.camera_handler.get_stream_generator()
            
        except Exception as e:
            self.logger.error(f"Error getting stream generator: {e}")
            return None
    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def set_auto_start(self, enabled):
        """
        Set auto-start configuration.
        
        Args:
            enabled (bool): Whether to enable auto-start
        """
        self.auto_start_enabled = enabled
        self.logger.info(f"Auto-start {'enabled' if enabled else 'disabled'}")
    
    def get_uptime(self):
        """
        Get camera uptime in seconds.
        
        Returns:
            float: Uptime in seconds, 0 if not started
        """
        if self.startup_time:
            return (datetime.now() - self.startup_time).total_seconds()
        return 0.0
    
    def _monitor_camera_availability(self):
        """
        Monitor camera availability in background thread.
        This method runs in a separate thread and continuously checks if camera hardware becomes available.
        """
        self.logger.info("🔍 Starting camera availability monitoring...")
        
        check_interval = 5.0  # Check every 5 seconds
        max_retries = 60  # Try for 5 minutes (60 * 5 seconds)
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Check if camera is now available
                camera_status = self.camera_handler.get_camera_status()
                
                if camera_status['camera_ready']:
                    self.logger.info("🎉 Camera hardware detected! Attempting to initialize...")
                    
                    # Try to initialize camera
                    if self.camera_handler.initialize_camera():
                        self.logger.info("✅ Camera initialized successfully")
                        
                        # Auto-start camera if enabled
                        if self.auto_start_enabled:
                            self.logger.info("🚀 Auto-starting camera...")
                            if self._auto_start_camera():
                                self.logger.info("✅ Camera auto-started successfully")
                                break
                            else:
                                self.logger.warning("⚠️  Auto-start failed, but camera is initialized")
                                break
                        else:
                            self.logger.info("✅ Camera ready for manual start")
                            break
                    else:
                        self.logger.warning("⚠️  Camera hardware detected but initialization failed")
                else:
                    self.logger.debug(f"📋 Camera not ready yet (attempt {retry_count + 1}/{max_retries})")
                    if retry_count % 12 == 0:  # Log every minute (12 * 5 seconds)
                        self.logger.info(f"⏳ Waiting for camera hardware... (attempt {retry_count + 1}/{max_retries})")
                
                retry_count += 1
                time.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"❌ Error in camera availability monitoring: {e}")
                retry_count += 1
                time.sleep(check_interval)
        
        if retry_count >= max_retries:
            self.logger.warning("⏰ Camera availability monitoring timed out - camera hardware not detected")
        else:
            self.logger.info("✅ Camera availability monitoring completed")
    
    def cleanup(self):
        """
        Cleanup camera manager resources.
        """
        try:
            self.logger.info("Cleaning up camera manager...")
            
            if self.camera_handler:
                self.camera_handler.close_camera()
            
            self.logger.info("Camera manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


def create_camera_manager(camera_handler=None, logger=None):
    """
    Factory function to create camera manager instance.
    
    Args:
        camera_handler: Camera handler instance
        logger: Logger instance
        
    Returns:
        CameraManager: Camera manager instance
    """
    if camera_handler is None:
        # Try to get camera handler from dependency container
        try:
            from edge.src.core.dependency_container import get_service
            camera_handler = get_service('camera_handler')
        except Exception as e:
            logger = logger or get_logger(__name__)
            logger.warning(f"Could not get camera handler from DI container: {e}")
    
    return CameraManager(camera_handler, logger)
