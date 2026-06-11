#!/usr/bin/env python3
"""
Enhanced Detection Processor Component for AI Camera v2.0

This component provides enhanced AI detection operations using Hailo AI models:
- Vehicle detection using Hailo accelerator with tracking and deduplication
- License plate detection with best frame selection
- License plate OCR with parallel processing (Hailo + Tesseract)
- Advanced image preprocessing (motion detection, illumination/contrast/denoise)
- Post-processing for natural color preservation
- Pre-OCR processing for optimal text recognition
- Event-driven pipeline orchestration
- Coordinate mapping with letterbox resizing
- Performance optimization and reliability improvements

Enhanced Features:
- Motion/change detection for efficient processing
- Vehicle tracking with deduplication rules
- Best frame selection for OCR
- Multi-condition lighting adaptation
- Resource-limited processing
- Storage optimization (85% quality)

Author: AI Camera Team  
Version: 2.0
Date: September 2025
"""

import os
import cv2
import numpy as np
import logging
import sqlite3
import time
import threading
import queue
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from enum import Enum

from edge.src.core.utils.logging_config import get_logger, get_detection_logger, RateLimitedLogger
from edge.src.core.config import (
    VEHICLE_DETECTION_MODEL, LICENSE_PLATE_DETECTION_MODEL, LICENSE_PLATE_OCR_MODEL,
    HEF_MODEL_PATH, MODEL_ZOO_URL, EASYOCR_LANGUAGES,
    IMAGE_SAVE_DIR, DATABASE_PATH, CONFIDENCE_THRESHOLD, PLATE_CONFIDENCE_THRESHOLD,
    TRACKING_ENABLED, REENTRY_TIME_THRESHOLD, IOU_THRESHOLD,
    ROI_ENABLED, ROI_X1, ROI_Y1, ROI_X2, ROI_Y2
)
from edge.src.components.async_ocr_loader import AsyncOCRLoader
from edge.src.components.parallel_ocr_processor import ParallelOCRProcessor
from edge.src.components.thai_lp_ocr import ThaiLPROCR, preprocess_plate_crop, validate_thai_plate
from edge.src.components.ocr_queue_worker import OcrQueueWorker, OcrTask

logger = get_logger(__name__)



class LightingCondition(Enum):
    """Lighting conditions for adaptive processing."""
    NORMAL = "normal"
    LOW_LIGHT = "low_light"
    BRIGHT = "bright"
    NIGHT = "night"


@dataclass
class VehicleTrack:
    """Vehicle tracking data structure."""
    track_id: int
    bbox: List[float]
    confidence: float
    first_seen: float
    last_seen: float
    frame_count: int
    best_frame_score: float
    best_frame_data: Optional[np.ndarray] = None
    plate_candidates: List[Dict] = None
    ocr_results: List[Dict] = None
    iou_history: deque = None
    # Async OCR queue fields
    ocr_submitted: bool = False          # True once track has been queued for OCR
    ocr_submitted_lap: float = 0.0      # Laplacian of the crop that was submitted
    plate_crop_buffer: deque = None      # (laplacian_var, crop_bgr) — maxlen=5

    def __post_init__(self):
        if self.plate_candidates is None:
            self.plate_candidates = []
        if self.ocr_results is None:
            self.ocr_results = []
        if self.iou_history is None:
            self.iou_history = deque(maxlen=10)
        if self.plate_crop_buffer is None:
            self.plate_crop_buffer = deque(maxlen=10)



