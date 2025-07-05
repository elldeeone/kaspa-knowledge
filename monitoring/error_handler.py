"""
Comprehensive Error Handling, Logging, and Monitoring System for Kaspa Knowledge Pipeline

This module provides a complete error handling, logging, and monitoring framework
for the entire Kaspa Knowledge Pipeline, including retry mechanisms, structured
error reporting, pipeline health monitoring, performance tracking, and alerting.
"""

import logging
import sys
import traceback
import smtplib
import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from functools import wraps
try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
except ImportError:
    # Python 3.13+ compatibility
    from email.message import EmailMessage as MimeText
    from email.message import EmailMessage as MimeMultipart


class ErrorSeverity(Enum):
    """Error severity levels for the pipeline."""

    CRITICAL = "critical"  # System-wide failures, pipeline cannot continue
    HIGH = "high"  # Component failures, impacts functionality
    MEDIUM = "medium"  # Recoverable errors, functionality degraded
    LOW = "low"  # Minor issues, no significant impact
    INFO = "info"  # Informational messages


class ErrorCategory(Enum):
    """Error category types for the entire pipeline."""

    # Data ingestion categories
    DATA_INGESTION = "data_ingestion"
    GITHUB_API = "github_api"
    MEDIUM_RSS = "medium_rss"
    TELEGRAM_API = "telegram_api"
    DISCOURSE_API = "discourse_api"

    # Processing categories
    DATA_LOADING = "data_loading"
    DATA_VALIDATION = "data_validation"
    DATA_AGGREGATION = "data_aggregation"
    SIGNAL_ENRICHMENT = "signal_enrichment"

    # AI processing categories
    AI_PROCESSING = "ai_processing"
    BRIEFING_GENERATION = "briefing_generation"
    FACT_EXTRACTION = "fact_extraction"
    RAG_GENERATION = "rag_generation"

    # Infrastructure categories
    FILE_OPERATIONS = "file_operations"
    PIPELINE_EXECUTION = "pipeline_execution"
    CONFIGURATION = "configuration"
    EXTERNAL_DEPENDENCY = "external_dependency"
    NETWORK = "network"
    AUTHENTICATION = "authentication"


class NotificationChannel(Enum):
    """Available notification channels."""

    EMAIL = "email"
    CONSOLE = "console"
    FILE = "file"
    WEBHOOK = "webhook"


@dataclass
class ErrorDetails:
    """Comprehensive error information for the pipeline."""

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
    user_impact: str = "unknown"
    estimated_fix_time: Optional[str] = None

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
            "user_impact": self.user_impact,
            "estimated_fix_time": self.estimated_fix_time,
        }

    def to_alert_message(self) -> str:
        """Convert error to human-readable alert message."""
        return f"""
🚨 KASPA PIPELINE ALERT - {self.severity.value.upper()}

Error ID: {self.error_id}
Component: {self.component}
Category: {self.category.value}
Time: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Message: {self.message}

Impact: {self.user_impact}
Recovery: {self.recovery_action or 'No recovery action specified'}

Context: {json.dumps(self.context, indent=2)}
        """.strip()


@dataclass
class ValidationResult:
    """Results of validation checks with enhanced reporting."""

    is_valid: bool
    errors: List[ErrorDetails] = field(default_factory=list)
    warnings: List[ErrorDetails] = field(default_factory=list)
    validation_time: float = 0.0
    component: str = "unknown"
    checked_items: int = 0
    passed_checks: int = 0

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

    def get_success_rate(self) -> float:
        """Calculate validation success rate."""
        if self.checked_items == 0:
            return 0.0
        return self.passed_checks / self.checked_items


