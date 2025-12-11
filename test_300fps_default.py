#!/usr/bin/env python3
"""
Test script to verify that 300 FPS is now the default performance target.
"""

import os
from vibe.core.performance import MAX_FPS, PERFORMANCE_MODE, is_high_performance

def test_default_performance():
    """Test that the default performance settings are optimized for 300 FPS."""
    
    print("🚀 Testing Default Performance Settings")
    print("=" * 50)
    
    # Test 1: Check MAX_FPS constant
    print(f"✓ MAX_FPS constant: {MAX_FPS} FPS")
    assert MAX_FPS == 300, f"Expected MAX_FPS to be 300, got {MAX_FPS}"
    
    # Test 2: Check default performance mode
    print(f"✓ Default performance mode: {PERFORMANCE_MODE}")
    assert PERFORMANCE_MODE == "high", f"Expected default mode to be 'high', got {PERFORMANCE_MODE}"
    
    # Test 3: Check high performance detection
    is_high = is_high_performance()
    print(f"✓ High performance mode active: {is_high}")
    assert is_high, "Expected high performance mode to be active by default"
    
    # Test 4: Calculate target frame time
    target_frame_time_ms = (1.0 / MAX_FPS) * 1000
    print(f"✓ Target frame time: {target_frame_time_ms:.3f} ms")
    
    print("\n🎉 All tests passed!")
    print(f"✅ Mistral Vibe is now optimized for {MAX_FPS} FPS by default!")
    print(f"✅ Running in '{PERFORMANCE_MODE}' performance mode")
    print(f"✅ Target frame budget: {target_frame_time_ms:.3f} ms per frame")
    
    # Performance recommendations
    print("\n📊 Performance Recommendations:")
    print(f"  • For maximum speed: vibe --performance-mode extreme")
    print(f"  • For development: vibe --performance-mode balanced")
    print(f"  • For benchmarks: vibe --benchmark")

if __name__ == "__main__":
    test_default_performance()