#!/usr/bin/env python3
"""
Logging Configuration Utility for AI Camera v2

This module provides centralized logging configuration for the entire
application with support for different log levels, file rotation,
and structured logging. Includes internal log rotation at 00:01 daily.

Author: AI Camera Team
Version: 2
Date: September 12, 2025
"""

import os
import logging
import logging.handlers
from logging.handlers import TimedRotatingFileHandler
import sys
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from collections import defaultdict


def setup_logging(
    level: str = "DEBUG",
    log_dir: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 3
) -> logging.Logger:
    """
    Setup logging configuration with internal daily rotation at 00:01.
    
    Args:
        level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir (Optional[str]): Directory for log files
        max_bytes (int): Maximum size of log file before rotation
        backup_count (int): Number of backup log files to keep
    
    Returns:
        logging.Logger: Configured logger
    """
    # Use centralized log directory at edge/logs (not edge/src/logs)
    if log_dir is None:
        # Point to edge/logs directory (ไม่ใช่ edge/src/logs)
        current_file = Path(__file__)  # edge/src/core/utils/logging_config.py
        project_root = current_file.parent.parent.parent.parent  # ขึ้นไป 4 ระดับถึง /home/camuser/aicamera
        log_dir = project_root / "logs"
    
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Use single log file with date rotation
    log_file = log_dir / "aicamera.log"
    # Dedicated communication log file (HTTP/WebSocket/Network comms)
    comm_log_file = log_dir / "unified_comm.log"

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {level}')
    
    # Create formatters - shorter, cleaner messages
    detailed_formatter = logging.Formatter(
        '%(asctime)s %(filename)s:%(lineno)d - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s %(message)s'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    # Console: แสดงเฉพาะ WARNING/ERROR เป็นค่าปริยาย เพื่อลด noise
    console_handler.setLevel(logging.WARNING)
    root_logger.addHandler(console_handler)
    
    # Custom filter: suppress known noisy third-party messages
    class MessageSuppressFilter(logging.Filter):
        SUPPRESS_SUBSTRINGS = (
            'Neither CUDA nor MPS are available - defaulting to CPU',
            'This module is much faster with a GPU',
            'Using CPU. Note: This module is much faster with a GPU',
        )
        def filter(self, record: logging.LogRecord) -> bool:
            msg = str(record.getMessage())
            return not any(s in msg for s in self.SUPPRESS_SUBSTRINGS)

    # Add file handler with daily rotation at 00:01
    try:
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when='midnight',        # Rotate at midnight
            interval=1,             # Daily
            backupCount=backup_count,  # Keep specified number of backups
            encoding='utf-8',
            atTime=datetime.strptime('00:01', '%H:%M').time()  # Rotate at 00:01
        )
        file_handler.setFormatter(detailed_formatter)
        file_handler.setLevel(logging.INFO)
        file_handler.addFilter(MessageSuppressFilter())
        root_logger.addHandler(file_handler)

        # Communication-specific file handler (separate file)
        comm_file_handler = TimedRotatingFileHandler(
            filename=str(comm_log_file),
            when='midnight',
            interval=1,
            backupCount=backup_count,
            encoding='utf-8',
            atTime=datetime.strptime('00:01', '%H:%M').time()
        )
        comm_file_handler.setFormatter(detailed_formatter)
        comm_file_handler.setLevel(logging.INFO)
        comm_file_handler.addFilter(StartStopInfoFilter())
        comm_file_handler.addFilter(MessageSuppressFilter())
        # Use a dedicated named logger for communication to avoid duplicating root logs
        comm_logger = logging.getLogger('communication')
        comm_logger.setLevel(logging.INFO)
        comm_logger.propagate = False  # prevent double logging to aicamera.log
        # Clear existing handlers to avoid duplicates on re-init
        for h in comm_logger.handlers[:]:
            comm_logger.removeHandler(h)
        comm_logger.addHandler(comm_file_handler)
        
        # Start background thread for log rotation management
        _start_log_rotation_manager(log_dir, backup_count)
        
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")
    
    # Suppress noisy third-party library logs
    logging.getLogger('picamera2').setLevel(logging.WARNING)
    logging.getLogger('libcamera').setLevel(logging.WARNING)
    logging.getLogger('libcamera._libcamera').setLevel(logging.WARNING)
    logging.getLogger('socketio').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    # Reduce third-party OCR/ML libraries
    logging.getLogger('easyocr').setLevel(logging.ERROR)
    logging.getLogger('easyocr.easyocr').setLevel(logging.ERROR)
    logging.getLogger('torch').setLevel(logging.ERROR)
    logging.getLogger('transformers').setLevel(logging.ERROR)
    
    # Log initial message to verify logging is working
    # ข้อความเริ่มต้นยังคงถูกบันทึก (เข้าข่าย start event)
    root_logger.info("Application Initialized")  # รายงานเริ่มทำงาน
    
    return root_logger


