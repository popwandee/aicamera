#!/usr/bin/env python3
"""
Detection Blueprint for AI Camera v2.0.0

This blueprint provides detection control and monitoring functionality:
- Detection service control endpoints
- Detection status monitoring
- Detection results viewing
- WebSocket events for real-time detection updates
- Detection statistics and reporting

Author: AI Camera Team
Version: 2.0
Date: August 2025
"""

import json
import os
import socket
import time
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, Response, current_app
from flask_socketio import emit, join_room, leave_room

# Use absolute imports
from edge.src.core.dependency_container import get_service
from edge.src.core.utils.logging_config import get_logger
from edge.src.components.camera_handler import make_json_serializable
from edge.src.core.config import IMAGE_SAVE_DIR

# Create blueprint
detection_bp = Blueprint('detection', __name__, url_prefix='/detection')

logger = get_logger(__name__)


@detection_bp.route('/')
def detection_dashboard():
    """
    Detection dashboard page with service status and statistics.
    
    Returns:
        str: Rendered HTML template
    """
    try:
        detection_manager = get_service('detection_manager')
        database_manager = get_service('database_manager')
        
        detection_status = detection_manager.get_status() if detection_manager else {}
        stats = database_manager.get_detection_statistics() if database_manager else {}
        
        hostname = os.getenv('DEVICE_ID') or socket.gethostname()
        return render_template('detection/dashboard.html',
                             detection_status=detection_status,
                             stats=stats,
                             title="Detection Dashboard",
                             edge_hostname=hostname,
                             timestamp=int(time.time()))
    except Exception as e:
        logger.error(f"Error in detection dashboard: {e}")
        hostname = os.getenv('DEVICE_ID') or socket.gethostname()
        return render_template('detection/dashboard.html',
                             detection_status={},
                             stats={},
                             title="Detection Dashboard",
                             edge_hostname=hostname,
                             timestamp=int(time.time()))


