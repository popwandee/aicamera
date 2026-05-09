#!/usr/bin/env python3
"""
Configuration file for AI Camera v1.3

This file provides default configuration values for the system.

Author: AI Camera Team
Version: 2
Date: December 2024
"""

import os
from pathlib import Path

# Load environment variables from .env.production first
def load_env_file():
    """Load environment variables from .env.production file."""
    env_file = Path(__file__).parent.parent.parent / 'installation' / '.env.production'
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

# Flask Configuration
FLASK_HOST =  '0.0.0.0'
FLASK_PORT = int(5000)
SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key-change-in-production')
DEBUG = "DEBUG"

# Base directory for the project - should be /home/camuser/aicamera/
current_file = Path(__file__)
BASE_DIR = str(current_file.parent.parent.parent.parent.absolute())  # Go up from core/src/edge/aicamera

# Database configuration
DATABASE_PATH = os.path.join(BASE_DIR, 'edge', 'db', 'lpr_data.db')
WEBSOCKET_LOG_FILE = os.path.join(BASE_DIR, "edge", "logs", "websocket.log")
DETECTION_LOG_FILE = os.path.join(BASE_DIR, "edge", "logs", "detection.log")
# AI Models Configuration
HEF_MODEL_PATH = "@local"
MODEL_ZOO_URL = os.path.join(BASE_DIR, 'resources') 
VEHICLE_DETECTION_MODEL = os.getenv("VEHICLE_DETECTION_MODEL", "yolov8n_relu6_car--640x640_quant_hailort_hailo8_1")
LICENSE_PLATE_DETECTION_MODEL = os.getenv("LICENSE_PLATE_DETECTION_MODEL", "yolov8n_relu6_lp--640x640_quant_hailort_hailo8_1")
LICENSE_PLATE_OCR_MODEL = os.getenv("LICENSE_PLATE_OCR_MODEL", "yolov8n_relu6_lp_ocr--256x128_quant_hailort_hailo8_1")
OCR_MODEL = os.getenv("OCR_MODEL", "easyOCR_raw_image") 

# OCR Configuration
EASYOCR_LANGUAGES = ['en', 'th']

# Image Storage - Can be overridden via environment variables
raw_dir = os.getenv("IMAGE_SAVE_DIR")
if raw_dir:
    IMAGE_SAVE_DIR = raw_dir if os.path.isabs(raw_dir) else os.path.join(BASE_DIR, 'edge', raw_dir)
else:
    IMAGE_SAVE_DIR = os.path.join(BASE_DIR, 'edge', 'captured_images')

# WebSocket server configuration
WEBSOCKET_SERVER_URL = os.getenv("WEBSOCKET_SERVER_URL")

# AI Camera Identification - Can be overridden via environment variables
AICAMERA_ID = os.getenv("AICAMERA_ID", "1")
CHECKPOINT_ID = os.getenv("CHECKPOINT_ID", "1")
CAMERA_NAME = os.getenv("CAMERA_NAME", "")
CAMERA_IP = os.getenv("CAMERA_IP", "")
LOCATION_LAT = os.getenv("LOCATION_LAT", "13.729610")
LOCATION_LON = os.getenv("LOCATION_LON", "100.501443")
CAMERA_LOCATION = os.getenv("CAMERA_LOCATION", "Main Entrance")

# Camera properties defaults - Can be overridden via environment variables
HIGH_QUALITY_CAPTURE_RESOLUTION = tuple(map(int, os.getenv("HIGH_QUALITY_CAPTURE_RESOLUTION", "2304x1296").split('x')))
DETECTION_RESOLUTION = tuple(map(int, os.getenv("DETECTION_RESOLUTION", "640x640").split('x')))
QUALITY_ENHANCEMENT_ENABLED = os.getenv("QUALITY_ENHANCEMENT_ENABLED", "true").lower() == "true"
DEFAULT_RESOLUTION = tuple(map(int, os.getenv("CAMERA_RESOLUTION", "640x640").split('x')))

# Camera focus control - Can be overridden via environment variables
CAMERA_FOCUS_MODE = os.getenv("CAMERA_FOCUS_MODE", "auto")  # "auto" or "manual"
CAMERA_MANUAL_FOCUS = float(os.getenv("CAMERA_MANUAL_FOCUS", "0.3"))  # 0.0 to 1.0

