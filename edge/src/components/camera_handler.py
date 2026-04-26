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
from typing import Dict, Any, Optional, Tuple, Union, Literal, List
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
from collections import deque

from edge.src.core.utils.logging_config import get_logger, get_camera_logger, RateLimitedLogger
from edge.src.core.config import (
    DEFAULT_AUTOFOCUS_ENABLED,
    DEFAULT_AUTOFOCUS_MODE,
    MAIN_RESOLUTION,
    LORES_RESOLUTION,
    DEFAULT_FRAMERATE,
    DEFAULT_SHARPNESS,
    DEFAULT_NOISE_REDUCTION_MODE,
    AUTOFOCUS_TRIGGER_BEFORE_CAPTURE,
    FOCUS_QUALITY_MIN_THRESHOLD,
    DEFAULT_BRIGHTNESS,
    DEFAULT_CONTRAST,
    DEFAULT_SATURATION,
    QUALITY_ENHANCEMENT_ENABLED,
    HIGH_QUALITY_CAPTURE_RESOLUTION,
    FOCUS_HEALTH_ENABLED,
    FOCUS_HEALTH_DURATION,
    FOCUS_HEALTH_MIN_SAMPLES,
    FOCUS_HEALTH_VARIATION_THRESHOLD,
    FOCUS_HEALTH_MIN_FOM,
    FOCUS_HEALTH_RETRY_ATTEMPTS,
)

logger = get_logger(__name__)
opt_logger = get_camera_logger(logger)

