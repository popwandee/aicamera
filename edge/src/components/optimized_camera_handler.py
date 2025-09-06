#!/usr/bin/env python3
"""
Optimized Camera Handler Component for AI Camera v2.0

This component provides enhanced camera operations using Picamera2 with:
- Unified capture methods for frames and metadata
- Enhanced autofocus and low-light optimization
- Robust singleton pattern implementation
- Optimal resource management and reconfiguration flow
- Advanced camera status and metadata retrieval

Features:
- Picamera2 integration with fallback support
- Unified capture_frame method with multiple sources and types
- Enhanced camera controls (autofocus, low-light adjustment)
- Thread-safe singleton pattern with proper resource management
- Optimized stop/release/reconfigure workflow
- Comprehensive camera status and metadata APIs

Author: AI Camera Team
Version: 2.0
Date: December 2025
"""

import threading
import time
import multiprocessing
from typing import Dict, Any, Optional, Tuple, Union, Literal
from pathlib import Path
import json
import queue
import os
import cv2
import numpy as np
from datetime import datetime
import weakref
import atexit
from contextlib import contextmanager

from edge.src.core.utils.logging_config import get_logger

logger = get_logger(__name__)

# Type definitions
CaptureSource = Literal["direct", "buffer"]
StreamType = Literal["main", "lores", "both"]
QualityMode = Literal["normal", "low_light", "bright", "high_quality"]

