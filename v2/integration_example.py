#!/usr/bin/env python3
"""
Integration Example: How to modify existing v2/app.py to use ImprovedCameraManager

This example shows the minimal changes needed to integrate the improved camera manager
with the existing v2 codebase while maintaining backward compatibility.
"""

import os
import threading
import queue
import time
from datetime import datetime
from flask import Flask, render_template, Response, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit
import asyncio
import logging

# Original imports
from config import (
    FLASK_HOST, FLASK_PORT, DEFAULT_RESOLUTION, DEFAULT_FRAMERATE,
    DEFAULT_BRIGHTNESS, DEFAULT_CONTRAST, DEFAULT_SATURATION,
    DEFAULT_SHARPNESS, DEFAULT_AWB_MODE, HEALTH_CHECK_INTERVAL,
    SECRET_KEY, BASE_DIR
)

# Replace the original camera_handler import with improved version
# from camera_handler import CameraHandler  # OLD
from improved_camera_manager import get_camera_manager, ensure_camera_initialized, ensure_camera_streaming, get_camera_health  # NEW

from detection_processor import DetectionProcessor
from database_manager import DatabaseManager
from websocket_client import WebSocketClient
from health_monitor import HealthMonitor
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app)

# --- MODIFIED INITIALIZATION ---
# OLD: Complex queue and handler initialization
# frames_queue = queue.Queue(maxsize=10)
# metadata_queue = queue.Queue(maxsize=1)
# camera_handler = CameraHandler(frames_queue, metadata_queue)

# NEW: Simplified singleton-based initialization
frames_queue = queue.Queue(maxsize=10)
metadata_queue = queue.Queue(maxsize=1)
camera_manager = get_camera_manager(frames_queue, metadata_queue)  # Singleton instance

# Other managers remain the same
db_lock = threading.Lock()
db_manager = DatabaseManager(db_lock)
detection_processor = DetectionProcessor(frames_queue)
websocket_client = WebSocketClient()

# Modified health monitor to use improved camera manager
class ImprovedHealthMonitor(HealthMonitor):
    """Health monitor that uses the improved camera manager"""
    
    def check_camera(self):
        """Use improved camera manager's health check"""
        component = "Camera"
        try:
            camera_ok, camera_msg = get_camera_health()
            status = "PASS" if camera_ok else "FAIL"
            self._log_result(component, status, camera_msg)
            return camera_ok
        except Exception as e:
            self._log_result(component, "FAIL", f"Camera check failed: {e}")
            return False

health_monitor = ImprovedHealthMonitor(frames_queue, camera_manager)

# Thread objects
detection_thread = None
sender_thread = None
monitor_thread = None
metadata_thread = None
stop_event = threading.Event()

# --- MODIFIED THREAD MANAGEMENT ---

def start_threads():
    """Starts the background detection and sender threads with improved camera handling"""
    global detection_thread, sender_thread, monitor_thread, metadata_thread
    
    logger.info("Starting background threads with improved camera management...")
    
    # NEW: Ensure camera is initialized and streaming BEFORE starting other threads
    default_settings = {
        'resolution': DEFAULT_RESOLUTION,
        'framerate': DEFAULT_FRAMERATE,
        'brightness': DEFAULT_BRIGHTNESS,
        'contrast': DEFAULT_CONTRAST,
        'saturation': DEFAULT_SATURATION,
        'sharpness': DEFAULT_SHARPNESS,
        'awb_mode': DEFAULT_AWB_MODE
    }
    
    if not ensure_camera_initialized(**default_settings):
        logger.error("Failed to initialize camera - cannot start threads")
        return False
    
    if not ensure_camera_streaming():
        logger.error("Failed to start camera streaming - cannot start threads")
        return False
    
    logger.info("Camera initialized and streaming - starting other threads...")
    
    # Start Metadata Sender Thread (unchanged)
    if metadata_thread and metadata_thread.is_alive():
        logger.info("Metadata sender thread already running.")
    else:
        logger.info("Starting metadata sender thread...")
        metadata_thread = threading.Thread(target=run_metadata_sender, daemon=True)
        metadata_thread.start()
        logger.info("Metadata sender thread started.")

    # Start Detection Thread (unchanged)
    if detection_thread and detection_thread.is_alive():
        logger.info("Detection thread already running.")
    else:
        logger.info("Starting detection thread...")
        detection_thread = threading.Thread(target=run_detection_processor, daemon=True)
        detection_thread.start()
        logger.info("Detection thread started.")

    # Start WebSocket sender Thread (unchanged)
    if sender_thread and sender_thread.is_alive():
        logger.info("Sender thread already running.")
    else:
        logger.info("Starting WebSocket sender thread...")
        new_loop = asyncio.new_event_loop()
        sender_thread = threading.Thread(target=run_websocket_client_async_loop, args=(new_loop,), daemon=True)
        sender_thread.start()
        logger.info("WebSocket sender thread started.")

    # Start Health Monitor Thread (unchanged)
    if monitor_thread and monitor_thread.is_alive():
        logger.info("Health monitor thread already running.")
    else:
        logger.info("Starting health monitor thread...")
        monitor_thread = threading.Thread(target=run_health_monitor, daemon=True)
        monitor_thread.start()
        logger.info("Health monitor thread started.")
    
    return True

