"""
Configuration module for Kaspa Pipeline Monitoring System

This module provides configuration management for the monitoring, logging,
and alerting systems with environment variable support and sensible defaults.
"""

import os
from typing import List, Optional
from pathlib import Path

from .error_handler import NotificationConfig, NotificationChannel, ErrorSeverity


class MonitoringConfig:
    """Configuration for the entire monitoring system."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        # Logging configuration
        self.log_level = os.getenv("KASPA_LOG_LEVEL", "INFO").upper()
        self.log_file = os.getenv("KASPA_LOG_FILE")
        self.enable_console_logging = (
            os.getenv("KASPA_CONSOLE_LOGGING", "true").lower() == "true"
        )
        self.enable_file_logging = (
            os.getenv("KASPA_FILE_LOGGING", "true").lower() == "true"
        )

        # Default log file if file logging is enabled but no file specified
        if self.enable_file_logging and not self.log_file:
            log_dir = Path("monitoring/logs")
            log_dir.mkdir(exist_ok=True)
            self.log_file = str(log_dir / "kaspa_pipeline.log")

        # Health monitoring configuration
        self.health_check_interval = int(
            os.getenv("KASPA_HEALTH_CHECK_INTERVAL", "300")
        )  # 5 minutes
        self.component_timeout = int(
            os.getenv("KASPA_COMPONENT_TIMEOUT", "1800")
        )  # 30 minutes
        self.max_error_history = int(os.getenv("KASPA_MAX_ERROR_HISTORY", "1000"))

        # Performance monitoring
        self.enable_performance_tracking = (
            os.getenv("KASPA_PERFORMANCE_TRACKING", "true").lower() == "true"
        )
        self.performance_sampling_rate = float(
            os.getenv("KASPA_PERFORMANCE_SAMPLING", "1.0")
        )  # 100% by default

        # Notification configuration
        self.notification_config = self._create_notification_config()

        # Retry configuration
        self.default_max_retries = int(os.getenv("KASPA_MAX_RETRIES", "3"))
        self.default_backoff_factor = float(os.getenv("KASPA_BACKOFF_FACTOR", "2.0"))
        self.retry_timeout = int(
            os.getenv("KASPA_RETRY_TIMEOUT", "300")
        )  # 5 minutes total retry time

        # Validation configuration
        self.strict_validation = (
            os.getenv("KASPA_STRICT_VALIDATION", "false").lower() == "true"
        )
        self.validation_timeout = int(
            os.getenv("KASPA_VALIDATION_TIMEOUT", "60")
        )  # 1 minute

    def _create_notification_config(self) -> Optional[NotificationConfig]:
        """Create notification configuration from environment variables."""
        if not self._is_notifications_enabled():
            return None

        channels = self._get_notification_channels()

        config = NotificationConfig(
            enabled=True,
            channels=channels,
            # Email configuration
            email_smtp_host=os.getenv("KASPA_SMTP_HOST", "smtp.gmail.com"),
            email_smtp_port=int(os.getenv("KASPA_SMTP_PORT", "587")),
            email_username=os.getenv("KASPA_EMAIL_USERNAME", ""),
            email_password=os.getenv("KASPA_EMAIL_PASSWORD", ""),
            email_from=os.getenv("KASPA_EMAIL_FROM", ""),
            email_to=self._parse_email_list(os.getenv("KASPA_EMAIL_TO", "")),
            # Webhook configuration
            webhook_url=os.getenv("KASPA_WEBHOOK_URL", ""),
            webhook_headers=self._parse_webhook_headers(),
            # Notification thresholds
            notify_on_severities=self._get_notification_severities(),
            # Rate limiting
            max_notifications_per_hour=int(
                os.getenv("KASPA_MAX_NOTIFICATIONS_HOUR", "10")
            ),
            cooldown_period_minutes=int(os.getenv("KASPA_NOTIFICATION_COOLDOWN", "15")),
        )

        return config

    def _is_notifications_enabled(self) -> bool:
        """Check if notifications are enabled."""
        return os.getenv("KASPA_NOTIFICATIONS_ENABLED", "false").lower() == "true"

    def _get_notification_channels(self) -> List[NotificationChannel]:
        """Get configured notification channels."""
        channels = []

        # Console notifications (always enabled if notifications are on)
        channels.append(NotificationChannel.CONSOLE)

        # File notifications (always enabled if notifications are on)
        channels.append(NotificationChannel.FILE)

        # Email notifications (if configured)
        if (
            os.getenv("KASPA_EMAIL_USERNAME")
            and os.getenv("KASPA_EMAIL_TO")
            and os.getenv("KASPA_EMAIL_ENABLED", "false").lower() == "true"
        ):
            channels.append(NotificationChannel.EMAIL)

        # Webhook notifications (if configured)
        if (
            os.getenv("KASPA_WEBHOOK_URL")
            and os.getenv("KASPA_WEBHOOK_ENABLED", "false").lower() == "true"
        ):
            channels.append(NotificationChannel.WEBHOOK)

        return channels

    def _parse_email_list(self, email_string: str) -> List[str]:
        """Parse comma-separated email list."""
        if not email_string:
            return []
        return [email.strip() for email in email_string.split(",") if email.strip()]

    def _parse_webhook_headers(self) -> dict:
        """Parse webhook headers from environment."""
        headers = {}

        # Parse KASPA_WEBHOOK_HEADERS in format "key1:value1,key2:value2"
        headers_string = os.getenv("KASPA_WEBHOOK_HEADERS", "")
        if headers_string:
            for header_pair in headers_string.split(","):
                if ":" in header_pair:
                    key, value = header_pair.split(":", 1)
                    headers[key.strip()] = value.strip()

        # Add content type if not specified
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        return headers

    def _get_notification_severities(self) -> List[ErrorSeverity]:
        """Get severities that should trigger notifications."""
        severity_string = os.getenv("KASPA_NOTIFICATION_SEVERITIES", "critical,high")
        severities = []

        severity_map = {
            "critical": ErrorSeverity.CRITICAL,
            "high": ErrorSeverity.HIGH,
            "medium": ErrorSeverity.MEDIUM,
            "low": ErrorSeverity.LOW,
            "info": ErrorSeverity.INFO,
        }

        for severity_name in severity_string.lower().split(","):
            severity_name = severity_name.strip()
            if severity_name in severity_map:
                severities.append(severity_map[severity_name])

        # Default to critical and high if nothing configured
        if not severities:
            severities = [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]

        return severities

    def get_component_config(self, component_name: str) -> dict:
        """Get component-specific configuration."""
        # Component-specific overrides
        prefix = f"KASPA_{component_name.upper()}_"

        return {
            "max_retries": int(
                os.getenv(f"{prefix}MAX_RETRIES", str(self.default_max_retries))
            ),
            "backoff_factor": float(
                os.getenv(f"{prefix}BACKOFF_FACTOR", str(self.default_backoff_factor))
            ),
            "timeout": int(os.getenv(f"{prefix}TIMEOUT", str(self.component_timeout))),
            "log_level": os.getenv(f"{prefix}LOG_LEVEL", self.log_level),
            "enabled": os.getenv(f"{prefix}ENABLED", "true").lower() == "true",
        }

    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []

        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            issues.append(
                f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}"
            )

        # Validate log file path if specified
        if self.log_file:
            log_path = Path(self.log_file)
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create log directory {log_path.parent}: {e}")

        # Validate notification configuration
        if self.notification_config:
            if NotificationChannel.EMAIL in self.notification_config.channels:
                if not self.notification_config.email_username:
                    issues.append(
                        "Email notifications enabled but KASPA_EMAIL_USERNAME not set"
                    )
                if not self.notification_config.email_to:
                    issues.append(
                        "Email notifications enabled but KASPA_EMAIL_TO not set"
                    )

            if NotificationChannel.WEBHOOK in self.notification_config.channels:
                if not self.notification_config.webhook_url:
                    issues.append(
                        "Webhook notifications enabled but KASPA_WEBHOOK_URL not set"
                    )

        # Validate numeric ranges
        if self.health_check_interval < 60:
            issues.append("Health check interval should be at least 60 seconds")

        if self.performance_sampling_rate < 0 or self.performance_sampling_rate > 1:
            issues.append("Performance sampling rate must be between 0.0 and 1.0")

        return issues

    def to_dict(self) -> dict:
        """Convert configuration to dictionary for logging/debugging."""
        return {
            "logging": {
                "log_level": self.log_level,
                "log_file": self.log_file,
                "console_logging": self.enable_console_logging,
                "file_logging": self.enable_file_logging,
            },
            "monitoring": {
                "health_check_interval": self.health_check_interval,
                "component_timeout": self.component_timeout,
                "max_error_history": self.max_error_history,
                "performance_tracking": self.enable_performance_tracking,
                "performance_sampling_rate": self.performance_sampling_rate,
            },
            "notifications": {
                "enabled": self.notification_config is not None,
                "channels": (
                    [c.value for c in self.notification_config.channels]
                    if self.notification_config
                    else []
                ),
                "severities": (
                    [s.value for s in self.notification_config.notify_on_severities]
                    if self.notification_config
                    else []
                ),
            },
            "retry": {
                "max_retries": self.default_max_retries,
                "backoff_factor": self.default_backoff_factor,
                "timeout": self.retry_timeout,
            },
            "validation": {
                "strict_validation": self.strict_validation,
                "validation_timeout": self.validation_timeout,
            },
        }


def load_monitoring_config() -> MonitoringConfig:
    """Load and validate monitoring configuration."""
    config = MonitoringConfig()

    # Validate configuration
    issues = config.validate_config()
    if issues:
        print("Configuration warnings:")
        for issue in issues:
            print(f"  - {issue}")

    return config


def create_example_env_file(filename: str = "monitoring/.env.example") -> None:
    """Create an example environment file with all monitoring configuration options."""
    example_content = """# Kaspa Pipeline Monitoring Configuration

