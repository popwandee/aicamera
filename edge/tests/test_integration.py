#!/usr/bin/env python3
"""
Integration test to verify camera handler, detection processor, and health module compatibility.
"""

import sys
import os
import time
import requests
import json

# Add the edge/src directory to the path
sys.path.insert(0, '/home/camuser/aicamera/edge/src')

def test_camera_detection_integration():
    """Test camera handler and detection processor integration."""
    print("🔍 Testing Camera-Detection Integration...")
    
    try:
        from core.dependency_container import get_service
        
        # Get camera manager
        camera_manager = get_service('camera_manager')
        if not camera_manager:
            print("❌ Camera manager not available")
            return False
        
        print("✅ Camera manager retrieved")
        
        # Get detection manager
        detection_manager = get_service('detection_manager')
        if not detection_manager:
            print("❌ Detection manager not available")
            return False
        
        print("✅ Detection manager retrieved")
        
        # Test camera manager status
        print("📊 Testing camera manager status...")
        camera_status = camera_manager.get_status()
        print(f"📊 Camera initialized: {camera_status.get('initialized', False)}")
        print(f"📊 Camera streaming: {camera_status.get('streaming', False)}")
        print(f"📊 Frame count: {camera_status.get('frame_count', 0)}")
        
        # Test detection manager status
        print("📊 Testing detection manager status...")
        detection_status = detection_manager.get_status()
        print(f"📊 Detection service running: {detection_status.get('service_running', False)}")
        print(f"📊 Thread alive: {detection_status.get('thread_alive', False)}")
        
        # Test frame capture from camera manager
        print("📸 Testing frame capture...")
        frame = camera_manager.capture_main_frame()
        if frame is not None:
            print(f"✅ Frame captured successfully, shape: {frame.shape}")
        else:
            print("❌ Frame capture failed")
            return False
        
        # Test detection processing
        print("🎯 Testing detection processing...")
        result = detection_manager.process_frame_from_camera(camera_manager)
        if result is not None:
            print("✅ Detection processing successful")
            print(f"📊 Detection result keys: {list(result.keys())}")
        else:
            print("❌ Detection processing failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_health_module_integration():
    """Test health module integration."""
    print("\n🔍 Testing Health Module Integration...")
    
    try:
        from core.dependency_container import get_service
        
        # Get health service
        health_service = get_service('health_service')
        if not health_service:
            print("❌ Health service not available")
            return False
        
        print("✅ Health service retrieved")
        
        # Test health service status
        print("📊 Testing health service status...")
        health_status = health_service.get_status()
        print(f"📊 Health service initialized: {health_status.get('initialized', False)}")
        print(f"📊 Health monitoring: {health_status.get('monitoring', False)}")
        
        # Test system health
        print("🏥 Testing system health...")
        system_health = health_service.get_system_health()
        if system_health.get('success', False):
            print("✅ System health check successful")
            print(f"📊 Overall status: {system_health.get('data', {}).get('overall_status', 'unknown')}")
        else:
            print("❌ System health check failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Health integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test API endpoints for integration."""
    print("\n🔍 Testing API Endpoints...")
    
    base_url = "http://localhost"
    
    # Test camera status endpoint
    try:
        print("📊 Testing camera status endpoint...")
        response = requests.get(f"{base_url}/api/camera/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Camera status: {data.get('initialized', False)}")
            print(f"📊 Streaming: {data.get('streaming', False)}")
        else:
            print(f"❌ Camera status endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Camera status test failed: {e}")
        return False
    
    # Test detection status endpoint
    try:
        print("📊 Testing detection status endpoint...")
        response = requests.get(f"{base_url}/api/detection/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Detection service running: {data.get('service_running', False)}")
        else:
            print(f"❌ Detection status endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Detection status test failed: {e}")
        return False
    
    # Test health endpoint
    try:
        print("🏥 Testing health endpoint...")
        response = requests.get(f"{base_url}/api/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health endpoint working: {data.get('success', False)}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False
    
    return True

def main():
    """Run all integration tests."""
    print("🚀 Starting Integration Tests")
    print("=" * 50)
    
    # Test camera-detection integration
    camera_detection_ok = test_camera_detection_integration()
    
    # Test health module integration
    health_ok = test_health_module_integration()
    
    # Test API endpoints
    api_ok = test_api_endpoints()
    
    print("\n" + "=" * 50)
    print("📊 Integration Test Results:")
    print(f"📊 Camera-Detection Integration: {'✅ PASS' if camera_detection_ok else '❌ FAIL'}")
    print(f"📊 Health Module Integration: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"📊 API Endpoints: {'✅ PASS' if api_ok else '❌ FAIL'}")
    
    if camera_detection_ok and health_ok and api_ok:
        print("🎉 All integration tests passed!")
        return True
    else:
        print("❌ Some integration tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