class DetectionProcessor:
    """
    Enhanced Detection Processor Component for AI model inference.
    
    This component handles:
    - Loading and managing Hailo AI models
    - Motion/change detection for efficient processing
    - Advanced image preprocessing (illumination/contrast/denoise)
    - Vehicle detection with tracking and deduplication
    - License plate detection with best frame selection
    - Parallel OCR processing (Hailo + Tesseract)
    - Post-processing for natural color preservation
    - Pre-OCR processing for optimal text recognition
    - Event-driven pipeline orchestration
    - Coordinate mapping with letterbox resizing
    - Performance optimization and reliability improvements
    """
    
    def __init__(self, logger=None):
        """
        Initialize Detection Processor.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger or get_logger(__name__)
        self.opt_logger = get_detection_logger(self.logger)
        self.rate_limited = RateLimitedLogger(self.logger, default_interval=5.0)
        
        # Track last logged states to avoid repetitive logging
        self.last_logged_states = {
            'vehicles_detected': 0,
            'plates_detected': 0,
            'ocr_successful': 0,
            'processing_time': 0,
            'last_detection_time': 0
        }
        
        # Statistics for periodic logging
        self.stats_start_time = time.time()
        self.last_stats_log = 0
        self.stats_interval = 60  # Log stats every 60 seconds
        
        # Detection activity tracking
        self.detection_activity = {
            'active_detections': 0,
            'inactive_periods': 0,
            'last_activity_time': time.time()
        }
        
        self.opt_logger.log_initialization("Starting Detection Processor initialization...")
        
        # Model instances
        self.logger.info("🔍 [DETECTION_PROC] Initializing model instances...")
        self.vehicle_model = None
        self.lp_detection_model = None
        self.lp_ocr_model = None
        self.ocr_reader = None  # Legacy - will be replaced by async_ocr_loader
        self.logger.info("🔍 [DETECTION_PROC] Model instances initialized")
        
        # Async OCR loader (legacy EasyOCR — kept as last-resort fallback)
        self.logger.info("🔍 [DETECTION_PROC] Creating AsyncOCRLoader...")
        self.async_ocr_loader = AsyncOCRLoader(languages=EASYOCR_LANGUAGES, logger=self.logger)
        self.logger.info("🔍 [DETECTION_PROC] AsyncOCRLoader created successfully")
        
        # ThaiLPROCR (Tesseract) instance — secondary OCR engine
        self.thai_lp_ocr = None

        # Parallel OCR processor for simultaneous Hailo + ThaiLPROCR
        self.logger.info("🔍 [DETECTION_PROC] Initializing parallel OCR processor...")
        self.parallel_ocr_processor = None
        self.logger.info("🔍 [DETECTION_PROC] Parallel OCR processor initialized")
        
        # State tracking
        self.logger.info("🔍 [DETECTION_PROC] Setting up state tracking...")
        self.models_loaded = False
        self._hailo_reinit_pending = False  # True while background reinit is in progress
        self.processing_stats = {
            'total_processed': 0,
            'vehicles_detected': 0,
            'plates_detected': 0,
            'successful_ocr': 0,
            'last_detection': None
        }
        self.logger.info("🔍 [DETECTION_PROC] State tracking initialized")
        
        # Configuration
        from edge.src.core.config import LORES_RESOLUTION
        self.detection_resolution = LORES_RESOLUTION
        self.confidence_threshold = CONFIDENCE_THRESHOLD
        self.plate_confidence_threshold = PLATE_CONFIDENCE_THRESHOLD
        self.logger.info("DetectionProcessor initialized")
        
        # Enhanced Detection Pipeline Configuration
        self.logger.info("🔧 [ENHANCED_DETECTION] Initializing enhanced detection pipeline...")
        # Vehicle Tracking (use config values)
        self.tracking_enabled = TRACKING_ENABLED
        self.next_track_id = 1
        self.active_tracks: Dict[int, VehicleTrack] = {}
        self.reentry_time_threshold = REENTRY_TIME_THRESHOLD  # seconds for deduplication (from config)
        # track_timeout must be >= reentry_time_threshold so the same physical vehicle
        # keeps the same track_id within the dedup window.  If track_timeout < reentry_time_threshold,
        # a vehicle that briefly drops below confidence threshold expires, gets a new track_id,
        # and bypasses the manager's recent_tracks dedup check → duplicate DB records.
        self.track_timeout = REENTRY_TIME_THRESHOLD  # 30 s (matches dedup window)
        self.iou_threshold = IOU_THRESHOLD  # IoU threshold for tracking (from config)
        
        # Best Frame Selection
        self.best_frame_selection_enabled = True
        self.frame_score_weights = {
            'sharpness': 0.4,
            'plate_confidence': 0.3,
            'area_ratio': 0.2,
            'plate_centeredness': 0.1
        }
        
        # Thread Safety
        self._processing_lock = threading.RLock()
        self._track_lock = threading.RLock()

        # ── Async OCR Queue (Producer-Consumer) ────────────────────────────
        # Worker is created here but not started until load_models() completes
        # so ThaiLPROCR is ready before the worker thread begins.
        self.ocr_queue_worker: Optional[OcrQueueWorker] = None
        self._async_ocr_enabled: bool = True   # set False to fall back to sync

        # Gatekeeper thresholds for async submit
        self._ocr_min_plate_frames: int = 1    # min plate frames before OCR (1 = submit on first clear plate, quality filtered by best_frame_score)
        self._ocr_min_frame_score: float = 0.3 # minimum best_frame_score

        # ROI trigger zone — loaded from config / .env (normalised 0-1)
        self._roi_zone = {
            'enabled': ROI_ENABLED,
            'x1': ROI_X1, 'y1': ROI_Y1,
            'x2': ROI_X2, 'y2': ROI_Y2,
        }
        # ──────────────────────────────────────────────────────────────────

        self.logger.info("🔧 [ENHANCED_DETECTION] Enhanced detection pipeline initialized successfully")
    
    def load_models(self) -> bool:
        """
        Load all detection and OCR models using configuration parameters.
        
        Returns:
            bool: True if models loaded successfully, False otherwise
        """
        self.logger.info("🔧 [DETECTION_PROC] Starting model loading process...")
        try:
            self.logger.info("🔧 [DETECTION_PROC] Loading detection models...")
            
            # Check if required model parameters are available
            self.logger.info("🔧 [DETECTION_PROC] Checking model configuration...")
            if not VEHICLE_DETECTION_MODEL:
                self.logger.warning("🔧 [DETECTION_PROC] VEHICLE_DETECTION_MODEL not configured")
                return False
            
            if not LICENSE_PLATE_DETECTION_MODEL:
                self.logger.warning("🔧 [DETECTION_PROC] LICENSE_PLATE_DETECTION_MODEL not configured")
                return False
            
            self.logger.info("🔧 [DETECTION_PROC] Model configuration validated")
            
            # Import degirum for Hailo model loading
            # Configure HailoRT logging before importing degirum
            self.logger.info("🔧 [DETECTION_PROC] Configuring HailoRT logging...")
            from edge.config.hailort_logging import configure_hailort_logging
            configure_hailort_logging()
            self.logger.info("🔧 [DETECTION_PROC] HailoRT logging configured")
            
            self.logger.info("🔧 [DETECTION_PROC] Importing degirum...")
            try:
                import degirum as dg
                self.logger.info("🔧 [DETECTION_PROC] ✅ Degirum available for Hailo AI model loading")
            except ImportError:
                self.logger.error("🔧 [DETECTION_PROC] degirum not available - cannot load Hailo models")
                return False
            
            models_loaded = 0
            
            # Load vehicle detection model
            self.logger.info("🔧 [DETECTION_PROC] Loading vehicle detection model...")
            try:
                self.logger.info(f"🔧 [DETECTION_PROC] Loading vehicle detection model: {VEHICLE_DETECTION_MODEL}")
                self.vehicle_model = dg.load_model(
                    model_name=VEHICLE_DETECTION_MODEL,
                    inference_host_address=HEF_MODEL_PATH,
                    zoo_url=MODEL_ZOO_URL
                )
                self.logger.info("🔧 [DETECTION_PROC] ✅ Vehicle detection model loaded successfully")
                models_loaded += 1
            except Exception as e:
                self.logger.error(f"🔧 [DETECTION_PROC] Failed to load vehicle detection model: {e}")
                return False
            
            # Load license plate detection model
            self.logger.info("🔧 [DETECTION_PROC] Loading license plate detection model...")
            try:
                self.logger.info(f"🔧 [DETECTION_PROC] Loading license plate detection model: {LICENSE_PLATE_DETECTION_MODEL}")
                self.lp_detection_model = dg.load_model(
                    model_name=LICENSE_PLATE_DETECTION_MODEL,
                    inference_host_address=HEF_MODEL_PATH,
                    zoo_url=MODEL_ZOO_URL,
                    overlay_color=[(255, 255, 0), (0, 255, 0)]
                )
                self.logger.info("🔧 [DETECTION_PROC] ✅ License plate detection model loaded successfully")
                models_loaded += 1
            except Exception as e:
                self.logger.error(f"🔧 [DETECTION_PROC] Failed to load license plate detection model: {e}")
                return False
            
            # Load license plate OCR model (optional)
            self.logger.info("🔧 [DETECTION_PROC] Checking for optional OCR model...")
            if LICENSE_PLATE_OCR_MODEL:
                self.logger.info("🔧 [DETECTION_PROC] Loading license plate OCR model...")
                try:
                    self.logger.info(f"🔧 [DETECTION_PROC] Loading license plate OCR model: {LICENSE_PLATE_OCR_MODEL}")
                    self.lp_ocr_model = dg.load_model(
                        model_name=LICENSE_PLATE_OCR_MODEL,
                        inference_host_address=HEF_MODEL_PATH,
                        zoo_url=MODEL_ZOO_URL,
                        output_use_regular_nms=False,
                        output_confidence_threshold=0.1
                    )
                    self.logger.info("🔧 [DETECTION_PROC] ✅ License plate OCR model loaded successfully")
                    models_loaded += 1
                except Exception as e:
                    self.logger.warning(f"🔧 [DETECTION_PROC] Failed to load OCR model (optional): {e}")
            else:
                self.logger.info("🔧 [DETECTION_PROC] No OCR model configured - skipping")
            
            # Load ThaiLPROCR (Tesseract) — secondary OCR engine for Thai plates
            self.logger.info("🔧 [DETECTION_PROC] Loading ThaiLPROCR (Tesseract)...")
            try:
                if self.thai_lp_ocr is None:
                    self.thai_lp_ocr = ThaiLPROCR(logger=self.logger)
                if not self.thai_lp_ocr.is_ready():
                    if self.thai_lp_ocr.load():
                        self.logger.info("🔧 [DETECTION_PROC] ✅ ThaiLPROCR loaded successfully")
                    else:
                        self.logger.warning("🔧 [DETECTION_PROC] ThaiLPROCR load failed — Thai OCR disabled")
                else:
                    self.logger.debug("🔧 [DETECTION_PROC] ThaiLPROCR already loaded — skipping")
            except Exception as e:
                self.logger.warning(f"🔧 [DETECTION_PROC] Failed to load ThaiLPROCR: {e}")
                self.thai_lp_ocr = None

            # Initialize parallel OCR processor (Hailo + ThaiLPROCR)
            self.logger.info("🔧 [DETECTION_PROC] Initializing parallel OCR processor...")
            try:
                self.parallel_ocr_processor = ParallelOCRProcessor(
                    hailo_ocr_model=self.lp_ocr_model,
                    thai_lp_ocr=self.thai_lp_ocr,
                    logger=self.logger
                )
                self.logger.info("🔧 [DETECTION_PROC] ✅ Parallel OCR processor initialized")
            except Exception as e:
                self.logger.warning(f"🔧 [DETECTION_PROC] Failed to initialize parallel OCR processor: {e}")
                self.parallel_ocr_processor = None
            
            self.models_loaded = models_loaded >= 2  # At least vehicle + LP detection

            # Start Async OCR Queue Worker (requires ThaiLPROCR to be ready)
            if self._async_ocr_enabled and self.thai_lp_ocr and self.thai_lp_ocr.is_ready():
                try:
                    self.ocr_queue_worker = OcrQueueWorker(
                        thai_lp_ocr=self.thai_lp_ocr,
                        ocr_queue_maxsize=10,
                        result_queue_maxsize=50,
                        num_workers=1,
                        logger=self.logger,
                    )
                    self.ocr_queue_worker.start()
                    self.logger.info("🔧 [DETECTION_PROC] ✅ Async OCR queue worker started")
                except Exception as e:
                    self.logger.warning(f"🔧 [DETECTION_PROC] Failed to start OCR queue worker: {e}")
                    self.ocr_queue_worker = None
            else:
                self.logger.info("🔧 [DETECTION_PROC] Async OCR worker skipped (ThaiLPROCR not ready or disabled)")

            self.logger.info("🔧 [DETECTION_PROC] Model loading process completed successfully")
            return self.models_loaded
            
        except Exception as e:
            self.logger.error(f"🔧 [DETECTION_PROC] Error loading models: {e}")
            return False
    
    def _trigger_hailo_reinit(self):
        """
        Recover from HAILO_STREAM_ABORT by reloading all Hailo models in a background thread.
        The VDMA ring enters an aborted state after an unclean worker exit; closing and
        reopening the model handles is the only way to get a clean ring without a full
        service restart. Runs once per abort event — subsequent calls are no-ops while
        reinit is in progress.
        """
        if self._hailo_reinit_pending:
            return

        self._hailo_reinit_pending = True
        self.models_loaded = False
        self.vehicle_model = None
        self.lp_detection_model = None
        self.lp_ocr_model = None
        self.logger.error(
            "HAILO_STREAM_ABORT detected — Hailo VDMA ring is in aborted state. "
            "Scheduling model reinitialisation in 10s..."
        )

        def _reinit():
            time.sleep(10)
            try:
                self.logger.info("Hailo reinit: starting load_models()...")
                success = self.load_models()
                if success:
                    self.logger.info("Hailo reinit: models reloaded successfully — inference resuming")
                else:
                    self.logger.error("Hailo reinit: load_models() failed — service restart required")
            except Exception as exc:
                self.logger.error(f"Hailo reinit: exception during reload: {exc}")
            finally:
                self._hailo_reinit_pending = False

        threading.Thread(target=_reinit, name="HailoReinit", daemon=True).start()

    def get_ocr_status(self) -> Dict[str, Any]:
        """
        Get current OCR loading and usage status.

        Returns:
            Dict containing OCR status information
        """
        status = self.async_ocr_loader.get_loading_status()
        # Include model names for frontend display
        status.update({
            'vehicle_model_name': VEHICLE_DETECTION_MODEL,
            'lp_detection_model_name': LICENSE_PLATE_DETECTION_MODEL,
            'lp_ocr_model_name': LICENSE_PLATE_OCR_MODEL or '',
            'tesseract_available': bool(self.thai_lp_ocr.is_ready() if self.thai_lp_ocr else False),
            'tesseract_ready': bool(self.thai_lp_ocr.is_ready() if self.thai_lp_ocr else False)
        })
        return status
    
    def wait_for_ocr_ready(self, timeout: float = 30.0) -> bool:
        """
        Wait for OCR to be ready with timeout.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if OCR is ready within timeout
        """
        return self.async_ocr_loader.wait_for_ready(timeout)
    
    def _log_periodic_stats(self):
        """Log periodic statistics with rate limiting."""
        try:
            current_time = time.time()
            uptime = current_time - self.stats_start_time
            
            stats = {
                'vehicles': self.processing_stats['vehicles_detected'],
                'plates': self.processing_stats['plates_detected'],
                'ocr_successful': self.processing_stats['ocr_successful'],
                'active_detections': self.detection_activity['active_detections'],
                'inactive_periods': self.detection_activity['inactive_periods'],
                'uptime': round(uptime, 1)
            }
            
            self.opt_logger.log_iteration_stats(stats)
            
        except Exception as e:
            self.rate_limited.debug_rate_limited(
                "stats_logging_error",
                f"Error logging periodic stats: {e}",
                interval=60.0
            )

    def cleanup(self):
        """
        Clean up all resources including async OCR loader, parallel processor, and models.
        Safe to call multiple times (idempotent).
        """
        try:
            self.logger.info("Cleaning up DetectionProcessor...")

            # Step 0: Shut down async OCR queue worker
            if hasattr(self, 'ocr_queue_worker') and self.ocr_queue_worker:
                try:
                    self.ocr_queue_worker.cleanup()
                    self.logger.debug("Async OCR queue worker shut down")
                except Exception as e:
                    self.logger.warning(f"Error shutting down OCR queue worker: {e}")
                finally:
                    self.ocr_queue_worker = None

            # Step 1: Clean up parallel OCR processor if present
            if hasattr(self, 'parallel_ocr_processor') and self.parallel_ocr_processor:
                try:
                    self.parallel_ocr_processor.cleanup()
                    self.logger.debug("Parallel OCR processor cleaned up")
                except Exception as e:
                    self.logger.warning(f"Error cleaning up parallel OCR processor: {e}")
            
            # Step 2: Clean up async OCR loader if present
            if hasattr(self, 'async_ocr_loader'):
                try:
                    self.async_ocr_loader.cleanup()
                    self.logger.debug("Async OCR loader cleaned up")
                except Exception as e:
                    self.logger.warning(f"Error cleaning up async OCR loader: {e}")
            
            # Step 3: Clean up model references
            try:
                self.vehicle_model = None
                self.lp_detection_model = None  
                self.lp_ocr_model = None
                self.ocr_reader = None
                self.models_loaded = False
                self.logger.debug("Model references cleaned up")
            except Exception as e:
                self.logger.warning(f"Error cleaning up model references: {e}")
            
            self.logger.info("DetectionProcessor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during DetectionProcessor cleanup: {e}")
    
    def enhance_for_detection(self, frame: np.ndarray) -> np.ndarray:
        """
        Enhance frame specifically for detection models.
        
        Args:
            frame: Input image frame
            
        Returns:
            np.ndarray: Enhanced frame optimized for detection
        """
        try:
            enhanced_frame = frame.copy()
            
            # Step 1: Assess lighting condition
            self.lighting_condition = self._assess_lighting_condition(enhanced_frame)
            
            # Step 2: Apply lighting-specific enhancements
            if self.lighting_condition == LightingCondition.LOW_LIGHT:
                enhanced_frame = self._enhance_for_low_light(enhanced_frame)
            elif self.lighting_condition == LightingCondition.BRIGHT:
                enhanced_frame = self._enhance_for_bright_light(enhanced_frame)
            elif self.lighting_condition == LightingCondition.NIGHT:
                enhanced_frame = self._enhance_for_night(enhanced_frame)
            else:  # NORMAL
                enhanced_frame = self._enhance_for_normal_light(enhanced_frame)
            
            # Step 3: Apply general enhancements
            enhanced_frame = self._apply_general_enhancements(enhanced_frame)
            
            return enhanced_frame
            
        except Exception as e:
            self.logger.error(f"🔧 [ENHANCEMENT] Frame enhancement error: {e}")
            return frame
    
    def enhance_for_ocr(self, plate_region: np.ndarray) -> np.ndarray:
        """
        Enhance license plate region specifically for OCR.
        
        Args:
            plate_region: Cropped license plate region
            
        Returns:
            np.ndarray: Enhanced plate region optimized for OCR
        """
        try:
            ocr_frame = plate_region.copy()
            
            # Step 1: Resize to optimal OCR size
            ocr_frame = self._resize_for_ocr(ocr_frame)
            
            # Step 2: Apply OCR-specific preprocessing
            ocr_frame = self._apply_ocr_preprocessing(ocr_frame)
            
            # Step 3: Enhance text clarity
            ocr_frame = self._enhance_text_clarity(ocr_frame)
            
            # Step 4: Apply character edge enhancement
            ocr_frame = self._enhance_character_edges(ocr_frame)
            
            return ocr_frame
            
        except Exception as e:
            self.logger.error(f"🔧 [OCR_ENHANCEMENT] OCR enhancement error: {e}")
            return plate_region
    
    def validate_and_enhance_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Validate and enhance image frame for vehicle detection.
        
        Args:
            frame: Input image frame as numpy array

        Returns:
            Optional[np.ndarray]: Enhanced frame or None if validation fails
        """
        # self.logger.debug(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame called with frame type: {type(frame)}")  # DEBUG: ปิดรายละเอียด
        
        if frame is None:
            self.logger.warning(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame failed: frame is None")
            return None
        
        # Check if frame is a dict (should be numpy array)
        if isinstance(frame, dict):
            self.logger.debug(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame: received dict, extracting frame")
            if 'frame' in frame:
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame: extracting frame from dict")
                frame = frame['frame']
                if frame is None:
                    self.logger.warning(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame failed: extracted frame is None")
                    return None
            else:
                self.logger.error(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame failed: dict does not contain 'frame' key")
                return None
        
        # Check if frame is numpy array
        if not isinstance(frame, np.ndarray):
            self.logger.error(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame failed: expected numpy array, got {type(frame)}")
            return None
        
        # Check frame size
        if frame.size == 0:
            self.logger.warning(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame failed: empty array")
            return None
        
        # self.logger.debug(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame: frame shape: {frame.shape}, dtype: {frame.dtype}")  # DEBUG: ปิดรายละเอียด
        
        try:
            # Ensure frame is in BGR format for detection models
            if len(frame.shape) == 3:
                if frame.shape[2] == 4:  # BGRA
                    self.logger.debug(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame: converting BGRA to BGR")
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                elif frame.shape[2] == 3:  # RGB from camera - convert to BGR for OpenCV
                    self.logger.debug(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame: converting RGB to BGR")
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            elif len(frame.shape) == 2:  # Grayscale
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame: converting grayscale to BGR")
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            else:
                self.logger.warning(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame failed: unsupported frame shape: {frame.shape}")
                return None
            
            # ไม่ resize ที่นี่ - ให้ resize_for_model_input ทำครั้งเดียวด้วย letterbox
            # frame = cv2.resize(frame, self.detection_resolution)  # ปิดเพื่อหลีกเลี่ยง resize ซ้ำ
            
            # Basic enhancement - can be extended
            # Optional: histogram equalization, noise reduction, etc.
            
            self.logger.debug(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame: returning enhanced frame with shape: {frame.shape}")
            return frame
            
        except Exception as e:
            self.logger.error(f"🔧 [DETECTION_PROCESSOR] validate_and_enhance_frame error: {e}")
            return None
    
    def detect_vehicles(self, frame: np.ndarray) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Perform vehicle detection on image frame.
        
        Args:
            frame: Input image frame (original resolution)
            
        Returns:
            Tuple[List[Dict[str, Any]], Dict[str, Any]]: List of detected vehicle objects and mapping_info
        """
        # self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_vehicles called with frame shape: {frame.shape if frame is not None else 'None'}")  # DEBUG: ปิดรายละเอียด
        
        if not self.models_loaded or not self.vehicle_model:
            self.rate_limited.warning_rate_limited(
                "vehicle_model_missing",
                f"Vehicle detection model not loaded: models_loaded={self.models_loaded}, vehicle_model={self.vehicle_model is not None}",
                interval=30.0
            )
            return [], {}
        
        try:
            start_time = time.time()
            
            # 1. Resize for model input with letterbox (640x640) และเก็บ mapping_info
            model_frame, mapping_info = self.resize_for_model_input(frame, (640, 640))
            
            # 2. BGR→RGB conversion for model
            if len(model_frame.shape) == 3 and model_frame.shape[2] == 3:
                model_frame = cv2.cvtColor(model_frame, cv2.COLOR_BGR2RGB)
            
            # 3. Perform detection on resized frame
            results = self.vehicle_model(model_frame)
            vehicle_boxes = getattr(results, "results", [])
            
            # 4. Filter by confidence threshold และ map พิกัดกลับสู่ภาพต้นฉบับ
            filtered_boxes = []
            for box in vehicle_boxes:
                confidence = box.get('score', 0)
                if confidence >= self.confidence_threshold:
                    # Map bounding box coordinates back to original frame
                    if 'bbox' in box:
                        mapped_bbox = self.map_coordinates_to_original(box['bbox'], mapping_info)
                        box['bbox'] = mapped_bbox
                        box['bbox_original'] = mapped_bbox  # เก็บพิกัดต้นฉบับ
                    filtered_boxes.append(box)
            
            processing_time = (time.time() - start_time) * 1000

            # Log per-vehicle details at INFO — always visible in field test logs
            vehicles_count = len(filtered_boxes)
            if vehicles_count != self.last_logged_states['vehicles_detected']:
                self.opt_logger.logger.info(f"🚗 Vehicles detected: {vehicles_count} (filtered from {len(vehicle_boxes)})")
                self.last_logged_states['vehicles_detected'] = vehicles_count
            for box in filtered_boxes:
                x1, y1, x2, y2 = box['bbox']
                vw, vh = int(x2 - x1), int(y2 - y1)
                self.logger.info(
                    f"[VEHICLE] conf={box.get('score', 0):.3f} "
                    f"size={vw}×{vh}px "
                    f"bbox=[{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}] "
                    f"detect_time={processing_time:.0f}ms"
                )
            
            # Update processing statistics
            self.processing_stats['total_processed'] += 1
            self.processing_stats['vehicles_detected'] += vehicles_count
            self.processing_stats['processing_time_ms'] = processing_time
            
            # Track detection activity
            if vehicles_count > 0:
                self.detection_activity['active_detections'] += 1
                self.detection_activity['last_activity_time'] = time.time()
            else:
                self.detection_activity['inactive_periods'] += 1
            
            return filtered_boxes, mapping_info
            
        except Exception as e:
            err_str = str(e)
            if "HAILO_STREAM_ABORT" in err_str or "STREAM_ABORT" in err_str:
                self._trigger_hailo_reinit()
            else:
                self.rate_limited.warning_rate_limited(
                    "vehicle_detection_error",
                    f"Vehicle detection error: {e}",
                    interval=30.0
                )
            return [], {}

    def detect_license_plates(self, frame: np.ndarray, vehicle_boxes: List[Dict], mapping_info: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Detect license plates within detected vehicles.
        
        Args:
            frame: Original image frame
            vehicle_boxes: List of detected vehicle bounding boxes (with mapped coordinates)
            mapping_info: Mapping information for coordinate conversion (optional)
            
        Returns:
            List[Dict[str, Any]]: List of detected license plates with mapped coordinates
        """
        # self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_license_plates called with frame shape: {frame.shape if frame is not None else 'None'}, vehicle_boxes: {len(vehicle_boxes)}")  # DEBUG: ปิดรายละเอียด
        
        if not self.models_loaded or not self.lp_detection_model:
            self.logger.warning(f"🔧 [DETECTION_PROCESSOR] detect_license_plates failed: models_loaded={self.models_loaded}, lp_detection_model={self.lp_detection_model is not None}")
            return []
        
        detected_plates = []
        
        for i, vehicle_box in enumerate(vehicle_boxes):
            try:
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: processing vehicle {i}")
                
                # Extract vehicle region
                if 'bbox' not in vehicle_box:
                    self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: vehicle {i} has no bbox, skipping")
                    continue
                    
                x1, y1, x2, y2 = vehicle_box['bbox']
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: vehicle {i} bbox: [{x1}, {y1}, {x2}, {y2}]")
                
                vehicle_region = frame[int(y1):int(y2), int(x1):int(x2)]
                
                if vehicle_region.size == 0:
                    self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: vehicle {i} region is empty, skipping")
                    continue
                
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: vehicle {i} region shape: {vehicle_region.shape}")
                
                # Perform license plate detection on vehicle region
                lp_results = self.lp_detection_model(vehicle_region)
                lp_boxes = getattr(lp_results, "results", [])
                
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: vehicle {i} raw LP detection results: {len(lp_boxes)} plates found")
                
                # Filter by confidence and convert coordinates back to full frame
                for j, lp_box in enumerate(lp_boxes):
                    confidence = lp_box.get('score', 0)
                    if confidence >= self.plate_confidence_threshold:
                        # Convert coordinates back to full frame
                        lp_x1, lp_y1, lp_x2, lp_y2 = lp_box['bbox']
                        full_x1 = x1 + lp_x1
                        full_y1 = y1 + lp_y1
                        full_x2 = x1 + lp_x2
                        full_y2 = y1 + lp_y2
                        
                        plate_data = {
                            'bbox': [full_x1, full_y1, full_x2, full_y2],
                            'bbox_original': [full_x1, full_y1, full_x2, full_y2],  # พิกัดต้นฉบับ
                            'score': confidence,
                            'vehicle_idx': i,
                            'vehicle_bbox': vehicle_box['bbox']
                        }

                        pw, ph = int(full_x2 - full_x1), int(full_y2 - full_y1)
                        ar = round(pw / ph, 2) if ph > 0 else 0
                        detected_plates.append(plate_data)
                        self.logger.info(
                            f"[PLATE] conf={confidence:.3f} "
                            f"size={pw}×{ph}px ar={ar} "
                            f"bbox=[{full_x1:.0f},{full_y1:.0f},{full_x2:.0f},{full_y2:.0f}] "
                            f"vehicle={i}"
                        )
                    else:
                        # lp_x1/lp_x2 not yet assigned (bbox only unpacked in the if-branch above)
                        if 'bbox' in lp_box:
                            _lx1, _ly1, _lx2, _ly2 = lp_box['bbox']
                            pw, ph = int(_lx2 - _lx1), int(_ly2 - _ly1)
                        else:
                            pw, ph = 0, 0
                        self.logger.info(
                            f"[PLATE_SKIP] conf={confidence:.3f} < thresh={self.plate_confidence_threshold} "
                            f"size={pw}×{ph}px vehicle={i}"
                        )
                
            except Exception as e:
                self.logger.warning(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: error detecting plates in vehicle {i}: {e}")
                continue
        
        # self.logger.info(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: 🔢 License plates detected: {len(detected_plates)} from {len(vehicle_boxes)} vehicles")  # INFO: ปิดรายละเอียด
        self.processing_stats['plates_detected'] += len(detected_plates)
        
        self.logger.debug(f"🔧 [DETECTION_PROCESSOR] detect_license_plates: returning {len(detected_plates)} detected plates")
        return detected_plates
    
    def perform_ocr(self, frame: np.ndarray, plate_boxes: List[Dict]) -> List[Dict[str, Any]]:
        """
        Perform OCR on detected license plates.
        
        Args:
            frame: Original image frame
            plate_boxes: List of detected license plate bounding boxes
            
        Returns:
            List[Dict[str, Any]]: OCR results with text and confidence
        """
        # self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr called with frame shape: {frame.shape if frame is not None else 'None'}, plate_boxes: {len(plate_boxes)}")  # DEBUG: ปิดรายละเอียด
        
        ocr_results = []
        
        for i, plate_box in enumerate(plate_boxes):
            try:
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr: processing plate {i}")
                
                # Extract license plate region using safe padding
                bbox = plate_box['bbox']
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr: plate {i} bbox: {bbox}")
                # Log plate size + frame token before crop
                bw = int(bbox[2] - bbox[0])
                bh = int(bbox[3] - bbox[1])
                frame_fid = id(frame) % 1_000_000
                self.logger.info(
                    f"[LP_SIZE] fid={frame_fid} plate={i} "
                    f"size={bw}×{bh}px "
                    f"det_conf={plate_box.get('score',0):.3f} "
                    f"bbox=[{bbox[0]:.0f},{bbox[1]:.0f},{bbox[2]:.0f},{bbox[3]:.0f}]"
                )
                # ใช้ crop_with_safe_padding เพื่อขยายขอบ 15% สำหรับ OCR
                plate_region, crop_info = self.crop_with_safe_padding(frame, bbox, padding_ratio=0.15)
                
                if plate_region.size == 0:
                    self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr: plate {i} region is empty, skipping")
                    continue

                # Check plate quality before OCR processing — log metrics ALWAYS
                quality_check = self._check_plate_quality(plate_region)
                qm = quality_check.get('metrics', {})
                if quality_check['is_acceptable']:
                    self.logger.info(
                        f"[PLATE_QUALITY] plate={i} PASS "
                        f"size={qm.get('size','?')} ar={qm.get('aspect','?')} "
                        f"sharp={qm.get('sharpness','?')} bright={qm.get('brightness','?')} "
                        f"contrast={qm.get('contrast','?')} "
                        f"upscale={qm.get('upscale_w','?')}×"
                    )
                else:
                    self.logger.warning(
                        f"[PLATE_QUALITY] plate={i} FAIL reason={quality_check['reason']} "
                        f"bbox={bbox}"
                    )
                    continue
                
                # Enhanced OCR preprocessing: Use enhance_for_ocr() for better OCR accuracy
                # This includes resize, OCR preprocessing, text clarity enhancement, and character edge enhancement
                plate_region = self.enhance_for_ocr(plate_region)
                
                self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr: plate {i} region shape: {plate_region.shape}")
                
                # Try Hailo OCR model first (if available)
                hailo_ocr_text = ""
                hailo_ocr_confidence = 0.0
                hailo_ocr_success = False
                
                if self.lp_ocr_model:
                    try:
                        ocr_result = self.lp_ocr_model(plate_region)
                        char_list = getattr(ocr_result, 'results', [])
                        valid = [r for r in char_list if r.get('score', 0) >= 0.25]
                        if valid:
                            valid.sort(key=lambda r: r.get('bbox', [0])[0])
                            hailo_ocr_text = ''.join(r.get('label', '') for r in valid)
                            hailo_ocr_confidence = sum(r.get('score', 0) for r in valid) / len(valid)
                            hailo_ocr_success = bool(hailo_ocr_text)
                        else:
                            hailo_ocr_text = ''
                            hailo_ocr_confidence = 0.0
                            hailo_ocr_success = False
                    except Exception as e:
                        self.logger.debug(f"Hailo OCR failed for plate {i}: {e}")

                # Use parallel OCR processing (Hailo + Tesseract simultaneously)
                parallel_results = None
                if self.parallel_ocr_processor:
                    try:
                        parallel_results = self.parallel_ocr_processor.process_plate_parallel(
                            plate_region, i, timeout=10.0
                        )
                    except Exception as e:
                        self.logger.warning(f"Parallel OCR failed for plate {i}: {e}")
                
                # Extract results from parallel processing
                if parallel_results:
                    # Get best result
                    best_result = parallel_results.get('best_result', {})
                    if best_result and best_result.get('success'):
                        final_ocr_text = best_result['text']
                        final_ocr_confidence = best_result['confidence']
                        ocr_method = best_result['method']
                    
                    # Extract individual results for database storage
                    hailo_result = parallel_results.get('hailo', {})
                    tesseract_result = parallel_results.get('tesseract', {})

                    hailo_ocr_text = hailo_result.get('text', '') if hailo_result.get('success') else ''
                    hailo_ocr_confidence = hailo_result.get('confidence', 0.0)
                    hailo_ocr_success = hailo_result.get('success', False)

                    tesseract_text = tesseract_result.get('text', '') if tesseract_result.get('success') else ''
                    tesseract_confidence = tesseract_result.get('confidence', 0.0)
                    tesseract_success = tesseract_result.get('success', False)

                else:
                    # Fallback to individual OCR methods if parallel processing failed
                    tesseract_text = ""
                    tesseract_confidence = 0.0
                    tesseract_success = False

                    if self.thai_lp_ocr and self.thai_lp_ocr.is_ready():
                        try:
                            preprocessed = preprocess_plate_crop(plate_region.copy())
                            thai_result = self.thai_lp_ocr.read_plate(preprocessed)
                            if thai_result.get('success'):
                                tesseract_text = thai_result['text']
                                tesseract_confidence = thai_result['confidence']
                                tesseract_success = True
                        except Exception as e:
                            self.logger.debug(f"ThaiLPROCR fallback failed for plate {i}: {e}")
                    else:
                        self.logger.debug(f"ThaiLPROCR not available - skipping Thai OCR for plate {i}")

                # Determine final OCR result.
                # Prefer Tesseract ONLY when it produces a structurally valid Thai plate
                # (letters + digits pattern matched). Garbage output from sparse-text PSM
                # must not beat clean digit-only Hailo results.
                thai_ocr_validation = validate_thai_plate(tesseract_text) if tesseract_success and tesseract_text else {'valid': False}
                thai_plate_valid = thai_ocr_validation.get('valid', False)

                if thai_plate_valid:
                    final_ocr_text = thai_ocr_validation['formatted']
                    final_ocr_confidence = tesseract_confidence
                    ocr_method = "tesseract"
                elif hailo_ocr_success:
                    final_ocr_text = hailo_ocr_text
                    final_ocr_confidence = hailo_ocr_confidence
                    ocr_method = "hailo"
                else:
                    final_ocr_text = tesseract_text
                    final_ocr_confidence = tesseract_confidence
                    ocr_method = "tesseract" if tesseract_success else "none"

                # Reformat Hailo-only result if it contains Thai chars
                if final_ocr_text and ocr_method == "hailo":
                    plate_validation = validate_thai_plate(final_ocr_text)
                    if plate_validation['valid']:
                        final_ocr_text = plate_validation['formatted']

                if final_ocr_text:
                    self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr: plate {i} OCR successful with method: {ocr_method}, text: '{final_ocr_text.strip()}', confidence: {final_ocr_confidence:.3f}")
                    
                    # Enhanced OCR result with parallel processing metadata
                    ocr_result = {
                        'plate_idx': i,
                        'bbox': plate_box['bbox'],
                        'text': final_ocr_text.strip(),
                        'confidence': final_ocr_confidence,
                        'vehicle_idx': plate_box.get('vehicle_idx', -1),
                        'detection_confidence': plate_box.get('score', 0),
                        'ocr_method': ocr_method,
                        'hailo_ocr': {
                            'text': hailo_ocr_text.strip() if hailo_ocr_success else "",
                            'confidence': hailo_ocr_confidence,
                            'success': hailo_ocr_success
                        },
                        'tesseract': {
                            'text': tesseract_text.strip() if tesseract_success else "",
                            'confidence': tesseract_confidence,
                            'success': tesseract_success
                        }
                    }

                    # Add parallel processing metadata if available
                    if parallel_results:
                        ocr_result['parallel_processing'] = {
                            'parallel_success': parallel_results.get('parallel_success', False),
                            'processing_time': parallel_results.get('processing_time', 0.0),
                            'hailo_time': parallel_results.get('hailo', {}).get('processing_time', 0.0),
                            'tesseract_time': parallel_results.get('tesseract', {}).get('processing_time', 0.0),
                            'selection_reason': parallel_results.get('best_result', {}).get('selection_reason', '')
                        }
                    
                    ocr_results.append(ocr_result)
                    self.processing_stats['successful_ocr'] += 1
                else:
                    self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr: plate {i} OCR failed - no text extracted")
                
            except Exception as e:
                self.logger.warning(f"🔧 [DETECTION_PROCESSOR] perform_ocr: error performing OCR on plate {i}: {e}")
                continue
        
        # self.logger.info(f"🔧 [DETECTION_PROCESSOR] perform_ocr: 📝 OCR successful: {len(ocr_results)} from {len(plate_boxes)} plates")  # INFO: ปิดรายละเอียด
        self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr: returning {len(ocr_results)} OCR results")
        return ocr_results
    
    def save_detection_results(self, original_frame: np.ndarray, vehicle_boxes: List[Dict], 
                             plate_boxes: List[Dict], ocr_results: List[Dict]) -> Tuple[str, str, str, List[str]]:
        """
        Save only original image for performance optimization.
        Detection bounding boxes will be drawn dynamically in showDetail.
        
        Args:
            original_frame: Original image frame
            vehicle_boxes: Detected vehicles
            plate_boxes: Detected license plates
            ocr_results: OCR results
            
        Returns:
            Tuple[str, str, str, List[str]]: Path to original image, empty strings for compatibility
        """
        try:
            # Generate timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]

            # Ensure directory exists and is writable
            Path(IMAGE_SAVE_DIR).mkdir(parents=True, exist_ok=True)
            if not os.access(IMAGE_SAVE_DIR, os.W_OK):
                self.logger.error(f"Image save directory not writable: {IMAGE_SAVE_DIR}")
                return "", "", "", []

            # Step 1: Save only original image with datetime format filename
            original_filename = f"detection_{timestamp}.jpg"
            original_path = os.path.join(IMAGE_SAVE_DIR, original_filename)

            # Ensure frame is uint8 for imwrite
            frame_to_save = original_frame
            if frame_to_save is None or not isinstance(frame_to_save, np.ndarray) or frame_to_save.size == 0:
                self.logger.error("Invalid frame provided to save_detection_results")
                return "", "", "", []
            if frame_to_save.dtype != np.uint8:
                try:
                    frame_to_save = np.clip(frame_to_save, 0, 255).astype(np.uint8)
                except Exception:
                    self.logger.error("Failed to convert frame to uint8 for saving")
                    return "", "", "", []

            # Pi5/PiSP: picamera2 "RGB888" make_array() delivers BGR in memory → cv2.imwrite expects BGR, no conversion
            # ─── [DIAG H5] Upload I/O Timing ────────────────────────
            time_save_start = time.perf_counter()
            success = cv2.imwrite(original_path, frame_to_save)
            time_save_ms = (time.perf_counter() - time_save_start) * 1000
            file_size_kb = os.path.getsize(original_path) / 1024 if success else 0
            self.logger.info(
                f"[UPLOAD] path={original_filename} | "
                f"size={file_size_kb:.0f}KB | "
                f"write_time={time_save_ms:.0f}ms | "
                f"success={success}"
            )
            # สิ่งที่ต้องสังเกต: ถ้า write_time= สูง (>200ms)
            # → SD Card I/O เป็นคอขวด → ยืนยัน H5
            # ────────────────────────────────────────────────────────
            if not success or (not os.path.exists(original_path)):
                self.logger.error(f"cv2.imwrite failed or file missing after write: {original_path}")
                return "", "", "", []
            try:
                if os.path.getsize(original_path) <= 0:
                    self.logger.error(f"Saved image file is empty: {original_path}")
                    return "", "", "", []
            except OSError as e:
                self.logger.error(f"Error verifying saved image file: {e}")
                return "", "", "", []

            # Return empty strings for other image paths to maintain database schema compatibility
            # Detection bounding boxes will be drawn dynamically in showDetail for better performance
            vehicle_detected_path = ""
            plate_detected_path = ""
            cropped_paths = []

            self.logger.info(f"Saved original image only: {original_path} (optimized for performance)")
            return original_path, vehicle_detected_path, plate_detected_path, cropped_paths

        except Exception as e:
            self.logger.error(f"Error saving detection results: {e}")
            return "", "", "", []
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the detection processor including model availability.
        
        Returns:
            Dict containing detection processor status information
        """
        # self.logger.debug(f"🔧 [DETECTION_PROCESSOR] get_status called")  # DEBUG: ปิดรายละเอียด
        
        try:
            # Check model availability
            vehicle_model_available = self.vehicle_model is not None
            lp_detection_model_available = self.lp_detection_model is not None
            lp_ocr_model_available = self.lp_ocr_model is not None
            
            self.logger.debug(f"🔧 [DETECTION_PROCESSOR] get_status: model availability - vehicle: {vehicle_model_available}, lp_detection: {lp_detection_model_available}, lp_ocr: {lp_ocr_model_available}")
            
            # Get OCR status
            self.logger.debug(f"🔧 [DETECTION_PROCESSOR] get_status: getting OCR status")
            ocr_status = self.get_ocr_status()
            tesseract_available = ocr_status.get('tesseract_ready', False)

            self.logger.debug(f"🔧 [DETECTION_PROCESSOR] get_status: OCR status - tesseract_available: {tesseract_available}")

            status = {
                'models_loaded': self.models_loaded,
                'vehicle_model_available': vehicle_model_available,
                'lp_detection_model_available': lp_detection_model_available,
                'lp_ocr_model_available': lp_ocr_model_available,
                'tesseract_available': tesseract_available,
                'detection_resolution': self.detection_resolution,
                'confidence_threshold': self.confidence_threshold,
                'plate_confidence_threshold': self.plate_confidence_threshold,
                'processing_stats': self.processing_stats.copy(),
                'last_update': datetime.now().isoformat()
            }
            
            self.logger.debug(f"🔧 [DETECTION_PROCESSOR] get_status: returning status: {status}")
            return status
            
        except Exception as e:
            self.logger.error(f"🔧 [DETECTION_PROCESSOR] Error getting detection processor status: {e}")
            error_status = {
                'models_loaded': False,
                'vehicle_model_available': False,
                'lp_detection_model_available': False,
                'lp_ocr_model_available': False,
                'tesseract_available': False,
                'detection_resolution': self.detection_resolution,
                'confidence_threshold': self.confidence_threshold,
                'plate_confidence_threshold': self.plate_confidence_threshold,
                'processing_stats': {},
                'last_update': datetime.now().isoformat(),
                'error': str(e)
            }
            self.logger.debug(f"🔧 [DETECTION_PROCESSOR] get_status: returning error status: {error_status}")
            return error_status
    # Enhanced Image Processing Helper Methods
    
    def _assess_lighting_condition(self, frame: np.ndarray) -> LightingCondition:
        """Assess lighting condition from frame."""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate brightness statistics
            mean_brightness = np.mean(gray)
            std_brightness = np.std(gray)
            
            # Classify lighting condition
            if mean_brightness < 50:
                return LightingCondition.NIGHT
            elif mean_brightness < 100:
                return LightingCondition.LOW_LIGHT
            elif mean_brightness > 200:
                return LightingCondition.BRIGHT
            else:
                return LightingCondition.NORMAL
                
        except Exception as e:
            self.logger.warning(f"Lighting assessment failed: {e}")
            return LightingCondition.NORMAL
    
    def _enhance_for_low_light(self, frame: np.ndarray) -> np.ndarray:
        """Enhance frame for low light conditions."""
        try:
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # Apply noise reduction
            enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"Low light enhancement failed: {e}")
            return frame
    
    def _enhance_for_bright_light(self, frame: np.ndarray) -> np.ndarray:
        """Enhance frame for bright light conditions."""
        try:
            # Reduce overexposure
            enhanced = cv2.convertScaleAbs(frame, alpha=0.8, beta=0)
            
            # Apply sharpening
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            enhanced = cv2.filter2D(enhanced, -1, kernel)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"Bright light enhancement failed: {e}")
            return frame
    
    def _enhance_for_night(self, frame: np.ndarray) -> np.ndarray:
        """Enhance frame for night conditions."""
        try:
            # Apply temporal averaging for noise reduction
            enhanced = cv2.fastNlMeansDenoisingColored(frame, None, 15, 15, 7, 21)
            
            # Apply gamma correction
            gamma = 1.5
            enhanced = np.power(enhanced / 255.0, gamma) * 255.0
            enhanced = np.uint8(enhanced)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"Night enhancement failed: {e}")
            return frame
    
    def _enhance_for_normal_light(self, frame: np.ndarray) -> np.ndarray:
        """Enhance frame for normal lighting conditions."""
        try:
            # Apply balanced enhancement
            enhanced = cv2.convertScaleAbs(frame, alpha=1.1, beta=10)
            
            # Apply mild sharpening
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
            enhanced = cv2.filter2D(enhanced, -1, kernel)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"Normal light enhancement failed: {e}")
            return frame
    
    def _apply_general_enhancements(self, frame: np.ndarray) -> np.ndarray:
        """Apply general enhancements to frame."""
        try:
            # Apply unsharp masking
            enhanced = self._apply_unsharp_masking(frame, amount=1.5, radius=1.0, threshold=0)
            
            # Apply CLAHE for contrast enhancement
            enhanced = self._apply_clahe_enhancement(enhanced)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"General enhancement failed: {e}")
            return frame
    
    def _resize_for_ocr(self, plate_region: np.ndarray) -> np.ndarray:
        """Resize plate region for optimal OCR."""
        try:
            # Resize to optimal OCR size (height = 64, maintain aspect ratio)
            height, width = plate_region.shape[:2]
            target_height = 64
            target_width = int(width * target_height / height)
            
            resized = cv2.resize(plate_region, (target_width, target_height), interpolation=cv2.INTER_CUBIC)
            
            return resized
            
        except Exception as e:
            self.logger.warning(f"OCR resize failed: {e}")
            return plate_region
    
    def _apply_ocr_preprocessing(self, plate_region: np.ndarray) -> np.ndarray:
        """Apply OCR-specific preprocessing with enhanced contrast and noise reduction."""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY) if len(plate_region.shape) == 3 else plate_region
            
            # Step 1: Noise reduction using bilateral filter (preserves edges)
            denoised = cv2.bilateralFilter(gray, 5, 50, 50)
            
            # Step 2: Contrast enhancement using CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # Step 3: Apply adaptive thresholding with improved parameters
            processed = cv2.adaptiveThreshold(
                enhanced, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 
                11, 2
            )
            
            # Step 4: Convert back to BGR for consistency
            processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            
            return processed
            
        except Exception as e:
            self.logger.warning(f"OCR preprocessing failed: {e}")
            return plate_region
    
    def _enhance_text_clarity(self, plate_region: np.ndarray) -> np.ndarray:
        """Enhance text clarity for OCR with improved morphological operations and sharpening."""
        try:
            # Convert to grayscale if needed
            if len(plate_region.shape) == 3:
                gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_region
            
            # Step 1: Apply morphological operations to clean up text
            # Use smaller kernel for better character preservation
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            cleaned = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            
            # Step 2: Apply sharpening filter to enhance character edges
            sharpen_kernel = np.array([[-1, -1, -1],
                                      [-1,  9, -1],
                                      [-1, -1, -1]])
            sharpened = cv2.filter2D(cleaned, -1, sharpen_kernel)
            
            # Step 3: Convert back to BGR
            enhanced = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"Text clarity enhancement failed: {e}")
            return plate_region
    
    def _check_plate_quality(self, plate_region: np.ndarray) -> Dict[str, Any]:
        """
        Check plate image quality before OCR processing.
        Thresholds calibrated for yolov8n_relu6_lp_ocr--256x128 model.
        """
        try:
            if plate_region.size == 0:
                return {'is_acceptable': False, 'reason': 'Empty region'}

            h, w = plate_region.shape[:2]
            # ─── [DIAG H2] LP Size Log — บันทึกขนาดทุกครั้งก่อน OCR ────
            self.logger.info(
                f"[LP_SIZE] w={w}px h={h}px "
                f"ratio={w/max(h,1):.2f} "
                f"area={w*h}px²"
            )
            # สิ่งที่ต้องสังเกต: ถ้า w= ส่วนใหญ่ < 80 → ยืนยัน H2
            # ─────────────────────────────────────────────────────────────

            # ── Minimum Size Check ───────────────────────────────────────────
            # Model input: 256×128 → max upscale 3× is acceptable
            # Thai LP aspect ratio ≈ 3.25:1 (52cm × 16cm)
            # Width and Height thresholds are INDEPENDENT — not the same value
            #
            #  Level        MIN_W   MIN_H   Upscale(W)  Upscale(H)  Quality
            #  Absolute     64px    20px      4.0×        6.4×       poor
            #  Acceptable   80px    24px      3.2×        5.3×       ok
            #  Good        128px    40px      2.0×        3.2×       good ✅ target
            #  Excellent   160px    50px      1.6×        2.6×       very good
            MIN_PLATE_WIDTH  = 80   # px — ~1/3 of model input width  (256px)
            MIN_PLATE_HEIGHT = 24   # px — based on Thai LP ratio 3.3:1

            if w < MIN_PLATE_WIDTH:
                return {
                    'is_acceptable': False,
                    'reason': f'Width too small ({w}px < {MIN_PLATE_WIDTH}px) '
                            f'— would require {256/max(w,1):.1f}× upscale into 256px model'
                }
            if h < MIN_PLATE_HEIGHT:
                return {
                    'is_acceptable': False,
                    'reason': f'Height too small ({h}px < {MIN_PLATE_HEIGHT}px) '
                            f'— would require {128/max(h,1):.1f}× upscale into 128px model'
                }

            # ── Aspect Ratio Sanity Check ─────────────────────────────────────
            # Thai LP ≈ 2.8–3.8:1.  Camera angle + distance foreshorten the plate,
            # so allow down to 1.2 (was 1.5) to catch slightly angled views.
            aspect_ratio = w / max(h, 1)
            if not (1.2 <= aspect_ratio <= 6.0):
                return {
                    'is_acceptable': False,
                    'reason': f'Aspect ratio {aspect_ratio:.2f} invalid for Thai LP '
                            f'(expected 1.2–6.0, got {w}×{h}px)'
                }

            # ── Convert to Grayscale ──────────────────────────────────────────
            if len(plate_region.shape) == 3:
                gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_region

            # ── Sharpness Check (Laplacian Variance) ──────────────────────────
            # Roadside mounting produces laplacian 20–40 even for real plates due to
            # viewing distance and vehicle speed. Base of 15.0 (was 30.0) prevents
            # rejecting all detections at typical deployment distances.
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            area_factor   = min(w * h / (128 * 40), 2.0)   # normalize to "good" size
            min_sharpness = 15.0 * area_factor              # 15–30 range (was 30–60)
            if laplacian_var < min_sharpness:
                return {
                    'is_acceptable': False,
                    'reason': f'Too blurry (laplacian={laplacian_var:.1f} '
                            f'< {min_sharpness:.1f}) — motion blur or out of focus'
                }

            # ── Brightness Check ──────────────────────────────────────────────
            mean_brightness = np.mean(gray)
            if mean_brightness < 30:
                return {'is_acceptable': False,
                        'reason': f'Too dark (brightness={mean_brightness:.1f}/255)'}
            if mean_brightness > 240:
                return {'is_acceptable': False,
                        'reason': f'Overexposed (brightness={mean_brightness:.1f}/255)'}

            # ── Contrast Check ────────────────────────────────────────────────
            contrast = np.std(gray)
            if contrast < 15.0:
                return {'is_acceptable': False,
                        'reason': f'Low contrast (std={contrast:.1f}) — may be blank region'}

            return {
                'is_acceptable': True,
                'reason': 'OK',
                'metrics': {
                    'size':       f'{w}×{h}px',
                    'aspect':     round(aspect_ratio, 2),
                    'sharpness':  round(laplacian_var, 1),
                    'brightness': round(float(mean_brightness), 1),
                    'contrast':   round(float(contrast), 1),
                    'upscale_w':  round(256 / w, 2),
                    'upscale_h':  round(128 / h, 2),
                }
            }

        except Exception as e:
            self.logger.warning(f"Plate quality check failed: {e}")
            return {'is_acceptable': True, 'reason': 'Check failed, proceeding'}
    
    def _enhance_character_edges(self, plate_region: np.ndarray) -> np.ndarray:
        """Enhance character edges for better OCR with improved edge detection and unsharp masking."""
        try:
            # Convert to grayscale if needed
            if len(plate_region.shape) == 3:
                gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_region
            
            # Step 1: Apply unsharp masking for better edge enhancement
            # Blur the image
            blurred = cv2.GaussianBlur(gray, (0, 0), 2.0)
            # Create unsharp mask
            unsharp_mask = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)
            
            # Step 2: Apply edge enhancement kernel (improved)
            edge_kernel = np.array([[-1, -1, -1],
                                   [-1,  9, -1],
                                   [-1, -1, -1]])
            edge_enhanced = cv2.filter2D(unsharp_mask, -1, edge_kernel)
            
            # Step 3: Normalize to 0-255 range
            normalized = cv2.normalize(edge_enhanced, None, 0, 255, cv2.NORM_MINMAX)
            
            # Step 4: Convert back to BGR
            enhanced = cv2.cvtColor(normalized.astype(np.uint8), cv2.COLOR_GRAY2BGR)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"Character edge enhancement failed: {e}")
            return plate_region
    
    # ── Async OCR Queue Methods ────────────────────────────────────────────────

    # ── ROI public API ────────────────────────────────────────────────────────

    def get_roi_zone(self) -> dict:
        """Return current ROI zone dict (safe copy)."""
        return dict(self._roi_zone)

    def set_roi_zone(self, enabled: bool,
                     x1: float, y1: float,
                     x2: float, y2: float) -> bool:
        """
        Update the ROI trigger zone at runtime (no restart required).

        Parameters are normalised image coordinates (0.0 – 1.0).
        x1 < x2 and y1 < y2 must both hold; values are clamped to [0, 1].
        Returns True on success, False on bad input.
        """
        x1, y1, x2, y2 = (max(0.0, min(1.0, v)) for v in (x1, y1, x2, y2))
        if x1 >= x2 or y1 >= y2:
            self.logger.warning(
                f"[ROI] Invalid zone (x1={x1}, y1={y1}, x2={x2}, y2={y2}) — rejected")
            return False
        self._roi_zone = {'enabled': bool(enabled),
                          'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
        self.logger.info(
            f"[ROI] Zone updated: enabled={enabled} "
            f"({x1:.3f},{y1:.3f})→({x2:.3f},{y2:.3f})")
        return True

    def _plate_in_roi(self, plate_bbox: List[float], frame_shape: tuple) -> bool:
        """Return True if plate center falls inside the configured ROI zone."""
        roi = self._roi_zone
        if not roi.get('enabled', False):
            return True
        h, w = frame_shape[:2]
        if w == 0 or h == 0:
            return True
        cx = (plate_bbox[0] + plate_bbox[2]) / 2 / w
        cy = (plate_bbox[1] + plate_bbox[3]) / 2 / h
        return roi['x1'] <= cx <= roi['x2'] and roi['y1'] <= cy <= roi['y2']

    # Minimum Laplacian variance for the best crop in the buffer before
    # submitting to Tesseract.  Below this value the crop is too blurry to
    # produce useful text.  Set via _ocr_min_crop_lap (tunable).
    _ocr_min_crop_lap: float = 80.0
    # If a new crop arrives with Laplacian >= this multiple of the previously
    # submitted crop's sharpness, reset ocr_submitted and re-submit with the
    # better crop.  Set to 0 to disable re-submit.
    _ocr_resubmit_ratio: float = 3.0

    def _should_submit_for_ocr(self, track: 'VehicleTrack', plate_bbox: List[float],
                                frame_shape: tuple) -> bool:
        """Gatekeeper — decide whether this track should be queued for OCR."""
        best_lap = max((s for s, _ in track.plate_crop_buffer), default=0.0) \
                   if track.plate_crop_buffer else 0.0

        if track.ocr_submitted:
            # Allow re-submit if a significantly sharper crop has arrived.
            # Ratio >= _ocr_resubmit_ratio means the new crop is substantially
            # clearer than what Tesseract already processed.
            if (self._ocr_resubmit_ratio > 0 and track.ocr_submitted_lap > 0
                    and best_lap >= track.ocr_submitted_lap * self._ocr_resubmit_ratio):
                track.ocr_submitted = False
                self.logger.info(
                    f"[OCR_GATE] RE-SUBMIT track={track.track_id}: "
                    f"new_lap={best_lap:.0f} >= {self._ocr_resubmit_ratio}× "
                    f"submitted_lap={track.ocr_submitted_lap:.0f} — retry with better crop")
            else:
                return False

        if len(track.plate_candidates) < self._ocr_min_plate_frames:
            self.logger.info(
                f"[OCR_GATE] SKIP track={track.track_id}: "
                f"plate_frames={len(track.plate_candidates)} < min={self._ocr_min_plate_frames} "
                f"(need more frames — vehicle moving too fast?)"
            )
            return False
        if track.best_frame_score < self._ocr_min_frame_score:
            self.logger.info(
                f"[OCR_GATE] SKIP track={track.track_id}: "
                f"frame_score={track.best_frame_score:.3f} < min={self._ocr_min_frame_score} "
                f"(image too blurry or low confidence)"
            )
            return False
        if best_lap < self._ocr_min_crop_lap:
            self.logger.info(
                f"[OCR_GATE] SKIP track={track.track_id}: "
                f"best_crop_lap={best_lap:.0f} < min={self._ocr_min_crop_lap} "
                f"(plate crop too blurry for OCR)")
            return False
        if not self._plate_in_roi(plate_bbox, frame_shape):
            cx = (plate_bbox[0] + plate_bbox[2]) / 2
            cy = (plate_bbox[1] + plate_bbox[3]) / 2
            self.logger.info(
                f"[OCR_GATE] SKIP track={track.track_id}: "
                f"plate center ({cx:.0f},{cy:.0f}) outside ROI zone"
            )
            return False
        self.logger.info(
            f"[OCR_GATE] PASS track={track.track_id}: "
            f"frames={len(track.plate_candidates)} score={track.best_frame_score:.3f} "
            f"best_lap={best_lap:.0f} — submitting for OCR"
        )
        return True

    def submit_for_ocr(self, track: 'VehicleTrack', plate_bbox: List[float],
                        det_confidence: float, frame_timestamp: float,
                        camera_id: str, frame_shape: tuple) -> bool:
        """
        Non-blocking submit of track's best plate crop to the OCR worker.
        Returns True if task was accepted, False if skipped or dropped.
        """
        if not self.ocr_queue_worker:
            return False
        if not self._should_submit_for_ocr(track, plate_bbox, frame_shape):
            return False

        # Pick best crop from buffer using height-weighted sharpness score.
        # For side-mounted cameras (vehicle passing laterally), a taller crop
        # requires less upscaling → sharper Tesseract input even at lower Laplacian.
        # min(lap, 500) caps the sharpness benefit; beyond 500 the image is
        # "good enough" and height becomes the primary differentiator.
        plate_crop = None
        if track.plate_crop_buffer:
            plate_crop = max(
                track.plate_crop_buffer,
                key=lambda x: min(x[0], 500) * x[1].shape[0]
            )[1]
        if plate_crop is None or plate_crop.size == 0:
            self.logger.debug(
                f"[ASYNC_OCR] track_id={track.track_id} no crop in buffer — skipping"
            )
            return False

        task = OcrTask(
            track_id=track.track_id,
            plate_crop=plate_crop,
            bbox=plate_bbox,
            det_confidence=det_confidence,
            frame_timestamp=frame_timestamp,
            camera_id=camera_id,
        )
        accepted = self.ocr_queue_worker.submit(task)
        if accepted:
            track.ocr_submitted = True
            best_lap = max((s for s, _ in track.plate_crop_buffer), default=0.0) \
                       if track.plate_crop_buffer else 0.0
            track.ocr_submitted_lap = best_lap   # store for re-submit comparison
            ch, cw = (plate_crop.shape[0], plate_crop.shape[1]) \
                     if plate_crop is not None and plate_crop.ndim >= 2 else (0, 0)
            self.logger.info(
                f"[OCR_SUBMIT] track={track.track_id} "
                f"crop={cw}×{ch}px blur={best_lap:.0f} "
                f"score={track.best_frame_score:.3f} det_conf={det_confidence:.3f} "
                f"queue_depth={self.ocr_queue_worker.queue_size}"
            )
        else:
            self.logger.warning(
                f"[OCR_SUBMIT_DROP] track={track.track_id} — queue full, task dropped"
            )
        return accepted

    def poll_ocr_results(self) -> List[Dict[str, Any]]:
        """
        Non-blocking drain of completed OCR results from the worker.
        Converts OcrResult → same dict schema as perform_ocr_on_enhanced_plates().
        Call once per frame iteration before the storage step.
        """
        if not self.ocr_queue_worker:
            return []
        raw_results = self.ocr_queue_worker.drain_results()
        if not raw_results:
            return []

        results = []
        for r in raw_results:
            if r.error:
                self.logger.warning(
                    f"[ASYNC_OCR] track_id={r.track_id} error: {r.error}"
                )
                continue
            ocr_entry = {
                'plate_idx': r.track_id,
                'bbox': r.bbox,
                'text': r.text,
                'confidence': r.confidence,
                'detection_confidence': r.det_confidence,
                'ocr_method': r.method,
                'enhanced_processing': True,
                'valid_thai': r.valid_thai,
                'async_ocr': True,
                'track_id': r.track_id,
            }
            results.append(ocr_entry)
            e2e_ms = (r.completed_at - r.frame_timestamp) * 1000 if r.frame_timestamp else 0
            self.logger.info(
                f"[OCR_DONE] ✅ track={r.track_id} "
                f"text='{r.text}' valid={r.valid_thai} "
                f"conf={r.confidence:.3f} method={r.method} "
                f"e2e={e2e_ms:.0f}ms (frame→OCR complete)"
            )
        return results

    # Vehicle Tracking and Deduplication Methods

    def update_vehicle_tracks(self, detections: List[Dict[str, Any]], frame: np.ndarray) -> List[VehicleTrack]:
        """
        Update vehicle tracks with new detections.
        
        Args:
            detections: List of vehicle detections
            frame: Current frame for best frame selection
            
        Returns:
            List[VehicleTrack]: Updated active tracks
        """
        try:
            with self._track_lock:
                current_time = time.time()
                # ─── [DIAG H4] บันทึก Track IDs ก่อน update ───────
                prev_ids = set(self.active_tracks.keys())
                # ────────────────────────────────────────────────────

                # Clean up expired tracks
                self._cleanup_expired_tracks(current_time)
                
                # Update existing tracks and create new ones
                updated_tracks = []
                matched_detections = set()
                
                for detection in detections:
                    best_track = self._find_best_track_match(detection, current_time)

                    if best_track:
                        # Update existing track — same vehicle continuing across frames
                        self._update_track(best_track, detection, frame, current_time)
                        updated_tracks.append(best_track)
                        matched_detections.add(id(detection))
                        self.logger.info(
                            f"[TRACK_UPDATE] track={best_track.track_id} "
                            f"frame_count={best_track.frame_count} "
                            f"score={best_track.best_frame_score:.3f} "
                            f"plates={len(best_track.plate_candidates)} "
                            f"ocr_submitted={best_track.ocr_submitted}"
                        )
                    else:
                        # Create new track — new vehicle entered frame
                        new_track = self._create_new_track(detection, frame, current_time)
                        updated_tracks.append(new_track)
                        matched_detections.add(id(detection))
                        x1, y1, x2, y2 = new_track.bbox
                        self.logger.info(
                            f"[TRACK_NEW] track={new_track.track_id} "
                            f"conf={new_track.confidence:.3f} "
                            f"size={int(x2-x1)}×{int(y2-y1)}px — new vehicle"
                        )
                
                # Update active tracks
                self.active_tracks = {track.track_id: track for track in updated_tracks}
                # ─── [DIAG H4] Structured Tracker Log ──────────────
                new_ids = set(self.active_tracks.keys())
                created = new_ids - prev_ids
                lost    = prev_ids - new_ids
                if created or lost:
                    self.logger.info(
                        f"[TRACKER] "
                        f"active={sorted(new_ids)} | "
                        f"created={sorted(created)} | "
                        f"lost={sorted(lost)} | "
                        f"total_detections={len(detections)}"
                    )
                # สิ่งที่ต้องสังเกต: ถ้ามี ID หายพร้อมกันกับ ID ใหม่
                # ขณะที่รถยังอยู่ในเฟรม → ยืนยัน H4: Track ID Reset
                # ────────────────────────────────────────────────────
                self.logger.debug(f"🔧 [TRACKING] Updated {len(updated_tracks)} tracks")
                return updated_tracks
                
        except Exception as e:
            self.logger.error(f"🔧 [TRACKING] Track update error: {e}")
            return []
    
    def _cleanup_expired_tracks(self, current_time: float):
        """Clean up expired tracks."""
        try:
            expired_tracks = []
            for track_id, track in self.active_tracks.items():
                if current_time - track.last_seen > self.track_timeout:
                    expired_tracks.append(track_id)
            
            for track_id in expired_tracks:
                track = self.active_tracks[track_id]
                # ─── [DIAG H4] Log expired track details ────────────
                self.logger.info(
                    f"[TRACKER_EXPIRE] track_id={track_id} | "
                    f"age={current_time - track.last_seen:.2f}s | "
                    f"frame_count={track.frame_count} | "
                    f"best_score={track.best_frame_score:.3f} | "
                    f"plates_found={len(track.plate_candidates)}"
                )
                # ────────────────────────────────────────────────────
                del self.active_tracks[track_id]
                self.logger.debug(f"🔧 [TRACKING] Removed expired track {track_id}")

        except Exception as e:
            self.logger.warning(f"Track cleanup error: {e}")
    
    def _find_best_track_match(self, detection: Dict[str, Any], current_time: float) -> Optional[VehicleTrack]:
        """
        Find best matching track for detection.

        Primary match:  IoU > iou_threshold  (existing behaviour).
        Fallback match: centre-point proximity, used when a moving vehicle shifts
                        enough between frames that IoU drops below threshold.
                        Only activates within half of track_timeout to avoid
                        matching unrelated vehicles.
        """
        try:
            best_track        = None
            best_iou          = 0.0
            best_center_track = None
            best_center_dist  = float('inf')
            # Max normalised centre-distance to accept as the same vehicle.
            # 0.4 means the centre can move up to 40 % of the detection's diagonal.
            CENTER_DIST_LIMIT = 0.4

            detection_bbox = detection.get('bbox', [])
            if not detection_bbox:
                return None

            dx1, dy1, dx2, dy2 = detection_bbox
            dcx = (dx1 + dx2) / 2
            dcy = (dy1 + dy2) / 2
            det_diag = max(((dx2 - dx1) ** 2 + (dy2 - dy1) ** 2) ** 0.5, 1.0)

            for track in self.active_tracks.values():
                if current_time - track.last_seen > self.track_timeout:
                    continue

                iou = self._calculate_iou(detection_bbox, track.bbox)

                if iou > 0:
                    self.logger.debug(
                        f"[IOUcheck] track={track.track_id} iou={iou:.3f} "
                        f"{'MATCH' if iou > self.iou_threshold else 'NO_MATCH'}"
                    )

                if iou > self.iou_threshold and iou > best_iou:
                    best_iou   = iou
                    best_track = track
                elif iou <= self.iou_threshold:
                    # Fallback: centre-point distance (catches fast-moving vehicles)
                    time_gap = current_time - track.last_seen
                    if time_gap < self.track_timeout / 2:
                        tx1, ty1, tx2, ty2 = track.bbox
                        tcx = (tx1 + tx2) / 2
                        tcy = (ty1 + ty2) / 2
                        norm_dist = ((dcx - tcx) ** 2 + (dcy - tcy) ** 2) ** 0.5 / det_diag
                        if norm_dist < CENTER_DIST_LIMIT and norm_dist < best_center_dist:
                            best_center_dist  = norm_dist
                            best_center_track = track

            if best_track:
                return best_track

            if best_center_track:
                self.logger.info(
                    f"[TRACK_CENTERMATCH] track={best_center_track.track_id} "
                    f"matched by centre-dist={best_center_dist:.2f} "
                    f"(IoU too low — vehicle moved between frames)"
                )
                return best_center_track

            return None

        except Exception as e:
            self.logger.warning(f"Track matching error: {e}")
            return None
    
    def _update_track(self, track: VehicleTrack, detection: Dict[str, Any],
                      frame: np.ndarray, current_time: float,
                      plate_bbox: Optional[List[float]] = None):
        """
        Update existing track with new detection.

        Parameters
        ----------
        plate_bbox : Optional[List[float]]
            Bounding box [x1,y1,x2,y2] of the licence plate detected in *this frame*,
            or None when no plate was found.

        ── FIX: best_frame_data now requires plate visibility ──────────────────
        best_frame_data is used as the OCR source crop.  If it were updated for
        every sharp vehicle frame (including side / rear views where no plate is
        visible), OCR would consistently get a crop without the plate, causing
        blank or wrong results AND saving rear-view images in the DB.

        New policy:
        • With plate_bbox   → update best_frame_data when score improves (same
                              as before, but now we KNOW a plate is in the frame).
        • Without plate_bbox → update score for tracking purposes but do NOT
                              replace best_frame_data.  Keeps the most recent
                              front-facing frame as the OCR source.
        ────────────────────────────────────────────────────────────────────────
        """
        try:
            # Update track properties
            track.bbox = detection.get('bbox', track.bbox)
            track.confidence = detection.get('score', track.confidence)
            track.last_seen = current_time
            track.frame_count += 1

            # Update IoU history
            if track.iou_history:
                prev_bbox = track.iou_history[-1] if track.iou_history else track.bbox
                iou = self._calculate_iou(track.bbox, prev_bbox)
                track.iou_history.append(iou)

            # Score with plate sharpness bonus when plate is visible
            current_score = self._calculate_frame_score(detection, frame, plate_bbox)
            prev_score = track.best_frame_score

            if plate_bbox is not None:
                # Plate is visible in this frame — eligible to become best_frame_data
                if current_score > track.best_frame_score:
                    old_fid = id(track.best_frame_data) % 1_000_000 \
                              if track.best_frame_data is not None else 0
                    track.best_frame_score = current_score
                    track.best_frame_data  = frame.copy()
                    new_fid = id(track.best_frame_data) % 1_000_000
                    self.logger.info(
                        f"[BEST_FRAME_UPDATE] track={track.track_id} "
                        f"score {prev_score:.3f}→{current_score:.3f} "
                        f"old_fid={old_fid} new_fid={new_fid} "
                        f"frame_count={track.frame_count} "
                        f"plate_visible=YES plates_so_far={len(track.plate_candidates)}"
                    )

                # Populate plate_crop_buffer for async OCR.
                #
                # Gate order (fail-fast):
                #   1. ar >= 1.5 on the RAW (unpadded) bbox — rejects square
                #      false positives (bumpers, bodywork) before any work.
                #   2. Apply 25% safe padding to give Tesseract context pixels.
                #   3. padded W >= 120px AND H >= 45px — minimum for reliable
                #      LSTM OCR on Thai plates at MAIN=2304×1296 resolution.
                #
                # Laplacian is measured AFTER applying CLAHE so the sharpness
                # score reflects the same contrast-normalised image that
                # preprocess_plate_crop() will send to Tesseract.
                #
                # submit_for_ocr picks the highest-Laplacian crop from the buffer.
                try:
                    x1_raw = int(plate_bbox[0]); y1_raw = int(plate_bbox[1])
                    x2_raw = int(plate_bbox[2]); y2_raw = int(plate_bbox[3])
                    cw_raw = x2_raw - x1_raw
                    ch_raw = y2_raw - y1_raw
                    aspect = cw_raw / ch_raw if ch_raw > 0 else 0.0

                    if aspect < 1.5:
                        # Square / tall crop → false positive (bumper, bodywork)
                        self.logger.info(
                            f"[PLATE_CROP_SKIP] track={track.track_id} "
                            f"raw={cw_raw}×{ch_raw}px ar={aspect:.2f} "
                            f"— rejected (ar<1.5, likely false positive)")
                    else:
                        # Apply safe padding: +25% on each side
                        pad_x = max(10, int(cw_raw * 0.25))
                        pad_y = max(5,  int(ch_raw * 0.25))
                        x1 = max(0, x1_raw - pad_x)
                        y1 = max(0, y1_raw - pad_y)
                        x2 = min(frame.shape[1], x2_raw + pad_x)
                        y2 = min(frame.shape[0], y2_raw + pad_y)
                        cw, ch = x2 - x1, y2 - y1

                        if cw >= 120 and ch >= 45:
                            crop = frame[y1:y2, x1:x2].copy()
                            if crop.size > 0:
                                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) \
                                       if crop.ndim == 3 else crop
                                # Measure sharpness on CLAHE-enhanced image
                                # (same normalisation path as preprocess_plate_crop)
                                _clahe = cv2.createCLAHE(
                                    clipLimit=3.0, tileGridSize=(4, 4))
                                gray_enh = _clahe.apply(gray)
                                lap = float(cv2.Laplacian(gray_enh, cv2.CV_64F).var())
                                track.plate_crop_buffer.append((lap, crop))
                                self.logger.info(
                                    f"[PLATE_CROP] track={track.track_id} "
                                    f"raw={cw_raw}×{ch_raw}px "
                                    f"padded={cw}×{ch}px "
                                    f"ar={aspect:.2f} lap={lap:.0f} "
                                    f"buf_depth={len(track.plate_crop_buffer)}")
                        else:
                            self.logger.info(
                                f"[PLATE_CROP_SKIP] track={track.track_id} "
                                f"raw={cw_raw}×{ch_raw}px padded={cw}×{ch}px "
                                f"ar={aspect:.2f} "
                                f"— rejected (need padded W>=120 H>=45)")
                except Exception as _crop_err:
                    self.logger.debug(f"[PLATE_CROP] crop error: {_crop_err}")

            else:
                # No plate in this frame — update score for tracking only (no frame copy)
                # This prevents rear/side views from becoming the OCR source
                if current_score > track.best_frame_score:
                    self.logger.debug(
                        f"[BEST_FRAME_SKIP] track={track.track_id} "
                        f"score {prev_score:.3f}→{current_score:.3f} "
                        f"plate_visible=NO — keeping existing best_frame_data"
                    )
                    # Update score so dedup/gating reflects frame quality
                    # but do NOT touch best_frame_data (no plate = no value for OCR)
                    track.best_frame_score = current_score

        except Exception as e:
            self.logger.warning(f"Track update error: {e}")
    
    def _create_new_track(self, detection: Dict[str, Any], frame: np.ndarray, current_time: float) -> VehicleTrack:
        """Create new track from detection."""
        try:
            track_id = self.next_track_id
            self.next_track_id += 1
            
            # Calculate initial frame score
            frame_score = self._calculate_frame_score(detection, frame)
            
            track = VehicleTrack(
                track_id=track_id,
                bbox=detection.get('bbox', []),
                confidence=detection.get('score', 0.0),
                first_seen=current_time,
                last_seen=current_time,
                frame_count=1,
                best_frame_score=frame_score,
                best_frame_data=frame.copy()
            )
            
            self.logger.debug(f"🔧 [TRACKING] Created new track {track_id} with score {frame_score:.3f}")
            return track
            
        except Exception as e:
            self.logger.warning(f"Track creation error: {e}")
            return None
    
    def _calculate_plate_region_sharpness(self, frame: np.ndarray, plate_bbox: List[float]) -> float:
        """
        Calculate sharpness specifically for license plate region.
        
        Args:
            frame: Full frame image
            plate_bbox: Bounding box of license plate [x1, y1, x2, y2]
            
        Returns:
            float: Sharpness score (Laplacian variance) for plate region
        """
        try:
            if len(plate_bbox) < 4:
                return 0.0
            
            # Extract plate region
            x1, y1, x2, y2 = int(plate_bbox[0]), int(plate_bbox[1]), int(plate_bbox[2]), int(plate_bbox[3])
            
            # Ensure coordinates are within frame bounds
            h, w = frame.shape[:2]
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            
            if x2 <= x1 or y2 <= y1:
                return 0.0
            
            plate_region = frame[y1:y2, x1:x2]
            
            if plate_region.size == 0:
                return 0.0
            
            # Convert to grayscale if needed
            if len(plate_region.shape) == 3:
                gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_region
            
            # Calculate Laplacian variance for sharpness
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            return float(laplacian_var)
            
        except Exception as e:
            self.logger.warning(f"Plate region sharpness calculation error: {e}")
            return 0.0
    
    def _calculate_frame_score(self, detection: Dict[str, Any], frame: np.ndarray, plate_bbox: Optional[List[float]] = None) -> float:
        """
        Calculate weighted score for best frame selection.
        Score = a*sharpness + b*plate_conf + y*area_ratio + k*plate_centeredness + p*plate_sharpness
        
        Args:
            detection: Vehicle detection dictionary
            frame: Full frame image
            plate_bbox: Optional license plate bounding box for plate-specific sharpness
        """
        try:
            # Calculate overall frame sharpness (Laplacian variance)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(sharpness / 1000.0, 1.0)  # Normalize to 0-1
            
            # Calculate plate region sharpness if plate bbox provided
            plate_sharpness_score = 0.0
            if plate_bbox and len(plate_bbox) >= 4:
                plate_sharpness = self._calculate_plate_region_sharpness(frame, plate_bbox)
                plate_sharpness_score = min(plate_sharpness / 1000.0, 1.0)  # Normalize to 0-1
            
            # Plate confidence (from detection)
            plate_conf = detection.get('score', 0.0)
            
            # Area ratio (detection area / frame area)
            bbox = detection.get('bbox', [0, 0, 0, 0])
            if len(bbox) >= 4:
                detection_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                frame_area = frame.shape[0] * frame.shape[1]
                area_ratio = min(detection_area / frame_area, 1.0)
            else:
                area_ratio = 0.0
            
            # Plate centeredness (how centered the detection is in frame)
            if len(bbox) >= 4:
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                frame_center_x = frame.shape[1] / 2
                frame_center_y = frame.shape[0] / 2
                
                distance_from_center = np.sqrt((center_x - frame_center_x)**2 + (center_y - frame_center_y)**2)
                max_distance = np.sqrt(frame_center_x**2 + frame_center_y**2)
                centeredness = 1.0 - (distance_from_center / max_distance)
            else:
                centeredness = 0.0
            
            # Calculate weighted score
            weights = self.frame_score_weights
            # Combine frame sharpness and plate sharpness (prefer plate sharpness if available)
            combined_sharpness = plate_sharpness_score if plate_sharpness_score > 0 else sharpness_score
            
            score = (weights['sharpness'] * combined_sharpness +
                    weights['plate_confidence'] * plate_conf +
                    weights['area_ratio'] * area_ratio +
                    weights['plate_centeredness'] * centeredness)
            # ─── [DIAG H3] Frame Score Breakdown Log ───────────────────
            self.logger.info(
                f"[FRAME_SCORE] "
                f"track={detection.get('track_id','?')} | "
                f"sharpness={combined_sharpness:.3f} "
                f"(plate={plate_sharpness_score:.3f} frame={sharpness_score:.3f}) | "
                f"conf={plate_conf:.3f} | "
                f"area={area_ratio:.3f} | "
                f"center={centeredness:.3f} | "
                f"SCORE={score:.3f}"
            )
            # สิ่งที่ต้องสังเกต: ถ้า score สูง แต่ OCR ยังล้มเหลว
            # → sharpness ต่ำ → ยืนยัน H3: scoring ไม่สัมพันธ์กับ OCR quality
            # ─────────────────────────────────────────────────────────────
            return score
            
        except Exception as e:
            self.logger.warning(f"Frame score calculation error: {e}")
            return 0.0
    
    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes."""
        try:
            if len(bbox1) < 4 or len(bbox2) < 4:
                return 0.0
            
            # Calculate intersection
            x1 = max(bbox1[0], bbox2[0])
            y1 = max(bbox1[1], bbox2[1])
            x2 = min(bbox1[2], bbox2[2])
            y2 = min(bbox1[3], bbox2[3])
            
            if x2 <= x1 or y2 <= y1:
                return 0.0
            
            intersection = (x2 - x1) * (y2 - y1)
            
            # Calculate union
            area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
            area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
            union = area1 + area2 - intersection
            
            if union <= 0:
                return 0.0
            
            return intersection / union
            
        except Exception as e:
            self.logger.warning(f"IoU calculation error: {e}")
            return 0.0
    
    def apply_deduplication_rules(self, tracks: List[VehicleTrack]) -> List[VehicleTrack]:
        """
        Apply deduplication rules to prevent duplicate vehicle detection.
        
        Args:
            tracks: List of vehicle tracks
            
        Returns:
            List[VehicleTrack]: Filtered tracks after deduplication
        """
        try:
            with self._track_lock:
                filtered_tracks = []
                current_time = time.time()
                
                for track in tracks:
                    if self._should_keep_track(track, current_time):
                        filtered_tracks.append(track)
                    else:
                        self.logger.info(
                            f"[DEDUP_FILTER] track={track.track_id} removed "
                            f"(too similar to another active track)"
                        )

                self.logger.info(
                    f"[DEDUP_SUMMARY] kept={len(filtered_tracks)}/{len(tracks)} tracks "
                    f"after deduplication"
                )
                return filtered_tracks
                
        except Exception as e:
            self.logger.error(f"🔧 [DEDUPLICATION] Deduplication error: {e}")
            return tracks
    
    def _should_keep_track(self, track: VehicleTrack, current_time: float) -> bool:
        """
        Determine if track should be kept based on deduplication rules.
        
        Rules:
        1. If same car has track id and time between finalize of old track and start of new track < reentry_time_thresh
        2. And similarity (IoU or small displacement) > 0.2, don't record new
        """
        try:
            # Check for recent similar tracks
            for existing_track_id, existing_track in self.active_tracks.items():
                if existing_track_id == track.track_id:
                    continue
                
                # Check time difference
                time_diff = current_time - existing_track.last_seen
                if time_diff < self.reentry_time_threshold:
                    # Check similarity
                    iou = self._calculate_iou(track.bbox, existing_track.bbox)
                    if iou > self.iou_threshold:
                        self.logger.info(
                            f"[DEDUP_MATCH] track={track.track_id} overlaps "
                            f"track={existing_track_id} iou={iou:.3f} "
                            f"age={time_diff:.1f}s → filtered as duplicate"
                        )
                        return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Deduplication rule check error: {e}")
            return True
    
    # Coordinate Mapping and Letterbox Resizing Utilities
    
    def map_coordinates_to_original(self, bbox: List[float], mapping_info: Dict[str, Any]) -> List[float]:
        """
        Map coordinates from resized frame back to original frame.
        
        Args:
            bbox: Bounding box in resized frame [x1, y1, x2, y2]
            mapping_info: Mapping information from resize_with_letterbox
            
        Returns:
            List[float]: Bounding box in original frame coordinates
        """
        try:
            if 'error' in mapping_info:
                return bbox
            
            scale = mapping_info['scale']
            offset_x, offset_y = mapping_info['offset']
            
            # Remove padding offset and scale back to original
            x1 = (bbox[0] - offset_x) / scale
            y1 = (bbox[1] - offset_y) / scale
            x2 = (bbox[2] - offset_x) / scale
            y2 = (bbox[3] - offset_y) / scale
            
            # Clamp to original frame bounds
            orig_w, orig_h = mapping_info['original_size']
            x1 = max(0, min(x1, orig_w))
            y1 = max(0, min(y1, orig_h))
            x2 = max(0, min(x2, orig_w))
            y2 = max(0, min(y2, orig_h))
            
            return [x1, y1, x2, y2]
            
        except Exception as e:
            self.logger.warning(f"Coordinate mapping failed: {e}")
            return bbox
    
    def crop_with_safe_padding(self, frame: np.ndarray, bbox: List[float], 
                              padding_ratio: float = 0.1) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Crop region with safe padding to avoid edge artifacts.
        
        Args:
            frame: Input frame
            bbox: Bounding box [x1, y1, x2, y2]
            padding_ratio: Padding ratio (0.1 = 10% padding)
            
        Returns:
            Tuple of (cropped_region, crop_info)
        """
        try:
            if len(bbox) < 4:
                return frame, {'error': 'Invalid bbox'}
            
            x1, y1, x2, y2 = bbox
            frame_h, frame_w = frame.shape[:2]
            
            # Calculate region dimensions
            region_w = x2 - x1
            region_h = y2 - y1
            
            # Calculate padding
            pad_w = int(region_w * padding_ratio)
            pad_h = int(region_h * padding_ratio)
            
            # Apply padding with bounds checking
            crop_x1 = max(0, int(x1 - pad_w))
            crop_y1 = max(0, int(y1 - pad_h))
            crop_x2 = min(frame_w, int(x2 + pad_w))
            crop_y2 = min(frame_h, int(y2 + pad_h))
            
            # Crop the region
            cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]
            
            # Create crop information
            crop_info = {
                'original_bbox': bbox,
                'crop_bbox': [crop_x1, crop_y1, crop_x2, crop_y2],
                'padding_applied': (pad_w, pad_h),
                'padding_ratio': padding_ratio,
                'crop_size': (crop_x2 - crop_x1, crop_y2 - crop_y1)
            }
            
            return cropped, crop_info
            
        except Exception as e:
            self.logger.warning(f"Safe padding crop failed: {e}")
            return frame, {'error': str(e)}
    
    def _enhance_plate_for_ocr(self, plate_region: np.ndarray) -> np.ndarray:
        """
        Enhance license plate region specifically for OCR accuracy.
        
        Args:
            plate_region: Cropped license plate region
            
        Returns:
            np.ndarray: Enhanced plate region optimized for OCR
        """
        try:
            # Convert to grayscale for processing
            if len(plate_region.shape) == 3:
                gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_region
            
            # Apply CLAHE for contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # Apply adaptive threshold for better text clarity
            enhanced = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            
            # Convert back to BGR for consistency
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
            
            return enhanced
            
        except Exception as e:
            self.logger.warning(f"Plate OCR enhancement failed: {e}")
            return plate_region
    
    def resize_for_model_input(self, frame: np.ndarray, model_input_size: Tuple[int, int]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Resize frame for model input with letterboxing and coordinate mapping.
        
        Args:
            frame: Input frame
            model_input_size: Model input size (width, height)
            
        Returns:
            Tuple of (resized_frame, mapping_info)
        """
        try:
            # Letterbox resize — preserves aspect ratio with padding
            target_w, target_h = model_input_size
            frame_h, frame_w = frame.shape[:2]
            scale = min(target_w / frame_w, target_h / frame_h)
            new_w, new_h = int(frame_w * scale), int(frame_h * scale)
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            canvas = np.full((target_h, target_w, 3), (114, 114, 114), dtype=np.uint8)
            pad_x = (target_w - new_w) // 2
            pad_y = (target_h - new_h) // 2
            canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
            mapping_info = {
                'original_size': (frame_w, frame_h),
                'target_size': (target_w, target_h),
                'scale': scale,
                'new_size': (new_w, new_h),
                'padding': (pad_x, pad_y),
                'offset': (pad_x, pad_y),
                'model_input_size': model_input_size,
                'resize_method': 'letterbox',
                'aspect_ratio_preserved': True,
            }
            return canvas, mapping_info

        except Exception as e:
            self.logger.error(f"Model input resize failed: {e}")
            return cv2.resize(frame, model_input_size), {'error': str(e)}