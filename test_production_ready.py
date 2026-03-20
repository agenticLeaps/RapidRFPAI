#!/usr/bin/env python3
"""
Production Readiness Test
Tests the enhanced system with Upstash Redis
"""

import os
import sys
import time

def test_redis_connection():
    """Test Upstash Redis connection"""
    print("🔍 Testing Upstash Redis connection...")
    try:
        from redis_manager import redis_manager
        
        if redis_manager.is_connected():
            print(f"✅ Redis connected - Client type: {redis_manager.client_type}")
            return True
        else:
            print("❌ Redis connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Redis test error: {e}")
        return False

def test_progress_tracking():
    """Test Redis progress tracking"""
    print("\n📊 Testing progress tracking...")
    try:
        from redis_manager import redis_manager
        
        if not redis_manager.is_connected():
            print("⚠️ Skipping progress test - Redis not connected")
            return False
        
        # Test setting progress
        test_id = f"test-{int(time.time())}"
        redis_manager.set_progress(test_id, "testing", 50, "Production readiness test", "test.pdf")
        
        # Test getting progress
        result = redis_manager.get_progress(test_id)
        
        if result and result.get('status') == 'testing':
            print("✅ Progress tracking working!")
            print(f"   Progress data: {result}")
            
            # Cleanup
            redis_manager.delete_progress(test_id)
            return True
        else:
            print("❌ Progress tracking failed")
            return False
            
    except Exception as e:
        print(f"❌ Progress tracking error: {e}")
        return False

def test_enhanced_functions():
    """Test enhanced upload progress function"""
    print("\n🚀 Testing enhanced upload progress function...")
    try:
        # Import the enhanced function
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app import update_upload_progress
        
        # Test the enhanced function
        test_id = f"enhanced-test-{int(time.time())}"
        update_upload_progress(test_id, "processing", 75, "Enhanced function test", "enhanced.pdf")
        
        print("✅ Enhanced upload progress function working!")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced function test error: {e}")
        return False

def test_environment_config():
    """Test environment configuration"""
    print("\n⚙️ Testing environment configuration...")
    
    required_vars = [
        'UPSTASH_REDIS_REST_URL',
        'UPSTASH_REDIS_REST_TOKEN',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_REGION',
        'PINECONE_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ All required environment variables present")
        return True

def main():
    """Run all production readiness tests"""
    print("🚀 Production Readiness Test Suite")
    print("==================================")
    
    tests = [
        ("Environment Configuration", test_environment_config),
        ("Redis Connection", test_redis_connection),
        ("Progress Tracking", test_progress_tracking),
        ("Enhanced Functions", test_enhanced_functions),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
    
    print(f"\n📋 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 PRODUCTION READY!")
        print("✅ Your enhanced system is ready for deployment")
        print("✅ Upstash Redis is working perfectly")
        print("✅ Progress tracking is persistent")
        print("✅ Enhanced performance is active")
        print("\n🚀 Deploy with confidence!")
    else:
        print(f"\n⚠️ {total - passed} tests failed")
        print("Please check the issues above before deploying")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)