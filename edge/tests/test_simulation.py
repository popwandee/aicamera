#!/usr/bin/env python3
"""
Test script for simulation environment
"""

import sqlite3
import os
import sys
from datetime import datetime

# Add the virtual environment to Python path
venv_path = os.path.join(os.path.dirname(__file__), 'venv_simulation', 'lib', 'python3.12', 'site-packages')
if os.path.exists(venv_path):
    sys.path.insert(0, venv_path)

def test_database_connection():
    """Test database connection and basic operations"""
    print("🧪 Testing database connection...")
    
    db_path = "edge/db/simulation_data.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Test health monitoring table
        cursor.execute("SELECT COUNT(*) FROM health_monitoring")
        health_count = cursor.fetchone()[0]
        print(f"✅ Health monitoring records: {health_count}")
        
        # Test detection results table
        cursor.execute("SELECT COUNT(*) FROM detection_results")
        detection_count = cursor.fetchone()[0]
        print(f"✅ Detection results records: {detection_count}")
        
        # Test system events table
        cursor.execute("SELECT COUNT(*) FROM system_events")
        events_count = cursor.fetchone()[0]
        print(f"✅ System events records: {events_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_imports():
    """Test that all required modules can be imported"""
    print("🧪 Testing module imports...")
    
    modules = [
        'flask',
        'flask_socketio',
        'sqlalchemy',
        'pandas',
        'numpy',
        'psutil',
        'requests'
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module} imported successfully")
        except ImportError as e:
            print(f"❌ {module} import failed: {e}")
            return False
    
    return True

def main():
    """Run all tests"""
    print("🧪 Running simulation environment tests...")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Module Imports", test_imports)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        if test_func():
            passed += 1
            print(f"✅ {test_name} passed")
        else:
            print(f"❌ {test_name} failed")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Simulation environment is ready.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the installation.")
        return False

if __name__ == "__main__":
    main()