# Thread worker functions (mostly unchanged)
def run_detection_processor():
    """Function to run the detection processor in a separate thread."""
    detection_processor.run()

def run_websocket_client_async_loop(loop):
    """Function to run the asyncio loop for the WebSocket client in a thread."""
    asyncio.set_event_loop(loop)
    loop.run_until_complete(websocket_client.run())

def run_health_monitor(): 
    """Function to run the health monitor in a separate thread."""
    health_monitor.run()

def run_metadata_sender():
    """Function to read from the metadata queue and emit to all connected clients."""
    while True:
        try:
            metadata = metadata_queue.get(timeout=1)
            socketio.emit('camera_metadata', metadata, broadcast=True)
            metadata_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logging.error(f"Error in metadata sender thread: {e}")
            time.sleep(1)

def stop_threads():
    """Signals background threads to stop and waits for them."""
    logger.info("Signaling background threads to stop...")
    detection_processor.stop()
    health_monitor.stop()
    asyncio.run(websocket_client.stop())
    
    # Join threads with timeout
    for thread_name, thread in [
        ("detection", detection_thread),
        ("sender", sender_thread), 
        ("monitor", monitor_thread)
    ]:
        if thread and thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning(f"{thread_name} thread did not terminate gracefully.")
    
    logger.info("Background threads stopped.")
    
    # NEW: Don't automatically close camera - let it persist
    # camera_handler.close_camera()  # OLD - removed
    # Camera will persist and can be reconnected to
    
    db_manager.close_connection()

# --- MODIFIED FLASK ROUTES ---

@app.route('/')
def index():
    """Home page with camera preview and settings form."""
    # NEW: Get camera properties from improved manager
    camera_stats = camera_manager.get_statistics()
    current_properties = camera_stats.get('current_settings', {})
    
    if not current_properties:
        # Use defaults if no settings available
        current_properties = {
            'resolution': DEFAULT_RESOLUTION,
            'framerate': DEFAULT_FRAMERATE,
            'brightness': DEFAULT_BRIGHTNESS,
            'contrast': DEFAULT_CONTRAST,
            'saturation': DEFAULT_SATURATION,
            'sharpness': DEFAULT_SHARPNESS,
            'awb_mode': DEFAULT_AWB_MODE
        }

    # Get latest health checks
    latest_health_checks = db_manager.get_latest_health_checks(limit=10)

    # Options for dropdowns
    exposure_modes = ['auto', 'normal', 'long', 'verylong', 'custom']
    awb_modes = ['auto', 'fluorescent', 'incandescent', 'tungsten', 'flash', 'horizon', 'daylight', 'cloudy', 'shade', 'custom']

    return render_template('index.html',
                          current_properties=current_properties,
                          exposure_modes=exposure_modes,
                          awb_modes=awb_modes,
                          latest_health_checks=latest_health_checks,
                          camera_stats=camera_stats)  # NEW: Add camera statistics

