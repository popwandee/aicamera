#!/usr/bin/env python3
"""
.0 Camera v2.0.0 Flask Application

Main Flask application that integrates camera services and web interface
using absolute imports and existing blueprint structure.

Author: AI Camera Team
Version: 2.0.0
Date: August 23, 2025
"""

import os
import socket
import sys
from pathlib import Path
from typing import Tuple
from datetime import datetime

# Load environment variables from .env.production first
def load_env_file():
    """Load environment variables from .env.production file."""
    env_file = Path(__file__).parent.parent / 'installation' / '.env.production'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    os.environ[key.strip()] = value

# Load environment variables
load_env_file()

from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
import logging

# Import import helper first to setup paths
try:
    from edge.src.core.utils.import_helper import setup_import_paths, validate_imports
    setup_import_paths()
except ImportError as e:
    # Fallback if import helper is not available
    print(f"Warning: Could not import import_helper: {e}")
    # Basic path setup as fallback
    import sys
    from pathlib import Path
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    edge_path = str(project_root / 'edge')
    if edge_path not in sys.path:
        sys.path.insert(0, edge_path)

# Setup logging with fallback
try:
    from edge.src.core.utils.logging_config import setup_logging, get_logger
    logger = setup_logging(level="INFO")
except ImportError as e:
    # Fallback logging setup
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import logging_config: {e}")

# Import other modules with error handling
try:
    from edge.src.core.dependency_container import get_container, get_service
    from edge.src.web.blueprints import register_blueprints
    from edge.src.core.config import (
        AUTO_START_CAMERA, AUTO_START_DETECTION, AUTO_START_HEALTH_MONITOR, AUTO_START_WEBSOCKET_SENDER,
        AUTO_START_STORAGE_MONITOR, STARTUP_DELAY, HEALTH_MONITOR_STARTUP_DELAY, 
        WEBSOCKET_SENDER_STARTUP_DELAY, STORAGE_MONITOR_STARTUP_DELAY, STORAGE_MONITOR_INTERVAL
    )
    from edge.src.services.registration_manager import initialize_registration, RegistrationState
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    # Set default values for testing
    AUTO_START_CAMERA = False
    AUTO_START_DETECTION = False
    AUTO_START_HEALTH_MONITOR = False
    AUTO_START_WEBSOCKET_SENDER = False
    AUTO_START_STORAGE_MONITOR = False
    STARTUP_DELAY = 1
    HEALTH_MONITOR_STARTUP_DELAY = 1
    WEBSOCKET_SENDER_STARTUP_DELAY = 1
    STORAGE_MONITOR_STARTUP_DELAY = 1
    STORAGE_MONITOR_INTERVAL = 60


