"""
Kaspa Pipeline Monitoring Module

This module provides comprehensive error handling, logging, and monitoring
capabilities for the entire Kaspa Knowledge Pipeline.

Main Components:
- KaspaPipelineLogger: Enhanced logging with performance tracking
- KaspaPipelineErrorHandler: Comprehensive error handling and health monitoring
- NotificationService: Multi-channel alerting system
- PipelineValidator: Enhanced validation with detailed reporting
- MonitoringConfig: Configuration management

Quick Start:
    from monitoring import setup_monitoring_from_env

    logger, error_handler = setup_monitoring_from_env()

    # Use in your code
    try:
        # Your code here
        pass
    except Exception as e:
        error_handler.handle_exception(e, "my_component")

Decorators:
    from monitoring import retry_on_failure, run_with_monitoring

    @retry_on_failure(max_retries=3, component="my_component")
    def my_function():
        # Function that might fail
        pass
"""

from .error_handler import (
    # Main classes
    KaspaPipelineLogger,
    KaspaPipelineErrorHandler,
    NotificationService,
    PipelineValidator,
    # Data classes
    ErrorDetails,
    ErrorSeverity,
    ErrorCategory,
    ValidationResult,
    PipelineHealth,
    PerformanceMetrics,
    NotificationConfig,
    NotificationChannel,
    # Utility functions
    retry_on_failure,
    run_with_monitoring,
    setup_monitoring_from_env,
    create_pipeline_logger,
    create_error_handler,
    create_validator,
)

from .config import (
    MonitoringConfig,
    load_monitoring_config,
    create_example_env_file,
)

# Version and metadata
__version__ = "1.0.0"
__author__ = "Kaspa Knowledge Pipeline Team"
__description__ = "Comprehensive monitoring and error handling for Kaspa Pipeline"

# Convenience imports for most common use cases
__all__ = [
    # Main classes
    "KaspaPipelineLogger",
    "KaspaPipelineErrorHandler",
    "NotificationService",
    "PipelineValidator",
    "MonitoringConfig",
    # Data classes
    "ErrorDetails",
    "ErrorSeverity",
    "ErrorCategory",
    "ValidationResult",
    "PipelineHealth",
    "PerformanceMetrics",
    "NotificationConfig",
    "NotificationChannel",
    # Utility functions
    "retry_on_failure",
    "run_with_monitoring",
    "setup_monitoring_from_env",
    "create_pipeline_logger",
    "create_error_handler",
    "create_validator",
    "load_monitoring_config",
    "create_example_env_file",
    # Metadata
    "__version__",
    "__author__",
    "__description__",
]


# Module-level convenience functions
def quick_setup(log_level: str = "INFO", enable_notifications: bool = False):
    """
    Quick setup for monitoring system with sensible defaults.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_notifications: Whether to enable console/file notifications

    Returns:
        Tuple of (logger, error_handler)
    """
    import os

    # Set basic environment variables
    os.environ["KASPA_LOG_LEVEL"] = log_level
    if enable_notifications:
        os.environ["KASPA_NOTIFICATIONS_ENABLED"] = "true"

    return setup_monitoring_from_env()


def create_component_logger(component_name: str, log_level: str = "INFO"):
    """
    Create a logger for a specific component.

    Args:
        component_name: Name of the component
        log_level: Logging level

    Returns:
        KaspaPipelineLogger instance
    """
    return create_pipeline_logger(log_level=log_level, component=component_name)


def get_health_dashboard():
    """
    Get a simple health dashboard for the pipeline.

    Returns:
        Dictionary with health information
    """
    # This would need to be implemented with a global error handler
    # or persistent storage to be truly useful
    logger, error_handler = setup_monitoring_from_env()
    return error_handler.get_health_report()


# Initialize monitoring directories
def _ensure_monitoring_directories():
    """Ensure monitoring directories exist."""
    from pathlib import Path

    directories = ["monitoring/logs", "monitoring/reports", "monitoring/alerts"]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


# Initialize on import
_ensure_monitoring_directories()
