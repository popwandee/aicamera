#!/usr/bin/env python3
"""
AI Camera v1.3 Flask Application

Main Flask application that integrates camera services and web interface
using absolute imports and existing blueprint structure.

Author: AI Camera Team
Version: 1.3
Date: August 7, 2025
"""

import os
import sys
from pathlib import Path
from typing import Tuple
from datetime import datetime

from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
import logging

# Import import helper first to setup paths
from v1_3.src.core.utils.import_helper import setup_import_paths, validate_imports
setup_import_paths()

from v1_3.src.core.utils.logging_config import setup_logging, get_logger
from v1_3.src.core.dependency_container import get_container, get_service
from v1_3.src.web.blueprints import register_blueprints
from v1_3.src.core.config import (
    AUTO_START_CAMERA, AUTO_START_DETECTION, AUTO_START_HEALTH_MONITOR, AUTO_START_WEBSOCKET_SENDER,
    STARTUP_DELAY, HEALTH_MONITOR_STARTUP_DELAY, WEBSOCKET_SENDER_STARTUP_DELAY
)


def _initialize_services(logger):
    """
    Initialize services in the correct order with auto-startup sequence.
    
    Sequence:
    1. Initialize camera manager (auto-starts camera if enabled)
    2. Initialize detection manager (auto-starts detection if enabled)
    3. Initialize health monitor (auto-starts monitoring when camera and detection are ready)
    4. Initialize WebSocket sender (auto-starts when health monitor is ready)
    
    Args:
        logger: Logger instance
    """
    logger.info("🚀 Starting service initialization sequence...")
    
    # Step 1: Initialize Camera Manager (will auto-start camera and streaming)
    try:
        logger.info("📸 Step 1: Initializing Camera Manager...")
        camera_manager = get_service('camera_manager')
        if camera_manager:
            success = camera_manager.initialize()
            if success:
                logger.info("✅ Camera Manager initialized successfully")
                if AUTO_START_CAMERA:
                    logger.info("🎥 Camera auto-start enabled - camera should be running")
            else:
                logger.error("❌ Camera Manager initialization failed")
                return False
        else:
            logger.error("❌ Camera Manager service not available")
            return False
    except Exception as e:
        logger.error(f"❌ Error initializing Camera Manager: {e}")
        return False
    
    # Step 2: Initialize Detection Manager (will auto-start detection if enabled)
    try:
        logger.info("🤖 Step 2: Initializing Detection Manager...")
        detection_manager = get_service('detection_manager')
        if detection_manager:
            success = detection_manager.initialize()
            if success:
                logger.info("✅ Detection Manager initialized successfully")
                if AUTO_START_DETECTION:
                    logger.info("🔍 Detection auto-start enabled - detection should be running")
            else:
                logger.error("❌ Detection Manager initialization failed")
                # Don't return False here - camera can work without detection
        else:
            logger.warning("⚠️  Detection Manager service not available")
    except Exception as e:
        logger.error(f"❌ Error initializing Detection Manager: {e}")
        # Don't return False here - camera can work without detection
    
    # Step 3: Initialize Health Monitor and Service (will auto-start monitoring when ready)
    try:
        logger.info("🏥 Step 3: Initializing Health Monitor and Service...")
        
        # Initialize health monitor component
        health_monitor = get_service('health_monitor')
        if health_monitor:
            logger.info("✅ Health Monitor component available")
            if health_monitor.initialize():
                logger.info("✅ Health Monitor component initialized successfully")
            else:
                logger.error("❌ Health Monitor component initialization failed")
        else:
            logger.warning("⚠️  Health Monitor component not available")
        
        # Initialize health service
        health_service = get_service('health_service')
        if health_service:
            logger.info("✅ Health Service available")
            if health_service.initialize():
                logger.info("✅ Health Service initialized successfully")
                
                # Set up auto-start monitoring if enabled
                if AUTO_START_HEALTH_MONITOR:
                    logger.info("🏥 Health Monitor auto-start enabled - will start when camera and detection are ready")
                    # The health service will automatically start monitoring when camera and detection are ready
                else:
                    logger.info("🏥 Health Monitor auto-start disabled")
            else:
                logger.error("❌ Health Service initialization failed")
        else:
            logger.warning("⚠️  Health Service not available")
            
    except Exception as e:
        logger.warning(f"⚠️  Health services initialization: {e}")
    
    # Step 4: Initialize WebSocket Sender (will auto-start when enabled)
    try:
        logger.info("📡 Step 4: Initializing WebSocket Sender...")
        
        websocket_sender = get_service('websocket_sender')
        if websocket_sender:
            logger.info("✅ WebSocket Sender available")
            if websocket_sender.initialize():
                logger.info("✅ WebSocket Sender initialized successfully")
                
                # Set up auto-start if enabled
                if AUTO_START_WEBSOCKET_SENDER:
                    logger.info("📤 WebSocket Sender auto-start enabled - starting service...")
                    # Add delay before starting WebSocket sender
                    import time
                    time.sleep(WEBSOCKET_SENDER_STARTUP_DELAY)
                    
                    if websocket_sender.start():
                        logger.info("✅ WebSocket Sender started successfully")
                    else:
                        logger.error("❌ WebSocket Sender failed to start")
                else:
                    logger.info("📤 WebSocket Sender auto-start disabled")
            else:
                logger.error("❌ WebSocket Sender initialization failed")
        else:
            logger.warning("⚠️  WebSocket Sender service not available")
            
    except Exception as e:
        logger.warning(f"⚠️  WebSocket Sender initialization: {e}")
    
    logger.info("🎉 Service initialization sequence completed!")
    return True


