#!/usr/bin/env python3
"""
Health Service for AI Camera v1.3

This service manages health monitoring business logic and provides
high-level health status information to the web interface.

Author: AI Camera Team
Version: 1.3
Date: August 2025
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from edge.src.core.utils.logging_config import get_logger
from edge.src.core.dependency_container import get_service

logger = get_logger(__name__)


class HealthService:
    """
    Health Service for managing system health monitoring.
    
    This service provides:
    - Health status aggregation
    - System resource monitoring
    - Health check scheduling
    - Status reporting for web interface
    """
    
    def __init__(self, health_monitor=None, logger=None):
        """
        Initialize Health Service.
        
        Args:
            health_monitor: HealthMonitor component instance
            logger: Logger instance
        """
        self.logger = logger or get_logger(__name__)
        self.health_monitor = health_monitor
        self.last_system_status = None
        self.last_check_time = None
        
        self.logger.info("HealthService initialized")
    
    def initialize(self) -> bool:
        """
        Initialize Health Service with dependencies.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        self.logger.debug(f"🔧 [HEALTH_SERVICE] initialize called")
        
        try:
            # Get health monitor from DI container if not provided
            if not self.health_monitor:
                self.logger.debug(f"🔧 [HEALTH_SERVICE] initialize: getting health_monitor from DI container")
                self.health_monitor = get_service('health_monitor')
                self.logger.debug(f"🔧 [HEALTH_SERVICE] initialize: health_monitor from DI container: {self.health_monitor is not None}")
            
            if not self.health_monitor:
                self.logger.error(f"🔧 [HEALTH_SERVICE] initialize failed: health monitor not available")
                return False
            
            # Initialize health monitor
            self.logger.debug(f"🔧 [HEALTH_SERVICE] initialize: calling health_monitor.initialize()")
            if not self.health_monitor.initialize():
                self.logger.error(f"🔧 [HEALTH_SERVICE] initialize failed: failed to initialize health monitor")
                return False
            
            self.logger.debug(f"🔧 [HEALTH_SERVICE] initialize: health_monitor.initialize() returned: True")
            
            # Set up auto-start monitoring only if enabled
            from edge.src.core.config import AUTO_START_HEALTH_MONITOR
            self.logger.debug(f"🔧 [HEALTH_SERVICE] initialize: AUTO_START_HEALTH_MONITOR: {AUTO_START_HEALTH_MONITOR}")
            
            if AUTO_START_HEALTH_MONITOR:
                self.logger.debug(f"🔧 [HEALTH_SERVICE] initialize: setting up auto-start monitoring")
                self._setup_auto_start_monitoring()
                self.logger.info(f"🔧 [HEALTH_SERVICE] HealthService initialized successfully with auto-start monitoring")
            else:
                self.logger.info(f"🔧 [HEALTH_SERVICE] HealthService initialized successfully (auto-start monitoring disabled)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"🔧 [HEALTH_SERVICE] initialize error: {e}")
            return False
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health status.
        
        Returns:
            Dict containing overall system health information
        """
        self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health called")
        
        try:
            if not self.health_monitor:
                self.logger.warning(f"🔧 [HEALTH_SERVICE] get_system_health failed: health monitor not available")
                return {
                    'success': False,
                    'error': 'Health monitor not available',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Run health checks to ensure we have latest data
            self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health: calling health_monitor.run_all_checks()")
            health_result = self.health_monitor.run_all_checks()
            self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health: health_monitor.run_all_checks() returned: {health_result.get('overall_status', 'unknown')}")
            
            # Get system resource information
            self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health: calling _get_system_info()")
            system_info = self._get_system_info()
            self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health: _get_system_info() returned system info with CPU usage: {system_info.get('cpu_usage', 0.0)}%")
            
            # Build comprehensive health response
            self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health: calling _build_component_status()")
            components = self._build_component_status(health_result)
            self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health: _build_component_status() returned components: {list(components.keys())}")
            
            # Add error details for non-healthy components
            error_details = {}
            for component_name, component_data in components.items():
                if component_data.get('status') not in ['healthy', 'unknown']:
                    error_details[component_name] = {
                        'status': component_data.get('status'),
                        'issues': self._get_component_issues(component_name, component_data)
                    }
            
            self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health: error details: {list(error_details.keys()) if error_details else 'none'}")
            
            response = {
                'success': True,
                'data': {
                    'overall_status': health_result.get('overall_status', 'unknown'),
                    'components': components,
                    'system': system_info,
                    'error_details': error_details if error_details else None,
                    'last_check': datetime.now().isoformat()
                },
                'timestamp': datetime.now().isoformat()
            }
            
            # Cache the result
            self.last_system_status = response
            self.last_check_time = datetime.now()
            
            self.logger.debug(f"🔧 [HEALTH_SERVICE] get_system_health: returning response with overall_status: {response['data']['overall_status']}")
            return response
            
        except Exception as e:
            self.logger.error(f"🔧 [HEALTH_SERVICE] get_system_health error: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_code': 'OPERATION_FAILED',
                'timestamp': datetime.now().isoformat()
            }
    
    def _build_component_status(self, health_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build component status from health check results.
        
        Args:
            health_result: Raw health check results
            
        Returns:
            Dict containing component status information
        """
        self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status called with health_result: {health_result.get('overall_status', 'unknown')}")
        
        try:
            component_status = health_result.get('component_status', {})
            latest_checks = health_result.get('latest_checks', [])
            
            self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: component_status: {component_status}")
            self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: latest_checks count: {len(latest_checks)}")
            
            # Get real-time system info
            system_info = self._get_system_info()
            
            # Build component status
            components = {}
            
            # Camera status - try to get from health checks, fallback to unknown
            camera_status = "healthy" if component_status.get('camera', False) else "unhealthy"
            camera_check = self._find_latest_check(latest_checks, "Camera")
            
            # Get camera manager status if available
            self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: getting camera_manager from DI container")
            camera_manager = get_service('camera_manager')
            camera_manager_status = None
            if camera_manager:
                try:
                    self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: calling camera_manager.get_status()")
                    camera_manager_status = camera_manager.get_status()
                    self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: camera_manager.get_status() returned: initialized={camera_manager_status.get('initialized', False)}, streaming={camera_manager_status.get('streaming', False)}")
                except Exception as e:
                    self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: camera_manager.get_status() error: {e}")
            else:
                self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: camera_manager not available")
            
            # Get camera properties for model information
            camera_properties = {}
            if camera_manager_status and 'camera_handler' in camera_manager_status:
                camera_handler_status = camera_manager_status.get('camera_handler', {})
                camera_properties = camera_handler_status.get('camera_properties', {})
                self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: camera_properties: {camera_properties}")
            
            components['camera'] = {
                'status': camera_status,
                'initialized': camera_manager_status.get('initialized', False) if camera_manager_status else False,
                'streaming': camera_manager_status.get('streaming', False) if camera_manager_status else False,
                'frame_count': camera_manager_status.get('frame_count', 0) if camera_manager_status else 0,
                'average_fps': camera_manager_status.get('average_fps', 0.0) if camera_manager_status else 0.0,
                'uptime': camera_manager_status.get('uptime', 0) if camera_manager_status else 0,
                'auto_start_enabled': True,  # Default to True as per config
                'last_check': camera_check.get('timestamp') if camera_check else None,
                'camera_properties': camera_properties
            }
            
            self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: camera component status: {components['camera']['status']}")
            
            # Detection status - use detection module patterns for accurate status
            self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: getting detection_manager from DI container")
            detection_manager = get_service('detection_manager')
            detection_status = "unknown"
            detection_active = False
            models_loaded = False
            easyocr_available = False
            service_running = False
            thread_alive = False
            
            if detection_manager:
                try:
                    self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: calling detection_manager.get_status()")
                    detection_status_info = detection_manager.get_status()
                    self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: detection_manager.get_status() returned: service_running={detection_status_info.get('service_running', False)}, thread_alive={detection_status_info.get('thread_alive', False)}")
                    
                    service_running = detection_status_info.get('service_running', False)
                    thread_alive = detection_status_info.get('thread_alive', False)
                    
                    # Check detection processor status using detection module patterns
                    processor_status = detection_status_info.get('detection_processor_status', {})
                    models_loaded = processor_status.get('models_loaded', False)
                    easyocr_available = processor_status.get('easyocr_available', False)
                    
                    self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: detection processor status: models_loaded={models_loaded}, easyocr_available={easyocr_available}")
                    
                    # Determine overall detection status
                    if service_running and thread_alive and models_loaded:
                        detection_status = "healthy"
                        detection_active = True
                        self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: detection status determined as: healthy")
                    elif service_running and thread_alive:
                        detection_status = "warning"  # Service running but models not loaded
                        self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: detection status determined as: warning (service running but models not loaded)")
                    elif service_running:
                        detection_status = "warning"  # Service running but thread not alive
                        self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: detection status determined as: warning (service running but thread not alive)")
                    else:
                        detection_status = "unhealthy"
                        self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: detection status determined as: unhealthy")
                        
                except Exception as e:
                    self.logger.error(f"🔧 [HEALTH_SERVICE] _build_component_status: error getting detection status: {e}")
                    detection_status = "error"
            else:
                self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: detection_manager not available")
            
            # Fallback to health check results if detection manager not available
            if detection_status == "unknown":
                # Only require models — EasyOCR is never loaded on edge devices
                detection_status = "healthy" if component_status.get('models', False) else "unhealthy"
                models_check = self._find_latest_check(latest_checks, "Detection Models")
                models_loaded = models_check.get('status') == 'PASS' if models_check else False
            
            components['detection'] = {
                'status': detection_status,
                'models_loaded': models_loaded,
                'easyocr_available': easyocr_available,
                'detection_active': detection_active,
                'service_running': service_running,
                'thread_alive': thread_alive,
                'auto_start': True,  # Default to True as per config
                'last_check': datetime.now().isoformat()
            }
            
            # Database status - try to get from health checks, fallback to unknown
            db_status = "healthy" if component_status.get('database', False) else "unhealthy"
            db_check = self._find_latest_check(latest_checks, "Database")
            
            # Get database manager status if available
            db_manager = get_service('database_manager')
            db_connected = False
            if db_manager and db_manager.connection:
                try:
                    db_manager.connection.execute("SELECT 1")
                    db_connected = True
                except:
                    db_connected = False
            
            components['database'] = {
                'status': db_status,
                'connected': db_connected,
                'database_path': db_manager.database_path if db_manager else None,
                'last_check': db_check.get('timestamp') if db_check else None
            }
            
            # System status - use real-time data instead of health check data
            system_status = "healthy"  # System is generally healthy if we can get this data
            components['system'] = {
                'status': system_status,
                'last_check': datetime.now().isoformat(),
                'os_info': system_info.get('os_info', {}),
                'cpu_info': system_info.get('cpu_info', {}),
                'ai_accelerator_info': system_info.get('ai_accelerator_info', {})
            }
            
            self.logger.debug(f"🔧 [HEALTH_SERVICE] _build_component_status: returning components: {list(components.keys())}")
            return components
            
        except Exception as e:
            self.logger.error(f"🔧 [HEALTH_SERVICE] _build_component_status error: {e}")
            return {}
    
    def _find_latest_check(self, checks: List[Dict[str, Any]], component: str) -> Optional[Dict[str, Any]]:
        """Find the latest check for a specific component."""
        for check in checks:
            if check.get('component') == component:
                return check
        return None
    
    def _extract_cpu_usage(self, cpu_check: Optional[Dict[str, Any]]) -> float:
        """Extract CPU usage from health check details."""
        try:
            if cpu_check and cpu_check.get('details'):
                import json
                details = json.loads(cpu_check['details'])
                return details.get('cpu_percent', 0.0)
        except:
            pass
        return 0.0
    
    def _extract_memory_usage(self, cpu_check: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract memory usage from health check details."""
        try:
            if cpu_check and cpu_check.get('details'):
                import json
                details = json.loads(cpu_check['details'])
                return {
                    'used': details.get('ram_used_gb', 0.0),
                    'total': details.get('ram_total_gb', 0.0),
                    'percentage': details.get('ram_percent', 0.0)
                }
        except:
            pass
        return {'used': 0.0, 'total': 0.0, 'percentage': 0.0}
    
    def _extract_disk_usage(self, disk_check: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract disk usage from health check details."""
        try:
            if disk_check and disk_check.get('details'):
                import json
                details = json.loads(disk_check['details'])
                return {
                    'used': details.get('used_gb', 0.0),
                    'total': details.get('total_gb', 0.0),
                    'percentage': details.get('used_percent', 0.0)
                }
        except:
            pass
        return {'used': 0.0, 'total': 0.0, 'percentage': 0.0}
    
    def _get_component_issues(self, component_name: str, component_data: Dict[str, Any]) -> List[str]:
        """Get specific issues for a component."""
        issues = []
        
        if component_name == 'camera':
            if not component_data.get('initialized', False):
                issues.append('Camera not initialized')
            if not component_data.get('streaming', False):
                issues.append('Camera not streaming')
            if not component_data.get('auto_start_enabled', False):
                issues.append('Auto-start disabled')
                
        elif component_name == 'detection':
            if not component_data.get('models_loaded', False):
                issues.append('AI models not loaded')
            # EasyOCR is never loaded on edge devices — Tesseract is used instead
            if not component_data.get('detection_active', False):
                issues.append('Detection not active')
            if not component_data.get('service_running', False):
                issues.append('Detection service not running')
            if not component_data.get('thread_alive', False):
                issues.append('Detection thread not alive')
                
        elif component_name == 'database':
            if not component_data.get('connected', False):
                issues.append('Database connection failed')
                
        elif component_name == 'system':
            issues.append('System resources critical')
            
        return issues
    
    def _get_system_uptime(self) -> float:
        """Get system uptime in seconds."""
        try:
            import psutil
            return time.time() - psutil.boot_time()
        except:
            return 0.0
    
    def _get_system_info(self) -> Dict[str, Any]:
        """
        Get current system resource information.
        
        Returns:
            Dict containing system resource information
        """
        try:
            import psutil
            import platform
            import subprocess
            import os
            
            # CPU information
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Get detailed CPU architecture information
            cpu_arch = platform.machine()
            cpu_processor = platform.processor()
            
            # Try to get Raspberry Pi specific information
            pi_model = "Unknown"
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    for line in cpuinfo.split('\n'):
                        if line.startswith('Model'):
                            pi_model = line.split(':')[1].strip()
                            break
            except:
                pass
            
            # Get CPU frequency
            cpu_freq = "Unknown"
            try:
                with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq', 'r') as f:
                    freq_khz = int(f.read().strip())
                    cpu_freq = f"{freq_khz // 1000} MHz"
            except:
                pass
            
            # Memory information
            memory = psutil.virtual_memory()
            
            # Disk information
            disk = psutil.disk_usage('/')
            
            # System uptime
            uptime = time.time() - psutil.boot_time()
            
            # Enhanced OS information
            os_name = platform.system()
            os_release = platform.release()
            os_version = platform.version()
            
            # Get distribution information
            dist_name = "Unknown"
            dist_version = "Unknown"
            try:
                with open('/etc/os-release', 'r') as f:
                    os_release_content = f.read()
                    for line in os_release_content.split('\n'):
                        if line.startswith('PRETTY_NAME='):
                            dist_name = line.split('=', 1)[1].strip().strip('"')
                            break
                        elif line.startswith('NAME='):
                            dist_name = line.split('=', 1)[1].strip().strip('"')
                        elif line.startswith('VERSION='):
                            dist_version = line.split('=', 1)[1].strip().strip('"')
            except:
                pass
            
            # Get kernel version
            kernel_version = os_release
            
            # Get AI Accelerator information
            ai_accelerator_info = self._get_ai_accelerator_info()
            
            os_info = {
                'name': os_name,
                'distribution': dist_name,
                'distribution_version': dist_version,
                'kernel_version': kernel_version,
                'release': os_release,
                'version': os_version,
                'platform': platform.platform(),
                'architecture': cpu_arch
            }
            
            # CPU architecture information
            cpu_info = {
                'architecture': cpu_arch,
                'processor': cpu_processor,
                'model': pi_model,
                'cores': cpu_count,
                'frequency': cpu_freq,
                'usage_percent': round(cpu_percent, 1)
            }
            
            return {
                'cpu_info': cpu_info,
                'cpu_usage': round(cpu_percent, 1),
                'cpu_count': cpu_count,
                'memory_usage': {
                    'used': round(memory.used / (1024**3), 2),
                    'total': round(memory.total / (1024**3), 2),
                    'percentage': round(memory.percent, 1)
                },
                'disk_usage': {
                    'used': round(disk.used / (1024**3), 2),
                    'total': round(disk.total / (1024**3), 2),
                    'percentage': round((disk.used / disk.total) * 100, 1)
                },
                'uptime': round(uptime, 1),
                'os_info': os_info,
                'ai_accelerator_info': ai_accelerator_info
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system info: {e}")
            return {
                'cpu_info': {
                    'architecture': 'Unknown',
                    'processor': 'Unknown',
                    'model': 'Unknown',
                    'cores': 0,
                    'frequency': 'Unknown',
                    'usage_percent': 0.0
                },
                'cpu_usage': 0.0,
                'cpu_count': 0,
                'memory_usage': {'used': 0.0, 'total': 0.0, 'percentage': 0.0},
                'disk_usage': {'used': 0.0, 'total': 0.0, 'percentage': 0.0},
                'uptime': 0.0,
                'os_info': {
                    'name': 'Unknown',
                    'distribution': 'Unknown',
                    'distribution_version': 'Unknown',
                    'kernel_version': 'Unknown',
                    'release': 'Unknown',
                    'version': 'Unknown',
                    'platform': 'Unknown',
                    'architecture': 'Unknown'
                },
                'ai_accelerator_info': {
                    'device_architecture': 'Unknown',
                    'firmware_version': 'Unknown',
                    'board_name': 'Unknown',
                    'status': 'Error'
                }
            }
    
    def _get_ai_accelerator_info(self) -> Dict[str, Any]:
        """
        Get AI Accelerator information using hailortcli command.
        
        Returns:
            Dict containing AI accelerator information
        """
        try:
            import subprocess
            self.logger.info("Attempting to get AI accelerator information...")
            
            # Run hailortcli fw-control identify command
            result = subprocess.run(
                ['hailortcli', 'fw-control', 'identify'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            self.logger.info(f"hailortcli command completed with return code: {result.returncode}")
            self.logger.info(f"hailortcli stdout: {result.stdout}")
            self.logger.info(f"hailortcli stderr: {result.stderr}")
            
            if result.returncode != 0:
                self.logger.warning(f"hailortcli command failed: {result.stderr}")
                return {
                    'device_architecture': 'Unknown',
                    'firmware_version': 'Unknown',
                    'board_name': 'Unknown',
                    'status': 'Not available'
                }
            
            # Parse the output
            output_lines = result.stdout.strip().split('\n')
            ai_info = {
                'device_architecture': 'Unknown',
                'firmware_version': 'Unknown',
                'board_name': 'Unknown',
                'status': 'Available'
            }
            
            for line in output_lines:
                line = line.strip()
                if line.startswith('Device Architecture:'):
                    ai_info['device_architecture'] = line.split(':', 1)[1].strip()
                elif line.startswith('Firmware Version:'):
                    ai_info['firmware_version'] = line.split(':', 1)[1].strip()
                elif line.startswith('Board Name:'):
                    ai_info['board_name'] = line.split(':', 1)[1].strip().replace('\x00', '')
            
            self.logger.info(f"Parsed AI accelerator info: {ai_info}")
            return ai_info
            
        except subprocess.TimeoutExpired:
            self.logger.warning("hailortcli command timed out")
            return {
                'device_architecture': 'Unknown',
                'firmware_version': 'Unknown',
                'board_name': 'Unknown',
                'status': 'Timeout'
            }
        except FileNotFoundError:
            self.logger.warning("hailortcli command not found")
            return {
                'device_architecture': 'Unknown',
                'firmware_version': 'Unknown',
                'board_name': 'Unknown',
                'status': 'Not installed'
            }
        except Exception as e:
            self.logger.error(f"Error getting AI accelerator info: {e}")
            return {
                'device_architecture': 'Unknown',
                'firmware_version': 'Unknown',
                'board_name': 'Unknown',
                'status': 'Error'
            }
    
    def get_health_logs(self, level: str = None, limit: int = 50, page: int = 1) -> Dict[str, Any]:
        """
        Get health check logs from database with pagination.
        
        Args:
            level: Log level filter (DEBUG, INFO, WARNING, ERROR)
            limit: Number of log entries per page (default: 50)
            page: Page number (default: 1)
            
        Returns:
            Dict containing health logs with pagination info
        """
        try:
            if not self.health_monitor:
                return {
                    'success': False,
                    'error': 'Health monitor not available',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Get all health checks first (for filtering and counting)
            all_logs = self.health_monitor.get_latest_health_checks(1000)  # Get more for filtering
            
            # Filter by level if specified
            if level:
                all_logs = [log for log in all_logs if log.get('status') == level.upper()]
            
            # Calculate pagination
            total_count = len(all_logs)
            total_pages = (total_count + limit - 1) // limit  # Ceiling division
            page = max(1, min(page, total_pages)) if total_pages > 0 else 1
            
            # Apply pagination
            start_index = (page - 1) * limit
            end_index = start_index + limit
            paginated_logs = all_logs[start_index:end_index]
            
            # Convert to log format
            formatted_logs = []
            for log in paginated_logs:
                formatted_log = {
                    'timestamp': log.get('timestamp'),
                    'level': log.get('status'),
                    'module': log.get('component'),
                    'message': log.get('message'),
                    'details': log.get('details')
                }
                formatted_logs.append(formatted_log)
            
            return {
                'success': True,
                'data': {
                    'logs': formatted_logs,
                    'pagination': {
                        'current_page': page,
                        'total_pages': total_pages,
                        'total_count': total_count,
                        'per_page': limit,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    },
                    'level_filter': level
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting health logs: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def start_monitoring(self, interval: int = None) -> bool:
        """
        Start continuous health monitoring.
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            bool: True if monitoring started successfully, False otherwise
        """
        try:
            if not self.health_monitor:
                self.logger.error("Health monitor not available")
                return False
            
            return self.health_monitor.start_monitoring(interval)
            
        except Exception as e:
            self.logger.error(f"Error starting health monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop continuous health monitoring."""
        try:
            if self.health_monitor:
                self.health_monitor.stop_monitoring()
        except Exception as e:
            self.logger.error(f"Error stopping health monitoring: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get health service status.
        
        Returns:
            Dict containing service status
        """
        return {
            'initialized': self.health_monitor is not None,
            'monitoring': self.health_monitor.running if self.health_monitor else False,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None
        }
    
    def cleanup(self):
        """Cleanup health service resources."""
        try:
            self.stop_monitoring()
            if self.health_monitor:
                self.health_monitor.cleanup()
            self.logger.info("HealthService cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during HealthService cleanup: {e}")
    
    def _setup_auto_start_monitoring(self):
        """Set up auto-start monitoring when camera and detection are ready."""
        try:
            # Start a background thread to monitor system status
            import threading
            import time
            from edge.src.core.config import AUTO_START_HEALTH_MONITOR, HEALTH_MONITOR_STARTUP_DELAY
            
            def auto_start_monitor():
                self.logger.info("🏥 Auto-start monitoring thread started - waiting for camera and detection to be ready...")
                
                # Initial delay before starting checks
                time.sleep(HEALTH_MONITOR_STARTUP_DELAY)
                
                check_count = 0
                max_checks = 30  # Maximum 30 checks (22.5 minutes with 45-second intervals)
                
                while check_count < max_checks:
                    try:
                        check_count += 1
                        
                        # Check if camera and detection are running
                        if self._should_start_monitoring():
                            self.logger.info("🎉 Camera and detection are ready - starting health monitoring")
                            success = self.start_monitoring(interval=60)
                            if success:
                                self.logger.info("✅ Health monitoring started successfully")
                            else:
                                self.logger.error("❌ Failed to start health monitoring")
                            break
                        else:
                            camera_status, detection_status = self._get_component_readiness()
                            self.logger.info(f"⏳ Waiting for components to be ready... (check {check_count}/{max_checks})")
                            self.logger.info(f"   Camera: {camera_status}, Detection: {detection_status}")
                        
                        # Wait 60 seconds before next check (increased for better detection initialization and reduced resource usage)
                        time.sleep(60)
                        
                    except Exception as e:
                        self.logger.error(f"Error in auto-start monitor: {e}")
                        time.sleep(30)
                
                if check_count >= max_checks:
                    self.logger.warning("⚠️ Auto-start monitoring timeout - components not ready after 22.5 minutes")
                    self.logger.info("🏥 Health monitoring will need to be started manually")
            
            # Start the monitoring thread
            monitor_thread = threading.Thread(target=auto_start_monitor, daemon=True, name="HealthAutoStart")
            monitor_thread.start()
            
            self.logger.info("✅ Auto-start monitoring thread started")
            
        except Exception as e:
            self.logger.error(f"Failed to setup auto-start monitoring: {e}")
    
    def _get_component_readiness(self) -> tuple:
        """Get detailed readiness status of camera and detection components."""
        try:
            # Get camera manager status
            camera_manager = get_service('camera_manager')
            camera_status = "unknown"
            if camera_manager:
                status = camera_manager.get_status()
                if status.get('initialized', False) and status.get('streaming', False):
                    camera_status = "ready"
                elif status.get('initialized', False):
                    camera_status = "initialized"
                else:
                    camera_status = "not_ready"
            
            # Get detection manager status using detection module patterns
            detection_manager = get_service('detection_manager')
            detection_status = "unknown"
            detection_details = []
            
            if detection_manager:
                status = detection_manager.get_status()
                
                # Check service running status
                service_running = status.get('service_running', False)
                thread_alive = status.get('thread_alive', False)
                
                # Check detection processor status
                processor_status = status.get('detection_processor_status', {})
                models_loaded = processor_status.get('models_loaded', False)
                
                if service_running and thread_alive and models_loaded:
                    detection_status = "ready"
                elif service_running and thread_alive:
                    detection_status = "running_no_models"
                    detection_details.append("service running but models not loaded")
                elif service_running:
                    detection_status = "service_only"
                    detection_details.append("service running but thread not alive")
                else:
                    detection_status = "not_ready"
                    detection_details.append("service not running")
                
                # Add model details
                if not models_loaded:
                    detection_details.append("models not loaded")
                
            else:
                detection_details.append("detection manager not available")
            
            # Log detailed detection status
            if detection_details:
                self.logger.debug(f"Detection details: {', '.join(detection_details)}")
            
            return camera_status, detection_status
            
        except Exception as e:
            self.logger.error(f"Error getting component readiness: {e}")
            return "error", "error"
    
    def _should_start_monitoring(self) -> bool:
        """Check if health monitoring should start automatically."""
        try:
            # Check camera manager directly
            camera_manager = get_service('camera_manager')
            camera_ready = False
            if camera_manager:
                status = camera_manager.get_status()
                camera_ready = (status.get('initialized', False) and 
                              status.get('streaming', False))
            
            # Check detection manager using proper detection patterns
            detection_manager = get_service('detection_manager')
            detection_ready = False
            if detection_manager:
                status = detection_manager.get_status()
                
                # Check if detection service is running (using detection module pattern)
                detection_ready = (
                    status.get('service_running', False) and  # Service is running
                    status.get('thread_alive', False) and     # Detection thread is alive
                    self._is_detection_processor_ready(status)  # Models are loaded and ready
                )
            
            self.logger.debug(f"Camera ready: {camera_ready}, Detection ready: {detection_ready}")
            
            return camera_ready and detection_ready
            
        except Exception as e:
            self.logger.error(f"Error checking if should start monitoring: {e}")
            return False
    
    def _is_detection_processor_ready(self, detection_status: Dict[str, Any]) -> bool:
        """Check if detection processor is ready using detection module patterns."""
        try:
            processor_status = detection_status.get('detection_processor_status', {})
            
            # Check if essential models are loaded (vehicle + LP detection).
            # lp_ocr_model_available and easyocr_available are optional — Tesseract is
            # used as OCR fallback and EasyOCR is never loaded on edge devices.
            models_ready = (
                processor_status.get('models_loaded', False) and
                processor_status.get('vehicle_model_available', False) and
                processor_status.get('lp_detection_model_available', False)
            )
            
            self.logger.debug(f"Detection processor models ready: {models_ready}")
            return models_ready
            
        except Exception as e:
            self.logger.error(f"Error checking detection processor readiness: {e}")
            return False


def create_health_service(health_monitor=None, logger=None):
    """
    Factory function to create HealthService instance.
    
    Args:
        health_monitor: HealthMonitor component instance
        logger: Logger instance
        
    Returns:
        HealthService: New HealthService instance
    """
    return HealthService(health_monitor, logger)
