#!/usr/bin/env python3
"""
Camera Blueprint for AI Camera v2.0.0

This blueprint provides camera control and video streaming functionality:
- Video streaming endpoints
- Camera configuration management
- Camera status monitoring
- WebSocket events for real-time updates
- Auto-start status display

Author: AI Camera Team
Version: 2.0.0
Date: August 23, 2025
"""

import sys
import cv2
import numpy as np
import json
import time
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, Response, current_app
from flask_socketio import emit, join_room, leave_room

# Use absolute imports
from edge.src.core.dependency_container import get_service
from edge.src.core.utils.logging_config import get_logger
from edge.src.components.camera_handler import make_json_serializable
from edge.src.core.config import MAIN_RESOLUTION, DEFAULT_FRAMERATE
from edge.src.services.browser_connection_manager import BrowserConnectionManager

# Create blueprint
camera_bp = Blueprint('camera', __name__, url_prefix='/camera')

logger = get_logger(__name__)


@camera_bp.route('/')
def camera_dashboard():
    """
    Camera dashboard page with auto-start status.
    
    Returns:
        str: Rendered HTML template
    """
    try:
        camera_manager = get_service('camera_manager')
        camera_status = camera_manager.get_status() if camera_manager else {}
        camera_settings = camera_manager.get_available_settings() if camera_manager else {}
        
        # Add auto-start information to template context
        auto_start_info = {
            'enabled': camera_status.get('auto_start_enabled', False),
            'uptime': camera_status.get('uptime', 0)
        }
        
        response = render_template('camera/dashboard.html',
                             camera_status=camera_status,
                             camera_settings=camera_settings,
                             auto_start_info=auto_start_info,
                             title="Camera Dashboard",
                             use_socketio=False,
                             timestamp=int(time.time()))
        return response
    except Exception as e:
        logger.error(f"Error in camera dashboard: {e}")
        response = render_template('camera/dashboard.html',
                             camera_status={},
                             camera_settings={},
                             auto_start_info={'enabled': False, 'uptime': 0},
                             title="Camera Dashboard",
                             use_socketio=True,
                             timestamp=int(time.time()))
        return response


@camera_bp.route('/status')
def get_camera_status():
    """
    Get current camera status including auto-start information.
    
    Returns:
        dict: JSON response with camera status
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            response = jsonify({'error': 'Camera manager not available'}), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
        
        status = camera_manager.get_status()
        
        # Ensure all status data is JSON serializable
        serializable_status = make_json_serializable(status)
        
        response = jsonify({
            'success': True,
            'status': serializable_status,
            'timestamp': datetime.now().isoformat()
        })
        response.headers['Cache-Control'] = 'no-cache'
        
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"Error getting camera status: {e}")
        response = jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
        response[0].headers['Cache-Control'] = 'no-cache'
        
        response[0].headers['Expires'] = '0'
        return response


@camera_bp.route('/start', methods=['POST'])
def start_camera():
    """
    Start camera streaming (manual start).
    
    Returns:
        dict: JSON response with start result
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            response = jsonify({'error': 'Camera manager not available'}), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
        
        success = camera_manager.start()
        if success:
            response = jsonify({
                'success': True,
                'message': 'Camera started successfully',
                'timestamp': datetime.now().isoformat()
            })
            response.headers['Cache-Control'] = 'no-cache'
            
            response.headers['Expires'] = '0'
            return response
        else:
            response = jsonify({
                'success': False,
                'error': 'Failed to start camera',
                'timestamp': datetime.now().isoformat()
            }), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
    except Exception as e:
        logger.error(f"Error starting camera: {e}")
        response = jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
        response[0].headers['Cache-Control'] = 'no-cache'
        
        response[0].headers['Expires'] = '0'
        return response


@camera_bp.route('/stop', methods=['POST'])
def stop_camera():
    """
    Stop camera streaming.
    
    Returns:
        dict: JSON response with stop result
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            response = jsonify({'error': 'Camera manager not available'}), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
        
        success = camera_manager.stop()
        if success:
            response = jsonify({
                'success': True,
                'message': 'Camera stopped successfully',
                'timestamp': datetime.now().isoformat()
            })
            response.headers['Cache-Control'] = 'no-cache'
            
            response.headers['Expires'] = '0'
            return response
        else:
            response = jsonify({
                'success': False,
                'error': 'Failed to stop camera',
                'timestamp': datetime.now().isoformat()
            }), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
    except Exception as e:
        logger.error(f"Error stopping camera: {e}")
        response = jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
        response[0].headers['Cache-Control'] = 'no-cache'
        
        response[0].headers['Expires'] = '0'
        return response


@camera_bp.route('/restart', methods=['POST'])
def restart_camera():
    """
    Restart camera.
    
    Returns:
        dict: JSON response with restart result
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            return jsonify({'error': 'Camera manager not available'}), 500
        
        success = camera_manager.restart()
        if success:
            response = jsonify({
                'success': True,
                'message': 'Camera restarted successfully',
                'timestamp': datetime.now().isoformat()
            })
            response.headers['Cache-Control'] = 'no-cache'
            
            response.headers['Expires'] = '0'
            return response
        else:
            response = jsonify({
                'success': False,
                'error': 'Failed to restart camera',
                'timestamp': datetime.now().isoformat()
            }), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
    except Exception as e:
        logger.error(f"Error restarting camera: {e}")
        response = jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
        response[0].headers['Cache-Control'] = 'no-cache'
        
        response[0].headers['Expires'] = '0'
        return response


@camera_bp.route('/config', methods=['GET', 'POST'])
def camera_config():
    """
    Camera configuration management.
    
    Returns:
        dict: JSON response with configuration data
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            response = jsonify({'error': 'Camera manager not available'}), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
        
        if request.method == 'GET':
            # Get current configuration
            config = camera_manager.get_configuration()
            
            response = jsonify({
                'success': True,
                'config': config,
                'timestamp': datetime.now().isoformat()
            })
            response.headers['Cache-Control'] = 'no-cache'
            
            response.headers['Expires'] = '0'
            return response
        else:
            # Update configuration
            data = request.get_json()
            if not data:
                response = jsonify({'error': 'No configuration data provided'}), 400
                response[0].headers['Cache-Control'] = 'no-cache'
                
                response[0].headers['Expires'] = '0'
                return response
            
            result = camera_manager.update_configuration(data)
            
            response = jsonify({
                'success': result.get('success', False),
                'message': result.get('message', ''),
                'error': result.get('error', ''),
                'timestamp': datetime.now().isoformat()
            })
            response.headers['Cache-Control'] = 'no-cache'
            
            response.headers['Expires'] = '0'
            return response
    except Exception as e:
        logger.error(f"Error in camera config: {e}")
        response = jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
        response[0].headers['Cache-Control'] = 'no-cache'
        
        response[0].headers['Expires'] = '0'
        return response


@camera_bp.route('/capture', methods=['POST'])
def capture_image():
    """
    Capture a single image.
    
    Returns:
        dict: JSON response with capture result
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            return jsonify({'error': 'Camera manager not available'}), 500
        
        image_data = camera_manager.capture_image()
        if image_data:
            # Extract data from camera manager response
            # Note: camera_manager.capture_image() returns the frame data, not file info
            # We need to handle this differently
            
            # For now, return basic success response
            # The actual image saving is handled by the camera manager internally
            response = jsonify({
                'success': True,
                'message': 'Image captured successfully',
                'timestamp': datetime.now().isoformat()
            })
            response.headers['Cache-Control'] = 'no-cache'
            
            response.headers['Expires'] = '0'
            return response
        else:
            response = jsonify({
                'success': False,
                'error': 'Failed to capture image',
                'timestamp': datetime.now().isoformat()
            }), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
    except Exception as e:
        logger.error(f"Error capturing image: {e}")
        response = jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
        response[0].headers['Cache-Control'] = 'no-cache'
        
        response[0].headers['Expires'] = '0'
        return response


