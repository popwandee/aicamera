#!/usr/bin/env python3
"""
Parallel OCR Processor for AI Camera v1.4

This module provides parallel execution of both Hailo OCR and PaddleOCR (Thai)
for better Thai alphabet recognition. Both OCR engines run simultaneously
to maximize accuracy and coverage for license plate recognition.

Features:
- Parallel execution of Hailo OCR and ThaiLPROCR (PaddleOCR)
- Thread-safe OCR processing
- Confidence scoring and result comparison
- Fallback handling when one OCR fails
- Performance monitoring and statistics

Author: AI Camera Team
Version: 1.4
Date: April 2026
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Dict, List, Optional, Tuple, Any
import logging


class ParallelOCRProcessor:
    """
    Parallel OCR Processor for simultaneous Hailo and EasyOCR execution.
    
    This processor runs both OCR engines in parallel to maximize accuracy
    for Thai license plate recognition. Results from both engines are
    compared and the best result is selected based on confidence scores.
    """
    
    def __init__(self, hailo_ocr_model, thai_lp_ocr, logger=None):
        """
        Initialize the parallel OCR processor.

        Args:
            hailo_ocr_model: Hailo OCR model for license plate recognition
            thai_lp_ocr: ThaiLPROCR instance (PaddleOCR) for Thai alphabet recognition
            logger: Logger instance for debugging
        """
        self.hailo_ocr_model = hailo_ocr_model
        self.thai_lp_ocr = thai_lp_ocr
        self.logger = logger or logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ParallelOCR")
        
        self.logger.info("✅ Parallel OCR Processor initialized")
    
    def process_plate_parallel(self, plate_image, plate_idx: int, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Process a license plate image using both Hailo and EasyOCR in parallel.
        
        Args:
            plate_image: License plate image to process
            plate_idx: Index of the plate for logging
            timeout: Maximum time to wait for both OCR engines
            
        Returns:
            Dict containing results from both engines and the best result
        """
        start_time = time.time()
        
        try:
            # Submit both OCR tasks to thread pool
            hailo_future = self.executor.submit(self._hailo_ocr_worker, plate_image, plate_idx)
            thai_future = self.executor.submit(self._thai_ocr_worker, plate_image, plate_idx)

            # Wait for both results with timeout
            hailo_result = None
            thai_result = None

            try:
                hailo_result = hailo_future.result(timeout=timeout)
            except FutureTimeoutError:
                self.logger.warning(f"Hailo OCR timed out for plate {plate_idx}")
            except Exception as e:
                self.logger.warning(f"Hailo OCR failed for plate {plate_idx}: {e}")

            try:
                thai_result = thai_future.result(timeout=timeout)
            except FutureTimeoutError:
                self.logger.warning(f"Thai OCR timed out for plate {plate_idx}")
            except Exception as e:
                self.logger.warning(f"Thai OCR failed for plate {plate_idx}: {e}")

            # Determine best result
            best_result = self._select_best_result(hailo_result, thai_result, plate_idx)

            processing_time = time.time() - start_time

            return {
                'parallel_success': best_result['success'],
                'processing_time': processing_time,
                'best_result': best_result,
                'hailo': hailo_result or {'success': False, 'error': 'No result'},
                'easyocr': thai_result or {'success': False, 'error': 'No result'},
                'plate_idx': plate_idx
            }

        except Exception as e:
            self.logger.error(f"Parallel OCR processing failed for plate {plate_idx}: {e}")
            return {
                'parallel_success': False,
                'processing_time': time.time() - start_time,
                'best_result': {'success': False, 'error': str(e)},
                'hailo': {'success': False, 'error': str(e)},
                'easyocr': {'success': False, 'error': str(e)},
                'plate_idx': plate_idx
            }
    
    def _hailo_ocr_worker(self, plate_image, plate_idx: int) -> Dict[str, Any]:
        """Worker function for Hailo OCR processing."""
        start_time = time.time()

        try:
            if not self.hailo_ocr_model:
                return {'success': False, 'error': 'Hailo OCR model not available'}

            # Perform Hailo OCR — returns DeGirum DetectionResults
            hailo_result_obj = self.hailo_ocr_model(plate_image)

            # DeGirum OCR model detects individual characters; access via .results list
            char_list = getattr(hailo_result_obj, 'results', [])
            if not char_list:
                return {'success': False, 'error': 'No Hailo OCR results'}

            # Filter by minimum confidence, then sort left-to-right by x1
            min_conf = 0.25
            valid = [r for r in char_list if r.get('score', 0) >= min_conf]
            if not valid:
                return {'success': False, 'error': 'All characters below confidence threshold'}

            valid.sort(key=lambda r: r.get('bbox', [0])[0])
            plate_text = ''.join(r.get('label', '') for r in valid)
            avg_conf = sum(r.get('score', 0) for r in valid) / len(valid)

            processing_time = time.time() - start_time
            self.logger.debug(f"Hailo OCR plate {plate_idx}: '{plate_text}' (conf={avg_conf:.3f}, chars={len(valid)})")

            return {
                'success': True,
                'text': plate_text,
                'confidence': float(avg_conf),
                'processing_time': processing_time,
                'method': 'hailo'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    def _thai_ocr_worker(self, plate_image, plate_idx: int) -> Dict[str, Any]:
        """Worker function for Thai PaddleOCR processing."""
        start_time = time.time()

        try:
            if not self.thai_lp_ocr or not self.thai_lp_ocr.is_ready():
                return {'success': False, 'error': 'ThaiLPROCR not ready'}

            # Preprocess specifically for PaddleOCR (resize, deskew, CLAHE)
            from edge.src.components.thai_lp_ocr import preprocess_plate_crop
            preprocessed = preprocess_plate_crop(plate_image.copy())

            result = self.thai_lp_ocr.read_plate(preprocessed)

            processing_time = time.time() - start_time

            if result.get('success'):
                self.logger.debug(
                    f"Thai OCR plate {plate_idx}: '{result['text']}' "
                    f"(conf={result['confidence']:.3f})"
                )
                return {
                    'success': True,
                    'text': result['text'],
                    'confidence': result['confidence'],
                    'processing_time': processing_time,
                    'method': 'paddleocr',
                    'validation': result.get('validation', {}),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'No text detected'),
                    'processing_time': processing_time,
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time,
            }
    
    def _select_best_result(self, hailo_result: Optional[Dict], easyocr_result: Optional[Dict], plate_idx: int) -> Dict[str, Any]:
        """
        Select the best OCR result from Hailo and EasyOCR.
        
        Selection criteria:
        1. Higher confidence score
        2. Text quality (length, character patterns)
        3. Method preference (Hailo for speed, EasyOCR for Thai)
        """
        if not hailo_result and not easyocr_result:
            return {'success': False, 'error': 'No OCR results available'}
        
        if not hailo_result:
            return easyocr_result
        
        if not easyocr_result:
            return hailo_result
        
        # Both results available - compare
        hailo_success = hailo_result.get('success', False)
        easyocr_success = easyocr_result.get('success', False)
        
        if not hailo_success and not easyocr_success:
            return {'success': False, 'error': 'Both OCR methods failed'}
        
        if not hailo_success:
            return easyocr_result
        
        if not easyocr_success:
            return hailo_result
        
        # Both successful - compare confidence
        hailo_conf = hailo_result.get('confidence', 0.0)
        thai_conf = easyocr_result.get('confidence', 0.0)

        # Prefer Thai OCR ONLY when it passed validate_thai_plate (structural check).
        # Raw PSM-11 output can contain Thai chars but still be garbage — validation
        # confirms the letters+digits format is present.
        thai_validated = easyocr_result.get('validation', {}).get('valid', False)
        confidence_threshold = 0.1

        if thai_validated and (thai_conf - hailo_conf) > -confidence_threshold:
            self.logger.debug(
                f"Plate {plate_idx}: Selected Thai OCR (valid plate format, "
                f"conf: {thai_conf:.3f} vs hailo: {hailo_conf:.3f})"
            )
            return {
                **easyocr_result,
                'selection_reason': 'Valid Thai plate format detected',
            }

        # Otherwise prefer higher confidence
        if hailo_conf >= thai_conf:
            self.logger.debug(
                f"Plate {plate_idx}: Selected Hailo OCR (conf: {hailo_conf:.3f} vs thai: {thai_conf:.3f})"
            )
            return {**hailo_result, 'selection_reason': 'Higher confidence'}
        else:
            self.logger.debug(
                f"Plate {plate_idx}: Selected Thai OCR (conf: {thai_conf:.3f} vs hailo: {hailo_conf:.3f})"
            )
            return {**easyocr_result, 'selection_reason': 'Higher confidence'}
    
    def cleanup(self):
        """Clean up resources."""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)
                self.logger.info("Parallel OCR processor cleaned up")
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")
