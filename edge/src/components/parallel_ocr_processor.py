#!/usr/bin/env python3
"""
Parallel OCR Processor for AI Camera v1.4

This module provides parallel execution of both Hailo OCR and Tesseract (Thai)
for better Thai alphabet recognition. Both OCR engines run simultaneously
to maximize accuracy and coverage for license plate recognition.

Features:
- Parallel execution of Hailo OCR and ThaiLPROCR (Tesseract)
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
    Parallel OCR Processor for simultaneous Hailo and Tesseract execution.

    This processor runs both OCR engines in parallel to maximize accuracy
    for Thai license plate recognition. Results from both engines are
    compared and the best result is selected based on confidence scores.
    """
    
    def __init__(self, hailo_ocr_model, thai_lp_ocr, logger=None):
        """
        Initialize the parallel OCR processor.

        Args:
            hailo_ocr_model: Hailo OCR model for license plate recognition
            thai_lp_ocr: ThaiLPROCR instance (Tesseract) for Thai alphabet recognition
            logger: Logger instance for debugging
        """
        self.hailo_ocr_model = hailo_ocr_model
        self.thai_lp_ocr = thai_lp_ocr
        self.logger = logger or logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ParallelOCR")
        
        self.logger.info("✅ Parallel OCR Processor initialized")
    
    def process_plate_parallel(self, plate_image, plate_idx: int, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Process a license plate image using both Hailo and Tesseract in parallel.
        
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
                'tesseract': thai_result or {'success': False, 'error': 'No result'},
                'plate_idx': plate_idx
            }

        except Exception as e:
            self.logger.error(f"Parallel OCR processing failed for plate {plate_idx}: {e}")
            return {
                'parallel_success': False,
                'processing_time': time.time() - start_time,
                'best_result': {'success': False, 'error': str(e)},
                'hailo': {'success': False, 'error': str(e)},
                'tesseract': {'success': False, 'error': str(e)},
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
        """Worker function for Thai Tesseract processing."""
        start_time = time.time()

        try:
            if not self.thai_lp_ocr or not self.thai_lp_ocr.is_ready():
                return {'success': False, 'error': 'ThaiLPROCR not ready'}

            # Preprocess for Tesseract (resize, deskew, CLAHE)
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
                    'method': 'tesseract',
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
    
    def _select_best_result(self, hailo_result: Optional[Dict], tesseract_result: Optional[Dict], plate_idx: int) -> Dict[str, Any]:
        """
        Select the best OCR result from Hailo and Tesseract.

        Priority rules (in order):
        1. Tesseract wins when validate_thai_plate() passes AND confidence ≥ MIN_THAI_CONF
           (or ≥ 60 % of Hailo confidence). Thai plate structure is more valuable than
           raw digit accuracy — Hailo lacks Thai consonants in its character set.
        2. Hailo wins when Tesseract confidence is too low to trust even a valid-format result.
        3. Otherwise prefer whichever engine has higher confidence.
        """
        if not hailo_result and not tesseract_result:
            return {'success': False, 'error': 'No OCR results available'}
        if not hailo_result:
            return tesseract_result
        if not tesseract_result:
            return hailo_result

        hailo_success     = hailo_result.get('success', False)
        tesseract_success = tesseract_result.get('success', False)

        if not hailo_success and not tesseract_success:
            return {'success': False, 'error': 'Both OCR methods failed'}
        if not hailo_success:
            return tesseract_result
        if not tesseract_success:
            return hailo_result

        hailo_conf = hailo_result.get('confidence', 0.0)
        thai_conf  = tesseract_result.get('confidence', 0.0)
        thai_validated = tesseract_result.get('validation', {}).get('valid', False)

        # Minimum absolute confidence required to trust a Tesseract valid-format result.
        # Below this, Tesseract's text is likely noise even though it looks like a plate.
        MIN_THAI_CONF = 0.35

        def _log(winner, reason):
            hailo_txt = hailo_result.get('text', '')
            thai_txt  = tesseract_result.get('text', '')
            self.logger.info(
                f"[OCR_SELECT] plate={plate_idx} → {winner} | "
                f"hailo='{hailo_txt}' {hailo_conf:.3f} | "
                f"thai='{thai_txt}' {thai_conf:.3f} valid={thai_validated} | "
                f"reason={reason}"
            )

        if thai_validated:
            # Tesseract structurally valid Thai plate.
            # Accept when confidence is sufficient OR at least 60 % of Hailo's.
            if thai_conf >= MIN_THAI_CONF or thai_conf >= hailo_conf * 0.60:
                _log('Tesseract', 'valid Thai plate format detected')
                return {**tesseract_result, 'selection_reason': 'Valid Thai plate format detected'}
            # Valid format but very low confidence → Hailo digits are more reliable
            _log('Hailo', f'Thai valid but conf {thai_conf:.3f} < min {MIN_THAI_CONF}')
            return {**hailo_result, 'selection_reason': 'Higher confidence (Thai valid but low conf)'}

        # No valid Thai structure from Tesseract → prefer higher raw confidence
        if hailo_conf >= thai_conf:
            _log('Hailo', 'higher confidence')
            return {**hailo_result, 'selection_reason': 'Higher confidence'}
        else:
            _log('Tesseract', 'higher confidence')
            return {**tesseract_result, 'selection_reason': 'Higher confidence'}
    
    def cleanup(self):
        """Clean up resources."""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)
                self.logger.info("Parallel OCR processor cleaned up")
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")