@camera_bp.route('/health')
def camera_health():
    """
    Camera health check endpoint.
    
    Returns:
        dict: JSON response with health status
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            response = jsonify({'error': 'Camera manager not available'}), 500
            response[0].headers['Cache-Control'] = 'no-cache'
            
            response[0].headers['Expires'] = '0'
            return response
        
        health = camera_manager.health_check()
        
        response = jsonify({
            'success': True,
            'health': health,
            'timestamp': datetime.now().isoformat()
        })
        response.headers['Cache-Control'] = 'no-cache'
        
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"Error in camera health check: {e}")
        response = jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
        response[0].headers['Cache-Control'] = 'no-cache'
        
        response[0].headers['Expires'] = '0'
        return response


def generate_frames():
    """
    Generate video frames for streaming using camera manager data.
    Implements comprehensive error handling with retry mechanisms and graceful degradation.
    
    Yields:
        bytes: Frame data in multipart format
    """
    # Error handling configuration
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 1.0  # seconds
    ERROR_FRAME_INTERVAL = 2.0  # seconds between error frames
    HEALTH_CHECK_INTERVAL = 30  # seconds between health checks
    
    retry_count = 0
    last_error_time = 0
    last_health_check = 0
    consecutive_errors = 0
    frame_count = 0
    
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            logger.error("Camera manager not available for streaming")
            yield _generate_error_placeholder("Camera manager not available")
            return
        
        # Initial health check
        manager_status = camera_manager.get_status()
        if not manager_status.get('initialized', False):
            logger.warning("Camera not initialized according to manager")
            yield _generate_error_placeholder("Camera not initialized")
            return
        
        if not manager_status.get('streaming', False):
            logger.warning("Camera not streaming according to manager")
            yield _generate_error_placeholder("Camera not streaming")
            return
        
        logger.info("Starting video stream generation using camera manager")

        _frame_interval = 1.0 / DEFAULT_FRAMERATE  # match capture FPS (e.g. 0.067s @ 15 FPS)

        while True:
            try:
                loop_start = time.time()
                current_time = loop_start

                # Periodic health check
                if current_time - last_health_check > HEALTH_CHECK_INTERVAL:
                    try:
                        manager_status = camera_manager.get_status()
                        if not manager_status.get('initialized', False):
                            logger.warning("Camera lost initialization during streaming")
                            yield _generate_error_placeholder("Camera lost initialization")
                            time.sleep(RETRY_DELAY)
                            continue
                        if not manager_status.get('streaming', False):
                            logger.warning("Camera stopped streaming during operation")
                            yield _generate_error_placeholder("Camera stopped streaming")
                            time.sleep(RETRY_DELAY)
                            continue
                        last_health_check = current_time
                        consecutive_errors = 0  # Reset error counter on successful health check
                    except Exception as health_error:
                        logger.error(f"Health check failed: {health_error}")
                        consecutive_errors += 1
                
                # Get lores frame from camera manager
                frame_data = camera_manager.camera_handler.capture_frame(source="buffer", stream_type="lores", include_metadata=False)
                
                if frame_data is None:
                    consecutive_errors += 1
                    if consecutive_errors > MAX_RETRY_ATTEMPTS:
                        logger.error(f"Too many consecutive errors ({consecutive_errors}), sending error frame")
                        yield _generate_error_placeholder("Camera temporarily unavailable")
                        time.sleep(ERROR_FRAME_INTERVAL)
                    else:
                        logger.warning(f"No lores frame data (attempt {consecutive_errors}/{MAX_RETRY_ATTEMPTS})")
                        yield _generate_error_placeholder("No frame data available")
                        time.sleep(RETRY_DELAY)
                    continue
                
                # Handle different frame data formats with validation
                frame = None
                if isinstance(frame_data, dict) and 'frame' in frame_data:
                    frame = frame_data['frame']
                elif isinstance(frame_data, np.ndarray):
                    frame = frame_data
                else:
                    consecutive_errors += 1
                    logger.warning(f"Invalid frame data format: {type(frame_data)}")
                    yield _generate_error_placeholder("Invalid frame format")
                    time.sleep(RETRY_DELAY)
                    continue
                
                # Validate frame data
                if frame is None or not isinstance(frame, np.ndarray):
                    consecutive_errors += 1
                    logger.warning("Frame is None or not a numpy array")
                    yield _generate_error_placeholder("Invalid frame data")
                    time.sleep(RETRY_DELAY)
                    continue
                
                if frame.size == 0 or len(frame.shape) != 3:
                    consecutive_errors += 1
                    logger.warning(f"Invalid frame shape: {frame.shape}")
                    yield _generate_error_placeholder("Invalid frame dimensions")
                    time.sleep(RETRY_DELAY)
                    continue
                
                # Encode frame with error handling
                try:
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if not ret or buffer is None:
                        consecutive_errors += 1
                        logger.warning("Frame encoding failed")
                        yield _generate_error_placeholder("Frame encoding failed")
                        time.sleep(RETRY_DELAY)
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    if len(frame_bytes) == 0:
                        consecutive_errors += 1
                        logger.warning("Encoded frame is empty")
                        yield _generate_error_placeholder("Empty encoded frame")
                        time.sleep(RETRY_DELAY)
                        continue
                    
                    # Success - reset error counters
                    consecutive_errors = 0
                    retry_count = 0
                    frame_count += 1
                    
                    # Log progress every 100 frames
                    if frame_count % 100 == 0:
                        logger.info(f"Successfully generated {frame_count} frames")
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                except Exception as encode_error:
                    consecutive_errors += 1
                    logger.error(f"Frame encoding error: {encode_error}")
                    yield _generate_error_placeholder("Frame encoding error")
                    time.sleep(RETRY_DELAY)
                    continue
                
                # Rate-limit to match the capture FPS so the stream doesn't spin faster
                # than the buffer updates (avoids repeated/skipped frames)
                elapsed = time.time() - loop_start
                sleep_time = _frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as frame_error:
                consecutive_errors += 1
                current_time = time.time()
                
                # Rate limit error logging
                if current_time - last_error_time > 5.0:  # Log errors at most every 5 seconds
                    logger.error(f"Error generating frame: {frame_error}")
                    last_error_time = current_time
                
                # Handle different types of errors
                if "camera" in str(frame_error).lower():
                    error_message = "Camera hardware error"
                elif "memory" in str(frame_error).lower():
                    error_message = "Memory allocation error"
                elif "timeout" in str(frame_error).lower():
                    error_message = "Camera timeout"
                else:
                    error_message = "Frame generation error"
                
                yield _generate_error_placeholder(error_message)
                
                # Adaptive retry delay based on error frequency
                if consecutive_errors > MAX_RETRY_ATTEMPTS:
                    time.sleep(ERROR_FRAME_INTERVAL)
                else:
                    time.sleep(RETRY_DELAY)
                
    except Exception as stream_error:
        logger.error(f"Critical error in generate_frames: {stream_error}")
        yield _generate_error_placeholder("Critical streaming error")
    finally:
        logger.info("Video stream generation ended")


def generate_lores_frames():
    """
    Generate low resolution video frames for streaming.
    Implements comprehensive error handling with retry mechanisms and graceful degradation.
    
    Yields:
        bytes: Frame data in multipart format
    """
    # Error handling configuration
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 1.0  # seconds
    ERROR_FRAME_INTERVAL = 2.0  # seconds between error frames
    HEALTH_CHECK_INTERVAL = 30  # seconds between health checks
    
    retry_count = 0
    last_error_time = 0
    last_health_check = 0
    consecutive_errors = 0
    frame_count = 0
    
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager or not camera_manager.camera_handler:
            logger.error("Camera manager or handler not available for lores streaming")
            yield _generate_error_placeholder("Camera manager not available")
            return
        
        camera_handler = camera_manager.camera_handler
        
        # Initial health check
        camera_status = camera_handler.get_camera_status()
        if not camera_status.get('initialized', False):
            logger.warning("Camera not initialized for lores streaming")
            yield _generate_error_placeholder("Camera not initialized")
            return
        
        if not camera_status.get('streaming', False):
            logger.warning("Camera not streaming for lores, attempting to start...")
            # Try to start the camera if it's not streaming
            try:
                # Use camera manager to ensure camera is streaming
                if camera_manager.ensure_camera_streaming():
                    logger.info("Camera streaming started successfully for lores")
                    # Get updated status
                    camera_status = camera_handler.get_camera_status()
                else:
                    logger.warning("Failed to start camera streaming for lores, sending placeholder")
                    yield _generate_error_placeholder("Camera not streaming - failed to start")
                    return
            except Exception as e:
                logger.error(f"Error starting camera for lores: {e}")
                yield _generate_error_placeholder(f"Camera start error: {str(e)}")
                return
        
        logger.info("Starting low-resolution video stream generation")
        
        while True:
            try:
                current_time = time.time()
                
                # Periodic health check
                if current_time - last_health_check > HEALTH_CHECK_INTERVAL:
                    try:
                        camera_status = camera_handler.get_camera_status()
                        if not camera_status.get('initialized', False):
                            logger.warning("Camera lost initialization during lores streaming")
                            yield _generate_error_placeholder("Camera lost initialization")
                            time.sleep(RETRY_DELAY)
                            continue
                        if not camera_status.get('streaming', False):
                            logger.warning("Camera stopped streaming during lores operation")
                            yield _generate_error_placeholder("Camera stopped streaming")
                            time.sleep(RETRY_DELAY)
                            continue
                        last_health_check = current_time
                        consecutive_errors = 0  # Reset error counter on successful health check
                    except Exception as health_error:
                        logger.error(f"Lores health check failed: {health_error}")
                        consecutive_errors += 1
                
                # Use camera manager to capture lores frame
                frame_data = camera_manager.camera_handler.capture_frame(source="buffer", stream_type="lores", include_metadata=False)
                
                if frame_data is None:
                    consecutive_errors += 1
                    if consecutive_errors > MAX_RETRY_ATTEMPTS:
                        logger.error(f"Too many consecutive lores errors ({consecutive_errors}), sending error frame")
                        yield _generate_error_placeholder("Camera temporarily unavailable")
                        time.sleep(ERROR_FRAME_INTERVAL)
                    else:
                        logger.warning(f"No lores frame data (attempt {consecutive_errors}/{MAX_RETRY_ATTEMPTS})")
                        yield _generate_error_placeholder("No lores frame data")
                        time.sleep(RETRY_DELAY)
                    continue
                
                # Handle different frame data formats with validation
                frame = None
                if isinstance(frame_data, dict) and 'frame' in frame_data:
                    frame = frame_data['frame']
                elif isinstance(frame_data, np.ndarray):
                    frame = frame_data
                else:
                    consecutive_errors += 1
                    logger.warning(f"Invalid lores frame data format: {type(frame_data)}")
                    yield _generate_error_placeholder("Invalid lores frame format")
                    time.sleep(RETRY_DELAY)
                    continue
                
                # Validate frame data
                if frame is None or not isinstance(frame, np.ndarray):
                    consecutive_errors += 1
                    logger.warning("Lores frame is None or not a numpy array")
                    yield _generate_error_placeholder("Invalid lores frame data")
                    time.sleep(RETRY_DELAY)
                    continue
                
                if frame.size == 0 or len(frame.shape) != 3:
                    consecutive_errors += 1
                    logger.warning(f"Invalid lores frame shape: {frame.shape}")
                    yield _generate_error_placeholder("Invalid lores frame dimensions")
                    time.sleep(RETRY_DELAY)
                    continue
                
                # Encode frame with error handling
                try:
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if not ret or buffer is None:
                        consecutive_errors += 1
                        logger.warning("Lores frame encoding failed")
                        yield _generate_error_placeholder("Lores frame encoding failed")
                        time.sleep(RETRY_DELAY)
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    if len(frame_bytes) == 0:
                        consecutive_errors += 1
                        logger.warning("Encoded lores frame is empty")
                        yield _generate_error_placeholder("Empty encoded lores frame")
                        time.sleep(RETRY_DELAY)
                        continue
                    
                    # Success - reset error counters
                    consecutive_errors = 0
                    retry_count = 0
                    frame_count += 1
                    
                    # Log progress every 100 frames
                    if frame_count % 100 == 0:
                        logger.info(f"Successfully generated {frame_count} lores frames")
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                except Exception as encode_error:
                    consecutive_errors += 1
                    logger.error(f"Lores frame encoding error: {encode_error}")
                    yield _generate_error_placeholder("Lores frame encoding error")
                    time.sleep(RETRY_DELAY)
                    continue
                
                time.sleep(0.1)  # ~10 FPS for lores
                
            except Exception as frame_error:
                consecutive_errors += 1
                current_time = time.time()
                
                # Rate limit error logging
                if current_time - last_error_time > 5.0:  # Log errors at most every 5 seconds
                    logger.error(f"Error generating lores frame: {frame_error}")
                    last_error_time = current_time
                
                # Handle different types of errors
                if "camera" in str(frame_error).lower():
                    error_message = "Camera hardware error"
                elif "memory" in str(frame_error).lower():
                    error_message = "Memory allocation error"
                elif "timeout" in str(frame_error).lower():
                    error_message = "Camera timeout"
                else:
                    error_message = "Lores frame generation error"
                
                yield _generate_error_placeholder(error_message)
                
                # Adaptive retry delay based on error frequency
                if consecutive_errors > MAX_RETRY_ATTEMPTS:
                    time.sleep(ERROR_FRAME_INTERVAL)
                else:
                    time.sleep(RETRY_DELAY)
                
    except Exception as e:
        logger.error(f"Critical error in generate_lores_frames: {e}")
        yield _generate_error_placeholder(f"Critical lores stream error: {str(e)}")
    finally:
        logger.info("Lores video stream generation ended")


def _generate_status_frame(manager_status, frame_count):
    """
    Generate a status frame showing camera information.
    
    Args:
        manager_status: Camera manager status
        frame_count: Current frame count
    
    Returns:
        numpy.ndarray: Status frame image
    """
    try:
        # Create a simple status display frame
        from edge.src.core.config import LORES_RESOLUTION
        width, height = LORES_RESOLUTION
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Fill with dark background
        frame[:] = (20, 20, 20)
        
        # Add status information
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        color = (255, 255, 255)
        thickness = 2
        
        # Title
        cv2.putText(frame, "AI Camera Status", (50, 50), font, 1.2, (0, 255, 0), 2)
        
        # Status information
        y_position = 100
        line_height = 35
        
        status_info = [
            f"Camera Available: {manager_status.get('camera_available', 'Unknown')}",
            f"Streaming: {manager_status.get('streaming', 'Unknown')}",
            f"Initialized: {manager_status.get('initialized', 'Unknown')}",
            f"Frame Count: {frame_count}",
            f"Uptime: {manager_status.get('uptime', 'Unknown')}",
            f"Auto Start: {manager_status.get('auto_start_enabled', 'Unknown')}",
            f"Auto Streaming: {manager_status.get('auto_streaming_enabled', 'Unknown')}"
        ]
        
        for info in status_info:
            cv2.putText(frame, info, (50, y_position), font, font_scale, color, thickness)
            y_position += line_height
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, f"Last Update: {timestamp}", (50, height - 30), font, 0.6, (150, 150, 150), 1)
        
        return frame
        
    except Exception as e:
        logger.error(f"Error generating status frame: {e}")
        return None


def _generate_error_placeholder(message):
    """
    Generate a placeholder image for error states with improved visual feedback.
    
    Args:
        message (str): Error message to display
        
    Returns:
        bytes: Placeholder frame data
    """
    try:
        # Create a simple error placeholder image
        import numpy as np
        
        # Create a 640x480 image with gradient background
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Create gradient background (dark to lighter)
        for y in range(480):
            intensity = int(20 + (y / 480) * 40)  # 20 to 60
            img[y, :] = (intensity, intensity, intensity)
        
        # Add text to the image
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        color = (255, 255, 255)  # White text
        thickness = 2
        
        # Add error icon/indicator
        cv2.circle(img, (320, 120), 40, (0, 0, 255), 3)  # Red circle
        cv2.putText(img, "!", (310, 140), font, 1.5, (0, 0, 255), 3)  # Exclamation mark
        
        # Add title
        cv2.putText(img, "Camera Error", (200, 200), font, 1.2, (0, 0, 255), 2)
        
        # Split message into lines for better readability
        words = message.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            # Estimate text width (rough calculation)
            if len(test_line) > 30:  # Approximate character limit
                lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        
        if current_line:
            lines.append(current_line)
        
        # Display message lines
        y_position = 250
        line_height = 35
        
        for line in lines:
            # Get text size for centering
            (text_width, text_height), baseline = cv2.getTextSize(line, font, font_scale, thickness)
            x_position = (640 - text_width) // 2
            cv2.putText(img, line, (x_position, y_position), font, font_scale, color, thickness)
            y_position += line_height
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        cv2.putText(img, f"Time: {timestamp}", (50, 450), font, 0.6, (150, 150, 150), 1)
        
        # Add retry indicator
        cv2.putText(img, "Retrying...", (500, 450), font, 0.6, (0, 255, 0), 1)
        
        # Encode to JPEG with good quality
        ret, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ret:
            frame_bytes = buffer.tobytes()
            return (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # Fallback to simple text response
            return (b'--frame\r\n'
                   b'Content-Type: text/plain\r\n\r\n' + message.encode() + b'\r\n')
    except Exception as e:
        logger.error(f"Error generating placeholder: {e}")
        # Ultimate fallback - simple text response
        return (b'--frame\r\n'
               b'Content-Type: text/plain\r\n\r\nCamera Error: ' + message.encode() + b'\r\n')


def _generate_error_frame(message):
    """
    Generate a proper JPEG error frame instead of text placeholder.
    
    Args:
        message: Error message to display
        
    Returns:
        bytes: JPEG image data
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Create a simple error image
        img = Image.new('RGB', (640, 480), color='red')
        draw = ImageDraw.Draw(img)
        
        # Try to use a default font, fallback to basic if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            try:
                font = ImageFont.load_default()
            except:
                font = None
        
        # Draw error message
        text = f"Camera Error: {message}"
        if font:
            # Center the text
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (640 - text_width) // 2
            y = (480 - text_height) // 2
            draw.text((x, y), text, fill='white', font=font)
        else:
            # Fallback: draw text at fixed position
            draw.text((50, 200), text, fill='white')
        
        # Convert to JPEG bytes
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG', quality=85)
        return img_io.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating error frame: {e}")
        # Ultimate fallback: return a minimal valid JPEG
        return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'