# === LOGGING CONFIGURATION ===
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
KASPA_LOG_LEVEL=INFO

# Log file path (optional, defaults to monitoring/logs/kaspa_pipeline.log)
KASPA_LOG_FILE=monitoring/logs/kaspa_pipeline.log

# Enable console/file logging
KASPA_CONSOLE_LOGGING=true
KASPA_FILE_LOGGING=true

# === HEALTH MONITORING ===
# Health check interval in seconds
KASPA_HEALTH_CHECK_INTERVAL=300

# Component timeout in seconds  
KASPA_COMPONENT_TIMEOUT=1800

# Maximum error history to keep
KASPA_MAX_ERROR_HISTORY=1000

# === PERFORMANCE MONITORING ===
# Enable performance tracking
KASPA_PERFORMANCE_TRACKING=true

# Performance sampling rate (0.0 to 1.0)
KASPA_PERFORMANCE_SAMPLING=1.0

# === NOTIFICATIONS ===
# Enable notifications
KASPA_NOTIFICATIONS_ENABLED=false

# Notification severities (comma-separated: critical,high,medium,low,info)
KASPA_NOTIFICATION_SEVERITIES=critical,high

# Rate limiting
KASPA_MAX_NOTIFICATIONS_HOUR=10
KASPA_NOTIFICATION_COOLDOWN=15