def _initialize_services(logger):
    """
    Initialize services in the correct order with modular architecture support.
    
    Modular Architecture:
    - Core modules (camera, detection, health) are essential and must work
    - Optional modules (websocket sender, storage) can be disabled without affecting core
    - Each phase is independent and can fail without stopping the system
    
    Args:
        logger: Logger instance
    """
    logger.info("🚀 Starting modular service initialization sequence...")
    logger.debug(f"🔧 [APP] _initialize_services called")
    
    # Track initialization results
    init_results = {
        'core_modules': {},
        'optional_modules': {},
        'errors': []
    }
    logger.debug(f"🔧 [APP] _initialize_services: initialization results tracking initialized")
    
    # === PHASE 0: Device Registration ===
    logger.info("🔐 Phase 0: Device Registration")
    
    # Check if device registration is enabled
    registration_enabled = os.getenv('DEVICE_REGISTRATION_ENABLED', 'true').lower() == 'true'
    
    if not registration_enabled:
        logger.info("ℹ️ Device registration disabled by configuration")
        init_results['core_modules']['device_registration'] = True  # Mark as successful since it's intentionally disabled
    else:
        try:
            server_url = os.getenv('SERVER_URL', 'http://localhost')
            registration_manager = initialize_registration(server_url)
        
            # Set up registration callbacks
            def on_registration_success(message):
                logger.info(f"✅ Registration successful: {message}")
            
            def on_approval(message):
                logger.info(f"✅ Device approved: {message}")
            
            def on_rejection(message):
                logger.error(f"❌ Device rejected: {message}")
            
            def on_error(message):
                logger.error(f"❌ Registration error: {message}")
            
            def on_active(message):
                logger.info(f"✅ Device active: {message}")
            
            registration_manager.register_callback('on_registration_success', on_registration_success)
            registration_manager.register_callback('on_approval', on_approval)
            registration_manager.register_callback('on_rejection', on_rejection)
            registration_manager.register_callback('on_error', on_error)
            registration_manager.register_callback('on_active', on_active)
            
            # Start registration process
            registration_type = os.getenv('REGISTRATION_TYPE', 'self')  # self, pre_provision
            registration_success = registration_manager.start_registration_process(registration_type)
            
            if registration_success or registration_manager.state in [RegistrationState.PENDING_APPROVAL, RegistrationState.ACTIVE]:
                logger.info("✅ Device registration initialized")
                init_results['core_modules']['device_registration'] = True
            else:
                logger.warning("⚠️ Device registration failed, continuing with limited functionality")
                init_results['core_modules']['device_registration'] = True  # Mark as successful since it's optional
                init_results['errors'].append("Device registration failed (optional)")
            
        except Exception as e:
            logger.error(f"❌ Device registration error: {e}")
            init_results['core_modules']['device_registration'] = True  # Mark as successful since it's optional
            init_results['errors'].append(f"Device registration: {e} (optional)")
    
    # === PHASE 1: Core Infrastructure ===
    logger.info("📋 Phase 1: Core Infrastructure")
    try:
        # Logger and config are already initialized by DI container
        logger.info("✅ Core infrastructure ready")
    except Exception as e:
        logger.error(f"❌ Core infrastructure failed: {e}")
        init_results['errors'].append(f"Core infrastructure: {e}")
        return False  # Core infrastructure failure is critical
    
    # === PHASE 2: Core Components ===
    logger.info("🔧 Phase 2: Core Components")
    
    # Camera Handler
    try:
        camera_handler = get_service('camera_handler')
        if camera_handler:
            logger.info("✅ Camera Handler available")
            init_results['core_modules']['camera_handler'] = True
        else:
            logger.error("❌ Camera Handler not available")
            init_results['core_modules']['camera_handler'] = False
            init_results['errors'].append("Camera Handler not available")
    except Exception as e:
        logger.error(f"❌ Camera Handler error: {e}")
        init_results['core_modules']['camera_handler'] = False
        init_results['errors'].append(f"Camera Handler: {e}")
    
    # Detection Processor
    try:
        detection_processor = get_service('detection_processor')
        if detection_processor:
            logger.info("✅ Detection Processor available")
            init_results['core_modules']['detection_processor'] = True
        else:
            logger.warning("⚠️ Detection Processor not available")
            init_results['core_modules']['detection_processor'] = False
    except Exception as e:
        logger.warning(f"⚠️ Detection Processor error: {e}")
        init_results['core_modules']['detection_processor'] = False
    
    # Database Manager
    try:
        database_manager = get_service('database_manager')
        if database_manager:
            logger.info("✅ Database Manager available")
            init_results['core_modules']['database_manager'] = True
        else:
            logger.error("❌ Database Manager not available")
            init_results['core_modules']['database_manager'] = False
            init_results['errors'].append("Database Manager not available")
    except Exception as e:
        logger.error(f"❌ Database Manager error: {e}")
        init_results['core_modules']['database_manager'] = False
        init_results['errors'].append(f"Database Manager: {e}")
    
    # Health Monitor
    try:
        health_monitor = get_service('health_monitor')
        if health_monitor:
            logger.info("✅ Health Monitor available")
            init_results['core_modules']['health_monitor'] = True
        else:
            logger.error("❌ Health Monitor not available")
            init_results['core_modules']['health_monitor'] = False
            init_results['errors'].append("Health Monitor not available")
    except Exception as e:
        logger.error(f"❌ Health Monitor error: {e}")
        init_results['core_modules']['health_monitor'] = False
        init_results['errors'].append(f"Health Monitor: {e}")
    
    # === PHASE 3: Core Services ===
    logger.info("⚙️ Phase 3: Core Services")
    
    # Camera Manager
    try:
        logger.info("🎥 === PHASE 2: Camera Manager Initialization ===")
        camera_manager = get_service('camera_manager')
        logger.info("🎥 CameraManager service obtained, starting initialization...")
        if camera_manager:
            logger.info("🎥 About to call camera_manager.initialize()...")
            success = camera_manager.initialize()
            logger.info(f"🎥 Camera manager initialize() returned: {success}")
            if success:
                logger.info("✅ Camera Manager initialized successfully")
                init_results['core_modules']['camera_manager'] = True
                if AUTO_START_CAMERA:
                    logger.info("🎥 Camera auto-start enabled")
            else:
                logger.error("❌ Camera Manager initialization failed")
                init_results['core_modules']['camera_manager'] = False
                init_results['errors'].append("Camera Manager initialization failed")
        else:
            logger.error("❌ Camera Manager service not available")
            init_results['core_modules']['camera_manager'] = False
            init_results['errors'].append("Camera Manager service not available")
        logger.info("🎥 Camera Manager phase completed")
    except Exception as e:
        logger.error(f"❌ Camera Manager error: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        init_results['core_modules']['camera_manager'] = False
        init_results['errors'].append(f"Camera Manager: {e}")
    
    # Detection Manager
    try:
        logger.info("🔍 === PHASE 3: Detection Manager Initialization ===")
        detection_manager = get_service('detection_manager')
        if detection_manager:
            logger.info("🔍 DetectionManager service obtained, starting initialization...")
            success = detection_manager.initialize()
            if success:
                logger.info("✅ Detection Manager initialized successfully")
                init_results['core_modules']['detection_manager'] = True
                if AUTO_START_DETECTION:
                    logger.info("🔍 Detection auto-start enabled - will start in background")
            else:
                logger.warning("⚠️ Detection Manager initialization failed")
                init_results['core_modules']['detection_manager'] = False
        else:
            logger.warning("⚠️ Detection Manager service not available")
            init_results['core_modules']['detection_manager'] = False
        logger.info("🔍 Detection Manager phase completed")
    except Exception as e:
        logger.error(f"❌ Detection Manager error: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        init_results['core_modules']['detection_manager'] = False
    
    # Health Service
    try:
        logger.info("🏥 === PHASE 4: Health Service Initialization ===")
        health_service = get_service('health_service')
        if health_service:
            logger.info("🏥 HealthService service obtained, starting initialization...")
            success = health_service.initialize()
            if success:
                logger.info("✅ Health Service initialized successfully")
                init_results['core_modules']['health_service'] = True
                if AUTO_START_HEALTH_MONITOR:
                    logger.info("🏥 Health Monitor auto-start enabled - will start in background")
            else:
                logger.error("❌ Health Service initialization failed")
                init_results['core_modules']['health_service'] = False
                init_results['errors'].append("Health Service initialization failed")
        else:
            logger.error("❌ Health Service not available")
            init_results['core_modules']['health_service'] = False
            init_results['errors'].append("Health Service not available")
        logger.info("🏥 Health Service phase completed")
    except Exception as e:
        logger.error(f"❌ Health Service error: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        init_results['core_modules']['health_service'] = False
        init_results['errors'].append(f"Health Service: {e}")
    
    # Video Streaming
    try:
        video_streaming = get_service('video_streaming')
        if video_streaming:
            logger.info("✅ Video Streaming available")
            init_results['core_modules']['video_streaming'] = True
        else:
            logger.warning("⚠️ Video Streaming not available")
            init_results['core_modules']['video_streaming'] = False
    except Exception as e:
        logger.warning(f"⚠️ Video Streaming error: {e}")
        init_results['core_modules']['video_streaming'] = False
    
    # === PHASE 4: Optional Components ===
    logger.info("🔌 Phase 4: Optional Components")
    
    # Storage Monitor (Optional)
    try:
        storage_monitor = get_service('storage_monitor')
        if storage_monitor:
            logger.info("✅ Storage Monitor available")
            init_results['optional_modules']['storage_monitor'] = True
        else:
            logger.info("ℹ️ Storage Monitor not available (optional)")
            init_results['optional_modules']['storage_monitor'] = False
    except Exception as e:
        logger.info(f"ℹ️ Storage Monitor error (optional): {e}")
        init_results['optional_modules']['storage_monitor'] = False
    
    # === PHASE 5: Optional Services ===
    logger.info("🔌 Phase 5: Optional Services")
    
    # WebSocket Sender (Optional)
    try:
        websocket_sender = get_service('websocket_sender')
        if websocket_sender:
            success = websocket_sender.initialize()
            if success:
                logger.info("✅ WebSocket Sender initialized successfully")
                init_results['optional_modules']['websocket_sender'] = True
                if AUTO_START_WEBSOCKET_SENDER:
                    logger.info("📤 WebSocket Sender auto-start enabled")
                    import time
                    time.sleep(WEBSOCKET_SENDER_STARTUP_DELAY)
                    if websocket_sender.start():
                        logger.info("✅ WebSocket Sender started successfully")
                    else:
                        logger.warning("⚠️ WebSocket Sender failed to start")
            else:
                logger.warning("⚠️ WebSocket Sender initialization failed")
                init_results['optional_modules']['websocket_sender'] = False
        else:
            logger.info("ℹ️ WebSocket Sender not available (optional)")
            init_results['optional_modules']['websocket_sender'] = False
    except Exception as e:
        logger.info(f"ℹ️ WebSocket Sender error (optional): {e}")
        init_results['optional_modules']['websocket_sender'] = False

    # MQTT Health Sender (Optional - health status via MQTT)
    try:
        from edge.src.core.dependency_container import get_container
        container = get_container()
        mqtt_health_sender = container.get_service('mqtt_health_sender') if container.has_service('mqtt_health_sender') else None
        if mqtt_health_sender:
            success = mqtt_health_sender.initialize()
            if success:
                logger.info("✅ MQTT Health Sender initialized successfully")
                init_results['optional_modules']['mqtt_health_sender'] = True
                if mqtt_health_sender.start():
                    logger.info("✅ MQTT Health Sender started successfully")
                else:
                    logger.warning("⚠️ MQTT Health Sender failed to start")
            else:
                init_results['optional_modules']['mqtt_health_sender'] = False
        else:
            logger.info("ℹ️ MQTT Health Sender not available (optional)")
            init_results['optional_modules']['mqtt_health_sender'] = False
    except Exception as e:
        logger.info("ℹ️ MQTT Health Sender error (optional): %s", e)
        init_results['optional_modules']['mqtt_health_sender'] = False

    # Storage Service (Optional)
    try:
        storage_service = get_service('storage_service')
        if storage_service:
            success = storage_service.initialize()
            if success:
                logger.info("✅ Storage Service initialized successfully")
                init_results['optional_modules']['storage_service'] = True
                if AUTO_START_STORAGE_MONITOR:
                    logger.info("💾 Storage Monitor auto-start enabled")
                    import time
                    time.sleep(STORAGE_MONITOR_STARTUP_DELAY)
                    if storage_service.start_storage_monitoring(interval=STORAGE_MONITOR_INTERVAL):
                        logger.info("✅ Storage monitoring started successfully")
                    else:
                        logger.warning("⚠️ Storage monitoring failed to start")
            else:
                logger.warning("⚠️ Storage Service initialization failed")
                init_results['optional_modules']['storage_service'] = False
        else:
            logger.info("ℹ️ Storage Service not available (optional)")
            init_results['optional_modules']['storage_service'] = False
    except Exception as e:
        logger.info(f"ℹ️ Storage Service error (optional): {e}")
        init_results['optional_modules']['storage_service'] = False
    
    # === SUMMARY ===
    logger.info("📊 Initialization Summary:")
    
    # Core modules status
    core_success = sum(init_results['core_modules'].values())
    core_total = len(init_results['core_modules'])
    logger.info(f"   Core Modules: {core_success}/{core_total} successful")
    
    for module, status in init_results['core_modules'].items():
        status_icon = "✅" if status else "❌"
        logger.info(f"     {status_icon} {module}")
    
    # Optional modules status
    optional_success = sum(init_results['optional_modules'].values())
    optional_total = len(init_results['optional_modules'])
    logger.info(f"   Optional Modules: {optional_success}/{optional_total} successful")
    
    for module, status in init_results['optional_modules'].items():
        status_icon = "✅" if status else "ℹ️"
        logger.info(f"     {status_icon} {module}")
    
    # Error summary
    if init_results['errors']:
        logger.warning(f"   Errors: {len(init_results['errors'])} errors occurred")
        for error in init_results['errors']:
            logger.warning(f"     ❌ {error}")
    
    # Determine if system is functional
    critical_modules = ['camera_handler', 'camera_manager', 'database_manager', 'health_monitor', 'health_service']
    critical_success = all(init_results['core_modules'].get(module, False) for module in critical_modules)
    
    if critical_success:
        logger.info("🎉 System initialization completed successfully!")
        logger.info("   Core functionality is available")
        if optional_success > 0:
            logger.info(f"   {optional_success} optional modules are also available")
        return True
    else:
        logger.error("❌ System initialization failed!")
        logger.error("   Critical modules are missing or failed")
        return False


def create_app():
    """Create and configure Flask application using absolute imports."""
    # Setup logging
    logger = setup_logging(level="DEBUG")
    logger.info("🚀 === STARTING FLASK APP CREATION ===")
    logger.info("🔧 [APP] create_app called")
    
    # Validate imports
    logger.debug(f"🔧 [APP] create_app: validating imports")
    import_errors = validate_imports()
    if import_errors:
        logger.warning("🔧 [APP] create_app: some imports failed:")
        for error in import_errors:
            logger.warning(f"🔧 [APP] create_app:   {error}")
    else:
        logger.debug(f"🔧 [APP] create_app: all imports validated successfully")
    
    # Set template and static folders
    current_dir = Path(__file__).parent
    template_dir = current_dir / 'web' / 'templates'
    static_dir = current_dir / 'web' / 'static'
    logger.debug(f"🔧 [APP] create_app: template_dir: {template_dir}, static_dir: {static_dir}")

    # Create Flask app
    logger.debug(f"🔧 [APP] create_app: creating Flask app")
    app = Flask(__name__, 
                template_folder=str(template_dir),
                static_folder=str(static_dir))
    logger.debug(f"🔧 [APP] create_app: Flask app created successfully")
    
    # Load configuration using absolute import
    logger.debug(f"🔧 [APP] create_app: loading configuration from edge.src.core.config")
    app.config.from_object('edge.src.core.config')
    logger.debug(f"🔧 [APP] create_app: configuration loaded successfully")
    
    # Global template context (hostname, etc.)
    @app.context_processor
    def inject_edge_context():
        hostname = os.getenv('DEVICE_ID') or socket.gethostname()
        return {'edge_hostname': hostname}
    
    # Initialize dependency container
    logger.debug(f"🔧 [APP] create_app: initializing dependency container")
    container = get_container()
    logger.info("🔧 [APP] create_app: dependency container initialized")
    
    # Initialize SocketIO with improved configuration
    logger.debug(f"🔧 [APP] create_app: initializing SocketIO")
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*", 
        async_mode='threading',
        ping_timeout=60,  # Increase ping timeout
        ping_interval=25,  # Reduce ping interval
        max_http_buffer_size=1e8,  # Increase buffer size
        logger=True,  # Enable logging
        engineio_logger=True,  # Enable engineio logging
        cors_credentials=True
    )
    logger.debug(f"🔧 [APP] create_app: SocketIO initialized successfully")
    
    # Register blueprints using existing structure
    logger.debug(f"🔧 [APP] create_app: registering blueprints")
    register_blueprints(app, socketio)
    logger.debug(f"🔧 [APP] create_app: blueprints registered successfully")
    
    # Initialize services with auto-startup sequence
    logger.info("🔧 === ABOUT TO INITIALIZE SERVICES ===")
    logger.debug(f"🔧 [APP] create_app: about to initialize services")
    try:
        _initialize_services(logger)
        logger.info("✅ === SERVICES INITIALIZATION COMPLETED ===")
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    @app.route('/api/health')
    def api_health():
        """API Health check endpoint."""
        try:
            logger.info("Health check endpoint called")
            
            # Simple health check without service dependencies
            return jsonify({
                'success': True,
                'status': 'healthy',
                'message': 'Service is running',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'success': False,
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
    
    @app.route('/api/registration/status')
    def api_registration_status():
        """Get device registration status."""
        try:
            from edge.src.services.registration_manager import get_registration_manager
            registration_manager = get_registration_manager()
            status = registration_manager.get_status()
            
            return jsonify({
                'success': True,
                'registration': status,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Registration status check failed: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
    
    @app.route('/api/registration/force-reregister', methods=['POST'])
    def api_force_reregister():
        """Force device re-registration (for testing/recovery)."""
        try:
            from edge.src.services.registration_manager import get_registration_manager
            registration_manager = get_registration_manager()
            registration_manager.force_re_registration()
            
            return jsonify({
                'success': True,
                'message': 'Device reset for re-registration',
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Force re-registration failed: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
    

    @app.route('/system/info')
    def api_system_info():
        """Return system information used by the dashboard.

        Response shape expected by dashboard.js.updateSystemInfoFromAPI:
        { "success": true, "info": { ... } }
        """
        try:
            # Prefer consolidated data from health_service if available
            health_service = get_service('health_service')
            if health_service and hasattr(health_service, 'get_system_health'):
                health_data = health_service.get_system_health()
                # health_data is expected to be { success: bool, data: { system: {...}, ... }, ... }
                system_info = None
                if isinstance(health_data, dict):
                    data_obj = health_data.get('data') or {}
                    system_info = data_obj.get('system') or {}

                return jsonify({
                    'success': True,
                    'info': system_info or {}
                })

            # Fallback minimal info when health_service is unavailable
            return jsonify({
                'success': True,
                'info': {}
            })
        except Exception as e:
            logger.error(f"System info endpoint error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500
    
    logger.info("✅ === FLASK APPLICATION CREATED SUCCESSFULLY ===")
    logger.debug(f"🔧 [APP] create_app: returning Flask app and SocketIO instance")
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