#!/usr/bin/env python3
"""
Comprehensive Camera Handler Method Testing Script

This script tests all public methods of the CameraHandler class
with sample inputs and outputs to verify proper functionality.
"""

import sys
import os
import time
import traceback
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'edge'))

def test_camera_handler_methods():
    """Test all CameraHandler methods systematically."""
    
    print("🔍 === CAMERA HANDLER METHOD TESTING ===")
    print("=" * 50)
    
    try:
        # Import camera handler
        from edge.src.components.camera_handler import CameraHandler, check_camera_availability
        print("✅ Successfully imported CameraHandler")
        
        # Test 1: Camera Availability Check
        print("\n📋 Test 1: Camera Availability Check")
        print("-" * 30)
        try:
            availability = check_camera_availability()
            print(f"✅ Camera availability: {availability}")
            print(f"   - Hardware available: {availability.get('hardware_available', False)}")
            print(f"   - Software available: {availability.get('software_available', False)}")
            print(f"   - Camera ready: {availability.get('camera_ready', False)}")
        except Exception as e:
            print(f"❌ Camera availability check failed: {e}")
        
        # Test 2: CameraHandler Singleton Creation
        print("\n📋 Test 2: CameraHandler Singleton Creation")
        print("-" * 30)
        try:
            camera_handler = CameraHandler()
            print(f"✅ CameraHandler instance created: {type(camera_handler)}")
            print(f"   - Initialized: {camera_handler.initialized}")
            print(f"   - Streaming: {camera_handler.streaming}")
        except Exception as e:
            print(f"❌ CameraHandler creation failed: {e}")
            return
        
        # Test 3: Camera Status Methods
        print("\n📋 Test 3: Camera Status Methods")
        print("-" * 30)
        
        # Test get_camera_status()
        try:
            status = camera_handler.get_camera_status()
            print(f"✅ get_camera_status(): {type(status)}")
            print(f"   - Keys: {list(status.keys())}")
            print(f"   - Initialized: {status.get('initialized', 'N/A')}")
            print(f"   - Streaming: {status.get('streaming', 'N/A')}")
        except Exception as e:
            print(f"❌ get_camera_status() failed: {e}")
        
        # Test get_status()
        try:
            status = camera_handler.get_status()
            print(f"✅ get_status(): {type(status)}")
            print(f"   - Keys: {list(status.keys())}")
            print(f"   - Initialized: {status.get('initialized', 'N/A')}")
            print(f"   - Frame count: {status.get('frame_count', 'N/A')}")
        except Exception as e:
            print(f"❌ get_status() failed: {e}")
        
        # Test 4: Frame Buffer Methods
        print("\n📋 Test 4: Frame Buffer Methods")
        print("-" * 30)
        
        # Test is_frame_buffer_ready()
        try:
            buffer_ready = camera_handler.is_frame_buffer_ready()
            print(f"✅ is_frame_buffer_ready(): {buffer_ready}")
        except Exception as e:
            print(f"❌ is_frame_buffer_ready() failed: {e}")
        
        # Test get_main_frame()
        try:
            main_frame = camera_handler.get_main_frame()
            if main_frame is not None:
                print(f"✅ get_main_frame(): {type(main_frame)}, shape: {main_frame.shape}")
            else:
                print(f"ℹ️ get_main_frame(): None (no frame available)")
        except Exception as e:
            print(f"❌ get_main_frame() failed: {e}")
        
        # Test get_lores_frame()
        try:
            lores_frame = camera_handler.get_lores_frame()
            if lores_frame is not None:
                print(f"✅ get_lores_frame(): {type(lores_frame)}, shape: {lores_frame.shape}")
            else:
                print(f"ℹ️ get_lores_frame(): None (no frame available)")
        except Exception as e:
            print(f"❌ get_lores_frame() failed: {e}")
        
        # Test get_cached_metadata()
        try:
            metadata = camera_handler.get_cached_metadata()
            print(f"✅ get_cached_metadata(): {type(metadata)}")
            print(f"   - Keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"❌ get_cached_metadata() failed: {e}")
        
        # Test 5: Camera Control Methods
        print("\n📋 Test 5: Camera Control Methods")
        print("-" * 30)
        
        # Test initialize_camera()
        try:
            init_result = camera_handler.initialize_camera()
            print(f"✅ initialize_camera(): {init_result}")
            print(f"   - Camera initialized: {camera_handler.initialized}")
        except Exception as e:
            print(f"❌ initialize_camera() failed: {e}")
        
        # Test start_camera() (only if initialized)
        if camera_handler.initialized:
            try:
                start_result = camera_handler.start_camera()
                print(f"✅ start_camera(): {start_result}")
                print(f"   - Camera streaming: {camera_handler.streaming}")
            except Exception as e:
                print(f"❌ start_camera() failed: {e}")
        
        # Test 6: Frame Capture Methods (if streaming)
        if camera_handler.streaming:
            print("\n📋 Test 6: Frame Capture Methods")
            print("-" * 30)
            
            # Test capture_frame()
            try:
                frame_data = camera_handler.capture_frame()
                if frame_data is not None:
                    print(f"✅ capture_frame(): {type(frame_data)}")
                    print(f"   - Keys: {list(frame_data.keys())}")
                    print(f"   - Frame shape: {frame_data.get('size', 'N/A')}")
                    print(f"   - Format: {frame_data.get('format', 'N/A')}")
                else:
                    print(f"ℹ️ capture_frame(): None (no frame available)")
            except Exception as e:
                print(f"❌ capture_frame() failed: {e}")
            
            # Test capture_lores_frame()
            try:
                lores_data = camera_handler.capture_lores_frame()
                if lores_data is not None:
                    print(f"✅ capture_lores_frame(): {type(lores_data)}")
                    print(f"   - Keys: {list(lores_data.keys())}")
                else:
                    print(f"ℹ️ capture_lores_frame(): None (no frame available)")
            except Exception as e:
                print(f"❌ capture_lores_frame() failed: {e}")
        
        # Test 7: Configuration Methods
        print("\n📋 Test 7: Configuration Methods")
        print("-" * 30)
        
        # Test get_configuration()
        try:
            config = camera_handler.get_configuration()
            print(f"✅ get_configuration(): {type(config)}")
            print(f"   - Keys: {list(config.keys()) if isinstance(config, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"❌ get_configuration() failed: {e}")
        
        # Test get_controls()
        try:
            controls = camera_handler.get_controls()
            print(f"✅ get_controls(): {type(controls)}")
            print(f"   - Keys: {list(controls.keys()) if isinstance(controls, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"❌ get_controls() failed: {e}")
        
        # Test 8: Diagnostic Methods
        print("\n📋 Test 8: Diagnostic Methods")
        print("-" * 30)
        
        # Test diagnose_latency_issues()
        try:
            diagnosis = camera_handler.diagnose_latency_issues()
            print(f"✅ diagnose_latency_issues(): {type(diagnosis)}")
            print(f"   - Keys: {list(diagnosis.keys()) if isinstance(diagnosis, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"❌ diagnose_latency_issues() failed: {e}")
        
        # Test get_buffer_status()
        try:
            buffer_status = camera_handler.get_buffer_status()
            print(f"✅ get_buffer_status(): {type(buffer_status)}")
            print(f"   - Keys: {list(buffer_status.keys()) if isinstance(buffer_status, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"❌ get_buffer_status() failed: {e}")
        
        # Test 9: Cleanup
        print("\n📋 Test 9: Cleanup Methods")
        print("-" * 30)
        
        # Test stop_camera()
        if camera_handler.streaming:
            try:
                stop_result = camera_handler.stop_camera()
                print(f"✅ stop_camera(): {stop_result}")
                print(f"   - Camera streaming: {camera_handler.streaming}")
            except Exception as e:
                print(f"❌ stop_camera() failed: {e}")
        
        # Test close_camera()
        try:
            close_result = camera_handler.close_camera()
            print(f"✅ close_camera(): {close_result}")
        except Exception as e:
            print(f"❌ close_camera() failed: {e}")
        
        print("\n🎉 === CAMERA HANDLER TESTING COMPLETED ===")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Critical error in camera handler testing: {e}")
        print(f"   Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_camera_handler_methods()
