"""
Error Handling, Logging, and Validation System for RAG Document Generation Pipeline

This module provides a comprehensive error handling, logging, and validation framework
for the entire RAG document generation pipeline, including retry mechanisms,
structured error reporting, and pipeline health monitoring.
"""

import logging
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import time
from functools import wraps

# Removed unused import: subprocess


class ErrorSeverity(Enum):
    """Error severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorCategory(Enum):
    """Error category types."""

    DATA_LOADING = "data_loading"
    DATA_VALIDATION = "data_validation"
    TEMPLATE_GENERATION = "template_generation"
    SIGNAL_FILTERING = "signal_filtering"
    FILE_OPERATIONS = "file_operations"
    PIPELINE_EXECUTION = "pipeline_execution"
    CONFIGURATION = "configuration"
    EXTERNAL_DEPENDENCY = "external_dependency"


@dataclass
class ErrorDetails:
    """Detailed error information."""

    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    exception_type: str
    traceback_info: str
    context: Dict[str, Any] = field(default_factory=dict)
    component: str = "unknown"
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recovery_action: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert error details to dictionary for logging."""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "exception_type": self.exception_type,
            "traceback": self.traceback_info,
            "context": self.context,
            "component": self.component,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "recovery_action": self.recovery_action,
            "retry_count": self.retry_count,
        }


@dataclass
class ValidationResult:
    """Results of validation checks."""

    is_valid: bool
    errors: List[ErrorDetails] = field(default_factory=list)
    warnings: List[ErrorDetails] = field(default_factory=list)
    validation_time: float = 0.0
    component: str = "unknown"

    def add_error(self, error: ErrorDetails) -> None:
        """Add an error to the validation result."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: ErrorDetails) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(warning)

    def has_critical_errors(self) -> bool:
        """Check if there are any critical errors."""
        return any(error.severity == ErrorSeverity.CRITICAL for error in self.errors)


@dataclass
class PipelineHealth:
    """Pipeline health monitoring information."""

    component: str
    is_healthy: bool
    last_check: datetime
    error_count: int = 0
    warning_count: int = 0
    success_rate: float = 0.0
    average_execution_time: float = 0.0
    last_error: Optional[ErrorDetails] = None

    def update_health(
        self,
        is_success: bool,
        execution_time: float,
        error: Optional[ErrorDetails] = None,
    ):
        """Update health metrics."""
        self.last_check = datetime.now()

        # Initialize success rate to 1.0 for new components on first success
        if self.success_rate == 0.0 and is_success:
            self.success_rate = 1.0
        elif is_success:
            self.success_rate = min(1.0, self.success_rate + 0.1)
        else:
            self.success_rate = max(0.0, self.success_rate - 0.2)
            self.error_count += 1
            if error:
                self.last_error = error

        # Update average execution time
        if self.average_execution_time == 0.0:
            self.average_execution_time = execution_time
        else:
            weighted_old = self.average_execution_time * 0.8
            weighted_new = execution_time * 0.2
            self.average_execution_time = weighted_old + weighted_new

        self.is_healthy = self.success_rate >= 0.8 and self.error_count < 5


class RAGPipelineLogger:
    """Enhanced logging system for RAG pipeline."""

    def __init__(self, log_level: str = "INFO", log_file: Optional[str] = None):
        """
        Initialize the pipeline logger.

        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional log file path
        """
        self.logger = logging.getLogger("rag_pipeline")
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Clear existing handlers
        self.logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler (if specified)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log_error(self, error: ErrorDetails) -> None:
        """Log an error with structured information."""
        error_dict = error.to_dict()
        # Remove 'message' from extra to avoid conflict with logging system
        extra_data = {k: v for k, v in error_dict.items() if k != "message"}
        self.logger.error(f"Error {error.error_id}: {error.message}", extra=extra_data)

    def log_validation_result(self, result: ValidationResult) -> None:
        """Log validation results."""
        if result.is_valid:
            self.logger.info(
                f"Validation passed for {result.component} "
                f"in {result.validation_time:.2f}s"
            )
        else:
            self.logger.error(
                f"Validation failed for {result.component} "
                f"with {len(result.errors)} errors"
            )
            for error in result.errors:
                self.log_error(error)

    def log_pipeline_health(self, health: PipelineHealth) -> None:
        """Log pipeline health information."""
        status = "HEALTHY" if health.is_healthy else "UNHEALTHY"
        self.logger.info(
            f"Pipeline Health - {health.component}: {status} "
            f"(Success Rate: {health.success_rate:.1%}, "
            f"Avg Time: {health.average_execution_time:.2f}s, "
            f"Errors: {health.error_count})"
        )


class RAGErrorHandler:
    """Comprehensive error handling system for RAG pipeline."""

    def __init__(self, logger: Optional[RAGPipelineLogger] = None):
        """
        Initialize the error handler.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or RAGPipelineLogger()
        self.error_counter = 0
        self.health_metrics: Dict[str, PipelineHealth] = {}
        self.error_history: List[ErrorDetails] = []

    def generate_error_id(self) -> str:
        """Generate unique error ID."""
        self.error_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"RAG_ERROR_{timestamp}_{self.error_counter:04d}"

    def create_error(
        self,
        message: str,
        severity: ErrorSeverity,
        category: ErrorCategory,
        exception: Optional[Exception] = None,
        component: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None,
    ) -> ErrorDetails:
        """
        Create structured error details.

        Args:
            message: Error message
            severity: Error severity level
            category: Error category
            exception: Optional exception object
            component: Component where error occurred
            context: Additional context information
            recovery_action: Suggested recovery action

        Returns:
            ErrorDetails object
        """
        error_id = self.generate_error_id()

        # Extract exception information
        exception_type = type(exception).__name__ if exception else "UnknownError"
        traceback_info = traceback.format_exc() if exception else ""

        # Extract file path and line number from traceback
        file_path = None
        line_number = None
        if exception:
            tb = traceback.extract_tb(exception.__traceback__)
            if tb:
                file_path = tb[-1].filename
                line_number = tb[-1].lineno

        error = ErrorDetails(
            error_id=error_id,
            timestamp=datetime.now(),
            severity=severity,
            category=category,
            message=message,
            exception_type=exception_type,
            traceback_info=traceback_info,
            context=context or {},
            component=component,
            file_path=file_path,
            line_number=line_number,
            recovery_action=recovery_action,
        )

        self.error_history.append(error)
        self.logger.log_error(error)

        return error

    def handle_exception(
        self,
        exception: Exception,
        component: str,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        category: ErrorCategory = ErrorCategory.PIPELINE_EXECUTION,
        context: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None,
    ) -> ErrorDetails:
        """
        Handle an exception with proper logging and error creation.

        Args:
            exception: The exception to handle
            component: Component where exception occurred
            severity: Error severity level
            category: Error category
            context: Additional context information
            recovery_action: Suggested recovery action

        Returns:
            ErrorDetails object
        """
        message = str(exception)
        return self.create_error(
            message=message,
            severity=severity,
            category=category,
            exception=exception,
            component=component,
            context=context,
            recovery_action=recovery_action,
        )

    def update_component_health(
        self,
        component: str,
        is_success: bool,
        execution_time: float,
        error: Optional[ErrorDetails] = None,
    ):
        """Update health metrics for a component."""
        if component not in self.health_metrics:
            self.health_metrics[component] = PipelineHealth(
                component=component, is_healthy=True, last_check=datetime.now()
            )

        self.health_metrics[component].update_health(is_success, execution_time, error)
        self.logger.log_pipeline_health(self.health_metrics[component])

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_errors": len(self.error_history),
            "recent_errors": len(
                [
                    e
                    for e in self.error_history
                    if (datetime.now() - e.timestamp).seconds < 3600
                ]
            ),
            "components": {
                name: {
                    "is_healthy": health.is_healthy,
                    "success_rate": health.success_rate,
                    "error_count": health.error_count,
                    "last_check": health.last_check.isoformat(),
                }
                for name, health in self.health_metrics.items()
            },
            "critical_errors": len(
                [e for e in self.error_history if e.severity == ErrorSeverity.CRITICAL]
            ),
        }


