"""Performance benchmarking utilities for Mistral Vibe.

This module provides tools for measuring and optimizing performance
across different components of the application.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
import time
from typing import Any, TypeVar

from textual import work

from vibe.core.performance import PerformanceMonitor

T = TypeVar("T")


class BenchmarkResult:
    """Container for benchmark results."""
    
    def __init__(self) -> None:
        self.start_time = 0.0
        self.end_time = 0.0
        self.duration = 0.0
        self.operations = 0
        self.ops_per_second = 0.0
        self.memory_usage = 0.0  # In MB
        self.success = True
        self.error: str | None = None

    def __str__(self) -> str:
        return (f"BenchmarkResult(duration={self.duration:.4f}s, "
                f"ops={self.operations}, "
                f"ops/s={self.ops_per_second:.2f}, "
                f"memory={self.memory_usage:.2f}MB, "
                f"success={self.success})")


class PerformanceBenchmark:
    """Benchmark performance of specific operations."""
    
    def __init__(self, name: str = "Unnamed Benchmark") -> None:
        self.name = name
        self._monitor = PerformanceMonitor()
        
    def benchmark_sync(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> BenchmarkResult:
        """Benchmark a synchronous function."""
        result = BenchmarkResult()
        result.start_time = time.perf_counter()
        
        try:
            # Warm-up run
            func(*args, **kwargs)
            
            # Actual benchmark
            result.start_time = time.perf_counter()
            func(*args, **kwargs)
            result.end_time = time.perf_counter()
            result.duration = result.end_time - result.start_time
            result.success = True
            
        except Exception as e:
            result.end_time = time.perf_counter()
            result.duration = result.end_time - result.start_time
            result.success = False
            result.error = str(e)
        
        return result
    
    async def benchmark_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> BenchmarkResult:
        """Benchmark an asynchronous function."""
        result = BenchmarkResult()
        result.start_time = time.perf_counter()
        
        try:
            # Warm-up run
            await func(*args, **kwargs)
            
            # Actual benchmark
            result.start_time = time.perf_counter()
            await func(*args, **kwargs)
            result.end_time = time.perf_counter()
            result.duration = result.end_time - result.start_time
            result.success = True
            
        except Exception as e:
            result.end_time = time.perf_counter()
            result.duration = result.end_time - result.start_time
            result.success = False
            result.error = str(e)
        
        return result
    
    def benchmark_generator(self, func: Callable[..., Generator[T, None, None]], *args: Any, **kwargs: Any) -> BenchmarkResult:
        """Benchmark a generator function."""
        result = BenchmarkResult()
        result.start_time = time.perf_counter()
        
        try:
            # Warm-up run
            list(func(*args, **kwargs))
            
            # Actual benchmark
            result.start_time = time.perf_counter()
            items = list(func(*args, **kwargs))
            result.end_time = time.perf_counter()
            result.duration = result.end_time - result.start_time
            result.operations = len(items)
            result.ops_per_second = result.operations / result.duration if result.duration > 0 else 0
            result.success = True
            
        except Exception as e:
            result.end_time = time.perf_counter()
            result.duration = result.end_time - result.start_time
            result.success = False
            result.error = str(e)
        
        return result
    
    async def benchmark_async_generator(self, func: Callable[..., AsyncGenerator[T, None]], *args: Any, **kwargs: Any) -> BenchmarkResult:
        """Benchmark an async generator function."""
        result = BenchmarkResult()
        result.start_time = time.perf_counter()
        
        try:
            # Warm-up run
            items = []
            async for item in func(*args, **kwargs):
                items.append(item)
            
            # Actual benchmark
            result.start_time = time.perf_counter()
            items = []
            async for item in func(*args, **kwargs):
                items.append(item)
            result.end_time = time.perf_counter()
            result.duration = result.end_time - result.start_time
            result.operations = len(items)
            result.ops_per_second = result.operations / result.duration if result.duration > 0 else 0
            result.success = True
            
        except Exception as e:
            result.end_time = time.perf_counter()
            result.duration = result.end_time - result.start_time
            result.success = False
            result.error = str(e)
        
        return result


class SystemPerformanceTester:
    """Test overall system performance capabilities."""
    
    def __init__(self) -> None:
        self._results: dict[str, BenchmarkResult] = {}
        
    def add_result(self, name: str, result: BenchmarkResult) -> None:
        """Add a benchmark result."""
        self._results[name] = result
        
    def get_results(self) -> dict[str, BenchmarkResult]:
        """Get all benchmark results."""
        return self._results
        
    def print_summary(self) -> None:
        """Print a summary of all benchmarks."""
        print(f"\n{'='*60}")
        print("PERFORMANCE BENCHMARK SUMMARY")
        print(f"{'='*60}")
        
        for name, result in self._results.items():
            status = "✓ PASS" if result.success else f"✗ FAIL: {result.error}"
            print(f"{name:.<40} {status}")
            print(f"  Duration: {result.duration:.4f}s | Ops: {result.operations} | "
                  f"Ops/s: {result.ops_per_second:.2f}")
        
        print(f"{'='*60}\n")


@work(exclusive=True, thread=True)
def cpu_intensive_benchmark(iterations: int = 1_000_000) -> float:
    """Benchmark CPU-intensive operations."""
    start = time.perf_counter()
    
    # Perform some CPU-intensive calculations
    result = 0
    for i in range(iterations):
        result += i * i
        result %= 1000  # Keep it bounded
    
    end = time.perf_counter()
    return end - start


async def memory_benchmark(size_mb: int = 100) -> float:
    """Benchmark memory allocation performance."""
    start = time.perf_counter()
    
    # Allocate and release memory
    data = bytearray(size_mb * 1024 * 1024)
    for i in range(len(data)):
        data[i] = i % 256
    
    # Force garbage collection
    del data
    
    end = time.perf_counter()
    return end - start


def run_comprehensive_benchmark() -> SystemPerformanceTester:
    """Run a comprehensive performance benchmark."""
    tester = SystemPerformanceTester()
    benchmark = PerformanceBenchmark("System Performance")
    
    print("Running performance benchmarks...")
    
    # CPU benchmark
    print("  Testing CPU performance...")
    cpu_result = benchmark.benchmark_sync(cpu_intensive_benchmark, 500_000)
    tester.add_result("CPU Intensive Operations", cpu_result)
    
    # Memory benchmark
    print("  Testing memory performance...")
    memory_result = asyncio.run(benchmark.benchmark_async(memory_benchmark, 50))
    tester.add_result("Memory Allocation", memory_result)
    
    return tester