@dataclass
class PerformanceMetrics:
    """Performance monitoring metrics for pipeline components."""

    component: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time: float = 0.0
    min_execution_time: float = float("inf")
    max_execution_time: float = 0.0
    last_execution_time: float = 0.0
    average_execution_time: float = 0.0

    # Resource usage tracking
    peak_memory_usage: float = 0.0
    average_memory_usage: float = 0.0

    # Data throughput tracking
    total_items_processed: int = 0
    items_per_second: float = 0.0

    def update_metrics(
        self,
        execution_time: float,
        success: bool,
        items_processed: int = 0,
        memory_usage: float = 0.0,
    ):
        """Update performance metrics with new execution data."""
        self.total_executions += 1
        self.last_execution_time = execution_time
        self.total_execution_time += execution_time

        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1

        # Update time statistics
        self.min_execution_time = min(self.min_execution_time, execution_time)
        self.max_execution_time = max(self.max_execution_time, execution_time)
        self.average_execution_time = self.total_execution_time / self.total_executions

        # Update resource usage
        if memory_usage > 0:
            self.peak_memory_usage = max(self.peak_memory_usage, memory_usage)
            # Simple moving average for memory usage
            if self.average_memory_usage == 0:
                self.average_memory_usage = memory_usage
            else:
                self.average_memory_usage = (
                    self.average_memory_usage * 0.9 + memory_usage * 0.1
                )

        # Update throughput
        self.total_items_processed += items_processed
        if execution_time > 0:
            self.items_per_second = items_processed / execution_time

    def get_success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100

    def is_performing_well(self) -> bool:
        """Determine if component is performing within acceptable parameters."""
        success_rate = self.get_success_rate()

        # Performance thresholds
        min_success_rate = 95.0  # 95% success rate required
        max_avg_time = 300.0  # 5 minutes max average execution time

        return (
            success_rate >= min_success_rate
            and self.average_execution_time <= max_avg_time
        )


@dataclass
class PipelineHealth:
    """Enhanced pipeline health monitoring information."""

    component: str
    is_healthy: bool
    last_check: datetime
    error_count: int = 0
    warning_count: int = 0
    success_rate: float = 0.0
    average_execution_time: float = 0.0
    last_error: Optional[ErrorDetails] = None

    # Enhanced health metrics
    consecutive_failures: int = 0
    uptime_percentage: float = 100.0
    last_successful_run: Optional[datetime] = None
    health_score: float = 100.0  # 0-100 health score

    # Performance tracking
    performance_metrics: Optional[PerformanceMetrics] = None

    def __post_init__(self):
        """Initialize performance metrics if not provided."""
        if self.performance_metrics is None:
            self.performance_metrics = PerformanceMetrics(self.component)

    def update_health(
        self,
        is_success: bool,
        execution_time: float,
        error: Optional[ErrorDetails] = None,
        items_processed: int = 0,
        memory_usage: float = 0.0,
    ):
        """Update comprehensive health metrics."""
        self.last_check = datetime.now()

        # Update performance metrics
        self.performance_metrics.update_metrics(
            execution_time, is_success, items_processed, memory_usage
        )

        # Update basic health indicators
        if is_success:
            self.consecutive_failures = 0
            self.last_successful_run = datetime.now()
            self.success_rate = min(1.0, self.success_rate + 0.1)
        else:
            self.consecutive_failures += 1
            self.success_rate = max(0.0, self.success_rate - 0.2)
            self.error_count += 1
            if error:
                self.last_error = error
                if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                    self.warning_count += 1

        # Update average execution time
        if self.average_execution_time == 0.0:
            self.average_execution_time = execution_time
        else:
            # Exponential moving average
            self.average_execution_time = (
                self.average_execution_time * 0.8 + execution_time * 0.2
            )

        # Calculate health score (0-100)
        self._calculate_health_score()

        # Update overall health status
        self.is_healthy = self._determine_health_status()

    def _calculate_health_score(self) -> None:
        """Calculate overall health score based on multiple factors."""

        # Success rate impact (50% weight)
        success_rate_score = self.success_rate * 50

        # Consecutive failures penalty (20% weight)
        failure_penalty = min(self.consecutive_failures * 5, 20)

        # Performance impact (20% weight)
        performance_score = 20.0
        if self.performance_metrics and self.performance_metrics.is_performing_well():
            performance_score = 20.0
        else:
            performance_score = 10.0

        # Recency impact (10% weight)
        recency_score = 10.0
        if self.last_successful_run:
            hours_since_success = (
                datetime.now() - self.last_successful_run
            ).total_seconds() / 3600
            if hours_since_success > 24:  # More than 24 hours
                recency_score = max(0, 10 - (hours_since_success - 24) * 0.5)

        self.health_score = max(
            0, success_rate_score + performance_score + recency_score - failure_penalty
        )

    def _determine_health_status(self) -> bool:
        """Determine if component is healthy based on multiple criteria."""
        return (
            self.health_score >= 80.0
            and self.consecutive_failures < 3
            and self.success_rate >= 0.8
            and self.error_count < 10
        )

    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        return {
            "component": self.component,
            "is_healthy": self.is_healthy,
            "health_score": round(self.health_score, 1),
            "success_rate": round(self.success_rate * 100, 1),
            "consecutive_failures": self.consecutive_failures,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "last_check": self.last_check.isoformat(),
            "last_successful_run": (
                self.last_successful_run.isoformat()
                if self.last_successful_run
                else None
            ),
            "average_execution_time": round(self.average_execution_time, 2),
            "performance_metrics": (
                {
                    "total_executions": self.performance_metrics.total_executions,
                    "success_rate": round(
                        self.performance_metrics.get_success_rate(), 1
                    ),
                    "avg_execution_time": round(
                        self.performance_metrics.average_execution_time, 2
                    ),
                    "items_per_second": round(
                        self.performance_metrics.items_per_second, 2
                    ),
                    "peak_memory_usage": round(
                        self.performance_metrics.peak_memory_usage, 2
                    ),
                }
                if self.performance_metrics
                else {}
            ),
        }


