#!/usr/bin/env python3
"""
Parallel OCR Processor for AI Camera v1.3

This module provides parallel execution of both Hailo OCR and EasyOCR
for better Thai alphabet recognition. Both OCR engines run simultaneously
to maximize accuracy and coverage for license plate recognition.

Features:
- Parallel execution of Hailo OCR and EasyOCR
- Thread-safe OCR processing
- Confidence scoring and result comparison
- Fallback handling when one OCR fails
- Performance monitoring and statistics

Author: AI Camera Team
Version: 1.3
Date: August 2025
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
    
    def __init__(self, hailo_ocr_model, async_ocr_loader, logger=None):
        """
        Initialize the parallel OCR processor.
        
        Args:
            hailo_ocr_model: Hailo OCR model for license plate recognition
            async_ocr_loader: AsyncOCRLoader instance for EasyOCR
            logger: Logger instance for debugging
        """
        self.hailo_ocr_model = hailo_ocr_model
        self.async_ocr_loader = async_ocr_loader
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
            easyocr_future = self.executor.submit(self._easyocr_worker, plate_image, plate_idx)
            
            # Wait for both results with timeout
            hailo_result = None
            easyocr_result = None
            
            try:
                hailo_result = hailo_future.result(timeout=timeout)
            except FutureTimeoutError:
                self.logger.warning(f"Hailo OCR timed out for plate {plate_idx}")
            except Exception as e:
                self.logger.warning(f"Hailo OCR failed for plate {plate_idx}: {e}")
            
            try:
                easyocr_result = easyocr_future.result(timeout=timeout)
            except FutureTimeoutError:
                self.logger.warning(f"EasyOCR timed out for plate {plate_idx}")
            except Exception as e:
                self.logger.warning(f"EasyOCR failed for plate {plate_idx}: {e}")
            
            # Determine best result
            best_result = self._select_best_result(hailo_result, easyocr_result, plate_idx)
            
            processing_time = time.time() - start_time
            
            return {
                'parallel_success': best_result['success'],
                'processing_time': processing_time,
                'best_result': best_result,
                'hailo': hailo_result or {'success': False, 'error': 'No result'},
                'easyocr': easyocr_result or {'success': False, 'error': 'No result'},
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
            
            # Perform Hailo OCR
            hailo_results = self.hailo_ocr_model(plate_image)
            
            if hailo_results:
                if isinstance(hailo_results, dict):
                    hailo_results = [hailo_results]

                def _get_confidence(item):
                    if hasattr(item, 'confidence'):
                        return float(item.confidence)
                    if isinstance(item, dict):
                        return float(item.get('confidence', 0.0))
                    return 0.0

                def _get_text(item):
                    if hasattr(item, 'text'):
                        return str(item.text)
                    if isinstance(item, dict):
                        return str(item.get('text', ''))
                    return str(item)

                best_result = max(hailo_results, key=_get_confidence)
                best_text = _get_text(best_result)
                best_confidence = _get_confidence(best_result)

                processing_time = time.time() - start_time

                return {
                    'success': True,
                    'text': best_text,
                    'confidence': best_confidence,
                    'processing_time': processing_time,
                    'method': 'hailo'
                }
            else:
                return {'success': False, 'error': 'No Hailo OCR results'}
                
        except Exception as e:
            return {
                'success': False, 
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    def _easyocr_worker(self, plate_image, plate_idx: int) -> Dict[str, Any]:
        """Worker function for EasyOCR processing."""
        start_time = time.time()
        
        try:
            if not self.async_ocr_loader.is_ready():
                if self.async_ocr_loader.is_loading():
                    return {'success': False, 'error': 'EasyOCR still loading'}
                else:
                    return {'success': False, 'error': 'EasyOCR not available'}
            
            # Perform EasyOCR
            easyocr_results = self.async_ocr_loader.read_text(plate_image)
            
            if easyocr_results and len(easyocr_results) > 0:
                # Extract the best result (highest confidence)
                best_result = max(easyocr_results, key=lambda x: x[2])
                
                processing_time = time.time() - start_time
                
                return {
                    'success': True,
                    'text': best_result[1],
                    'confidence': float(best_result[2]),
                    'processing_time': processing_time,
                    'method': 'easyocr'
                }
            else:
                return {'success': False, 'error': 'No EasyOCR results'}
                
        except Exception as e:
            return {
                'success': False, 
                'error': str(e),
                'processing_time': time.time() - start_time
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
        easyocr_conf = easyocr_result.get('confidence', 0.0)
        
        # Prefer EasyOCR for Thai characters (if confidence is close)
        thai_chars = any(ord(c) > 127 for c in easyocr_result.get('text', ''))
        confidence_threshold = 0.1  # EasyOCR gets preference if within 10%
        
        if thai_chars and (easyocr_conf - hailo_conf) > -confidence_threshold:
            self.logger.debug(f"Plate {plate_idx}: Selected EasyOCR for Thai characters (conf: {easyocr_conf:.3f} vs {hailo_conf:.3f})")
            return {
                **easyocr_result,
                'selection_reason': 'Thai characters detected, EasyOCR preferred'
            }
        
        # Otherwise, prefer higher confidence
        if hailo_conf >= easyocr_conf:
            self.logger.debug(f"Plate {plate_idx}: Selected Hailo OCR (conf: {hailo_conf:.3f} vs {easyocr_conf:.3f})")
            return {
                **hailo_result,
                'selection_reason': 'Higher confidence'
            }
        else:
            self.logger.debug(f"Plate {plate_idx}: Selected EasyOCR (conf: {easyocr_conf:.3f} vs {hailo_conf:.3f})")
            return {
                **easyocr_result,
                'selection_reason': 'Higher confidence'
            }
    
    def cleanup(self):
        """Clean up resources."""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)
                self.logger.info("Parallel OCR processor cleaned up")
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")
