"""
Common utility functions and helpers.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Callable, TypeVar
from datetime import datetime, timezone
import time
import signal
import threading
from functools import wraps

from ..models.story_model import SyncState
from ..utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


def get_utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def format_datetime_iso(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.isoformat()


def parse_datetime_iso(iso_string: str) -> datetime:
    """Parse ISO datetime string."""
    try:
        return datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    except ValueError as e:
        logger.error(f"Error parsing datetime string '{iso_string}': {str(e)}")
        raise


def ensure_directory_exists(file_path: str) -> None:
    """Ensure directory exists for the given file path."""
    directory = Path(file_path).parent
    directory.mkdir(parents=True, exist_ok=True)


def load_json_file(file_path: str, default: Any = None) -> Any:
    """
    Load JSON data from file with error handling.
    
    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist or is invalid
        
    Returns:
        Any: Loaded JSON data or default value
    """
    try:
        if not os.path.exists(file_path):
            logger.debug(f"JSON file not found: {file_path}, using default")
            return default
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.debug(f"Successfully loaded JSON from: {file_path}")
            return data
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {file_path}: {str(e)}")
        return default
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {str(e)}")
        return default


def save_json_file(file_path: str, data: Any) -> bool:
    """
    Save data to JSON file with error handling.
    
    Args:
        file_path: Path to JSON file
        data: Data to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ensure_directory_exists(file_path)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        
        logger.debug(f"Successfully saved JSON to: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {str(e)}")
        return False


def load_sync_state(state_file: str) -> SyncState:
    """
    Load sync state from file.
    
    Args:
        state_file: Path to state file
        
    Returns:
        SyncState: Loaded sync state or default state
    """
    try:
        data = load_json_file(state_file, {})
        if data:
            return SyncState.from_dict(data)
        else:
            logger.info("No existing sync state found, creating new state")
            return SyncState()
            
    except Exception as e:
        logger.error(f"Error loading sync state: {str(e)}, creating new state")
        return SyncState()


def save_sync_state(state_file: str, state: SyncState) -> bool:
    """
    Save sync state to file.
    
    Args:
        state_file: Path to state file
        state: Sync state to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        data = state.to_dict()
        return save_json_file(state_file, data)
    except Exception as e:
        logger.error(f"Error saving sync state: {str(e)}")
        return False


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        str: Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.2f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        remaining_seconds = seconds % 60
        return f"{hours}h {remaining_minutes}m {remaining_seconds:.2f}s"


def format_bytes(bytes_count: int) -> str:
    """
    Format bytes to human-readable string.
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        str: Formatted bytes string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"


def calculate_throughput(items_count: int, duration: float) -> float:
    """
    Calculate throughput (items per second).
    
    Args:
        items_count: Number of items processed
        duration: Duration in seconds
        
    Returns:
        float: Throughput in items per second
    """
    if duration <= 0:
        return 0.0
    return items_count / duration


def timing_decorator(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to measure and log function execution time.
    
    Args:
        func: Function to decorate
        
    Returns:
        Callable: Decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {str(e)}")
            raise
    return wrapper


class GracefulShutdownHandler:
    """Handler for graceful shutdown on SIGTERM/SIGINT."""
    
    def __init__(self):
        """Initialize shutdown handler."""
        self.shutdown_event = threading.Event()
        self.shutdown_requested = False
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info("Graceful shutdown handler initialized")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        
        self.shutdown_requested = True
        self.shutdown_event.set()
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown was requested."""
        return self.shutdown_requested
    
    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for shutdown signal.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if shutdown was requested, False if timeout
        """
        return self.shutdown_event.wait(timeout)


class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.metrics = {}
        self.start_times = {}
    
    def start_timer(self, operation: str) -> None:
        """Start timing an operation."""
        self.start_times[operation] = time.time()
    
    def end_timer(self, operation: str) -> float:
        """
        End timing an operation and return duration.
        
        Args:
            operation: Operation name
            
        Returns:
            float: Duration in seconds
        """
        if operation not in self.start_times:
            logger.warning(f"Timer not started for operation: {operation}")
            return 0.0
        
        duration = time.time() - self.start_times[operation]
        del self.start_times[operation]
        
        # Store metric
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(duration)
        
        return duration
    
    def get_average_duration(self, operation: str) -> float:
        """Get average duration for an operation."""
        if operation not in self.metrics or not self.metrics[operation]:
            return 0.0
        
        return sum(self.metrics[operation]) / len(self.metrics[operation])
    
    def get_metrics_summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary of all metrics."""
        summary = {}
        
        for operation, durations in self.metrics.items():
            if durations:
                summary[operation] = {
                    "count": len(durations),
                    "total": sum(durations),
                    "average": sum(durations) / len(durations),
                    "min": min(durations),
                    "max": max(durations)
                }
        
        return summary
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self.metrics.clear()
        self.start_times.clear()


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0
) -> Callable:
    """
    Decorator for retry with exponential backoff.
    
    Args:
        max_retries: Maximum number of retries
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Backoff multiplier
        
    Returns:
        Callable: Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise
                    
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {str(e)}, retrying in {delay:.2f}s")
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator
