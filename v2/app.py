import os
import threading
import queue
import time
from datetime import datetime
from flask import Flask, render_template, Response, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit # emit สำหรับการส่งข้อมูลไปยัง client
import asyncio # For running async websocket client in a thread
import logging

# Import our custom modules
from config import (
    FLASK_HOST, FLASK_PORT, DEFAULT_RESOLUTION, DEFAULT_FRAMERATE,
    DEFAULT_BRIGHTNESS, DEFAULT_CONTRAST, DEFAULT_SATURATION,
    DEFAULT_SHARPNESS,  DEFAULT_AWB_MODE,
    HEALTH_CHECK_INTERVAL,SECRET_KEY, BASE_DIR
    
)

from camera_handler import CameraHandler
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
# ใช้ Queue สำหรับสื่อสารระหว่าง CameraHandler และ DetectionProcessor
frames_queue = queue.Queue(maxsize=10)
metadata_queue = queue.Queue(maxsize=1) # ใช้สำหรับเก็บ metadata ของเฟรมล่าสุด
# ใช้สำหรับป้องกันการเข้าถึงฐานข้อมูลพร้อมกัน
db_lock = threading.Lock()

# Custom Jinja2 filter for datetime formatting
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    """Format a datetime object to a string."""
    if isinstance(value, str):
        # Assuming value is in ISO format from database
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value # Return as is if not a valid ISO format string
    return value.strftime(format)

# Initialize our handlers (they use the Singleton pattern, so this gets the single instance)
camera_handler = CameraHandler(frames_queue, metadata_queue)
db_manager = DatabaseManager(db_lock) 
detection_processor = DetectionProcessor(frames_queue)
websocket_client = WebSocketClient()
health_monitor = HealthMonitor(frames_queue, camera_handler)

# Thread objects
detection_thread = None
sender_thread = None
monitor_thread = None
metadata_thread = None
stop_event = threading.Event() # Event to signal threads to stop

# --- Thread Management Functions ---

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
            # ดึง metadata จากคิวด้วย timeout
            metadata = metadata_queue.get(timeout=1)
            # ส่งข้อมูลไปยัง client ผ่าน WebSocket
            socketio.emit('camera_metadata', metadata, broadcast=True)
            metadata_queue.task_done()
        except queue.Empty:
            # คิวว่างก็ให้ทำต่อไปเรื่อยๆ
            continue
        except Exception as e:
            logging.error(f"Error in metadata sender thread: {e}")
            time.sleep(1)

def start_threads():
    """Starts the background detection and sender threads."""
    global detection_thread, sender_thread, monitor_thread,metadata_thread
   
    # Start Metadata Sender Thread
    if metadata_thread and metadata_thread.is_alive():
        logger.info("Metadata sender thread already running.")
    else:
        logger.info("Starting metadata sender thread...")
        metadata_thread = threading.Thread(target=run_metadata_sender, daemon=True)
        metadata_thread.start()
        logger.info("Metadata sender thread started.")

    # Start Detection Thread
    if detection_thread and detection_thread.is_alive():
        logger.info("Detection thread already running.")
    else:
        logger.info("Starting detection thread...")
        last_props = camera_handler.get_latest_camera_properties()
        detection_thread = threading.Thread(target=run_detection_processor, daemon=True)
        detection_thread.start()
        logger.info("Detection thread started.")

    # Start WebSocket sender Thread
    if sender_thread and sender_thread.is_alive():
        logger.info("Sender thread already running.")
    else:
        logger.info("Starting WebSocket sender thread...")
        # Create a new event loop for the async client in this thread
        new_loop = asyncio.new_event_loop()
        sender_thread = threading.Thread(target=run_websocket_client_async_loop, args=(new_loop,), daemon=True)
        sender_thread.start()
        logger.info("WebSocket sender thread started.")

    # Start Health Monitor Thread
    if monitor_thread and monitor_thread.is_alive():
        logger.info("Health monitor thread already running.")
    else:
        logger.info("Starting health monitor thread...")
        monitor_thread = threading.Thread(target=run_health_monitor, daemon=True)
        monitor_thread.start()
        logger.info("Health monitor thread started.")

def stop_threads():
    """Signals background threads to stop and waits for them."""
    logger.info("Signaling background threads to stop...")
    detection_processor.stop()
    health_monitor.stop()
    asyncio.run(websocket_client.stop()) # Await the async stop method
    
    # Give threads a moment to finish, then join them
    if detection_thread and detection_thread.is_alive():
        detection_thread.join(timeout=5) # Wait up to 5 seconds
        if detection_thread.is_alive():
            logger.warning("Detection thread did not terminate gracefully.")
    
    if sender_thread and sender_thread.is_alive():
        sender_thread.join(timeout=5) # Wait up to 5 seconds
        if sender_thread.is_alive():
            logger.warning("Sender thread did not terminate gracefully.")

    if monitor_thread and monitor_thread.is_alive():
        monitor_thread.join(timeout=5)
        if monitor_thread.is_alive():
            logger.warning("Health monitor thread did not terminate gracefully.")
            
    logger.info("Background threads stopped.")
    camera_handler.close_camera()
    db_manager.close_connection()


# --- Flask Routes ---

