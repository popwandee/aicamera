#!/usr/bin/env python3
"""
WebSocket Sender Blueprint for AI Camera v1.3

This blueprint provides WebSocket sender management endpoints and WebSocket events
for server communication status and sending logs.

Author: AI Camera Team
Version: 1.3
Date: December 2024
"""

from flask import Blueprint, render_template, jsonify, request
from flask_socketio import emit, join_room, leave_room
from datetime import datetime
from typing import Dict, Any

from v1_3.src.core.utils.logging_config import get_logger
from v1_3.src.core.dependency_container import get_service

websocket_sender_bp = Blueprint('websocket_sender', __name__, url_prefix='/websocket-sender')
logger = get_logger(__name__)


@websocket_sender_bp.route('/')
def websocket_sender_dashboard():
    """Render WebSocket sender dashboard."""
    try:
        return render_template('websocket_sender/dashboard.html')
    except Exception as e:
        logger.error(f"Error rendering WebSocket sender dashboard: {e}")
        return "WebSocket sender dashboard not available", 500


@websocket_sender_bp.route('')
def websocket_sender_redirect():
    """Redirect /websocket-sender to /websocket-sender/ for dashboard."""
    from flask import redirect, url_for
    return redirect(url_for('websocket_sender.websocket_sender_dashboard'))