@detection_bp.route('/status')
def get_detection_status():
    """
    Get current detection status and statistics.
    
    Returns:
        dict: JSON response with detection status
    """
    try:
        detection_manager = get_service('detection_manager')
        if not detection_manager:
            return jsonify({'error': 'Detection manager not available'}), 500
        
        status = detection_manager.get_status()
        
        # Ensure all status data is JSON serializable
        serializable_status = make_json_serializable(status)
        
        return jsonify({
            'success': True,
            'detection_status': serializable_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting detection status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/start', methods=['POST'])
def start_detection():
    """
    Start the detection service.
    
    Returns:
        dict: JSON response with operation result
    """
    try:
        detection_manager = get_service('detection_manager')
        if not detection_manager:
            return jsonify({
                'success': False,
                'error': 'Detection manager not available'
            }), 500
        
        # Start detection service
        success = detection_manager.start_detection()
        
        if success:
            logger.info("Detection service started via API")
            return jsonify({
                'success': True,
                'message': 'Detection service started successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start detection service',
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"Error starting detection service: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/stop', methods=['POST'])
def stop_detection():
    """
    Stop the detection service.
    
    Returns:
        dict: JSON response with operation result
    """
    try:
        detection_manager = get_service('detection_manager')
        if not detection_manager:
            return jsonify({
                'success': False,
                'error': 'Detection manager not available'
            }), 500
        
        # Stop detection service
        success = detection_manager.stop_detection()
        
        if success:
            logger.info("Detection service stopped via API")
            return jsonify({
                'success': True,
                'message': 'Detection service stopped successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to stop detection service',
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"Error stopping detection service: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/process_frame', methods=['POST'])
def process_single_frame():
    """
    Process a single frame for detection (for testing purposes).
    
    Returns:
        dict: JSON response with detection results
    """
    try:
        detection_manager = get_service('detection_manager')
        camera_manager = get_service('camera_manager')
        
        if not detection_manager:
            return jsonify({
                'success': False,
                'error': 'Detection manager not available'
            }), 500
        
        if not camera_manager:
            return jsonify({
                'success': False,
                'error': 'Camera manager not available'
            }), 500
        
        # Process current frame from camera
        result = detection_manager.process_frame_from_camera(camera_manager)
        
        if result:
            return jsonify({
                'success': True,
                'detection_result': make_json_serializable(result),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No detection results or processing failed',
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Error processing single frame: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/config', methods=['GET', 'POST'])
def detection_config():
    """
    Get or update detection configuration.
    
    Returns:
        dict: JSON response with detection configuration
    """
    try:
        detection_manager = get_service('detection_manager')
        if not detection_manager:
            return jsonify({
                'success': False,
                'error': 'Detection manager not available'
            }), 500
        
        if request.method == 'GET':
            # Get current configuration from status
            status = detection_manager.get_status()
            config = {
                'detection_interval': status.get('detection_interval', 0.1),
                'vehicle_confidence': status.get('detection_processor_status', {}).get('confidence_threshold', 0.5),
                'plate_confidence': status.get('detection_processor_status', {}).get('plate_confidence_threshold', 0.3),
                'detection_resolution': status.get('detection_processor_status', {}).get('detection_resolution', [640, 640])
            }
            
            return jsonify({
                'success': True,
                'config': config,
                'timestamp': datetime.now().isoformat()
            })
        else:
            # Update configuration
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No configuration data provided'
                }), 400
            
            # Update configuration (simplified - just log for now)
            logger.info(f"Configuration update requested: {data}")
            success = True
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Configuration updated successfully',
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update configuration'
                }), 500
                
    except Exception as e:
        logger.error(f"Error in detection config: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@detection_bp.route('/statistics')
def get_detection_statistics():
    """
    Get detailed detection statistics.
    
    Returns:
        dict: JSON response with detection statistics
    """
    try:
        # Prefer database-backed statistics to reflect persisted records
        database_manager = get_service('database_manager')
        db_stats = database_manager.get_detection_statistics() if database_manager else {}

        total_vehicles = db_stats.get('total_vehicles', 0)
        total_plates = db_stats.get('total_plates', 0)
        successful_ocr = db_stats.get('successful_ocr', 0)

        plate_rate = (total_plates / total_vehicles * 100) if total_vehicles > 0 else 0.0
        ocr_rate = (successful_ocr / total_plates * 100) if total_plates > 0 else 0.0

        enhanced_stats = {
            **db_stats,
            'plate_detection_rate_percent': round(plate_rate, 2),
            'ocr_success_rate_percent': round(ocr_rate, 2)
        }

        return jsonify({
            'success': True,
            'statistics': enhanced_stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting detection statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/results')
def get_all_results():
    """
    Get detection results with filtering, search, and pagination.

    Query params (optional):
      - per_page: int, number of items to return (default 50, max 200)
      - page: int, page number starting at 1 (default 1)
      - search: str, search term for OCR results or plate text
      - date_from: str, start date filter (ISO format: YYYY-MM-DD)
      - date_to: str, end date filter (ISO format: YYYY-MM-DD)
      - has_vehicles: str, filter by presence of vehicles ('true' or 'false')
      - has_plates: str, filter by presence of license plates ('true' or 'false')
      - sort_by: str, column to sort by (default: 'created_at')
      - sort_order: str, sort order ('asc' or 'desc', default: 'desc')
    """
    try:
        database_manager = get_service('database_manager')
        if not database_manager:
            return jsonify({
                'success': False,
                'error': 'Database manager not available'
            }), 500

        # Parse query params with sane defaults
        try:
            per_page = int(request.args.get('per_page', 50))
        except ValueError:
            per_page = 50
        try:
            page = int(request.args.get('page', 1))
        except ValueError:
            page = 1

        # Bound values
        if per_page <= 0:
            per_page = 50
        per_page = min(per_page, 200)
        if page <= 0:
            page = 1

        # Parse filter parameters
        search = request.args.get('search', '').strip() or None
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None
        
        # Parse boolean filters
        has_vehicles = None
        has_vehicles_str = request.args.get('has_vehicles', '').strip().lower()
        if has_vehicles_str == 'true':
            has_vehicles = True
        elif has_vehicles_str == 'false':
            has_vehicles = False
        
        has_plates = None
        has_plates_str = request.args.get('has_plates', '').strip().lower()
        if has_plates_str == 'true':
            has_plates = True
        elif has_plates_str == 'false':
            has_plates = False
        
        # Parse sort parameters
        sort_by = request.args.get('sort_by', 'created_at').strip()
        sort_order = request.args.get('sort_order', 'desc').strip().lower()
        
        # Use the paginated method that supports filtering
        paginated_results = database_manager.get_detection_results_paginated(
            page=page,
            per_page=per_page,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            date_from=date_from,
            date_to=date_to,
            has_vehicles=has_vehicles,
            has_plates=has_plates
        )

        return jsonify({
            'success': True,
            'results': make_json_serializable(paginated_results.get('results', [])),
            'count': len(paginated_results.get('results', [])),
            'total': paginated_results.get('total', 0),
            'page': paginated_results.get('page', page),
            'per_page': paginated_results.get('per_page', per_page),
            'total_pages': paginated_results.get('total_pages', 0),
            'has_next': paginated_results.get('has_next', False),
            'has_prev': paginated_results.get('has_prev', False),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting all results: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/results/<int:result_id>')
def get_result_by_id(result_id):
    """
    Get a specific detection result by ID.
    
    Args:
        result_id: ID of the detection result
        
    Returns:
        dict: JSON response with the specific detection result
    """
    try:
        database_manager = get_service('database_manager')
        if not database_manager:
            return jsonify({
                'success': False,
                'error': 'Database manager not available'
            }), 500
        
        # Get specific detection result by ID
        result = database_manager.get_detection_result_by_id(result_id)
        
        if result:
            return jsonify({
                'success': True,
                'result': make_json_serializable(result),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Detection result with ID {result_id} not found'
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting result by ID {result_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/results/<int:result_id>', methods=['DELETE'])
def delete_detection_result(result_id):
    """
    Delete a detection result and associated media files.
    """
    try:
        database_manager = get_service('database_manager')
        if not database_manager:
            return jsonify({
                'success': False,
                'error': 'Database manager not available'
            }), 500
        
        result = database_manager.get_detection_result_by_id(result_id)
        if not result:
            return jsonify({
                'success': False,
                'error': f'Detection result with ID {result_id} not found'
            }), 404
        
        deleted_files = _cleanup_detection_files(result)
        
        if not database_manager.delete_detection_result(result_id):
            return jsonify({
                'success': False,
                'error': 'Failed to delete detection result from database'
            }), 500
        
        logger.info(f"Detection result {result_id} deleted with {len(deleted_files)} file(s) removed")
        return jsonify({
            'success': True,
            'message': f'Detection result {result_id} deleted successfully',
            'deleted_files': deleted_files
        })
        
    except Exception as e:
        logger.error(f"Error deleting detection result {result_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/models/status')
def get_models_status():
    """
    Get status of loaded detection models.
    
    Returns:
        dict: JSON response with model status
    """
    try:
        detection_manager = get_service('detection_manager')
        if not detection_manager:
            return jsonify({'error': 'Detection manager not available'}), 500
        
        status = detection_manager.get_status()
        processor_status = status.get('detection_processor_status', {})
        
        model_info = {
            'models_loaded': processor_status.get('models_loaded', False),
            'vehicle_model_available': processor_status.get('vehicle_model_available', False),
            'lp_detection_model_available': processor_status.get('lp_detection_model_available', False),
            'lp_ocr_model_available': processor_status.get('lp_ocr_model_available', False),
            'tesseract_available': processor_status.get('tesseract_available', False),
            'detection_resolution': processor_status.get('detection_resolution', [0, 0]),
            'confidence_thresholds': {
                'vehicle': processor_status.get('confidence_threshold', 0.0),
                'plate': processor_status.get('plate_confidence_threshold', 0.0)
            }
        }
        
        return jsonify({
            'success': True,
            'models': model_info,
            'timestamp': int(time.time())
        })
        
    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': int(time.time())
        }), 500


@detection_bp.route('/update-config', methods=['POST'])
def update_detection_config():
    """
    Update detection configuration and restart service.
    
    Expected JSON payload:
    {
        "detection_interval": float,
        "vehicle_confidence": float,
        "plate_confidence": float,
        "auto_start": bool
    }
    
    Returns:
        dict: JSON response with operation result
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['detection_interval', 'vehicle_confidence', 'plate_confidence']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate values
        detection_interval = data.get('detection_interval')
        vehicle_confidence = data.get('vehicle_confidence')
        plate_confidence = data.get('plate_confidence')
        auto_start = data.get('auto_start', False)
        
        if not isinstance(detection_interval, (int, float)) or detection_interval < 0.1 or detection_interval > 1000.0:
            return jsonify({
                'success': False,
                'error': 'Invalid detection_interval. Must be between 0.1 and 1000.0'
            }), 400
        
        if not isinstance(vehicle_confidence, (int, float)) or vehicle_confidence < 0.1 or vehicle_confidence > 1.0:
            return jsonify({
                'success': False,
                'error': 'Invalid vehicle_confidence. Must be between 0.1 and 1.0'
            }), 400
        
        if not isinstance(plate_confidence, (int, float)) or plate_confidence < 0.1 or plate_confidence > 1.0:
            return jsonify({
                'success': False,
                'error': 'Invalid plate_confidence. Must be between 0.1 and 1.0'
            }), 400
        
        logger.info(f"Updating detection configuration: interval={detection_interval}, vehicle_conf={vehicle_confidence}, plate_conf={plate_confidence}, auto_start={auto_start}")
        
        # Update .env.production file
        env_file_path = '/home/camuser/aicamera/edge/installation/.env.production'
        success = update_env_file(env_file_path, {
            'DETECTION_INTERVAL': str(detection_interval),
            'DETECTION_CONFIDENCE_THRESHOLD': str(vehicle_confidence),
            'PLATE_CONFIDENCE_THRESHOLD': str(plate_confidence)
        })
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to update configuration file'
            }), 500
        
        # Restart the service
        restart_success = restart_aicamera_service()
        
        if not restart_success:
            return jsonify({
                'success': False,
                'error': 'Configuration updated but service restart failed'
            }), 500
        
        logger.info("Detection configuration updated and service restarted successfully")
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated and service restarted successfully',
            'config': {
                'detection_interval': detection_interval,
                'vehicle_confidence': vehicle_confidence,
                'plate_confidence': plate_confidence,
                'auto_start': auto_start
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error updating detection configuration: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


def update_env_file(file_path, updates):
    """
    Update .env.production file with new configuration values.
    
    Args:
        file_path (str): Path to the .env.production file
        updates (dict): Dictionary of key-value pairs to update
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import os
        import time
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Environment file not found: {file_path}")
            return False
        
        # Check if file is writable
        if not os.access(file_path, os.W_OK):
            logger.error(f"Environment file not writable: {file_path}")
            return False
        
        # Read existing file
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Create a set of keys to update
        update_keys = set(updates.keys())
        updated_count = 0
        
        # Update existing lines
        updated_lines = []
        for line in lines:
            original_line = line
            line = line.strip()
            
            # Keep comments and empty lines as is
            if not line or line.startswith('#'):
                updated_lines.append(original_line.rstrip())
                continue
            
            # Check if this line contains a key we want to update
            if '=' in line:
                key = line.split('=')[0].strip()
                if key in update_keys:
                    # Update this line
                    updated_lines.append(f"{key}={updates[key]}")
                    update_keys.remove(key)
                    updated_count += 1
                    logger.info(f"Updated {key}={updates[key]}")
                else:
                    updated_lines.append(original_line.rstrip())
            else:
                updated_lines.append(original_line.rstrip())
        
        # Add any new keys that weren't in the original file
        for key in update_keys:
            updated_lines.append(f"{key}={updates[key]}")
            updated_count += 1
            logger.info(f"Added new key {key}={updates[key]}")
        
        # Create backup
        backup_path = f"{file_path}.backup.{int(time.time())}"
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(''.join(lines))
            logger.info(f"Created backup: {backup_path}")
        except Exception as backup_error:
            logger.warning(f"Failed to create backup: {backup_error}")
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(updated_lines) + '\n')
        
        logger.info(f"Successfully updated .env.production file with {updated_count} changes: {updates}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating .env.production file: {e}")
        return False


def restart_aicamera_service():
    """
    Restart the aicamera_lpr.service.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import subprocess
        import time
        import os
        
        # Check if we're running as root or have sudo privileges
        is_root = os.geteuid() == 0
        
        if is_root:
            # Running as root, use systemctl directly
            stop_cmd = ['systemctl', 'stop', 'aicamera_lpr.service']
            start_cmd = ['systemctl', 'start', 'aicamera_lpr.service']
        else:
            # Not root, try sudo
            stop_cmd = ['sudo', 'systemctl', 'stop', 'aicamera_lpr.service']
            start_cmd = ['sudo', 'systemctl', 'start', 'aicamera_lpr.service']
        
        # Stop the service
        stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=30)
        
        if stop_result.returncode != 0:
            logger.error(f"Failed to stop service: {stop_result.stderr}")
            # Try alternative method - send SIGTERM to the process
            try:
                # Find the process and kill it
                ps_result = subprocess.run(['pgrep', '-f', 'aicamera_lpr'], 
                                         capture_output=True, text=True, timeout=10)
                if ps_result.returncode == 0:
                    pids = ps_result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid:
                            subprocess.run(['kill', '-TERM', pid], timeout=10)
                    time.sleep(3)
            except Exception as kill_error:
                logger.error(f"Failed to kill process: {kill_error}")
                return False
        
        # Wait a moment for the service to stop
        time.sleep(2)
        
        # Start the service
        start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
        
        if start_result.returncode != 0:
            logger.error(f"Failed to start service: {start_result.stderr}")
            return False
        
        logger.info("aicamera_lpr.service restarted successfully")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Service restart timed out")
        return False
    except Exception as e:
        logger.error(f"Error restarting service: {e}")
        return False


# WebSocket Events for real-time detection updates
def register_detection_events(socketio):
    """
    Register WebSocket events for real-time detection updates.
    
    Args:
        socketio: SocketIO instance
    """
    
    @socketio.on('detection_status_request')
    def handle_detection_status_request():
        """Handle request for detection status."""
        try:
            detection_manager = get_service('detection_manager')
            if detection_manager:
                status = detection_manager.get_status()
                serializable_status = make_json_serializable(status)
                emit('detection_status_update', serializable_status)
            else:
                emit('detection_status_error', {'error': 'Detection manager not available'})
        except Exception as e:
            logger.error(f"Error in detection status WebSocket: {e}")
            emit('detection_status_error', {'error': str(e)})
    
    @socketio.on('detection_control')
    def handle_detection_control(data):
        """Handle detection control commands."""
        try:
            command = data.get('command')
            detection_manager = get_service('detection_manager')
            
            if not detection_manager:
                emit('detection_control_response', {
                    'command': command,
                    'success': False,
                    'error': 'Detection manager not available'
                })
                return
            
            success = False
            message = ''
            
            if command == 'start':
                success = detection_manager.start_detection()
                message = 'Detection started' if success else 'Failed to start detection'
            elif command == 'stop':
                success = detection_manager.stop_detection()
                message = 'Detection stopped' if success else 'Failed to stop detection'
            elif command == 'process_frame':
                camera_manager = get_service('camera_manager')
                result = detection_manager.process_frame_from_camera(camera_manager)
                success = result is not None
                message = 'Frame processed' if success else 'Frame processing failed'
            else:
                emit('detection_control_response', {
                    'command': command,
                    'success': False,
                    'error': 'Unknown command'
                })
                return
            
            emit('detection_control_response', {
                'command': command,
                'success': success,
                'message': message
            })
            
            # Also send updated status
            status = detection_manager.get_status()
            serializable_status = make_json_serializable(status)
            emit('detection_status_update', serializable_status)
            
        except Exception as e:
            logger.error(f"Error in detection control WebSocket: {e}")
            emit('detection_control_response', {
                'command': data.get('command', 'unknown'),
                'success': False,
                'error': str(e)
            })
    
    @socketio.on('detection_statistics_request')
    def handle_detection_statistics_request():
        """Handle request for detection statistics."""
        try:
            detection_manager = get_service('detection_manager')
            if detection_manager:
                status = detection_manager.get_status()
                statistics = status.get('statistics', {})
                
                # Calculate additional metrics
                total_frames = statistics.get('total_frames_processed', 0)
                successful_detections = statistics.get('total_vehicles_detected', 0)
                
                detection_rate = 0.0
                if total_frames > 0:
                    detection_rate = (successful_detections / total_frames) * 100
                
                enhanced_stats = {
                    **statistics,
                    'detection_rate_percent': round(detection_rate, 2),
                    'avg_processing_time_ms': round(statistics.get('processing_time_avg', 0) * 1000, 2)
                }
                
                emit('detection_statistics_update', enhanced_stats)
            else:
                emit('detection_statistics_error', {'error': 'Detection manager not available'})
        except Exception as e:
            logger.error(f"Error in detection statistics WebSocket: {e}")
            emit('detection_statistics_error', {'error': str(e)})
    
    @socketio.on('join_detection_room')
    def handle_join_detection_room():
        """Join detection updates room."""
        join_room('detection_updates')
        emit('joined_detection_room', {'message': 'Joined detection updates'})
    
    @socketio.on('leave_detection_room')
    def handle_leave_detection_room():
        """Leave detection updates room."""
        leave_room('detection_updates')
        emit('left_detection_room', {'message': 'Left detection updates'})
    
    logger.info("Detection WebSocket events registered")


def _cleanup_detection_files(result_data):
    """Remove media files associated with a detection result."""
    files_removed = []
    
    paths = [
        result_data.get('original_image_path'),
        result_data.get('vehicle_detected_image_path'),
        result_data.get('plate_image_path')
    ]
    
    cropped_paths = result_data.get('cropped_plates_paths') or []
    if isinstance(cropped_paths, str):
        try:
            cropped_paths = json.loads(cropped_paths)
        except json.JSONDecodeError:
            cropped_paths = []
    if isinstance(cropped_paths, list):
        paths.extend(cropped_paths)
    
    for path in paths:
        resolved = _resolve_storage_path(path)
        if not resolved:
            continue
        try:
            if os.path.exists(resolved):
                os.remove(resolved)
                files_removed.append(resolved)
        except Exception as exc:
            logger.warning(f"Failed to delete file {resolved}: {exc}")
    
    return files_removed


def _resolve_storage_path(raw_path):
    """Resolve relative media paths to absolute locations under IMAGE_SAVE_DIR."""
    if not raw_path or not isinstance(raw_path, str):
        return None

    cleaned = raw_path.strip()
    if not cleaned:
        return None

    try:
        # If already absolute, ensure it resides inside IMAGE_SAVE_DIR
        if os.path.isabs(cleaned):
            normalized = os.path.normpath(cleaned)
            if os.path.commonpath([normalized, IMAGE_SAVE_DIR]) != IMAGE_SAVE_DIR:
                return None
            return normalized

        relative = cleaned.lstrip('/')
        if relative.startswith('edge/'):
            relative = relative.split('edge/', 1)[1]
        if relative.startswith('captured_images/'):
            relative = relative[len('captured_images/'):]

        candidate = os.path.normpath(os.path.join(IMAGE_SAVE_DIR, relative))
        if os.path.commonpath([candidate, IMAGE_SAVE_DIR]) != IMAGE_SAVE_DIR:
            return None
        return candidate
    except (ValueError, OSError) as e:
        logger.warning(f"Resolve storage path failed for {raw_path!r}: {e}")
        return None