@dataclass
class NotificationConfig:
    """Configuration for alert notifications."""

    enabled: bool = True
    channels: List[NotificationChannel] = field(default_factory=list)

    # Email configuration
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_from: str = ""
    email_to: List[str] = field(default_factory=list)

    # Webhook configuration
    webhook_url: str = ""
    webhook_headers: Dict[str, str] = field(default_factory=dict)

    # Severity thresholds for notifications
    notify_on_severities: List[ErrorSeverity] = field(
        default_factory=lambda: [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]
    )

    # Rate limiting
    max_notifications_per_hour: int = 10
    cooldown_period_minutes: int = (
        15  # Minimum time between same error type notifications
    )


class NotificationService:
    """Service for sending alerts and notifications."""

    def __init__(self, config: NotificationConfig):
        """Initialize notification service with configuration."""
        self.config = config
        self.notification_history: Dict[str, List[datetime]] = {}
        self.last_notification_time: Dict[str, datetime] = {}

    def should_send_notification(self, error: ErrorDetails) -> bool:
        """Determine if a notification should be sent for this error."""
        if not self.config.enabled:
            return False

        # Check severity threshold
        if error.severity not in self.config.notify_on_severities:
            return False

        # Check rate limiting
        now = datetime.now()
        error_key = f"{error.component}:{error.category.value}"

        # Check cooldown period
        if error_key in self.last_notification_time:
            time_since_last = now - self.last_notification_time[error_key]
            if (
                time_since_last.total_seconds()
                < self.config.cooldown_period_minutes * 60
            ):
                return False

        # Check hourly rate limit
        if error_key not in self.notification_history:
            self.notification_history[error_key] = []

        # Clean old notifications (older than 1 hour)
        cutoff_time = now - timedelta(hours=1)
        self.notification_history[error_key] = [
            time for time in self.notification_history[error_key] if time > cutoff_time
        ]

        # Check if we're under the rate limit
        if (
            len(self.notification_history[error_key])
            >= self.config.max_notifications_per_hour
        ):
            return False

        return True

    def send_notification(self, error: ErrorDetails) -> bool:
        """Send notification for the given error."""
        if not self.should_send_notification(error):
            return False

        success = False

        # Send to all configured channels
        for channel in self.config.channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    success |= self._send_email_notification(error)
                elif channel == NotificationChannel.CONSOLE:
                    success |= self._send_console_notification(error)
                elif channel == NotificationChannel.FILE:
                    success |= self._send_file_notification(error)
                elif channel == NotificationChannel.WEBHOOK:
                    success |= self._send_webhook_notification(error)
            except Exception as e:
                logging.error(f"Failed to send notification via {channel.value}: {e}")

        # Update notification history
        if success:
            error_key = f"{error.component}:{error.category.value}"
            now = datetime.now()
            self.notification_history[error_key].append(now)
            self.last_notification_time[error_key] = now

        return success

    def _send_email_notification(self, error: ErrorDetails) -> bool:
        """Send email notification."""
        if not self.config.email_to or not self.config.email_username:
            return False

        try:
            msg = MimeMultipart()
            msg["From"] = self.config.email_from or self.config.email_username
            msg["To"] = ", ".join(self.config.email_to)
            msg["Subject"] = (
                f"Kaspa Pipeline Alert - {error.severity.value.upper()}: {error.component}"
            )

            body = error.to_alert_message()
            msg.attach(MimeText(body, "plain"))

            server = smtplib.SMTP(
                self.config.email_smtp_host, self.config.email_smtp_port
            )
            server.starttls()
            server.login(self.config.email_username, self.config.email_password)
            server.send_message(msg)
            server.quit()

            return True
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")
            return False

    def _send_console_notification(self, error: ErrorDetails) -> bool:
        """Send console notification."""
        try:
            alert_message = error.to_alert_message()
            print(f"\n{'='*80}")
            print(alert_message)
            print(f"{'='*80}\n")
            return True
        except Exception as e:
            logging.error(f"Failed to send console notification: {e}")
            return False

    def _send_file_notification(self, error: ErrorDetails) -> bool:
        """Send file notification."""
        try:
            alert_file = Path("monitoring/alerts.log")
            alert_file.parent.mkdir(exist_ok=True)

            alert_message = error.to_alert_message()
            with open(alert_file, "a", encoding="utf-8") as f:
                f.write(f"\n{alert_message}\n")
                f.write(f"{'='*80}\n")

            return True
        except Exception as e:
            logging.error(f"Failed to send file notification: {e}")
            return False

    def _send_webhook_notification(self, error: ErrorDetails) -> bool:
        """Send webhook notification."""
        if not self.config.webhook_url:
            return False

        try:
            import requests

            payload = {
                "error": error.to_dict(),
                "alert_message": error.to_alert_message(),
                "timestamp": error.timestamp.isoformat(),
            }

            response = requests.post(
                self.config.webhook_url,
                json=payload,
                headers=self.config.webhook_headers,
                timeout=30,
            )

            return response.status_code == 200
        except Exception as e:
            logging.error(f"Failed to send webhook notification: {e}")
            return False


