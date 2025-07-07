#!/usr/bin/env python3
"""
Resource Manager for Large Temporal Chunks Processing

This module provides comprehensive resource management capabilities for handling
large temporal data chunks in the Kaspa Knowledge Hub pipeline, including:
- Memory usage monitoring and limits
- Chunked processing for large datasets
- Resource exhaustion detection and graceful degradation
- Retry mechanisms with exponential backoff
- Progress tracking for large operations
- Enhanced disk space monitoring
- Streaming/pagination support for large data processing
"""

import gc
import json
import psutil
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

# Memory thresholds (in bytes)
MEMORY_WARNING_THRESHOLD = 1 * 1024 * 1024 * 1024  # 1GB
MEMORY_CRITICAL_THRESHOLD = 2 * 1024 * 1024 * 1024  # 2GB
MEMORY_ABORT_THRESHOLD = 4 * 1024 * 1024 * 1024  # 4GB

# Disk space thresholds (in bytes)
DISK_WARNING_THRESHOLD = 5 * 1024 * 1024 * 1024  # 5GB
DISK_CRITICAL_THRESHOLD = 1 * 1024 * 1024 * 1024  # 1GB

# Chunk processing defaults
DEFAULT_CHUNK_SIZE = 1000  # Items per chunk
DEFAULT_MEMORY_CHUNK_SIZE = 100 * 1024 * 1024  # 100MB per chunk
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_BACKOFF_FACTOR = 2.0


class ResourceMonitor:
    """Monitor system resources and provide alerts."""

    def __init__(self):
        self.process = psutil.Process()
        self.initial_memory = self.get_memory_usage()
        self.peak_memory = self.initial_memory
        self.start_time = time.time()

    def get_memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        return self.process.memory_info().rss

    def get_memory_percent(self) -> float:
        """Get current memory usage as percentage of system RAM."""
        return self.process.memory_percent()

    def get_cpu_percent(self) -> float:
        """Get current CPU usage percentage."""
        return self.process.cpu_percent()

    def get_disk_usage(self, path: Union[str, Path]) -> Tuple[int, int, int]:
        """Get disk usage for given path. Returns (total, used, free) in bytes."""
        stat = shutil.disk_usage(path)
        return stat.total, stat.used, stat.free

    def check_memory_limits(self) -> Tuple[bool, str, str]:
        """Check if memory usage is within safe limits.

        Returns:
            (is_safe, level, message)
        """
        current_memory = self.get_memory_usage()
        self.peak_memory = max(self.peak_memory, current_memory)

        memory_increase = current_memory - self.initial_memory

        if current_memory > MEMORY_ABORT_THRESHOLD:
            return (
                False,
                "ABORT",
                f"Memory usage critical: {current_memory / (1024**3):.2f}GB "
                f"(>{MEMORY_ABORT_THRESHOLD / (1024**3):.1f}GB limit)",
            )
        elif current_memory > MEMORY_CRITICAL_THRESHOLD:
            return (
                False,
                "CRITICAL",
                f"Memory usage high: {current_memory / (1024**3):.2f}GB "
                f"(>{MEMORY_CRITICAL_THRESHOLD / (1024**3):.1f}GB limit)",
            )
        elif current_memory > MEMORY_WARNING_THRESHOLD:
            return (
                True,
                "WARNING",
                f"Memory usage elevated: {current_memory / (1024**3):.2f}GB "
                f"(>{MEMORY_WARNING_THRESHOLD / (1024**3):.1f}GB limit)",
            )
        else:
            return (
                True,
                "OK",
                f"Memory usage normal: {current_memory / (1024**3):.2f}GB "
                f"(increase: {memory_increase / (1024**3):.2f}GB)",
            )

    def check_disk_space(self, path: Union[str, Path]) -> Tuple[bool, str, str]:
        """Check if disk space is sufficient.

        Returns:
            (is_safe, level, message)
        """
        try:
            total, used, free = self.get_disk_usage(path)

            if free < DISK_CRITICAL_THRESHOLD:
                return (
                    False,
                    "CRITICAL",
                    f"Disk space critical: {free / (1024**3):.2f}GB free "
                    f"(<{DISK_CRITICAL_THRESHOLD / (1024**3):.1f}GB limit)",
                )
            elif free < DISK_WARNING_THRESHOLD:
                return (
                    True,
                    "WARNING",
                    f"Disk space low: {free / (1024**3):.2f}GB free "
                    f"(<{DISK_WARNING_THRESHOLD / (1024**3):.1f}GB limit)",
                )
            else:
                return (
                    True,
                    "OK",
                    f"Disk space sufficient: {free / (1024**3):.2f}GB free",
                )
        except Exception as e:
            return False, "ERROR", f"Could not check disk space: {e}"

    def get_resource_report(self, path: Union[str, Path] = ".") -> Dict[str, Any]:
        """Get comprehensive resource usage report."""
        memory_safe, memory_level, memory_msg = self.check_memory_limits()
        disk_safe, disk_level, disk_msg = self.check_disk_space(path)

        return {
            "timestamp": time.time(),
            "uptime": time.time() - self.start_time,
            "memory": {
                "current_bytes": self.get_memory_usage(),
                "current_gb": self.get_memory_usage() / (1024**3),
                "peak_bytes": self.peak_memory,
                "peak_gb": self.peak_memory / (1024**3),
                "percent": self.get_memory_percent(),
                "is_safe": memory_safe,
                "level": memory_level,
                "message": memory_msg,
            },
            "cpu": {
                "percent": self.get_cpu_percent(),
            },
            "disk": {
                "is_safe": disk_safe,
                "level": disk_level,
                "message": disk_msg,
            },
            "overall_safe": memory_safe and disk_safe,
        }

    def trigger_gc(self) -> int:
        """Trigger garbage collection and return memory freed."""
        before = self.get_memory_usage()
        gc.collect()
        after = self.get_memory_usage()
        freed = max(0, before - after)
        return freed