def _generate_error_stream(message):
    """
    Generate a continuous error stream with proper JPEG frames.
    
    Args:
        message: Error message to display
        
    Yields:
        bytes: Error frame data
    """
    error_frame = _generate_error_frame(message)
    while True:
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
        time.sleep(2.0)  # Show error frame every 2 seconds


@camera_bp.route('/video_feed')
def video_feed():
    """
    Video streaming endpoint with enhanced fallback mechanisms and improved chunked encoding.
    
    Returns:
        Response: Multipart video stream
    """
    try:
        # Check if video streaming service is available
        video_streaming = get_service('video_streaming')
        if video_streaming and hasattr(video_streaming, 'get_frame'):
            # Use video streaming service if available
            logger.info("Using video streaming service for video feed")
            return Response(
                _generate_frames_from_service_improved(video_streaming),
                mimetype='multipart/x-mixed-replace; boundary=frame',
                headers={
                    'Cache-Control': 'no-cache',
                    'Expires': '0',
                    'Connection': 'keep-alive',
                    'Transfer-Encoding': 'chunked',
                    'X-Accel-Buffering': 'no',  # Disable nginx buffering
                    'X-Content-Type-Options': 'nosniff'
                }
            )
        else:
            # Fallback to direct camera manager
            logger.info("Video streaming service not available, using direct camera manager")
            try:
                return Response(
                    generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Expires': '0',
                        'Connection': 'keep-alive',
                        'Transfer-Encoding': 'chunked',
                        'X-Accel-Buffering': 'no',  # Disable nginx buffering
                        'X-Content-Type-Options': 'nosniff'
                    }
                )
            except Exception as fallback_error:
                logger.error(f"Direct camera manager fallback failed: {fallback_error}")
                # Ultimate fallback: error stream
                return Response(
                    _generate_error_stream("Camera service unavailable"),
                    mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Expires': '0',
                        'Connection': 'keep-alive',
                        'Transfer-Encoding': 'chunked',
                        'X-Accel-Buffering': 'no',  # Disable nginx buffering
                        'X-Content-Type-Options': 'nosniff'
                    }
                )
    except Exception as e:
        logger.error(f"Error in video_feed endpoint: {e}")
        # Return error stream instead of failing completely
        return Response(
            _generate_error_stream("Video feed error"),
            mimetype='multipart/x-mixed-replace; boundary=frame',
            headers={
                'Cache-Control': 'no-cache',
                
                'Expires': '0',
                'Connection': 'keep-alive',
                'Transfer-Encoding': 'chunked',
                'X-Accel-Buffering': 'no',  # Disable nginx buffering
                'X-Content-Type-Options': 'nosniff'
            }
        )


