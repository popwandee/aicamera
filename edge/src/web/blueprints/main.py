#!/usr/bin/env python3
"""
Main Blueprint for AI Camera v2.0.0

This blueprint handles the main dashboard and system overview.
"""

from flask import Blueprint, render_template, redirect
from flask_socketio import emit
import time
from edge.src.core.dependency_container import get_service
from edge.src.core.utils.logging_config import get_logger

main_bp = Blueprint('main', __name__)
logger = get_logger(__name__)


@main_bp.route('/')
def index():
    """Main dashboard page."""
    try:
        camera_manager = get_service('camera_manager')
        camera_status = camera_manager.get_status() if camera_manager else {}
        
        response = render_template('index.html', 
                             camera_status=camera_status,
                             title="AI Camera Dashboard",
                             use_socketio=True,
                             timestamp=int(time.time()))
        return response
    except KeyError as e:
        logger.error(f"Service not Registered: {e}")
        response = render_template('index.html', 
                             camera_status={'error': f'Camera service not available: {e}'},
                             title="AI Camera Dashboard",
                             use_socketio=True,
                             timestamp=int(time.time()))
        return response
    except Exception as e:
        logger.error(f"Error in main index: {e}")
        response = render_template('index.html', 
                             camera_status={'error': str(e)},
                             title="AI Camera Dashboard",
                             use_socketio=True,
                             timestamp=int(time.time()))
        return response


@main_bp.route('/websocket_sender')
def redirect_websocket_sender():
    """Redirect to WebSocket Sender dashboard (path /websocket-sender/)."""
    return redirect('/websocket-sender/')


@main_bp.route('/mqtt_service')
def redirect_mqtt_service():
    """Redirect to MQTT Service dashboard (path /mqtt-service/)."""
    return redirect('/mqtt-service/')


def register_main_events(socketio):
    """Register WebSocket events for main functionality."""
    
    @socketio.on('main_status_request')
    def handle_main_status_request():
        """Handle main status request from client."""
        try:
            camera_manager = get_service('camera_manager')
            status = camera_manager.get_status() if camera_manager else {}
            
            emit('main_status_update', {
                'status': 'ok',
                'camera': status,
                'message': 'System status retrieved successfully'
            })
        except KeyError as e:
            logger.error(f"Service not registered: {e}")
            emit('main_status_update', {
                'status': 'error',
                'error': 'Camera service not available',
                'message': 'Failed to get system status'
            })
        except Exception as e:
            logger.error(f"Error handling main status request: {e}")
            emit('main_status_update', {
                'status': 'error',
                'error': str(e),
                'message': 'Failed to get system status'
            })
