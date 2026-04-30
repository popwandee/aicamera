#!/usr/bin/env python3
"""
Direct test of camera functionality without health module dependencies.
"""

import sys
import os
import time
import numpy as np
from datetime import datetime

# Add the edge/src directory to the path
sys.path.insert(0, '/home/camuser/aicamera/edge/src')

def test_camera_handler():
    """Test camera handler directly."""
    print("🔍 Testing Camera Handler...")
    
    try:
        from components.camera_handler import CameraHandler
        
        # Create camera handler instance
        camera_handler = CameraHandler()
        print("✅ Camera handler created successfully")
        
        # Test initialization
        print("🔧 Initializing camera...")
        init_result = camera_handler.initialize_camera()
        print(f"📊 Initialization result: {init_result}")
        
        if init_result:
            # Test camera status
            print("📊 Getting camera status...")
            status = camera_handler.get_camera_status()
            print(f"📊 Camera status: {status}")
            
            # Test starting camera
            print("🚀 Starting camera...")
            start_result = camera_handler.start_camera()
            print(f"📊 Start result: {start_result}")
            
            if start_result:
                # Wait a bit for camera to stabilize
                print("⏳ Waiting for camera to stabilize...")
                time.sleep(3)
                
                # Test frame capture
                print("📸 Testing frame capture...")
                frame_data = camera_handler.capture_frame()
                print(f"📊 Frame data type: {type(frame_data)}")
                
                if isinstance(frame_data, dict) and 'frame' in frame_data:
                    frame = frame_data['frame']
                    print(f"📊 Frame shape: {frame.shape if hasattr(frame, 'shape') else 'No shape'}")
                    print("✅ Frame capture successful")
                elif isinstance(frame_data, np.ndarray):
                    print(f"📊 Frame shape: {frame_data.shape}")
                    print("✅ Frame capture successful")
                else:
                    print(f"❌ Invalid frame data: {frame_data}")
                
                # Test frame buffer
                print("📊 Testing frame buffer...")
                buffer_ready = camera_handler.is_frame_buffer_ready()
                print(f"📊 Frame buffer ready: {buffer_ready}")
                
                # Test getting status
                print("📊 Getting detailed status...")
                detailed_status = camera_handler.get_status()
                print(f"📊 Detailed status keys: {list(detailed_status.keys())}")
                
                # Stop camera
                print("🛑 Stopping camera...")
                stop_result = camera_handler.stop_camera()
                print(f"📊 Stop result: {stop_result}")
                
                return True
            else:
                print("❌ Failed to start camera")
                return False
        else:
            print("❌ Failed to initialize camera")
            return False
            
    except Exception as e:
        print(f"❌ Camera handler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_manager():
    """Test camera manager directly."""
    print("\n🔍 Testing Camera Manager...")
    
    try:
        from components.camera_handler import CameraHandler
        from services.camera_manager import CameraManager
        
        # Create camera handler
        camera_handler = CameraHandler()
        print("✅ Camera handler created")
        
        # Create camera manager
        camera_manager = CameraManager(camera_handler)
        print("✅ Camera manager created")
        
        # Test initialization
        print("🔧 Initializing camera manager...")
        init_result = camera_manager.initialize()
        print(f"📊 Initialization result: {init_result}")
        
        if init_result:
            # Test getting status
            print("📊 Getting camera manager status...")
            status = camera_manager.get_status()
            print(f"📊 Status keys: {list(status.keys())}")
            print(f"📊 Initialized: {status.get('initialized', False)}")
            print(f"📊 Streaming: {status.get('streaming', False)}")
            
            # Test health check
            print("🏥 Testing health check...")
            health = camera_manager.health_check()
            print(f"📊 Health status: {health.get('status', 'unknown')}")
            print(f"📊 Camera initialized: {health.get('camera_initialized', False)}")
            print(f"📊 Streaming active: {health.get('streaming_active', False)}")
            
            # Test frame capture
            print("📸 Testing frame capture from manager...")
            frame = camera_manager.capture_frame()
            if frame is not None:
                print(f"📊 Captured frame shape: {frame.shape}")
                print("✅ Frame capture from manager successful")
            else:
                print("❌ Frame capture from manager failed")
            
            return True
        else:
            print("❌ Failed to initialize camera manager")
            return False
            
    except Exception as e:
        print(f"❌ Camera manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all camera tests."""
    print("🚀 Starting Camera Functionality Tests")
    print("=" * 50)
    
    # Test camera handler
    camera_handler_ok = test_camera_handler()
    
    # Test camera manager
    camera_manager_ok = test_camera_manager()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"📊 Camera Handler: {'✅ PASS' if camera_handler_ok else '❌ FAIL'}")
    print(f"📊 Camera Manager: {'✅ PASS' if camera_manager_ok else '❌ FAIL'}")
    
    if camera_handler_ok and camera_manager_ok:
        print("🎉 All camera tests passed!")
        return True
    else:
        print("❌ Some camera tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
