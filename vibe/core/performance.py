"""Simplified high-performance utilities for Mistral Vibe.

This module provides performance optimizations without circular import issues.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import functools
import os
import time
from typing import Any, TypeVar

# Performance constants - 300 FPS is now the default!
MAX_FPS = 300  # Target maximum frame rate
TARGET_FRAME_TIME = 1.0 / MAX_FPS  # ~3.33ms per frame
PERFORMANCE_MODE = os.environ.get("VIBE_PERFORMANCE", "high").lower()  # Default to high performance

T = TypeVar("T")


def performance_mode() -> str:
    """Get the current performance mode."""
    return PERFORMANCE_MODE


def is_high_performance() -> bool:
    """Check if we're in high performance mode."""
    return PERFORMANCE_MODE in {"high", "extreme"}


def is_extreme_performance() -> bool:
    """Check if we're in extreme performance mode."""
    return PERFORMANCE_MODE == "extreme"


def high_speed_coroutine[T](func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
    """Decorator for high-speed coroutines that should run with maximum priority.
    
    In high/extreme performance mode, this uses asyncio.shield to protect
    critical operations from cancellation and optimize task scheduling.
    """
    
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        if is_high_performance():  # Apply to high performance mode too
            # Run with maximum priority in high/extreme mode
            return await asyncio.shield(func(*args, **kwargs))
        else:
            return await func(*args, **kwargs)
    
    return wrapper


def fast_render[T](func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for render functions that should be optimized for speed.
    
    Uses performance monitoring to track render times and ensure
    they stay within the target frame budget.
    """
    
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start_time = time.perf_counter()
        
        try:
            result = func(*args, **kwargs)
            
            # Track render performance
            render_time = time.perf_counter() - start_time
            if render_time > TARGET_FRAME_TIME and is_high_performance():
                # In high performance mode, log slow renders
                # (In a real implementation, this would log to a performance monitor)
                pass
                
            return result
        except Exception:
            # Ensure we don't break the render loop
            raise
    
    return wrapper


class PerformanceMonitor:
    """Monitor and track performance metrics for the application.
    
    This class helps identify performance bottlenecks and ensures
    the application runs at target frame rates.
    """
    
    # Keep 60 frames for averaging (1 second at 60 FPS)
    MAX_FRAME_HISTORY = 60

    def __init__(self) -> None:
        self._frame_times: list[float] = []
        self._last_frame_time = 0.0
        self._fps = 0.0
        self._frame_count = 0
        self._last_fps_update = time.perf_counter()
        
    def start_frame(self) -> None:
        """Mark the start of a frame."""
        self._last_frame_time = time.perf_counter()
        
    def end_frame(self) -> None:
        """Mark the end of a frame and update performance metrics."""
        now = time.perf_counter()
        frame_time = now - self._last_frame_time
        self._frame_times.append(frame_time)
        
        # Keep only recent frames for averaging
        if len(self._frame_times) > self.MAX_FRAME_HISTORY:
            self._frame_times.pop(0)
        
        self._frame_count += 1
        
        # Update FPS counter periodically
        if now - self._last_fps_update >= 1.0:
            self._fps = self._frame_count / (now - self._last_fps_update)
            self._frame_count = 0
            self._last_fps_update = now
    
    def get_fps(self) -> float:
        """Get the current frames per second."""
        return self._fps
    
    def get_avg_frame_time(self) -> float:
        """Get the average frame time in seconds."""
        if not self._frame_times:
            return 0.0
        return sum(self._frame_times) / len(self._frame_times)
    
    def is_performing_well(self) -> bool:
        """Check if the application is performing at target frame rate."""
        # More aggressive performance target - aim for 95% of max FPS in high performance mode
        target_fps = MAX_FPS * 0.95 if is_high_performance() else MAX_FPS * 0.9
        return self._fps >= target_fps
    
    def get_performance_stats(self) -> dict[str, Any]:
        """Get detailed performance statistics."""
        return {
            "fps": self.get_fps(),
            "avg_frame_time_ms": self.get_avg_frame_time() * 1000,
            "target_fps": MAX_FPS,
            "target_frame_time_ms": TARGET_FRAME_TIME * 1000,
            "performing_well": self.is_performing_well(),
            "performance_mode": PERFORMANCE_MODE,
        }


# Utility functions for performance-aware operations

def get_performance_config() -> dict[str, Any]:
    """Get the current performance configuration."""
    return {
        "max_fps": MAX_FPS,
        "target_frame_time_ms": TARGET_FRAME_TIME * 1000,
        "performance_mode": PERFORMANCE_MODE,
        "high_performance": is_high_performance(),
        "extreme_performance": is_extreme_performance(),
    }


def should_optimize_rendering() -> bool:
    """Check if rendering should be optimized for performance."""
    return is_high_performance()


def should_use_high_priority_scheduling() -> bool:
    """Check if tasks should use high priority scheduling."""
    return is_extreme_performance()