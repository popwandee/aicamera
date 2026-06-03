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
    TRACKING_ENABLED, REENTRY_TIME_THRESHOLD, IOU_THRESHOLD
)
from edge.src.components.async_ocr_loader import AsyncOCRLoader
from edge.src.components.parallel_ocr_processor import ParallelOCRProcessor
from edge.src.components.thai_lp_ocr import ThaiLPROCR, preprocess_plate_crop, validate_thai_plate
from edge.src.components.ocr_queue_worker import OcrQueueWorker, OcrTask

logger = get_logger(__name__)


class ProcessingStage(Enum):
    """Processing stages in the enhanced detection pipeline."""
    MOTION_DETECTION = "motion_detection"
    PREPROCESSING = "preprocessing"
    VEHICLE_DETECTION = "vehicle_detection"
    TRACKING = "tracking"
    PLATE_DETECTION = "plate_detection"
    OCR_PROCESSING = "ocr_processing"
    POSTPROCESSING = "postprocessing"
    STORAGE = "storage"


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
    plate_crop_buffer: deque = None      # (laplacian_var, crop_bgr) — maxlen=5

    def __post_init__(self):
        if self.plate_candidates is None:
            self.plate_candidates = []
        if self.ocr_results is None:
            self.ocr_results = []
        if self.iou_history is None:
            self.iou_history = deque(maxlen=10)
        if self.plate_crop_buffer is None:
            self.plate_crop_buffer = deque(maxlen=5)