def _start_log_rotation_manager(log_dir: Path, backup_count: int):
    """Start background thread for log rotation management."""
    def rotation_manager():
        while True:
            try:
                # Wait until next 00:01
                now = datetime.now()
                next_rotation = now.replace(hour=0, minute=1, second=0, microsecond=0)
                if next_rotation <= now:
                    next_rotation += timedelta(days=1)
                
                sleep_seconds = (next_rotation - now).total_seconds()
                time.sleep(sleep_seconds)
                
                # Perform log rotation cleanup
                _cleanup_old_logs(log_dir, backup_count)
                
            except Exception as e:
                print(f"Error in log rotation manager: {e}")
                time.sleep(3600)  # Wait 1 hour before retrying
    
    # Start the rotation manager in a daemon thread
    rotation_thread = threading.Thread(target=rotation_manager, daemon=True)
    rotation_thread.start()

def _cleanup_old_logs(log_dir: Path, backup_count: int):
    """Clean up old log files beyond retention period."""
    try:
        # Patterns to clean up (mirror rotation policy)
        patterns = [
            "aicamera.log.*",
            "unified_comm.log.*",
        ]
        for pattern in patterns:
            rotated_files = list(log_dir.glob(pattern))
            if len(rotated_files) > backup_count:
                rotated_files.sort(key=lambda x: x.stat().st_mtime)
                files_to_remove = rotated_files[:-backup_count]
                for log_file in files_to_remove:
                    try:
                        log_file.unlink()
                        print(f"Deleted old log file: {log_file}")
                    except Exception as e:
                        print(f"Failed to delete old log file {log_file}: {e}")
                    
    except Exception as e:
        print(f"Error during log cleanup: {e}")
    

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.
    
    Args:
        name (str): Logger name
    
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)


# ============================================================================
# OPTIMIZED LOGGING UTILITIES FOR REDUCED LOG FREQUENCY
# ============================================================================

class RateLimitedLogger:
    """
    Logger wrapper that implements rate limiting for repetitive log messages.
    """
    
    def __init__(self, logger: logging.Logger, default_interval: float = 5.0):
        self.logger = logger
        self.default_interval = default_interval
        self.last_log_times: Dict[str, float] = {}
        self.log_counts: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()
    
    def _should_log(self, key: str, interval: float = None) -> bool:
        """Check if enough time has passed since last log for this key."""
        if interval is None:
            interval = self.default_interval
            
        with self.lock:
            current_time = time.time()
            last_time = self.last_log_times.get(key, 0)
            
            if current_time - last_time >= interval:
                self.last_log_times[key] = current_time
                self.log_counts[key] += 1
                return True
            return False
    
    def info_rate_limited(self, key: str, message: str, interval: float = None):
        """Log info message with rate limiting."""
        if self._should_log(key, interval):
            count = self.log_counts[key]
            if count > 1:
                message = f"{message} (logged {count} times)"
            self.logger.info(message)
    
    def debug_rate_limited(self, key: str, message: str, interval: float = None):
        """Log debug message with rate limiting."""
        if self._should_log(key, interval):
            count = self.log_counts[key]
            if count > 1:
                message = f"{message} (logged {count} times)"
            self.logger.debug(message)
    
    def warning_rate_limited(self, key: str, message: str, interval: float = None):
        """Log warning message with rate limiting."""
        if self._should_log(key, interval):
            count = self.log_counts[key]
            if count > 1:
                message = f"{message} (logged {count} times)"
            self.logger.warning(message)
    
    def error_rate_limited(self, key: str, message: str, interval: float = None):
        """Log error message with rate limiting."""
        if self._should_log(key, interval):
            count = self.log_counts[key]
            if count > 1:
                message = f"{message} (logged {count} times)"
            self.logger.error(message)