class ChunkedProcessor:
    """Process large datasets in manageable chunks."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        memory_monitor: Optional[ResourceMonitor] = None,
    ):
        self.chunk_size = chunk_size
        self.monitor = memory_monitor or ResourceMonitor()
        self.processed_items = 0
        self.failed_items = 0
        self.start_time = time.time()

    def process_list_in_chunks(
        self,
        items: List[Any],
        processor_func: callable,
        progress_callback: Optional[callable] = None,
    ) -> Generator[Any, None, None]:
        """Process a list of items in chunks with resource monitoring.

        Args:
            items: List of items to process
            processor_func: Function to process each item
            progress_callback: Optional callback for progress updates

        Yields:
            Processed items
        """
        total_items = len(items)

        for i in range(0, total_items, self.chunk_size):
            chunk = items[i : i + self.chunk_size]
            chunk_start = time.time()

            # Check resources before processing chunk
            resource_report = self.monitor.get_resource_report()

            if not resource_report["overall_safe"]:
                # Try garbage collection
                freed = self.monitor.trigger_gc()
                print(
                    f"Resource warning detected. Freed "
                    f"{freed / (1024**3):.2f}GB through garbage collection"
                )

                # Re-check after GC
                resource_report = self.monitor.get_resource_report()

                if not resource_report["memory"]["is_safe"]:
                    if resource_report["memory"]["level"] == "ABORT":
                        raise MemoryError(
                            f"Memory usage too high: "
                            f"{resource_report['memory']['message']}"
                        )
                    else:
                        print(f"Warning: {resource_report['memory']['message']}")

            # Process chunk
            chunk_results = []
            for item in chunk:
                try:
                    result = processor_func(item)
                    chunk_results.append(result)
                    self.processed_items += 1
                except Exception as e:
                    print(f"Error processing item: {e}")
                    self.failed_items += 1
                    continue

            # Yield results
            for result in chunk_results:
                yield result

            # Progress update
            chunk_time = time.time() - chunk_start
            if progress_callback:
                progress_callback(
                    processed=min(i + self.chunk_size, total_items),
                    total=total_items,
                    chunk_time=chunk_time,
                    resource_report=resource_report,
                )

            # Clear chunk results to free memory
            del chunk_results
            gc.collect()

    def process_file_in_chunks(
        self,
        file_path: Union[str, Path],
        processor_func: callable,
        progress_callback: Optional[callable] = None,
    ) -> Generator[Any, None, None]:
        """Process a large JSON file in chunks.

        Args:
            file_path: Path to JSON file
            processor_func: Function to process each item
            progress_callback: Optional callback for progress updates

        Yields:
            Processed items
        """
        file_path = Path(file_path)

        try:
            # Check file size
            file_size = file_path.stat().st_size
            print(f"Processing file: {file_path} ({file_size / (1024**3):.2f}GB)")

            # Load and process in chunks
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Handle different JSON structures
                if isinstance(data, dict):
                    # If it's a dict, look for list-like structures
                    if "sources" in data:
                        items = []
                        for source_key, source_data in data["sources"].items():
                            if isinstance(source_data, list):
                                items.extend(source_data)
                    else:
                        # Convert dict to list of key-value pairs
                        items = list(data.items())
                elif isinstance(data, list):
                    items = data
                else:
                    items = [data]

                # Process using list chunking
                yield from self.process_list_in_chunks(
                    items, processor_func, progress_callback
                )

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            raise

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get statistics about processing performance."""
        elapsed = time.time() - self.start_time

        return {
            "processed_items": self.processed_items,
            "failed_items": self.failed_items,
            "success_rate": self.processed_items
            / max(1, self.processed_items + self.failed_items),
            "elapsed_time": elapsed,
            "items_per_second": self.processed_items / max(1, elapsed),
            "peak_memory_gb": self.monitor.peak_memory / (1024**3),
        }