# Main and Lores stream resolutions - Can be overridden via environment variables
MAIN_RESOLUTION = tuple(map(int, os.getenv("MAIN_RESOLUTION", "640x640").split('x')))
LORES_RESOLUTION = tuple(map(int, os.getenv("LORES_RESOLUTION", "640x480").split('x')))  # LPR optimized: 640x640 for web preview/streaming
DEFAULT_FRAMERATE = int(os.getenv("CAMERA_FPS", "30"))
DEFAULT_BRIGHTNESS = float(os.getenv("CAMERA_BRIGHTNESS", "0.0"))  # -1.0 to 1.0
DEFAULT_CONTRAST = float(os.getenv("CAMERA_CONTRAST", "1.0"))    # 0.0 to 2.0
DEFAULT_SATURATION = float(os.getenv("CAMERA_SATURATION", "1.0"))  # 0.0 to 2.0
DEFAULT_SHARPNESS = float(os.getenv("CAMERA_SHARPNESS", "2.0"))   # 0.0 to 4.0 (Increased from 1.0 for better sharpness, matching rpicam default)
DEFAULT_AWB_MODE = int(os.getenv("CAMERA_AWB_MODE", "0"))      # 0=auto, 1=fluorescent, etc.
DEFAULT_NOISE_REDUCTION_MODE = int(os.getenv("CAMERA_NOISE_REDUCTION_MODE", "0"))  # 0=Off, 1=Normal, 2=HighQuality (0=Off for maximum sharpness)
DEFAULT_AUTOFOCUS_MODE = int(os.getenv("DEFAULT_AUTOFOCUS_MODE", "1"))  # 0=Manual, 1=Auto, 2=Continuous (Changed from 2 to 1 for better focus stability, matching rpicam)
DEFAULT_AUTOFOCUS_ENABLED = os.getenv("DEFAULT_AUTOFOCUS_ENABLED", "true").lower() == "true"
# Camera sensor type — controls NoIR IR compensation
# "imx708"      = standard sensor with IR cut filter (aicamera1)
# "imx708_noir" = no IR cut filter, needs software colour correction (aicamera2)
CAMERA_SENSOR_TYPE = os.getenv("CAMERA_SENSOR_TYPE", "imx708")
# NoIR software colour correction via picamera2 ColourGains — only used when CAMERA_SENSOR_TYPE=imx708_noir
NOIR_AWB_ENABLED = os.getenv("NOIR_AWB_ENABLED", "false").lower() == "true"
NOIR_COLOUR_GAIN_RED = float(os.getenv("NOIR_COLOUR_GAIN_RED", "1.8"))
NOIR_COLOUR_GAIN_BLUE = float(os.getenv("NOIR_COLOUR_GAIN_BLUE", "2.6"))
AUTOFOCUS_TRIGGER_BEFORE_CAPTURE = os.getenv("AUTOFOCUS_TRIGGER_BEFORE_CAPTURE", "false").lower() == "true"  # Trigger AF before important captures
FOCUS_QUALITY_MIN_THRESHOLD = int(os.getenv("FOCUS_QUALITY_MIN_THRESHOLD", "150"))  # Minimum FocusFoM; IMX708 outdoor max ≈230
DEFAULT_QUALITY_MONITORING = os.getenv("DEFAULT_QUALITY_MONITORING", "enabled")
FOCUS_HEALTH_ENABLED = os.getenv("FOCUS_HEALTH_ENABLED", "true").lower() == "true"
FOCUS_HEALTH_DURATION = float(os.getenv("FOCUS_HEALTH_DURATION", "3.0"))
FOCUS_HEALTH_MIN_SAMPLES = int(os.getenv("FOCUS_HEALTH_MIN_SAMPLES", "20"))
FOCUS_HEALTH_VARIATION_THRESHOLD = float(os.getenv("FOCUS_HEALTH_VARIATION_THRESHOLD", "5.0"))
FOCUS_HEALTH_MIN_FOM = int(os.getenv("FOCUS_HEALTH_MIN_FOM", "150"))  # IMX708 outdoor max ≈230; 150 allows healthy settled focus
FOCUS_HEALTH_RETRY_ATTEMPTS = int(os.getenv("FOCUS_HEALTH_RETRY_ATTEMPTS", "2"))

# Detection Settings - Can be overridden via environment variables
DETECTION_INTERVAL = float(os.getenv("DETECTION_INTERVAL", "30.0"))  # Optimized to 30.0s for performance
CONFIDENCE_THRESHOLD = float(os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.8"))
PLATE_CONFIDENCE_THRESHOLD = float(os.getenv("PLATE_CONFIDENCE_THRESHOLD", "0.6"))

# Vehicle Tracking Configuration - Can be overridden via environment variables
TRACKING_ENABLED = os.getenv("TRACKING_ENABLED", "true").lower() == "true"  # Enable vehicle tracking and deduplication
REENTRY_TIME_THRESHOLD = float(os.getenv("REENTRY_TIME_THRESHOLD", "30.0"))  # Time in seconds before same car can be recorded again
IOU_THRESHOLD = float(os.getenv("IOU_THRESHOLD", "0.2"))  # IoU threshold for identifying same vehicle (0.0 to 1.0)

# Threading intervals (in seconds) - Can be overridden via environment variables
SENDER_INTERVAL = float(os.getenv("SENDER_INTERVAL", "60.0"))    # How often the sender thread checks for new detections (1 minute)
HEALTH_SENDER_INTERVAL = float(os.getenv("HEALTH_SENDER_INTERVAL", "300.0"))  # How often health status is sent to server (5 minutes)

# Health monitoring interval (in seconds, 3600 seconds = 1 hour)
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "3600"))