@websocket_sender_bp.route('/status')
def get_websocket_sender_status():
    """
    Get WebSocket sender status.
    
    Returns:
        JSON response with WebSocket sender status information
    """
    try:
        websocket_sender = get_service('websocket_sender')
        if not websocket_sender:
            return jsonify({
                'success': False,
                'error': 'WebSocket sender service not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get WebSocket sender status
        status = websocket_sender.get_status()
        
        return jsonify({
            'success': True,
            'status': status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting WebSocket sender status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@websocket_sender_bp.route('/logs')
def get_websocket_sender_logs():
    """
    Get WebSocket sender logs with pagination.
    
    Query Parameters:
        page (optional): Page number (default: 1)
        limit (optional): Records per page (default: 50)
    
    Returns:
        JSON response with WebSocket sender logs
    """
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        # Validate parameters
        page = max(1, page)
        limit = min(max(1, limit), 200)  # Limit maximum records per page
        
        database_manager = get_service('database_manager')
        if not database_manager:
            return jsonify({
                'success': False,
                'error': 'Database manager not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get logs from database
        logs = database_manager.get_websocket_sender_logs(limit=limit)
        
        return jsonify({
            'success': True,
            'logs': logs,
            'page': page,
            'limit': limit,
            'total_logs': len(logs),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting WebSocket sender logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@websocket_sender_bp.route('/start', methods=['POST'])
def start_websocket_sender():
    """
    Start WebSocket sender service.
    
    Returns:
        JSON response with operation result
    """
    try:
        websocket_sender = get_service('websocket_sender')
        if not websocket_sender:
            return jsonify({
                'success': False,
                'error': 'WebSocket sender service not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Start the service
        success = websocket_sender.start()
        
        if success:
            logger.info("WebSocket sender started via web interface")
            return jsonify({
                'success': True,
                'message': 'WebSocket sender started successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start WebSocket sender',
                'timestamp': datetime.now().isoformat()
            }), 500
        
    except Exception as e:
        logger.error(f"Error starting WebSocket sender: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@websocket_sender_bp.route('/stop', methods=['POST'])
def stop_websocket_sender():
    """
    Stop WebSocket sender service.
    
    Returns:
        JSON response with operation result
    """
    try:
        websocket_sender = get_service('websocket_sender')
        if not websocket_sender:
            return jsonify({
                'success': False,
                'error': 'WebSocket sender service not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Stop the service
        websocket_sender.stop()
        logger.info("WebSocket sender stopped via web interface")
        
        return jsonify({
            'success': True,
            'message': 'WebSocket sender stopped successfully',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error stopping WebSocket sender: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@websocket_sender_bp.route('/connection-test', methods=['POST'])
def test_connection():
    """
    Test WebSocket connection to server.
    
    Returns:
        JSON response with connection test result
    """
    try:
        websocket_sender = get_service('websocket_sender')
        if not websocket_sender:
            return jsonify({
                'success': False,
                'error': 'WebSocket sender service not available',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Test connection using asyncio
        import asyncio
        connection_result = asyncio.run(websocket_sender.connect())
        
        if connection_result:
            # Disconnect after test
            await_disconnect = asyncio.run(websocket_sender.disconnect())
            
            return jsonify({
                'success': True,
                'message': 'Connection test successful',
                'server_url': websocket_sender.server_url,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Connection test failed',
                'server_url': websocket_sender.server_url,
                'timestamp': datetime.now().isoformat()
            }), 500
        
    except Exception as e:
        logger.error(f"Error testing WebSocket connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


def register_websocket_sender_events(socketio):
    """Register WebSocket sender related SocketIO events."""
    
    @socketio.on('websocket_sender_status_request')
    def handle_websocket_sender_status_request():
        """Handle WebSocket sender status request."""
        try:
            websocket_sender = get_service('websocket_sender')
            if websocket_sender:
                status = websocket_sender.get_status()
                emit('websocket_sender_status_update', {
                    'success': True,
                    'status': status,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                emit('websocket_sender_status_update', {
                    'success': False,
                    'error': 'WebSocket sender service not available',
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            logger.error(f"Error handling WebSocket sender status request: {e}")
            emit('websocket_sender_status_update', {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio.on('websocket_sender_logs_request')
    def handle_websocket_sender_logs_request(data):
        """Handle WebSocket sender logs request."""
        try:
            limit = data.get('limit', 50) if data else 50
            
            database_manager = get_service('database_manager')
            if database_manager:
                logs = database_manager.get_websocket_sender_logs(limit=limit)
                emit('websocket_sender_logs_update', {
                    'success': True,
                    'logs': logs,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                emit('websocket_sender_logs_update', {
                    'success': False,
                    'error': 'Database manager not available',
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            logger.error(f"Error handling WebSocket sender logs request: {e}")
            emit('websocket_sender_logs_update', {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio.on('websocket_sender_start')
    def handle_websocket_sender_start():
        """Handle WebSocket sender start request."""
        try:
            websocket_sender = get_service('websocket_sender')
            if websocket_sender:
                success = websocket_sender.start()
                emit('websocket_sender_control_response', {
                    'action': 'start',
                    'success': success,
                    'message': 'WebSocket sender started successfully' if success else 'Failed to start WebSocket sender',
                    'timestamp': datetime.now().isoformat()
                })
            else:
                emit('websocket_sender_control_response', {
                    'action': 'start',
                    'success': False,
                    'error': 'WebSocket sender service not available',
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            logger.error(f"Error handling WebSocket sender start: {e}")
            emit('websocket_sender_control_response', {
                'action': 'start',
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio.on('websocket_sender_stop')
    def handle_websocket_sender_stop():
        """Handle WebSocket sender stop request."""
        try:
            websocket_sender = get_service('websocket_sender')
            if websocket_sender:
                websocket_sender.stop()
                emit('websocket_sender_control_response', {
                    'action': 'stop',
                    'success': True,
                    'message': 'WebSocket sender stopped successfully',
                    'timestamp': datetime.now().isoformat()
                })
            else:
                emit('websocket_sender_control_response', {
                    'action': 'stop',
                    'success': False,
                    'error': 'WebSocket sender service not available',
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            logger.error(f"Error handling WebSocket sender stop: {e}")
            emit('websocket_sender_control_response', {
                'action': 'stop',
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio.on('join_websocket_sender_room')
    def handle_join_websocket_sender_room():
        """Handle joining WebSocket sender monitoring room."""
        try:
            join_room('websocket_sender_monitoring')
            emit('websocket_sender_room_joined', {
                'success': True,
                'message': 'Joined WebSocket sender monitoring room',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error joining WebSocket sender room: {e}")
            emit('websocket_sender_room_joined', {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    @socketio.on('leave_websocket_sender_room')
    def handle_leave_websocket_sender_room():
        """Handle leaving WebSocket sender monitoring room."""
        try:
            leave_room('websocket_sender_monitoring')
            emit('websocket_sender_room_left', {
                'success': True,
                'message': 'Left WebSocket sender monitoring room',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error leaving WebSocket sender room: {e}")
            emit('websocket_sender_room_left', {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })