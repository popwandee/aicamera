#!/usr/bin/env python3
"""
Focus Mode Testing Script for AI Camera

This script allows you to test different focus modes independently
without restarting the main service.

Usage:
    python edge/src/tools/test_focus_modes.py --mode continuous --duration 300
    python edge/src/tools/test_focus_modes.py --mode auto --duration 300 --trigger-interval 30
    python edge/src/tools/test_focus_modes.py --compare-all --duration 300

Author: AI Camera Team
Version: 2.0
Date: December 2025
"""

import sys
import os
import argparse
import time
import signal
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Determine project root - handle both direct execution and module execution
if __file__:
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent.parent
else:
    # Fallback if __file__ is not available
    project_root = Path.cwd()
print(f"🔧 Project root: {project_root}\n")
# Set PYTHONPATH environment variable
pythonpath = os.environ.get('PYTHONPATH', '')
if str(project_root) not in pythonpath:
    if pythonpath:
        os.environ['PYTHONPATH'] = f"{project_root}:{pythonpath}"
    else:
        os.environ['PYTHONPATH'] = str(project_root)
print(f"🔧PYTHONPATH: {os.environ.get('PYTHONPATH')}\n")
# Add project root to sys.path
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
print(f"🔧 sys.path: {sys.path}\n")
# Change to project root directory for proper imports
original_cwd = os.getcwd()
try:
    os.chdir(project_root)
except Exception:
    pass
print(f"🔧 original_cwd: {original_cwd}\n")
# Now import modules
try:
    from edge.src.core.dependency_container import get_service
    from edge.src.core.utils.logging_config import get_logger
    from edge.src.components.enhanced_focus_controller import EnhancedFocusController
    from edge.src.components.focus_test_framework import FocusTestFramework
except ImportError as e:
    # Fallback: try adding edge/src to path
    edge_src = project_root / 'edge' / 'src'
    if str(edge_src) not in sys.path:
        sys.path.insert(0, str(edge_src))
    
    try:
        from core.dependency_container import get_service
        from core.utils.logging_config import get_logger
        from components.enhanced_focus_controller import EnhancedFocusController
        from components.focus_test_framework import FocusTestFramework
    except ImportError as e2:
        print(f"Error: Failed to import required modules.")
        print(f"Project root: {project_root}")
        print(f"Python path: {sys.path}")
        print(f"Import error: {e}")
        print(f"Fallback import error: {e2}")
        print("\nPlease ensure you are running from the project root directory.")
        print("Or set PYTHONPATH: export PYTHONPATH=$PWD:$PYTHONPATH")
        sys.exit(1)
print(f"🔧 Import modules successfully\n")
logger = get_logger(__name__)