# === EMAIL NOTIFICATIONS ===
KASPA_EMAIL_ENABLED=false
KASPA_SMTP_HOST=smtp.gmail.com
KASPA_SMTP_PORT=587
KASPA_EMAIL_USERNAME=your-email@gmail.com
KASPA_EMAIL_PASSWORD=your-app-password
KASPA_EMAIL_FROM=kaspa-pipeline@yourorganization.com
KASPA_EMAIL_TO=admin@yourorganization.com,devops@yourorganization.com

# === WEBHOOK NOTIFICATIONS ===
KASPA_WEBHOOK_ENABLED=false
KASPA_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
KASPA_WEBHOOK_HEADERS=Authorization:Bearer token,X-Custom-Header:value

# === RETRY CONFIGURATION ===
# Default retry settings
KASPA_MAX_RETRIES=3
KASPA_BACKOFF_FACTOR=2.0
KASPA_RETRY_TIMEOUT=300

# === VALIDATION ===
KASPA_STRICT_VALIDATION=false
KASPA_VALIDATION_TIMEOUT=60

# === COMPONENT-SPECIFIC OVERRIDES ===
# You can override settings for specific components using the pattern:
# KASPA_{COMPONENT_NAME}_{SETTING}

# Examples:
# KASPA_GITHUB_INGEST_MAX_RETRIES=5
# KASPA_AI_PROCESSING_TIMEOUT=3600
# KASPA_DATA_LOADER_LOG_LEVEL=DEBUG
"""

    # Create the monitoring directory if it doesn't exist
    Path(filename).parent.mkdir(exist_ok=True)

    with open(filename, "w") as f:
        f.write(example_content)


if __name__ == "__main__":
    # Create example configuration file
    create_example_env_file()
    print("Created monitoring/.env.example")

    # Load and display current configuration
    config = load_monitoring_config()
    print("\nCurrent Configuration:")
    import json

    print(json.dumps(config.to_dict(), indent=2))
