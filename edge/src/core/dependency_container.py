#!/usr/bin/env python3
"""
Dependency Injection Container for AI Camera v1.3

This module implements a dependency injection container to manage all
core components and their dependencies in a modular using absolute imports.

Components managed:
- CameraManager (Picamera2 integration)
- DetectionManager (Hailo AI models)
- VideoStreaming (Real-time video streaming)
- HealthMonitor (System health monitoring)
- WebSocketSender (Server communication)
- FlaskApp (Web interface)

Author: AI Camera Team
Version: 1.3
Date: August 7, 2025
"""

from edge.src.core.utils.logging_config import get_logger
from typing import Dict, Any, Optional, Type, TypeVar
import logging
from dataclasses import dataclass
from pathlib import Path

# Import config values lazily to avoid circular imports
from edge.src.core.config import (
    FLASK_HOST, FLASK_PORT, SECRET_KEY,
    VEHICLE_DETECTION_MODEL, LICENSE_PLATE_DETECTION_MODEL,
    EASYOCR_LANGUAGES, IMAGE_SAVE_DIR, DETECTION_INTERVAL,
    WEBSOCKET_SENDER_ENABLED, STORAGE_MONITOR_ENABLED,
    EXPERIMENT_ENABLED
)
from edge.src.core.config_communication import MQTT_ENABLED

T = TypeVar('T')


@dataclass
class ServiceConfig:
    """Configuration for a service in the DI container."""
    service_type: Type
    singleton: bool = True
    factory: Optional[callable] = None
    dependencies: Optional[Dict[str, str]] = None


