#!/usr/bin/env python3
"""
Improved Camera Manager for v2 Application

This module provides a robust singleton camera manager that:
1. Prevents multiple camera initialization
2. Provides thread-safe access to camera resources
3. Enables persistent streaming and detection operation
4. Integrates with existing v2 codebase architecture
"""

import threading
import queue
import time
import logging
import cv2
from datetime import datetime
from pathlib import Path
import json

from picamera2 import Picamera2
from libcamera import controls

from config import (
    DEFAULT_RESOLUTION, DEFAULT_FRAMERATE, DEFAULT_BRIGHTNESS, 
    DEFAULT_CONTRAST, DEFAULT_SATURATION, DEFAULT_SHARPNESS, 
    DEFAULT_AWB_MODE, BASE_DIR
)

logger = logging.getLogger(__name__)

class CameraState:
    """Manages camera state persistence"""
    
    def __init__(self, state_file="camera_state.json"):
        self.state_file = Path(BASE_DIR) / state_file
        self.state = {
            "initialized": False,
            "streaming": False,
            "initialization_count": 0,
            "last_settings": {
                "resolution": DEFAULT_RESOLUTION,
                "framerate": DEFAULT_FRAMERATE,
                "brightness": DEFAULT_BRIGHTNESS,
                "contrast": DEFAULT_CONTRAST,
                "saturation": DEFAULT_SATURATION,
                "sharpness": DEFAULT_SHARPNESS,
                "awb_mode": DEFAULT_AWB_MODE
            },
            "last_initialization": None,
            "last_error": None
        }
        self.lock = threading.Lock()
        self.load_state()
    
    def load_state(self):
        """Load camera state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    saved_state = json.load(f)
                    self.state.update(saved_state)
                logger.info(f"Loaded camera state from {self.state_file}")
        except Exception as e:
            logger.warning(f"Could not load camera state: {e}, using defaults")
    
    def save_state(self):
        """Save camera state to file"""
        try:
            with self.lock:
                with open(self.state_file, 'w') as f:
                    json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save camera state: {e}")
    
    def update_state(self, **kwargs):
        """Update state and save"""
        with self.lock:
            self.state.update(kwargs)
            self.save_state()
    
    def get_state(self, key=None):
        """Get state value or entire state"""
        with self.lock:
            return self.state.get(key) if key else self.state.copy()

class ImprovedCameraManager:
    """
    Improved Camera Manager with singleton pattern and robust initialization control
    
    Key Features:
    - Singleton pattern prevents multiple instances
    - Thread-safe camera operations
    - Persistent state management
    - Integration with existing queue-based architecture
    - Non-disruptive health checking
    """
    
    _instance = None
    _instance_lock = threading.Lock()
    
    def __new__(cls, frames_queue=None, metadata_queue=None):
        """Ensure singleton pattern"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, frames_queue=None, metadata_queue=None):
        """Initialize camera manager (only once due to singleton)"""
        if self._initialized:
            # Already initialized, just update queues if provided
            if frames_queue is not None:
                self.frames_queue = frames_queue
            if metadata_queue is not None:
                self.metadata_queue = metadata_queue
            return
        
        # First-time initialization
        self.picam2 = None
        self.camera_lock = threading.RLock()  # Re-entrant lock for nested operations
        self.is_initialized = False
        self.streaming_active = False
        self.stream_thread = None
        
        # State management
        self.camera_state = CameraState()
        self.current_settings = {}
        
        # Queue management
        self.frames_queue = frames_queue or queue.Queue(maxsize=10)
        self.metadata_queue = metadata_queue or queue.Queue(maxsize=1)
        
        # Statistics and monitoring
        self.frame_count = 0
        self.error_count = 0
        self.last_frame_time = None
        
        self._initialized = True
        logger.info("ImprovedCameraManager singleton instance created")
    
    def initialize_camera_once(self, **camera_settings):
        """
        Initialize camera only if not already initialized
        Thread-safe with comprehensive error handling
        """
        with self.camera_lock:
            init_count = self.camera_state.get_state('initialization_count') + 1
            self.camera_state.update_state(initialization_count=init_count)
            
            logger.info(f"Camera initialization attempt #{init_count}")
            
            # Check if already initialized
            if self.is_initialized and self.picam2:
                logger.info("Camera already initialized and working, skipping re-initialization")
                return True
            
            try:
                # Clean up any existing instance
                self._cleanup_camera_internal()
                
                # Create new camera instance
                logger.info("Creating new Picamera2 instance...")
                self.picam2 = Picamera2()
                
                # Configure camera
                resolution = camera_settings.get('resolution', DEFAULT_RESOLUTION)
                framerate = camera_settings.get('framerate', DEFAULT_FRAMERATE)
                
                main_config = {"size": resolution}
                lores_config = {"size": (640, 480)}  # For efficient processing
                
                config = self.picam2.create_video_configuration(
                    main=main_config,
                    lores=lores_config,
                    encode="lores"
                )
                
                self.picam2.configure(config)
                logger.info(f"Camera configured with resolution: {resolution}")
                
                # Apply camera controls
                self._apply_camera_controls(**camera_settings)
                
                # Start camera
                self.picam2.start()
                
                # Verify camera is working
                if not self._verify_camera_working():
                    raise Exception("Camera failed verification test")
                
                # Update state
                self.is_initialized = True
                self.current_settings = camera_settings.copy()
                self.camera_state.update_state(
                    initialized=True,
                    last_settings=camera_settings,
                    last_initialization=datetime.now().isoformat(),
                    last_error=None
                )
                
                logger.info(f"Camera successfully initialized with settings: {camera_settings}")
                return True
                
            except Exception as e:
                error_msg = f"Failed to initialize camera: {e}"
                logger.error(error_msg)
                
                self.is_initialized = False
                self.picam2 = None
                self.error_count += 1
                
                self.camera_state.update_state(
                    initialized=False,
                    last_error=error_msg
                )
                
                return False
    
    def _verify_camera_working(self):
        """Verify camera is actually working by capturing a test frame"""
        try:
            if not self.picam2:
                return False
                
            # Try to capture a single frame
            test_request = self.picam2.capture_request()
            test_frame = test_request.make_array('main')
            test_request.release()
            
            if test_frame is None or test_frame.size == 0:
                return False
                
            logger.debug(f"Camera verification successful - captured frame shape: {test_frame.shape}")
            return True
            
        except Exception as e:
            logger.error(f"Camera verification failed: {e}")
            return False
    
    def _apply_camera_controls(self, **settings):
        """Apply camera control settings safely"""
        if not self.picam2:
            logger.warning("Cannot apply camera controls - camera not initialized")
            return
        
        try:
            controls_to_set = {}
            
            # Basic controls
            if 'brightness' in settings:
                controls_to_set["Brightness"] = float(settings['brightness'])
            if 'contrast' in settings:
                controls_to_set["Contrast"] = float(settings['contrast'])
            if 'saturation' in settings:
                controls_to_set["Saturation"] = float(settings['saturation'])
            if 'sharpness' in settings:
                controls_to_set["Sharpness"] = float(settings['sharpness'])
            
            if controls_to_set:
                self.picam2.set_controls(controls_to_set)
                logger.debug(f"Applied camera controls: {controls_to_set}")
            
            # AWB mode
            awb_mode = settings.get('awb_mode', 'auto')
            awb_modes_map = {
                'auto': controls.AwbModeEnum.Auto,
                'fluorescent': controls.AwbModeEnum.Fluorescent,
                'incandescent': controls.AwbModeEnum.Incandescent,
                'tungsten': controls.AwbModeEnum.Tungsten,
                'indoor': controls.AwbModeEnum.Indoor,
                'daylight': controls.AwbModeEnum.Daylight,
                'cloudy': controls.AwbModeEnum.Cloudy,
                'custom': controls.AwbModeEnum.Custom
            }
            
            if awb_mode in awb_modes_map:
                self.picam2.set_controls({"AwbMode": awb_modes_map[awb_mode]})
                logger.debug(f"Applied AWB mode: {awb_mode}")
            else:
                logger.warning(f"Unknown AWB mode: {awb_mode}, using auto")
                self.picam2.set_controls({"AwbMode": controls.AwbModeEnum.Auto})
                
        except Exception as e:
            logger.error(f"Error applying camera controls: {e}")
    
    def start_streaming(self):
        """Start camera streaming in dedicated thread"""
        with self.camera_lock:
            if not self.is_initialized:
                logger.error("Cannot start streaming - camera not initialized")
                return False
            
            if self.streaming_active:
                logger.info("Camera streaming already active")
                return True
            
            try:
                self.streaming_active = True
                self.stream_thread = threading.Thread(
                    target=self._stream_worker,
                    name="CameraStreamWorker",
                    daemon=True
                )
                self.stream_thread.start()
                
                self.camera_state.update_state(streaming=True)
                logger.info("Camera streaming started successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start camera streaming: {e}")
                self.streaming_active = False
                return False
    
    def _stream_worker(self):
        """Camera streaming worker thread"""
        logger.info("Camera streaming worker started")
        
        frame_interval = 1.0 / 30.0  # Target 30 FPS
        last_frame_time = 0
        
        while self.streaming_active:
            try:
                current_time = time.time()
                
                # Rate limiting
                if current_time - last_frame_time < frame_interval:
                    time.sleep(0.01)
                    continue
                
                # Check camera health
                if not self.is_initialized or not self.picam2:
                    logger.warning("Camera not available in streaming worker")
                    time.sleep(1)
                    continue
                
                # Capture frame and metadata
                request = self.picam2.capture_request()
                frame = request.make_array('main')
                metadata = request.get_metadata()
                request.release()
                
                # Update statistics
                self.frame_count += 1
                self.last_frame_time = current_time
                last_frame_time = current_time
                
                # Queue management - non-blocking
                self._queue_frame_safely(frame)
                self._queue_metadata_safely(metadata)
                
            except Exception as e:
                logger.error(f"Error in streaming worker: {e}")
                self.error_count += 1
                time.sleep(1)  # Brief pause on error
        
        logger.info("Camera streaming worker stopped")
    
    def _queue_frame_safely(self, frame):
        """Safely add frame to queue without blocking"""
        try:
            if not self.frames_queue.full():
                self.frames_queue.put_nowait(frame)
            else:
                # Remove oldest frame and add new one
                try:
                    self.frames_queue.get_nowait()
                except queue.Empty:
                    pass
                self.frames_queue.put_nowait(frame)
        except Exception as e:
            logger.debug(f"Error queuing frame: {e}")
    
    def _queue_metadata_safely(self, metadata):
        """Safely add metadata to queue without blocking"""
        try:
            # Always keep only the latest metadata
            try:
                self.metadata_queue.get_nowait()
            except queue.Empty:
                pass
            self.metadata_queue.put_nowait(metadata)
        except Exception as e:
            logger.debug(f"Error queuing metadata: {e}")
    
    def get_frame(self, timeout=1.0):
        """Get frame from queue with timeout"""
        try:
            return self.frames_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_metadata(self, timeout=0.1):
        """Get metadata from queue with timeout"""
        try:
            return self.metadata_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def generate_frames(self):
        """Generate frames for Flask video streaming"""
        logger.info("Starting video stream generator")
        
        while self.streaming_active:
            frame = self.get_frame(timeout=1.0)
            if frame is not None:
                try:
                    # Convert frame to JPEG
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    frame_bytes = buffer.tobytes()
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                           
                except Exception as e:
                    logger.error(f"Error encoding frame for streaming: {e}")
                    continue
            else:
                # No frame available, yield a small delay
                time.sleep(0.1)
        
        logger.info("Video stream generator stopped")
    
    def health_check(self):
        """Non-disruptive health check"""
        try:
            with self.camera_lock:
                if not self.is_initialized or not self.picam2:
                    return False, "Camera not initialized"
                
                if not hasattr(self.picam2, 'started') or not self.picam2.started:
                    return False, "Camera not started"
                
                # Check if frames are being produced
                if self.last_frame_time:
                    time_since_last_frame = time.time() - self.last_frame_time
                    if time_since_last_frame > 5.0:  # No frames for 5 seconds
                        return False, f"No frames for {time_since_last_frame:.1f} seconds"
                
                return True, f"Camera healthy - {self.frame_count} frames captured"
                
        except Exception as e:
            return False, f"Health check failed: {e}"
    
    def get_statistics(self):
        """Get camera statistics"""
        return {
            "initialized": self.is_initialized,
            "streaming": self.streaming_active,
            "frame_count": self.frame_count,
            "error_count": self.error_count,
            "last_frame_time": self.last_frame_time,
            "queue_sizes": {
                "frames": self.frames_queue.qsize(),
                "metadata": self.metadata_queue.qsize()
            },
            "current_settings": self.current_settings.copy(),
            "state": self.camera_state.get_state()
        }
    
    def stop_streaming(self):
        """Stop camera streaming"""
        logger.info("Stopping camera streaming...")
        self.streaming_active = False
        
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=5)
            if self.stream_thread.is_alive():
                logger.warning("Stream thread did not stop gracefully")
        
        self.camera_state.update_state(streaming=False)
        logger.info("Camera streaming stopped")
    
    def _cleanup_camera_internal(self):
        """Internal cleanup of camera resources"""
        if self.picam2:
            try:
                if hasattr(self.picam2, 'started') and self.picam2.started:
                    self.picam2.stop()
                    logger.debug("Camera stopped")
                
                self.picam2.close()
                logger.debug("Camera closed")
                
            except Exception as e:
                logger.error(f"Error during camera cleanup: {e}")
            finally:
                self.picam2 = None
                self.is_initialized = False
    
    def close_camera(self):
        """Public method to close camera"""
        logger.info("Closing camera...")
        
        # Stop streaming first
        self.stop_streaming()
        
        # Clean up camera resources
        with self.camera_lock:
            self._cleanup_camera_internal()
            
        # Update state
        self.camera_state.update_state(
            initialized=False,
            streaming=False
        )
        
        logger.info("Camera closed successfully")
    
    def restart_camera(self, **new_settings):
        """Restart camera with new settings"""
        logger.info("Restarting camera with new settings...")
        
        # Stop current operations
        self.stop_streaming()
        
        with self.camera_lock:
            self._cleanup_camera_internal()
        
        # Use current settings if no new settings provided
        settings = self.current_settings.copy()
        settings.update(new_settings)
        
        # Re-initialize and restart
        if self.initialize_camera_once(**settings):
            return self.start_streaming()
        else:
            return False

# Integration helper functions for existing v2 codebase
def get_camera_manager(frames_queue=None, metadata_queue=None):
    """Get the singleton camera manager instance"""
    return ImprovedCameraManager(frames_queue, metadata_queue)

def ensure_camera_initialized(**settings):
    """Ensure camera is initialized with given settings"""
    camera_manager = get_camera_manager()
    return camera_manager.initialize_camera_once(**settings)

def ensure_camera_streaming():
    """Ensure camera is streaming"""
    camera_manager = get_camera_manager()
    return camera_manager.start_streaming()

def get_camera_health():
    """Get camera health status"""
    camera_manager = get_camera_manager()
    return camera_manager.health_check()

def get_camera_statistics():
    """Get camera statistics"""
    camera_manager = get_camera_manager()
    return camera_manager.get_statistics()