def retry_on_failure(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Exception, ...] = (Exception,),
    component: str = "unknown",
):
    """
    Decorator for retrying functions on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff factor
        exceptions: Tuple of exceptions to catch and retry
        component: Component name for logging
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = RAGErrorHandler()

            for attempt in range(max_retries + 1):
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time

                    # Update health metrics on success
                    error_handler.update_component_health(
                        component, True, execution_time
                    )

                    return result

                except exceptions as e:
                    execution_time = time.time() - start_time

                    # Create error details
                    error = error_handler.handle_exception(
                        e,
                        component,
                        context={"attempt": attempt + 1, "max_retries": max_retries},
                    )

                    # Update health metrics on failure
                    error_handler.update_component_health(
                        component, False, execution_time, error
                    )

                    if attempt == max_retries:
                        # Final attempt failed
                        raise e

                    # Wait before retrying
                    wait_time = backoff_factor**attempt
                    time.sleep(wait_time)

                    error_handler.logger.logger.warning(
                        f"Retry attempt {attempt + 1}/{max_retries} for {component} "
                        f"after {wait_time:.1f}s delay"
                    )

        return wrapper

    return decorator


class PipelineValidator:
    """Validation system for pipeline components."""

    def __init__(self, error_handler: Optional[RAGErrorHandler] = None):
        """
        Initialize the validator.

        Args:
            error_handler: Optional error handler instance
        """
        self.error_handler = error_handler or RAGErrorHandler()

    def validate_data_directory(
        self, data_dir: Path, component: str = "data_loader"
    ) -> ValidationResult:
        """Validate data directory structure."""
        start_time = time.time()
        result = ValidationResult(is_valid=True, component=component)

        required_subdirs = ["aggregated", "briefings", "facts"]

        for subdir in required_subdirs:
            path = data_dir / subdir
            if not path.exists():
                error = self.error_handler.create_error(
                    f"Required directory '{subdir}' not found at {path}",
                    ErrorSeverity.HIGH,
                    ErrorCategory.DATA_LOADING,
                    component=component,
                    context={"directory": str(path)},
                )
                result.add_error(error)
            elif not path.is_dir():
                error = self.error_handler.create_error(
                    f"Path '{path}' exists but is not a directory",
                    ErrorSeverity.HIGH,
                    ErrorCategory.DATA_LOADING,
                    component=component,
                    context={"path": str(path)},
                )
                result.add_error(error)

        result.validation_time = time.time() - start_time
        return result

    def validate_json_structure(
        self,
        data: Dict[str, Any],
        required_fields: List[str],
        component: str = "data_validator",
    ) -> ValidationResult:
        """Validate JSON data structure."""
        start_time = time.time()
        result = ValidationResult(is_valid=True, component=component)

        for field_name in required_fields:
            if field_name not in data:
                error = self.error_handler.create_error(
                    f"Required field '{field_name}' missing from JSON data",
                    ErrorSeverity.MEDIUM,
                    ErrorCategory.DATA_VALIDATION,
                    component=component,
                    context={
                        "missing_field": field_name,
                        "available_fields": list(data.keys()),
                    },
                )
                result.add_error(error)

        result.validation_time = time.time() - start_time
        return result

    def validate_output_file(
        self, file_path: Path, component: str = "output_validator"
    ) -> ValidationResult:
        """Validate output file was created successfully."""
        start_time = time.time()
        result = ValidationResult(is_valid=True, component=component)

        if not file_path.exists():
            error = self.error_handler.create_error(
                f"Output file not created: {file_path}",
                ErrorSeverity.HIGH,
                ErrorCategory.FILE_OPERATIONS,
                component=component,
                context={"file_path": str(file_path)},
            )
            result.add_error(error)
        else:
            # Check if file is empty
            if file_path.stat().st_size == 0:
                error = self.error_handler.create_error(
                    f"Output file is empty: {file_path}",
                    ErrorSeverity.MEDIUM,
                    ErrorCategory.FILE_OPERATIONS,
                    component=component,
                    context={"file_path": str(file_path)},
                )
                result.add_error(error)

        result.validation_time = time.time() - start_time
        return result


def create_pipeline_logger(
    log_level: str = "INFO", log_file: Optional[str] = None
) -> RAGPipelineLogger:
    """Create a configured pipeline logger."""
    return RAGPipelineLogger(log_level, log_file)


def create_error_handler(logger: Optional[RAGPipelineLogger] = None) -> RAGErrorHandler:
    """Create a configured error handler."""
    return RAGErrorHandler(logger)


def create_validator(
    error_handler: Optional[RAGErrorHandler] = None,
) -> PipelineValidator:
    """Create a configured validator."""
    return PipelineValidator(error_handler)


def run_with_error_handling(
    func: Callable,
    component: str,
    error_handler: Optional[RAGErrorHandler] = None,
    **kwargs,
) -> Tuple[Any, Optional[ErrorDetails]]:
    """
    Run a function with comprehensive error handling.

    Args:
        func: Function to run
        component: Component name
        error_handler: Optional error handler
        **kwargs: Arguments to pass to function

    Returns:
        Tuple of (result, error_details)
    """
    handler = error_handler or RAGErrorHandler()

    try:
        start_time = time.time()
        result = func(**kwargs)
        execution_time = time.time() - start_time

        handler.update_component_health(component, True, execution_time)
        return result, None

    except Exception as e:
        execution_time = time.time() - start_time
        error = handler.handle_exception(e, component)
        handler.update_component_health(component, False, execution_time, error)

        return None, error


# Example usage and testing
if __name__ == "__main__":
    # Create logger and error handler
    logger = create_pipeline_logger("DEBUG")
    error_handler = create_error_handler(logger)
    validator = create_validator(error_handler)

    # Test error handling
    try:
        raise ValueError("Test error")
    except Exception as e:
        error_handler.handle_exception(e, "test_component")

    # Test validation
    from pathlib import Path

    result = validator.validate_data_directory(Path("data"))
    logger.log_validation_result(result)

    # Print health report
    health_report = error_handler.get_health_report()
    print("\nHealth Report:")
    print(json.dumps(health_report, indent=2))
