#!/usr/bin/env python3
"""
WebSocket Blueprint for AI Camera v2.0.0

This blueprint provides WebSocket functionality for real-time communication.
This blueprint handles general WebSocket communication functionality using absolute imports
and dependency injection pattern.

Author: AI Camera Team
Version: 2.0
Date: August 8, 2025
"""

from flask import Blueprint, render_template, jsonify, request
from flask_socketio import emit, join_room, leave_room
from datetime import datetime

# Use absolute imports
from edge.src.core.dependency_container import get_service
from edge.src.core.utils.logging_config import get_logger
from edge.src.core.config import MAIN_RESOLUTION, LORES_RESOLUTION

# Create blueprint
websocket_bp = Blueprint('websocket', __name__, url_prefix='/websocket')
logger = get_logger(__name__)


@websocket_bp.route('/')
def websocket_dashboard():
    """Render WebSocket dashboard."""
    return render_template('websocket/dashboard.html')


@websocket_bp.route('/status')
def get_websocket_status():
    """Get WebSocket connection status."""
    try:
        # Get status from various services
        camera_manager = get_service('camera_manager')
        detection_manager = get_service('detection_manager')
        health_service = get_service('health_service')
        websocket_sender = get_service('websocket_sender')
        
        status = {
            'camera': camera_manager.get_status() if camera_manager else None,
            'detection': detection_manager.get_status() if detection_manager else None,
            'health': health_service.get_system_health() if health_service else None,
            'websocket_sender': websocket_sender.get_status() if websocket_sender else None
        }
        
        return jsonify({
            'success': True,
            'status': status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# WebSocket Sender Routes
@websocket_bp.route('/sender/status')
def websocket_sender_status():
    """Get WebSocket sender status."""
    try:
        websocket_sender = get_service('websocket_sender')
        if websocket_sender:
            status = websocket_sender.get_status()
            return jsonify({
                'success': True,
                'status': status
            })
        else:
            return jsonify({
                'success': True,
                'status': {
                    'connected': False,
                    'running': False,
                    'enabled': False,
                    'server_url': 'Not configured',
                    'retry_count': 0,
                    'aicamera_id': 'Not configured',
                    'checkpoint_id': 'Not configured',
                    'total_detections_sent': 0,
                    'total_health_sent': 0
                }
            })
    except Exception as e:
        logger.error(f"Error getting WebSocket sender status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@websocket_bp.route('/sender/logs')
def websocket_sender_logs():
    """Get WebSocket sender logs."""
    try:
        websocket_sender = get_service('websocket_sender')
        if websocket_sender:
            logs = websocket_sender.get_logs(limit=20)
            return jsonify({
                'success': True,
                'logs': logs,
                'total_logs': len(logs)
            })
        else:
            # Return empty logs if service not available
            return jsonify({
                'success': True,
                'logs': [],
                'total_logs': 0
            })
    except Exception as e:
        logger.error(f"Error getting WebSocket sender logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@websocket_bp.route('/sender/start', methods=['POST'])
def websocket_sender_start():
    """Start WebSocket sender."""
    try:
        websocket_sender = get_service('websocket_sender')
        if websocket_sender:
            success = websocket_sender.start()
            return jsonify({
                'success': success,
                'message': 'WebSocket sender started successfully' if success else 'Failed to start WebSocket sender'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'WebSocket sender service not available'
            })
    except Exception as e:
        logger.error(f"Error starting WebSocket sender: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@websocket_bp.route('/sender/stop', methods=['POST'])
def websocket_sender_stop():
    """Stop WebSocket sender."""
    try:
        websocket_sender = get_service('websocket_sender')
        if websocket_sender:
            success = websocket_sender.stop()
            return jsonify({
                'success': success,
                'message': 'WebSocket sender stopped successfully' if success else 'Failed to stop WebSocket sender'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'WebSocket sender service not available'
            })
    except Exception as e:
        logger.error(f"Error stopping WebSocket sender: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@websocket_bp.route('/sender/connection-test', methods=['POST'])
def websocket_sender_connection_test():
    """Test WebSocket connection."""
    try:
        websocket_sender = get_service('websocket_sender')
        if websocket_sender:
            success = websocket_sender.test_connection()
            return jsonify({
                'success': success,
                'message': 'Connection test successful' if success else 'Connection test failed'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'WebSocket sender service not available'
            })
    except Exception as e:
        logger.error(f"Error testing WebSocket connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@websocket_bp.route('/streaming/status')
def streaming_status():
    """Get streaming status."""
    try:
        camera_manager = get_service('camera_manager')
        if camera_manager:
            status = camera_manager.get_status()
            return jsonify({
                'success': True,
                'status': {
                    'active': status.get('streaming', False),
                    'streaming': status.get('streaming', False),
                    'fps': status.get('config', {}).get('framerate', 30),
                    'resolution': status.get('config', {}).get('resolution', LORES_RESOLUTION)
                }
            })
        else:
            return jsonify({
                'success': True,
                'status': {
                    'active': False,
                    'streaming': False,
                    'fps': 30,
                    'resolution': LORES_RESOLUTION
                }
            })
    except Exception as e:
        logger.error(f"Error getting streaming status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def register_websocket_events(socketio):
    """Register WebSocket events for general WebSocket functionality."""

    # dashboard.js connects to the /dashboard namespace for real-time updates.
    # Without this handler Engine.IO rejects the namespace with "Unable to connect",
    # which logs Session is disconnected errors on every startup.
    @socketio.on('connect', namespace='/dashboard')
    def handle_dashboard_connect():
        emit('connection_response', {
            'success': True,
            'message': 'Connected to AI Camera dashboard',
        }, namespace='/dashboard')

    @socketio.on('join_dashboard_room', namespace='/dashboard')
    def handle_join_dashboard_room():
        from flask_socketio import join_room
        join_room('dashboard')
        emit('dashboard_room_joined', {'success': True}, namespace='/dashboard')

    @socketio.on('websocket_status_request')
    def handle_websocket_status_request():
        """Handle WebSocket status request from client."""
        try:
            # Get status from various services
            camera_manager = get_service('camera_manager')
            detection_manager = get_service('detection_manager')
            health_service = get_service('health_service')
            websocket_sender = get_service('websocket_sender')
            
            status = {
                'camera': camera_manager.get_status() if camera_manager else None,
                'detection': detection_manager.get_status() if detection_manager else None,
                'health': health_service.get_system_health() if health_service else None,
                'websocket_sender': websocket_sender.get_status() if websocket_sender else None
            }
            
            emit('websocket_status_update', status)
        except Exception as e:
            logger.error(f"Error handling WebSocket status request: {e}")
            emit('websocket_status_update', {
                'error': str(e)
            })
    
    @socketio.on('system_status_request')
    def handle_system_status_request():
        """Handle system-wide status request."""
        try:
            # Get comprehensive system status
            camera_manager = get_service('camera_manager')
            detection_manager = get_service('detection_manager')
            health_service = get_service('health_service')
            websocket_sender = get_service('websocket_sender')
            
            system_status = {
                'camera': {
                    'status': camera_manager.get_status() if camera_manager else None,
                    'component': 'Camera Manager'
                },
                'detection': {
                    'status': detection_manager.get_status() if detection_manager else None,
                    'component': 'Detection Manager'
                },
                'health': {
                    'status': health_service.get_system_health() if health_service else None,
                    'component': 'Health Service'
                },
                'websocket_sender': {
                    'status': websocket_sender.get_status() if websocket_sender else None,
                    'component': 'WebSocket Sender'
                }
            }
            
            emit('system_status_update', system_status)
        except Exception as e:
            logger.error(f"Error handling system status request: {e}")
            emit('system_status_update', {
                'error': str(e)
            })
    
    @socketio.on('join_system_room')
    def handle_join_system_room():
        """Join system room for real-time updates."""
        join_room('system')
        emit('system_room_joined', {
            'success': True,
            'message': 'Joined system room'
        })
    
    @socketio.on('leave_system_room')
    def handle_leave_system_room():
        """Leave system room."""
        leave_room('system')
        emit('system_room_left', {
            'success': True,
            'message': 'Left system room'
        })
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info(f"Client connected: {request.sid}")
        emit('connection_response', {
            'success': True,
            'message': 'Connected to AI Camera v2.0.0 WebSocket',
            'timestamp': datetime.now().isoformat()
        })
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info(f"Client disconnected: {request.sid}")
    
    @socketio.on('ping')
    def handle_ping():
        """Handle ping request."""
        emit('pong', {
            'timestamp': datetime.now().isoformat()
        })
