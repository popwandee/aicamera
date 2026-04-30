u#!/usr/bin/env python3
"""
Simple test of camera functionality using the running service.
"""

import requests
import json
import time

def test_camera_via_api():
    """Test camera functionality via API endpoints."""
    print("🔍 Testing Camera via API...")
    
    base_url = "http://localhost"
    
    # Test basic connectivity
    try:
        print("🌐 Testing basic connectivity...")
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"📊 Root endpoint status: {response.status_code}")
    except Exception as e:
        print(f"❌ Basic connectivity failed: {e}")
        return False
    
    # Test camera status endpoint
    try:
        print("📊 Testing camera status endpoint...")
        response = requests.get(f"{base_url}/api/camera/status", timeout=10)
        print(f"📊 Camera status response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Camera initialized: {data.get('initialized', False)}")
            print(f"📊 Camera streaming: {data.get('streaming', False)}")
            print(f"📊 Frame count: {data.get('frame_count', 0)}")
            print(f"📊 Average FPS: {data.get('average_fps', 0)}")
            print("✅ Camera status endpoint working")
        else:
            print(f"❌ Camera status endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Camera status test failed: {e}")
        return False
    
    # Test camera configuration endpoint
    try:
        print("⚙️ Testing camera configuration endpoint...")
        response = requests.get(f"{base_url}/api/camera/config", timeout=10)
        print(f"📊 Camera config response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Config keys: {list(data.keys())}")
            print("✅ Camera configuration endpoint working")
        else:
            print(f"❌ Camera configuration endpoint failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Camera configuration test failed: {e}")
    
    # Test frame capture endpoint
    try:
        print("📸 Testing frame capture endpoint...")
        response = requests.get(f"{base_url}/api/camera/capture", timeout=15)
        print(f"📊 Frame capture response: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Frame capture endpoint working")
        else:
            print(f"❌ Frame capture endpoint failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Frame capture test failed: {e}")
    
    return True

def test_detection_via_api():
    """Test detection functionality via API endpoints."""
    print("\n🔍 Testing Detection via API...")
    
    base_url = "http://localhost"
    
    # Test detection status endpoint
    try:
        print("📊 Testing detection status endpoint...")
        response = requests.get(f"{base_url}/api/detection/status", timeout=10)
        print(f"📊 Detection status response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Service running: {data.get('service_running', False)}")
            print(f"📊 Models loaded: {data.get('detection_processor_status', {}).get('models_loaded', False)}")
            print(f"📊 Thread alive: {data.get('thread_alive', False)}")
            print("✅ Detection status endpoint working")
        else:
            print(f"❌ Detection status endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Detection status test failed: {e}")
        return False
    
    # Test detection trigger endpoint
    try:
        print("🎯 Testing detection trigger endpoint...")
        response = requests.post(f"{base_url}/api/detection/trigger", timeout=15)
        print(f"📊 Detection trigger response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Detection success: {data.get('success', False)}")
            print("✅ Detection trigger endpoint working")
        else:
            print(f"❌ Detection trigger endpoint failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Detection trigger test failed: {e}")
    
    return True

def main():
    """Run all tests."""
    print("🚀 Starting API-based Component Tests")
    print("=" * 50)
    
    # Test camera via API
    camera_ok = test_camera_via_api()
    
    # Test detection via API
    detection_ok = test_detection_via_api()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"📊 Camera API: {'✅ PASS' if camera_ok else '❌ FAIL'}")
    print(f"📊 Detection API: {'✅ PASS' if detection_ok else '❌ FAIL'}")
    
    if camera_ok and detection_ok:
        print("🎉 All API tests passed!")
        return True
    else:
        print("❌ Some API tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