@dataclass
class ProcessingMetrics:
    """Processing performance metrics."""
    motion_detection_time: float = 0.0
    preprocessing_time: float = 0.0
    vehicle_detection_time: float = 0.0
    tracking_time: float = 0.0
    plate_detection_time: float = 0.0
    ocr_time: float = 0.0
    total_time: float = 0.0
    frames_skipped: int = 0
    vehicles_tracked: int = 0
    plates_detected: int = 0
    ocr_successful: int = 0


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
        
        # Motion Detection
        self.motion_detection_enabled = True
        self.motion_threshold = 0.1  # Threshold for motion detection
        self.previous_frame = None
        self.frame_buffer_size = 5  # Circular buffer for motion detection
        
        # Vehicle Tracking (use config values)
        self.tracking_enabled = TRACKING_ENABLED
        self.next_track_id = 1
        self.active_tracks: Dict[int, VehicleTrack] = {}
        self.track_timeout = 5.0  # seconds
        self.reentry_time_threshold = REENTRY_TIME_THRESHOLD  # seconds for deduplication (from config)
        self.iou_threshold = IOU_THRESHOLD  # IoU threshold for tracking (from config)
        
        # Best Frame Selection
        self.best_frame_selection_enabled = True
        self.frame_score_weights = {
            'sharpness': 0.4,
            'plate_confidence': 0.3,
            'area_ratio': 0.2,
            'plate_centeredness': 0.1
        }
        
        # Processing Pipeline
        self.pipeline_stage = ProcessingStage.MOTION_DETECTION
        self.processing_metrics = ProcessingMetrics()
        self.resource_limited_mode = True
        self.max_processing_time = 0.1  # 100ms max processing time
        
        # Image Processing
        self.lighting_condition = LightingCondition.NORMAL
        self.adaptive_processing = True
        self.quality_optimization = True
        
        # Storage Optimization
        self.image_quality = 85  # JPEG quality for storage
        self.storage_optimization = True
        
        # Thread Safety
        self._processing_lock = threading.RLock()
        self._track_lock = threading.RLock()

        # ── Async OCR Queue (Producer-Consumer) ────────────────────────────
        # Worker is created here but not started until load_models() completes
        # so ThaiLPROCR is ready before the worker thread begins.
        self.ocr_queue_worker: Optional[OcrQueueWorker] = None
        self._async_ocr_enabled: bool = True   # set False to fall back to sync

        # Gatekeeper thresholds for async submit
        self._ocr_min_plate_frames: int = 3    # wait for N frames before OCR
        self._ocr_min_frame_score: float = 0.3 # minimum best_frame_score

        # ROI trigger zone (normalized 0-1, disabled by default)
        self._roi_zone = {
            'enabled': False,
            'x1': 0.1, 'y1': 0.2,
            'x2': 0.9, 'y2': 0.8,
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
    
    def detect_motion(self, frame: np.ndarray) -> bool:
        """
        Detect motion/change in frame for efficient processing.
        
        Args:
            frame: Input image frame
            
        Returns:
            bool: True if significant motion detected, False otherwise
        """
        try:
            if not self.motion_detection_enabled or self.previous_frame is None:
                self.previous_frame = frame.copy()
                return True  # Process first frame
            
            # Convert to grayscale for motion detection
            gray_current = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_previous = cv2.cvtColor(self.previous_frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate frame difference
            frame_diff = cv2.absdiff(gray_current, gray_previous)
            
            # Apply threshold
            _, thresh = cv2.threshold(frame_diff, 30, 255, cv2.THRESH_BINARY)
            
            # Calculate motion percentage
            motion_pixels = np.sum(thresh > 0)
            total_pixels = thresh.shape[0] * thresh.shape[1]
            motion_ratio = motion_pixels / total_pixels
            
            # Update previous frame
            self.previous_frame = frame.copy()
            
            # Check if motion exceeds threshold
            motion_detected = motion_ratio > self.motion_threshold
            # ─── [DIAG H6] Motion Ratio Log ─────────────────────────
            self.logger.debug(
                f"[MOTION] ratio={motion_ratio:.4f} | "
                f"threshold={self.motion_threshold} | "
                f"detected={motion_detected} | "
                f"frames_skipped={self.processing_metrics.frames_skipped}"
            )
            # ────────────────────────────────────────────────────────
            if motion_detected:
                self.logger.debug(f"🔧 [MOTION_DETECTION] Motion detected: {motion_ratio:.3f} > {self.motion_threshold}")
            else:
                self.logger.debug(f"🔧 [MOTION_DETECTION] No significant motion: {motion_ratio:.3f} <= {self.motion_threshold}")
                self.processing_metrics.frames_skipped += 1
            
            return motion_detected
            
        except Exception as e:
            self.logger.error(f"🔧 [MOTION_DETECTION] Motion detection error: {e}")
            return True  # Process frame on error
    
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
    
    def enhance_for_storage(self, frame: np.ndarray) -> np.ndarray:
        """
        Enhance frame for natural color preservation in storage.
        
        Args:
            frame: Input image frame
            
        Returns:
            np.ndarray: Enhanced frame with natural colors
        """
        try:
            storage_frame = frame.copy()
            
            # Apply color correction for natural appearance
            storage_frame = self._apply_color_correction(storage_frame)
            
            # Apply brightness/contrast normalization
            storage_frame = self._normalize_brightness_contrast(storage_frame)
            
            # Apply noise reduction for storage quality
            storage_frame = self._apply_storage_noise_reduction(storage_frame)
            
            return storage_frame
            
        except Exception as e:
            self.logger.error(f"🔧 [STORAGE_ENHANCEMENT] Storage enhancement error: {e}")
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
                # ─── [DIAG H2] บันทึกขนาด bbox ก่อน crop ──────────────────
                bw = int(bbox[2] - bbox[0])
                bh = int(bbox[3] - bbox[1])
                self.logger.info(
                    f"[LP_SIZE] track={plate_box.get('vehicle_idx','?')} "
                    f"bbox_w={bw}px bbox_h={bh}px "
                    f"det_conf={plate_box.get('score',0):.3f}"
                )
                # ─────────────────────────────────────────────────────────────
                # ใช้ crop_with_safe_padding เพื่อขยายขอบ 15% สำหรับ OCR
                plate_region, crop_info = self.crop_with_safe_padding(frame, bbox, padding_ratio=0.15)
                
                if plate_region.size == 0:
                    self.logger.debug(f"🔧 [DETECTION_PROCESSOR] perform_ocr: plate {i} region is empty, skipping")
                    continue

                # Check plate quality before OCR processing
                quality_check = self._check_plate_quality(plate_region)
                if not quality_check['is_acceptable']:
                    self.logger.warning(f"🔧 [DETECTION_PROCESSOR] perform_ocr: plate {i} quality too low - {quality_check['reason']}, skipping OCR")
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
    
    def _create_high_quality_detection_pipeline(self, frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create high-quality frame for storage and detection-optimized frame for AI models.
        
        Returns:
            Tuple of (high_quality_frame, detection_frame)
        """
        try:
            # Keep original high-quality frame for storage
            high_quality_frame = frame.copy()
            
            # Create detection-optimized frame
            detection_frame = self._optimize_for_detection(frame)
            
            return high_quality_frame, detection_frame
            
        except Exception as e:
            self.logger.error(f"Failed to create detection pipeline: {e}")
            return frame, frame

    def _optimize_for_detection(self, frame: np.ndarray) -> np.ndarray:
        """Optimize frame specifically for detection models."""
        try:
            # Step 1: Apply quality enhancements before resizing
            enhanced_frame = self._enhance_frame_quality(frame)
            
            # Step 2: Smart resizing with letterboxing for aspect ratio preservation
            detection_frame = self._resize_with_letterbox(enhanced_frame, self.detection_resolution)
            
            # Step 3: Apply final detection-specific optimizations
            detection_frame = self._apply_detection_optimizations(detection_frame)
            
            return detection_frame
            
        except Exception as e:
            self.logger.error(f"Detection optimization failed: {e}")
            return cv2.resize(frame, self.detection_resolution)

    def _resize_with_letterbox(self, frame: np.ndarray, target_size: Tuple[int, int], 
                            padding_color: Tuple[int, int, int] = (114, 114, 114)) -> np.ndarray:
        """
        Resize frame to target size while preserving aspect ratio using letterboxing.
        
        Args:
            frame: Input frame
            target_size: Target (width, height)
            padding_color: BGR color for padding
            
        Returns:
            Resized frame with letterboxing
        """
        try:
            target_w, target_h = target_size
            frame_h, frame_w = frame.shape[:2]
            
            # Calculate scaling factor
            scale = min(target_w / frame_w, target_h / frame_h)
            
            # Calculate new dimensions
            new_w = int(frame_w * scale)
            new_h = int(frame_h * scale)
            
            # Resize frame
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Create target canvas with padding color
            canvas = np.full((target_h, target_w, 3), padding_color, dtype=np.uint8)
            
            # Calculate padding
            pad_x = (target_w - new_w) // 2
            pad_y = (target_h - new_h) // 2
            
            # Place resized frame on canvas
            canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
            
            return canvas
            
        except Exception as e:
            self.logger.error(f"Letterbox resizing failed: {e}")
            return cv2.resize(frame, target_size)

            # Add to DetectionProcessor
   
    def _enhance_frame_quality(self, frame: np.ndarray) -> np.ndarray:
        """Apply advanced image enhancement for better detection quality."""
        try:
            enhanced_frame = frame.copy()
            
            # Step 1: Noise reduction
            enhanced_frame = cv2.fastNlMeansDenoisingColored(enhanced_frame, None, 10, 10, 7, 21)
            
            # Step 2: Sharpening using unsharp masking
            enhanced_frame = self._apply_unsharp_masking(enhanced_frame, amount=1.5, radius=1.0, threshold=0)
            
            # Step 3: Contrast enhancement using CLAHE
            enhanced_frame = self._apply_clahe_enhancement(enhanced_frame)
            
            # Step 4: Brightness normalization
            enhanced_frame = self._normalize_brightness(enhanced_frame)
            
            return enhanced_frame
            
        except Exception as e:
            self.logger.warning(f"Frame enhancement failed: {e}")
            return frame

    def _apply_unsharp_masking(self, frame: np.ndarray, amount: float = 1.5, 
                          radius: float = 1.0, threshold: int = 0) -> np.ndarray:
        """Apply unsharp masking for image sharpening."""
        try:
            # Convert to float for processing
            frame_float = frame.astype(np.float32) / 255.0
            
            # Create Gaussian blur
            blurred = cv2.GaussianBlur(frame_float, (0, 0), radius)
            
            # Apply unsharp masking
            sharpened = frame_float + amount * (frame_float - blurred)
            
            # Clip values and convert back to uint8
            sharpened = np.clip(sharpened, 0, 1)
            return (sharpened * 255).astype(np.uint8)
            
        except Exception as e:
            self.logger.warning(f"Unsharp masking failed: {e}")
            return frame

            # Add to DetectionProcessor
   
    def _assess_frame_quality(self, frame: np.ndarray) -> Dict[str, Any]:
        """Assess overall frame quality for detection."""
        try:
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate Laplacian variance for sharpness
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Calculate brightness and contrast
            brightness = np.mean(gray)
            contrast = np.std(gray)
            
            # Calculate noise level using local variance
            noise_level = self._estimate_noise_level(gray)
            
            # Determine overall quality score
            quality_score = self._calculate_quality_score(laplacian_var, brightness, contrast, noise_level)
            
            return {
                'sharpness_score': laplacian_var,
                'brightness': brightness,
                'contrast': contrast,
                'noise_level': noise_level,
                'quality_score': quality_score,
                'overall_quality': 'excellent' if quality_score > 80 else 'good' if quality_score > 60 else 'fair' if quality_score > 40 else 'poor'
            }
            
        except Exception as e:
            self.logger.warning(f"Quality assessment failed: {e}")
            return {}

    def _calculate_quality_score(self, sharpness: float, brightness: float, 
                            contrast: float, noise: float) -> float:
        """Calculate overall quality score (0-100)."""
        try:
            # Normalize values to 0-100 scale
            sharpness_score = min(sharpness / 10.0, 100)  # Normalize sharpness
            brightness_score = 100 - abs(brightness - 128) / 1.28  # Optimal around 128
            contrast_score = min(contrast / 2.0, 100)  # Normalize contrast
            noise_score = max(100 - noise, 0)  # Lower noise = higher score
            
            # Weighted average
            weights = [0.4, 0.2, 0.2, 0.2]  # Sharpness is most important
            scores = [sharpness_score, brightness_score, contrast_score, noise_score]
            
            quality_score = sum(w * s for w, s in zip(weights, scores))
            return max(0, min(100, quality_score))
            
        except Exception as e:
            self.logger.warning(f"Quality score calculation failed: {e}")
            return 50.0  # Default middle score

    def _log_quality_metrics(self, frame: np.ndarray, detection_results: List[Dict[str, Any]]):
        """Log quality metrics for analytics and monitoring."""
        try:
            quality_metrics = self._assess_frame_quality(frame)
            
            # Add detection performance metrics
            quality_metrics.update({
                'detection_count': len(detection_results),
                'detection_confidence_avg': np.mean([d.get('confidence', 0) for d in detection_results]) if detection_results else 0,
                'timestamp': time.time(),
                'frame_shape': frame.shape
            })
            
            # Log to database or analytics system
            self._store_quality_metrics(quality_metrics)
            
            # Alert if quality is consistently poor
            if quality_metrics['overall_quality'] == 'poor':
                self._alert_poor_quality(quality_metrics)
                
        except Exception as e:
            self.logger.warning(f"Quality metrics logging failed: {e}")

    def _monitor_processing_performance(self):
        """Monitor detection processing performance."""
        try:
            current_time = time.time()
            
            # Calculate processing time
            if hasattr(self, '_last_processing_time'):
                processing_time = current_time - self._last_processing_time
                self._processing_times.append(processing_time)
                
                # Keep only last 100 measurements
                if len(self._processing_times) > 100:
                    self._processing_times.pop(0)
                    
                # Calculate average processing time
                avg_processing_time = np.mean(self._processing_times)
                
                # Alert if processing is too slow
                if avg_processing_time > 0.1:  # More than 100ms
                    self.logger.warning(f"Slow processing detected: {avg_processing_time:.3f}s average")
                    
            self._last_processing_time = current_time
            
        except Exception as e:
            self.logger.warning(f"Performance monitoring failed: {e}")
    
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
    
    def _apply_color_correction(self, frame: np.ndarray) -> np.ndarray:
        """Apply color correction for natural appearance."""
        try:
            # Apply white balance correction
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            lab[:, :, 1] = lab[:, :, 1] * 1.1  # Enhance a channel
            lab[:, :, 2] = lab[:, :, 2] * 1.1  # Enhance b channel
            corrected = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            return corrected
            
        except Exception as e:
            self.logger.warning(f"Color correction failed: {e}")
            return frame
    
    def _normalize_brightness_contrast(self, frame: np.ndarray) -> np.ndarray:
        """Normalize brightness and contrast."""
        try:
            # Apply histogram equalization
            yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
            normalized = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
            
            return normalized
            
        except Exception as e:
            self.logger.warning(f"Brightness/contrast normalization failed: {e}")
            return frame
    
    def _apply_storage_noise_reduction(self, frame: np.ndarray) -> np.ndarray:
        """Apply noise reduction for storage quality."""
        try:
            # Apply bilateral filter for noise reduction while preserving edges
            denoised = cv2.bilateralFilter(frame, 9, 75, 75)
            
            return denoised
            
        except Exception as e:
            self.logger.warning(f"Storage noise reduction failed: {e}")
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
            # Thai LP ≈ 2.8–3.8:1  |  reject garbage detections (squares, tall boxes)
            aspect_ratio = w / max(h, 1)
            if not (1.5 <= aspect_ratio <= 6.0):
                return {
                    'is_acceptable': False,
                    'reason': f'Aspect ratio {aspect_ratio:.2f} invalid for Thai LP '
                            f'(expected 1.5–6.0, got {w}×{h}px)'
                }

            # ── Convert to Grayscale ──────────────────────────────────────────
            if len(plate_region.shape) == 3:
                gray = cv2.cvtColor(plate_region, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_region

            # ── Sharpness Check (Laplacian Variance) ──────────────────────────
            # Normalize threshold by plate area — small crops naturally have lower variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            # Scale threshold: large plate → stricter (more expected detail)
            area_factor   = min(w * h / (128 * 40), 2.0)   # normalize to "good" size
            min_sharpness = 30.0 * area_factor              # 30–60 range
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

    def _should_submit_for_ocr(self, track: 'VehicleTrack', plate_bbox: List[float],
                                frame_shape: tuple) -> bool:
        """Gatekeeper — decide whether this track should be queued for OCR."""
        if track.ocr_submitted:
            # Silent: already handled, logged at submit time
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
            f"frames={len(track.plate_candidates)} score={track.best_frame_score:.3f} — submitting for OCR"
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

        # Pick sharpest crop from buffer; fall back to best_frame_data full frame
        plate_crop = None
        if track.plate_crop_buffer:
            plate_crop = max(track.plate_crop_buffer, key=lambda x: x[0])[1]
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
            best_lap = max((s for s, _ in track.plate_crop_buffer), default=0) \
                       if track.plate_crop_buffer else 0
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
        """Find best matching track for detection."""
        try:
            best_track = None
            best_iou = 0.0
            
            detection_bbox = detection.get('bbox', [])
            if not detection_bbox:
                return None
            
            for track in self.active_tracks.values():
                # Check if track is recent enough
                if current_time - track.last_seen > self.track_timeout:
                    continue
                
                # Calculate IoU
                iou = self._calculate_iou(detection_bbox, track.bbox)
                # ─── [DIAG H4] IoU Logging ──────────────────────────
                if iou > 0:  # log เฉพาะที่มีการ overlap บ้าง
                    self.logger.debug(
                        f"[IOUcheck] track={track.track_id} | "
                        f"iou={iou:.3f} | "
                        f"threshold={self.iou_threshold} | "
                        f"{'MATCH' if iou > self.iou_threshold else 'NO_MATCH'}"
                    )
                # ────────────────────────────────────────────────────
                if iou > self.iou_threshold and iou > best_iou:
                    best_iou = iou
                    best_track = track
            
            return best_track
            
        except Exception as e:
            self.logger.warning(f"Track matching error: {e}")
            return None
    
    def _update_track(self, track: VehicleTrack, detection: Dict[str, Any], frame: np.ndarray, current_time: float):
        """Update existing track with new detection."""
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
            
            # Update best frame if current frame is better
            current_score = self._calculate_frame_score(detection, frame)
            if current_score > track.best_frame_score:
                track.best_frame_score = current_score
                track.best_frame_data = frame.copy()
                self.logger.debug(f"🔧 [TRACKING] Updated best frame for track {track.track_id} with score {current_score:.3f}")
                # ─── [DIAG H3] Best Frame Updated ──────────────────────
                self.logger.info(
                    f"[FRAME] track_id={track.track_id} | "
                    f"new_best_score={current_score:.3f} | "
                    f"prev_score={track.best_frame_score:.3f} | "
                    f"frame_count={track.frame_count}"
                )
                # ────────────────────────────────────────────────────────
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
    
    # Enhanced Detection Pipeline Orchestration
    
    #def process_enhanced_pipeline(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
    def process_enhanced_pipeline(self, frame: np.ndarray,
                               frame_capture_time: float = None) -> Optional[Dict[str, Any]]:
        """
        Process frame through enhanced detection pipeline with event-driven orchestration.
        
        Pipeline Flow:
        1. Motion detection -> if no motion, skip entirely
        2. Preprocessing for detection
        3. Vehicle detection
        4. Tracking and deduplication
        5. Plate detection on best frames
        6. OCR processing
        7. Post-processing and storage
        
        Args:
            frame: Input image frame
            
        Returns:
            Optional[Dict[str, Any]]: Enhanced detection results or None if skipped
        """
        try:
            with self._processing_lock:
                start_time = time.perf_counter()

                # ─── [DIAG H1/H6] Frame Age Check ──────────────────────────
                if frame_capture_time is None:
                    frame_capture_time = start_time
                frame_age_ms = (start_time - frame_capture_time) * 1000
                self.logger.info(
                    f"[TIMING] frame_age={frame_age_ms:.0f}ms"
                )
                if frame_age_ms > 300:
                    self.logger.warning(
                        f"[STALE_FRAME] age={frame_age_ms:.0f}ms > 300ms — "
                        f"pipeline lag detected, skipping stale frame"
                    )
                    return None

                self.processing_metrics.total_time = 0.0
                
                # Step 1: Motion Detection
                motion_start = time.time()
                if not self.detect_motion(frame):
                    self.logger.debug("🔧 [PIPELINE] No motion detected - skipping frame")
                    self.processing_metrics.frames_skipped += 1
                    return None
                self.processing_metrics.motion_detection_time = time.time() - motion_start
                
                # Step 2: Preprocessing for Detection
                preprocess_start = time.time()
                enhanced_frame = self.enhance_for_detection(frame)
                self.processing_metrics.preprocessing_time = time.time() - preprocess_start
                
                # Step 3: Vehicle Detection
                detection_start = time.time()
                vehicle_boxes, mapping_info = self.detect_vehicles(enhanced_frame)
                if not vehicle_boxes:
                    self.logger.debug("🔧 [PIPELINE] No vehicles detected")
                    return None
                self.processing_metrics.vehicle_detection_time = time.time() - detection_start
                
                # Step 4: Tracking and Deduplication
                tracking_start = time.time()
                tracks = self.update_vehicle_tracks(vehicle_boxes, frame)
                filtered_tracks = self.apply_deduplication_rules(tracks)
                self.processing_metrics.tracking_time = time.time() - tracking_start
                self.processing_metrics.vehicles_tracked = len(filtered_tracks)
                
                if not filtered_tracks:
                    self.logger.debug("🔧 [PIPELINE] No tracks after deduplication")
                    return None
                
                # Step 5: Plate Detection on Best Frames
                plate_start = time.time()
                plate_results = []
                for track in filtered_tracks:
                    # Use best frame if available, otherwise use current frame
                    frame_for_plate = track.best_frame_data if track.best_frame_data is not None else frame

                    # Detect plates in vehicle region
                    plates = self.detect_license_plates(frame_for_plate, [{'bbox': track.bbox, 'score': track.confidence}])
                    track.plate_candidates.extend(plates)
                    plate_results.extend(plates)

                    # Buffer plate crops for async OCR best-frame selection
                    if self._async_ocr_enabled and plates:
                        for plate in plates:
                            x1, y1, x2, y2 = plate['bbox']
                            crop = frame_for_plate[int(y1):int(y2), int(x1):int(x2)]
                            if crop.size > 0:
                                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
                                blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                                track.plate_crop_buffer.append((blur_score, crop.copy()))

                self.processing_metrics.plate_detection_time = time.time() - plate_start
                self.processing_metrics.plates_detected = len(plate_results)

                # Step 6: OCR Processing
                ocr_start = time.time()
                ocr_results = []

                # Step 6a: Poll for completed async OCR results from previous frames (non-blocking)
                async_polled = self.poll_ocr_results()
                if async_polled:
                    ocr_results.extend(async_polled)
                    self.logger.info(
                        f"[PIPELINE] Polled {len(async_polled)} async OCR result(s) "
                        f"from background worker"
                    )

                # Step 6b: Submit current-frame plates to async queue OR run sync fallback
                if plate_results:
                    if self._async_ocr_enabled and self.ocr_queue_worker:
                        # Async path — non-blocking submit; OCR runs in background thread
                        from edge.src.core.config import AICAMERA_ID
                        frame_ts = time.time()
                        for track in filtered_tracks:
                            if track.plate_candidates:
                                best_plate = max(
                                    track.plate_candidates,
                                    key=lambda p: p.get('score', 0.0)
                                )
                                self.submit_for_ocr(
                                    track=track,
                                    plate_bbox=best_plate['bbox'],
                                    det_confidence=best_plate.get('score', 0.0),
                                    frame_timestamp=frame_ts,
                                    camera_id=AICAMERA_ID,
                                    frame_shape=frame.shape,
                                )
                    else:
                        # Sync fallback — blocking OCR (legacy behaviour, kept intact)
                        for track in filtered_tracks:
                            if track.plate_candidates:
                                ocr_frame = track.best_frame_data if track.best_frame_data is not None else frame
                                enhanced_plates = []
                                for plate in track.plate_candidates:
                                    x1, y1, x2, y2 = plate['bbox']
                                    plate_region = ocr_frame[int(y1):int(y2), int(x1):int(x2)]
                                    if plate_region.size > 0:
                                        enhanced_plate_region = self.enhance_for_ocr(plate_region)
                                        enhanced_plates.append({
                                            'bbox': plate['bbox'],
                                            'score': plate['score'],
                                            'enhanced_region': enhanced_plate_region
                                        })
                                if enhanced_plates:
                                    track_ocr = self.perform_ocr_on_enhanced_plates(enhanced_plates)
                                    track.ocr_results.extend(track_ocr)
                                    ocr_results.extend(track_ocr)

                self.processing_metrics.ocr_time = time.time() - ocr_start
                self.processing_metrics.ocr_successful = len(ocr_results)
                
                # Step 7: Post-processing and Storage
                storage_start = time.time()
                storage_frame = self.enhance_for_storage(frame)
                storage_results = self.save_enhanced_detection_results(
                    storage_frame, filtered_tracks, plate_results, ocr_results
                )
                storage_time = time.time() - storage_start
                
                # Calculate total processing time
                total_time = time.time() - start_time
                self.processing_metrics.total_time = total_time
                
                # Check resource limits
                if self.resource_limited_mode and total_time > self.max_processing_time:
                    self.logger.warning(f"🔧 [PIPELINE] Processing time exceeded limit: {total_time:.3f}s > {self.max_processing_time}s")
                
                # Create enhanced results
                enhanced_results = {
                    'timestamp': datetime.now().isoformat(),
                    'processing_metrics': {
                        'motion_detection_time': self.processing_metrics.motion_detection_time,
                        'preprocessing_time': self.processing_metrics.preprocessing_time,
                        'vehicle_detection_time': self.processing_metrics.vehicle_detection_time,
                        'tracking_time': self.processing_metrics.tracking_time,
                        'plate_detection_time': self.processing_metrics.plate_detection_time,
                        'ocr_time': self.processing_metrics.ocr_time,
                        'total_time': total_time,
                        'frames_skipped': self.processing_metrics.frames_skipped,
                        'vehicles_tracked': self.processing_metrics.vehicles_tracked,
                        'plates_detected': self.processing_metrics.plates_detected,
                        'ocr_successful': self.processing_metrics.ocr_successful
                    },
                    'tracks': [
                        {
                            'track_id': track.track_id,
                            'bbox': track.bbox,
                            'confidence': track.confidence,
                            'frame_count': track.frame_count,
                            'best_frame_score': track.best_frame_score,
                            'plate_candidates': track.plate_candidates,
                            'ocr_results': track.ocr_results
                        }
                        for track in filtered_tracks
                    ],
                    'plates': plate_results,
                    'ocr_results': ocr_results,
                    'storage_results': storage_results,
                    'lighting_condition': self.lighting_condition.value,
                    'pipeline_stage': self.pipeline_stage.value
                }
                
                self.logger.info(f"🔧 [PIPELINE] Enhanced processing completed: {len(filtered_tracks)} tracks, {len(plate_results)} plates, {len(ocr_results)} OCR in {total_time:.3f}s")
                
                self.logger.debug(f"🔧 [PIPELINE] Start time {start_time}, Motion detection {motion_start}, Preprocessing {preprocessing_start}, Vehicle detection {detection_start}, Tracking {tracking_start}, Plate detection {plate_start}, OCR {ocr_start}, Storage {storage_start}")
                # ─── [DIAG H1] Structured Timing Log ───────────────────────
                self.logger.info(
                    f"[PROCESS ENHANCED PIPELINE TIMING] "
                    f"frame age={frame_age_ms:.0f}ms | "
                    f"motion={self.processing_metrics.motion_detection_time*1000:.0f}ms | "
                    f"preprocess={self.processing_metrics.preprocessing_time*1000:.0f}ms | "
                    f"vehicle={self.processing_metrics.vehicle_detection_time*1000:.0f}ms | "
                    f"plate={self.processing_metrics.plate_detection_time*1000:.0f}ms | "
                    f"ocr={self.processing_metrics.ocr_time*1000:.0f}ms | "
                    f"storage={storage_time*1000:.0f}ms | "
                    f"total={total_time*1000:.0f}ms"
                )
                # สิ่งที่ต้องสังเกต: ถ้า ocr= สูงมาก (>500ms) และ total= สูงตาม
                # → ยืนยัน H1: OCR Blocking หลัก Pipeline
                # ─────────────────────────────────────────────────────────────
                return enhanced_results
                
        except Exception as e:
            self.logger.error(f"🔧 [PIPELINE] Enhanced pipeline error: {e}")
            return None
    
    def perform_ocr_on_enhanced_plates(self, enhanced_plates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Perform OCR on enhanced plate regions.
        
        Args:
            enhanced_plates: List of enhanced plate regions
            
        Returns:
            List[Dict[str, Any]]: OCR results
        """
        try:
            ocr_results = []
            
            for i, plate_data in enumerate(enhanced_plates):
                enhanced_region = plate_data['enhanced_region']
                bbox = plate_data['bbox']
                confidence = plate_data['score']
                
                # Use parallel OCR processing if available
                if self.parallel_ocr_processor:
                    try:
                        parallel_results = self.parallel_ocr_processor.process_plate_parallel(
                            enhanced_region, i, timeout=5.0
                        )
                        
                        if parallel_results and parallel_results.get('best_result', {}).get('success'):
                            best_result = parallel_results['best_result']
                            ocr_result = {
                                'plate_idx': i,
                                'bbox': bbox,
                                'text': best_result['text'],
                                'confidence': best_result['confidence'],
                                'detection_confidence': confidence,
                                'ocr_method': best_result['method'],
                                'enhanced_processing': True,
                                'parallel_results': parallel_results
                            }
                            ocr_results.append(ocr_result)
                            
                    except Exception as e:
                        self.logger.warning(f"Parallel OCR failed for enhanced plate {i}: {e}")
                
                # Fallback to individual OCR methods
                if not ocr_results or len(ocr_results) <= i:
                    # Try Hailo OCR first
                    hailo_text = ""
                    hailo_confidence = 0.0
                    hailo_success = False
                    
                    if self.lp_ocr_model:
                        try:
                            ocr_result = self.lp_ocr_model(enhanced_region)
                            hailo_text = str(ocr_result)
                            hailo_confidence = 0.8
                            hailo_success = True
                        except Exception as e:
                            self.logger.debug(f"Hailo OCR failed for enhanced plate {i}: {e}")
                    
                    # Try legacy EasyOCR via async_ocr_loader (last-resort fallback)
                    easyocr_text = ""
                    easyocr_confidence = 0.0
                    easyocr_success = False
                    
                    if self.async_ocr_loader.is_ready():
                        try:
                            easyocr_results = self.async_ocr_loader.read_text(enhanced_region)
                            if easyocr_results:
                                best_result = max(easyocr_results, key=lambda x: x[2])
                                easyocr_text = best_result[1]
                                easyocr_confidence = best_result[2]
                                easyocr_success = True
                        except Exception as e:
                            self.logger.debug(f"EasyOCR failed for enhanced plate {i}: {e}")
                    
                    # Choose best result
                    if hailo_success and easyocr_success:
                        # Use the one with higher confidence
                        if hailo_confidence > easyocr_confidence:
                            final_text = hailo_text
                            final_confidence = hailo_confidence
                            ocr_method = "hailo"
                        else:
                            final_text = easyocr_text
                            final_confidence = easyocr_confidence
                            ocr_method = "easyocr"
                    elif hailo_success:
                        final_text = hailo_text
                        final_confidence = hailo_confidence
                        ocr_method = "hailo"
                    elif easyocr_success:
                        final_text = easyocr_text
                        final_confidence = easyocr_confidence
                        ocr_method = "easyocr"
                    else:
                        continue
                    
                    ocr_result = {
                        'plate_idx': i,
                        'bbox': bbox,
                        'text': final_text.strip(),
                        'confidence': final_confidence,
                        'detection_confidence': confidence,
                        'ocr_method': ocr_method,
                        'enhanced_processing': True,
                        'hailo_ocr': {
                            'text': hailo_text.strip() if hailo_success else "",
                            'confidence': hailo_confidence,
                            'success': hailo_success
                        },
                        'easyocr': {
                            'text': easyocr_text.strip() if easyocr_success else "",
                            'confidence': easyocr_confidence,
                            'success': easyocr_success
                        }
                    }
                    ocr_results.append(ocr_result)
            
            return ocr_results
            
        except Exception as e:
            self.logger.error(f"Enhanced OCR processing error: {e}")
            return []
    
    def save_enhanced_detection_results(self, storage_frame: np.ndarray, tracks: List[VehicleTrack], 
                                      plates: List[Dict], ocr_results: List[Dict]) -> Dict[str, Any]:
        """
        Save enhanced detection results with optimized storage.
        
        Args:
            storage_frame: Frame enhanced for storage
            tracks: Vehicle tracks
            plates: Detected plates
            ocr_results: OCR results
            
        Returns:
            Dict[str, Any]: Storage results
        """
        try:
            # Generate timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            
            # Ensure directory exists
            Path(IMAGE_SAVE_DIR).mkdir(parents=True, exist_ok=True)
            
            # Save original image with 85% quality for storage optimization
            original_filename = f"detection_{timestamp}.jpg"
            original_path = os.path.join(IMAGE_SAVE_DIR, original_filename)
            
            # Apply storage optimization
            t_write = time.perf_counter()
            if self.storage_optimization:
                success = cv2.imwrite(original_path, storage_frame, [cv2.IMWRITE_JPEG_QUALITY, self.image_quality])
            else:
                success = cv2.imwrite(original_path, storage_frame)
            t_write_ms = (time.perf_counter() - t_write) * 1000

            if not success or not os.path.exists(original_path):
                self.logger.error(f"[IMG_SAVE] FAIL write {original_path}")
                return {'success': False, 'error': 'Image save failed'}

            # Verify file size
            file_size = os.path.getsize(original_path)
            if file_size <= 0:
                self.logger.error(f"[IMG_SAVE] FAIL empty file {original_path}")
                return {'success': False, 'error': 'Empty image file'}

            self.logger.info(
                f"[IMG_SAVE] {original_filename} "
                f"size={file_size//1024}KB write={t_write_ms:.0f}ms "
                f"quality={self.image_quality}% tracks={len(tracks)} plates={len(plates)}"
            )

            storage_results = {
                'success': True,
                'original_image_path': original_path,
                'relative_path': f"captured_images/{original_filename}",
                'file_size_bytes': file_size,
                'image_quality': self.image_quality,
                'storage_optimized': self.storage_optimization,
                'timestamp': timestamp,
                'tracks_count': len(tracks),
                'plates_count': len(plates),
                'ocr_results_count': len(ocr_results)
            }
            
            return storage_results
            
        except Exception as e:
            self.logger.error(f"Enhanced storage error: {e}")
            return {'success': False, 'error': str(e)}
    
    # Coordinate Mapping and Letterbox Resizing Utilities
    
    def resize_with_letterbox(self, frame: np.ndarray, target_size: Tuple[int, int], 
                            padding_color: Tuple[int, int, int] = (114, 114, 114)) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Resize frame to target size while preserving aspect ratio using letterboxing.
        
        Args:
            frame: Input frame
            target_size: Target (width, height)
            padding_color: BGR color for padding
            
        Returns:
            Tuple of (resized_frame, mapping_info)
        """
        try:
            target_w, target_h = target_size
            frame_h, frame_w = frame.shape[:2]
            
            # Calculate scaling factor
            scale = min(target_w / frame_w, target_h / frame_h)
            
            # Calculate new dimensions
            new_w = int(frame_w * scale)
            new_h = int(frame_h * scale)
            
            # Resize frame
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Create target canvas with padding color
            canvas = np.full((target_h, target_w, 3), padding_color, dtype=np.uint8)
            
            # Calculate padding
            pad_x = (target_w - new_w) // 2
            pad_y = (target_h - new_h) // 2
            
            # Place resized frame on canvas
            canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
            
            # Create mapping information
            mapping_info = {
                'original_size': (frame_w, frame_h),
                'target_size': (target_w, target_h),
                'scale': scale,
                'new_size': (new_w, new_h),
                'padding': (pad_x, pad_y),
                'offset': (pad_x, pad_y)
            }
            
            return canvas, mapping_info
            
        except Exception as e:
            self.logger.error(f"Letterbox resizing failed: {e}")
            return cv2.resize(frame, target_size), {'error': str(e)}
    
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
    
    def map_coordinates_to_resized(self, bbox: List[float], mapping_info: Dict[str, Any]) -> List[float]:
        """
        Map coordinates from original frame to resized frame.
        
        Args:
            bbox: Bounding box in original frame [x1, y1, x2, y2]
            mapping_info: Mapping information from resize_with_letterbox
            
        Returns:
            List[float]: Bounding box in resized frame coordinates
        """
        try:
            if 'error' in mapping_info:
                return bbox
            
            scale = mapping_info['scale']
            offset_x, offset_y = mapping_info['offset']
            
            # Scale and add padding offset
            x1 = bbox[0] * scale + offset_x
            y1 = bbox[1] * scale + offset_y
            x2 = bbox[2] * scale + offset_x
            y2 = bbox[3] * scale + offset_y
            
            # Clamp to resized frame bounds
            target_w, target_h = mapping_info['target_size']
            x1 = max(0, min(x1, target_w))
            y1 = max(0, min(y1, target_h))
            x2 = max(0, min(x2, target_w))
            y2 = max(0, min(y2, target_h))
            
            return [x1, y1, x2, y2]
            
        except Exception as e:
            self.logger.warning(f"Coordinate mapping to resized failed: {e}")
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
            # Use letterbox resizing to preserve aspect ratio
            resized_frame, mapping_info = self.resize_with_letterbox(frame, model_input_size)
            
            # Add model-specific information
            mapping_info.update({
                'model_input_size': model_input_size,
                'resize_method': 'letterbox',
                'aspect_ratio_preserved': True
            })
            
            return resized_frame, mapping_info
            
        except Exception as e:
            self.logger.error(f"Model input resize failed: {e}")
            return cv2.resize(frame, model_input_size), {'error': str(e)}
    
    def process_detection_with_coordinate_mapping(self, frame: np.ndarray, 
                                                detections: List[Dict[str, Any]], 
                                                mapping_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process detections with coordinate mapping back to original frame.
        
        Args:
            frame: Original frame
            detections: Detections in resized frame coordinates
            mapping_info: Mapping information from resize
            
        Returns:
            List[Dict[str, Any]]: Detections with original frame coordinates
        """
        try:
            mapped_detections = []
            
            for detection in detections:
                # Map bounding box coordinates
                if 'bbox' in detection:
                    original_bbox = self.map_coordinates_to_original(detection['bbox'], mapping_info)
                    detection['bbox'] = original_bbox
                    detection['bbox_original'] = original_bbox
                    detection['bbox_resized'] = detection.get('bbox_resized', detection['bbox'])
                
                # Add mapping information
                detection['coordinate_mapping'] = {
                    'mapped': True,
                    'mapping_info': mapping_info,
                    'original_frame_size': mapping_info.get('original_size'),
                    'resized_frame_size': mapping_info.get('target_size')
                }
                
                mapped_detections.append(detection)
            
            return mapped_detections
            
        except Exception as e:
            self.logger.error(f"Coordinate mapping processing failed: {e}")
            return detections
    
    # Performance Optimization and Reliability Improvements
    
    def get_enhanced_status(self) -> Dict[str, Any]:
        """
        Get enhanced status including performance metrics and reliability information.
        
        Returns:
            Dict[str, Any]: Enhanced status information
        """
        try:
            # Get base status
            base_status = self.get_status()
            
            # Add enhanced metrics
            enhanced_status = base_status.copy()
            enhanced_status.update({
                'enhanced_pipeline': {
                    'motion_detection_enabled': self.motion_detection_enabled,
                    'tracking_enabled': self.tracking_enabled,
                    'best_frame_selection_enabled': self.best_frame_selection_enabled,
                    'resource_limited_mode': self.resource_limited_mode,
                    'max_processing_time': self.max_processing_time,
                    'adaptive_processing': self.adaptive_processing,
                    'quality_optimization': self.quality_optimization,
                    'storage_optimization': self.storage_optimization,
                    'image_quality': self.image_quality
                },
                'processing_metrics': {
                    'motion_detection_time': self.processing_metrics.motion_detection_time,
                    'preprocessing_time': self.processing_metrics.preprocessing_time,
                    'vehicle_detection_time': self.processing_metrics.vehicle_detection_time,
                    'tracking_time': self.processing_metrics.tracking_time,
                    'plate_detection_time': self.processing_metrics.plate_detection_time,
                    'ocr_time': self.processing_metrics.ocr_time,
                    'total_time': self.processing_metrics.total_time,
                    'frames_skipped': self.processing_metrics.frames_skipped,
                    'vehicles_tracked': self.processing_metrics.vehicles_tracked,
                    'plates_detected': self.processing_metrics.plates_detected,
                    'ocr_successful': self.processing_metrics.ocr_successful
                },
                'tracking_info': {
                    'active_tracks_count': len(self.active_tracks),
                    'next_track_id': self.next_track_id,
                    'track_timeout': self.track_timeout,
                    'reentry_time_threshold': self.reentry_time_threshold,
                    'iou_threshold': self.iou_threshold
                },
                'lighting_condition': self.lighting_condition.value,
                'pipeline_stage': self.pipeline_stage.value,
                'frame_score_weights': self.frame_score_weights,
                'performance_optimization': {
                    'motion_detection_threshold': self.motion_threshold,
                    'frame_buffer_size': self.frame_buffer_size,
                    'processing_lock_acquired': self._processing_lock.locked(),
                    'track_lock_acquired': self._track_lock.locked()
                }
            })
            
            return enhanced_status
            
        except Exception as e:
            self.logger.error(f"Enhanced status error: {e}")
            return base_status
    
    def optimize_for_performance(self, target_fps: float = 30.0) -> Dict[str, Any]:
        """
        Optimize detection processor for target performance.
        
        Args:
            target_fps: Target FPS for processing
            
        Returns:
            Dict[str, Any]: Optimization results
        """
        try:
            optimization_results = {
                'target_fps': target_fps,
                'optimizations_applied': [],
                'performance_impact': {}
            }
            
            # Calculate target processing time per frame
            target_processing_time = 1.0 / target_fps
            
            # Adjust motion detection threshold based on target FPS
            if target_fps < 15:
                # Lower FPS - can be more sensitive to motion
                self.motion_threshold = 0.05
                optimization_results['optimizations_applied'].append('motion_threshold_lowered')
            elif target_fps > 30:
                # Higher FPS - need to be less sensitive to motion
                self.motion_threshold = 0.15
                optimization_results['optimizations_applied'].append('motion_threshold_raised')
            
            # Adjust processing time limits
            if target_processing_time < 0.05:  # Very high FPS
                self.max_processing_time = target_processing_time * 0.8
                self.resource_limited_mode = True
                optimization_results['optimizations_applied'].append('processing_time_limited')
            
            # Adjust tracking parameters for performance
            if target_fps > 20:
                # High FPS - reduce tracking complexity
                self.track_timeout = 3.0  # Shorter timeout
                self.reentry_time_threshold = 5.0  # Shorter reentry threshold
                optimization_results['optimizations_applied'].append('tracking_parameters_optimized')
            
            # Adjust image quality for storage optimization
            if target_fps > 25:
                # High FPS - reduce storage quality to save space
                self.image_quality = 75
                optimization_results['optimizations_applied'].append('storage_quality_reduced')
            
            # Enable/disable features based on performance requirements
            if target_processing_time < 0.02:  # Very high FPS
                self.best_frame_selection_enabled = False
                optimization_results['optimizations_applied'].append('best_frame_selection_disabled')
            
            optimization_results['performance_impact'] = {
                'motion_threshold': self.motion_threshold,
                'max_processing_time': self.max_processing_time,
                'track_timeout': self.track_timeout,
                'reentry_time_threshold': self.reentry_time_threshold,
                'image_quality': self.image_quality,
                'best_frame_selection_enabled': self.best_frame_selection_enabled
            }
            
            self.logger.info(f"🔧 [PERFORMANCE] Optimized for {target_fps} FPS: {len(optimization_results['optimizations_applied'])} optimizations applied")
            
            return optimization_results
            
        except Exception as e:
            self.logger.error(f"Performance optimization error: {e}")
            return {'error': str(e)}
    
    def monitor_performance(self) -> Dict[str, Any]:
        """
        Monitor current performance and provide recommendations.
        
        Returns:
            Dict[str, Any]: Performance monitoring results
        """
        try:
            monitoring_results = {
                'timestamp': datetime.now().isoformat(),
                'current_metrics': {
                    'total_time': self.processing_metrics.total_time,
                    'frames_skipped': self.processing_metrics.frames_skipped,
                    'vehicles_tracked': self.processing_metrics.vehicles_tracked,
                    'plates_detected': self.processing_metrics.plates_detected,
                    'ocr_successful': self.processing_metrics.ocr_successful
                },
                'performance_analysis': {},
                'recommendations': []
            }
            
            # Analyze processing time
            if self.processing_metrics.total_time > self.max_processing_time:
                monitoring_results['performance_analysis']['processing_slow'] = True
                monitoring_results['recommendations'].append('Consider reducing motion detection threshold')
                monitoring_results['recommendations'].append('Consider disabling best frame selection')
            else:
                monitoring_results['performance_analysis']['processing_slow'] = False
            
            # Analyze frame skipping rate
            total_frames = self.processing_metrics.frames_skipped + self.processing_metrics.vehicles_tracked
            if total_frames > 0:
                skip_rate = self.processing_metrics.frames_skipped / total_frames
                monitoring_results['performance_analysis']['skip_rate'] = skip_rate
                
                if skip_rate > 0.8:
                    monitoring_results['recommendations'].append('High frame skip rate - consider adjusting motion threshold')
                elif skip_rate < 0.2:
                    monitoring_results['recommendations'].append('Low frame skip rate - may be processing too many frames')
            
            # Analyze detection success rate
            if self.processing_metrics.plates_detected > 0:
                ocr_success_rate = self.processing_metrics.ocr_successful / self.processing_metrics.plates_detected
                monitoring_results['performance_analysis']['ocr_success_rate'] = ocr_success_rate
                
                if ocr_success_rate < 0.5:
                    monitoring_results['recommendations'].append('Low OCR success rate - consider improving preprocessing')
            
            # Analyze tracking efficiency
            if self.processing_metrics.vehicles_tracked > 0:
                tracking_efficiency = self.processing_metrics.vehicles_tracked / max(1, len(self.active_tracks))
                monitoring_results['performance_analysis']['tracking_efficiency'] = tracking_efficiency
                
                if tracking_efficiency < 0.7:
                    monitoring_results['recommendations'].append('Low tracking efficiency - consider adjusting IoU threshold')
            
            return monitoring_results
            
        except Exception as e:
            self.logger.error(f"Performance monitoring error: {e}")
            return {'error': str(e)}
    
    def apply_reliability_improvements(self) -> Dict[str, Any]:
        """
        Apply reliability improvements to the detection processor.
        
        Returns:
            Dict[str, Any]: Reliability improvement results
        """
        try:
            improvements = {
                'timestamp': datetime.now().isoformat(),
                'improvements_applied': [],
                'reliability_metrics': {}
            }
            
            # Enable resource-limited mode for stability
            if not self.resource_limited_mode:
                self.resource_limited_mode = True
                improvements['improvements_applied'].append('resource_limited_mode_enabled')
            
            # Set conservative processing time limits
            if self.max_processing_time > 0.1:
                self.max_processing_time = 0.1
                improvements['improvements_applied'].append('processing_time_limited_conservative')
            
            # Enable adaptive processing for different conditions
            if not self.adaptive_processing:
                self.adaptive_processing = True
                improvements['improvements_applied'].append('adaptive_processing_enabled')
            
            # Enable quality optimization
            if not self.quality_optimization:
                self.quality_optimization = True
                improvements['improvements_applied'].append('quality_optimization_enabled')
            
            # Set conservative tracking parameters
            if self.track_timeout < 5.0:
                self.track_timeout = 5.0
                improvements['improvements_applied'].append('track_timeout_increased')
            
            if self.reentry_time_threshold < 10.0:
                self.reentry_time_threshold = 10.0
                improvements['improvements_applied'].append('reentry_threshold_increased')
            
            # Enable storage optimization
            if not self.storage_optimization:
                self.storage_optimization = True
                improvements['improvements_applied'].append('storage_optimization_enabled')
            
            # Set reliable image quality
            if self.image_quality < 80:
                self.image_quality = 85
                improvements['improvements_applied'].append('image_quality_optimized')
            
            improvements['reliability_metrics'] = {
                'resource_limited_mode': self.resource_limited_mode,
                'max_processing_time': self.max_processing_time,
                'adaptive_processing': self.adaptive_processing,
                'quality_optimization': self.quality_optimization,
                'track_timeout': self.track_timeout,
                'reentry_time_threshold': self.reentry_time_threshold,
                'storage_optimization': self.storage_optimization,
                'image_quality': self.image_quality
            }
            
            self.logger.info(f"🔧 [RELIABILITY] Applied {len(improvements['improvements_applied'])} reliability improvements")
            
            return improvements
            
        except Exception as e:
            self.logger.error(f"Reliability improvements error: {e}")
            return {'error': str(e)}
    
    def reset_performance_metrics(self):
        """Reset performance metrics for fresh monitoring."""
        try:
            self.processing_metrics = ProcessingMetrics()
            self.logger.info("🔧 [PERFORMANCE] Performance metrics reset")
        except Exception as e:
            self.logger.warning(f"Performance metrics reset error: {e}")
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics.
        
        Returns:
            Dict[str, Any]: Processing statistics
        """
        try:
            stats = {
                'timestamp': datetime.now().isoformat(),
                'processing_metrics': {
                    'motion_detection_time': self.processing_metrics.motion_detection_time,
                    'preprocessing_time': self.processing_metrics.preprocessing_time,
                    'vehicle_detection_time': self.processing_metrics.vehicle_detection_time,
                    'tracking_time': self.processing_metrics.tracking_time,
                    'plate_detection_time': self.processing_metrics.plate_detection_time,
                    'ocr_time': self.processing_metrics.ocr_time,
                    'total_time': self.processing_metrics.total_time,
                    'frames_skipped': self.processing_metrics.frames_skipped,
                    'vehicles_tracked': self.processing_metrics.vehicles_tracked,
                    'plates_detected': self.processing_metrics.plates_detected,
                    'ocr_successful': self.processing_metrics.ocr_successful
                },
                'tracking_statistics': {
                    'active_tracks': len(self.active_tracks),
                    'next_track_id': self.next_track_id,
                    'track_timeout': self.track_timeout,
                    'reentry_time_threshold': self.reentry_time_threshold,
                    'iou_threshold': self.iou_threshold
                },
                'system_status': {
                    'motion_detection_enabled': self.motion_detection_enabled,
                    'tracking_enabled': self.tracking_enabled,
                    'best_frame_selection_enabled': self.best_frame_selection_enabled,
                    'resource_limited_mode': self.resource_limited_mode,
                    'adaptive_processing': self.adaptive_processing,
                    'quality_optimization': self.quality_optimization,
                    'storage_optimization': self.storage_optimization
                },
                'lighting_condition': self.lighting_condition.value,
                'pipeline_stage': self.pipeline_stage.value
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Processing statistics error: {e}")
            return {'error': str(e)}