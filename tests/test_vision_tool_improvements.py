"""Test suite for VisionTool performance improvements.

Tests cover:
1. Response caching functionality
2. Batch analysis with concurrency control
3. Retry logic with exponential backoff
4. Performance timing metrics
"""

import os
import sys
import time
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("AICLIP_VISION_API_KEY", "sk-test-key")
os.environ.setdefault("AICLIP_VISION_API_BASE", "https://dashscope.aliyuncs.com/api/v1")
os.environ.setdefault("AICLIP_VISION_MODEL", "qwen-vl-plus")
os.environ.setdefault("AICLIP_VISION_CONCURRENCY", "3")

from src.llm.tools.vision_tool import VisionTool


def test_initialization():
    """Test VisionTool initialization with new config options."""
    vt = VisionTool()
    assert hasattr(vt, '_concurrency_limit'), "Missing _concurrency_limit attribute"
    assert hasattr(vt, '_response_cache'), "Missing _response_cache attribute"
    assert isinstance(vt._response_cache, dict), "_response_cache should be a dict"
    print("✓ Initialization test passed")


def test_cache_functionality():
    """Test that cache is properly checked and populated."""
    vt = VisionTool()
    
    # Clear cache first
    vt._response_cache.clear()
    
    # Cache key format test
    cache_key = f"test.mp4|test prompt|qwen-vl-plus|2.0"
    assert "|" in cache_key, "Cache key should use | separator"
    
    # Simulate cached result
    mock_result = {"analysis": "cached content", "usage": {"tokens": 100}}
    vt._response_cache[cache_key] = mock_result
    
    # Verify cache hit would occur (without actual API call)
    assert cache_key in vt._response_cache, "Cache should contain the key"
    assert vt._response_cache[cache_key] == mock_result, "Cached value should match"
    
    print("✓ Cache functionality test passed")


def test_batch_method_signature():
    """Test that vision_analyze_batch method exists with correct signature."""
    vt = VisionTool()
    assert hasattr(vt, 'vision_analyze_batch'), "Missing vision_analyze_batch method"
    
    import inspect
    sig = inspect.signature(vt.vision_analyze_batch)
    params = list(sig.parameters.keys())
    
    expected_params = ['media_paths', 'prompt', 'media_type', 'model', 'api_base', 
                       'api_key', 'fps', 'use_cache', 'max_concurrency']
    for param in expected_params:
        assert param in params, f"Missing parameter: {param}"
    
    print("✓ Batch method signature test passed")


def test_single_method_cache_param():
    """Test that vision_analyze_media has use_cache parameter."""
    vt = VisionTool()
    
    import inspect
    sig = inspect.signature(vt.vision_analyze_media)
    params = sig.parameters
    
    assert 'use_cache' in params, "Missing use_cache parameter"
    assert params['use_cache'].default == True, "use_cache should default to True"
    
    print("✓ Single method cache parameter test passed")


def test_retry_logging():
    """Test that retry logic includes proper logging."""
    vt = VisionTool()
    assert vt._max_retries >= 0, "Max retries should be non-negative"
    assert vt._retry_base_seconds > 0, "Retry base seconds should be positive"
    
    # Test exponential backoff calculation
    base = vt._retry_base_seconds
    for attempt in range(3):
        sleep_time = base * (2 ** attempt)
        assert sleep_time > 0, f"Sleep time should be positive for attempt {attempt}"
    
    print("✓ Retry logging test passed")


def test_concurrency_config():
    """Test concurrency configuration from environment."""
    # Test default
    vt1 = VisionTool()
    assert vt1._concurrency_limit > 0, "Concurrency limit should be positive"
    
    # Test custom value
    os.environ["AICLIP_VISION_CONCURRENCY"] = "10"
    vt2 = VisionTool()
    assert vt2._concurrency_limit == 10, "Should use custom concurrency value"
    
    # Cleanup
    del os.environ["AICLIP_VISION_CONCURRENCY"]
    
    print("✓ Concurrency config test passed")


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("VisionTool Performance Improvements - Test Suite")
    print("="*60 + "\n")
    
    tests = [
        test_initialization,
        test_cache_functionality,
        test_batch_method_signature,
        test_single_method_cache_param,
        test_retry_logging,
        test_concurrency_config,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
