#!/usr/bin/env python3
"""
Improved Application Architecture for Camera Detection System

This design addresses:
1. Prevents multiple camera initialization 
2. Enables camera and detection to run simultaneously even when user exits browser
3. Proper health checking without disrupting camera operations
4. Robust singleton pattern for camera management
5. State persistence across browser sessions
"""

import os
import threading
import queue
import time
import signal
import sys
from datetime import datetime
from flask import Flask, render_template, Response, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit
import asyncio
import logging
import json
from pathlib import Path

# Import configuration and modules
from config import (
    FLASK_HOST, FLASK_PORT, DEFAULT_RESOLUTION, DEFAULT_FRAMERATE,
    DEFAULT_BRIGHTNESS, DEFAULT_CONTRAST, DEFAULT_SATURATION,
    DEFAULT_SHARPNESS, DEFAULT_AWB_MODE, HEALTH_CHECK_INTERVAL,
    SECRET_KEY, BASE_DIR
)

class ApplicationState:
    """Manages application state persistence across browser sessions"""
    
    def __init__(self, state_file="app_state.json"):
        self.state_file = Path(BASE_DIR) / state_file
        self.state = {
            "camera_initialized": False,
            "detection_running": False,
            "health_monitor_running": False,
            "websocket_running": False,
            "last_camera_settings": {
                "resolution": DEFAULT_RESOLUTION,
                "framerate": DEFAULT_FRAMERATE,
                "brightness": DEFAULT_BRIGHTNESS,
                "contrast": DEFAULT_CONTRAST,
                "saturation": DEFAULT_SATURATION,
                "sharpness": DEFAULT_SHARPNESS,
                "awb_mode": DEFAULT_AWB_MODE
            },
            "startup_time": None,
            "last_health_check": None
        }
        self.lock = threading.Lock()
        self.load_state()
    
    def load_state(self):
        """Load state from file if exists"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    saved_state = json.load(f)
                    self.state.update(saved_state)
                logging.info(f"Loaded application state from {self.state_file}")
        except Exception as e:
            logging.warning(f"Could not load state file: {e}, using defaults")
    
    def save_state(self):
        """Save current state to file"""
        try:
            with self.lock:
                with open(self.state_file, 'w') as f:
                    json.dump(self.state, f, indent=2, default=str)
                logging.debug("Application state saved")
        except Exception as e:
            logging.error(f"Could not save state: {e}")
    
    def update_state(self, **kwargs):
        """Update state and save to file"""
        with self.lock:
            self.state.update(kwargs)
            self.save_state()
    
    def get_state(self, key=None):
        """Get state value or entire state"""
        with self.lock:
            return self.state.get(key) if key else self.state.copy()

class ImprovedCameraManager:
    """
    Singleton Camera Manager with robust initialization control
    Prevents multiple initialization and provides thread-safe access
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.picam2 = None
        self.is_camera_initialized = False
        self.camera_lock = threading.RLock()  # Re-entrant lock
        self.frames_queue = queue.Queue(maxsize=10)
        self.metadata_queue = queue.Queue(maxsize=1)
        self.current_settings = {}
        self.streaming_active = False
        self.stream_thread = None
        self.initialization_count = 0
        self._initialized = True
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def initialize_camera_once(self, **camera_settings):
        """
        Initialize camera only if not already initialized
        Thread-safe initialization with proper error handling
        """
        with self.camera_lock:
            self.initialization_count += 1
            self.logger.info(f"Camera initialization attempt #{self.initialization_count}")
            
            if self.is_camera_initialized and self.picam2:
                self.logger.info("Camera already initialized, skipping re-initialization")
                return True
                
            try:
                # Close any existing camera instance
                if self.picam2:
                    self._close_camera_internal()
                    
                from picamera2 import Picamera2
                self.picam2 = Picamera2()
                
                # Configure camera with provided settings
                resolution = camera_settings.get('resolution', DEFAULT_RESOLUTION)
                main_config = {"size": resolution}
                lores_config = {"size": (640, 480)}
                
                config = self.picam2.create_video_configuration(
                    main=main_config, 
                    lores=lores_config, 
                    encode="lores"
                )
                self.picam2.configure(config)
                
                # Apply camera controls
                self._apply_camera_controls(**camera_settings)
                
                # Start camera
                self.picam2.start()
                self.is_camera_initialized = True
                self.current_settings = camera_settings.copy()
                
                self.logger.info(f"Camera successfully initialized with settings: {camera_settings}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to initialize camera: {e}")
                self.is_camera_initialized = False
                self.picam2 = None
                return False
    
    def _apply_camera_controls(self, **settings):
        """Apply camera control settings"""
        if not self.picam2:
            return
            
        try:
            controls = {}
            if 'brightness' in settings:
                controls["Brightness"] = settings['brightness']
            if 'contrast' in settings:
                controls["Contrast"] = settings['contrast']
            if 'saturation' in settings:
                controls["Saturation"] = settings['saturation']
            if 'sharpness' in settings:
                controls["Sharpness"] = settings['sharpness']
                
            if controls:
                self.picam2.set_controls(controls)
                
        except Exception as e:
            self.logger.error(f"Error applying camera controls: {e}")
    
    def start_streaming(self):
        """Start camera streaming in a separate thread"""
        with self.camera_lock:
            if not self.is_camera_initialized:
                self.logger.error("Cannot start streaming: camera not initialized")
                return False
                
            if self.streaming_active:
                self.logger.info("Streaming already active")
                return True
                
            self.streaming_active = True
            self.stream_thread = threading.Thread(target=self._stream_frames, daemon=True)
            self.stream_thread.start()
            self.logger.info("Camera streaming started")
            return True
    
    def _stream_frames(self):
        """Internal method to continuously capture and queue frames"""
        self.logger.info("Frame streaming thread started")
        
        while self.streaming_active:
            try:
                if not self.is_camera_initialized or not self.picam2:
                    time.sleep(0.1)
                    continue
                    
                # Capture frame and metadata
                request = self.picam2.capture_request()
                frame = request.make_array('main')
                metadata = request.get_metadata()
                request.release()
                
                # Add to queues (non-blocking)
                try:
                    if not self.frames_queue.full():
                        self.frames_queue.put_nowait(frame)
                    else:
                        # Remove old frame and add new one
                        try:
                            self.frames_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self.frames_queue.put_nowait(frame)
                    
                    # Update metadata queue
                    try:
                        self.metadata_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.metadata_queue.put_nowait(metadata)
                    
                except queue.Full:
                    pass  # Skip if queues are full
                    
                time.sleep(0.03)  # ~30 FPS
                
            except Exception as e:
                self.logger.error(f"Error in frame streaming: {e}")
                time.sleep(1)
                
        self.logger.info("Frame streaming thread stopped")
    
    def get_frame(self, timeout=1.0):
        """Get latest frame from queue"""
        try:
            return self.frames_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_metadata(self, timeout=0.1):
        """Get latest metadata from queue"""
        try:
            return self.metadata_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def generate_video_stream(self):
        """Generate video stream for Flask Response"""
        import cv2
        
        while self.streaming_active:
            frame = self.get_frame(timeout=1.0)
            if frame is not None:
                try:
                    # Encode frame as JPEG
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = buffer.tobytes()
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                           
                except Exception as e:
                    self.logger.error(f"Error encoding frame: {e}")
                    continue
            else:
                time.sleep(0.1)
    
    def health_check(self):
        """Perform health check without disrupting streaming"""
        with self.camera_lock:
            try:
                if self.is_camera_initialized and self.picam2 and hasattr(self.picam2, 'started'):
                    if self.picam2.started:
                        return True, "Camera initialized and streaming"
                    else:
                        return False, "Camera initialized but not started"
                else:
                    return False, "Camera not initialized"
            except Exception as e:
                return False, f"Camera health check failed: {e}"
    
    def stop_streaming(self):
        """Stop camera streaming"""
        self.streaming_active = False
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=5)
        self.logger.info("Camera streaming stopped")
    
    def _close_camera_internal(self):
        """Internal method to close camera resources"""
        if self.picam2:
            try:
                if hasattr(self.picam2, 'started') and self.picam2.started:
                    self.picam2.stop()
                self.picam2.close()
                self.logger.info("Camera resources released")
            except Exception as e:
                self.logger.error(f"Error closing camera: {e}")
            finally:
                self.picam2 = None
                self.is_camera_initialized = False
    
    def shutdown(self):
        """Graceful shutdown of camera manager"""
        self.logger.info("Shutting down camera manager")
        self.stop_streaming()
        with self.camera_lock:
            self._close_camera_internal()