@app.route('/')
def index():
    """Home page with camera preview and settings form."""
    current_properties = camera_handler.get_latest_camera_properties()
    if not current_properties:
        # If camera hasn't been initialized yet, use defaults from config
        current_properties = {
            'resolution': DEFAULT_RESOLUTION,
            'framerate': DEFAULT_FRAMERATE,
            'brightness': DEFAULT_BRIGHTNESS,
            'contrast': DEFAULT_CONTRAST,
            'saturation': DEFAULT_SATURATION,
            'sharpness': DEFAULT_SHARPNESS,
            'awb_mode': DEFAULT_AWB_MODE
        }

    #Get latest health checks
    latest_health_checks = db_manager.get_latest_health_checks(limit=10)

    # Options for dropdowns
    exposure_modes = ['auto', 'normal', 'long', 'verylong', 'custom']
    awb_modes = ['auto', 'fluorescent', 'incandescent', 'tungsten', 'flash', 'horizon', 'daylight', 'cloudy', 'shade', 'custom']

    return render_template('index.html',
                           current_properties=current_properties,
                           exposure_modes=exposure_modes,
                           awb_modes=awb_modes,
                           latest_health_checks=latest_health_checks)

@app.route('/video_feed')
def video_feed():
    """Route to stream camera video feed."""
    return Response(camera_handler.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/update_camera_settings', methods=['POST'])
def update_camera_settings():
    """Handles submission of camera settings form."""
    try:
        resolution_str = request.form.get('resolution', f"{DEFAULT_RESOLUTION[0]}x{DEFAULT_RESOLUTION[1]}")
        resolution = tuple(map(int, resolution_str.split('x')))
        framerate = int(request.form.get('framerate', DEFAULT_FRAMERATE))
        brightness = float(request.form.get('brightness', DEFAULT_BRIGHTNESS))
        contrast = float(request.form.get('contrast', DEFAULT_CONTRAST))
        saturation = float(request.form.get('saturation', DEFAULT_SATURATION))
        sharpness = float(request.form.get('sharpness', DEFAULT_SHARPNESS))
        awb_mode = request.form.get('awb_mode', DEFAULT_AWB_MODE)

        # Stop existing threads and re-initialize camera
        stop_threads() # This will also close camera
        logger.info("Camera settings updated. Re-initializing camera and restarting app...")
        
        camera_handler.initialize_camera(
            resolution=resolution,
            framerate=framerate,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            sharpness=sharpness,
            awb_mode=awb_mode
        )
        
        # Restart threads
        start_threads()

        flash('Camera settings updated successfully and application restarted!', 'success')
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
    Stops all background threads, closes the camera, and returns a JSON response.
    """
    try:
        logger.info("Received request to close camera. Stopping all services.")
        
        # หยุดการทำงานของทุก thread และคืนทรัพยากรกล้อง
        stop_threads()
        camera_handler.close_camera()
        time.sleep(1)  # ให้เวลาสำหรับการปิดกล้อง
        # ล้างคิวเฟรมเพื่อให้แน่ใจว่าไม่มีงานค้าง
        while not frames_queue.empty():
            frames_queue.get()
        
        # ส่งสถานะกลับไปให้เบราวเซอร์
        return jsonify({'status': 'success', 'message': 'Camera closed successfully.'})
    except Exception as e:
        logger.error(f"Failed to close camera: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/shutdown_system', methods=['POST'])
def shutdown_system():
    """
    Gracefully shuts down the entire system and stops all services.
    """
    try:
        logger.info("🛑 Received request to shutdown system. Stopping all services...")
        
        # Stop all background threads
        stop_threads()
        
        # Close camera
        camera_handler.close_camera()
        
        # Clear queues
        while not frames_queue.empty():
            frames_queue.get()
        while not metadata_queue.empty():
            metadata_queue.get()
        
        # Close database connection
        db_manager.close_connection()
        
        logger.info("✅ System shutdown complete")
        
        return jsonify({
            'status': 'success', 
            'message': 'System shutdown successfully. All services stopped and resources released.'
        })
    except Exception as e:
        logger.error(f"Failed to shutdown system: {e}")
        return jsonify({'status': 'error', 'message': str(e)})
    
# --- Application Startup and Shutdown ---

def startup():
    """Initialize camera and start threads immediately on app start."""
    logger.info("Setting up application: Initializing camera and starting background threads.")
    # 1. Initialize camera with default settings or last saved if any (CameraHandler will manage this)
    if not camera_handler.is_initialized:
        camera_handler.initialize_camera(
            resolution=DEFAULT_RESOLUTION,
            framerate=DEFAULT_FRAMERATE,
            brightness=DEFAULT_BRIGHTNESS,
            contrast=DEFAULT_CONTRAST,
            saturation=DEFAULT_SATURATION,
            sharpness=DEFAULT_SHARPNESS,
            awb_mode=DEFAULT_AWB_MODE
        )
    # 2. Run health check
    health_monitor.run_all_checks()
    # 3. Start threads 
    start_threads()
    # Startup sequence following lines 1233-1228 (reverse order)
    logger.info("🎉 Application startup complete - Auto-start enabled:")
    logger.info("   5. ✅ WebSocket sender active")
    logger.info("   4. ✅ Health monitoring active")
    logger.info("   3. ✅ Detection active")
    logger.info("   2. ✅ Camera initialization and streaming")
    logger.info("   1. ✅ Database initialized")

@app.teardown_appcontext
def shutdown_application(exception=None):
    """Gracefully shuts down resources when Flask app context ends."""
    logger.info("Tearing down application: Stopping background threads and closing resources.")
    stop_threads()
    logger.info("Application teardown complete.")

# --- Run the Flask App ---
if __name__ == '__main__':
    startup()  
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=True,use_reloader=False, allow_unsafe_werkzeug=True)