def _generate_frames_from_service_improved(video_streaming):
    """
    Generate frames using video streaming service with improved error handling and complete MJPEG stream formatting.
    
    Args:
        video_streaming: Video streaming service instance
        
    Yields:
        bytes: Frame data in multipart format
    """
    consecutive_errors = 0
    max_errors = 3  # Reduced from 5 to 3
    error_delay = 0.5  # Reduced from 1.0 to 0.5
    frame_count = 0
    last_frame_time = time.time()
    
    try:
        # Start streaming if not already started
        if not video_streaming.streaming:
            try:
                video_streaming.start_streaming()
                time.sleep(0.5)  # Wait for streaming to start
                logger.info("Video streaming started successfully")
            except Exception as start_error:
                logger.error(f"Failed to start video streaming: {start_error}")
                # Continue with fallback frames
        
        while True:
            try:
                # Get frame from service with no timeout
                frame_data = video_streaming.get_frame()  # Reduced from 2.0 to 1.0 video_streaming.get_frame(timeout=1.0)
                
                if frame_data and 'frame_bytes' in frame_data:
                    # Use MJPEG bytes directly (no base64 decode needed)
                    try:
                        frame_bytes = frame_data['frame_bytes']
                        # Log frame information for debugging
                        source = frame_data.get('source', 'unknown')
                        width = frame_data.get('width', 'unknown')
                        height = frame_data.get('height', 'unknown')
                        quality = frame_data.get('quality', 'unknown')
                        timestamp_capture = frame_data.get('timestamp_capture', 0)
                        timestamp_enqueue = frame_data.get('timestamp_enqueue', 0)
                        
                        # Validate frame data
                        if len(frame_bytes) > 100:  # Ensure frame has reasonable size
                            # Reset error counter on success
                            consecutive_errors = 0
                            frame_count += 1
                            current_time = time.time()
                            
                            # Calculate latency metrics
                            latency_capture_to_yield = current_time - timestamp_capture if timestamp_capture > 0 else 0
                            latency_enqueue_to_yield = current_time - timestamp_enqueue if timestamp_enqueue > 0 else 0
                            
                            # สรุปการทำงานเป็นช่วง ๆ เพื่อลดการใช้พื้นที่ log
                            if frame_count % 300 == 0:  # Every ~300 frames
                                fps = 300.0 / (current_time - last_frame_time) if current_time > last_frame_time else 0
                                logger.info(f"Video feed summary - frames:{frame_count} fps:{fps:.1f} latency:{latency_capture_to_yield*1000:.0f}ms src:{source}")
                                last_frame_time = current_time
                            
                            # Send frame with proper MJPEG formatting
                            # Ensure complete multipart boundary and content
                            frame_data = (b'--frame\r\n'
                                         b'Content-Type: image/jpeg\r\n'
                                         b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n'
                                         b'\r\n' + frame_bytes + b'\r\n')
                            
                            # Ensure proper encoding and yield
                            yield frame_data
                            
                            # No sleep here - FPS is controlled by the worker thread
                            
                        else:
                            consecutive_errors += 1
                            logger.warning(f"Frame too small: {len(frame_bytes)} bytes, Source: {source}, Expected size: {width}x{height}")
                            # Generate error frame for small frames
                            error_frame = _generate_error_frame(f"Frame data too small: {len(frame_bytes)} bytes")
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n'
                                   b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n'
                                   b'\r\n' + error_frame + b'\r\n')
                            time.sleep(error_delay)
                            
                    except Exception as decode_error:
                        consecutive_errors += 1
                        logger.error(f"Frame decode error: {decode_error}, Source: {source}, Frame data keys: {list(frame_data.keys()) if frame_data else 'None'}")
                        # Generate error frame for decode errors
                        error_frame = _generate_error_frame(f"Frame decode error: {str(decode_error)[:50]}")
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n'
                               b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n'
                               b'\r\n' + error_frame + b'\r\n')
                        time.sleep(error_delay)
                else:
                    consecutive_errors += 1
                    if consecutive_errors > max_errors:
                        # Generate error frame instead of placeholder
                        error_frame = _generate_error_frame("No frame data from streaming service")
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n'
                               b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n'
                               b'\r\n' + error_frame + b'\r\n')
                        time.sleep(error_delay)
                    else:
                        time.sleep(0.1)
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error getting frame from streaming service: {e}")
                
                if consecutive_errors > max_errors:
                    # Generate error frame instead of placeholder
                    error_frame = _generate_error_frame("Streaming service error")
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n'
                           b'\r\n' + error_frame + b'\r\n')
                    time.sleep(error_delay)
                else:
                    time.sleep(0.1)
                    
    except Exception as e:
        logger.error(f"Critical error in _generate_frames_from_service_improved: {e}")
        # Generate error frame
        error_frame = _generate_error_frame("Critical streaming service error")
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n'
               b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n'
               b'\r\n' + error_frame + b'\r\n')
        # Continue generating error frames
        while True:
            time.sleep(2.0)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n'
                   b'\r\n' + error_frame + b'\r\n')