class RetryManager:
    """Manage retry operations with exponential backoff."""

    def __init__(
        self,
        max_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        base_delay: float = DEFAULT_RETRY_DELAY,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor

    def retry_with_backoff(self, func: callable, *args, **kwargs) -> Any:
        """Execute function with retry and exponential backoff.

        Args:
            func: Function to execute
            *args: Arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt == self.max_attempts - 1:
                    # Last attempt failed
                    break

                # Calculate delay with exponential backoff
                delay = self.base_delay * (self.backoff_factor**attempt)
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
                time.sleep(delay)

        # All attempts failed
        raise last_exception


class ProgressTracker:
    """Track progress of large operations."""

    def __init__(self, total_items: int, description: str = "Processing"):
        self.total_items = total_items
        self.description = description
        self.processed_items = 0
        self.start_time = time.time()
        self.last_update = 0

    def update(self, items_processed: int, force: bool = False):
        """Update progress."""
        self.processed_items = items_processed
        current_time = time.time()

        # Update every 5 seconds or when forced
        if force or current_time - self.last_update > 5:
            self.last_update = current_time
            self._print_progress()

    def _print_progress(self):
        """Print current progress."""
        elapsed = time.time() - self.start_time
        percent = (self.processed_items / self.total_items) * 100

        if self.processed_items > 0:
            avg_time = elapsed / self.processed_items
            eta = avg_time * (self.total_items - self.processed_items)
            eta_str = f"ETA: {eta:.0f}s"
        else:
            eta_str = "ETA: unknown"

        print(
            f"{self.description}: {self.processed_items}/{self.total_items} "
            f"({percent:.1f}%) - {eta_str}"
        )

    def complete(self):
        """Mark processing as complete."""
        self.processed_items = self.total_items
        elapsed = time.time() - self.start_time
        print(
            f"{self.description}: Complete! {self.total_items} items in {elapsed:.2f}s "
            f"({self.total_items/elapsed:.1f} items/s)"
        )


class LargeDatasetManager:
    """Comprehensive manager for large temporal dataset processing."""

    def __init__(self, work_dir: Union[str, Path] = "."):
        self.work_dir = Path(work_dir)
        self.monitor = ResourceMonitor()
        self.retry_manager = RetryManager()
        self.stats = {
            "operations": 0,
            "total_items_processed": 0,
            "total_failures": 0,
            "memory_warnings": 0,
            "disk_warnings": 0,
            "recoveries": 0,
        }

    def process_large_dataset(
        self,
        data: Union[List[Any], Dict[str, Any], Path],
        processor_func: callable,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        description: str = "Processing dataset",
    ) -> List[Any]:
        """Process a large dataset with full resource management.

        Args:
            data: Dataset to process (list, dict, or file path)
            processor_func: Function to process each item
            chunk_size: Size of processing chunks
            description: Description for progress tracking

        Returns:
            List of processed results
        """
        self.stats["operations"] += 1

        # Initialize components
        chunked_processor = ChunkedProcessor(chunk_size, self.monitor)
        results = []

        # Determine data source
        if isinstance(data, (str, Path)):
            data_path = Path(data)
            if not data_path.exists():
                raise FileNotFoundError(f"Data file not found: {data_path}")

            # Estimate total items for progress tracking
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    sample = json.load(f)
                    if isinstance(sample, list):
                        total_items = len(sample)
                    elif isinstance(sample, dict) and "sources" in sample:
                        total_items = sum(
                            len(v)
                            for v in sample["sources"].values()
                            if isinstance(v, list)
                        )
                    else:
                        total_items = 1
            except Exception:
                total_items = 1000  # Default estimate

            progress_tracker = ProgressTracker(total_items, description)

            def progress_callback(processed, total, chunk_time, resource_report):
                progress_tracker.update(processed)

                # Check for warnings
                if not resource_report["memory"]["is_safe"]:
                    self.stats["memory_warnings"] += 1
                if not resource_report["disk"]["is_safe"]:
                    self.stats["disk_warnings"] += 1

            # Process file in chunks
            try:
                for result in chunked_processor.process_file_in_chunks(
                    data_path, processor_func, progress_callback
                ):
                    results.append(result)

                progress_tracker.complete()

            except Exception as e:
                print(f"Error processing file: {e}")
                # Try recovery by processing smaller chunks
                print("Attempting recovery with smaller chunks...")
                smaller_chunk_size = max(1, chunk_size // 4)
                chunked_processor = ChunkedProcessor(smaller_chunk_size, self.monitor)

                try:
                    for result in chunked_processor.process_file_in_chunks(
                        data_path, processor_func, progress_callback
                    ):
                        results.append(result)

                    self.stats["recoveries"] += 1
                    progress_tracker.complete()

                except Exception as recovery_error:
                    print(f"Recovery failed: {recovery_error}")
                    raise

        elif isinstance(data, list):
            total_items = len(data)
            progress_tracker = ProgressTracker(total_items, description)

            def progress_callback(processed, total, chunk_time, resource_report):
                progress_tracker.update(processed)

                # Check for warnings
                if not resource_report["memory"]["is_safe"]:
                    self.stats["memory_warnings"] += 1
                if not resource_report["disk"]["is_safe"]:
                    self.stats["disk_warnings"] += 1

            # Process list in chunks
            try:
                for result in chunked_processor.process_list_in_chunks(
                    data, processor_func, progress_callback
                ):
                    results.append(result)

                progress_tracker.complete()

            except Exception as e:
                print(f"Error processing list: {e}")
                raise

        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

        # Update statistics
        proc_stats = chunked_processor.get_processing_stats()
        self.stats["total_items_processed"] += proc_stats["processed_items"]
        self.stats["total_failures"] += proc_stats["failed_items"]

        return results

    def get_manager_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the manager."""
        resource_report = self.monitor.get_resource_report(self.work_dir)

        return {
            "operations": self.stats["operations"],
            "total_items_processed": self.stats["total_items_processed"],
            "total_failures": self.stats["total_failures"],
            "memory_warnings": self.stats["memory_warnings"],
            "disk_warnings": self.stats["disk_warnings"],
            "recoveries": self.stats["recoveries"],
            "success_rate": self.stats["total_items_processed"]
            / max(
                1, self.stats["total_items_processed"] + self.stats["total_failures"]
            ),
            "current_resources": resource_report,
        }


# Utility functions for easy integration
def process_with_resource_management(
    data: Union[List[Any], Dict[str, Any], Path],
    processor_func: callable,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    description: str = "Processing",
    work_dir: Union[str, Path] = ".",
) -> List[Any]:
    """Convenience function for processing data with full resource management."""
    manager = LargeDatasetManager(work_dir)
    return manager.process_large_dataset(data, processor_func, chunk_size, description)


def check_resources(path: Union[str, Path] = ".") -> Dict[str, Any]:
    """Convenience function to check current resource usage."""
    monitor = ResourceMonitor()
    return monitor.get_resource_report(path)


def retry_operation(func: callable, *args, **kwargs) -> Any:
    """Convenience function to retry an operation with exponential backoff."""
    retry_manager = RetryManager()
    return retry_manager.retry_with_backoff(func, *args, **kwargs)