class StateChangeLogger:
    """
    Logger that only logs when state actually changes.
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.last_states: Dict[str, Any] = {}
        self.lock = threading.Lock()
    
    def log_state_change(self, key: str, new_state: Any, message_template: str):
        """Log only when state changes from previous value."""
        with self.lock:
            last_state = self.last_states.get(key)
            
            if last_state != new_state:
                self.last_states[key] = new_state
                message = message_template.format(state=new_state, previous=last_state)
                self.logger.info(message)
                return True
            return False
    
    def log_status_change(self, component: str, status: str, details: str = ""):
        """Log component status changes."""
        key = f"{component}_status"
        message_template = f"{component} status changed to: {{state}}"
        if details:
            message_template += f" - {details}"
        return self.log_state_change(key, status, message_template)


class IterationLogger:
    """
    Logger optimized for iteration loops with minimal changes.
    """
    
    def __init__(self, logger: logging.Logger, summary_interval: int = 100):
        self.logger = logger
        self.summary_interval = summary_interval
        self.iteration_counts: Dict[str, int] = defaultdict(int)
        self.last_summary_times: Dict[str, float] = {}
        self.lock = threading.Lock()
    
    def log_iteration_start(self, loop_name: str, message: str = None):
        """Log iteration start with rate limiting."""
        with self.lock:
            self.iteration_counts[loop_name] += 1
            count = self.iteration_counts[loop_name]
            
            # Log start only on first iteration or every summary_interval
            if count == 1 or count % self.summary_interval == 0:
                if message:
                    self.logger.info(f"{loop_name}: {message} (iteration {count})")
                else:
                    self.logger.info(f"{loop_name} started (iteration {count})")
    
    def log_iteration_summary(self, loop_name: str, stats: Dict[str, Any]):
        """Log periodic summary of iteration statistics."""
        with self.lock:
            current_time = time.time()
            last_time = self.last_summary_times.get(loop_name, 0)
            
            # Log summary every 30 seconds minimum
            if current_time - last_time >= 30:
                self.last_summary_times[loop_name] = current_time
                count = self.iteration_counts[loop_name]
                
                stats_str = ", ".join([f"{k}: {v}" for k, v in stats.items()])
                self.logger.info(f"{loop_name} summary (iterations: {count}): {stats_str}")
    
    def log_iteration_error(self, loop_name: str, error: Exception, context: str = ""):
        """Log iteration errors with rate limiting."""
        error_key = f"{loop_name}_error"
        error_msg = f"{loop_name} error: {error}"
        if context:
            error_msg += f" (context: {context})"
        
        # Use rate limiting for errors (max once per minute)
        rate_limited_logger = RateLimitedLogger(self.logger, 60.0)
        rate_limited_logger.error_rate_limited(error_key, error_msg)


class ComponentLogger:
    """
    Specialized logger for different components with optimized logging patterns.
    """
    
    def __init__(self, component_name: str, logger: logging.Logger):
        self.component_name = component_name
        self.logger = logger
        self.rate_limited = RateLimitedLogger(logger)
        self.state_change = StateChangeLogger(logger)
        self.iteration = IterationLogger(logger)
    
    def log_initialization(self, message: str = None):
        """Log component initialization."""
        if message:
            self.logger.info(f"[{self.component_name}] {message}")
        else:
            self.logger.info(f"[{self.component_name}] Initialized")
    
    def log_operation_start(self, operation: str):
        """Log operation start with rate limiting."""
        self.rate_limited.info_rate_limited(
            f"{self.component_name}_{operation}_start",
            f"[{self.component_name}] {operation} started",
            interval=10.0  # Log max once per 10 seconds
        )
    
    def log_operation_success(self, operation: str, details: str = ""):
        """Log operation success with rate limiting."""
        message = f"[{self.component_name}] {operation} successful"
        if details:
            message += f" - {details}"
        
        self.rate_limited.info_rate_limited(
            f"{self.component_name}_{operation}_success",
            message,
            interval=5.0
        )
    
    def log_operation_error(self, operation: str, error: Exception):
        """Log operation errors with rate limiting."""
        self.rate_limited.warning_rate_limited(
            f"{self.component_name}_{operation}_error",
            f"[{self.component_name}] {operation} error: {error}",
            interval=30.0  # Log max once per 30 seconds
        )
    
    def log_status_change(self, status: str, details: str = ""):
        """Log status changes only when they occur."""
        self.state_change.log_status_change(self.component_name, status, details)
    
    def log_iteration_stats(self, stats: Dict[str, Any]):
        """Log iteration statistics with rate limiting."""
        self.iteration.log_iteration_summary(self.component_name, stats)


# Component-specific logger factory functions
def get_camera_logger(logger: logging.Logger) -> ComponentLogger:
    """Get optimized logger for camera component."""
    return ComponentLogger("CAMERA", logger)

def get_detection_logger(logger: logging.Logger) -> ComponentLogger:
    """Get optimized logger for detection component."""
    return ComponentLogger("DETECTION", logger)

def get_health_logger(logger: logging.Logger) -> ComponentLogger:
    """Get optimized logger for health monitor component."""
    return ComponentLogger("HEALTH", logger)

def get_database_logger(logger: logging.Logger) -> ComponentLogger:
    """Get optimized logger for database component."""
    return ComponentLogger("DATABASE", logger)

def get_websocket_logger(logger: logging.Logger) -> ComponentLogger:
    """Get optimized logger for websocket sender component."""
    return ComponentLogger("WEBSOCKET", logger)


def configure_production_logging(logger: logging.Logger, log_level: str = "INFO"):
    """
    Configure logging for production with reduced verbosity.
    
    Args:
        logger: Logger instance
        log_level: Base log level for production
    """
    # Set base level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    
    # Reduce verbosity for specific noisy loggers
    noisy_loggers = [
        'picamera2',
        'libcamera',
        'libcamera._libcamera',
        'urllib3',
        'requests',
        'socketio',
        'engineio',
        'werkzeug'
    ]
    
    for noisy_logger in noisy_loggers:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    
    # Optimize component-specific loggers
    component_loggers = [
        'edge.src.components.camera_handler',
        'edge.src.components.detection_processor',
        'edge.src.components.health_monitor',
        'edge.src.components.database_manager',
        'edge.src.services.websocket_sender'
    ]
    
    for component_logger in component_loggers:
        comp_logger = logging.getLogger(component_logger)
        # Keep INFO level but reduce DEBUG verbosity
        comp_logger.setLevel(logging.INFO)