# WebSocket sender configuration
WEBSOCKET_SENDER_ENABLED = True  # Enable WebSocket sender
WEBSOCKET_CONNECTION_TIMEOUT = 30.0  # Connection timeout in seconds
WEBSOCKET_RETRY_INTERVAL = 60.0  # Retry connection interval in seconds
WEBSOCKET_MAX_RETRIES = 5  # Maximum connection retries before giving up

# Storage monitoring configuration
STORAGE_MONITOR_ENABLED = True  # Enable storage monitoring
STORAGE_MONITOR_INTERVAL = 300  # Storage monitoring interval in seconds (5 minutes)
STORAGE_MIN_FREE_SPACE_GB = 10.0  # Minimum free space in GB before cleanup

# Browser Connection Management Configuration
BROWSER_CONNECTION_TIMEOUT = int(os.getenv("BROWSER_CONNECTION_TIMEOUT", "300"))  # 5 minutes timeout for inactive connections
BROWSER_CLEANUP_INTERVAL = int(os.getenv("BROWSER_CLEANUP_INTERVAL", "60"))  # 1 minute cleanup interval
BROWSER_CONNECTION_TRACKING_ENABLED = os.getenv("BROWSER_CONNECTION_TRACKING_ENABLED", "true").lower() == "true"
CONDITIONAL_RESOURCE_ALLOCATION = os.getenv("CONDITIONAL_RESOURCE_ALLOCATION", "true").lower() == "true"

# Experiment service configuration
EXPERIMENT_ENABLED = True  # Enable experiment service
EXPERIMENT_RESULTS_DIR = os.path.join(BASE_DIR, 'edge', 'experiment_results')

# Health monitoring configuration
AUTO_START_HEALTH_MONITOR = True  # Enable automatic health monitoring startup
STORAGE_RETENTION_DAYS = 7  # Number of days to keep images

# Experiment configuration
EXPERIMENT_RESULTS_DIR = os.path.join(BASE_DIR, 'edge', 'experiment_results')
EXPERIMENT_ENABLED = os.getenv('EXPERIMENT_ENABLED', 'true').lower() == 'true'  # Enable/disable experiment functionality
EXPERIMENT_AUTO_SAVE = os.getenv('EXPERIMENT_AUTO_SAVE', 'true').lower() == 'true'  # Auto-save experiment results
EXPERIMENT_MAX_RETRIES = int(os.getenv('EXPERIMENT_MAX_RETRIES', '3'))  # Maximum retries for failed experiment steps
STORAGE_BATCH_SIZE = 100  # Number of files to delete in each batch
STORAGE_FOLDER_PATH = os.path.join(BASE_DIR, 'edge', 'captured_images')  # Path to monitored folder

# Auto-startup configuration
AUTO_START_CAMERA = True      # Auto start camera on system startup
AUTO_START_STREAMING = True   # Auto start streaming when camera starts
AUTO_START_DETECTION = True   # Auto start detection when streaming starts
AUTO_START_HEALTH_MONITOR = True  # Auto start health monitoring when detection starts
AUTO_START_WEBSOCKET_SENDER = True  # Auto start WebSocket sender when health monitor starts
AUTO_START_STORAGE_MONITOR = True  # Auto start storage monitoring when WebSocket sender starts
STARTUP_DELAY = 5.0          # Delay in seconds between startup steps
HEALTH_MONITOR_STARTUP_DELAY = 5.0  # Delay before starting health monitoring (increased for model loading)
WEBSOCKET_SENDER_STARTUP_DELAY = 5.0  # Delay before starting WebSocket sender
STORAGE_MONITOR_STARTUP_DELAY = 5.0  # Delay before starting storage monitoring

# Create directories if they don't exist - all in BASE_DIR (aicamera/)
Path(IMAGE_SAVE_DIR).mkdir(parents=True, exist_ok=True)
if DATABASE_PATH:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
# Create logs directory
Path(BASE_DIR, 'edge', 'logs').mkdir(parents=True, exist_ok=True)

# Debug: Print BASE_DIR for verification
from edge.src.core.utils.logging_config import get_logger
logger = get_logger(__name__)
logger.info(f"Config BASE_DIR set to: {BASE_DIR}")
logger.info(f"IMAGE_SAVE_DIR: {IMAGE_SAVE_DIR}")
logger.info(f"DATABASE_PATH: {DATABASE_PATH}")
logger.info(f"LOGS directory: {os.path.join(BASE_DIR, 'edge', 'logs')}")