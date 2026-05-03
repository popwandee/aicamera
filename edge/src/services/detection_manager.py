#!/usr/bin/env python3
"""
Detection Manager Service for AI Camera v1.3

This service manages the complete detection workflow:
- Coordinates with camera service to receive image frames
- Orchestrates the detection pipeline using DetectionProcessor
- Manages detection timing and intervals
- Handles database storage of detection results
- Provides detection status and management APIs

Author: AI Camera Team
Version: 1.3  
Date: August 2025
"""

import threading
import time
import queue
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import numpy as np

from edge.src.core.utils.logging_config import get_logger
from edge.src.core.config import DETECTION_INTERVAL, AUTO_START_DETECTION, STARTUP_DELAY, IMAGE_SAVE_DIR, TRACKING_ENABLED, REENTRY_TIME_THRESHOLD, IOU_THRESHOLD
from edge.src.core.dependency_container import get_service

logger = get_logger(__name__)


class DetectionManager:
    """
    Detection Manager Service for orchestrating AI detection workflow.
    
    This service provides:
    - Detection pipeline management
    - Integration with camera service
    - Detection timing and scheduling
    - Database integration for results
    - Status monitoring and reporting
    
    Workflow:
    1. Receive images from camera service
    2. Image frame validation and enhancing for vehicle detection model
    3. Vehicle detection - if not found, skip and continue next loop
    4. If found vehicle object, perform license plate detection
    5. Crop license plate then perform OCR
    6. Save original image with license plate detection result bounding box drawing
    7. Insert information from OCR and MODEL detection results into SQLite
    """
    
    def __init__(self, detection_processor=None, database_manager=None, logger=None):
        """
        Initialize Detection Manager.
        
        Args:
            detection_processor: DetectionProcessor component instance
            database_manager: DatabaseManager component instance
            logger: Logger instance
        """
        self.detection_processor = detection_processor
        self.database_manager = database_manager
        self.logger = logger or get_logger(__name__)
        
        # Detection state
        self.is_running = False
        self.detection_thread = None
        self.detection_queue = queue.Queue(maxsize=10)
        
        # Statistics tracking
        self.detection_stats = {
            'started_at': None,
            'total_frames_processed': 0,
            'total_vehicles_detected': 0,
            'total_plates_detected': 0,
            'successful_ocr': 0,
            'failed_detections': 0,
            'last_detection': None,
            'processing_time_avg': 0.0
        }
        
        # Configuration
        self.detection_interval = DETECTION_INTERVAL
        self.auto_start_enabled = AUTO_START_DETECTION  # Auto-start detection from config
        
        # Tracking configuration
        self.tracking_enabled = TRACKING_ENABLED
        self.reentry_time_threshold = REENTRY_TIME_THRESHOLD
        self.iou_threshold = IOU_THRESHOLD
        
        # Track storage for deduplication
        self.recent_tracks = {}  # track_id -> {'last_saved': timestamp, 'bbox': bbox, 'plate_text': text}
        self.track_cleanup_interval = 300.0  # Clean up old tracks every 5 minutes
        self.last_track_cleanup = time.time()
        
        self.logger.info(f"DetectionManager initialized (tracking: {self.tracking_enabled})")
    
    def initialize(self) -> bool:
        """
        Initialize the detection manager and load models.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        self.logger.debug(f"🔧 [DETECTION_MANAGER] initialize called")
        
        try:
            self.logger.info("🔧 [DETECTION_MANAGER] Initializing Detection Manager...")
            
            # Initialize detection processor models
            if self.detection_processor:
                self.logger.debug(f"🔧 [DETECTION_MANAGER] initialize: calling detection_processor.load_models()")
                success = self.detection_processor.load_models()
                self.logger.debug(f"🔧 [DETECTION_MANAGER] initialize: detection_processor.load_models() returned: {success}")
                
                if success:
                    self.logger.info("🔧 [DETECTION_MANAGER] Detection models loaded successfully")
                    
                    # Initialize database if available
                    if self.database_manager:
                        self.logger.debug(f"🔧 [DETECTION_MANAGER] initialize: calling database_manager.initialize()")
                        db_success = self.database_manager.initialize()
                        self.logger.debug(f"🔧 [DETECTION_MANAGER] initialize: database_manager.initialize() returned: {db_success}")
                        
                        if db_success:
                            self.logger.info("🔧 [DETECTION_MANAGER] Database initialized successfully")
                        else:
                            self.logger.warning("🔧 [DETECTION_MANAGER] Database initialization failed")
                    else:
                        self.logger.debug(f"🔧 [DETECTION_MANAGER] initialize: no database_manager available")
                    
                    # Auto-start detection if enabled
                    if self.auto_start_enabled:
                        self.logger.info("🔧 [DETECTION_MANAGER] 🤖 Auto-start detection enabled - starting detection automatically")
                        return self._auto_start_detection()
                    else:
                        self.logger.info("🔧 [DETECTION_MANAGER] Auto-start detection disabled - ready for manual start")
                        return True
                else:
                    self.logger.error("🔧 [DETECTION_MANAGER] Failed to load detection models")
                    return False
            else:
                self.logger.error("🔧 [DETECTION_MANAGER] Detection processor not available")
                return False
                
        except Exception as e:
            self.logger.error(f"🔧 [DETECTION_MANAGER] Error initializing detection manager: {e}")
            return False
    
    def _auto_start_detection(self) -> bool:
        """
        Auto-start detection functionality.
        
        Returns:
            bool: True if auto-start successful, False otherwise
        """
        try:
            self.logger.info("🚀 Starting detection auto-start sequence...")
            
            # Wait for startup delay to ensure camera is fully ready
            self.logger.info(f"⏱️  Waiting {STARTUP_DELAY} seconds for camera to be ready...")
            time.sleep(STARTUP_DELAY)
            
            # Verify camera is streaming before starting detection
            camera_manager = get_service('camera_manager')
            if camera_manager:
                camera_status = camera_manager.get_status()
                if camera_status.get('streaming', False):
                    self.logger.info("✅ Camera confirmed streaming - starting detection")
                    
                    # Start detection using existing method
                    if self.start_detection():
                        self.logger.info("✅ Detection auto-started successfully")
                        return True
                    else:
                        self.logger.error("❌ Failed to auto-start detection")
                        return False
                else:
                    self.logger.warning("⚠️  Camera not streaming - detection auto-start delayed")
                    # Could implement retry logic here if needed
                    return False
            else:
                self.logger.error("❌ Camera manager not available")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error during detection auto-start: {e}")
            return False
    
    def _is_camera_ready(self, camera_manager) -> bool:
        """
        Check if camera is ready for detection.
        
        Args:
            camera_manager: CameraManager instance
            
        Returns:
            bool: True if camera is ready, False otherwise
        """
        try:
            status = camera_manager.get_status()
            return status.get('initialized', False) and status.get('streaming', False)
        except Exception as e:
            self.logger.debug(f"Error checking camera status: {e}")
            return False
    
    def start_detection(self) -> bool:
        """
        Start the detection service.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.is_running:
            self.logger.debug("Detection service already running")
            return True
        
        try:
            self.logger.info("Starting detection service...")
            
            # Check if detection processor is ready
            if not self.detection_processor or not self.detection_processor.models_loaded:
                self.logger.error("Detection processor not ready - models not loaded")
                return False
            
            # Start detection thread
            self.is_running = True
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                name="DetectionThread",
                daemon=True
            )
            self.detection_thread.start()
            
            # Update statistics
            self.detection_stats['started_at'] = datetime.now().isoformat()
            
            self.logger.info("Detection service started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting detection service: {e}")
            self.is_running = False
            return False
    
    def stop_detection(self) -> bool:
        """
        Stop the detection service.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.is_running:
            self.logger.warning("Detection service not running")
            return True
        
        try:
            self.logger.info("Stopping detection service...")
            
            # Signal thread to stop
            self.is_running = False
            
            # Wait for thread to finish
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=5.0)
                
                if self.detection_thread.is_alive():
                    self.logger.warning("Detection thread did not stop gracefully")
                else:
                    self.logger.info("Detection thread stopped successfully")
            
            self.detection_thread = None
            
            self.logger.info("Detection service stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping detection service: {e}")
            return False
    
    def process_frame_from_camera(self, camera_manager) -> Optional[Dict[str, Any]]:
        """
        Process a single frame from the camera manager.
        
        Args:
            camera_manager: CameraManager service instance
            
        Returns:
            Optional[Dict[str, Any]]: Detection results or None if processing failed
        """
        self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame_from_camera called with camera_manager: {camera_manager is not None}")
        
        try:
            if not camera_manager:
                self.logger.warning(f"🔧 [DETECTION_MANAGER] process_frame_from_camera failed: camera manager not available")
                return None
            
            # Capture main frame from camera for detection processing
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame_from_camera: calling camera_manager.camera_handler.capture_frame(source='buffer', stream_type='main', include_metadata=False)")
            frame = camera_manager.camera_handler.capture_frame(source="buffer", stream_type="main", include_metadata=False)
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame_from_camera: camera_handler.capture_frame() returned frame type: {type(frame)}")
            
            if frame is None:
                self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame_from_camera: no frame available from camera")
                return None
            
            # Camera manager returns numpy array directly, not dict
            if isinstance(frame, np.ndarray):
                self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame_from_camera: frame is numpy array with shape: {frame.shape}, calling process_frame()")
                result = self.process_frame(frame)
                self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame_from_camera: process_frame() returned: {result is not None}")
                return result
            else:
                self.logger.error(f"🔧 [DETECTION_MANAGER] process_frame_from_camera failed: invalid frame data format: expected numpy array, got {type(frame)}")
                return None
            
        except Exception as e:
            self.logger.error(f"🔧 [DETECTION_MANAGER] process_frame_from_camera error: {e}")
            self.detection_stats['failed_detections'] += 1
            return None
    
    def process_frame(self, frame) -> Optional[Dict[str, Any]]:
        """
        Process a single frame through the complete detection pipeline with tracking and deduplication.
        
        Args:
            frame: Image frame as numpy array
            
        Returns:
            Optional[Dict[str, Any]]: Detection results or None if processing failed
        """
        self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame called with frame shape: {frame.shape if frame is not None else 'None'}")
        
        start_time = time.time()
        
        try:
            self.detection_stats['total_frames_processed'] += 1
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: total frames processed: {self.detection_stats['total_frames_processed']}")
            
            # Step 1: Validate and enhance frame
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 1 - calling detection_processor.validate_and_enhance_frame()")
            enhanced_frame = self.detection_processor.validate_and_enhance_frame(frame)
            if enhanced_frame is None:
                self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 1 failed - frame validation failed")
                return None
            
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 1 completed - enhanced frame shape: {enhanced_frame.shape}")
            
            # Step 2: Vehicle detection — pass enhanced_frame (BGR) so detect_vehicles COLOR_BGR2RGB is correct
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 2 - calling detection_processor.detect_vehicles()")
            vehicle_boxes, mapping_info = self.detection_processor.detect_vehicles(enhanced_frame)  # BGR: validate_and_enhance_frame converts RGB→BGR
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 2 completed - vehicles detected: {len(vehicle_boxes)}")
            
            if not vehicle_boxes:
                self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: no vehicles detected - skipping to next frame")
                return None
            
            self.detection_stats['total_vehicles_detected'] += len(vehicle_boxes)
            
            # Step 2.5: Vehicle tracking and deduplication (if enabled)
            tracks_to_save = []
            if self.tracking_enabled and hasattr(self.detection_processor, 'update_vehicle_tracks'):
                self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 2.5 - updating vehicle tracks")
                try:
                    # Convert vehicle_boxes to detection format for tracking
                    vehicle_detections = [{'bbox': vb['bbox'], 'score': vb.get('score', 0.0)} for vb in vehicle_boxes]
                    
                    # Update tracks
                    tracks = self.detection_processor.update_vehicle_tracks(vehicle_detections, frame)
                    
                    # Apply deduplication rules
                    filtered_tracks = self.detection_processor.apply_deduplication_rules(tracks)
                    
                    # Check which tracks should be saved (not duplicates)
                    for track in filtered_tracks:
                        if self._should_save_detection(track):
                            tracks_to_save.append(track)
                            # Mark track as saved
                            self._mark_track_saved(track)
                    
                    self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 2.5 completed - {len(tracks_to_save)} tracks to save after deduplication")
                    
                    # If no tracks to save, skip processing
                    if not tracks_to_save:
                        self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: all vehicles are duplicates - skipping save")
                        return None
                    
                except Exception as e:
                    self.logger.warning(f"🔧 [DETECTION_MANAGER] Tracking error, falling back to non-tracking mode: {e}")
                    tracks_to_save = None  # Fall back to non-tracking mode
            
            # Step 3: License plate detection — pass enhanced_frame (BGR) for correct internal color ops
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 3 - calling detection_processor.detect_license_plates()")
            plate_boxes = self.detection_processor.detect_license_plates(enhanced_frame, vehicle_boxes, mapping_info)
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 3 completed - plates detected: {len(plate_boxes)}")
            
            if not plate_boxes:
                self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: no license plates detected")
                # Still save vehicle detection results
            else:
                self.detection_stats['total_plates_detected'] += len(plate_boxes)
            
            # Step 4: OCR on detected plates
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 4 - calling detection_processor.perform_ocr()")
            ocr_results = []
            if plate_boxes:
                ocr_results = self.detection_processor.perform_ocr(enhanced_frame, plate_boxes)  # BGR: internal OCR preprocessing uses COLOR_BGR2GRAY / COLOR_BGR2LAB
                self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 4 completed - OCR results: {len(ocr_results)}")
                if ocr_results:
                    self.detection_stats['successful_ocr'] += len(ocr_results)
            
            # Step 5: Determine which frame to save (best frame from track if available)
            frame_to_save = frame
            if self.tracking_enabled and tracks_to_save:
                # Use best frame from the first track (or combine best frames from multiple tracks)
                # For simplicity, use best frame from the track with highest score
                best_track = max(tracks_to_save, key=lambda t: t.best_frame_score)
                if best_track.best_frame_data is not None:
                    frame_to_save = best_track.best_frame_data
                    self.logger.debug(f"🔧 [DETECTION_MANAGER] Using best frame from track {best_track.track_id} (score: {best_track.best_frame_score:.3f})")
            
            # Step 6: Save only original image (optimized for disk space)
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 6 - calling detection_processor.save_detection_results()")
            original_path, _, _, _ = self.detection_processor.save_detection_results(
                frame_to_save, vehicle_boxes, plate_boxes, ocr_results
            )
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 6 completed - original_path: {original_path}")
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: processing time: {processing_time:.3f}s")
            
            # Step 6: Store results in database (only original image path)
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: Step 6 - creating detection record")
            detection_record = {
                'timestamp': datetime.now().isoformat(),
                'vehicles_count': len(vehicle_boxes),
                'plates_count': len(plate_boxes),
                'ocr_results': ocr_results,
                'original_image_path': f"captured_images/{os.path.basename(original_path)}" if original_path else '',
                'vehicle_detections': vehicle_boxes,
                'plate_detections': plate_boxes,
                'processing_time_ms': processing_time * 1000.0,  # Convert to milliseconds
                'coordinate_mapping': mapping_info  # เก็บ mapping_info สำหรับ frontend
            }
            
            # Extract parallel OCR data from OCR results
            if ocr_results:
                # Collect all Hailo and EasyOCR results
                hailo_ocr_results = []
                easyocr_results = []
                best_ocr_method = 'none'
                parallel_ocr_success = False
                ocr_processing_time_ms = 0.0
                hailo_ocr_confidence = 0.0
                easyocr_confidence = 0.0
                hailo_processing_time_ms = 0.0
                easyocr_processing_time_ms = 0.0
                hailo_ocr_error = ''
                easyocr_error = ''
                
                for ocr_result in ocr_results:
                    # Extract Hailo OCR data
                    hailo_ocr = ocr_result.get('hailo_ocr', {})
                    if hailo_ocr.get('success'):
                        hailo_ocr_results.append({
                            'text': hailo_ocr.get('text', ''),
                            'confidence': hailo_ocr.get('confidence', 0.0),
                            'success': True
                        })
                        hailo_ocr_confidence = max(hailo_ocr_confidence, hailo_ocr.get('confidence', 0.0))
                    else:
                        hailo_ocr_error = hailo_ocr.get('error', '')
                    
                    # Extract EasyOCR data
                    easyocr = ocr_result.get('easyocr', {})
                    if easyocr.get('success'):
                        easyocr_results.append({
                            'text': easyocr.get('text', ''),
                            'confidence': easyocr.get('confidence', 0.0),
                            'success': True
                        })
                        easyocr_confidence = max(easyocr_confidence, easyocr.get('confidence', 0.0))
                    else:
                        easyocr_error = easyocr.get('error', '')
                    
                    # Get best method and processing time from parallel processing metadata
                    parallel_metadata = ocr_result.get('parallel_processing', {})
                    if parallel_metadata:
                        parallel_ocr_success = parallel_metadata.get('parallel_success', False)
                        ocr_processing_time_ms = parallel_metadata.get('processing_time', 0.0) * 1000.0
                        hailo_processing_time_ms = parallel_metadata.get('hailo_time', 0.0) * 1000.0
                        easyocr_processing_time_ms = parallel_metadata.get('easyocr_time', 0.0) * 1000.0
                        best_ocr_method = parallel_metadata.get('selection_reason', 'none')
                    else:
                        # Fallback to OCR method from result
                        best_ocr_method = ocr_result.get('ocr_method', 'none')
                
                # Add parallel OCR data to detection record
                detection_record.update({
                    'hailo_ocr_results': hailo_ocr_results,
                    'easyocr_results': easyocr_results,
                    'best_ocr_method': best_ocr_method,
                    'ocr_processing_time_ms': ocr_processing_time_ms,
                    'parallel_ocr_success': parallel_ocr_success,
                    'hailo_ocr_confidence': hailo_ocr_confidence,
                    'easyocr_confidence': easyocr_confidence,
                    'hailo_processing_time_ms': hailo_processing_time_ms,
                    'easyocr_processing_time_ms': easyocr_processing_time_ms,
                    'hailo_ocr_error': hailo_ocr_error,
                    'easyocr_error': easyocr_error
                })
            
            # Always insert into DB; image save failure only means no image path
            if not original_path:
                self.logger.warning("Image save failed — inserting detection record without image path")
            elif not os.path.exists(original_path):
                self.logger.warning(f"Image path missing on disk after save: {original_path} — inserting record without image")
                detection_record['original_image_path'] = ''
            if self.database_manager:
                self.database_manager.insert_detection_result(detection_record)
            
            # Update statistics
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: updating processing statistics")
            self._update_processing_stats(processing_time)
            self.detection_stats['last_detection'] = datetime.now().isoformat()
            
            self.logger.info(
                f"🔧 [DETECTION_MANAGER] process_frame: Detection completed: {len(vehicle_boxes)} vehicles, "
                f"{len(plate_boxes)} plates, {len(ocr_results)} OCR results in {processing_time:.3f}s"
            )
            
            self.logger.debug(f"🔧 [DETECTION_MANAGER] process_frame: returning detection record with {len(vehicle_boxes)} vehicles, {len(plate_boxes)} plates, {len(ocr_results)} OCR results")
            return detection_record
            
        except Exception as e:
            self.logger.error(f"🔧 [DETECTION_MANAGER] process_frame error: {e}")
            self.detection_stats['failed_detections'] += 1
            return None
    
    def _detection_loop(self):
        """
        Main detection loop running in separate thread.
        
        This loop continuously processes frames from the camera when detection is active.
        """
        self.logger.info("Detection loop started")
        
        # Get camera manager from dependency container    
        while self.is_running:
            try:
                # Get camera manager
                camera_manager = get_service('camera_manager')
                if camera_manager and self._is_camera_ready(camera_manager):
                    # Process frame from camera
                    result = self.process_frame_from_camera(camera_manager)
                    
                    if result:
                        self.logger.debug("Frame processed successfully")
                    else:
                        self.logger.debug("Frame processing returned no results")
                else:
                    self.logger.debug("Camera not active, waiting...")
                
                # Wait for next detection interval
                time.sleep(self.detection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in detection loop: {e}")
                time.sleep(1.0)  # Wait before retry
        
        self.logger.info("Detection loop stopped")
    
    def _should_save_detection(self, track) -> bool:
        """
        Check if a track should be saved (not a duplicate).
        
        Args:
            track: VehicleTrack object
            
        Returns:
            bool: True if should save, False if duplicate
        """
        if not self.tracking_enabled:
            return True
        
        try:
            current_time = time.time()
            
            # Clean up old tracks periodically
            if current_time - self.last_track_cleanup > self.track_cleanup_interval:
                self._cleanup_old_tracks(current_time)
                self.last_track_cleanup = current_time
            
            # Check if this track was recently saved
            track_id = track.track_id
            if track_id in self.recent_tracks:
                track_info = self.recent_tracks[track_id]
                time_since_saved = current_time - track_info['last_saved']
                
                # Check time threshold
                if time_since_saved < self.reentry_time_threshold:
                    # Check IoU similarity
                    if hasattr(self.detection_processor, '_calculate_iou'):
                        iou = self.detection_processor._calculate_iou(track.bbox, track_info['bbox'])
                        if iou > self.iou_threshold:
                            self.logger.debug(f"🔧 [DEDUPLICATION] Track {track_id} is duplicate (IoU: {iou:.3f}, time: {time_since_saved:.1f}s)")
                            return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error checking if should save detection: {e}")
            return True  # Default to saving if check fails
    
    def _mark_track_saved(self, track):
        """
        Mark a track as saved to prevent duplicate saves.
        
        Args:
            track: VehicleTrack object
        """
        try:
            track_id = track.track_id
            self.recent_tracks[track_id] = {
                'last_saved': time.time(),
                'bbox': track.bbox.copy() if isinstance(track.bbox, list) else track.bbox,
                'plate_text': ''  # Will be updated if OCR results available
            }
        except Exception as e:
            self.logger.warning(f"Error marking track as saved: {e}")
    
    def _cleanup_old_tracks(self, current_time: float):
        """Clean up old tracks from recent_tracks dictionary."""
        try:
            tracks_to_remove = []
            for track_id, track_info in self.recent_tracks.items():
                time_since_saved = current_time - track_info['last_saved']
                # Remove tracks older than reentry threshold * 2
                if time_since_saved > (self.reentry_time_threshold * 2):
                    tracks_to_remove.append(track_id)
            
            for track_id in tracks_to_remove:
                del self.recent_tracks[track_id]
            
            if tracks_to_remove:
                self.logger.debug(f"🔧 [DEDUPLICATION] Cleaned up {len(tracks_to_remove)} old tracks")
        except Exception as e:
            self.logger.warning(f"Error cleaning up old tracks: {e}")
    
    def _update_processing_stats(self, processing_time: float):
        """Update processing time statistics."""
        if self.detection_stats['processing_time_avg'] == 0.0:
            self.detection_stats['processing_time_avg'] = processing_time
        else:
            # Simple moving average
            alpha = 0.1
            self.detection_stats['processing_time_avg'] = (
                alpha * processing_time + 
                (1 - alpha) * self.detection_stats['processing_time_avg']
            )
    
    def _calculate_quality_metrics(self) -> Dict[str, float]:
        """
        Calculate quality metrics from detection statistics.
        
        Returns:
            Dict[str, float]: Quality metrics for frontend progress bars
        """
        stats = self.detection_stats
        
        # Detection Accuracy: Based on successful vehicle detections vs total frames
        total_frames = stats['total_frames_processed']
        if total_frames > 0:
            detection_accuracy = (stats['total_vehicles_detected'] / total_frames) * 100
        else:
            detection_accuracy = 0.0
        
        # OCR Accuracy: Based on successful OCR vs total plates detected
        total_plates = stats['total_plates_detected']
        if total_plates > 0:
            ocr_accuracy = (stats['successful_ocr'] / total_plates) * 100
        else:
            ocr_accuracy = 0.0
        
        # System Reliability: Based on service uptime and error rate
        if total_frames > 0:
            error_rate = (stats['failed_detections'] / total_frames) * 100
            system_reliability = max(0, 100 - error_rate)  # Higher is better
        else:
            system_reliability = 100.0  # No errors if no frames processed
        
        return {
            'detection_accuracy': round(detection_accuracy, 1),
            'ocr_accuracy': round(ocr_accuracy, 1),
            'system_reliability': round(system_reliability, 1)
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the detection manager.
        
        Returns:
            Dict[str, Any]: Status information including statistics
        """
        self.logger.debug(f"🔧 [DETECTION_MANAGER] get_status called")
        
        processor_status = {}
        if self.detection_processor:
            self.logger.debug(f"🔧 [DETECTION_MANAGER] get_status: calling detection_processor.get_status()")
            processor_status = self.detection_processor.get_status()
            self.logger.debug(f"🔧 [DETECTION_MANAGER] get_status: detection_processor.get_status() returned: {processor_status}")
        
        # Augment processor status with model names for UI mapping
        if self.detection_processor:
            try:
                self.logger.debug(f"🔧 [DETECTION_MANAGER] get_status: calling detection_processor.get_ocr_status()")
                ocr_status = self.detection_processor.get_ocr_status()
                processor_status.update({
                    'vehicle_model_name': ocr_status.get('vehicle_model_name'),
                    'lp_detection_model_name': ocr_status.get('lp_detection_model_name'),
                    'lp_ocr_model_name': ocr_status.get('lp_ocr_model_name'),
                    'easyocr_available': ocr_status.get('easyocr_available', False)
                })
                self.logger.debug(f"🔧 [DETECTION_MANAGER] get_status: OCR status updated")
            except Exception as e:
                self.logger.debug(f"🔧 [DETECTION_MANAGER] get_status: error getting OCR status: {e}")

        # Calculate quality metrics from available statistics
        self.logger.debug(f"🔧 [DETECTION_MANAGER] get_status: calculating quality metrics")
        quality_metrics = self._calculate_quality_metrics()
        
        status = {
            'service_running': self.is_running,
            'detection_processor_status': processor_status,
            'detection_interval': self.detection_interval,
            'auto_start': self.auto_start_enabled,
            'statistics': self.detection_stats.copy(),
            'queue_size': self.detection_queue.qsize() if self.detection_queue else 0,
            'thread_alive': self.detection_thread.is_alive() if self.detection_thread else False,
            'last_update': datetime.now().isoformat(),
            # Add quality metrics for frontend progress bars
            'detection_accuracy': quality_metrics['detection_accuracy'],
            'ocr_accuracy': quality_metrics['ocr_accuracy'],
            'system_reliability': quality_metrics['system_reliability']
        }
        
        self.logger.debug(f"🔧 [DETECTION_MANAGER] get_status: returning status: {status}")
        return status
    
    def cleanup(self):
        """Clean up resources and stop detection service."""
        try:
            self.logger.info("Cleaning up DetectionManager...")
            
            # Stop detection service
            self.stop_detection()
            
            # Clean up detection processor
            if self.detection_processor:
                self.detection_processor.cleanup()
            
            self.logger.info("DetectionManager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during DetectionManager cleanup: {e}")


def create_detection_manager(detection_processor=None, database_manager=None, logger=None) -> DetectionManager:
    """
    Factory function to create DetectionManager with dependencies.
    
    Args:
        detection_processor: DetectionProcessor component instance
        database_manager: DatabaseManager component instance  
        logger: Logger instance
        
    Returns:
        DetectionManager: Configured DetectionManager instance
    """
    manager = DetectionManager(
        detection_processor=detection_processor,
        database_manager=database_manager,
        logger=logger
    )
    
    # Initialize the manager
    if manager.initialize():
        logger.info("DetectionManager created and initialized successfully") if logger else None
        return manager
    else:
        logger.error("Failed to initialize DetectionManager") if logger else None
        return manager  # Return anyway, but not initialized