def create_app():
    """Create and configure Flask application using absolute imports."""
    # Setup logging
    logger = setup_logging(level="INFO")
    logger.info("Creating Flask application...")
    
    # Validate imports
    import_errors = validate_imports()
    if import_errors:
        logger.warning("Some imports failed:")
        for error in import_errors:
            logger.warning(f"  {error}")
    
    # Set template and static folders
    current_dir = Path(__file__).parent
    template_dir = current_dir / 'web' / 'templates'
    static_dir = current_dir / 'web' / 'static'

    # Create Flask app
    app = Flask(__name__, 
                template_folder=str(template_dir),
                static_folder=str(static_dir))
    
    # Load configuration using absolute import
    app.config.from_object('v1_3.src.core.config')
    
    # Initialize dependency container
    container = get_container()
    logger.info("Dependency container initialized")
    
    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # Register blueprints using existing structure
    register_blueprints(app, socketio)
    
    # Initialize services with auto-startup sequence
    try:
        _initialize_services(logger)
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        try:
            camera_manager = get_service('camera_manager')
            detection_manager = get_service('detection_manager')
            
            camera_health = camera_manager.health_check() if camera_manager else {}
            detection_health = detection_manager.get_status() if detection_manager else {}
            
            return jsonify({
                'success': True,
                'status': 'healthy',
                'camera': camera_health,
                'detection': detection_health,
                'errors': [],
                'database_errors': [],
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'success': False,
                'status': 'unhealthy',
                'error': str(e),
                'errors': [str(e)],
                'database_errors': [],
                'timestamp': datetime.now().isoformat()
            }), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500
    
    logger.info("Flask application created successfully")
    return app, socketio


def main():
    """Main application entry point."""
    app, socketio = create_app()
    
    # Run the application
    host = app.config.get('FLASK_HOST', '0.0.0.0')
    port = app.config.get('FLASK_PORT', 5000)
    debug = app.config.get('DEBUG', False)
    
    logger = get_logger(__name__)
    logger.info(f"Starting AI Camera application on {host}:{port}")
    
    try:
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        # Cleanup
        try:
            camera_manager = get_service('camera_manager')
            if camera_manager:
                camera_manager.cleanup()
                logger.info("Camera manager cleaned up")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


if __name__ == '__main__':
    main()