class KaspaPipelineLogger:
    """Enhanced logging system for the entire Kaspa Knowledge Pipeline."""

    def __init__(
        self,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        component: str = "kaspa_pipeline",
    ):
        """
        Initialize the pipeline logger.

        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional log file path
            component: Component name for the logger
        """
        self.component = component
        self.logger = logging.getLogger(f"kaspa_pipeline.{component}")
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Clear existing handlers to avoid duplication
        self.logger.handlers.clear()

        # Create detailed formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console handler with color support
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler with rotation (if specified)
        if log_file:
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,  # 10MB max, 5 backups
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        # Performance tracking
        self.operation_times: Dict[str, List[float]] = {}

    def log_error(self, error: ErrorDetails) -> None:
        """Log an error with structured information."""
        error_dict = error.to_dict()
        extra_data = {k: v for k, v in error_dict.items() if k != "message"}
        extra_data["component"] = error.component

        self.logger.error(f"Error {error.error_id}: {error.message}", extra=extra_data)

    def log_validation_result(self, result: ValidationResult) -> None:
        """Log validation results with enhanced metrics."""
        extra_data = {"component": result.component}

        if result.is_valid:
            success_rate = result.get_success_rate()
            self.logger.info(
                f"Validation passed for {result.component} "
                f"({result.passed_checks}/{result.checked_items} checks passed, "
                f"{success_rate:.1f}% success rate) "
                f"in {result.validation_time:.2f}s",
                extra=extra_data,
            )
        else:
            self.logger.error(
                f"Validation failed for {result.component} "
                f"with {len(result.errors)} errors and {len(result.warnings)} warnings",
                extra=extra_data,
            )
            for error in result.errors:
                self.log_error(error)

    def log_pipeline_health(self, health: PipelineHealth) -> None:
        """Log comprehensive pipeline health information."""
        status = "HEALTHY" if health.is_healthy else "UNHEALTHY"
        extra_data = {"component": health.component}

        self.logger.info(
            f"Pipeline Health - {health.component}: {status} "
            f"(Score: {health.health_score:.1f}/100, "
            f"Success Rate: {health.success_rate:.1%}, "
            f"Consecutive Failures: {health.consecutive_failures}, "
            f"Avg Time: {health.average_execution_time:.2f}s)",
            extra=extra_data,
        )

    def log_performance_metrics(self, metrics: PerformanceMetrics) -> None:
        """Log performance metrics for a component."""
        extra_data = {"component": metrics.component}

        self.logger.info(
            f"Performance Metrics - {metrics.component}: "
            f"Executions: {metrics.total_executions}, "
            f"Success Rate: {metrics.get_success_rate():.1f}%, "
            f"Avg Time: {metrics.average_execution_time:.2f}s, "
            f"Throughput: {metrics.items_per_second:.2f} items/sec",
            extra=extra_data,
        )

    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        return self._OperationTimer(self, operation_name)

    class _OperationTimer:
        """Context manager for timing operations."""

        def __init__(self, logger: "KaspaPipelineLogger", operation_name: str):
            self.logger = logger
            self.operation_name = operation_name
            self.start_time = None

        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.start_time:
                execution_time = time.time() - self.start_time

                # Track operation times
                if self.operation_name not in self.logger.operation_times:
                    self.logger.operation_times[self.operation_name] = []
                self.logger.operation_times[self.operation_name].append(execution_time)

                # Log operation completion
                self.logger.logger.info(
                    f"Operation '{self.operation_name}' completed in {execution_time:.2f}s",
                    extra={"component": self.logger.component},
                )

    def get_operation_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all timed operations."""
        stats = {}
        for operation, times in self.operation_times.items():
            if times:
                stats[operation] = {
                    "count": len(times),
                    "total_time": sum(times),
                    "average_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                }
        return stats


class KaspaPipelineErrorHandler:
    """Comprehensive error handling system for the entire Kaspa Knowledge Pipeline."""

    def __init__(
        self,
        logger: Optional[KaspaPipelineLogger] = None,
        notification_config: Optional[NotificationConfig] = None,
    ):
        """
        Initialize the error handler.

        Args:
            logger: Optional logger instance
            notification_config: Optional notification configuration
        """
        self.logger = logger or KaspaPipelineLogger()
        self.error_counter = 0
        self.health_metrics: Dict[str, PipelineHealth] = {}
        self.error_history: List[ErrorDetails] = []

        # Initialize notification service
        self.notification_service = None
        if notification_config:
            self.notification_service = NotificationService(notification_config)

    def generate_error_id(self) -> str:
        """Generate unique error ID with timestamp."""
        self.error_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"KASPA_ERROR_{timestamp}_{self.error_counter:04d}"

    def create_error(
        self,
        message: str,
        severity: ErrorSeverity,
        category: ErrorCategory,
        exception: Optional[Exception] = None,
        component: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None,
        user_impact: str = "unknown",
    ) -> ErrorDetails:
        """
        Create structured error details with enhanced information.

        Args:
            message: Error message
            severity: Error severity level
            category: Error category
            exception: Optional exception object
            component: Component where error occurred
            context: Additional context information
            recovery_action: Suggested recovery action
            user_impact: Description of impact on users

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

        # Estimate fix time based on severity and category
        estimated_fix_time = self._estimate_fix_time(severity, category)

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
            user_impact=user_impact,
            estimated_fix_time=estimated_fix_time,
        )

        self.error_history.append(error)
        self.logger.log_error(error)

        # Send notification if configured
        if self.notification_service:
            self.notification_service.send_notification(error)

        return error

    def _estimate_fix_time(
        self, severity: ErrorSeverity, category: ErrorCategory
    ) -> str:
        """Estimate fix time based on error characteristics."""
        severity_times = {
            ErrorSeverity.CRITICAL: "1-2 hours",
            ErrorSeverity.HIGH: "2-4 hours",
            ErrorSeverity.MEDIUM: "4-8 hours",
            ErrorSeverity.LOW: "1-2 days",
            ErrorSeverity.INFO: "As needed",
        }

        # Adjust based on category complexity
        complex_categories = [
            ErrorCategory.AI_PROCESSING,
            ErrorCategory.GITHUB_API,
            ErrorCategory.EXTERNAL_DEPENDENCY,
        ]

        base_time = severity_times.get(severity, "Unknown")
        if category in complex_categories:
            return f"{base_time} (potentially longer due to external dependencies)"
        return base_time

    def handle_exception(
        self,
        exception: Exception,
        component: str,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        category: ErrorCategory = ErrorCategory.PIPELINE_EXECUTION,
        context: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None,
        user_impact: str = "Service degradation",
    ) -> ErrorDetails:
        """
        Handle an exception with comprehensive error creation.

        Args:
            exception: The exception to handle
            component: Component where exception occurred
            severity: Error severity level
            category: Error category
            context: Additional context information
            recovery_action: Suggested recovery action
            user_impact: Description of user impact

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
            user_impact=user_impact,
        )

    def update_component_health(
        self,
        component: str,
        is_success: bool,
        execution_time: float,
        error: Optional[ErrorDetails] = None,
        items_processed: int = 0,
        memory_usage: float = 0.0,
    ):
        """Update comprehensive health metrics for a component."""
        if component not in self.health_metrics:
            self.health_metrics[component] = PipelineHealth(
                component=component, is_healthy=True, last_check=datetime.now()
            )

        self.health_metrics[component].update_health(
            is_success, execution_time, error, items_processed, memory_usage
        )
        self.logger.log_pipeline_health(self.health_metrics[component])

    def get_component_health(self, component: str) -> Optional[PipelineHealth]:
        """Get health information for a specific component."""
        return self.health_metrics.get(component)

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report for the entire pipeline."""
        total_errors = len(self.error_history)
        recent_errors = len(
            [
                e
                for e in self.error_history
                if (datetime.now() - e.timestamp).seconds < 3600
            ]
        )
        critical_errors = len(
            [e for e in self.error_history if e.severity == ErrorSeverity.CRITICAL]
        )

        # Calculate overall pipeline health
        healthy_components = sum(
            1 for h in self.health_metrics.values() if h.is_healthy
        )
        total_components = len(self.health_metrics)
        overall_health_score = (
            (healthy_components / total_components * 100) if total_components > 0 else 0
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "overall_health": {
                "score": round(overall_health_score, 1),
                "is_healthy": overall_health_score >= 80,
                "healthy_components": healthy_components,
                "total_components": total_components,
            },
            "error_summary": {
                "total_errors": total_errors,
                "recent_errors_1h": recent_errors,
                "critical_errors": critical_errors,
                "error_rate_1h": round(
                    recent_errors / 1 if recent_errors > 0 else 0, 2
                ),
            },
            "component_health": {
                name: health.get_health_summary()
                for name, health in self.health_metrics.items()
            },
            "recent_critical_errors": [
                error.to_dict()
                for error in self.error_history[-5:]
                if error.severity == ErrorSeverity.CRITICAL
            ],
        }

    def get_error_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze error trends over specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = [e for e in self.error_history if e.timestamp > cutoff_time]

        # Group errors by component
        component_errors = {}
        category_errors = {}
        severity_errors = {}

        for error in recent_errors:
            # By component
            if error.component not in component_errors:
                component_errors[error.component] = 0
            component_errors[error.component] += 1

            # By category
            cat_name = error.category.value
            if cat_name not in category_errors:
                category_errors[cat_name] = 0
            category_errors[cat_name] += 1

            # By severity
            sev_name = error.severity.value
            if sev_name not in severity_errors:
                severity_errors[sev_name] = 0
            severity_errors[sev_name] += 1

        return {
            "time_period_hours": hours,
            "total_errors": len(recent_errors),
            "errors_by_component": component_errors,
            "errors_by_category": category_errors,
            "errors_by_severity": severity_errors,
            "most_problematic_component": (
                max(component_errors.items(), key=lambda x: x[1])[0]
                if component_errors
                else None
            ),
        }

    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check across all components."""
        health_check_results = {}

        for component_name, health in self.health_metrics.items():
            health_check_results[component_name] = {
                "status": "HEALTHY" if health.is_healthy else "UNHEALTHY",
                "health_score": health.health_score,
                "last_check": health.last_check.isoformat(),
                "issues": [],
            }

            # Check for specific issues
            if health.consecutive_failures >= 3:
                health_check_results[component_name]["issues"].append(
                    f"High consecutive failures: {health.consecutive_failures}"
                )

            if health.success_rate < 0.8:
                health_check_results[component_name]["issues"].append(
                    f"Low success rate: {health.success_rate:.1%}"
                )

            if health.average_execution_time > 300:  # 5 minutes
                health_check_results[component_name]["issues"].append(
                    f"High execution time: {health.average_execution_time:.1f}s"
                )

        return {
            "health_check_timestamp": datetime.now().isoformat(),
            "components": health_check_results,
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
        component: Component name for logging and health tracking
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = KaspaPipelineErrorHandler()

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
                        recovery_action=(
                            f"Retrying ({attempt + 1}/{max_retries})"
                            if attempt < max_retries
                            else "Manual intervention required"
                        ),
                    )
                    error.retry_count = attempt + 1

                    # Update health metrics on failure
                    error_handler.update_component_health(
                        component, False, execution_time, error
                    )

                    if attempt == max_retries:
                        # Final attempt failed
                        raise e

                    # Wait before retrying with exponential backoff
                    wait_time = backoff_factor**attempt
                    time.sleep(wait_time)

                    error_handler.logger.logger.warning(
                        f"Retry attempt {attempt + 1}/{max_retries} for {component} "
                        f"after {wait_time:.1f}s delay"
                    )

        return wrapper

    return decorator


class PipelineValidator:
    """Enhanced validation system for pipeline components."""

    def __init__(self, error_handler: Optional[KaspaPipelineErrorHandler] = None):
        """
        Initialize the validator.

        Args:
            error_handler: Optional error handler instance
        """
        self.error_handler = error_handler or KaspaPipelineErrorHandler()

    def validate_data_directory(
        self, data_dir: Path, component: str = "data_loader"
    ) -> ValidationResult:
        """Validate data directory structure with enhanced checks."""
        start_time = time.time()
        result = ValidationResult(is_valid=True, component=component)

        required_subdirs = ["aggregated", "briefings", "facts"]
        result.checked_items = len(required_subdirs)

        for subdir in required_subdirs:
            path = data_dir / subdir
            if not path.exists():
                error = self.error_handler.create_error(
                    f"Required directory '{subdir}' not found at {path}",
                    ErrorSeverity.HIGH,
                    ErrorCategory.DATA_VALIDATION,
                    component=component,
                    context={"directory": str(path), "parent_dir": str(data_dir)},
                    recovery_action=f"Create directory: mkdir -p {path}",
                )
                result.add_error(error)
            elif not path.is_dir():
                error = self.error_handler.create_error(
                    f"Path '{path}' exists but is not a directory",
                    ErrorSeverity.HIGH,
                    ErrorCategory.DATA_VALIDATION,
                    component=component,
                    context={"path": str(path)},
                    recovery_action=f"Remove file and create directory: rm {path} && mkdir -p {path}",
                )
                result.add_error(error)
            else:
                result.passed_checks += 1

        result.validation_time = time.time() - start_time
        return result

    def validate_json_structure(
        self,
        data: Dict[str, Any],
        required_fields: List[str],
        component: str = "data_validator",
    ) -> ValidationResult:
        """Validate JSON data structure with enhanced field checking."""
        start_time = time.time()
        result = ValidationResult(is_valid=True, component=component)

        result.checked_items = len(required_fields)

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
                        "data_size": len(data) if isinstance(data, dict) else 0,
                    },
                    recovery_action=f"Add required field '{field_name}' to JSON structure",
                )
                result.add_error(error)
            else:
                result.passed_checks += 1

        result.validation_time = time.time() - start_time
        return result

    def validate_output_file(
        self, file_path: Path, min_size: int = 1, component: str = "output_validator"
    ) -> ValidationResult:
        """Validate output file with enhanced size and content checks."""
        start_time = time.time()
        result = ValidationResult(is_valid=True, component=component)
        result.checked_items = 3  # existence, size, readability

        # Check file existence
        if not file_path.exists():
            error = self.error_handler.create_error(
                f"Output file not created: {file_path}",
                ErrorSeverity.HIGH,
                ErrorCategory.FILE_OPERATIONS,
                component=component,
                context={"file_path": str(file_path)},
                recovery_action="Check file creation logic and permissions",
            )
            result.add_error(error)
        else:
            result.passed_checks += 1

            # Check file size
            file_size = file_path.stat().st_size
            if file_size < min_size:
                error = self.error_handler.create_error(
                    f"Output file too small: {file_path} ({file_size} bytes)",
                    ErrorSeverity.MEDIUM,
                    ErrorCategory.FILE_OPERATIONS,
                    component=component,
                    context={
                        "file_path": str(file_path),
                        "file_size": file_size,
                        "min_size": min_size,
                    },
                    recovery_action="Check if file generation completed successfully",
                )
                result.add_error(error)
            else:
                result.passed_checks += 1

            # Check file readability
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    f.read(1)  # Try to read first character
                result.passed_checks += 1
            except Exception as e:
                error = self.error_handler.create_error(
                    f"Output file not readable: {file_path}",
                    ErrorSeverity.HIGH,
                    ErrorCategory.FILE_OPERATIONS,
                    component=component,
                    context={"file_path": str(file_path), "error": str(e)},
                    recovery_action="Check file permissions and encoding",
                )
                result.add_error(error)

        result.validation_time = time.time() - start_time
        return result


def create_pipeline_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    component: str = "kaspa_pipeline",
) -> KaspaPipelineLogger:
    """Create a configured pipeline logger."""
    return KaspaPipelineLogger(log_level, log_file, component)


def create_error_handler(
    logger: Optional[KaspaPipelineLogger] = None,
    notification_config: Optional[NotificationConfig] = None,
) -> KaspaPipelineErrorHandler:
    """Create a configured error handler."""
    return KaspaPipelineErrorHandler(logger, notification_config)


def create_validator(
    error_handler: Optional[KaspaPipelineErrorHandler] = None,
) -> PipelineValidator:
    """Create a configured validator."""
    return PipelineValidator(error_handler)


def run_with_monitoring(
    func: Callable,
    component: str,
    error_handler: Optional[KaspaPipelineErrorHandler] = None,
    **kwargs,
) -> Tuple[Any, Optional[ErrorDetails]]:
    """
    Run a function with comprehensive monitoring and error handling.

    Args:
        func: Function to run
        component: Component name for monitoring
        error_handler: Optional error handler
        **kwargs: Arguments to pass to function

    Returns:
        Tuple of (result, error_details)
    """
    handler = error_handler or KaspaPipelineErrorHandler()

    try:
        start_time = time.time()

        # Use the logger's timing context if available
        with handler.logger.time_operation(f"{component}.{func.__name__}"):
            result = func(**kwargs)

        execution_time = time.time() - start_time
        handler.update_component_health(component, True, execution_time)

        return result, None

    except Exception as e:
        execution_time = time.time() - start_time
        error = handler.handle_exception(
            e,
            component,
            context={"function": func.__name__, "kwargs": list(kwargs.keys())},
            recovery_action="Check function parameters and dependencies",
        )
        handler.update_component_health(component, False, execution_time, error)

        return None, error


def setup_monitoring_from_env() -> (
    Tuple[KaspaPipelineLogger, KaspaPipelineErrorHandler]
):
    """Set up monitoring system from environment variables."""
    # Get configuration from environment
    log_level = os.getenv("KASPA_LOG_LEVEL", "INFO")
    log_file = os.getenv("KASPA_LOG_FILE")

    # Create logger
    logger = create_pipeline_logger(log_level, log_file)

    # Set up notification configuration
    notification_config = None
    if os.getenv("KASPA_NOTIFICATIONS_ENABLED", "false").lower() == "true":
        notification_config = NotificationConfig(
            enabled=True,
            channels=[NotificationChannel.CONSOLE, NotificationChannel.FILE],
            email_smtp_host=os.getenv("KASPA_SMTP_HOST", "smtp.gmail.com"),
            email_smtp_port=int(os.getenv("KASPA_SMTP_PORT", "587")),
            email_username=os.getenv("KASPA_EMAIL_USERNAME", ""),
            email_password=os.getenv("KASPA_EMAIL_PASSWORD", ""),
            email_from=os.getenv("KASPA_EMAIL_FROM", ""),
            email_to=(
                os.getenv("KASPA_EMAIL_TO", "").split(",")
                if os.getenv("KASPA_EMAIL_TO")
                else []
            ),
            webhook_url=os.getenv("KASPA_WEBHOOK_URL", ""),
        )

        # Add email channel if configured
        if notification_config.email_username and notification_config.email_to:
            notification_config.channels.append(NotificationChannel.EMAIL)

        # Add webhook channel if configured
        if notification_config.webhook_url:
            notification_config.channels.append(NotificationChannel.WEBHOOK)

    # Create error handler
    error_handler = create_error_handler(logger, notification_config)

    return logger, error_handler


# Example usage and testing
if __name__ == "__main__":
    # Test the monitoring system
    logger, error_handler = setup_monitoring_from_env()
    validator = create_validator(error_handler)

    # Test error handling
    try:
        raise ValueError("Test error for monitoring system")
    except Exception as e:
        error_handler.handle_exception(
            e,
            "test_component",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.PIPELINE_EXECUTION,
            recovery_action="This is a test - no action needed",
        )

    # Test validation
    result = validator.validate_data_directory(Path("data"))
    logger.log_validation_result(result)

    # Test health check
    health_check = error_handler.run_health_check()
    print("\nHealth Check Results:")
    print(json.dumps(health_check, indent=2))

    # Test comprehensive health report
    health_report = error_handler.get_health_report()
    print("\nFull Health Report:")
    print(json.dumps(health_report, indent=2))