class ServiceManager:
    """
    Manages all background services with proper lifecycle control
    Ensures services continue running even when browser is disconnected
    """
    
    def __init__(self, app_state, camera_manager):
        self.app_state = app_state
        self.camera_manager = camera_manager
        self.services = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Service control
        self.running = True
        self.service_lock = threading.Lock()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_all_services()
        sys.exit(0)
    
    def start_detection_service(self):
        """Start detection service"""
        if 'detection' in self.services and self.services['detection'].is_alive():
            self.logger.info("Detection service already running")
            return True
            
        try:
            detection_thread = threading.Thread(
                target=self._detection_worker,
                name="DetectionService",
                daemon=False  # Not daemon - should persist
            )
            detection_thread.start()
            
            with self.service_lock:
                self.services['detection'] = detection_thread
                
            self.app_state.update_state(detection_running=True)
            self.logger.info("Detection service started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start detection service: {e}")
            return False
    
    def _detection_worker(self):
        """Detection service worker"""
        self.logger.info("Detection worker started")
        
        # Initialize detection models here
        # detection_processor = DetectionProcessor()
        
        while self.running:
            try:
                frame = self.camera_manager.get_frame(timeout=1.0)
                if frame is not None:
                    # Perform detection on frame
                    # results = detection_processor.process_frame(frame)
                    # Save results to database
                    pass
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error in detection worker: {e}")
                time.sleep(1)
        
        self.logger.info("Detection worker stopped")
    
    def start_health_monitor_service(self):
        """Start health monitoring service"""
        if 'health_monitor' in self.services and self.services['health_monitor'].is_alive():
            self.logger.info("Health monitor service already running")
            return True
            
        try:
            health_thread = threading.Thread(
                target=self._health_monitor_worker,
                name="HealthMonitorService",
                daemon=False
            )
            health_thread.start()
            
            with self.service_lock:
                self.services['health_monitor'] = health_thread
                
            self.app_state.update_state(health_monitor_running=True)
            self.logger.info("Health monitor service started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start health monitor service: {e}")
            return False
    
    def _health_monitor_worker(self):
        """Health monitor worker"""
        self.logger.info("Health monitor worker started")
        
        while self.running:
            try:
                self.logger.info("Running system health checks...")
                
                # Check camera health
                camera_ok, camera_msg = self.camera_manager.health_check()
                self.logger.info(f"Camera Health: {'PASS' if camera_ok else 'FAIL'} - {camera_msg}")
                
                # Other health checks would go here
                # - Disk space
                # - Network connectivity
                # - Database connection
                # - Model loading status
                
                self.app_state.update_state(last_health_check=datetime.now().isoformat())
                
                # Sleep for health check interval
                for _ in range(HEALTH_CHECK_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in health monitor: {e}")
                time.sleep(60)  # Wait longer on error
        
        self.logger.info("Health monitor worker stopped")
    
    def start_websocket_service(self):
        """Start WebSocket communication service"""
        if 'websocket' in self.services and self.services['websocket'].is_alive():
            self.logger.info("WebSocket service already running")
            return True
            
        try:
            ws_thread = threading.Thread(
                target=self._websocket_worker,
                name="WebSocketService",
                daemon=False
            )
            ws_thread.start()
            
            with self.service_lock:
                self.services['websocket'] = ws_thread
                
            self.app_state.update_state(websocket_running=True)
            self.logger.info("WebSocket service started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start WebSocket service: {e}")
            return False
    
    def _websocket_worker(self):
        """WebSocket service worker"""
        self.logger.info("WebSocket worker started")
        
        # Initialize WebSocket client
        # websocket_client = WebSocketClient()
        
        while self.running:
            try:
                # Send detection results and health checks to server
                # websocket_client.send_pending_data()
                time.sleep(5)  # Send data every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in WebSocket worker: {e}")
                time.sleep(10)
        
        self.logger.info("WebSocket worker stopped")
    
    def start_all_services(self):
        """Start all background services"""
        self.logger.info("Starting all background services...")
        
        # Start services in order
        services_started = []
        
        if self.start_detection_service():
            services_started.append("detection")
            
        if self.start_health_monitor_service():
            services_started.append("health_monitor")
            
        if self.start_websocket_service():
            services_started.append("websocket")
        
        self.logger.info(f"Started services: {services_started}")
        return len(services_started) > 0
    
    def stop_service(self, service_name):
        """Stop a specific service"""
        with self.service_lock:
            if service_name in self.services:
                thread = self.services[service_name]
                if thread.is_alive():
                    # Signal the thread to stop
                    self.running = False  # This will be handled per-service in future
                    thread.join(timeout=10)
                    if thread.is_alive():
                        self.logger.warning(f"Service {service_name} did not stop gracefully")
                    else:
                        self.logger.info(f"Service {service_name} stopped")
                del self.services[service_name]
    
    def shutdown_all_services(self):
        """Shutdown all services gracefully"""
        self.logger.info("Shutting down all services...")
        self.running = False
        
        with self.service_lock:
            for service_name, thread in self.services.items():
                if thread.is_alive():
                    self.logger.info(f"Stopping {service_name} service...")
                    thread.join(timeout=10)
                    if thread.is_alive():
                        self.logger.warning(f"Service {service_name} did not stop gracefully")
        
        self.services.clear()
        self.app_state.update_state(
            detection_running=False,
            health_monitor_running=False,
            websocket_running=False
        )
        self.logger.info("All services shutdown complete")

class ImprovedFlaskApp:
    """
    Improved Flask application with persistent background services
    """
    
    def __init__(self):
        # Initialize core components
        self.app_state = ApplicationState()
        self.camera_manager = ImprovedCameraManager()
        self.service_manager = ServiceManager(self.app_state, self.camera_manager)
        
        # Initialize Flask app
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = SECRET_KEY
        self.socketio = SocketIO(self.app)
        
        # Setup routes
        self._setup_routes()
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            state = self.app_state.get_state()
            return render_template('index.html', 
                                 app_state=state,
                                 camera_settings=state['last_camera_settings'])
        
        @self.app.route('/video_feed')
        def video_feed():
            return Response(self.camera_manager.generate_video_stream(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/api/status')
        def api_status():
            camera_ok, camera_msg = self.camera_manager.health_check()
            state = self.app_state.get_state()
            
            return jsonify({
                'camera_status': camera_ok,
                'camera_message': camera_msg,
                'services_running': {
                    'detection': state.get('detection_running', False),
                    'health_monitor': state.get('health_monitor_running', False),
                    'websocket': state.get('websocket_running', False)
                },
                'uptime': state.get('startup_time'),
                'last_health_check': state.get('last_health_check')
            })
        
        @self.app.route('/api/start_services', methods=['POST'])
        def start_services():
            if self.service_manager.start_all_services():
                return jsonify({'status': 'success', 'message': 'Services started'})
            else:
                return jsonify({'status': 'error', 'message': 'Failed to start services'})
        
        @self.app.route('/api/stop_services', methods=['POST'])
        def stop_services():
            self.service_manager.shutdown_all_services()
            return jsonify({'status': 'success', 'message': 'Services stopped'})
    
    def startup(self):
        """Application startup sequence"""
        self.logger.info("Starting improved application...")
        
        # Update startup time
        self.app_state.update_state(startup_time=datetime.now().isoformat())
        
        # Initialize camera with last known settings
        camera_settings = self.app_state.get_state('last_camera_settings')
        if self.camera_manager.initialize_camera_once(**camera_settings):
            self.app_state.update_state(camera_initialized=True)
            
            # Start camera streaming
            self.camera_manager.start_streaming()
            
            # Start background services
            self.service_manager.start_all_services()
            
            self.logger.info("Application startup complete")
            return True
        else:
            self.logger.error("Failed to initialize camera during startup")
            return False
    
    def shutdown(self):
        """Application shutdown sequence"""
        self.logger.info("Shutting down application...")
        
        # Stop all services
        self.service_manager.shutdown_all_services()
        
        # Shutdown camera
        self.camera_manager.shutdown()
        
        # Update state
        self.app_state.update_state(
            camera_initialized=False,
            detection_running=False,
            health_monitor_running=False,
            websocket_running=False
        )
        
        self.logger.info("Application shutdown complete")
    
    def run(self):
        """Run the Flask application"""
        if self.startup():
            try:
                self.socketio.run(self.app, host=FLASK_HOST, port=FLASK_PORT, debug=False)
            finally:
                self.shutdown()
        else:
            self.logger.error("Failed to start application")

# Main execution
if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run improved application
    improved_app = ImprovedFlaskApp()
    improved_app.run()