@app.route('/video_feed')
def video_feed():
    """Route to stream camera video feed."""
    # NEW: Use improved camera manager's stream generator
    return Response(camera_manager.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/camera_status')
def api_camera_status():
    """NEW: API endpoint to get detailed camera status"""
    camera_ok, camera_msg = get_camera_health()
    camera_stats = camera_manager.get_statistics()
    
    return jsonify({
        'health': {
            'status': camera_ok,
            'message': camera_msg
        },
        'statistics': camera_stats
    })

@app.route('/update_camera_settings', methods=['POST'])
def update_camera_settings():
    """Handles submission of camera settings form."""
    try:
        # Parse form data (unchanged)
        resolution_str = request.form.get('resolution', f"{DEFAULT_RESOLUTION[0]}x{DEFAULT_RESOLUTION[1]}")
        resolution = tuple(map(int, resolution_str.split('x')))
        framerate = int(request.form.get('framerate', DEFAULT_FRAMERATE))
        brightness = float(request.form.get('brightness', DEFAULT_BRIGHTNESS))
        contrast = float(request.form.get('contrast', DEFAULT_CONTRAST))
        saturation = float(request.form.get('saturation', DEFAULT_SATURATION))
        sharpness = float(request.form.get('sharpness', DEFAULT_SHARPNESS))
        awb_mode = request.form.get('awb_mode', DEFAULT_AWB_MODE)

        new_settings = {
            'resolution': resolution,
            'framerate': framerate,
            'brightness': brightness,
            'contrast': contrast,
            'saturation': saturation,
            'sharpness': sharpness,
            'awb_mode': awb_mode
        }

        # NEW: Use improved camera manager's restart method
        logger.info(f"Updating camera settings: {new_settings}")
        
        if camera_manager.restart_camera(**new_settings):
            flash('Camera settings updated successfully!', 'success')
            logger.info("Camera settings updated and restarted successfully")
        else:
            flash('Failed to update camera settings', 'danger')
            logger.error("Failed to restart camera with new settings")

    except ValueError as e:
        flash(f'Invalid input for camera settings: {e}', 'danger')
        logger.error(f"Validation error: {e}")
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
        logger.error(f"Error updating camera settings: {e}")
    
    return redirect(url_for('index'))

@app.route('/close_camera', methods=['POST'])
def close_camera():
    """
    NEW: Modified to stop streaming but keep camera available for reconnection
    """
    try:
        logger.info("Received request to stop camera streaming")
        
        # Stop streaming but don't close camera completely
        camera_manager.stop_streaming()
        
        # Clear frame queue
        while not frames_queue.empty():
            try:
                frames_queue.get_nowait()
            except queue.Empty:
                break
        
        return jsonify({'status': 'success', 'message': 'Camera streaming stopped (camera remains available)'})
    except Exception as e:
        logger.error(f"Failed to stop camera streaming: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/start_camera', methods=['POST'])
def start_camera():
    """
    NEW: API endpoint to restart camera streaming
    """
    try:
        logger.info("Received request to start camera streaming")
        
        if ensure_camera_streaming():
            return jsonify({'status': 'success', 'message': 'Camera streaming started'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to start camera streaming'})
    except Exception as e:
        logger.error(f"Failed to start camera streaming: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

# --- MODIFIED APPLICATION STARTUP ---

def startup():
    """Initialize camera and start threads immediately on app start."""
    logger.info("Setting up improved application with persistent camera management...")
    
    # NEW: Initialize camera once with default settings
    default_settings = {
        'resolution': DEFAULT_RESOLUTION,
        'framerate': DEFAULT_FRAMERATE,
        'brightness': DEFAULT_BRIGHTNESS,
        'contrast': DEFAULT_CONTRAST,
        'saturation': DEFAULT_SATURATION,
        'sharpness': DEFAULT_SHARPNESS,
        'awb_mode': DEFAULT_AWB_MODE
    }
    
    if not ensure_camera_initialized(**default_settings):
        logger.error("Failed to initialize camera during startup")
        return False
    
    # Run initial health check
    health_monitor.run_all_checks()
    
    # Load detection models
    detection_processor.load_detection_models()
    
    # Start all threads (this will also start camera streaming)
    if start_threads():
        logger.info("Improved application setup complete")
        return True
    else:
        logger.error("Failed to start application threads")
        return False

@app.teardown_appcontext
def shutdown_application(exception=None):
    """Gracefully shuts down resources when Flask app context ends."""
    logger.info("Tearing down application...")
    stop_threads()
    # NEW: Camera persists even after app shutdown for potential reconnection
    logger.info("Application teardown complete")

# Custom Jinja2 filter (unchanged)
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    """Format a datetime object to a string."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(format)

# --- Run the Flask App ---
if __name__ == '__main__':
    if startup():
        try:
            socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=True, allow_unsafe_werkzeug=True)
        finally:
            # Graceful shutdown
            logger.info("Application shutting down...")
            camera_manager.close_camera()  # Only close on final shutdown
    else:
        logger.error("Failed to start application")

"""
Key Changes Summary:

1. CAMERA INITIALIZATION:
   - OLD: Multiple initialization attempts, potential conflicts
   - NEW: Singleton pattern, initialize once, reuse instance

2. THREADING:
   - OLD: Camera initialized in thread, potential race conditions
   - NEW: Camera initialized before threads start, guaranteed availability

3. HEALTH CHECKING:
   - OLD: Health checks could interfere with camera operations
   - NEW: Non-disruptive health checks using camera manager

4. BROWSER DISCONNECTION:
   - OLD: All services stop when browser closes
   - NEW: Camera and detection continue running, can reconnect

5. STATE MANAGEMENT:
   - OLD: No persistence of camera state
   - NEW: Camera state persisted to file, survives restarts

6. ERROR HANDLING:
   - OLD: Basic error handling
   - NEW: Comprehensive error handling with recovery

To integrate this into your existing v2 codebase:
1. Copy improved_camera_manager.py to v2/
2. Replace camera_handler imports with improved_camera_manager imports
3. Update the initialization and thread management as shown above
4. Test thoroughly with your existing detection logic
"""