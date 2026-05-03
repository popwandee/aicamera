#!/usr/bin/env python3
"""
Video Streaming Service for AI Camera v1.3

This service manages video streaming functionality using absolute imports
and dependency injection pattern with comprehensive fallback mechanisms.

Author: AI Camera Team
Version: 1.3
Date: August 8, 2025
"""

import threading
import time
import queue
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import cv2
import numpy as np
import base64
import io
from PIL import Image, ImageDraw, ImageFont

# Use absolute imports
from edge.src.core.utils.logging_config import get_logger
from edge.src.core.config import DEFAULT_RESOLUTION, DEFAULT_FRAMERATE, LORES_RESOLUTION

logger = get_logger(__name__)


class VideoStreamingService:
    """
    Video Streaming Service for managing video streaming functionality.
    
    Features:
    - Real-time video streaming with fallback mechanisms
    - Multiple frame sources (camera, cached, placeholder)
    - Frame processing and encoding with error recovery
    - Thread-safe operations
    - Integration with camera manager
    - WebSocket broadcasting
    - Graceful degradation on failures
    """
    
    def __init__(self, camera_manager=None, logger=None):
        """
        Initialize Video Streaming Service.
        
        Args:
            camera_manager: Camera manager instance
            logger: Logger instance
        """
        self.camera_manager = camera_manager
        self.logger = logger or get_logger(__name__)
        
        # Streaming state
        self.streaming = False
        self.streaming_thread = None
        self.stop_event = threading.Event()
        
        # Video settings - Use lores resolution for video feed (no resize needed)
        self.width, self.height = LORES_RESOLUTION  # Use config resolution
        self.fps = DEFAULT_FRAMERATE
        self.quality = 70
        
        # Frame queue for processing - reduced size for low latency
        self.frame_queue = queue.Queue(maxsize=3)  # Single frame buffer to prevent overlap (3 frames ป้องกันกระตุก เมื่อเน็ตช้า)
        
        # Fallback mechanisms
        self.fallback_mode = False
        self.fallback_frame = None
        self.last_successful_frame = None
        self.frame_source_history = []
        self.error_count = 0
        self.max_errors = 10
        self.error_recovery_time = 5.0  # seconds
        self.last_error_time = 0
        
        # Statistics
        self.frames_processed = 0
        self.frames_from_camera = 0
        self.frames_from_cache = 0
        self.frames_from_fallback = 0
        self.start_time = None
        self.last_frame_time = None
        self.average_fps = 0.0
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Initialize fallback frame
        self._initialize_fallback_frame()
        
        self.logger.info("VideoStreamingService initialized with fallback mechanisms")
    
    def _initialize_fallback_frame(self):
        """Initialize fallback frame for error states."""
        try:
            # Create a fallback frame with proper color and resolution
            fallback_img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            fallback_img[:] = (50, 50, 50)  # Dark gray background
            
            # Add a subtle pattern to make it more visible
            for i in range(0, self.height, 20):
                for j in range(0, self.width, 20):
                    if (i // 20 + j // 20) % 2 == 0:
                        fallback_img[i:i+20, j:j+20] = [40, 40, 40]  # Slightly darker
            
            # Add text with better visibility
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(fallback_img, "AI Camera", (self.width//2 - 100, self.height//2 - 50), 
                       font, 1.5, (255, 255, 255), 2)
            cv2.putText(fallback_img, "Video Feed", (self.width//2 - 80, self.height//2), 
                       font, 1.0, (200, 200, 200), 2)
            cv2.putText(fallback_img, "Initializing...", (self.width//2 - 70, self.height//2 + 50), 
                       font, 0.8, (150, 150, 150), 1)
            cv2.putText(fallback_img, f"{self.width}x{self.height}", (self.width//2 - 60, self.height//2 + 80), 
                       font, 0.6, (100, 100, 100), 1)
            
            self.fallback_frame = fallback_img
            self.logger.info(f"Fallback frame initialized with resolution {self.width}x{self.height}")
            
        except Exception as e:
            self.logger.error(f"Error initializing fallback frame: {e}")
            # Create minimal fallback using config resolution
            self.fallback_frame = np.zeros((LORES_RESOLUTION[1], LORES_RESOLUTION[0], 3), dtype=np.uint8)
    
    def _get_frame_with_fallback(self) -> Tuple[Optional[bytes], str]:
        """
        Get frame with comprehensive fallback mechanisms.
        
        Returns:
            Tuple[Optional[bytes], str]: Frame data (MJPEG bytes) and source description
        """
        current_time = time.time()
        
        # Check if we're in error recovery mode
        if self.fallback_mode and (current_time - self.last_error_time) < self.error_recovery_time:
            return self.fallback_frame, "fallback_recovery"
        
        try:
            # Primary source: Camera manager
            if self.camera_manager:
                # Try to get frame from camera manager
                try:
                    frame = self.camera_manager.camera_handler.capture_frame(source="buffer", stream_type="lores", include_metadata=False)
                    if frame is not None:
                        # Handle hardware-encoded frames (H.264 or MJPEG) and RGB888 arrays
                        if isinstance(frame, bytes) and len(frame) > 100:  # Hardware-encoded bytes
                            self.error_count = 0
                            self.fallback_mode = False
                            self.last_successful_frame = frame  # Store encoded bytes directly
                            self.frames_from_camera += 1
                            
                            # Determine encoder type based on frame header
                            if frame.startswith(b'\x00\x00\x00\x01') or frame.startswith(b'\x00\x00\x01'):
                                # H.264 NAL unit header
                                # self.logger.debug(f"Hardware H.264 frame: {len(frame)} bytes")  # INFO: ปิดเพื่อประหยัดพื้นที่
                                return frame, "camera_lores_h264"
                            else:
                                # MJPEG frame
                                # self.logger.debug(f"Hardware MJPEG frame: {len(frame)} bytes")  # INFO: ปิดเพื่อประหยัดพื้นที่
                                return frame, "camera_lores_mjpeg"
                        elif isinstance(frame, np.ndarray) and frame.size > 0:  # RGB888 array fallback
                            # Convert array to MJPEG bytes (software encoding)
                            try:
                                # Ensure frame has correct shape and color format
                                if len(frame.shape) == 3 and frame.shape[2] == 3:
                                    # On Pi5/PiSP, picamera2 "RGB888" make_array() delivers BGR in memory.
                                    # cv2.imencode expects BGR → pass directly, no conversion needed.
                                    frame_bgr = frame
                                else:
                                    # Handle grayscale or other formats
                                    if len(frame.shape) == 2:
                                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                                    else:
                                        frame_bgr = frame

                                # Ensure frame matches expected resolution
                                #if frame_bgr.shape[:2] != (self.height, self.width):
                                #    frame_bgr = cv2.resize(frame_bgr, (self.width, self.height))

                                # Encode to MJPEG
                                _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
                                mjpeg_bytes = buffer.tobytes()
                                
                                self.error_count = 0
                                self.fallback_mode = False
                                self.last_successful_frame = mjpeg_bytes
                                self.frames_from_camera += 1
                                # self.logger.debug(f"Software MJPEG frame: {len(mjpeg_bytes)} bytes, shape: {frame_bgr.shape}")  # INFO: ปิดเพื่อประหยัดพื้นที่
                                return mjpeg_bytes, "camera_lores_software"
                            except Exception as encode_error:
                                self.logger.error(f"Error encoding RGB888 to MJPEG: {encode_error}")
                                self.error_count += 1
                        else:
                            self.logger.warning(f"Invalid frame: type={type(frame)}, size={len(frame) if isinstance(frame, bytes) else frame.size if hasattr(frame, 'size') else 'N/A'}")
                    else:
                        self.logger.debug("No frame from camera manager")
                except Exception as camera_error:
                    self.logger.error(f"Camera capture error: {camera_error}")
                    self.error_count += 1
            
            # Secondary source: Last successful frame (cached)
            if self.last_successful_frame is not None:
                self.logger.debug("Using cached MJPEG frame")
                self.frames_from_cache += 1
                return self.last_successful_frame, "cached_frame"  # MJPEG bytes, no copy needed
            
            # Tertiary source: Fallback frame (convert to MJPEG)
            self.logger.debug("Using fallback frame")
            self.frames_from_fallback += 1
            self.fallback_mode = True
            self.last_error_time = current_time
            # Convert fallback frame to MJPEG bytes
            fallback_mjpeg = self._convert_fallback_to_mjpeg()
            return fallback_mjpeg, "fallback_frame"
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error getting frame: {e}")
            self.fallback_mode = True
            self.last_error_time = current_time
            
            # Return fallback frame as MJPEG
            fallback_mjpeg = self._convert_fallback_to_mjpeg()
            return fallback_mjpeg, "fallback_error"
    
    def _convert_fallback_to_mjpeg(self) -> bytes:
        """Convert fallback frame to MJPEG bytes."""
        try:
            _, buffer = cv2.imencode('.jpg', self.fallback_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            return buffer.tobytes()
        except Exception as e:
            self.logger.error(f"Error converting fallback frame to MJPEG: {e}")
            # Return minimal MJPEG header as last resort
            return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xff\xd9'
    
    def _process_frame_with_fallback(self, frame: bytes, source: str) -> Optional[Dict[str, Any]]:
        """
        Process frame with error handling and fallback mechanisms.
        
        Args:
            frame: Input frame as MJPEG bytes
            source: Source description for tracking
            
        Returns:
            Dict containing processed frame data or None if processing failed
        """
        try:
            # Frame is already MJPEG bytes from hardware encoder, no processing needed
            # Just validate and return with metadata
            
            # Validate MJPEG bytes
            if len(frame) < 100:
                self.logger.warning(f"Frame too small: {len(frame)} bytes")
                return None
            
            # Determine quality based on source
            quality = self.quality
            if source == "fallback_frame":
                quality = 60  # Lower quality for fallback
            elif source == "cached_frame":
                quality = 70  # Medium quality for cached
            elif source == "camera_lores_mjpeg":
                quality = 85  # High quality for hardware-encoded frames
            
            return {
                'frame_bytes': frame,  # MJPEG bytes directly
                'timestamp': datetime.now().isoformat(),
                'timestamp_capture': time.time(),  # For latency measurement
                'width': self.width,
                'height': self.height,
                'fps': self.fps,
                'source': source,
                'quality': quality,
                'format': 'MJPEG'
            }
            
        except Exception as e:
            self.logger.error(f"Error processing frame from {source}: {e}")
            return None
    
    def start_streaming(self) -> bool:
        """
        Start video streaming with fallback mechanisms.
        
        Returns:
            bool: True if streaming started successfully
        """
        with self.lock:
            if self.streaming:
                self.logger.info("Video streaming already active")
                return True
            
            try:
                self.stop_event.clear()
                self.streaming_thread = threading.Thread(
                    target=self._streaming_worker,
                    daemon=True
                )
                self.streaming_thread.start()
                self.streaming = True
                self.start_time = datetime.now()
                self.frames_processed = 0
                self.frames_from_camera = 0
                self.frames_from_cache = 0
                self.frames_from_fallback = 0
                self.error_count = 0
                self.fallback_mode = False
                self.logger.info("Video streaming started successfully with fallback mechanisms")
                return True
            except Exception as e:
                self.logger.error(f"Failed to start video streaming: {e}")
                return False
    
    def stop_streaming(self) -> bool:
        """
        Stop video streaming.
        
        Returns:
            bool: True if streaming stopped successfully
        """
        with self.lock:
            if not self.streaming:
                self.logger.info("Video streaming not active")
                return True
            
            try:
                self.stop_event.set()
                if self.streaming_thread and self.streaming_thread.is_alive():
                    self.streaming_thread.join(timeout=5)
                self.streaming = False
                self.logger.info("Video streaming stopped successfully")
                return True
            except Exception as e:
                self.logger.error(f"Failed to stop video streaming: {e}")
                return False
    
    def _streaming_worker(self):
        """Video streaming worker thread with fallback mechanisms."""
        self.logger.info("Video streaming worker started with fallback mechanisms")
        
        while not self.stop_event.is_set():
            try:
                # Get frame with fallback
                frame, source = self._get_frame_with_fallback()
                
                if frame is not None:
                    # Process frame (frame is already MJPEG bytes)
                    processed_frame = self._process_frame_with_fallback(frame, source)
                    
                    if processed_frame:
                        # Add timestamp for enqueue
                        processed_frame['timestamp_enqueue'] = time.time()
                        
                        # Add to queue (non-blocking)
                        try:
                            # Clear queue completely to prevent frame overlap
                            while not self.frame_queue.empty():
                                try:
                                    self.frame_queue.get_nowait()
                                except queue.Empty:
                                    break
                            self.frame_queue.put_nowait(processed_frame)
                        except queue.Full:
                            # This shouldn't happen with maxsize=1, but just in case
                            pass
                        
                        # Update statistics
                        self.frames_processed += 1
                        self.last_frame_time = datetime.now()
                        
                        # Track source history
                        self.frame_source_history.append(source)
                        if len(self.frame_source_history) > 100:
                            self.frame_source_history = self.frame_source_history[-100:]
                        
                        # Calculate average FPS
                        if self.start_time:
                            elapsed = (self.last_frame_time - self.start_time).total_seconds()
                            if elapsed > 0:
                                self.average_fps = self.frames_processed / elapsed
                
                # Sleep to maintain target FPS
                time.sleep(1.0 / self.fps)
                
            except Exception as e:
                self.logger.error(f"Error in streaming worker: {e}")
                self.error_count += 1
                time.sleep(0.1)  # Brief pause on error
        
        self.logger.info("Video streaming worker stopped")
    
    def get_frame(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Get the latest frame from the queue.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Frame data or None if no frame available
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get streaming service status with fallback information.
        
        Returns:
            Dict containing status information
        """
        # Calculate source distribution
        total_frames = self.frames_from_camera + self.frames_from_cache + self.frames_from_fallback
        source_distribution = {}
        if total_frames > 0:
            source_distribution = {
                'camera': round(self.frames_from_camera / total_frames * 100, 1),
                'cached': round(self.frames_from_cache / total_frames * 100, 1),
                'fallback': round(self.frames_from_fallback / total_frames * 100, 1)
            }
        
        # Get recent source history
        recent_sources = self.frame_source_history[-10:] if self.frame_source_history else []
        
        return {
            'streaming': self.streaming,
            'frames_processed': self.frames_processed,
            'average_fps': round(self.average_fps, 2),
            'queue_size': self.frame_queue.qsize(),
            'resolution': f"{self.width}x{self.height}",
            'target_fps': self.fps,
            'quality': self.quality,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_frame_time': self.last_frame_time.isoformat() if self.last_frame_time else None,
            'uptime': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            'fallback_mode': self.fallback_mode,
            'error_count': self.error_count,
            'source_distribution': source_distribution,
            'recent_sources': recent_sources,
            'frame_counts': {
                'camera': self.frames_from_camera,
                'cached': self.frames_from_cache,
                'fallback': self.frames_from_fallback
            }
        }
    
    def update_settings(self, **settings) -> bool:
        """
        Update streaming settings.
        
        Args:
            **settings: Settings to update
            
        Returns:
            bool: True if settings updated successfully
        """
        try:
            with self.lock:
                if 'width' in settings and 'height' in settings:
                    self.width = settings['width']
                    self.height = settings['height']
                    # Reinitialize fallback frame with new dimensions
                    self._initialize_fallback_frame()
                
                if 'fps' in settings:
                    self.fps = settings['fps']
                
                if 'quality' in settings:
                    self.quality = max(1, min(100, settings['quality']))
                
                self.logger.info(f"Streaming settings updated: {settings}")
                return True
        except Exception as e:
            self.logger.error(f"Error updating streaming settings: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on streaming service with fallback status.
        
        Returns:
            Dict containing health status
        """
        try:
            # Calculate health metrics
            total_frames = self.frames_from_camera + self.frames_from_cache + self.frames_from_fallback
            camera_ratio = self.frames_from_camera / total_frames if total_frames > 0 else 0
            fallback_ratio = self.frames_from_fallback / total_frames if total_frames > 0 else 0
            
            status = {
                'healthy': True,
                'streaming': self.streaming,
                'thread_alive': self.streaming_thread.is_alive() if self.streaming_thread else False,
                'queue_healthy': self.frame_queue.qsize() < 8,  # Not too full
                'fps_healthy': self.average_fps > 0.5 * self.fps,  # At least 50% of target FPS
                'last_frame_recent': True,
                'camera_health': camera_ratio > 0.5,  # At least 50% frames from camera
                'fallback_health': fallback_ratio < 0.3,  # Less than 30% fallback frames
                'error_rate_healthy': self.error_count < self.max_errors
            }
            
            # Check if last frame was recent
            if self.last_frame_time:
                time_since_last = (datetime.now() - self.last_frame_time).total_seconds()
                status['last_frame_recent'] = time_since_last < 5.0  # Within 5 seconds
            
            # Overall health assessment
            status['healthy'] = all([
                status['streaming'],
                status['thread_alive'],
                status['queue_healthy'],
                status['fps_healthy'],
                status['last_frame_recent'],
                status['error_rate_healthy']
            ])
            
            # Add detailed metrics
            status['metrics'] = {
                'camera_ratio': round(camera_ratio * 100, 1),
                'fallback_ratio': round(fallback_ratio * 100, 1),
                'error_count': self.error_count,
                'fallback_mode': self.fallback_mode
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
            return {
                'healthy': False,
                'error': str(e)
            }
    
    def reset_fallback_mode(self) -> bool:
        """
        Reset fallback mode and error counters.
        
        Returns:
            bool: True if reset successful
        """
        try:
            with self.lock:
                self.fallback_mode = False
                self.error_count = 0
                self.last_error_time = 0
                self.logger.info("Fallback mode reset")
                return True
        except Exception as e:
            self.logger.error(f"Error resetting fallback mode: {e}")
            return False
    
    def cleanup(self):
        """Cleanup resources."""
        try:
            self.stop_streaming()
            
            # Clear frame queue
            while not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.logger.info("VideoStreamingService cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


def create_video_streaming_service(camera_manager=None, logger=None) -> VideoStreamingService:
    """
    Factory function for VideoStreamingService.
    
    Args:
        camera_manager: Camera manager instance
        logger: Logger instance
        
    Returns:
        VideoStreamingService instance
    """
    return VideoStreamingService(camera_manager, logger)
