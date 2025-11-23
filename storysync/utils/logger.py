"""
Structured logging setup with JSON format and rotation using loguru.
"""
import sys
import os
from pathlib import Path
from typing import Optional
from loguru import logger

from ..config.settings import Settings
from ..config.constants import LOG_FORMAT

# Global logger instance
_logger_initialized = False


def setup_logger(settings: Settings) -> None:
    """
    Setup structured logging with rotation and JSON format.
    
    Args:
        settings: Application settings containing log configuration
    """
    global _logger_initialized
    
    if _logger_initialized:
        return
    
    # Remove default logger
    logger.remove()
    
    # Ensure log directory exists
    log_file_path = Path(settings.log_file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Console handler with colored output
    logger.add(
        sys.stdout,
        format=LOG_FORMAT,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # File handler with rotation and JSON format
    logger.add(
        settings.log_file,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="gz",
        backtrace=True,
        diagnose=True,
        serialize=False  # Set to True for JSON format if needed
    )
    
    # JSON log file for structured logging
    json_log_file = str(log_file_path).replace('.log', '_structured.json')
    logger.add(
        json_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
        level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="gz",
        serialize=True,  # JSON format
        backtrace=True,
        diagnose=True
    )
    
    _logger_initialized = True
    logger.info(f"Logger initialized with level: {settings.log_level}")


def get_logger(name: Optional[str] = None) -> "logger":
    """
    Get logger instance with optional name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logger: Configured logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


def log_function_call(func_name: str, **kwargs) -> None:
    """
    Log function call with parameters.
    
    Args:
        func_name: Name of the function being called
        **kwargs: Function parameters to log
    """
    logger.debug(f"Calling {func_name} with parameters: {kwargs}")


def log_performance(func_name: str, duration: float, **metrics) -> None:
    """
    Log performance metrics.
    
    Args:
        func_name: Name of the function
        duration: Execution duration in seconds
        **metrics: Additional performance metrics
    """
    logger.info(f"Performance - {func_name}: {duration:.3f}s", extra={
        "performance": {
            "function": func_name,
            "duration_seconds": duration,
            **metrics
        }
    })


def log_sync_metrics(
    operation: str,
    documents_processed: int,
    documents_successful: int,
    documents_failed: int,
    duration: float,
    errors: Optional[list] = None
) -> None:
    """
    Log sync operation metrics in structured format.
    
    Args:
        operation: Type of sync operation (full, incremental)
        documents_processed: Total documents processed
        documents_successful: Successfully processed documents
        documents_failed: Failed documents
        duration: Operation duration in seconds
        errors: List of error messages
    """
    success_rate = (documents_successful / documents_processed * 100) if documents_processed > 0 else 0
    
    logger.info(f"Sync {operation} completed", extra={
        "sync_metrics": {
            "operation": operation,
            "documents_processed": documents_processed,
            "documents_successful": documents_successful,
            "documents_failed": documents_failed,
            "success_rate_percent": round(success_rate, 2),
            "duration_seconds": round(duration, 3),
            "throughput_docs_per_second": round(documents_processed / duration, 2) if duration > 0 else 0,
            "error_count": len(errors) if errors else 0
        }
    })
    
    if errors:
        for error in errors[:10]:  # Log first 10 errors
            logger.error(f"Sync error: {error}")


def log_health_check(component: str, status: dict) -> None:
    """
    Log health check results.
    
    Args:
        component: Component name (mongodb, elasticsearch)
        status: Health check status dictionary
    """
    is_healthy = status.get("status") == "healthy"
    log_level = "info" if is_healthy else "error"
    
    getattr(logger, log_level)(f"Health check - {component}: {status.get('status', 'unknown')}", extra={
        "health_check": {
            "component": component,
            "status": status.get("status"),
            "connected": status.get("connected", False),
            "details": status
        }
    })


class LoggerContextManager:
    """Context manager for logging function execution."""
    
    def __init__(self, func_name: str, log_args: bool = False, **kwargs):
        """
        Initialize logger context manager.
        
        Args:
            func_name: Name of the function
            log_args: Whether to log function arguments
            **kwargs: Function arguments to log
        """
        self.func_name = func_name
        self.log_args = log_args
        self.kwargs = kwargs
        self.start_time = None
    
    def __enter__(self):
        """Enter context manager."""
        import time
        self.start_time = time.time()
        
        if self.log_args:
            log_function_call(self.func_name, **self.kwargs)
        else:
            logger.debug(f"Starting {self.func_name}")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        import time
        duration = time.time() - self.start_time
        
        if exc_type is None:
            logger.debug(f"Completed {self.func_name} in {duration:.3f}s")
        else:
            logger.error(f"Failed {self.func_name} after {duration:.3f}s: {exc_val}")
        
        return False  # Don't suppress exceptions