# Type definitions
CaptureSource = Literal["direct", "buffer"]
StreamType = Literal["main", "lores", "both"]
QualityMode = Literal["normal", "low_light", "bright", "high_quality"]

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
        # Check if camera device exists
        camera_devices = ['/dev/video0', '/dev/video1', '/dev/video2']
        for device in camera_devices:
            if os.path.exists(device):
                status['hardware_available'] = True
                status['details']['camera_device'] = device
                break
    except Exception as e:
        status['diagnostics']['hardware_check_error'] = str(e)
    
    # Check for Picamera2 availability
    try:
        import picamera2
        status['picamera2_available'] = True
        status['details']['picamera2_version'] = getattr(picamera2, '__version__', 'unknown')
    except ImportError as e:
        status['diagnostics']['picamera2_import_error'] = str(e)
    
    # Check for libcamera availability
    try:
        import libcamera
        status['libcamera_available'] = True
        status['details']['libcamera_version'] = getattr(libcamera, '__version__', 'unknown')
    except ImportError as e:
        status['diagnostics']['libcamera_import_error'] = str(e)
    
    # Overall software availability
    status['software_available'] = status['picamera2_available'] and status['libcamera_available']
    
    # Camera ready if both hardware and software are available
    status['camera_ready'] = status['hardware_available'] and status['software_available']
    
    return status

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
    elif hasattr(obj, '__class__') and 'ColorSpace' in str(type(obj)):
        # Handle ColorSpace objects specifically
        return str(obj)
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
        self.autofocus_enabled = DEFAULT_AUTOFOCUS_ENABLED
        self.auto_exposure_enabled = True
        self.noise_reduction_enabled = True
        
        # Environmental adaptation parameters
        self.low_light_threshold = 50000  # ExposureTime microseconds
        self.bright_light_threshold = 1000  # ExposureTime microseconds
        self.focus_scan_range = (0.0, 10.0)  # Focus range in diopters
        self.focus_good_threshold = 900
        self.focus_poor_threshold = 350
        self.low_light_focus_poor_threshold = 250
        self.good_frames_required = 60
        self.poor_frames_required = 8
        self.focus_check_interval = 90.0  # seconds between re-evaluations
        self.post_focus_cooldown = 10.0  # seconds to wait after triggering AF
        self.focus_distance_range = (1.0, 5.0)  # meters
        self.focus_target_distance_m = 3.0
        self.focus_locked = False
        self.last_focus_lock_time = 0.0
        self.last_focus_action_time = 0.0
        self.good_frame_counter = 0
        self.poor_frame_counter = 0
        self.last_lens_position = None
        self.focus_fom_history = deque(maxlen=30)
        self.focus_fom_history = deque(maxlen=30)
        
        # Performance tracking
        self.last_enhancement_time = 0
        self.enhancement_interval = 1.0  # seconds
        
        # State tracking to prevent unnecessary adjustments
        self.last_lighting_condition = None
        self.last_applied_controls = {}  # Track last applied controls to avoid redundant changes
        self.stable_condition_count = 0  # Count how many times condition has been stable
        self.stable_condition_threshold = 3  # Stop adjusting after 3 stable checks (6 seconds)
        self.enhancement_paused = False  # Pause enhancement when conditions are stable and focus is good
        
    def enhance_for_conditions(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environmental enhancements based on current conditions.
        Only adjusts when conditions change or focus quality is poor.
        Stops adjusting when conditions are stable and focus is good.
        
        Args:
            metadata: Current camera metadata
            
        Returns:
            Dict: Applied enhancements and their results
        """
        enhancements = {
            'applied': [],
            'exposure_assessment': 'unknown',
            'focus_quality': 'unknown',
            'lighting_condition': 'unknown',
            'skipped': False
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
            
            # Assess focus quality
            focus_quality = self._assess_focus_quality(metadata)
            enhancements['focus_quality'] = focus_quality
            enhancements['exposure_assessment'] = self._assess_exposure_adequacy(metadata)
            
            # Check if conditions are stable
            if lighting_condition == self.last_lighting_condition:
                self.stable_condition_count += 1
            else:
                self.stable_condition_count = 0
                self.last_lighting_condition = lighting_condition
                self.enhancement_paused = False  # Reset pause when condition changes
            
            # Skip enhancement if:
            # 1. Conditions are stable (same lighting condition for threshold checks)
            # 2. Focus quality is good (excellent or good)
            # 3. Enhancement is already paused
            if (self.stable_condition_count >= self.stable_condition_threshold and 
                focus_quality in ['excellent', 'good'] and
                self.enhancement_paused):
                enhancements['skipped'] = True
                enhancements['reason'] = 'stable_conditions_good_focus'
                return enhancements
            
            # If conditions are stable and focus is good, pause future enhancements
            if (self.stable_condition_count >= self.stable_condition_threshold and 
                focus_quality in ['excellent', 'good']):
                self.enhancement_paused = True
                enhancements['skipped'] = True
                enhancements['reason'] = 'pausing_enhancement_stable_good'
                return enhancements
            
            # Reset pause if focus quality degrades
            if focus_quality in ['poor', 'fair']:
                self.enhancement_paused = False
            
            # Apply lighting-specific enhancements (only if needed)
            if lighting_condition == "low_light":
                self._enhance_for_low_light(enhancements, metadata)
            elif lighting_condition == "bright_light":
                self._enhance_for_bright_light(enhancements, metadata)
            else:
                self._enhance_for_normal_light(enhancements, metadata)
            
            # Apply autofocus if enabled
            if self.autofocus_enabled:
                focus_result = self._apply_autofocus(focus_fom, metadata)
                if focus_result:
                    enhancements['applied'].append(focus_result)
            
        except Exception as e:
            self.logger.warning(f"Enhancement engine error: {e}")
            enhancements['error'] = str(e)
            
        return enhancements
    
    def _enhance_for_low_light(self, enhancements: Dict[str, Any], metadata: Dict[str, Any]):
        """Apply low-light specific optimizations only if needed."""
        try:
            if not self.camera or not self.camera.picam2:
                return
            
            controls = {}
            needs_update = False
            
            # Check current NoiseReductionMode
            current_nr = self.last_applied_controls.get("NoiseReductionMode")
            if self.noise_reduction_enabled and current_nr != 2:
                controls["NoiseReductionMode"] = 2  # High quality
                needs_update = True
            
            # Don't override ExposureTime/AnalogueGain if Auto Exposure is enabled
            # Let Auto Exposure handle it, but we can set limits if needed
            # Only apply lens shading correction
            current_lsm = self.last_applied_controls.get("LensShadingMapMode")
            if current_lsm != 1:
                controls["LensShadingMapMode"] = 1
                needs_update = True
            
            if needs_update and controls:
                self.camera.picam2.set_controls(controls)
                self.last_applied_controls.update(controls)
                enhancements['applied'].append("low_light_optimization")
                
        except Exception as e:
            self.logger.warning(f"Low light enhancement failed: {e}")
    
    def _enhance_for_bright_light(self, enhancements: Dict[str, Any], metadata: Dict[str, Any]):
        """Apply bright light specific optimizations only if needed."""
        try:
            if not self.camera or not self.camera.picam2:
                return
            
            controls = {}
            needs_update = False
            
            # Check current NoiseReductionMode
            current_nr = self.last_applied_controls.get("NoiseReductionMode")
            if current_nr != DEFAULT_NOISE_REDUCTION_MODE:
                controls["NoiseReductionMode"] = DEFAULT_NOISE_REDUCTION_MODE  # Use config value (0=Off)
                needs_update = True
            
            # Check current Sharpness - don't reduce it if already at good value
            current_sharpness = self.last_applied_controls.get("Sharpness")
            if current_sharpness is None or current_sharpness < DEFAULT_SHARPNESS:
                controls["Sharpness"] = DEFAULT_SHARPNESS  # Use config value (2.0)
                needs_update = True
            
            # Don't override ExposureTime/AnalogueGain - let Auto Exposure handle it
            
            if needs_update and controls:
                self.camera.picam2.set_controls(controls)
                self.last_applied_controls.update(controls)
                enhancements['applied'].append("bright_light_optimization")
                
        except Exception as e:
            self.logger.warning(f"Bright light enhancement failed: {e}")
    
    def _enhance_for_normal_light(self, enhancements: Dict[str, Any], metadata: Dict[str, Any]):
        """Apply normal lighting optimizations only if needed."""
        try:
            if not self.camera or not self.camera.picam2:
                return
            
            controls = {}
            needs_update = False
            
            # Only adjust if values differ from expected defaults
            current_nr = self.last_applied_controls.get("NoiseReductionMode")
            if current_nr != DEFAULT_NOISE_REDUCTION_MODE:
                controls["NoiseReductionMode"] = DEFAULT_NOISE_REDUCTION_MODE
                needs_update = True
            
            current_sharpness = self.last_applied_controls.get("Sharpness")
            if current_sharpness is None or current_sharpness != DEFAULT_SHARPNESS:
                controls["Sharpness"] = DEFAULT_SHARPNESS
                needs_update = True
            
            # Ensure Auto Exposure is enabled (should already be from initial controls)
            # Don't override it unnecessarily
            
            if needs_update and controls:
                self.camera.picam2.set_controls(controls)
                self.last_applied_controls.update(controls)
                enhancements['applied'].append("normal_light_optimization")
                
        except Exception as e:
            self.logger.warning(f"Normal light enhancement failed: {e}")
    
    def _is_autofocus_available(self) -> bool:
        """
        Check if autofocus is available on the camera.
        
        Returns:
            bool: True if autofocus is available, False otherwise
        """
        try:
            if not self.camera or not self.camera.picam2:
                return False
                
            # Check if libcamera controls are available
            from libcamera import controls
            return True
            
        except ImportError:
            return False
        except Exception:
            return False
    
    
    
    def _apply_autofocus(self, current_fom: float, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Manage autofocus with hysteresis, cooldown, and lighting-aware thresholds.
        """
        try:
            if not self.camera or not self.camera.picam2:
                return None
            
            if not self._is_autofocus_available():
                self.logger.debug("Autofocus not available, skipping AF logic")
                return None
            
            current_time = time.time()
            
            # Track history
            self.focus_fom_history.append(current_fom)
            avg_fom = (sum(self.focus_fom_history) / len(self.focus_fom_history)
                       if self.focus_fom_history else current_fom)
            
            # Adjust thresholds in low-light conditions
            exposure_time = metadata.get("ExposureTime", 0)
            analogue_gain = metadata.get("AnalogueGain", 1.0)
            poor_threshold = self.focus_poor_threshold
            if analogue_gain >= 8.0 or exposure_time >= 50000:
                poor_threshold = self.low_light_focus_poor_threshold
            
            if current_fom >= self.focus_good_threshold and avg_fom >= self.focus_good_threshold:
                self.good_frame_counter += 1
                self.poor_frame_counter = 0
            elif current_fom <= poor_threshold and avg_fom <= poor_threshold:
                self.poor_frame_counter += 1
                self.good_frame_counter = 0
            else:
                # Minor fluctuation: slowly decay counters
                self.good_frame_counter = max(0, self.good_frame_counter - 1)
                self.poor_frame_counter = max(0, self.poor_frame_counter - 1)
            
            # Interval-based unlock
            if self.focus_locked and (current_time - self.last_focus_lock_time) >= self.focus_check_interval:
                self.focus_locked = False
                self.good_frame_counter = 0
                self.poor_frame_counter = 0
                return "focus_unlock_interval"
            
            # Handle locked focus degradation
            if self.focus_locked:
                if self.poor_frame_counter >= self.poor_frames_required:
                    self.focus_locked = False
                    return self._trigger_autofocus("locked_degraded")
                return "focus_locked"
            
            # Trigger autofocus if poor quality sustained
            if (self.poor_frame_counter >= self.poor_frames_required and
                    (current_time - self.last_focus_action_time) >= self.post_focus_cooldown):
                return self._trigger_autofocus("poor_quality")
            
            # Lock focus when quality sustained
            if self.good_frame_counter >= self.good_frames_required:
                return self._lock_focus(metadata)
            
            return None
        
        except Exception as e:
            self.logger.warning(f"Autofocus management failed: {e}")
            return None

    def _trigger_autofocus(self, reason: str) -> Optional[str]:
        """Trigger hardware autofocus scan and wait for completion."""
        try:
            if not self.camera or not getattr(self.camera, "picam2", None):
                return None
            
            min_fom = max(self.focus_good_threshold, FOCUS_QUALITY_MIN_THRESHOLD)
            autofocus_success = self.camera._trigger_and_wait_autofocus(
                timeout=3.0,
                min_fom=min_fom
            )
            
            self.last_focus_action_time = time.time()
            if autofocus_success:
                self.focus_locked = True
                self.good_frame_counter = 0
                self.poor_frame_counter = 0
                self.last_focus_lock_time = self.last_focus_action_time
                return f"autofocus_locked_{reason}"
            
            self.focus_locked = False
            return f"autofocus_failed_{reason}"
        except Exception as af_error:
            self.logger.warning(f"AF trigger failed: {af_error}")
            return None

    def _lock_focus(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Lock focus by switching to manual mode with current lens position."""
        try:
            lens_position = None
            if metadata:
                lens_position = metadata.get("LensPosition")
            if lens_position is not None and self.camera and self.camera.picam2:
                controls = {
                    "AfMode": 0,
                    "LensPosition": float(lens_position),
                    "AfMetering": 1,
                    "AfRange": 0
                }
                self.camera.picam2.set_controls(controls)
                self.last_lens_position = float(lens_position)
            else:
                self._set_manual_focus(self.focus_target_distance_m)
            self.focus_locked = True
            self.good_frame_counter = 0
            self.poor_frame_counter = 0
            self.last_focus_lock_time = time.time()
            self.last_focus_action_time = self.last_focus_lock_time
            return "focus_locked"
        except Exception as lock_error:
            self.logger.warning(f"Failed to lock focus: {lock_error}")
            return None

    def _distance_to_lens_position(self, distance_m: float) -> float:
        """Convert desired distance in meters to approximate lens position (diopters)."""
        distance_m = max(min(distance_m, self.focus_distance_range[1]), self.focus_distance_range[0])
        if distance_m <= 0:
            return self.focus_scan_range[1]
        diopters = 1.0 / distance_m
        return float(min(max(diopters, self.focus_scan_range[0]), self.focus_scan_range[1]))

    def _set_manual_focus(self, distance_m: Optional[float] = None):
        """Set lens position to target distance with manual focus centered in frame."""
        target_distance = distance_m or self.focus_target_distance_m
        lens_position = self._distance_to_lens_position(target_distance)
        controls = {
            "AfMode": 0,
            "LensPosition": lens_position,
            "AfMetering": 1,
            "AfRange": 0
        }
        self.camera.picam2.set_controls(controls)
        self.last_lens_position = lens_position
    
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

class CameraHandler:
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
    _capture_interval = 1.0 / DEFAULT_FRAMERATE  # Calculated from DEFAULT_FRAMERATE (15 FPS default)

    def _get_af_mode_name(self, mode: int) -> str:
        """Convert numeric AF mode to descriptive name."""
        af_modes = {0: "Manual", 1: "Auto", 2: "Continuous"}
        return af_modes.get(mode, f"Unknown({mode})")
    
    @classmethod
    def get_instance(cls, *args, **kwargs):
        """
        Get singleton instance with thread-safe double-checked locking.
        
        Returns:
            CameraHandler: Singleton instance
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
        self.opt_logger = opt_logger
        self.rate_limited = RateLimitedLogger(logger, default_interval=5.0)
        
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
        
        # Focus health tracking
        self.last_focus_health = None
        self.focus_health_enabled = FOCUS_HEALTH_ENABLED
        
        self.logger.info("CameraHandler singleton initialized")
        # self.logger.info(f"Camera availability: {self.camera_status}")  # INFO: ปิดรายละเอียด เพื่อลดขนาด log
        
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
            
            self.logger.info("Initializing camera...")
            
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
                
                # Create optimized dual-stream configuration with hardware MJPEG encoding
                main_size = (HIGH_QUALITY_CAPTURE_RESOLUTION
                             if QUALITY_ENHANCEMENT_ENABLED
                             else MAIN_RESOLUTION)
                main_config = {"size": main_size, "format": "RGB888"}  # Main stream with RGB color for detection
                lores_config = {"size": LORES_RESOLUTION, "format": "RGB888"}   # Lores stream with RGB color for proper display
                self.logger.info(
                    f"Main stream resolution set to {main_size} "
                    f"(quality_enhancement={'on' if QUALITY_ENHANCEMENT_ENABLED else 'off'})"
                )
                
                # Import MJPEG encoder
                from picamera2.encoders import MJPEGEncoder
                
                config = self.picam2.create_video_configuration(
                    main=main_config,
                    lores=lores_config
                )
                
                # Set framerate using FrameDurationLimits (in microseconds)
                # For 15 FPS: 1000000 / 15 = 66666 microseconds per frame
                # For 30 FPS: 1000000 / 30 = 33333 microseconds per frame
                frame_duration_us = int(1000000 / DEFAULT_FRAMERATE)
                if "controls" not in config:
                    config["controls"] = {}
                config["controls"]["FrameDurationLimits"] = (frame_duration_us, frame_duration_us)
                self.logger.info(f"Camera framerate set to {DEFAULT_FRAMERATE} FPS (FrameDurationLimits: {frame_duration_us}μs)")
                
                # Create hardware encoders for lores stream (if available)
                from picamera2.outputs import CircularOutput
                from picamera2.encoders import H264Encoder
                
                try:
                    # Try H.264 encoder first (more efficient)
                    #if H264Encoder._hw_encoder_available:
                    #    self.h264_encoder = H264Encoder(bitrate=1000000, quality=85)  # 1Mbps, quality 85
                    #    self.h264_output = CircularOutput(size=10)
                    #    self.h264_encoder.output = self.h264_output
                    #    self.logger.info("Hardware H.264 encoder initialized successfully")
                    #    self.primary_encoder = "h264"
                    if MJPEGEncoder._hw_encoder_available:
                        self.mjpeg_encoder = MJPEGEncoder(bitrate=2000000, quality=85)  # 2Mbps, quality 85
                        self.mjpeg_output = CircularOutput(size=10)
                        self.mjpeg_encoder.output = self.mjpeg_output
                        self.logger.info("Hardware MJPEG encoder initialized successfully")
                        self.primary_encoder = "mjpeg"
                    else:
                        self.logger.warning("No hardware encoders available, will use software encoding")
                        self.h264_encoder = None
                        self.mjpeg_encoder = None
                        self.primary_encoder = "software"
                except Exception as e:
                    self.logger.warning(f"Failed to initialize hardware encoders: {e}")
                    self.h264_encoder = None
                    self.mjpeg_encoder = None
                    self.primary_encoder = "software"
                
                # Apply configuration
                self.picam2.configure(config)
                self.current_config = config
                
                # Apply initial camera controls
                self._apply_initial_controls()
                
                # Initialize enhancement engine state tracking
                if hasattr(self, 'enhancement_engine'):
                    # Store initial controls as last applied
                    initial_controls = {
                        "Sharpness": DEFAULT_SHARPNESS,
                        "NoiseReductionMode": DEFAULT_NOISE_REDUCTION_MODE,
                        "AfMode": DEFAULT_AUTOFOCUS_MODE,
                    }
                    self.enhancement_engine.last_applied_controls = initial_controls.copy()
                
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
                
            # Basic quality controls with enhanced color settings (Optimized for sharp images, matching rpicam behavior)
            controls = {
                "Brightness": DEFAULT_BRIGHTNESS,
                "Contrast": DEFAULT_CONTRAST,
                "Saturation": DEFAULT_SATURATION,
                "Sharpness": DEFAULT_SHARPNESS,  # Increased to 2.0 for better sharpness (matching rpicam)
                "NoiseReductionMode": DEFAULT_NOISE_REDUCTION_MODE,  # 0=Off for maximum sharpness
                "AwbMode": 0,       # Auto white balance
                "AeEnable": True,   # Auto exposure enabled
                "AwbEnable": True,  # Auto white balance enabled
                "AfMode": DEFAULT_AUTOFOCUS_MODE,  # 1=Auto mode (changed from 2=Continuous for better focus stability)
                "AfTrigger": 0,     # Will be triggered when needed
                "AfRange": 0,       # Full range (0=Full, 1=Macro, 2=Normal)
                "AfSpeed": 0,       # Normal speed (0=Normal, 1=Fast)
                "AfMetering": 1,    # Center-weighted metering
            }
            
            # Try to apply libcamera-specific controls
            try:
                from libcamera import controls as lc_controls
                
                # Auto white balance
                controls["AwbMode"] = lc_controls.AwbModeEnum.Auto
                
                # Auto exposure with constraints
                controls["AeEnable"] = True
                controls["AeConstraintMode"] = lc_controls.AeConstraintModeEnum.Normal
                
                # Autofocus setup - use numeric mode for proper AF trigger support (if enabled)
                if DEFAULT_AUTOFOCUS_ENABLED:
                    controls["AfMode"] = DEFAULT_AUTOFOCUS_MODE  # 0=Manual, 1=Auto, 2=Continuous
                    # Note: AfMode is already set above, this ensures it's correct
                
            except ImportError:
                self.logger.debug("libcamera controls not available, using basic controls")
            
            self.picam2.set_controls(controls)
            
            # Log AF mode if autofocus is enabled
            if DEFAULT_AUTOFOCUS_ENABLED and "AfMode" in controls:
                af_mode_name = self._get_af_mode_name(controls["AfMode"])
                self.logger.info(f"Autofocus enabled with mode: {af_mode_name} ({controls['AfMode']})")
            
            # Apply IMX708 auto-focus defaults (mirrors focus test harness)
            self.apply_auto_focus_defaults()
            
        except Exception as e:
            self.logger.warning(f"Failed to apply initial controls: {e}")
    
    def apply_auto_focus_defaults(self) -> bool:
        """
        Apply the same IMX708 auto-focus configuration used by the focus test harness.
        Ensures AfMode=Auto, full-range scan, and consistent image processing controls.
        """
        if not self.picam2:
            return False
        
        controls = {
            "AeEnable": True,
            "AwbEnable": True,
            "AfMode": 1,      # Auto
            "AfRange": 0,     # Full range
            "AfSpeed": 0,     # Normal speed
            "AfMetering": 1,  # Center-weighted
            "Brightness": 0.0,
            "Contrast": 1.0,
            "Saturation": 1.0,
            "Sharpness": 1.0,
        }
        
        try:
            self.picam2.set_controls(controls)
            time.sleep(0.1)
            try:
                self.picam2.set_controls({"AfTrigger": 0})
            except Exception as trigger_error:
                self.logger.debug(f"Auto focus trigger skipped: {trigger_error}")
            self.logger.info("Auto focus defaults applied (AfMode=Auto, AfRange=Full, AfSpeed=Normal)")
            return True
        except Exception as focus_error:
            self.logger.warning(f"Failed to apply auto focus defaults: {focus_error}")
            return False
    
    def _trigger_and_wait_autofocus(self, timeout: float = 2.0, min_fom: int = None) -> bool:
        """
        Trigger autofocus and wait until focus is achieved.
        
        This method is useful for ensuring sharp images before important captures,
        similar to how rpicam-still waits for focus completion.
        
        Args:
            timeout: Maximum time to wait for focus (seconds)
            min_fom: Minimum FocusFoM to consider as focused (defaults to FOCUS_QUALITY_MIN_THRESHOLD)
            
        Returns:
            bool: True if focus achieved, False if timeout or error
        """
        try:
            if not self.picam2 or not DEFAULT_AUTOFOCUS_ENABLED:
                return False
            
            if min_fom is None:
                min_fom = FOCUS_QUALITY_MIN_THRESHOLD
            
            # Switch to Auto mode if not already
            self.picam2.set_controls({"AfMode": 1})  # 1=Auto mode
            time.sleep(0.1)
            
            # Trigger autofocus
            self.picam2.set_controls({"AfTrigger": 0})  # 0=Start trigger
            
            # Wait for focus to complete
            start_time = time.time()
            focus_achieved = False
            
            while time.time() - start_time < timeout:
                request = self.picam2.capture_request()
                try:
                    metadata = request.get_metadata()
                    focus_fom = metadata.get("FocusFoM", 0)
                    
                    if focus_fom >= min_fom:
                        self.logger.debug(f"Autofocus achieved: FocusFoM={focus_fom} (threshold: {min_fom})")
                        focus_achieved = True
                        break
                finally:
                    request.release()
                
                time.sleep(0.1)
            
            if not focus_achieved:
                self.logger.warning(f"Autofocus timeout after {timeout}s (may still be acceptable)")
            
            return focus_achieved
            
        except Exception as e:
            self.logger.warning(f"Autofocus trigger failed: {e}")
            return False
    
    def _collect_focus_health_metrics(
        self,
        duration: float = None,
        min_samples: int = None
    ) -> Dict[str, Any]:
        """Collect short-term FocusFoM statistics for health verification."""
        duration = duration or FOCUS_HEALTH_DURATION
        min_samples = min_samples or FOCUS_HEALTH_MIN_SAMPLES
        
        samples: List[float] = []
        lens_positions: List[float] = []
        end_time = time.time() + duration
        
        while time.time() < end_time and len(samples) < min_samples:
            frame = self.capture_frame(
                source="buffer",
                stream_type="main",
                include_metadata=True
            )
            if not frame or not isinstance(frame, dict):
                time.sleep(0.02)
                continue
            
            metadata = frame.get('metadata', {})
            focus_fom = metadata.get("FocusFoM")
            if focus_fom:
                samples.append(float(focus_fom))
            lens_position = metadata.get("LensPosition")
            if lens_position is not None:
                lens_positions.append(float(lens_position))
            
            time.sleep(0.02)
        
        variation = (max(samples) - min(samples)) if len(samples) >= 2 else 0.0
        metrics = {
            'samples': len(samples),
            'fom_min': min(samples) if samples else 0.0,
            'fom_max': max(samples) if samples else 0.0,
            'variation': variation,
            'lens_min': min(lens_positions) if lens_positions else None,
            'lens_max': max(lens_positions) if lens_positions else None,
            'timestamp': datetime.now().isoformat()
        }
        return metrics
    
    def _is_focus_health_good(self, metrics: Dict[str, Any]) -> bool:
        if not metrics or metrics.get('samples', 0) < FOCUS_HEALTH_MIN_SAMPLES:
            return False
        if metrics.get('variation', 0.0) < FOCUS_HEALTH_VARIATION_THRESHOLD:
            return False
        if metrics.get('fom_max', 0.0) < FOCUS_HEALTH_MIN_FOM:
            return False
        return True
    
    def _verify_focus_health(self) -> bool:
        """Ensure camera focus behaves like the validated auto-focus profile."""
        if not self.focus_health_enabled:
            return True
        
        attempts = max(1, FOCUS_HEALTH_RETRY_ATTEMPTS)
        last_metrics = None
        
        for attempt in range(attempts):
            metrics = self._collect_focus_health_metrics()
            last_metrics = metrics
            
            if self._is_focus_health_good(metrics):
                self.last_focus_health = metrics
                self.logger.info(
                    "Focus health verified ✅ (samples=%s, FoM %.0f-%.0f, variation=%.1f, lens=%s-%s)",
                    metrics.get('samples'),
                    metrics.get('fom_min', 0.0),
                    metrics.get('fom_max', 0.0),
                    metrics.get('variation', 0.0),
                    metrics.get('lens_min'),
                    metrics.get('lens_max')
                )
                return True
            
            self.logger.warning(
                "Focus health check failed (attempt %s/%s). FoM range %.0f-%.0f, variation=%.1f. Re-triggering autofocus...",
                attempt + 1,
                attempts,
                metrics.get('fom_min', 0.0),
                metrics.get('fom_max', 0.0),
                metrics.get('variation', 0.0)
            )
            self._trigger_and_wait_autofocus(
                timeout=3.0,
                min_fom=max(FOCUS_HEALTH_MIN_FOM, FOCUS_QUALITY_MIN_THRESHOLD)
            )
            time.sleep(0.2)
        
        self.last_focus_health = last_metrics
        self.logger.error(
            "Focus health verification failed after %s attempts. FoM range %.0f-%.0f, variation=%.1f",
            attempts,
            (last_metrics or {}).get('fom_min', 0.0),
            (last_metrics or {}).get('fom_max', 0.0),
            (last_metrics or {}).get('variation', 0.0)
        )
        return False
    
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
                
                # Start hardware encoder for lores stream
                if hasattr(self, 'h264_encoder') and self.h264_encoder:
                    self.picam2.start_encoder(self.h264_encoder, "lores")
                    self.logger.info("H.264 encoder started")
                elif hasattr(self, 'mjpeg_encoder') and self.mjpeg_encoder:
                    self.picam2.start_encoder(self.mjpeg_encoder, "lores")
                    self.logger.info("MJPEG encoder started")
                
                # Start frame capture thread
                if not self._start_capture_thread():
                    self.picam2.stop()
                    return False
                
                self.streaming = True
                
                # Verify focus quality matches validated profile
                self._verify_focus_health()
                
                self.logger.info("Camera started")
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
        self.opt_logger.log_operation_start("frame_capture_loop")
        
        enhancement_interval = 2.0  # Apply enhancements every 2 seconds initially
        stable_enhancement_interval = 30.0  # When stable, check every 30 seconds
        current_enhancement_interval = enhancement_interval
        last_enhancement = 0
        metadata_copy_interval = max(0.01, 1.0 / max(DEFAULT_FRAMERATE, 1))
        last_metadata_update = 0.0
        last_stats_log = time.time()
        
        while self._capture_running:
            try:
                if not self.streaming or not self.picam2:
                    time.sleep(0.1)
                    continue
                
                # Capture both streams and metadata in single request
                request = self.picam2.capture_request()
                
                try:
                    # Get frames - main is RGB888 for detection, lores from hardware encoder
                    main_frame = request.make_array("main")
                    
                    # Try to get hardware-encoded frame (H.264 or MJPEG)
                    lores_frame = None
                    if hasattr(self, 'h264_output') and not self.h264_output.empty():
                        try:
                            lores_frame = self.h264_output.get_frame()
                        except Exception as e:
                            self.logger.debug(f"H.264 encoder frame not ready: {e}")
                            lores_frame = request.make_array("lores")
                    elif hasattr(self, 'mjpeg_output') and not self.mjpeg_output.empty():
                        try:
                            lores_frame = self.mjpeg_output.get_frame()
                        except Exception as e:
                            self.logger.debug(f"MJPEG encoder frame not ready: {e}")
                            lores_frame = request.make_array("lores")
                    else:
                        # Fallback to array if no hardware encoder
                        lores_frame = request.make_array("lores")
                    
                    metadata = request.get_metadata()
                    
                    # Update buffers atomically
                    with self._frame_buffer_lock:
                        self._main_frame_buffer = main_frame  # No copy needed for detection # if want to copy the frame to the buffer use main_frame.copy()
                        self._lores_frame_buffer = lores_frame  # Store RGB888 array
                        current_time = time.time()
                        if current_time - last_metadata_update >= metadata_copy_interval:
                            self._metadata_buffer = make_json_serializable(metadata)
                            last_metadata_update = current_time
                    
                    # Update statistics
                    self._update_frame_statistics()
                    
                    # Apply environmental enhancements periodically
                    current_time = time.time()
                    if current_time - last_enhancement > current_enhancement_interval:
                        try:
                            enhancements = self.enhancement_engine.enhance_for_conditions(metadata)
                            
                            # Adjust interval based on stability
                            if enhancements.get('skipped'):
                                # Conditions are stable and focus is good - use longer interval
                                current_enhancement_interval = stable_enhancement_interval
                            else:
                                # Conditions changed or focus needs adjustment - use shorter interval
                                current_enhancement_interval = enhancement_interval
                            
                            if enhancements.get('applied'):
                                # Only log if enhancement actually changed
                                enhancement_key = str(enhancements['applied'])
                                if not hasattr(self, 'last_logged_states'):
                                    self.last_logged_states = {'last_enhancement': None}
                                if self.last_logged_states.get('last_enhancement') != enhancement_key:
                                    self.rate_limited.debug_rate_limited(
                                        "enhancement_applied",
                                        f"Applied enhancements: {enhancements['applied']}",
                                        interval=10.0
                                    )
                                    self.last_logged_states['last_enhancement'] = enhancement_key
                            elif enhancements.get('skipped'):
                                # Log when skipping (but rate limited)
                                self.rate_limited.debug_rate_limited(
                                    "enhancement_skipped",
                                    f"Skipped enhancement: {enhancements.get('reason', 'unknown')}",
                                    interval=60.0
                                )
                        except Exception as e:
                            self.rate_limited.debug_rate_limited(
                                "enhancement_error",
                                f"Enhancement application failed: {e}",
                                interval=30.0
                            )
                        
                        last_enhancement = current_time
                    
                    # Log periodic statistics
                    if current_time - last_stats_log > 30:  # Every 30 seconds
                        self._log_periodic_stats()
                        last_stats_log = current_time
                    
                finally:
                    request.release()
                
            except Exception as e:
                self.rate_limited.warning_rate_limited(
                    "capture_loop_error",
                    f"Frame capture loop error: {e}",
                    interval=10.0
                )
                time.sleep(0.1)
        
        self.opt_logger.log_operation_success("frame_capture_loop", "stopped")
    
    def _log_periodic_stats(self):
        """Log periodic statistics with rate limiting."""
        try:
            current_time = time.time()
            uptime = current_time - self.stats_start_time
            
            # Calculate FPS
            fps = self.frame_count / uptime if uptime > 0 else 0
            
            stats = {
                'frames': self.frame_count,
                'fps': round(fps, 2),
                'uptime': round(uptime, 1),
                'errors': self.error_count
            }
            
            self.opt_logger.log_iteration_stats(stats)
            
        except Exception as e:
            self.rate_limited.debug_rate_limited(
                "stats_logging_error",
                f"Error logging periodic stats: {e}",
                interval=60.0
            )
    
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
                     quality_mode: QualityMode = "normal",
                     trigger_autofocus: bool = False) -> Optional[Union[Dict[str, Any], np.ndarray]]:
        """
        Unified frame capture method supporting multiple sources and stream types.
        
        Args:
            source: Capture source - "buffer" for thread-safe buffered access, 
                   "direct" for immediate camera capture
            stream_type: Stream type - "main", "lores", or "both"
            include_metadata: Whether to include metadata in response
            quality_mode: Quality optimization mode
            trigger_autofocus: If True, trigger autofocus and wait before capture (for better focus quality)
            
        Returns:
            Union[Dict[str, Any], np.ndarray]: Frame data, format depends on parameters
        """
        try:
            if not self.initialized:
                self.logger.warning("Camera not initialized")
                return None
            
            # Trigger autofocus if requested (useful for important captures like detection)
            if trigger_autofocus or AUTOFOCUS_TRIGGER_BEFORE_CAPTURE:
                self._trigger_and_wait_autofocus()
            
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
    
    def _capture_from_buffer(self, stream_type: StreamType, include_metadata: bool) -> Optional[Union[Dict[str, Any], np.ndarray, bytes]]:
        """Capture frame from thread-safe buffer."""
        with self._frame_buffer_lock:
            if stream_type == "main":
                frame = self._main_frame_buffer.copy() if self._main_frame_buffer is not None else None
            elif stream_type == "lores":
                frame = self._lores_frame_buffer  # RGB888 array, no copy needed
            elif stream_type == "both":
                main_frame = self._main_frame_buffer.copy() if self._main_frame_buffer is not None else None
                lores_frame = self._lores_frame_buffer  # RGB888 array, no copy needed
                
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
                if stream_type == "lores":
                    return {
                        'frame': frame,  # RGB888 array
                        'metadata': self._metadata_buffer.copy(),
                        'timestamp': time.time(),
                        'stream_type': stream_type,
                        'source': 'buffer',
                        'format': 'RGB888',
                        'size': LORES_RESOLUTION  # Use config resolution
                    }
                else:
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
                status['current_config'] = make_json_serializable(self.current_config)
            
            # Add camera properties if available
            if self.camera_properties:
                status['camera_properties'] = make_json_serializable(self.camera_properties)
            
            if self.last_focus_health:
                status['focus_health'] = self.last_focus_health
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get camera status: {e}")
            return {
                'initialized': False,
                'streaming': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_configuration(self) -> Dict[str, Any]:
        """
        Get current camera configuration.
        
        Returns:
            Dict: Current camera configuration
        """
        try:
            if self.current_config:
                return make_json_serializable(self.current_config)
            else:
                return {
                    'status': 'not_configured',
                    'message': 'Camera not yet configured',
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            self.logger.error(f"Error getting configuration: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def get_focus_health_status(self) -> Optional[Dict[str, Any]]:
        """Return the most recent focus health verification result."""
        return self.last_focus_health
    
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
                
                # Stop hardware encoder first
                if hasattr(self, 'h264_encoder') and self.h264_encoder:
                    try:
                        self.picam2.stop_encoder(self.h264_encoder)
                        self.logger.info("Hardware H.264 encoder stopped")
                    except Exception as e:
                        self.logger.warning(f"Error stopping H.264 encoder: {e}")
                elif hasattr(self, 'mjpeg_encoder') and self.mjpeg_encoder:
                    try:
                        self.picam2.stop_encoder(self.mjpeg_encoder)
                        self.logger.info("Hardware MJPEG encoder stopped")
                    except Exception as e:
                        self.logger.warning(f"Error stopping MJPEG encoder: {e}")
                
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
    
    def close_camera(self) -> bool:
        """
        Close camera and release all resources with enhanced cleanup.
        
        Returns:
            bool: True if closed successfully, False otherwise
        """
        try:
            self.logger.info("Closing camera and releasing resources...")
            
            # Stop capture thread first
            self._stop_capture_thread()
            
            # Stop camera streaming
            if self.picam2 and hasattr(self.picam2, 'started') and self.picam2.started:
                self.logger.info("Stopping camera streaming...")
                self.picam2.stop()
                self.streaming = False
            
            # Release all resources
            self._release_all_resources()
            
            # Reset state
            self.initialized = False
            self.streaming = False
            self.current_config = {}
            self.camera_properties = {}
            self.sensor_modes = []
            
            # Clear frame buffers
            with self._frame_buffer_lock:
                self._main_frame_buffer = None
                self._lores_frame_buffer = None
                self._metadata_buffer = {}
                self._frame_buffer_ready = False
            
            self.logger.info("Camera closed and resources released successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing camera: {e}")
            return False
    
    def try_connect_camera(self) -> bool:
        """
        Try to connect to camera if it becomes available.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if hasattr(self, 'connection_retry_count') and hasattr(self, 'max_retry_attempts'):
            if self.connection_retry_count >= self.max_retry_attempts:
                self.logger.warning(f"Max retry attempts ({self.max_retry_attempts}) reached")
                return False
            
            self.connection_retry_count += 1
            self.logger.info(f"Attempting camera connection (attempt {self.connection_retry_count}/{self.max_retry_attempts})")
        
        # Check if camera is now available
        camera_status = check_camera_availability()
        
        if camera_status['camera_ready']:
            self.logger.info("Camera is now available - attempting to initialize")
            return self.initialize_camera()
        else:
            self.logger.info("Camera not ready yet - will retry later")
            return False

# Factory functions and compatibility layer
def get_camera_handler():
    """Get the singleton camera handler instance."""
    return CameraHandler.get_instance()

def create_camera_handler():
    """Create or get camera handler instance (compatibility)."""
    return get_camera_handler()

# Export the camera handler
# CameraHandler is now the main class