class FocusTestRunner:
    """Standalone focus test runner."""
    
    def __init__(self, service_name='aicamera_lpr'):
        """
        Initialize test runner.
        
        Args:
            service_name: Systemd service name (default: aicamera_lpr)
        """
        self.camera_handler = None
        self.detection_manager = None
        self.test_framework = None
        self.running = True
        self.service_name = service_name
        self.service_was_running = False
        self.adaptive_controller = None
        self.health_check_enabled = True
        self.health_check_duration = 3.0
        self.health_check_variation = 50.0
        self.health_check_samples = 20
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        print(f"🔧 Signal handlers set up\n")
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals."""
        logger.info("Received interrupt signal, shutting down gracefully...")
        self.running = False
        # Ensure cleanup happens
        self.cleanup()
        sys.exit(1)
    
    def _check_service_status(self) -> bool:
        """
        Check if service is running.
        
        Returns:
            bool: True if service is running, False otherwise
        """
        try:
            import subprocess
            result = subprocess.run(
                ['systemctl', 'is-active', '--quiet', self.service_name],
                capture_output=True,
                timeout=5
            )
            print(f"🔧 Service status: {result.returncode == 0}\n")
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Failed to check service status: {e}")
            print(f"🔧 Failed to check service status: {e}\n")
            return False
    
    def _stop_service(self) -> bool:
        """
        Stop the camera service.
        
        Returns:
            bool: True if service was stopped successfully
        """
        try:
            import subprocess
            
            # Check if service is running
            if not self._check_service_status():
                logger.info(f"Service {self.service_name} is not running.")
                print(f"🔧 Service {self.service_name} is not running.\n")
                return True
            
            logger.info(f"Stopping service {self.service_name}...")
            result = subprocess.run(
                ['sudo', 'systemctl', 'stop', self.service_name],
                capture_output=True,
                timeout=30,
                text=True
            )
            print(f"🔧 Service {self.service_name} stopped: {result.returncode == 0}\n")
            if result.returncode == 0:
                # Wait for service to fully stop
                logger.info("Waiting for service to stop...")
                for i in range(30):  # Wait up to 3 seconds
                    if not self._check_service_status():
                        logger.info(f"Service {self.service_name} stopped successfully.")
                        self.service_was_running = True
                        return True
                    time.sleep(0.1)
                
                logger.warning("Service stop timeout, but continuing...")
                self.service_was_running = True
                return True
            else:
                logger.error(f"Failed to stop service: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Service stop command timed out")
            return False
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            return False
    
    def _start_service(self) -> bool:
        """
        Start the camera service.
        
        Returns:
            bool: True if service was started successfully
        """
        if not self.service_was_running:
            logger.info(f"Service {self.service_name} was not running before test, skipping start.")
            return True
        
        try:
            import subprocess
            
            logger.info(f"Starting service {self.service_name}...")
            print(f"🔧 Starting service {self.service_name}...\n")
            result = subprocess.run(
                ['sudo', 'systemctl', 'start', self.service_name],
                capture_output=True,
                timeout=30,
                text=True
            )
            
            if result.returncode == 0:
                # Wait for service to fully start
                logger.info("Waiting for service to start...")
                for i in range(60):  # Wait up to 6 seconds
                    if self._check_service_status():
                        logger.info(f"Service {self.service_name} started successfully.")
                        print(f"🔧 Service {self.service_name} started successfully.\n")
                        return True
                    time.sleep(0.1)
                
                logger.warning("Service start timeout, but service may be starting...")
                print(f"🔧 Service start timeout, but service may be starting...\n")
                return True
            else:
                logger.error(f"Failed to start service: {result.stderr}")
                print(f"🔧 Failed to start service: {result.stderr}\n")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Service start command timed out")
            print(f"🔧 Service start command timed out\n")
            return False
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            print(f"🔧 Error starting service: {e}\n")
            return False
    
    def initialize_services(self, skip_service_control=False):
        """
        Initialize camera and detection services.
        
        Args:
            skip_service_control: If True, skip service stop/start (service should already be stopped)
        """
        try:
            logger.info("Initializing services...")
            
            # Stop main service first (camera doesn't support multi-access)
            # Note: Service should already be stopped by main() if not skipped
            if not skip_service_control:
                if not self._stop_service():
                    logger.error("Failed to stop main service. Cannot proceed with test.")
                    print(f"🔧 Failed to stop main service. Cannot proceed with test.\n")
                    return False
                
                # Wait a bit for service to fully release camera
                logger.info("Waiting for camera to be released...")
                print(f"🔧 Waiting for camera to be released...\n")
                time.sleep(2)
            
            # Get camera handler from dependency container
            camera_manager = get_service('camera_manager')
            if not camera_manager:
                logger.error("Camera manager not available. Make sure the service is running.")
                print(f"🔧 Camera manager not available. Make sure the service is running.\n")
                return False
            
            self.camera_handler = camera_manager.camera_handler
            if not self.camera_handler:
                logger.error("Camera handler not available.")
                print(f"🔧 Camera handler not available.\n")
                return False
            
            # Check if camera is initialized and streaming
            if not self.camera_handler.initialized:
                logger.warning("Camera not initialized. Attempting to initialize...")
                if not self.camera_handler.initialize_camera():
                    logger.error("Failed to initialize camera.")
                    print(f"🔧 Failed to initialize camera.\n")
                    return False
            
            if not self.camera_handler.streaming:
                logger.warning("Camera not streaming. Attempting to start...")
                if not self.camera_handler.start_camera():
                    logger.error("Failed to start camera.")
                    print(f"🔧 Failed to start camera.\n")
                    return False
            
            # Camera configuration will be applied based on test mode
            # Don't apply default config here - let each mode configure itself
            
            # Wait for frame buffer to be ready
            logger.info("Waiting for frame buffer to be ready...")
            for i in range(30):  # Wait up to 3 seconds
                if self.camera_handler.is_frame_buffer_ready():
                    break
                time.sleep(0.1)
            else:
                logger.warning("Frame buffer not ready, but continuing...")
                print(f"🔧 Frame buffer not ready, but continuing...\n")
            
            # Get detection manager (optional)
            try:
                self.detection_manager = get_service('detection_manager')
                if self.detection_manager:
                    logger.info("Detection manager available.")
                    print(f"🔧 Detection manager available.\n")
                else:
                    logger.warning("Detection manager not available. Tests will run without detection.")
                    print(f"🔧 Detection manager not available. Tests will run without detection.\n")
            except Exception as e:
                logger.warning(f"Detection manager not available: {e}")
                print(f"🔧 Detection manager not available: {e}\n")
            
            # Initialize test framework
            self.test_framework = FocusTestFramework(
                self.camera_handler,
                self.detection_manager
            )
            
            logger.info("Services initialized successfully.")
            print(f"🔧 Services initialized successfully.\n")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            print(f"🔧 Failed to initialize services: {e}\n")
            return False
    
    def _log_health_check(self, result: Dict[str, Any], label: str):
        status_icon = "✅" if result.get('status') else "⚠️"
        logger.info(
            f"{label} focus health check {status_icon} "
            f"(samples={result.get('sample_count')}, "
            f"range={result.get('variation', 0):.1f}, "
            f"fom[{result.get('fom_min', 0):.0f}-{result.get('fom_max', 0):.0f}])"
        )
        print(
            f"🔧 {label} focus health check {status_icon}: "
            f"samples={result.get('sample_count')}, "
            f"variation={result.get('variation', 0):.1f}, "
            f"FoM[{result.get('fom_min', 0):.0f}-{result.get('fom_max', 0):.0f}]"
        )
        for warning in result.get('warnings', []):
            logger.warning(f"Health check warning: {warning}")
            print(f"🔧 ⚠️ {warning}")
    
    def _maybe_run_health_check(self, label: str = "Pre-test"):
        if not self.health_check_enabled or not self.test_framework:
            return None
        result = self.test_framework.perform_focus_health_check(
            duration=self.health_check_duration,
            min_valid_samples=self.health_check_samples,
            variation_threshold=self.health_check_variation
        )
        self._log_health_check(result, label)
        if not result.get('status'):
            logger.warning("Focus health check failed, continuing test but results may be unreliable.")
        return result
    
    def _log_result_summary(self, result: Dict[str, Any]):
        if not self.test_framework or not result:
            return
        summary = self.test_framework.summarize_metrics(result)
        logger.info(
            f"Result summary [{summary.get('mode')}]: "
            f"FoM mean={summary.get('focus_mean')}, "
            f"std={summary.get('focus_std')}, "
            f"frames={summary.get('frames')}, "
            f"detect_rate={summary.get('detection_rate')}, "
            f"lens[{summary.get('lens_min')}..{summary.get('lens_max')}]"
        )
        print(
            f"🔧 Summary ({summary.get('mode')}): "
            f"FoM mean={summary.get('focus_mean'):.1f} "
            f"(min={summary.get('focus_min'):.1f}, max={summary.get('focus_max'):.1f}), "
            f"σ={summary.get('focus_std'):.1f}, "
            f"frames={summary.get('frames')}, "
            f"detection_rate={summary.get('detection_rate'):.3f}"
        )
    
    def _apply_default_config(self):
        """Apply default IMX708 configuration (all auto)."""
        if not self.camera_handler:
            return False
        
        if hasattr(self.camera_handler, 'apply_auto_focus_defaults'):
            success = self.camera_handler.apply_auto_focus_defaults()
            if success:
                logger.info("Default IMX708 configuration applied via CameraHandler")
                print(f"🔧 Default IMX708 configuration applied (CameraHandler auto profile)\n")
                return True
        
        if not getattr(self.camera_handler, "picam2", None):
            return False
        
        try:
            logger.info("Applying default IMX708 configuration (fallback path)...")
            
            default_config = {
                "AeEnable": True,
                "AwbEnable": True,
                "AfMode": 1,
                "AfRange": 0,
                "AfSpeed": 0,
                "AfMetering": 1,
                "Brightness": 0.0,
                "Contrast": 1.0,
                "Saturation": 1.0,
                "Sharpness": 1.0,
            }
            
            try:
                from libcamera import controls as lc_controls
                default_config["AwbMode"] = lc_controls.AwbModeEnum.Auto
                default_config["AeConstraintMode"] = lc_controls.AeConstraintModeEnum.Normal
            except ImportError:
                pass
            
            self.camera_handler.picam2.set_controls(default_config)
            time.sleep(0.2)
            try:
                self.camera_handler.picam2.set_controls({"AfTrigger": 0})
                logger.info("Autofocus triggered (fallback)")
            except Exception as trigger_error:
                logger.warning(f"Failed to trigger autofocus: {trigger_error}")
            
            print(f"🔧 Default IMX708 configuration applied (fallback path)\n")
            return True
        except Exception as e:
            logger.error(f"Failed to apply default config: {e}")
            print(f"🔧 Failed to apply default config: {e}\n")
            return False
    
    def _apply_manual_config(self, **kwargs):
        """Apply manual configuration with custom parameters."""
        if not self.camera_handler or not self.camera_handler.picam2:
            return False
        
        try:
            logger.info("Applying manual configuration...")
            print(f"🔧 Applying manual configuration...\n")
            # Manual configuration from kwargs
            manual_config = {
                "AeEnable": kwargs.get('ae_enable', True),
                "AwbEnable": kwargs.get('awb_enable', True),
                "AfMode": kwargs.get('af_mode', 2),
                "AfRange": kwargs.get('af_range', 0),
                "AfSpeed": kwargs.get('af_speed', 0),
                "AfMetering": kwargs.get('af_metering', 1),
                "Brightness": kwargs.get('brightness', 0.0),
                "Contrast": kwargs.get('contrast', 1.0),
                "Saturation": kwargs.get('saturation', 1.0),
                "Sharpness": kwargs.get('sharpness', 1.0),
            }
            
            # Manual exposure if specified
            if kwargs.get('exposure_time'):
                manual_config["ExposureTime"] = kwargs['exposure_time']
                manual_config["AeEnable"] = False
            
            if kwargs.get('analogue_gain'):
                manual_config["AnalogueGain"] = kwargs['analogue_gain']
            
            # Try libcamera controls
            try:
                from libcamera import controls as lc_controls
                if kwargs.get('awb_mode') is not None:
                    manual_config["AwbMode"] = kwargs['awb_mode']
                else:
                    manual_config["AwbMode"] = lc_controls.AwbModeEnum.Auto
            except ImportError:
                pass
            
            self.camera_handler.picam2.set_controls(manual_config)
            logger.info(f"Manual configuration applied: {manual_config}")
            print(f"🔧 Manual configuration applied: {manual_config}\n")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply manual config: {e}")
            print(f"🔧 Failed to apply manual config: {e}\n")
            return False
    
    def _run_adaptive_test(self, duration: int) -> Dict[str, Any]:
        """
        Run adaptive optimization test.
        
        Args:
            duration: Test duration in seconds
            
        Returns:
            Dict with test results
        """
        import numpy as np
        from datetime import datetime
        
        if not self.adaptive_controller:
            logger.error("Adaptive controller not initialized")
            print(f"🔧 Adaptive controller not initialized\n")
            return None
        
        logger.info(f"Running adaptive optimization test for {duration}s")
        print(f"🔧 Running adaptive optimization test for {duration}s\n")
        # Initialize metrics
        metrics = {
            'mode': 'adaptive',
            'start_time': time.time(),
            'end_time': None,
            'duration': duration,
            'focus_fom_values': [],
            'quality_scores': [],
            'optimization_states': [],
            'settings_history': [],
            'detection_results': []
        }
        
        end_time = time.time() + duration
        frame_count = 0
        frame_interval = 1.0 / 30.0  # 30 FPS
        last_frame_time = time.time()
        
        while time.time() < end_time and self.running:
            current_time = time.time()
            
            # Rate limiting
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.001)
                continue
            
            try:
                # Capture frame with metadata
                frame_data = self.camera_handler.capture_frame(
                    source="buffer",
                    stream_type="main",
                    include_metadata=True
                )
                
                if frame_data is None:
                    continue
                
                # Extract metadata
                if isinstance(frame_data, dict):
                    metadata = frame_data.get('metadata', {})
                    frame = frame_data.get('frame')
                else:
                    metadata = {}
                    frame = frame_data
                
                # Update adaptive controller
                opt_result = self.adaptive_controller.update_quality(metadata)
                
                # Record metrics
                focus_fom = metadata.get("FocusFoM", 0)
                if focus_fom > 0:
                    metrics['focus_fom_values'].append(focus_fom)
                    metrics['quality_scores'].append(opt_result.get('quality_score', 0))
                    metrics['optimization_states'].append(opt_result.get('status', 'unknown'))
                    
                    # Record settings when they change
                    if opt_result.get('action') in ['adjusting_settings', 'fine_tuning', 'locked_stable']:
                        stats = self.adaptive_controller.get_statistics()
                        metrics['settings_history'].append({
                            'timestamp': current_time,
                            'settings': stats.get('current_settings', {}),
                            'quality': opt_result.get('quality_score', 0)
                        })
                
                # Run detection if available
                if self.detection_manager and frame is not None:
                    try:
                        detection_result = self.detection_manager.process_frame_from_camera(
                            self.camera_handler.camera_manager
                        )
                        if detection_result:
                            metrics['detection_results'].append({
                                'timestamp': current_time,
                                'vehicles_detected': len(detection_result.get('vehicles', [])),
                                'focus_fom': focus_fom
                            })
                    except Exception:
                        pass
                
                frame_count += 1
                last_frame_time = current_time
                
                # Log progress
                if frame_count % 100 == 0:
                    stats = self.adaptive_controller.get_statistics()
                    logger.info(f"Adaptive test progress: {frame_count} frames, "
                              f"State: {stats['state']}, Quality: {stats['current_quality']:.3f}")
                    print(f"🔧 Adaptive test progress: {frame_count} frames, "
                          f"State: {stats['state']}, Quality: {stats['current_quality']:.3f}\n")
                
            except Exception as e:
                logger.error(f"Error in adaptive test loop: {e}")
                print(f"🔧 Error in adaptive test loop: {e}\n")
                continue
        
        # Calculate final metrics
        metrics['end_time'] = time.time()
        metrics['actual_duration'] = metrics['end_time'] - metrics['start_time']
        metrics['total_frames'] = frame_count
        
        # Focus quality metrics
        if metrics['focus_fom_values']:
            metrics['focus_quality'] = {
                'mean': float(np.mean(metrics['focus_fom_values'])),
                'std': float(np.std(metrics['focus_fom_values'])),
                'min': float(np.min(metrics['focus_fom_values'])),
                'max': float(np.max(metrics['focus_fom_values']))
            }
        
        # Adaptive controller statistics
        stats = self.adaptive_controller.get_statistics()
        metrics['adaptive_stats'] = stats
        print(f"🔧 Adaptive controller statistics: {stats}\n")
        # Detection metrics
        if metrics['detection_results']:
            metrics['detection_metrics'] = {
                'total_detections': len(metrics['detection_results']),
                'detection_rate': len(metrics['detection_results']) / frame_count if frame_count > 0 else 0
            }
        else:
            metrics['detection_metrics'] = {
                'total_detections': 0,
                'detection_rate': 0.0
            }
        
        return metrics
    
    def run_single_test(self, mode: str, duration: int, **kwargs):
        """
        Run a single focus mode test.
        
        Args:
            mode: Focus mode ("auto", "continuous", "manual", "hybrid", "default", "adaptive")
            duration: Test duration in seconds
            **kwargs: Mode-specific parameters
        """
        if not self.test_framework and mode != "adaptive":
            logger.error("Test framework not initialized.")
            print(f"🔧 Test framework not initialized.\n")
            return None
        
        logger.info(f"Starting test: mode={mode}, duration={duration}s")
        print(f"🔧 Starting test: mode={mode}, duration={duration}s\n")
        
        self._maybe_run_health_check(label=f"{mode} pre-check")
        
        # Apply mode-specific configuration
        if mode == "default":
            if not self._apply_default_config():
                logger.error("Failed to apply default configuration")
                print(f"🔧 Failed to apply default configuration\n")
                return None
            # Use test framework with default config
            result = self.test_framework.run_test("continuous", duration, speed=0, metering=1, range_mode=0)
        elif mode == "manual":
            if not self._apply_manual_config(**kwargs):
                logger.error("Failed to apply manual configuration")
                print(f"🔧 Failed to apply manual configuration\n")
                return None
            # Use test framework with manual config
            # Filter kwargs to only include parameters that continuous mode accepts
            continuous_params = {
                'speed': kwargs.get('af_speed', 0),
                'metering': kwargs.get('af_metering', 1),
                'range_mode': kwargs.get('af_range', 0)
            }
            result = self.test_framework.run_test("continuous", duration, **continuous_params)
        elif mode == "adaptive":
            # Initialize adaptive controller
            if not self.adaptive_controller:
                from edge.src.components.adaptive_focus_controller import AdaptiveFocusController
                self.adaptive_controller = AdaptiveFocusController(self.camera_handler)
            self.adaptive_controller.start_optimization()
            logger.info("Adaptive optimization started")
            print(f"🔧 Adaptive optimization started\n")
            result = self._run_adaptive_test(duration)
        else:
            # Use test framework for other modes
            result = self.test_framework.run_test(mode, duration, **kwargs)
        
        if result:
            logger.info("Test completed successfully.")
            print(f"🔧 Test completed successfully.\n")
            if 'focus_quality' in result:
                logger.info(f"  Focus Quality - Mean: {result.get('focus_quality', {}).get('mean', 0):.1f}")
                print(f"🔧 Focus Quality - Mean: {result.get('focus_quality', {}).get('mean', 0):.1f}\n")
            if 'detection_metrics' in result:
                logger.info(f"  Detection Rate: {result.get('detection_metrics', {}).get('detection_rate', 0):.3f}")
                print(f"🔧 Detection Rate: {result.get('detection_metrics', {}).get('detection_rate', 0):.3f}\n")
            logger.info(f"  Total Frames: {result.get('total_frames', 0)}")
            print(f"🔧 Total Frames: {result.get('total_frames', 0)}\n")
            # Log adaptive stats if available
            if 'adaptive_stats' in result:
                stats = result['adaptive_stats']
                logger.info(f"  Adaptive State: {stats.get('state', 'unknown')}")
                print(f"🔧 Adaptive State: {stats.get('state', 'unknown')}\n")
                logger.info(f"  Best Quality: {stats.get('best_quality', 0):.3f}")
                print(f"🔧 Best Quality: {stats.get('best_quality', 0):.3f}\n")
                logger.info(f"  Optimization Cycles: {stats.get('stats', {}).get('optimization_cycles', 0)}")
                print(f"🔧 Optimization Cycles: {stats.get('stats', {}).get('optimization_cycles', 0)}\n")
        else:
            logger.error("Test failed or returned no results.")
            print(f"🔧 Test failed or returned no results.\n")
        
        self._log_result_summary(result)
        return result
    
    def _run_continuous_grid_search(self, duration: int = 300):
        """
        Run grid search for Continuous Focus mode.
        
        Args:
            duration: Test duration for each parameter combination in seconds
            
        Returns:
            Dict with best result and all tested combinations
        """
        logger.info(f"\n{'='*60}")
        logger.info("1. Continuous Focus Mode - Grid Search")
        logger.info(f"{'='*60}")
        
        self._maybe_run_health_check(label="Continuous grid search")
        
        # Grid search parameters for Continuous Focus
        speed_options = [0, 1]  # Normal, Fast
        metering_options = [0, 1]  # Auto, Center-weighted
        sharpness_options = [0.5, 1.0, 1.5, 2.0]  # Different sharpness levels
        
        best_result = None
        best_score = -1.0
        all_results = {}
        
        total_combinations = len(speed_options) * len(metering_options) * len(sharpness_options)
        current_combination = 0
        
        for speed in speed_options:
            for metering in metering_options:
                for sharpness in sharpness_options:
                    if not self.running:
                        logger.info("Test interrupted by user.")
                        break
                    
                    current_combination += 1
                    combination_name = f"continuous_s{speed}_m{metering}_sh{sharpness}"
                    
                    logger.info(f"\n[{current_combination}/{total_combinations}] Testing: Speed={speed}, Metering={metering}, Sharpness={sharpness}")
                    
                    # Apply manual config with continuous focus
                    params = {
                        'af_mode': 2,  # Continuous
                        'af_speed': speed,
                        'af_metering': metering,
                        'af_range': 0,  # Full range
                        'sharpness': sharpness,
                        'brightness': 0.0,
                        'contrast': 1.0,
                        'saturation': 1.0
                    }
                    
                    # Apply config first
                    if not self._apply_manual_config(**params):
                        logger.warning(f"Failed to apply config for {combination_name}, skipping...")
                        continue
                    
                    # Then run test with continuous mode (filter params for continuous mode)
                    continuous_params = {
                        'speed': speed,
                        'metering': metering,
                        'range_mode': 0
                    }
                    result = self.test_framework.run_test("continuous", duration, **continuous_params)
                    
                    if result:
                        all_results[combination_name] = result
                        
                        # Save each combination result immediately
                        try:
                            import json
                            from pathlib import Path
                            project_root = Path(__file__).resolve().parent.parent.parent.parent
                            results_dir = project_root / 'edge' / 'tests' / 'results'
                            results_dir.mkdir(parents=True, exist_ok=True)
                            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                            combo_file = results_dir / f"{session_id}_continuous_{combination_name}.json"
                            
                            def convert_numpy(obj):
                                import numpy as np
                                if isinstance(obj, np.integer):
                                    return int(obj)
                                elif isinstance(obj, np.floating):
                                    return float(obj)
                                elif isinstance(obj, np.ndarray):
                                    return obj.tolist()
                                elif isinstance(obj, dict):
                                    return {key: convert_numpy(value) for key, value in obj.items()}
                                elif isinstance(obj, list):
                                    return [convert_numpy(item) for item in obj]
                                return obj
                            
                            combo_data = {
                                'combination': combination_name,
                                'params': params,
                                'result': convert_numpy(result),
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            with open(combo_file, 'w') as f:
                                json.dump(combo_data, f, indent=2, default=str)
                            logger.debug(f"Saved combination result: {combo_file}")
                        except Exception as save_error:
                            logger.warning(f"Failed to save combination result: {save_error}")
                        
                        # Calculate score
                        focus_mean = result.get('focus_quality', {}).get('mean', 0) if result.get('focus_quality') else 0
                        detection_rate = result.get('detection_metrics', {}).get('detection_rate', 0) if result.get('detection_metrics') else 0
                        score = (focus_mean / 1000.0 * 0.6) + (detection_rate * 0.4)
                        
                        if score > best_score:
                            best_score = score
                            best_result = {
                                'combination': combination_name,
                                'params': params,
                                'result': result,
                                'score': score
                            }
                    
                    # Wait between combinations
                    if current_combination < total_combinations:
                        logger.info("Waiting 5 seconds before next combination...")
                        time.sleep(5)
        
        logger.info(f"\nBest Continuous Focus: {best_result['combination'] if best_result else 'N/A'}")
        logger.info(f"Best Score: {best_score:.3f}")
        
        return {
            'mode': 'continuous_grid_search',
            'best_result': best_result,
            'all_results': all_results,
            'total_combinations': total_combinations
        }
    
    def _run_manual_adaptive_grid_search(self, duration: int = 300):
        """
        Run grid search for Manual with Adaptive Focus mode.
        
        Args:
            duration: Test duration for each parameter combination in seconds
            
        Returns:
            Dict with best result and all tested combinations
        """
        logger.info(f"\n{'='*60}")
        logger.info("3. Manual with Adaptive Focus Mode - Grid Search")
        logger.info(f"{'='*60}")
        
        self._maybe_run_health_check(label="Manual adaptive grid search")
        
        # Grid search parameters for Manual with Adaptive
        sharpness_options = [0.5, 1.0, 1.5, 2.0]
        contrast_options = [0.8, 1.0, 1.2]
        brightness_options = [-0.1, 0.0, 0.1]
        
        best_result = None
        best_score = -1.0
        all_results = {}
        
        total_combinations = len(sharpness_options) * len(contrast_options) * len(brightness_options)
        current_combination = 0
        
        for sharpness in sharpness_options:
            for contrast in contrast_options:
                for brightness in brightness_options:
                    if not self.running:
                        logger.info("Test interrupted by user.")
                        break
                    
                    current_combination += 1
                    combination_name = f"manual_adaptive_sh{sharpness}_c{contrast}_b{brightness}"
                    
                    logger.info(f"\n[{current_combination}/{total_combinations}] Testing: Sharpness={sharpness}, Contrast={contrast}, Brightness={brightness}")
                    
                    # Apply manual config
                    params = {
                        'af_mode': 2,  # Continuous (for adaptive to work)
                        'af_speed': 0,  # Normal
                        'af_metering': 1,  # Center-weighted
                        'af_range': 0,  # Full range
                        'sharpness': sharpness,
                        'contrast': contrast,
                        'brightness': brightness,
                        'saturation': 1.0
                    }
                    
                    # Apply manual config first
                    if not self._apply_manual_config(**params):
                        logger.warning(f"Failed to apply config for {combination_name}, skipping...")
                        continue
                    
                    # Initialize adaptive controller
                    if not self.adaptive_controller:
                        from edge.src.components.adaptive_focus_controller import AdaptiveFocusController
                        self.adaptive_controller = AdaptiveFocusController(self.camera_handler)
                    
                    # Start adaptive optimization
                    self.adaptive_controller.start_optimization()
                    
                    # Run adaptive test
                    result = self._run_adaptive_test(duration)
                    
                    if result:
                        # Add manual config params to result
                        result['manual_config'] = params
                        all_results[combination_name] = result
                        
                        # Save each combination result immediately
                        try:
                            import json
                            from pathlib import Path
                            project_root = Path(__file__).resolve().parent.parent.parent.parent
                            results_dir = project_root / 'edge' / 'tests' / 'results'
                            results_dir.mkdir(parents=True, exist_ok=True)
                            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                            combo_file = results_dir / f"{session_id}_manual_adaptive_{combination_name}.json"
                            
                            def convert_numpy(obj):
                                import numpy as np
                                if isinstance(obj, np.integer):
                                    return int(obj)
                                elif isinstance(obj, np.floating):
                                    return float(obj)
                                elif isinstance(obj, np.ndarray):
                                    return obj.tolist()
                                elif isinstance(obj, dict):
                                    return {key: convert_numpy(value) for key, value in obj.items()}
                                elif isinstance(obj, list):
                                    return [convert_numpy(item) for item in obj]
                                return obj
                            
                            combo_data = {
                                'combination': combination_name,
                                'params': params,
                                'result': convert_numpy(result),
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            with open(combo_file, 'w') as f:
                                json.dump(combo_data, f, indent=2, default=str)
                            logger.debug(f"Saved combination result: {combo_file}")
                        except Exception as save_error:
                            logger.warning(f"Failed to save combination result: {save_error}")
                        
                        # Calculate score
                        focus_mean = result.get('focus_quality', {}).get('mean', 0) if result.get('focus_quality') else 0
                        detection_rate = result.get('detection_metrics', {}).get('detection_rate', 0) if result.get('detection_metrics') else 0
                        adaptive_quality = result.get('adaptive_stats', {}).get('best_quality', 0) if result.get('adaptive_stats') else 0
                        
                        # Combined score: focus quality (40%) + detection (30%) + adaptive quality (30%)
                        score = (focus_mean / 1000.0 * 0.4) + (detection_rate * 0.3) + (adaptive_quality * 0.3)
                        
                        if score > best_score:
                            best_score = score
                            best_result = {
                                'combination': combination_name,
                                'params': params,
                                'result': result,
                                'score': score
                            }
                    
                    # Reset adaptive controller for next combination
                    self.adaptive_controller = None
                    
                    # Wait between combinations
                    if current_combination < total_combinations:
                        logger.info("Waiting 5 seconds before next combination...")
                        time.sleep(5)
        
        logger.info(f"\nBest Manual with Adaptive: {best_result['combination'] if best_result else 'N/A'}")
        logger.info(f"Best Score: {best_score:.3f}")
        
        return {
            'mode': 'manual_adaptive_grid_search',
            'best_result': best_result,
            'all_results': all_results,
            'total_combinations': total_combinations
        }
    
    def _save_mode_result(self, mode_name: str, result_data: Dict[str, Any], test_session_id: str = None) -> str:
        """
        Save individual mode result to JSON file immediately.
        
        Args:
            mode_name: Name of the mode (e.g., 'auto_focus_default')
            result_data: Result data to save
            test_session_id: Optional session ID to group results
            
        Returns:
            Path to saved file
        """
        import json
        import numpy as np
        from pathlib import Path
        
        try:
            # Get results directory
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            results_dir = project_root / 'edge' / 'tests' / 'results'
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate session ID if not provided
            if not test_session_id:
                test_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create filename
            filename = f"{test_session_id}_{mode_name}.json"
            output_path = results_dir / filename
            
            # Convert numpy types for JSON serialization
            def convert_numpy(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_numpy(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy(item) for item in obj]
                return obj
            
            # Prepare data to save
            save_data = {
                'mode': mode_name,
                'test_session_id': test_session_id,
                'timestamp': datetime.now().isoformat(),
                'result': convert_numpy(result_data)
            }
            
            # Save to file
            with open(output_path, 'w') as f:
                json.dump(save_data, f, indent=2, default=str)
            
            logger.info(f"✅ Saved {mode_name} result to: {output_path}")
            print(f"🔧 Saved {mode_name} result to: {output_path}\n")
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to save {mode_name} result: {e}")
            # Try fallback location
            try:
                import os
                home_dir = os.path.expanduser("~")
                fallback_dir = Path(home_dir) / 'aicamera_test_results'
                fallback_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{test_session_id}_{mode_name}.json"
                fallback_path = fallback_dir / filename
                with open(fallback_path, 'w') as f:
                    json.dump(save_data, f, indent=2, default=str)
                logger.info(f"Saved {mode_name} result to fallback: {fallback_path}")
                return str(fallback_path)
            except Exception as e2:
                logger.error(f"Failed to save to fallback location: {e2}")
                return ""
    
    def _load_mode_results(self, test_session_id: str) -> Dict[str, Any]:
        """
        Load all mode results from JSON files for a given session.
        
        Args:
            test_session_id: Session ID to load results for
            
        Returns:
            Dict with loaded results
        """
        import json
        from pathlib import Path
        
        loaded_results = {}
        
        try:
            # Try project directory first
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            results_dir = project_root / 'edge' / 'tests' / 'results'
            
            # Find all files matching session ID
            pattern = f"{test_session_id}_*.json"
            result_files = list(results_dir.glob(pattern))
            
            if not result_files:
                # Try fallback location
                import os
                home_dir = os.path.expanduser("~")
                fallback_dir = Path(home_dir) / 'aicamera_test_results'
                result_files = list(fallback_dir.glob(pattern))
            
            for result_file in result_files:
                try:
                    with open(result_file, 'r') as f:
                        data = json.load(f)
                        mode_name = data.get('mode', result_file.stem.replace(f"{test_session_id}_", ""))
                        loaded_results[mode_name] = data.get('result', {})
                        logger.info(f"Loaded result from: {result_file}")
                except Exception as e:
                    logger.warning(f"Failed to load {result_file}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to load mode results: {e}")
        
        return loaded_results
    
    def _compare_loaded_results(self, loaded_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare loaded results and generate summary.
        
        Args:
            loaded_results: Dict with loaded results from files
            
        Returns:
            Comparison summary
        """
        # Prepare results for comparison
        comparison_results = {
            'auto_focus_default': loaded_results.get('auto_focus_default'),
            'continuous_best': loaded_results.get('continuous_best'),
            'manual_adaptive_best': loaded_results.get('manual_adaptive_best')
        }
        
        # Find best overall mode
        best_mode = None
        best_score = -1.0
        mode_scores = {}
        
        for mode_name, result in comparison_results.items():
            if not result:
                continue
            
            # Calculate overall score
            focus_mean = result.get('focus_quality', {}).get('mean', 0) if result.get('focus_quality') else 0
            detection_rate = result.get('detection_metrics', {}).get('detection_rate', 0) if result.get('detection_metrics') else 0
            
            # For adaptive mode, include adaptive quality
            if 'adaptive_stats' in result:
                adaptive_quality = result.get('adaptive_stats', {}).get('best_quality', 0)
                score = (focus_mean / 1000.0 * 0.4) + (detection_rate * 0.3) + (adaptive_quality * 0.3)
            else:
                score = (focus_mean / 1000.0 * 0.6) + (detection_rate * 0.4)
            
            mode_scores[mode_name] = {
                'score': score,
                'focus_mean': focus_mean,
                'detection_rate': detection_rate
            }
            
            if score > best_score:
                best_score = score
                best_mode = mode_name
        
        return {
            'timestamp': datetime.now().isoformat(),
            'best_mode': best_mode,
            'best_score': best_score,
            'mode_scores': mode_scores,
            'all_results': loaded_results
        }
    
    def run_comparison_test(self, duration: int = 300):
        """
        Run comparison test for 3 focus modes:
        1. Auto Focus mode (Camera mode Auto with default picamera2 parameter)
        2. Continuous Focus (with grid search)
        3. Manual with Adaptive Focus (with grid search)
        
        Each mode result is saved immediately to prevent data loss.
        
        Args:
            duration: Test duration for each mode/combination in seconds
        """
        if not self.test_framework:
            logger.error("Test framework not initialized.")
            return None
        
        # Generate session ID for this test run
        test_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"\n{'='*80}")
        logger.info("Running Comparison Test for 3 Focus Modes")
        logger.info(f"Test Session ID: {test_session_id}")
        logger.info(f"Duration per test: {duration}s")
        logger.info(f"{'='*80}")
        
        results = {}
        saved_files = {}  # Track saved files for each mode
        
        # 1. Auto Focus Mode (default picamera2 parameters)
        logger.info(f"\n{'='*60}")
        logger.info("1. Auto Focus Mode (Default picamera2 parameters)")
        logger.info(f"{'='*60}")
        
        if not self.running:
            logger.info("Test interrupted by user.")
            return None
        
        # Apply default auto configuration
        if not self._apply_default_config():
            logger.error("Failed to apply default auto config")
        else:
            self._maybe_run_health_check(label="Auto mode pre-check")
            # Use auto mode with default settings for testing
            result = self.test_framework.run_test("auto", duration, trigger_interval=30.0, poor_threshold=400)
            if result:
                results['auto_focus_default'] = result
                # Save immediately to prevent data loss
                saved_file = self._save_mode_result('auto_focus_default', result, test_session_id)
                saved_files['auto_focus_default'] = saved_file
        
        # Wait between modes
        logger.info("Waiting 10 seconds before next mode...")
        time.sleep(10)
        
        # 2. Continuous Focus with Grid Search
        if not self.running:
            logger.info("Test interrupted by user.")
            return None
        
        continuous_results = self._run_continuous_grid_search(duration)
        if continuous_results:
            results['continuous_grid_search'] = continuous_results
            # Store best result separately for comparison
            if continuous_results.get('best_result'):
                results['continuous_best'] = continuous_results['best_result']['result']
                # Save immediately to prevent data loss
                saved_file = self._save_mode_result('continuous_best', continuous_results['best_result']['result'], test_session_id)
                saved_files['continuous_best'] = saved_file
            # Also save full grid search results
            saved_file = self._save_mode_result('continuous_grid_search', continuous_results, test_session_id)
            saved_files['continuous_grid_search'] = saved_file
        
        # Wait between modes
        logger.info("Waiting 10 seconds before next mode...")
        time.sleep(10)
        
        # 3. Manual with Adaptive Focus with Grid Search
        if not self.running:
            logger.info("Test interrupted by user.")
            return None
        
        manual_adaptive_results = self._run_manual_adaptive_grid_search(duration)
        if manual_adaptive_results:
            results['manual_adaptive_grid_search'] = manual_adaptive_results
            # Store best result separately for comparison
            if manual_adaptive_results.get('best_result'):
                results['manual_adaptive_best'] = manual_adaptive_results['best_result']['result']
                # Save immediately to prevent data loss
                saved_file = self._save_mode_result('manual_adaptive_best', manual_adaptive_results['best_result']['result'], test_session_id)
                saved_files['manual_adaptive_best'] = saved_file
            # Also save full grid search results
            saved_file = self._save_mode_result('manual_adaptive_grid_search', manual_adaptive_results, test_session_id)
            saved_files['manual_adaptive_grid_search'] = saved_file
        
        # Compare results (can load from files if needed)
        if results:
            logger.info(f"\n{'='*80}")
            logger.info("Comparing Results...")
            logger.info(f"{'='*80}")
            
            # Prepare results for comparison
            comparison_results = {
                'auto_focus_default': results.get('auto_focus_default'),
                'continuous_best': results.get('continuous_best'),
                'manual_adaptive_best': results.get('manual_adaptive_best')
            }
            
            # Find best overall mode
            best_mode = None
            best_score = -1.0
            mode_scores = {}
            
            for mode_name, result in comparison_results.items():
                if not result:
                    continue
                
                # Calculate overall score
                focus_mean = result.get('focus_quality', {}).get('mean', 0) if result.get('focus_quality') else 0
                detection_rate = result.get('detection_metrics', {}).get('detection_rate', 0) if result.get('detection_metrics') else 0
                
                # For adaptive mode, include adaptive quality
                if 'adaptive_stats' in result:
                    adaptive_quality = result.get('adaptive_stats', {}).get('best_quality', 0)
                    score = (focus_mean / 1000.0 * 0.4) + (detection_rate * 0.3) + (adaptive_quality * 0.3)
                else:
                    score = (focus_mean / 1000.0 * 0.6) + (detection_rate * 0.4)
                
                mode_scores[mode_name] = {
                    'score': score,
                    'focus_mean': focus_mean,
                    'detection_rate': detection_rate
                }
                
                if score > best_score:
                    best_score = score
                    best_mode = mode_name
            
            # Display comparison
            logger.info("\n" + "="*80)
            logger.info("COMPARISON RESULTS")
            logger.info("="*80)
            
            for mode_name, score_data in sorted(mode_scores.items(), key=lambda x: x[1]['score'], reverse=True):
                logger.info(f"\n{mode_name}:")
                logger.info(f"  Overall Score: {score_data['score']:.3f}")
                logger.info(f"  Focus Mean: {score_data['focus_mean']:.1f}")
                logger.info(f"  Detection Rate: {score_data['detection_rate']:.3f}")
            
            logger.info(f"\n{'='*80}")
            logger.info(f"BEST MODE: {best_mode}")
            logger.info(f"BEST SCORE: {best_score:.3f}")
            logger.info(f"{'='*80}")
            
            # Store comparison in test framework for export
            if self.test_framework:
                # Add results to framework for export
                for mode_name, result in comparison_results.items():
                    if result:
                        result['mode'] = mode_name
                        self.test_framework.results.append(result)
            
            comparison = {
                'timestamp': datetime.now().isoformat(),
                'test_session_id': test_session_id,
                'best_mode': best_mode,
                'best_score': best_score,
                'mode_scores': mode_scores,
                'all_results': results,
                'saved_files': saved_files  # Track where each mode was saved
            }
            
            # Save comparison summary
            try:
                import json
                from pathlib import Path
                project_root = Path(__file__).resolve().parent.parent.parent.parent
                results_dir = project_root / 'edge' / 'tests' / 'results'
                results_dir.mkdir(parents=True, exist_ok=True)
                comparison_path = results_dir / f"{test_session_id}_comparison_summary.json"
                
                # Convert numpy types
                def convert_numpy(obj):
                    import numpy as np
                    if isinstance(obj, np.integer):
                        return int(obj)
                    elif isinstance(obj, np.floating):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    elif isinstance(obj, dict):
                        return {key: convert_numpy(value) for key, value in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_numpy(item) for item in obj]
                    return obj
                
                comparison_export = convert_numpy(comparison)
                
                with open(comparison_path, 'w') as f:
                    json.dump(comparison_export, f, indent=2, default=str)
                
                logger.info(f"\n✅ Comparison summary saved to: {comparison_path}")
                print(f"🔧 Comparison summary saved to: {comparison_path}\n")
                
            except Exception as e:
                logger.error(f"Failed to save comparison summary: {e}")
                # Try fallback location
                try:
                    import os
                    home_dir = os.path.expanduser("~")
                    fallback_dir = Path(home_dir) / 'aicamera_test_results'
                    fallback_dir.mkdir(parents=True, exist_ok=True)
                    fallback_path = fallback_dir / f"{test_session_id}_comparison_summary.json"
                    with open(fallback_path, 'w') as f:
                        json.dump(comparison_export, f, indent=2, default=str)
                    logger.info(f"Comparison summary saved to fallback: {fallback_path}")
                except Exception as e2:
                    logger.error(f"Failed to save comparison summary to fallback: {e2}")
            
            return comparison
        
        return None
    
    def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up...")
        
        # Stop adaptive controller if running
        if self.adaptive_controller:
            try:
                # Reset adaptive controller state
                self.adaptive_controller = None
            except Exception as e:
                logger.debug(f"Error cleaning up adaptive controller: {e}")
        
        # Stop camera properly with error handling
        if self.camera_handler:
            try:
                logger.info("Stopping camera...")
                
                # Stop streaming first (with timeout protection)
                try:
                    if hasattr(self.camera_handler, 'streaming') and self.camera_handler.streaming:
                        # Use try-except to prevent segmentation fault
                        try:
                            self.camera_handler.stop_camera()
                            logger.info("Camera stopped.")
                        except (AttributeError, RuntimeError, OSError) as stop_error:
                            logger.warning(f"Error stopping camera stream: {stop_error}")
                            # Force stop by setting streaming flag
                            try:
                                self.camera_handler.streaming = False
                            except:
                                pass
                except Exception as e:
                    logger.warning(f"Error accessing camera streaming state: {e}")
                
                # Wait for camera to fully release
                time.sleep(1.5)
                
                # Close camera to ensure complete release (with extra protection)
                try:
                    if hasattr(self.camera_handler, 'initialized') and self.camera_handler.initialized:
                        # Only close if picam2 exists and is valid
                        if hasattr(self.camera_handler, 'picam2') and self.camera_handler.picam2:
                            try:
                                # Check if picam2 is still valid before closing
                                picam2 = self.camera_handler.picam2
                                if picam2:
                                    self.camera_handler.close_camera()
                                    logger.info("Camera closed.")
                            except (AttributeError, RuntimeError, OSError) as close_error:
                                logger.warning(f"Error closing camera: {close_error}")
                                # Try to release resources manually
                                try:
                                    self.camera_handler.picam2 = None
                                    self.camera_handler.initialized = False
                                    self.camera_handler.streaming = False
                                except:
                                    pass
                except Exception as e:
                    logger.warning(f"Error in camera close process: {e}")
                
                # Final cleanup - clear references
                try:
                    self.camera_handler = None
                except:
                    pass
                
            except Exception as e:
                logger.warning(f"Error in camera cleanup: {e}")
                # Force cleanup on error
                try:
                    self.camera_handler = None
                except:
                    pass
        
        # Wait a bit before starting service to ensure camera is fully released
        logger.info("Waiting before restarting service...")
        time.sleep(2)
        
        # Restart main service (with delay to ensure camera is fully released)
        if self.service_was_running:
            logger.info("Waiting additional time before restarting service...")
            time.sleep(1)  # Additional wait
            logger.info("Restarting main service...")
            try:
                self._start_service()
            except Exception as e:
                logger.error(f"Failed to restart service: {e}")
        else:
            logger.info("Service was not running before test, not restarting.")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Test different focus modes for AI Camera',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test continuous mode for 5 minutes
  python edge/src/tools/test_focus_modes.py --mode continuous --duration 300
  
  # Test auto mode with custom parameters
  python edge/src/tools/test_focus_modes.py --mode auto --duration 300 --trigger-interval 30
  
  # Test all modes and compare
  python edge/src/tools/test_focus_modes.py --compare-all --duration 300
  
  # Test manual mode with specific distance
  python edge/src/tools/test_focus_modes.py --mode manual --duration 300 --distance 3.0
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['auto', 'continuous', 'manual', 'hybrid', 'default', 'adaptive'],
        help='Focus mode to test (default: all auto, adaptive: auto-optimize)'
    )
    
    parser.add_argument(
        '--compare-all',
        action='store_true',
        help='Test all modes and compare results'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=300,
        help='Test duration in seconds (default: 300)'
    )
    
    # Auto mode parameters
    parser.add_argument(
        '--trigger-interval',
        type=float,
        default=30.0,
        help='Auto mode: Trigger interval in seconds (default: 30.0)'
    )
    
    parser.add_argument(
        '--poor-threshold',
        type=int,
        default=400,
        help='Auto mode: Poor focus threshold (default: 400)'
    )
    
    # Continuous mode parameters
    parser.add_argument(
        '--speed',
        type=int,
        choices=[0, 1],
        default=0,
        help='Continuous mode: Focus speed (0=Normal, 1=Fast, default: 0)'
    )
    
    parser.add_argument(
        '--metering',
        type=int,
        choices=[0, 1],
        default=1,
        help='Continuous mode: Metering mode (0=Auto, 1=Center, default: 1)'
    )
    
    # Manual mode parameters
    parser.add_argument(
        '--distance',
        type=float,
        default=3.0,
        help='Manual mode: Focus distance in meters (default: 3.0)'
    )
    
    parser.add_argument(
        '--unlock-interval',
        type=float,
        default=60.0,
        help='Manual mode: Unlock interval in seconds (default: 60.0)'
    )
    
    # Hybrid mode parameters
    parser.add_argument(
        '--base-distance',
        type=float,
        default=3.0,
        help='Hybrid mode: Base distance in meters (default: 3.0)'
    )
    
    parser.add_argument(
        '--continuous-range',
        type=float,
        default=2.0,
        help='Hybrid mode: Continuous range in meters (default: 2.0)'
    )
    
    # Manual mode parameters (for manual config mode)
    parser.add_argument(
        '--af-mode',
        type=int,
        choices=[0, 1, 2],
        default=2,
        help='Manual mode: Autofocus mode (0=Manual, 1=Auto, 2=Continuous, default: 2)'
    )
    
    parser.add_argument(
        '--brightness',
        type=float,
        default=0.0,
        help='Manual mode: Brightness (-1.0 to 1.0, default: 0.0)'
    )
    
    parser.add_argument(
        '--contrast',
        type=float,
        default=1.0,
        help='Manual mode: Contrast (0.0 to 2.0, default: 1.0)'
    )
    
    parser.add_argument(
        '--saturation',
        type=float,
        default=1.0,
        help='Manual mode: Saturation (0.0 to 2.0, default: 1.0)'
    )
    
    parser.add_argument(
        '--sharpness',
        type=float,
        default=1.0,
        help='Manual mode: Sharpness (0.0 to 4.0, default: 1.0)'
    )
    
    parser.add_argument(
        '--exposure-time',
        type=int,
        help='Manual mode: Exposure time in microseconds (disables auto exposure)'
    )
    
    parser.add_argument(
        '--analogue-gain',
        type=float,
        help='Manual mode: Analogue gain (disables auto exposure)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Output file path for results (optional)'
    )
    
    parser.add_argument(
        '--skip-health-check',
        action='store_true',
        help='Skip pre-test focus health checks'
    )
    
    parser.add_argument(
        '--health-check-duration',
        type=float,
        default=3.0,
        help='Duration (seconds) for focus health check sampling (default: 3.0)'
    )
    
    parser.add_argument(
        '--health-check-variation',
        type=float,
        default=50.0,
        help='Required FocusFoM variation during health check (default: 50)'
    )
    
    parser.add_argument(
        '--health-check-samples',
        type=int,
        default=20,
        help='Minimum valid FocusFoM samples needed during health check (default: 20)'
    )
    
    parser.add_argument(
        '--service-name',
        type=str,
        default='aicamera_lpr',
        help='Systemd service name (default: aicamera_lpr)'
    )
    
    parser.add_argument(
        '--skip-service-control',
        action='store_true',
        help='Skip stopping/starting service (use with caution - camera may be busy)'
    )
    
    parser.add_argument(
        '--load-session',
        type=str,
        help='Load and compare results from a previous test session (session ID format: YYYYMMDD_HHMMSS)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.compare_all and not args.mode:
        parser.error("Either --mode or --compare-all must be specified")
    
    # Initialize test runner
    runner = FocusTestRunner(service_name=args.service_name)
    runner.health_check_enabled = not args.skip_health_check
    runner.health_check_duration = args.health_check_duration
    runner.health_check_variation = args.health_check_variation
    runner.health_check_samples = args.health_check_samples
    
    # Skip service control if requested
    if args.skip_service_control:
        logger.warning("Skipping service control - camera may be busy if service is running!")
        print(f"🔧 Skipping service control - camera may be busy if service is running!\n")
        runner.service_was_running = False  # Don't restart if we didn't stop
    
    try:
        # Stop main service first (camera doesn't support multi-access)
        if not args.skip_service_control:
            if not runner._stop_service():
                logger.error("Failed to stop main service. Use --skip-service-control if service is not running.")
                print(f"🔧 Failed to stop main service. Use --skip-service-control if service is not running.\n")
                sys.exit(1)
            time.sleep(2)  # Wait for camera to be released
        
        # Initialize services (service should already be stopped if not skipped)
        if not runner.initialize_services(skip_service_control=args.skip_service_control):
            logger.error("Failed to initialize services. Exiting.")
            print(f"🔧 Failed to initialize services. Exiting.\n")
            sys.exit(1)
        
        # Run test
        if args.load_session:
            # Load and compare results from previous session
            logger.info(f"Loading results from session: {args.load_session}")
            loaded_results = runner._load_mode_results(args.load_session)
            
            if loaded_results:
                logger.info(f"Loaded {len(loaded_results)} mode results")
                comparison = runner._compare_loaded_results(loaded_results)
                
                # Display comparison
                logger.info("\n" + "="*80)
                logger.info("COMPARISON RESULTS (from loaded files)")
                logger.info("="*80)
                
                for mode_name, score_data in sorted(comparison.get('mode_scores', {}).items(), 
                                                    key=lambda x: x[1]['score'], reverse=True):
                    logger.info(f"\n{mode_name}:")
                    logger.info(f"  Overall Score: {score_data['score']:.3f}")
                    logger.info(f"  Focus Mean: {score_data['focus_mean']:.1f}")
                    logger.info(f"  Detection Rate: {score_data['detection_rate']:.3f}")
                
                logger.info(f"\n{'='*80}")
                logger.info(f"BEST MODE: {comparison.get('best_mode', 'N/A')}")
                logger.info(f"BEST SCORE: {comparison.get('best_score', 0):.3f}")
                logger.info(f"{'='*80}")
                
                # Save comparison summary
                import json
                from pathlib import Path
                project_root = Path(__file__).resolve().parent.parent.parent.parent
                results_dir = project_root / 'edge' / 'tests' / 'results'
                results_dir.mkdir(parents=True, exist_ok=True)
                comparison_path = results_dir / f"{args.load_session}_comparison_summary.json"
                
                def convert_numpy(obj):
                    import numpy as np
                    if isinstance(obj, np.integer):
                        return int(obj)
                    elif isinstance(obj, np.floating):
                        return float(obj)
                    elif isinstance(obj, np.ndarray):
                        return obj.tolist()
                    elif isinstance(obj, dict):
                        return {key: convert_numpy(value) for key, value in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_numpy(item) for item in obj]
                    return obj
                
                comparison_export = convert_numpy(comparison)
                with open(comparison_path, 'w') as f:
                    json.dump(comparison_export, f, indent=2, default=str)
                
                logger.info(f"\n✅ Comparison summary saved to: {comparison_path}")
            else:
                logger.error(f"No results found for session: {args.load_session}")
                sys.exit(1)
        elif args.compare_all:
            # Run comparison test
            comparison = runner.run_comparison_test(duration=args.duration)
            
            if comparison and args.output:
                runner.test_framework.export_results(args.output)
        else:
            # Run single mode test
            mode_params = {}
            
            if args.mode == 'auto':
                mode_params = {
                    'trigger_interval': args.trigger_interval,
                    'poor_threshold': args.poor_threshold
                }
            elif args.mode == 'continuous':
                mode_params = {
                    'speed': args.speed,
                    'metering': args.metering,
                    'range_mode': 0
                }
            elif args.mode == 'manual':
                # Manual mode can be either manual focus mode or manual config mode
                # Check if manual config parameters are provided
                if args.af_mode or args.brightness != 0.0 or args.contrast != 1.0 or \
                   args.saturation != 1.0 or args.sharpness != 1.0 or args.exposure_time or args.analogue_gain:
                    # Manual config mode
                    mode_params = {
                        'af_mode': args.af_mode,
                        'brightness': args.brightness,
                        'contrast': args.contrast,
                        'saturation': args.saturation,
                        'sharpness': args.sharpness,
                        'exposure_time': args.exposure_time,
                        'analogue_gain': args.analogue_gain
                    }
                else:
                    # Manual focus mode (legacy)
                    mode_params = {
                        'distance_m': args.distance,
                        'unlock_interval': args.unlock_interval
                    }
            elif args.mode == 'hybrid':
                mode_params = {
                    'base_distance': args.base_distance,
                    'continuous_range': args.continuous_range
                }
            elif args.mode == 'default':
                mode_params = {}  # Use default config
            elif args.mode == 'adaptive':
                mode_params = {}  # Adaptive mode doesn't need params
            
            result = runner.run_single_test(
                args.mode,
                args.duration,
                **mode_params
            )
            
            if result and args.output:
                try:
                    if hasattr(runner, 'test_framework') and runner.test_framework:
                        runner.test_framework.export_results(args.output)
                    elif hasattr(runner, 'adaptive_controller') and runner.adaptive_controller:
                        # For adaptive mode, results are already in result dict
                        import json
                        from pathlib import Path
                        output_path = Path(args.output)
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'w') as f:
                            json.dump(result, f, indent=2, default=str)
                        logger.info(f"Results exported to: {output_path}")
                except Exception as e:
                    logger.error(f"Failed to export results to {args.output}: {e}")
                    # Try default location
                    try:
                        if hasattr(runner, 'test_framework') and runner.test_framework:
                            output_file = runner.test_framework.export_results()
                            logger.info(f"Results exported to default location: {output_file}")
                    except Exception as e2:
                        logger.error(f"Failed to export results: {e2}")
        
        logger.info("\nTest completed successfully!")
        print(f"🔧 Test completed successfully!\n")
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user.")
        print(f"🔧 Test interrupted by user.\n")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"🔧 Test failed: {e}\n")
        sys.exit(1)
    finally:
        runner.cleanup()


if __name__ == '__main__':
    main()