def make_json_serializable(obj: Any) -> Any:
    """
    Convert any object to JSON-serializable format.
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable object
    """
    if obj is None:
        return None
    elif isinstance(obj, (int, float, str, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif hasattr(obj, '__dict__'):
        # Handle objects with attributes
        if hasattr(obj, 'name'):
            return str(obj.name)
        elif hasattr(obj, '__str__'):
            return str(obj)
        else:
            return str(type(obj).__name__)
    else:
        return str(obj)

def check_camera_availability():
    """
    Enhanced camera availability check with detailed diagnostics.
    
    Returns:
        Dict: Comprehensive availability status with details
    """
    status = {
        'hardware_available': False,
        'software_available': False,
        'picamera2_available': False,
        'libcamera_available': False,
        'camera_ready': False,
        'details': {},
        'diagnostics': {}
    }
    
    # Check for camera hardware
    try:
        camera_devices = ['/dev/video0', '/dev/video1', '/dev/video2', '/dev/media0']
        available_devices = []
        
        for device in camera_devices:
            if os.path.exists(device):
                available_devices.append(device)
                status['hardware_available'] = True
        
        if available_devices:
            status['details']['camera_devices'] = available_devices
        
        # Check CSI camera interface
        if os.path.exists('/sys/class/video4linux'):
            video_devices = os.listdir('/sys/class/video4linux')
            if video_devices:
                status['hardware_available'] = True
                status['details']['video4linux_devices'] = video_devices
                
    except Exception as e:
        status['details']['hardware_check_error'] = str(e)
    
    # Check for libcamera with version info
    try:
        import libcamera
        status['libcamera_available'] = True
        status['details']['libcamera_version'] = getattr(libcamera, '__version__', 'unknown')
        
        # Check libcamera controls availability
        try:
            from libcamera import controls
            status['details']['libcamera_controls'] = True
        except ImportError:
            status['details']['libcamera_controls'] = False
            
    except ImportError:
        status['details']['libcamera_error'] = 'libcamera not available'
    except Exception as e:
        status['details']['libcamera_error'] = str(e)
    
    # Check for picamera2 with enhanced detection
    try:
        # Try system picamera2 first
        import sys
        sys.path.insert(0, '/usr/lib/python3/dist-packages')
        from picamera2 import Picamera2
        from picamera2.encoders import JpegEncoder
        from picamera2.outputs import FileOutput
        
        status['picamera2_available'] = True
        status['details']['picamera2_source'] = 'system'
        status['details']['picamera2_version'] = getattr(Picamera2, '__version__', 'unknown')
        
    except ImportError:
        try:
            # Fallback to pip version
            from picamera2 import Picamera2
            from picamera2.encoders import JpegEncoder
            from picamera2.outputs import FileOutput
            
            status['picamera2_available'] = True
            status['details']['picamera2_source'] = 'pip'
            
        except ImportError:
            status['details']['picamera2_error'] = 'picamera2 not available'
        except Exception as e:
            status['details']['picamera2_error'] = str(e)
    except Exception as e:
        status['details']['picamera2_error'] = str(e)
    
    # Overall readiness assessment
    status['software_available'] = status['libcamera_available'] and status['picamera2_available']
    status['camera_ready'] = status['hardware_available'] and status['software_available']
    
    # Enhanced diagnostics
    status['diagnostics'] = {
        'timestamp': datetime.now().isoformat(),
        'system_check': {
            'os_exists': os.path.exists('/dev'),
            'video4linux_exists': os.path.exists('/sys/class/video4linux'),
            'media_exists': os.path.exists('/dev/media0')
        }
    }
    
    return status

class CameraEnhancementEngine:
    """
    Enhanced camera controls for autofocus and environmental adaptation.
    """
    
    def __init__(self, camera_instance):
        self.camera = camera_instance
        self.logger = logger
        
        # Enhancement state
        self.autofocus_enabled = True
        self.auto_exposure_enabled = True
        self.noise_reduction_enabled = True
        
        # Environmental adaptation parameters
        self.low_light_threshold = 50000  # ExposureTime microseconds
        self.bright_light_threshold = 1000  # ExposureTime microseconds
        self.focus_scan_range = (0.0, 10.0)  # Focus range in diopters
        
        # Performance tracking
        self.last_enhancement_time = 0
        self.enhancement_interval = 1.0  # seconds
        
    def enhance_for_conditions(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environmental enhancements based on current conditions.
        
        Args:
            metadata: Current camera metadata
            
        Returns:
            Dict: Applied enhancements and their results
        """
        enhancements = {
            'applied': [],
            'exposure_assessment': 'unknown',
            'focus_quality': 'unknown',
            'lighting_condition': 'unknown'
        }
        
        try:
            # Assess current conditions
            exposure_time = metadata.get("ExposureTime", 0)
            analogue_gain = metadata.get("AnalogueGain", 1.0)
            focus_fom = metadata.get("FocusFoM", 0)
            
            # Classify lighting condition
            if exposure_time > self.low_light_threshold:
                lighting_condition = "low_light"
            elif exposure_time < self.bright_light_threshold:
                lighting_condition = "bright_light"  
            else:
                lighting_condition = "normal"
                
            enhancements['lighting_condition'] = lighting_condition
            
            # Apply lighting-specific enhancements
            if lighting_condition == "low_light":
                self._enhance_for_low_light(enhancements)
            elif lighting_condition == "bright_light":
                self._enhance_for_bright_light(enhancements)
            else:
                self._enhance_for_normal_light(enhancements)
            
            # Apply autofocus if enabled
            if self.autofocus_enabled:
                focus_result = self._apply_autofocus(focus_fom)
                if focus_result:
                    enhancements['applied'].append(focus_result)
                    
            # Assess image quality
            enhancements['exposure_assessment'] = self._assess_exposure_adequacy(metadata)
            enhancements['focus_quality'] = self._assess_focus_quality(metadata)
            
        except Exception as e:
            self.logger.warning(f"Enhancement engine error: {e}")
            enhancements['error'] = str(e)
            
        return enhancements
    
    def _enhance_for_low_light(self, enhancements: Dict[str, Any]):
        """Apply low-light specific optimizations."""
        try:
            if not self.camera or not self.camera.picam2:
                return
                
            controls = {}
            
            # Increase noise reduction
            if self.noise_reduction_enabled:
                controls["NoiseReductionMode"] = 2  # High quality
                enhancements['applied'].append("noise_reduction_high")
            
            # Optimize exposure for low light
            controls["ExposureTime"] = min(33333, 66666)  # Cap at 1/15s to prevent motion blur
            controls["AnalogueGain"] = min(8.0, 16.0)  # Reasonable gain limit
            
            # Apply lens shading correction
            controls["LensShadingMapMode"] = 1
            enhancements['applied'].append("lens_shading_correction")
            
            if controls:
                self.camera.picam2.set_controls(controls)
                enhancements['applied'].append("low_light_optimization")
                
        except Exception as e:
            self.logger.warning(f"Low light enhancement failed: {e}")
    
    def _enhance_for_bright_light(self, enhancements: Dict[str, Any]):
        """Apply bright light specific optimizations."""
        try:
            if not self.camera or not self.camera.picam2:
                return
                
            controls = {}
            
            # Reduce noise reduction for sharpness
            controls["NoiseReductionMode"] = 0  # Off
            enhancements['applied'].append("noise_reduction_off")
            
            # Optimize exposure for bright conditions
            controls["ExposureTime"] = max(100, 1000)  # Fast exposure
            controls["AnalogueGain"] = 1.0  # Minimum gain
            
            # Enable sharpening
            controls["Sharpness"] = 1.5
            enhancements['applied'].append("sharpening_enabled")
            
            if controls:
                self.camera.picam2.set_controls(controls)
                enhancements['applied'].append("bright_light_optimization")
                
        except Exception as e:
            self.logger.warning(f"Bright light enhancement failed: {e}")
    
    def _enhance_for_normal_light(self, enhancements: Dict[str, Any]):
        """Apply normal lighting optimizations."""
        try:
            if not self.camera or not self.camera.picam2:
                return
                
            controls = {}
            
            # Balanced noise reduction
            controls["NoiseReductionMode"] = 1  # Normal
            
            # Auto exposure with reasonable limits
            controls["AeEnable"] = True
            controls["AeConstraintMode"] = 0  # Normal constraint
            
            # Balanced sharpness
            controls["Sharpness"] = 1.0
            
            if controls:
                self.camera.picam2.set_controls(controls)
                enhancements['applied'].append("normal_light_optimization")
                
        except Exception as e:
            self.logger.warning(f"Normal light enhancement failed: {e}")
    
    def _apply_autofocus(self, current_fom: float) -> Optional[str]:
        """
        Apply intelligent autofocus based on current focus quality.
        
        Args:
            current_fom: Current focus figure of merit
            
        Returns:
            Optional[str]: Description of applied autofocus action
        """
        try:
            # Skip if too frequent
            current_time = time.time()
            if current_time - self.last_enhancement_time < self.enhancement_interval:
                return None
                
            self.last_enhancement_time = current_time
            
            if not self.camera or not self.camera.picam2:
                return None
            
            # Assess focus quality
            if current_fom < 400:  # Poor focus
                # Trigger autofocus scan
                try:
                    from libcamera import controls
                    
                    # Set autofocus mode to continuous
                    self.camera.picam2.set_controls({
                        "AfMode": controls.AfModeEnum.Continuous,
                        "AfTrigger": controls.AfTriggerEnum.Start
                    })
                    
                    return "autofocus_triggered_poor_quality"
                    
                except ImportError:
                    # Fallback to lens position adjustment
                    lens_position = 5.0  # Mid-range focus
                    self.camera.picam2.set_controls({"LensPosition": lens_position})
                    return "manual_focus_adjustment"
                    
            elif current_fom > 800:  # Excellent focus
                # Maintain current settings
                return "focus_maintained_excellent"
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Autofocus application failed: {e}")
            return None
    
    def _assess_exposure_adequacy(self, metadata: Dict[str, Any]) -> str:
        """Assess if exposure is adequate based on metadata."""
        exposure_time = metadata.get("ExposureTime", 0)
        analogue_gain = metadata.get("AnalogueGain", 1.0)
        
        if exposure_time < 500 and analogue_gain < 2.0:
            return "overexposed"
        elif exposure_time > 50000 or analogue_gain > 12.0:
            return "underexposed"
        else:
            return "adequate"
    
    def _assess_focus_quality(self, metadata: Dict[str, Any]) -> str:
        """Assess focus quality based on metadata."""
        focus_fom = metadata.get("FocusFoM", 0)
        
        if focus_fom > 1000:
            return "excellent"
        elif focus_fom > 700:
            return "good"
        elif focus_fom > 400:
            return "fair"
        else:
            return "poor"

class OptimizedCameraHandler:
    """
    Optimized Camera Handler with unified capture methods and enhanced controls.
    
    Key improvements:
    - Unified capture_frame method handling all sources and stream types
    - Enhanced singleton pattern with proper resource cleanup
    - Advanced autofocus and environmental adaptation
    - Optimized stop/release/reconfigure workflow
    - Comprehensive status and metadata APIs
    """
    
    # Singleton implementation with proper cleanup
    _instance = None
    _instance_lock = threading.RLock()
    _initialized = False
    _cleanup_registered = False
    
    # Global camera access control
    _camera_lock = threading.RLock()
    _frame_buffer_lock = threading.RLock()
    
    # Frame buffer system
    _main_frame_buffer = None
    _lores_frame_buffer = None
    _metadata_buffer = {}
    _capture_thread = None
    _capture_running = False
    _capture_interval = 0.033  # 30 FPS
    
    @classmethod
    def get_instance(cls, *args, **kwargs):
        """
        Get singleton instance with thread-safe double-checked locking.
        
        Returns:
            OptimizedCameraHandler: Singleton instance
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance.__init__(*args, **kwargs)
                    cls._instance = instance
                    
                    # Register cleanup on exit
                    if not cls._cleanup_registered:
                        atexit.register(cls._cleanup_on_exit)
                        cls._cleanup_registered = True
                    
        return cls._instance
    
    @classmethod
    def _cleanup_on_exit(cls):
        """Cleanup camera resources on application exit."""
        if cls._instance:
            try:
                cls._instance._release_all_resources()
                logger.info("Camera resources cleaned up on exit")
            except Exception as e:
                logger.error(f"Error during exit cleanup: {e}")
    
    def __new__(cls, *args, **kwargs):
        """Prevent direct instantiation, use get_instance instead."""
        if cls._instance is None:
            return cls.get_instance(*args, **kwargs)
        return cls._instance
    
    def __init__(self):
        """Initialize optimized camera handler (singleton-protected)."""
        if self._initialized:
            return
            
        self.logger = logger
        
        # Camera state
        self.picam2 = None
        self.initialized = False
        self.streaming = False
        self.recording = False
        
        # Configuration and properties
        self.current_config = {}
        self.camera_properties = {}
        self.sensor_modes = []
        self.camera_status = check_camera_availability()
        
        # Enhancement engine
        self.enhancement_engine = CameraEnhancementEngine(self)
        
        # Frame buffer system
        self._main_frame_buffer = None
        self._lores_frame_buffer = None
        self._metadata_buffer = {}
        self._capture_thread = None
        self._capture_running = False
        
        # Performance tracking
        self.frame_count = 0
        self.average_fps = 0.0
        self._frame_timestamps = []
        self._last_capture_time = time.time()
        self._stats_lock = threading.Lock()
        
        # Connection state
        self.connection_retry_count = 0
        self.max_retry_attempts = 5
        self.retry_delay = 2.0
        
        self.logger.info("OptimizedCameraHandler singleton initialized")
        self.logger.info(f"Camera availability: {self.camera_status}")
        
        self._initialized = True
    
    @contextmanager
    def _camera_operation(self):
        """Context manager for safe camera operations."""
        acquired = False
        try:
            acquired = self._camera_lock.acquire(timeout=5.0)
            if not acquired:
                raise TimeoutError("Could not acquire camera lock")
            yield
        finally:
            if acquired:
                self._camera_lock.release()
    
    def initialize_camera(self) -> bool:
        """
        Initialize camera with enhanced error handling and fallback support.
        
        Returns:
            bool: True if initialization successful
        """
        with self._camera_operation():
            if self.initialized:
                self.logger.info("Camera already initialized (singleton protection)")
                return True
            
            # Clean up any existing resources
            self._cleanup_camera_resources()
            
            self.logger.info("Initializing optimized camera...")
            
            # Check camera availability
            self.camera_status = check_camera_availability()
            if not self.camera_status['camera_ready']:
                self.logger.warning("Camera not ready - initializing in fallback mode")
                self.initialized = True  # Allow fallback mode
                return True
            
            try:
                # Import picamera2 components
                from picamera2 import Picamera2
                
                # Create camera instance
                self.picam2 = Picamera2()
                
                # Get camera properties
                self.camera_properties = self.picam2.camera_properties
                self.sensor_modes = self.picam2.sensor_modes
                
                # Create optimized dual-stream configuration
                main_config = {"size": (1920, 1080)}  # Full HD main stream
                lores_config = {"size": (640, 480)}   # VGA for web interface
                
                config = self.picam2.create_video_configuration(
                    main=main_config,
                    lores=lores_config,
                    encode="lores"  # Encode lores stream for efficiency
                )
                
                # Apply configuration
                self.picam2.configure(config)
                self.current_config = config
                
                # Apply initial camera controls
                self._apply_initial_controls()
                
                self.initialized = True
                self.logger.info("Camera initialized successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Camera initialization failed: {e}")
                self._cleanup_camera_resources()
                return False
    
    def _apply_initial_controls(self):
        """Apply initial camera controls for optimal performance."""
        try:
            if not self.picam2:
                return
                
            # Basic quality controls
            controls = {
                "Brightness": 0.0,
                "Contrast": 1.0,
                "Saturation": 1.0,
                "Sharpness": 1.0
            }
            
            # Try to apply libcamera-specific controls
            try:
                from libcamera import controls as lc_controls
                
                # Auto white balance
                controls["AwbMode"] = lc_controls.AwbModeEnum.Auto
                
                # Auto exposure with constraints
                controls["AeEnable"] = True
                controls["AeConstraintMode"] = lc_controls.AeConstraintModeEnum.Normal
                
                # Autofocus setup
                controls["AfMode"] = lc_controls.AfModeEnum.Continuous
                
            except ImportError:
                self.logger.debug("libcamera controls not available, using basic controls")
            
            self.picam2.set_controls(controls)
            self.logger.debug(f"Applied initial controls: {list(controls.keys())}")
            
        except Exception as e:
            self.logger.warning(f"Failed to apply initial controls: {e}")
    
    def start_camera(self) -> bool:
        """
        Start camera with optimized frame capture system.
        
        Returns:
            bool: True if started successfully
        """
        with self._camera_operation():
            if not self.initialized:
                self.logger.error("Camera not initialized")
                return False
            
            if self.streaming:
                self.logger.info("Camera already streaming")
                return True
            
            if not self.picam2:
                self.logger.error("Camera instance not available")
                return False
            
            try:
                # Start camera
                self.picam2.start()
                
                # Start frame capture thread
                if not self._start_capture_thread():
                    self.picam2.stop()
                    return False
                
                self.streaming = True
                self.logger.info("Camera started successfully with frame capture system")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to start camera: {e}")
                return False
    
    def _start_capture_thread(self) -> bool:
        """Start optimized frame capture thread."""
        if self._capture_thread and self._capture_thread.is_alive():
            return True
            
        try:
            self._capture_running = True
            self._capture_thread = threading.Thread(
                target=self._frame_capture_loop,
                name="OptimizedFrameCapture",
                daemon=True
            )
            self._capture_thread.start()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start capture thread: {e}")
            self._capture_running = False
            return False
    
    def _frame_capture_loop(self):
        """
        Optimized continuous frame capture loop with environmental adaptation.
        """
        self.logger.info("Starting optimized frame capture loop")
        
        enhancement_interval = 2.0  # Apply enhancements every 2 seconds
        last_enhancement = 0
        
        while self._capture_running:
            try:
                if not self.streaming or not self.picam2:
                    time.sleep(0.1)
                    continue
                
                # Capture both streams and metadata in single request
                request = self.picam2.capture_request()
                
                try:
                    # Get frames
                    main_frame = request.make_array("main")
                    lores_frame = request.make_array("lores")
                    metadata = request.get_metadata()
                    
                    # Update buffers atomically
                    with self._frame_buffer_lock:
                        self._main_frame_buffer = main_frame.copy()
                        self._lores_frame_buffer = lores_frame.copy()
                        self._metadata_buffer = make_json_serializable(metadata)
                    
                    # Update statistics
                    self._update_frame_statistics()
                    
                    # Apply environmental enhancements periodically
                    current_time = time.time()
                    if current_time - last_enhancement > enhancement_interval:
                        try:
                            enhancements = self.enhancement_engine.enhance_for_conditions(metadata)
                            if enhancements['applied']:
                                self.logger.debug(f"Applied enhancements: {enhancements['applied']}")
                        except Exception as e:
                            self.logger.debug(f"Enhancement application failed: {e}")
                        
                        last_enhancement = current_time
                    
                finally:
                    request.release()
                
            except Exception as e:
                self.logger.error(f"Frame capture loop error: {e}")
                time.sleep(0.1)
        
        self.logger.info("Optimized frame capture loop stopped")
    
    def _update_frame_statistics(self):
        """Update frame capture statistics."""
        try:
            with self._stats_lock:
                self.frame_count += 1
                current_time = time.time()
                
                # Update FPS calculation
                self._frame_timestamps.append(current_time)
                if len(self._frame_timestamps) > 30:  # Keep last 30 timestamps
                    self._frame_timestamps.pop(0)
                
                if len(self._frame_timestamps) >= 2:
                    time_span = self._frame_timestamps[-1] - self._frame_timestamps[0]
                    if time_span > 0:
                        self.average_fps = (len(self._frame_timestamps) - 1) / time_span
                
                self._last_capture_time = current_time
                
        except Exception as e:
            self.logger.debug(f"Statistics update error: {e}")
    
    def capture_frame(self, 
                     source: CaptureSource = "buffer",
                     stream_type: StreamType = "main", 
                     include_metadata: bool = True,
                     quality_mode: QualityMode = "normal") -> Optional[Union[Dict[str, Any], np.ndarray]]:
        """
        Unified frame capture method supporting multiple sources and stream types.
        
        Args:
            source: Capture source - "buffer" for thread-safe buffered access, 
                   "direct" for immediate camera capture
            stream_type: Stream type - "main", "lores", or "both"
            include_metadata: Whether to include metadata in response
            quality_mode: Quality optimization mode
            
        Returns:
            Union[Dict[str, Any], np.ndarray]: Frame data, format depends on parameters
        """
        try:
            if not self.initialized:
                self.logger.warning("Camera not initialized")
                return None
            
            if source == "buffer":
                return self._capture_from_buffer(stream_type, include_metadata)
            elif source == "direct":
                return self._capture_direct(stream_type, include_metadata, quality_mode)
            else:
                self.logger.error(f"Invalid capture source: {source}")
                return None
                
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return None
    
    def _capture_from_buffer(self, stream_type: StreamType, include_metadata: bool) -> Optional[Union[Dict[str, Any], np.ndarray]]:
        """Capture frame from thread-safe buffer."""
        with self._frame_buffer_lock:
            if stream_type == "main":
                frame = self._main_frame_buffer.copy() if self._main_frame_buffer is not None else None
            elif stream_type == "lores":
                frame = self._lores_frame_buffer.copy() if self._lores_frame_buffer is not None else None
            elif stream_type == "both":
                main_frame = self._main_frame_buffer.copy() if self._main_frame_buffer is not None else None
                lores_frame = self._lores_frame_buffer.copy() if self._lores_frame_buffer is not None else None
                
                if include_metadata:
                    return {
                        'main_frame': main_frame,
                        'lores_frame': lores_frame,
                        'metadata': self._metadata_buffer.copy(),
                        'timestamp': time.time(),
                        'source': 'buffer'
                    }
                else:
                    return {
                        'main_frame': main_frame,
                        'lores_frame': lores_frame
                    }
            else:
                return None
            
            if frame is None:
                return None
            
            if include_metadata:
                return {
                    'frame': frame,
                    'metadata': self._metadata_buffer.copy(),
                    'timestamp': time.time(),
                    'stream_type': stream_type,
                    'source': 'buffer',
                    'format': 'RGB888',
                    'size': frame.shape[:2] if hasattr(frame, 'shape') else None
                }
            else:
                return frame
    
    def _capture_direct(self, stream_type: StreamType, include_metadata: bool, quality_mode: QualityMode) -> Optional[Dict[str, Any]]:
        """Capture frame directly from camera with quality optimization."""
        if not self.streaming or not self.picam2:
            self.logger.warning("Camera not streaming")
            return None
        
        # Apply quality optimization before capture
        if quality_mode != "normal":
            self._apply_quality_mode(quality_mode)
        
        request = None
        try:
            request = self.picam2.capture_request()
            
            if stream_type == "main":
                frame = request.make_array("main")
                result = {
                    'frame': frame,
                    'timestamp': time.time(),
                    'stream_type': 'main',
                    'source': 'direct',
                    'quality_mode': quality_mode,
                    'format': 'RGB888',
                    'size': frame.shape[:2]
                }
            elif stream_type == "lores":
                frame = request.make_array("lores")
                result = {
                    'frame': frame,
                    'timestamp': time.time(),
                    'stream_type': 'lores',
                    'source': 'direct',
                    'quality_mode': quality_mode,
                    'format': 'RGB888',
                    'size': frame.shape[:2]
                }
            elif stream_type == "both":
                main_frame = request.make_array("main")
                lores_frame = request.make_array("lores")
                result = {
                    'main_frame': main_frame,
                    'lores_frame': lores_frame,
                    'timestamp': time.time(),
                    'stream_type': 'both',
                    'source': 'direct',
                    'quality_mode': quality_mode,
                    'main_format': 'RGB888',
                    'lores_format': 'RGB888',
                    'main_size': main_frame.shape[:2],
                    'lores_size': lores_frame.shape[:2]
                }
            else:
                return None
            
            if include_metadata:
                metadata = request.get_metadata()
                result['metadata'] = make_json_serializable(metadata)
                
                # Apply enhancements based on current conditions
                if hasattr(self, 'enhancement_engine'):
                    enhancements = self.enhancement_engine.enhance_for_conditions(metadata)
                    result['enhancements'] = enhancements
            
            return result
            
        finally:
            if request:
                request.release()
    
    def _apply_quality_mode(self, quality_mode: QualityMode):
        """Apply quality-specific camera settings."""
        try:
            if not self.picam2:
                return
                
            controls = {}
            
            if quality_mode == "high_quality":
                controls.update({
                    "NoiseReductionMode": 2,  # High quality
                    "Sharpness": 1.25,
                    "Contrast": 1.1
                })
            elif quality_mode == "low_light":
                controls.update({
                    "NoiseReductionMode": 2,
                    "ExposureTime": min(50000, 100000),
                    "AnalogueGain": min(8.0, 12.0)
                })
            elif quality_mode == "bright":
                controls.update({
                    "NoiseReductionMode": 0,
                    "ExposureTime": max(100, 1000),
                    "AnalogueGain": 1.0,
                    "Sharpness": 1.5
                })
            
            if controls:
                self.picam2.set_controls(controls)
                
        except Exception as e:
            self.logger.warning(f"Quality mode application failed: {e}")
    
    def get_camera_status(self) -> Dict[str, Any]:
        """
        Get comprehensive camera status with enhanced diagnostics.
        
        Returns:
            Dict: Comprehensive camera status
        """
        try:
            status = {
                'initialized': self.initialized,
                'streaming': self.streaming,
                'recording': getattr(self, 'recording', False),
                'camera_ready': self.camera_status.get('camera_ready', False),
                'hardware_available': self.camera_status.get('hardware_available', False),
                'software_available': self.camera_status.get('software_available', False),
                'singleton_active': self.__class__._instance is not None,
                'frame_count': self.frame_count,
                'average_fps': round(self.average_fps, 2),
                'buffer_status': self._get_buffer_status(),
                'enhancement_status': self._get_enhancement_status(),
                'diagnostics': self.camera_status.get('diagnostics', {}),
                'timestamp': datetime.now().isoformat()
            }
            
            # Add configuration if available
            if self.current_config:
                status['current_config'] = self.current_config
            
            # Add camera properties if available
            if self.camera_properties:
                status['camera_properties'] = make_json_serializable(self.camera_properties)
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get camera status: {e}")
            return {
                'initialized': False,
                'streaming': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_buffer_status(self) -> Dict[str, Any]:
        """Get frame buffer status."""
        with self._frame_buffer_lock:
            return {
                'main_frame_available': self._main_frame_buffer is not None,
                'lores_frame_available': self._lores_frame_buffer is not None,
                'metadata_available': bool(self._metadata_buffer),
                'capture_thread_running': self._capture_running,
                'last_capture_time': self._last_capture_time
            }
    
    def _get_enhancement_status(self) -> Dict[str, Any]:
        """Get enhancement engine status."""
        if not hasattr(self, 'enhancement_engine'):
            return {'available': False}
            
        return {
            'available': True,
            'autofocus_enabled': self.enhancement_engine.autofocus_enabled,
            'auto_exposure_enabled': self.enhancement_engine.auto_exposure_enabled,
            'noise_reduction_enabled': self.enhancement_engine.noise_reduction_enabled,
            'last_enhancement_time': self.enhancement_engine.last_enhancement_time
        }
    
    def get_metadata(self, comprehensive: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get camera metadata with optional comprehensive information.
        
        Args:
            comprehensive: Include detailed diagnostic information
            
        Returns:
            Optional[Dict]: Camera metadata
        """
        try:
            if not self.streaming:
                return None
            
            # Get metadata from buffer first (fastest)
            with self._frame_buffer_lock:
                metadata = self._metadata_buffer.copy() if self._metadata_buffer else {}
            
            if not metadata and self.picam2:
                # Fallback to direct capture if buffer empty
                request = self.picam2.capture_request()
                try:
                    metadata = make_json_serializable(request.get_metadata())
                finally:
                    request.release()
            
            if not metadata:
                return None
            
            # Enhance metadata with assessments
            if comprehensive and hasattr(self, 'enhancement_engine'):
                assessments = self.enhancement_engine.enhance_for_conditions(metadata)
                metadata.update({
                    'assessments': assessments,
                    'capture_time': datetime.now().isoformat(),
                    'frame_count': self.frame_count,
                    'average_fps': self.average_fps
                })
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Failed to get metadata: {e}")
            return None
    
    def stop_camera(self) -> bool:
        """
        Stop camera with proper resource cleanup.
        
        Returns:
            bool: True if stopped successfully
        """
        with self._camera_operation():
            if not self.streaming:
                self.logger.info("Camera not streaming")
                return True
            
            try:
                self.logger.info("Stopping camera with resource cleanup...")
                
                # Stop capture thread first
                self._stop_capture_thread()
                
                # Stop recording if active
                if getattr(self, 'recording', False):
                    self._stop_recording_internal()
                
                # Stop camera
                if self.picam2:
                    self.picam2.stop()
                
                self.streaming = False
                
                # Clear buffers
                with self._frame_buffer_lock:
                    self._main_frame_buffer = None
                    self._lores_frame_buffer = None
                    self._metadata_buffer = {}
                
                self.logger.info("Camera stopped successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to stop camera: {e}")
                return False
    
    def _stop_capture_thread(self):
        """Stop frame capture thread gracefully."""
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_running = False
            self._capture_thread.join(timeout=3.0)
            
            if self._capture_thread.is_alive():
                self.logger.warning("Capture thread did not stop gracefully")
            else:
                self.logger.info("Capture thread stopped")
    
    def _release_all_resources(self):
        """Release all camera resources completely."""
        try:
            self.logger.info("Releasing all camera resources...")
            
            # Stop everything
            self.stop_camera()
            
            # Close camera instance
            if self.picam2:
                try:
                    self.picam2.close()
                except:
                    pass
                self.picam2 = None
            
            # Reset state
            self.initialized = False
            self.streaming = False
            
            # Clear buffers
            with self._frame_buffer_lock:
                self._main_frame_buffer = None
                self._lores_frame_buffer = None
                self._metadata_buffer = {}
            
            self.logger.info("All camera resources released")
            
        except Exception as e:
            self.logger.error(f"Error releasing resources: {e}")
    
    def reconfigure_camera_safely(self, new_config: Dict[str, Any]) -> bool:
        """
        Safely reconfigure camera following best practices:
        1. Stop camera and streaming
        2. Release resources
        3. Apply new configuration  
        4. Reinitialize camera
        5. Restart streaming
        
        Args:
            new_config: New camera configuration
            
        Returns:
            bool: True if reconfiguration successful
        """
        with self._camera_operation():
            self.logger.info("Starting safe camera reconfiguration...")
            
            # Remember streaming state
            was_streaming = self.streaming
            
            try:
                # Step 1: Stop camera gracefully
                if not self.stop_camera():
                    self.logger.error("Failed to stop camera for reconfiguration")
                    return False
                
                # Step 2: Release resources
                if self.picam2:
                    try:
                        self.picam2.close()
                    except:
                        pass
                    self.picam2 = None
                
                # Step 3: Apply new configuration
                self.current_config.update(new_config)
                self.initialized = False
                
                # Step 4: Reinitialize with new configuration
                if not self.initialize_camera():
                    self.logger.error("Failed to reinitialize camera after reconfiguration")
                    return False
                
                # Step 5: Restart streaming if it was active
                if was_streaming:
                    if not self.start_camera():
                        self.logger.error("Failed to restart camera after reconfiguration")
                        return False
                
                self.logger.info("Camera reconfiguration completed successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Camera reconfiguration failed: {e}")
                
                # Attempt recovery
                try:
                    self.initialize_camera()
                    if was_streaming:
                        self.start_camera()
                except:
                    pass
                
                return False
    
    def _cleanup_camera_resources(self):
        """Internal method to cleanup existing camera resources."""
        try:
            if self.picam2:
                try:
                    if hasattr(self.picam2, 'started') and self.picam2.started:
                        self.picam2.stop()
                    self.picam2.close()
                except:
                    pass
                self.picam2 = None
                
        except Exception as e:
            self.logger.debug(f"Resource cleanup error: {e}")
    
    def is_frame_buffer_ready(self) -> bool:
        """Check if frame buffer system is ready."""
        with self._frame_buffer_lock:
            return (self._main_frame_buffer is not None and 
                   self._lores_frame_buffer is not None and
                   bool(self._metadata_buffer))

# Factory functions and compatibility layer
def get_optimized_camera_handler():
    """Get the singleton optimized camera handler instance."""
    return OptimizedCameraHandler.get_instance()

def create_camera_handler():
    """Create or get camera handler instance (compatibility)."""
    return get_optimized_camera_handler()

# Export the optimized handler as the main handler
CameraHandler = OptimizedCameraHandler