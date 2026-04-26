#!/usr/bin/env python3
"""
Adaptive Focus Controller for AI Camera v2.0

This module provides adaptive focus and exposure control that automatically
adjusts camera settings to achieve optimal image sharpness.

Features:
- Automatic focus optimization
- Automatic exposure adjustment
- Quality monitoring and feedback
- Adaptive parameter tuning
- Stability detection and lock mechanism

Author: AI Camera Team
Version: 2.0
Date: December 2025
"""

import time
import numpy as np
from typing import Dict, Any, Optional, Tuple
from collections import deque
from enum import Enum

from edge.src.core.utils.logging_config import get_logger

logger = get_logger(__name__)


class OptimizationState(Enum):
    """State of optimization process."""
    SEARCHING = "searching"  # Actively searching for optimal settings
    OPTIMIZING = "optimizing"  # Fine-tuning current settings
    STABLE = "stable"  # Found good settings, monitoring
    DEGRADED = "degraded"  # Quality degraded, need to re-optimize


class AdaptiveFocusController:
    """
    Adaptive focus and exposure controller that automatically optimizes
    camera settings for maximum image sharpness.
    
    Algorithm:
    1. Start with default/current settings
    2. Measure focus quality (FocusFoM)
    3. Adjust parameters systematically
    4. When quality is good, lock and monitor
    5. If quality degrades, re-optimize
    """
    
    def __init__(self, camera_handler):
        """
        Initialize adaptive focus controller.
        
        Args:
            camera_handler: CameraHandler instance
        """
        self.camera = camera_handler
        self.logger = logger
        
        # State
        self.state = OptimizationState.SEARCHING
        self.optimization_start_time = time.time()
        self.stable_start_time = None
        self.stable_duration = 60.0  # 1 minute stable period
        self.last_optimization_time = 0.0
        self.optimization_interval = 2.0  # Check every 2 seconds
        
        # Quality tracking
        self.focus_history = deque(maxlen=50)
        self.quality_history = deque(maxlen=30)
        self.best_quality = 0.0
        self.best_settings = {}
        
        # Current settings being tested
        self.current_settings = {
            'focus_mode': 2,  # Continuous
            'focus_speed': 0,  # Normal
            'focus_metering': 1,  # Center
            'brightness': 0.0,
            'contrast': 1.0,
            'saturation': 1.0,
            'sharpness': 1.0,
            'exposure_time': None,  # Auto
            'analogue_gain': None,  # Auto
        }
        
        # Optimization parameters
        self.focus_good_threshold = 700  # FocusFoM threshold for good quality
        self.focus_excellent_threshold = 900  # FocusFoM threshold for excellent
        self.quality_stable_threshold = 0.95  # 95% of best quality is considered stable
        self.degradation_threshold = 0.85  # 85% of best quality triggers re-optimization
        
        # Adjustment ranges
        self.adjustment_ranges = {
            'brightness': (-0.2, 0.2, 0.05),  # min, max, step
            'contrast': (0.8, 1.2, 0.1),
            'saturation': (0.8, 1.2, 0.1),
            'sharpness': (0.5, 2.0, 0.25),
            'focus_speed': (0, 1, 1),  # 0 or 1 only
        }
        
        # Statistics
        self.stats = {
            'optimization_cycles': 0,
            'settings_tested': 0,
            'stable_periods': 0,
            're_optimizations': 0
        }
        
        self.logger.info("AdaptiveFocusController initialized")
    
    def start_optimization(self):
        """Start optimization process."""
        self.state = OptimizationState.SEARCHING
        self.optimization_start_time = time.time()
        self.best_quality = 0.0
        self.best_settings = {}
        self.focus_history.clear()
        self.quality_history.clear()
        self.logger.info("Starting adaptive optimization...")
    
    def update_quality(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update quality assessment and adjust settings if needed.
        
        Args:
            metadata: Camera metadata with FocusFoM and exposure info
            
        Returns:
            Dict with optimization status and actions taken
        """
        if not metadata:
            return {'status': 'no_metadata'}
        
        focus_fom = metadata.get("FocusFoM", 0)
        exposure_time = metadata.get("ExposureTime", 0)
        analogue_gain = metadata.get("AnalogueGain", 1.0)
        
        current_time = time.time()
        
        # Record quality
        quality_score = self._calculate_quality_score(focus_fom, exposure_time, analogue_gain)
        self.focus_history.append(focus_fom)
        self.quality_history.append(quality_score)
        
        result = {
            'status': self.state.value,
            'focus_fom': focus_fom,
            'quality_score': quality_score,
            'best_quality': self.best_quality,
            'action': None
        }
        
        # Handle different states
        if self.state == OptimizationState.SEARCHING:
            result.update(self._handle_searching(focus_fom, quality_score, current_time))
        elif self.state == OptimizationState.OPTIMIZING:
            result.update(self._handle_optimizing(focus_fom, quality_score, current_time))
        elif self.state == OptimizationState.STABLE:
            result.update(self._handle_stable(focus_fom, quality_score, current_time))
        elif self.state == OptimizationState.DEGRADED:
            result.update(self._handle_degraded(focus_fom, quality_score, current_time))
        
        return result
    
    def _calculate_quality_score(self, focus_fom: float, exposure_time: float, 
                                 analogue_gain: float) -> float:
        """
        Calculate overall quality score from multiple factors.
        
        Args:
            focus_fom: Focus Figure of Merit
            exposure_time: Exposure time in microseconds
            analogue_gain: Analogue gain
            
        Returns:
            Quality score (0-1)
        """
        # Focus quality (0-1, weight: 0.7)
        focus_score = min(focus_fom / 1000.0, 1.0)
        
        # Exposure quality (0-1, weight: 0.2)
        # Good exposure: 1000-50000 microseconds
        if 1000 <= exposure_time <= 50000:
            exposure_score = 1.0
        elif exposure_time < 1000:
            exposure_score = exposure_time / 1000.0  # Too fast
        else:
            exposure_score = max(0.0, 1.0 - (exposure_time - 50000) / 100000.0)  # Too slow
        
        # Gain quality (0-1, weight: 0.1)
        # Good gain: 1.0-8.0
        if 1.0 <= analogue_gain <= 8.0:
            gain_score = 1.0
        elif analogue_gain < 1.0:
            gain_score = analogue_gain
        else:
            gain_score = max(0.0, 1.0 - (analogue_gain - 8.0) / 4.0)
        
        # Weighted combination
        total_score = (focus_score * 0.7) + (exposure_score * 0.2) + (gain_score * 0.1)
        return total_score
    
    def _handle_searching(self, focus_fom: float, quality_score: float, 
                         current_time: float) -> Dict[str, Any]:
        """Handle searching state - find initial good settings."""
        result = {'action': 'searching'}
        
        # Check if we found good quality
        if focus_fom >= self.focus_good_threshold and quality_score >= 0.7:
            self.best_quality = quality_score
            self.best_settings = self.current_settings.copy()
            self.state = OptimizationState.OPTIMIZING
            self.logger.info(f"Found good quality (FocusFoM: {focus_fom:.0f}, Score: {quality_score:.3f}), starting optimization")
            result['action'] = 'found_good_quality'
            result['transition'] = 'searching_to_optimizing'
        else:
            # Try different settings
            if current_time - self.last_optimization_time > self.optimization_interval:
                self._try_next_setting()
                self.last_optimization_time = current_time
                result['action'] = 'adjusting_settings'
        
        return result
    
    def _handle_optimizing(self, focus_fom: float, quality_score: float,
                          current_time: float) -> Dict[str, Any]:
        """Handle optimizing state - fine-tune settings."""
        result = {'action': 'optimizing'}
        
        # Update best if better
        if quality_score > self.best_quality:
            self.best_quality = quality_score
            self.best_settings = self.current_settings.copy()
            self.logger.debug(f"Improved quality: {quality_score:.3f} (FocusFoM: {focus_fom:.0f})")
        
        # Check if quality is stable and good
        if len(self.quality_history) >= 10:
            recent_qualities = list(self.quality_history)[-10:]
            avg_quality = np.mean(recent_qualities)
            quality_std = np.std(recent_qualities)
            
            # Stable if average is good and variance is low
            if (avg_quality >= self.best_quality * self.quality_stable_threshold and
                quality_std < 0.05 and
                focus_fom >= self.focus_excellent_threshold):
                
                # Lock to best settings
                self._apply_settings(self.best_settings)
                self.state = OptimizationState.STABLE
                self.stable_start_time = current_time
                self.stats['stable_periods'] += 1
                self.logger.info(f"Quality stable and excellent (FocusFoM: {focus_fom:.0f}), locking settings")
                result['action'] = 'locked_stable'
                result['transition'] = 'optimizing_to_stable'
                return result
        
        # Continue optimizing
        if current_time - self.last_optimization_time > self.optimization_interval:
            self._fine_tune_settings()
            self.last_optimization_time = current_time
            result['action'] = 'fine_tuning'
        
        return result
    
    def _handle_stable(self, focus_fom: float, quality_score: float,
                      current_time: float) -> Dict[str, Any]:
        """Handle stable state - monitor quality."""
        result = {'action': 'monitoring'}
        
        # Check if stable period completed (1 minute)
        if self.stable_start_time and (current_time - self.stable_start_time) >= self.stable_duration:
            self.logger.info(f"Stable period completed ({self.stable_duration}s), quality maintained")
            result['action'] = 'stable_period_completed'
            result['stable_duration'] = current_time - self.stable_start_time
            return result
        
        # Check if quality degraded
        if quality_score < self.best_quality * self.degradation_threshold:
            self.state = OptimizationState.DEGRADED
            self.stats['re_optimizations'] += 1
            self.logger.warning(f"Quality degraded (Score: {quality_score:.3f} < {self.best_quality * self.degradation_threshold:.3f}), re-optimizing")
            result['action'] = 'quality_degraded'
            result['transition'] = 'stable_to_degraded'
            return result
        
        # Still stable
        return result
    
    def _handle_degraded(self, focus_fom: float, quality_score: float,
                        current_time: float) -> Dict[str, Any]:
        """Handle degraded state - re-optimize."""
        result = {'action': 're_optimizing'}
        
        # Try to recover
        if current_time - self.last_optimization_time > self.optimization_interval:
            # Reset to best known settings
            self._apply_settings(self.best_settings)
            
            # Check if recovered
            if quality_score >= self.best_quality * self.quality_stable_threshold:
                self.state = OptimizationState.STABLE
                self.stable_start_time = current_time
                self.logger.info("Recovered to stable state")
                result['action'] = 'recovered'
                result['transition'] = 'degraded_to_stable'
            else:
                # Need to search again
                self.state = OptimizationState.SEARCHING
                self.optimization_start_time = current_time
                self.logger.info("Need to search for new optimal settings")
                result['action'] = 'searching_again'
                result['transition'] = 'degraded_to_searching'
            
            self.last_optimization_time = current_time
        
        return result
    
    def _try_next_setting(self):
        """Try next setting in search space."""
        self.stats['settings_tested'] += 1
        
        # Try different focus speeds
        if self.current_settings['focus_speed'] == 0:
            self.current_settings['focus_speed'] = 1
        else:
            self.current_settings['focus_speed'] = 0
            # Try adjusting other parameters
            self._adjust_parameter('sharpness', direction=1)
        
        self._apply_settings(self.current_settings)
        self.logger.debug(f"Trying new settings: {self.current_settings}")
    
    def _fine_tune_settings(self):
        """Fine-tune current settings."""
        self.stats['optimization_cycles'] += 1
        
        # Fine-tune sharpness
        if self.current_settings['sharpness'] < self.adjustment_ranges['sharpness'][1]:
            self._adjust_parameter('sharpness', direction=1)
        
        # Fine-tune contrast
        if self.current_settings['contrast'] < self.adjustment_ranges['contrast'][1]:
            self._adjust_parameter('contrast', direction=1)
        
        self._apply_settings(self.current_settings)
        self.logger.debug(f"Fine-tuning settings: {self.current_settings}")
    
    def _adjust_parameter(self, param_name: str, direction: int = 1):
        """
        Adjust a parameter within its range.
        
        Args:
            param_name: Parameter name
            direction: 1 for increase, -1 for decrease
        """
        if param_name not in self.adjustment_ranges:
            return
        
        min_val, max_val, step = self.adjustment_ranges[param_name]
        current_val = self.current_settings.get(param_name, min_val)
        
        new_val = current_val + (direction * step)
        new_val = max(min_val, min(max_val, new_val))
        
        self.current_settings[param_name] = new_val
    
    def _apply_settings(self, settings: Dict[str, Any]):
        """Apply settings to camera."""
        if not self.camera or not self.camera.picam2:
            return
        
        try:
            controls = {
                "AfMode": settings.get('focus_mode', 2),
                "AfSpeed": settings.get('focus_speed', 0),
                "AfMetering": settings.get('focus_metering', 1),
                "AfRange": 0,  # Full range
                "Brightness": settings.get('brightness', 0.0),
                "Contrast": settings.get('contrast', 1.0),
                "Saturation": settings.get('saturation', 1.0),
                "Sharpness": settings.get('sharpness', 1.0),
                "AeEnable": True,  # Auto exposure
                "AwbEnable": True,  # Auto white balance
            }
            
            # Try libcamera controls
            try:
                from libcamera import controls as lc_controls
                controls["AwbMode"] = lc_controls.AwbModeEnum.Auto
                controls["AeConstraintMode"] = lc_controls.AeConstraintModeEnum.Normal
            except ImportError:
                pass
            
            self.camera.picam2.set_controls(controls)
            
        except Exception as e:
            self.logger.warning(f"Failed to apply settings: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return {
            'state': self.state.value,
            'best_quality': self.best_quality,
            'current_quality': self.quality_history[-1] if self.quality_history else 0.0,
            'stats': self.stats.copy(),
            'current_settings': self.current_settings.copy(),
            'best_settings': self.best_settings.copy(),
            'optimization_time': time.time() - self.optimization_start_time,
            'stable_duration': (time.time() - self.stable_start_time) if self.stable_start_time else 0.0
        }