class DependencyContainer:
    """
    Dependency Injection Container for managing service dependencies.
    
    This container manages the lifecycle and dependencies of all core
    components in the AI Camera system using absolute imports.
    
    Attributes:
        services (Dict[str, ServiceConfig]): Registered services
        instances (Dict[str, Any]): Singleton instances
        logger (logging.Logger): Logger instance
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the dependency container.
        
        Args:
            logger (Optional[logging.Logger]): Logger instance
        """
        self.services: Dict[str, ServiceConfig] = {}
        self.instances: Dict[str, Any] = {}
        self.logger = logger or get_logger(__name__)
        
        # Register default services
        self._register_default_services()

    def _register_experiment_services(self):
        """ลงทะเบียน Experiment services"""
        if EXPERIMENT_ENABLED:
            try:
                from edge.src.components.experiment_isolator import ExperimentIsolator
                from edge.src.services.experiment_service import ExperimentService, create_experiment_service
                
                # ลงทะเบียน Experiment Isolator
                self.register_service('experiment_isolator', ExperimentIsolator, 
                                    singleton=True, dependencies={
                                        'camera_manager': 'camera_manager',
                                        'detection_manager': 'detection_manager'
                                    })
                
                # ลงทะเบียน Experiment Service
                self.register_service('experiment_service', ExperimentService, 
                                    singleton=True, 
                                    factory=create_experiment_service,
                                    dependencies={
                                        'camera_manager': 'camera_manager',
                                        'detection_processor': 'detection_processor',
                                        'isolator': 'experiment_isolator'
                                    })
                
                self.logger.info("Experiment services registered successfully")
                
            except ImportError as e:
                self.logger.warning(f"Experiment services not available: {e}")
            except Exception as e:
                self.logger.error(f"Error registering experiment services: {e}")
        else:
            self.logger.info("Experiment services not registered (disabled in config)")

    def _register_default_services(self):
        """Register default services with their configurations using absolute imports."""
        # Core components - ALWAYS REGISTERED
        self.register_service('logger', logging.Logger, singleton=True,
                        factory=self._create_logger)
        self.register_service('config', dict, singleton=True, 
                            factory=self._create_config)
        
        # === CORE MODULES (Essential) ===
        # Register core components using absolute imports
        try:
            from edge.src.components.detection_processor import DetectionProcessor
            self.register_service('detection_processor', DetectionProcessor, 
                                singleton=True, dependencies={'logger': 'logger'})
        except ImportError:
            self.logger.warning("DetectionProcessor not available")
        
        try:
            from edge.src.components.camera_handler import CameraHandler
            self.register_service('camera_handler', CameraHandler, 
                                singleton=True, 
                                dependencies={})  # CameraHandler manages its own logger
        except ImportError:
            self.logger.warning("CameraHandler not available")
        
        try:
            from edge.src.components.health_monitor import HealthMonitor
            self.register_service('health_monitor', HealthMonitor, 
                                singleton=True, dependencies={'logger': 'logger'})
        except ImportError:
            self.logger.warning("HealthMonitor not available")
        
        try:
            from edge.src.components.database_manager import DatabaseManager
            self.register_service('database_manager', DatabaseManager, 
                                singleton=True, dependencies={'logger': 'logger'})
        except ImportError:
            self.logger.warning("DatabaseManager not available")
        
        # Register core service layer components using absolute imports
        try:
            from edge.src.services.camera_manager import CameraManager, create_camera_manager
            self.register_service('camera_manager', CameraManager, 
                                singleton=True, 
                                factory=create_camera_manager,
                                dependencies={'camera_handler': 'camera_handler', 'logger': 'logger'})
        except ImportError as e:
            self.logger.warning(f"CameraManager service not available: {e}")
        
        try:
            from edge.src.services.detection_manager import DetectionManager, create_detection_manager
            self.register_service('detection_manager', DetectionManager, 
                                singleton=True,
                                factory=create_detection_manager,
                                dependencies={'detection_processor': 'detection_processor',
                                            'database_manager': 'database_manager',
                                            'logger': 'logger'})
        except ImportError:
            self.logger.warning("DetectionManager service not available")
        
        try:
            from edge.src.services.video_streaming import VideoStreamingService, create_video_streaming_service
            self.register_service('video_streaming', VideoStreamingService, 
                                singleton=True,
                                factory=create_video_streaming_service,
                                dependencies={'camera_manager': 'camera_manager',
                                            'logger': 'logger'})
        except ImportError:
            self.logger.warning("VideoStreamingService not available")
        
        try:
            from edge.src.services.health_service import HealthService, create_health_service
            self.register_service('health_service', HealthService, 
                                singleton=True,
                                factory=create_health_service,
                                dependencies={'health_monitor': 'health_monitor', 'logger': 'logger'})
        except ImportError as e:
            self.logger.warning(f"HealthService not available: {e}")
        
        # === OPTIONAL MODULES (Can be disabled) ===
        # Register optional modules only if enabled in configuration
        
        # WebSocket Sender (Optional)
        if WEBSOCKET_SENDER_ENABLED:
            try:
                from edge.src.services.websocket_sender import WebSocketSender, create_websocket_sender
                self.register_service('websocket_sender', WebSocketSender, 
                                    singleton=True,
                                    factory=create_websocket_sender,
                                    dependencies={'database_manager': 'database_manager', 'logger': 'logger'})
                self.logger.info("WebSocket Sender registered (enabled in config)")
            except ImportError:
                self.logger.warning("WebSocketSender not available")
        else:
            self.logger.info("WebSocket Sender not registered (disabled in config)")

        # MQTT Health Sender (Optional - sends health status via MQTT)
        if MQTT_ENABLED:
            try:
                from edge.src.services.mqtt_health_sender import MqttHealthSender, create_mqtt_health_sender
                self.register_service('mqtt_health_sender', MqttHealthSender,
                                    singleton=True,
                                    factory=create_mqtt_health_sender,
                                    dependencies={'database_manager': 'database_manager', 'logger': 'logger'})
                self.logger.info("MQTT Health Sender registered (enabled in config)")
            except ImportError as e:
                self.logger.warning("MqttHealthSender not available: %s", e)
        else:
            self.logger.info("MQTT Health Sender not registered (MQTT disabled)")
        
        # Storage Management (Optional)
        if STORAGE_MONITOR_ENABLED:
            try:
                from edge.src.components.storage_monitor import StorageMonitor
                self.register_service('storage_monitor', StorageMonitor, 
                                    singleton=True, dependencies={'logger': 'logger'})
                
                # Register storage service after storage monitor
                try:
                    from edge.src.services.storage_service import StorageService, create_storage_service
                    self.register_service('storage_service', StorageService, 
                                        singleton=True,
                                        factory=create_storage_service,
                                        dependencies={'storage_monitor': 'storage_monitor', 'logger': 'logger'})
                    self.logger.info("Storage Service registered (enabled in config)")
                except ImportError as e:
                    self.logger.warning(f"StorageService not available: {e}")
                    
            except ImportError:
                self.logger.warning("StorageMonitor not available")
        else:
            self.logger.info("Storage Management not registered (disabled in config)")
        
        # Browser Connection Manager (Optional - For tracking only)
        try:
            from edge.src.services.browser_connection_manager import BrowserConnectionManager, create_browser_connection_manager
            self.register_service('browser_connection_manager', BrowserConnectionManager, 
                                singleton=True,
                                factory=create_browser_connection_manager,
                                dependencies={})  # No dependencies to avoid conflicts
            self.logger.info("BrowserConnectionManager registered (tracking only)")
        except ImportError as e:
            self.logger.warning(f"BrowserConnectionManager not available: {e}")
        
        # Experiment Service (Optional)
        self._register_experiment_services()
            
    def _create_logger(self, **kwargs) -> logging.Logger:
        """Create a logger instance."""
        return get_logger('aicamera_lpr')

    def _create_config(self) -> Dict[str, Any]:
        """Create application configuration using absolute imports."""
        return {
            'flask_host': FLASK_HOST,
            'flask_port': FLASK_PORT,
            'secret_key': SECRET_KEY,
            'vehicle_detection_model': VEHICLE_DETECTION_MODEL,
            'license_plate_detection_model': LICENSE_PLATE_DETECTION_MODEL,
            'easyocr_languages': EASYOCR_LANGUAGES,
            'image_save_dir': IMAGE_SAVE_DIR,
            'detection_interval': DETECTION_INTERVAL
        }
    
    def register_service(self, name: str, service_type: Type[T], 
                        singleton: bool = True, 
                        factory: Optional[callable] = None,
                        dependencies: Optional[Dict[str, str]] = None) -> None:
        """
        Register a service in the container.
        
        Args:
            name (str): Service name
            service_type (Type[T]): Service class type
            singleton (bool): Whether to create singleton instances
            factory (Optional[callable]): Factory function for creating instances
            dependencies (Optional[Dict[str, str]]): Service dependencies
        """
        self.services[name] = ServiceConfig(
            service_type=service_type,
            singleton=singleton,
            factory=factory,
            dependencies=dependencies
        )
        self.logger.debug(f"Registered service: {name} ({service_type.__name__})")
    
    def get_service(self, name: str) -> Any:
        """
        Get a service instance from the container.
        
        Args:
            name (str): Service name
            
        Returns:
            Any: Service instance
            
        Raises:
            KeyError: If service is not registered
            Exception: If service creation fails
        """
        if name not in self.services:
            raise KeyError(f"Service '{name}' not registered")
        
        service_config = self.services[name]
        
        # Return existing singleton instance
        if service_config.singleton and name in self.instances:
            return self.instances[name]
        
        # Create new instance
        instance = self._create_service_instance(name, service_config)
        
        # Store singleton instance
        if service_config.singleton:
            self.instances[name] = instance
        
        return instance
    
    def _create_service_instance(self, name: str, service_config: ServiceConfig) -> Any:
        """
        Create a service instance with its dependencies.
        
        Args:
            name (str): Service name
            service_config (ServiceConfig): Service configuration
            
        Returns:
            Any: Created service instance
        """
        try:
            # Resolve dependencies
            dependencies = {}
            if service_config.dependencies:
                for param_name, service_name in service_config.dependencies.items():
                    dependencies[param_name] = self.get_service(service_name)
            
            # Create instance using factory or constructor
            if service_config.factory:
                instance = service_config.factory(**dependencies)
            else:
                instance = service_config.service_type(**dependencies)
            
            self.logger.debug(f"Created instance of {name}: {type(instance).__name__}")
            return instance
            
        except Exception as e:
            self.logger.error(f"Failed to create service '{name}': {e}")
            raise
    
    def get_service_type(self, name: str) -> Type:
        """
        Get the type of a registered service.
        
        Args:
            name (str): Service name
            
        Returns:
            Type: Service type
        """
        if name not in self.services:
            raise KeyError(f"Service '{name}' not registered")
        return self.services[name].service_type
    
    def has_service(self, name: str) -> bool:
        """
        Check if a service is registered.
        
        Args:
            name (str): Service name
            
        Returns:
            bool: True if service is registered
        """
        return name in self.services
    
    def get_registered_services(self) -> Dict[str, Type]:
        """
        Get all registered services.
        
        Returns:
            Dict[str, Type]: Dictionary of service names and types
        """
        return {name: config.service_type for name, config in self.services.items()}
    
    def clear_instances(self):
        """Clear all singleton instances."""
        self.instances.clear()
        self.logger.debug("Cleared all service instances")
    
    def shutdown(self):
        """Shutdown the container and cleanup resources."""
        self.logger.info("Shutting down dependency container")
        
        # Call cleanup methods on services that have them
        for name, instance in self.instances.items():
            if hasattr(instance, 'cleanup'):
                try:
                    instance.cleanup()
                    self.logger.debug(f"Cleaned up service: {name}")
                except Exception as e:
                    self.logger.error(f"Error cleaning up service '{name}': {e}")
        
        self.clear_instances()
        self.logger.info("Dependency container shutdown complete")


# Global container instance
_container: Optional[DependencyContainer] = None


def get_container() -> DependencyContainer:
    """
    Get the global dependency container instance.
    
    Returns:
        DependencyContainer: Global container instance
    """
    global _container
    if _container is None:
        _container = DependencyContainer()
    return _container


def register_service(name: str, service_type: Type[T], **kwargs) -> None:
    """
    Register a service in the global container.
    
    Args:
        name (str): Service name
        service_type (Type[T]): Service class type
        **kwargs: Additional registration parameters
    """
    container = get_container()
    container.register_service(name, service_type, **kwargs)


def get_service(name: str) -> Any:
    """
    Get a service from the global container.
    
    Args:
        name (str): Service name
        
    Returns:
        Any: Service instance
    """
    container = get_container()
    return container.get_service(name)


def shutdown_container():
    """Shutdown the global dependency container."""
    global _container
    if _container:
        _container.shutdown()
        _container = None