@camera_bp.route('/video_feed_lores')
def video_feed_lores():
    """
    Low-resolution video streaming endpoint to match detection stream.
    Prefer the streaming service when available; otherwise fallback to direct capture.
    """
    try:
        video_streaming = get_service('video_streaming')
        if video_streaming and hasattr(video_streaming, 'get_frame'):
            logger.info("Using video streaming service for lores video feed")
            return Response(
                _generate_lores_frames_from_service(video_streaming),
                mimetype='multipart/x-mixed-replace; boundary=frame',
                headers={
                    'Cache-Control': 'no-cache',
                    'Expires': '0',
                    'Connection': 'keep-alive',
                    'Transfer-Encoding': 'chunked',
                    'X-Accel-Buffering': 'no',
                    'X-Content-Type-Options': 'nosniff'
                }
            )
        else:
            logger.info("Video streaming service not available, using direct lores generator")
            return Response(
                generate_lores_frames(),
                mimetype='multipart/x-mixed-replace; boundary=frame',
                headers={
                    'Cache-Control': 'no-cache',
                    'Expires': '0',
                    'Connection': 'keep-alive',
                    'Transfer-Encoding': 'chunked',
                    'X-Accel-Buffering': 'no',
                    'X-Content-Type-Options': 'nosniff'
                }
            )
    except Exception as e:
        logger.error(f"Error in video_feed_lores endpoint: {e}")
        return Response(
            _generate_error_stream("Lores video feed error"),
            mimetype='multipart/x-mixed-replace; boundary=frame',
            headers={
                'Cache-Control': 'no-cache',
                'Expires': '0',
                'Connection': 'keep-alive',
                'Transfer-Encoding': 'chunked',
                'X-Accel-Buffering': 'no',
                'X-Content-Type-Options': 'nosniff'
            }
        )

def _generate_lores_frames_from_service(video_streaming):
    """
    Generate lores frames using video streaming service with fallback.
    
    Args:
        video_streaming: Video streaming service instance
        
    Yields:
        bytes: Frame data in multipart format
    """
    consecutive_errors = 0
    max_errors = 5
    error_delay = 1.0
    
    try:
        # Start streaming if not already started
        if not video_streaming.streaming:
            video_streaming.start_streaming()
            time.sleep(0.5)  # Wait for streaming to start
        
        while True:
            try:
                # Get frame from service
                frame_data = video_streaming.get_frame(timeout=2.0)
                
                if frame_data and 'frame' in frame_data:
                    # Decode base64 frame
                    import base64
                    frame_bytes = base64.b64decode(frame_data['frame'])
                    
                    # Reset error counter on success
                    consecutive_errors = 0
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    consecutive_errors += 1
                    if consecutive_errors > max_errors:
                        yield _generate_error_placeholder("No lores frame data from streaming service")
                        time.sleep(error_delay)
                    else:
                        time.sleep(0.1)
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error getting lores frame from streaming service: {e}")
                
                if consecutive_errors > max_errors:
                    yield _generate_error_placeholder("Lores streaming service error")
                    time.sleep(error_delay)
                else:
                    time.sleep(0.1)
                    
    except Exception as e:
        logger.error(f"Critical error in _generate_lores_frames_from_service: {e}")
        yield _generate_error_placeholder(f"Critical lores streaming service error")


