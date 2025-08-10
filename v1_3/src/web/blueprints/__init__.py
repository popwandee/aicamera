#!/usr/bin/env python3
"""
Enhanced Web Blueprints Module for AI Camera v1.3

This module contains all Flask blueprints for the application.
Each blueprint handles a specific area of functionality using absolute imports.

Blueprints:
- main: Main dashboard and system overview
- camera: Camera operations and management
- detection: AI detection operations
- detection_results: Detection results viewing with pagination and filtering
- streaming: Video streaming functionality
- health: System health monitoring
- websocket: WebSocket communication
- websocket_sender: WebSocket sender management and server communication

Author: AI Camera Team
Version: 1.3
Date: August 7, 2025
"""

from flask import Flask
from flask_socketio import SocketIO

# Import blueprints using absolute paths
from v1_3.src.web.blueprints.main import main_bp, register_main_events
from v1_3.src.web.blueprints.camera import camera_bp, register_camera_events
from v1_3.src.web.blueprints.health import health_bp, register_health_events
from v1_3.src.web.blueprints.streaming import streaming_bp
from v1_3.src.web.blueprints.detection import detection_bp, register_detection_events
from v1_3.src.web.blueprints.detection_results import detection_results_bp
from v1_3.src.web.blueprints.websocket import websocket_bp
from v1_3.src.web.blueprints.websocket_sender import websocket_sender_bp, register_websocket_sender_events


def register_blueprints(app: Flask, socketio: SocketIO):
    """
    Register all Flask blueprints with the application.
    
    Args:
        app: Flask application instance
        socketio: Flask-SocketIO instance
    """
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(streaming_bp)
    app.register_blueprint(detection_bp)
    app.register_blueprint(detection_results_bp)
    app.register_blueprint(websocket_bp)
    app.register_blueprint(websocket_sender_bp)
    
    # Register WebSocket events
    register_main_events(socketio)
    register_camera_events(socketio)
    register_detection_events(socketio)
    register_health_events(socketio)
    register_websocket_sender_events(socketio)
    # register_streaming_events(socketio)