@camera_bp.route('/ml_frame')
def get_ml_frame():
    """
    Get ML-optimized frame for AI processing.
    
    Returns:
        dict: JSON response with frame data
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager or not camera_manager.camera_handler:
            return jsonify({'error': 'Camera manager or handler not available'}), 500
        
        camera_handler = camera_manager.camera_handler
        frame_data = camera_handler.capture_ml_frame()
        
        if frame_data and 'main_frame' in frame_data:
            main_frame = frame_data['main_frame']
            if main_frame is not None:
                # Convert to base64 for JSON response
                ret, buffer = cv2.imencode('.jpg', main_frame)
                if ret:
                    import base64
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')
                    return jsonify({
                        'success': True,
                        'frame': frame_base64,
                        'metadata': frame_data.get('metadata', {}),
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to encode frame',
                        'timestamp': datetime.now().isoformat()
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': 'Empty frame received',
                    'timestamp': datetime.now().isoformat()
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'No frame data available',
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        logger.error(f"Error getting ML frame: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


def register_camera_events(socketio):
    """
    Register WebSocket events for camera functionality with improved stability.
    
    Args:
        socketio: Flask-SocketIO instance
    """
    logger.info("Registering camera WebSocket events with improved stability")
    
    @socketio.on('connect')
    def handle_camera_connect():
        """Handle browser connection to camera WebSocket with improved error handling and navigation detection."""
        try:
            session_id = request.sid
            logger.info(f"New WebSocket connection: {session_id}")
            
            # Get comprehensive browser information for fingerprinting
            browser_info = {
                'user_agent': request.headers.get('User-Agent', 'Unknown')[:100],  # Limit length
                'ip_address': request.remote_addr,
                'accept_language': request.headers.get('Accept-Language', 'Unknown'),
                'accept_encoding': request.headers.get('Accept-Encoding', 'Unknown'),
                'accept': request.headers.get('Accept', 'Unknown'),
                'connected_at': datetime.now().isoformat()
            }
            
            # Track browser connection (non-blocking) with navigation detection
            try:
                browser_manager = get_service('browser_connection_manager')
                if browser_manager:
                    # Use threading to avoid blocking
                    import threading
                    def track_connection():
                        try:
                            success = browser_manager.on_browser_connect(session_id, browser_info)
                            if success:
                                logger.debug(f"Browser connection tracked: {session_id}")
                            else:
                                logger.warning(f"Failed to track browser connection: {session_id}")
                        except Exception as e:
                            logger.error(f"Error tracking browser connection: {e}")
                    
                    thread = threading.Thread(target=track_connection, daemon=True)
                    thread.start()
            except Exception as e:
                logger.warning(f"Browser connection tracking failed: {e}")
            
            # Send connection confirmation immediately
            emit('camera_connected', {
                'success': True,
                'message': 'Connected to camera WebSocket',
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"WebSocket connection established: {session_id}")
            
        except Exception as e:
            logger.error(f"Critical error in camera connect handler: {e}")
            try:
                emit('camera_connected', {
                    'success': False,
                    'error': 'Connection error',
                    'timestamp': datetime.now().isoformat()
                })
            except:
                pass  # Don't let emit errors crash the handler
    
    @socketio.on('disconnect')
    def handle_camera_disconnect():
        """Handle browser disconnection with improved error handling."""
        try:
            session_id = request.sid
            logger.info(f"WebSocket disconnection: {session_id}")
            
            # Track browser disconnection (non-blocking)
            try:
                browser_manager = get_service('browser_connection_manager')
                if browser_manager:
                    # Use threading to avoid blocking
                    import threading
                    def track_disconnection():
                        try:
                            success = browser_manager.on_browser_disconnect(session_id)
                            if success:
                                logger.debug(f"Browser disconnection tracked: {session_id}")
                            else:
                                logger.warning(f"Failed to track browser disconnection: {session_id}")
                        except Exception as e:
                            logger.error(f"Error tracking browser disconnection: {e}")
                    
                    thread = threading.Thread(target=track_disconnection, daemon=True)
                    thread.start()
            except Exception as e:
                logger.warning(f"Browser disconnection tracking failed: {e}")
            
        except Exception as e:
            logger.error(f"Error in camera disconnect handler: {e}")
    
    @socketio.on('camera_status_request')
    def handle_camera_status_request():
        """Handle camera status request with improved error handling."""
        try:
            session_id = request.sid
            
            # Update activity for this connection (non-blocking)
            try:
                browser_manager = get_service('browser_connection_manager')
                if browser_manager:
                    # Use threading to avoid blocking
                    import threading
                    def update_activity():
                        try:
                            browser_manager.update_activity(session_id)
                        except Exception as e:
                            logger.debug(f"Activity update failed: {e}")
                    
                    thread = threading.Thread(target=update_activity, daemon=True)
                    thread.start()
            except Exception as e:
                logger.debug(f"Activity tracking failed: {e}")
            
            # Get camera status
            camera_manager = get_service('camera_manager')
            if not camera_manager:
                emit('camera_status_update', {
                    'success': False,
                    'error': 'Camera manager not available',
                    'timestamp': datetime.now().isoformat()
                })
                return
            
            status = camera_manager.get_status()
            serializable_status = make_json_serializable(status)
            
            emit('camera_status_update', {
                'success': True,
                'status': serializable_status,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error handling camera status request: {e}")
            emit('camera_status_update', {
                'success': False,
                'error': 'Status request failed',
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio.on('camera_control')
    def handle_camera_control(data):
        """Handle camera control requests with connection tracking."""
        try:
            session_id = request.sid
            
            # Update activity for this connection
            browser_manager = get_service('browser_connection_manager')
            if browser_manager:
                browser_manager.update_activity(session_id)
            
            # Get camera manager
            camera_manager = get_service('camera_manager')
            if not camera_manager:
                emit('camera_control_response', {
                    'success': False,
                    'error': 'Camera manager not available',
                    'timestamp': datetime.now().isoformat()
                })
                return
            
            # Handle control commands
            command = data.get('command', '').lower()
            
            if command == 'start':
                success = camera_manager.start_camera()
                message = 'Camera started successfully' if success else 'Failed to start camera'
            elif command == 'stop':
                success = camera_manager.stop_camera()
                message = 'Camera stopped successfully' if success else 'Failed to stop camera'
            elif command == 'restart':
                success = camera_manager.restart_camera()
                message = 'Camera restarted successfully' if success else 'Failed to restart camera'
            else:
                success = False
                message = f'Unknown command: {command}'
            
            emit('camera_control_response', {
                'success': success,
                'message': message,
                'command': command,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error handling camera control: {e}")
            emit('camera_control_response', {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio.on('camera_config_update')
    def handle_camera_config_update(data):
        """Handle camera configuration updates with connection tracking."""
        try:
            session_id = request.sid
            
            # Update activity for this connection
            browser_manager = get_service('browser_connection_manager')
            if browser_manager:
                browser_manager.update_activity(session_id)
            
            # Get camera manager
            camera_manager = get_service('camera_manager')
            if not camera_manager:
                emit('camera_config_response', {
                    'success': False,
                    'error': 'Camera manager not available',
                    'timestamp': datetime.now().isoformat()
                })
                return
            
            # Update configuration
            config = data.get('config', {})
            success = camera_manager.update_configuration(config)
            
            if success:
                # Get updated configuration
                current_config = camera_manager.get_configuration()
                emit('camera_config_response', {
                    'success': True,
                    'message': 'Configuration updated successfully',
                    'config': current_config,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                emit('camera_config_response', {
                    'success': False,
                    'error': 'Failed to update configuration',
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Error handling camera config update: {e}")
            emit('camera_config_response', {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio.on('browser_activity')
    def handle_browser_activity(data):
        """Handle browser activity updates (optional tracking)."""
        try:
            session_id = request.sid
            
            # Update activity for this connection (optional)
            try:
                browser_manager = get_service('browser_connection_manager')
                if browser_manager:
                    browser_manager.update_activity(session_id)
                    
                    # Send connection status if requested
                    if data.get('request_status', False):
                        status = browser_manager.get_connection_status()
                        emit('browser_connection_status', {
                            'success': True,
                            'status': status,
                            'timestamp': datetime.now().isoformat()
                        })
            except Exception as e:
                logger.debug(f"Browser activity tracking failed: {e}")
            
        except Exception as e:
            logger.error(f"Error handling browser activity: {e}")
    
    logger.info("Browser connection tracking added (optional)")


@camera_bp.route('/debug')
def camera_debug():
    """
    Debug endpoint to check camera status and frame capture.
    
    Returns:
        dict: JSON response with debug information
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            return jsonify({'error': 'Camera manager not available'}), 500
        
        camera_handler = camera_manager.camera_handler
        if not camera_handler:
            return jsonify({'error': 'Camera handler not available'}), 500
        
        # Get camera status from both manager and handler
        manager_status = camera_manager.get_status()
        handler_status = camera_handler.get_camera_status()
        handler_config = camera_handler.get_configuration()
        
        # Test frame capture
        test_frame = None
        frame_shape = None
        frame_error = None
        
        try:
            test_frame = camera_handler.capture_frame()
            if test_frame and 'frame' in test_frame:
                frame_shape = test_frame['frame'].shape if test_frame['frame'] is not None else None
        except Exception as e:
            frame_error = str(e)
        
        debug_info = {
            'manager_status': manager_status,
            'handler_status': handler_status,
            'handler_config': handler_config,
            'frame_capture_success': test_frame is not None,
            'frame_shape': frame_shape,
            'frame_error': frame_error,
            'camera_initialized': handler_status.get('initialized', False),
            'camera_streaming': handler_status.get('streaming', False),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'debug': debug_info
        })
        
    except Exception as e:
        logger.error(f"Error in camera debug: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/metadata')
def camera_metadata():
    """
    Camera metadata viewer page.
    
    Returns:
        str: Rendered metadata template
    """
    return render_template('camera/metadata.html')


@camera_bp.route('/debug_metadata')
def debug_camera_metadata():
    """
    ข้อมูล debug metadata ของกล้อง
    
    Returns:
        dict: JSON response with debug information
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            return jsonify({
                'success': False,
                'error': 'Camera manager not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        camera_handler = camera_manager.camera_handler
        if not camera_handler:
            return jsonify({
                'success': False,
                'error': 'Camera handler not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get debug information from camera handler using unified method
        frame_result = camera_handler.capture_frame(source="buffer", stream_type="main", include_metadata=True)
        debug_info = frame_result.get('metadata', {}) if frame_result else {}
        
        # Add camera status information for debug display
        camera_status = camera_handler.get_camera_status()
        debug_info.update({
            'camera_initialized': camera_status.get('initialized', False),
            'camera_streaming': camera_status.get('streaming', False),
            'picam2_exists': camera_status.get('camera_ready', False),
            'picam2_started': camera_status.get('streaming', False),
            'success': True
        })
        
        return jsonify({
            'success': True,
            'debug_info': debug_info,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in debug metadata: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/api/metadata')
def get_camera_metadata_api():
    """
    API endpoint สำหรับ metadata ของกล้อง
    
    Returns:
        dict: JSON response with camera metadata
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            return jsonify({
                'success': False,
                'error': 'Camera manager not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get comprehensive camera status and metadata
        camera_status = camera_manager.get_status()
        
        # Prepare metadata for API response
        metadata_response = {
            'success': True,
            'camera_status': camera_status,
            'camera_properties': camera_status.get('camera_handler', {}).get('camera_properties', {}),
            'current_config': camera_status.get('camera_handler', {}).get('current_config', {}),
            'camera_controls': camera_status.get('camera_handler', {}).get('configuration', {}).get('controls', {}),
            'frame_metadata': camera_status.get('metadata', {}),
            'frame_statistics': {
                'frame_count': camera_status.get('frame_count', 0),
                'average_fps': camera_status.get('average_fps', 0.0),
                'last_frame_time': camera_status.get('timestamp', 'N/A')
            },
            'available_modes': camera_status.get('camera_handler', {}).get('sensor_modes', []),
            'sensor_modes_count': camera_status.get('camera_handler', {}).get('sensor_modes_count', 0),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(metadata_response)
        
    except Exception as e:
        logger.error(f"Error getting camera metadata API: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/api/experimental_metadata')
def get_experimental_metadata():
    """
    API endpoint สำหรับ comprehensive experimental metadata ของกล้อง
    
    Returns:
        dict: JSON response with comprehensive experimental metadata
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            return jsonify({
                'success': False,
                'error': 'Camera manager not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        camera_handler = camera_manager.camera_handler
        if not camera_handler:
            return jsonify({
                'success': False,
                'error': 'Camera handler not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get comprehensive experimental metadata using unified capture_frame method
        frame_result = camera_handler.capture_frame(source="buffer", stream_type="main", include_metadata=True)
        comprehensive_metadata = frame_result.get('metadata', {}) if frame_result else {}
        
        if comprehensive_metadata is None:
            return jsonify({
                'success': False,
                'error': 'Failed to capture comprehensive metadata',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        return jsonify({
            'success': True,
            'experimental_metadata': comprehensive_metadata,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting experimental metadata: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/api/metadata_summary')
def get_metadata_summary():
    """
    API endpoint สำหรับ metadata summary สำหรับ experimental efficiency
    
    Returns:
        dict: JSON response with metadata summary
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            return jsonify({
                'success': False,
                'error': 'Camera manager not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        camera_handler = camera_manager.camera_handler
        if not camera_handler:
            return jsonify({
                'success': False,
                'error': 'Camera handler not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get comprehensive metadata using unified capture_frame method
        frame_result = camera_handler.capture_frame(source="buffer", stream_type="main", include_metadata=True)
        comprehensive_metadata = frame_result.get('metadata', {}) if frame_result else {}
        
        if comprehensive_metadata is None:
            return jsonify({
                'success': False,
                'error': 'Failed to capture metadata',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Create summary for experimental efficiency
        metadata_summary = {
            'camera_status': {
                'initialized': camera_handler.initialized,
                'streaming': camera_handler.streaming,
                'frame_count': camera_handler.frame_count,
                'average_fps': camera_handler.average_fps
            },
            'image_quality': {
                'exposure_adequacy': comprehensive_metadata.get('experimental', {}).get('exposure_adequacy', 'unknown'),
                'focus_quality': comprehensive_metadata.get('experimental', {}).get('focus_quality', 'unknown'),
                'lighting_condition': comprehensive_metadata.get('experimental', {}).get('lighting_condition', 'unknown'),
                'noise_level': comprehensive_metadata.get('experimental', {}).get('noise_level', 'unknown'),
                'dynamic_range_utilization': comprehensive_metadata.get('experimental', {}).get('dynamic_range_utilization', 0)
            },
            'performance_metrics': {
                'buffer_ready': comprehensive_metadata.get('performance', {}).get('buffer_ready', False),
                'buffer_latency_ms': comprehensive_metadata.get('performance', {}).get('buffer_latency', 0),
                'capture_thread_active': comprehensive_metadata.get('performance', {}).get('capture_thread_active', False),
                'actual_framerate': comprehensive_metadata.get('configuration', {}).get('framerate', 0)
            },
            'camera_settings': {
                'resolution': comprehensive_metadata.get('configuration', {}).get('resolution', [0, 0]),
                'exposure_time_ms': comprehensive_metadata.get('exposure', {}).get('exposure_time_ms', 0),
                'total_gain': comprehensive_metadata.get('exposure', {}).get('total_gain', 1.0),
                'color_temperature': comprehensive_metadata.get('color', {}).get('color_temperature', 5500),
                'focus_distance': comprehensive_metadata.get('focus', {}).get('focus_distance', 0)
            },
            'experimental_indicators': {
                'image_stability': comprehensive_metadata.get('experimental', {}).get('image_stability', 0),
                'signal_to_noise_db': comprehensive_metadata.get('quality', {}).get('signal_to_noise', 0),
                'dynamic_range_stops': comprehensive_metadata.get('quality', {}).get('dynamic_range', 0),
                'focus_confidence': comprehensive_metadata.get('focus', {}).get('focus_confidence', 0)
            }
        }
        
        return jsonify({
            'success': True,
            'metadata_summary': metadata_summary,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting metadata summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/test')
def test_camera():
    """
    ทดสอบการทำงานของกล้อง
    
    Returns:
        dict: JSON response with test results
    """
    try:
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            return jsonify({
                'success': False,
                'error': 'Camera manager not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        camera_handler = camera_manager.camera_handler
        if not camera_handler:
            return jsonify({
                'success': False,
                'error': 'Camera handler not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get camera status
        camera_status = camera_manager.get_status()
        
        test_results = {
            'handler_initialized': camera_handler.initialized,
            'handler_streaming': camera_handler.streaming,
            'manager_initialized': camera_status.get('initialized', False),
            'manager_streaming': camera_status.get('streaming', False),
            'auto_start_enabled': camera_status.get('auto_start_enabled', False),
            'uptime': camera_status.get('uptime', 0),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'test_results': test_results
        })
        
    except Exception as e:
        logger.error(f"Error in camera test: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/video_test')
def video_test():
    """
    Video streaming test endpoint for end-to-end testing.
    
    Returns:
        dict: JSON response with test results
    """
    try:
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'overall_status': 'unknown'
        }
        
        # Test 1: Camera Manager Availability
        try:
            camera_manager = get_service('camera_manager')
            test_results['tests']['camera_manager'] = {
                'status': 'passed' if camera_manager else 'failed',
                'message': 'Camera manager available' if camera_manager else 'Camera manager not available'
            }
        except Exception as e:
            test_results['tests']['camera_manager'] = {
                'status': 'error',
                'message': f'Camera manager error: {str(e)}'
            }
        
        # Test 2: Camera Handler Status
        try:
            if camera_manager and camera_manager.camera_handler:
                camera_status = camera_manager.camera_handler.get_camera_status()
                test_results['tests']['camera_handler'] = {
                    'status': 'passed' if camera_status.get('initialized', False) else 'failed',
                    'message': f"Camera initialized: {camera_status.get('initialized', False)}, Streaming: {camera_status.get('streaming', False)}",
                    'details': camera_status
                }
            else:
                test_results['tests']['camera_handler'] = {
                    'status': 'failed',
                    'message': 'Camera handler not available'
                }
        except Exception as e:
            test_results['tests']['camera_handler'] = {
                'status': 'error',
                'message': f'Camera handler error: {str(e)}'
            }
        
        # Test 3: Frame Capture
        try:
            if camera_manager:
                frame = camera_manager.camera_handler.capture_frame(source="buffer", stream_type="lores", include_metadata=False)
                test_results['tests']['frame_capture'] = {
                    'status': 'passed' if frame is not None else 'failed',
                    'message': f"Frame captured: {frame is not None}",
                    'frame_shape': frame.shape if frame is not None else None
                }
            else:
                test_results['tests']['frame_capture'] = {
                    'status': 'failed',
                    'message': 'Camera manager not available for frame capture'
                }
        except Exception as e:
            test_results['tests']['frame_capture'] = {
                'status': 'error',
                'message': f'Frame capture error: {str(e)}'
            }
        
        # Test 4: Video Streaming Service
        try:
            video_streaming = get_service('video_streaming')
            if video_streaming:
                streaming_status = video_streaming.get_status()
                health_status = video_streaming.health_check()
                test_results['tests']['video_streaming'] = {
                    'status': 'passed' if health_status.get('healthy', False) else 'failed',
                    'message': f"Streaming service healthy: {health_status.get('healthy', False)}",
                    'details': {
                        'streaming': streaming_status.get('streaming', False),
                        'fallback_mode': streaming_status.get('fallback_mode', False),
                        'source_distribution': streaming_status.get('source_distribution', {}),
                        'health': health_status
                    }
                }
            else:
                test_results['tests']['video_streaming'] = {
                    'status': 'failed',
                    'message': 'Video streaming service not available'
                }
        except Exception as e:
            test_results['tests']['video_streaming'] = {
                'status': 'error',
                'message': f'Video streaming error: {str(e)}'
            }
        
        # Test 5: Frame Buffer
        try:
            if camera_manager and camera_manager.camera_handler:
                buffer_ready = camera_manager.camera_handler.is_frame_buffer_ready()
                test_results['tests']['frame_buffer'] = {
                    'status': 'passed' if buffer_ready else 'failed',
                    'message': f"Frame buffer ready: {buffer_ready}"
                }
            else:
                test_results['tests']['frame_buffer'] = {
                    'status': 'failed',
                    'message': 'Camera handler not available for buffer test'
                }
        except Exception as e:
            test_results['tests']['frame_buffer'] = {
                'status': 'error',
                'message': f'Frame buffer error: {str(e)}'
            }
        
        # Calculate overall status
        passed_tests = sum(1 for test in test_results['tests'].values() if test['status'] == 'passed')
        total_tests = len(test_results['tests'])
        
        if passed_tests == total_tests:
            test_results['overall_status'] = 'passed'
        elif passed_tests > 0:
            test_results['overall_status'] = 'partial'
        else:
            test_results['overall_status'] = 'failed'
        
        test_results['summary'] = {
            'passed': passed_tests,
            'total': total_tests,
            'success_rate': round(passed_tests / total_tests * 100, 1) if total_tests > 0 else 0
        }
        
        return jsonify({
            'success': True,
            'test_results': test_results
        })
        
    except Exception as e:
        logger.error(f"Error in video test: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'test_results': {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'error',
                'error': str(e)
            }
        }), 500


@camera_bp.route('/video_streaming_status')
def video_streaming_status():
    """
    Get detailed video streaming status with fallback information.
    
    Returns:
        dict: JSON response with streaming status
    """
    try:
        video_streaming = get_service('video_streaming')
        if not video_streaming:
            return jsonify({
                'success': False,
                'error': 'Video streaming service not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        status = video_streaming.get_status()
        health = video_streaming.health_check()
        
        return jsonify({
            'success': True,
            'status': status,
            'health': health,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting video streaming status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/video_streaming_reset', methods=['POST'])
def video_streaming_reset():
    """
    Reset video streaming service fallback mode.
    
    Returns:
        dict: JSON response with reset result
    """
    try:
        video_streaming = get_service('video_streaming')
        if not video_streaming:
            return jsonify({
                'success': False,
                'error': 'Video streaming service not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        success = video_streaming.reset_fallback_mode()
        
        return jsonify({
            'success': success,
            'message': 'Fallback mode reset successfully' if success else 'Failed to reset fallback mode',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error resetting video streaming: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/browser_connections')
def get_browser_connections():
    """
    Get browser connection status and statistics.
    
    Returns:
        dict: JSON response with browser connection information
    """
    try:
        browser_manager = get_service('browser_connection_manager')
        if not browser_manager:
            return jsonify({
                'success': False,
                'error': 'Browser connection manager not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        status = browser_manager.get_connection_status()
        
        return jsonify({
            'success': True,
            'status': status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting browser connections: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/browser_connections/clear', methods=['POST'])
def clear_browser_connections():
    """
    Clear all browser connections (for debugging/testing).
    
    Returns:
        dict: JSON response with clear result
    """
    try:
        browser_manager = get_service('browser_connection_manager')
        if not browser_manager:
            return jsonify({
                'success': False,
                'error': 'Browser connection manager not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Clear connections
        with browser_manager.lock:
            cleared_count = len(browser_manager.active_connections)
            browser_manager.active_connections.clear()
            browser_manager.current_connections = 0
        
        return jsonify({
            'success': True,
            'message': f'Cleared {cleared_count} browser connections',
            'cleared_count': cleared_count,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error clearing browser connections: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@camera_bp.route('/video_feed/health')
def video_feed_health():
    """
    Health check endpoint for video feed to help debug issues.
    
    Returns:
        JSON response with video feed health status
    """
    try:
        video_streaming = get_service('video_streaming')
        if not video_streaming:
            return jsonify({
                'success': False,
                'error': 'Video streaming service not available',
                'timestamp': datetime.now().isoformat()
            })
        
        # Get video streaming service status
        status = video_streaming.get_status()
        
        # Check if frames are being generated
        frame_queue_size = status.get('queue_size', 0)
        frames_processed = status.get('frames_processed', 0)
        streaming = status.get('streaming', False)
        
        # Health indicators
        health_status = 'healthy'
        if frame_queue_size == 0 and frames_processed == 0:
            health_status = 'no_frames'
        elif not streaming:
            health_status = 'not_streaming'
        elif frame_queue_size < 2:
            health_status = 'low_frames'
        
        return jsonify({
            'success': True,
            'health_status': health_status,
            'video_streaming_status': status,
            'timestamp': datetime.now().isoformat(),
            'recommendations': {
                'no_frames': 'Check camera manager and frame capture',
                'not_streaming': 'Start video streaming service',
                'low_frames': 'Monitor frame generation rate',
                'healthy': 'Video feed should work normally'
            }
        })
        
    except Exception as e:
        logger.error(f"Error in video feed health check: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })


@camera_bp.route('/video_feed/debug')
def video_feed_debug():
    """
    Debug endpoint for video feed to get detailed information.
    
    Returns:
        JSON response with debug information
    """
    try:
        video_streaming = get_service('video_streaming')
        camera_manager = get_service('camera_manager')
        
        debug_info = {
            'timestamp': datetime.now().isoformat(),
            'video_streaming_service': {
                'available': video_streaming is not None,
                'streaming': video_streaming.streaming if video_streaming else False,
                'frame_queue_size': video_streaming.frame_queue.qsize() if video_streaming else 0,
                'error_count': video_streaming.error_count if video_streaming else 0,
                'fallback_mode': video_streaming.fallback_mode if video_streaming else False,
            } if video_streaming else None,
            'camera_manager': {
                'available': camera_manager is not None,
                'status': camera_manager.get_status() if camera_manager else None,
            } if camera_manager else None,
            'system_info': {
                'python_version': sys.version,
                'opencv_version': cv2.__version__ if 'cv2' in sys.modules else 'Not available',
                'numpy_version': np.__version__ if 'numpy' in sys.modules else 'Not available',
            }
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        logger.error(f"Error in video feed debug: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

def _generate_fallback_stream():
    """
    Generate a fallback stream with test pattern when video streaming service is not available.
    
    Yields:
        bytes: Test pattern frames in multipart format
    """
    logger.info("Generating fallback stream with test pattern")
    
    try:
        # Generate a simple test pattern
        test_frame = _generate_test_pattern_frame()
        
        while True:
            # Send test frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + test_frame + b'\r\n')
            
            # Wait before sending next frame
            time.sleep(0.1)  # 10 FPS
            
    except Exception as e:
        logger.error(f"Error in fallback stream: {e}")
        # Generate error frame
        error_frame = _generate_error_frame("Fallback stream error")
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')

def _generate_test_pattern_frame():
    """
    Generate a test pattern frame for fallback stream.
    
    Returns:
        bytes: JPEG test pattern frame
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Create test pattern image
        img = Image.new('RGB', (640, 480), color='blue')
        draw = ImageDraw.Draw(img)
        
        # Add test pattern
        for i in range(0, 640, 40):
            for j in range(0, 480, 40):
                color = 'red' if (i + j) % 80 == 0 else 'green'
                draw.rectangle([i, j, i + 39, j + 39], fill=color)
        
        # Add text
        try:
            # Try to load a font
            font = ImageFont.load_default()
            draw.text((320, 240), "TEST PATTERN", fill='white', font=font, anchor='mm')
            draw.text((320, 260), "Video Service Unavailable", fill='yellow', font=font, anchor='mm')
        except:
            # If font loading fails, just draw rectangles
            pass
        
        # Convert to JPEG
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG', quality=85)
        return img_io.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating test pattern frame: {e}")
        # Return minimal JPEG data
        return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'