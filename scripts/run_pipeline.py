#!/usr/bin/env python3
"""
Kaspa Knowledge Hub Pipeline Runner

This script orchestrates the complete data pipeline process with comprehensive
resource management for large temporal chunks processing:

1. Period-based data ingestion from multiple sources
2. Resource-managed aggregation of raw sources
3. AI-powered content generation with memory monitoring
4. RAG document generation with chunked processing
5. Comprehensive error handling and recovery mechanisms

Features:
- Memory usage monitoring and limits
- Chunked processing for large temporal datasets
- Resource exhaustion detection and graceful degradation
- Retry mechanisms with exponential backoff
- Progress tracking for long-running operations
- Enhanced disk space monitoring
- Recovery mechanisms for failed operations
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

# Import the new monitoring system
from monitoring import (
    setup_monitoring_from_env,
    ErrorSeverity,
    ErrorCategory,
)

# Import resource management
from scripts.resource_manager import (
    ResourceMonitor,
    check_resources,
    retry_operation,
)

# Configure basic logging for pipeline operations
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize global monitoring system
LOGGER = None
ERROR_HANDLER = None


def initialize_monitoring():
    """Initialize the global monitoring system."""
    global LOGGER, ERROR_HANDLER
    LOGGER, ERROR_HANDLER = setup_monitoring_from_env()

    # Log pipeline startup
    LOGGER.logger.info("Kaspa Knowledge Pipeline initialized with monitoring system")
    return LOGGER, ERROR_HANDLER


def get_available_source_date_range() -> Tuple[str, str]:
    """
    Determine the available date range from source files.
    Returns tuple of (earliest_date, latest_date) in YYYY-MM-DD format.
    """
    sources_dir = Path("sources")
    all_dates = set()

    # Check all source subdirectories for date files
    source_subdirs = ["medium", "telegram", "github", "forum"]

    for subdir in source_subdirs:
        source_path = sources_dir / subdir
        if source_path.exists():
            for file_path in source_path.glob("*.json"):
                # Extract date from filename (YYYY-MM-DD.json)
                if file_path.stem.count("-") == 2:  # Valid date format
                    try:
                        # Validate it's a proper date
                        datetime.strptime(file_path.stem, "%Y-%m-%d")
                        all_dates.add(file_path.stem)
                    except ValueError:
                        continue  # Skip non-date files

    if not all_dates:
        # Default to last 30 days if no source files found
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    sorted_dates = sorted(all_dates)
    return sorted_dates[0], sorted_dates[-1]


def get_backfill_date_range(days_back: int = None) -> Tuple[str, str]:
    """
    Calculate date range for backfill or days-back processing.

    Args:
        days_back: Number of days back from today. If None, uses all available data.

    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format.
    """
    if days_back is not None:
        # Use specified days back from today
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
    else:
        # Use all available source data for backfill
        return get_available_source_date_range()


def get_period_chunks(
    start_date: str, end_date: str, period: str = "monthly"
) -> List[Tuple[str, str, str]]:
    """
    Generate period chunks between start_date and end_date.
    Returns list of tuples: (period_start, period_end, period_label)
    """
    from calendar import monthrange

    chunks = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if period == "weekly":
        # Start from the Monday of the week containing start_date
        current = start - timedelta(days=start.weekday())

        while current <= end:
            week_end = current + timedelta(days=6)
            # Don't go beyond the requested end date
            actual_end = min(week_end, end)

            # Only include if the week overlaps with our date range
            if current <= end and actual_end >= start:
                period_start = max(current, start).strftime("%Y-%m-%d")
                period_end = actual_end.strftime("%Y-%m-%d")
                week_label = f"{current.strftime('%Y-W%U')}"
                chunks.append((period_start, period_end, week_label))

            current = week_end + timedelta(days=1)

    elif period == "monthly":
        current = start.replace(day=1)  # Start of the month

        while current <= end:
            # Last day of the current month
            last_day = monthrange(current.year, current.month)[1]
            month_end = current.replace(day=last_day)

            # Don't go beyond the requested end date
            actual_end = min(month_end, end)

            # Only include if the month overlaps with our date range
            if current <= end and actual_end >= start:
                period_start = max(current, start).strftime("%Y-%m-%d")
                period_end = actual_end.strftime("%Y-%m-%d")
                month_label = current.strftime("%Y-%m")
                chunks.append((period_start, period_end, month_label))

            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

    return chunks


def get_date_range(start_date: str, end_date: str) -> List[str]:
    """
    Generate a list of dates between start_date and end_date (inclusive).

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of date strings in YYYY-MM-DD format
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return dates


def run_command(
    command: str,
    description: str,
    component: str = "pipeline_runner",
    required: bool = True,
    timeout: int = 1800,
) -> Tuple[bool, str]:
    """
    Run a command with comprehensive monitoring and error handling.

    Args:
        command: Command to execute
        description: Human-readable description of the command
        component: Component name for monitoring
        required: Whether this command is required for pipeline success
        timeout: Command timeout in seconds

    Returns:
        Tuple of (success: bool, status: str)
    """
    if not LOGGER or not ERROR_HANDLER:
        initialize_monitoring()

    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        with LOGGER.time_operation(
            f"{component}.{description.replace(' ', '_').lower()}"
        ):
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
                timeout=timeout,
            )

        execution_time = time.time() - start_time

        # Log command output
        if result.stdout:
            print(result.stdout)
            LOGGER.logger.debug(f"Command stdout: {result.stdout[:500]}...")

        if result.stderr:
            print(f"⚠️  stderr: {result.stderr}")
            LOGGER.logger.warning(f"Command stderr: {result.stderr[:500]}...")

        # Determine success and status
        if result.returncode == 0:
            print(f"✅ {description} completed successfully in {execution_time:.2f}s")

            # Update health metrics on success
            ERROR_HANDLER.update_component_health(
                component, True, execution_time, items_processed=1
            )

            LOGGER.logger.info(
                f"Command succeeded: {description} (exit code: {result.returncode}, "
                f"time: {execution_time:.2f}s)"
            )
            return True, "success"

        elif result.returncode == 2 and any(
            ingest_cmd in command
            for ingest_cmd in [
                "medium_ingest",
                "telegram_ingest",
                "github_ingest",
                "discourse_ingest",
            ]
        ):
            print(
                f"ℹ️  {description} found no new content - "
                "skipping downstream processing"
            )

            # This is still considered a success
            ERROR_HANDLER.update_component_health(
                component, True, execution_time, items_processed=0
            )

            LOGGER.logger.info(
                f"Command completed with no new content: {description} "
                f"(exit code: {result.returncode}, time: {execution_time:.2f}s)"
            )
            return True, "no_new_content"

        else:
            # Command failed
            error_message = f"{description} failed with return code {result.returncode}"
            print(f"❌ {error_message}")

            # Create detailed error information
            error = ERROR_HANDLER.create_error(
                message=error_message,
                severity=ErrorSeverity.HIGH if required else ErrorSeverity.MEDIUM,
                category=ErrorCategory.PIPELINE_EXECUTION,
                component=component,
                context={
                    "command": command,
                    "return_code": result.returncode,
                    "execution_time": execution_time,
                    "stdout": result.stdout[:1000] if result.stdout else None,
                    "stderr": result.stderr[:1000] if result.stderr else None,
                },
                recovery_action=f"Check command syntax and dependencies for: {command}",
                user_impact=(
                    "Pipeline step failed" if required else "Optional step failed"
                ),
            )

            # Update health metrics on failure
            ERROR_HANDLER.update_component_health(
                component, False, execution_time, error
            )

            return False, "failed"

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        error_message = f"{description} timed out after {timeout} seconds"
        print(f"⏰ {error_message}")

        # Create timeout error
        error = ERROR_HANDLER.create_error(
            message=error_message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PIPELINE_EXECUTION,
            component=component,
            context={
                "command": command,
                "timeout": timeout,
                "execution_time": execution_time,
            },
            recovery_action="Increase timeout or check for hanging processes",
            user_impact="Pipeline step timed out",
        )

        ERROR_HANDLER.update_component_health(component, False, execution_time, error)
        return False, "timeout"

    except Exception as e:
        execution_time = time.time() - start_time
        error_message = f"Error running {description}: {str(e)}"
        print(f"❌ {error_message}")

        # Handle unexpected exceptions
        error = ERROR_HANDLER.handle_exception(
            e,
            component,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PIPELINE_EXECUTION,
            context={
                "command": command,
                "description": description,
                "execution_time": execution_time,
            },
            recovery_action="Check system resources and command syntax",
            user_impact="Pipeline step failed unexpectedly",
        )

        ERROR_HANDLER.update_component_health(component, False, execution_time, error)
        return False, "error"


def run_full_pipeline(
    backfill=False,
    days_back=None,
    period=None,
    force=False,
    processing_mode="daily",
    start_date=None,
    end_date=None,
):
    """
    Run the complete pipeline process with comprehensive resource management.

    This function orchestrates all pipeline stages with monitoring, error handling,
    and resource management for large temporal chunks.
    """

    # Initialize resource management
    # resource_manager = LargeDatasetManager(".")  # For future large dataset operations
    resource_monitor = ResourceMonitor()

    # Initial resource check
    resource_report = check_resources(".")
    logger.info("=== PIPELINE START - Resource Check ===")
    logger.info(f"Memory status: {resource_report['memory']['message']}")
    logger.info(f"Disk status: {resource_report['disk']['message']}")

    if not resource_report["overall_safe"]:
        logger.warning("Resource warnings detected before pipeline start!")
        logger.warning(
            "Consider freeing up resources before proceeding with large temporal chunks"
        )

    pipeline_start_time = time.time()

    try:
        # Determine date range
        if processing_mode == "daily":
            if days_back is None:
                start_date = end_date = datetime.now().strftime("%Y-%m-%d")
            else:
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=days_back)).strftime(
                    "%Y-%m-%d"
                )
        elif processing_mode == "period":
            # start_date and end_date should already be set
            pass

        logger.info(f"Pipeline processing range: {start_date} to {end_date}")
        logger.info(f"Processing mode: {processing_mode}")

        # Step 1: Ingest raw data from sources with resource management
        logger.info("=== STEP 1: Data Ingestion with Resource Management ===")

        # Calculate days_back for ingestion based on date range
        if processing_mode == "daily":
            ingestion_days_back = days_back if days_back is not None else 7
        else:
            # For backfill or days_back mode, calculate total days needed
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            ingestion_days_back = (end_dt - start_dt).days + 1

            # Add some buffer to ensure we capture all data
            ingestion_days_back = max(ingestion_days_back, 7)

        force_flag = " --force" if force else ""
        days_back_flag = f" --days-back {ingestion_days_back}"

        # Run ingestion with resource monitoring
        ingestion_commands = [
            f"python -m scripts.medium_ingest{days_back_flag}{force_flag}",
            f"python -m scripts.telegram_ingest{days_back_flag}{force_flag}",
            f"python -m scripts.github_ingest{days_back_flag}{force_flag}",
            f"python -m scripts.forum_ingest{days_back_flag}{force_flag}",
        ]

        for cmd in ingestion_commands:
            try:
                # Check resources before each ingestion command
                resource_report = resource_monitor.get_resource_report(".")
                if not resource_report["memory"]["is_safe"]:
                    logger.warning(
                        f"Memory warning before {cmd}: "
                        f"{resource_report['memory']['message']}"
                    )

                    # Try garbage collection before proceeding
                    freed = resource_monitor.trigger_gc()
                    if freed > 0:
                        logger.info(
                            f"Freed {freed / (1024**3):.2f}GB through "
                            f"garbage collection"
                        )

                # Execute with retry mechanism
                retry_operation(_run_command_safely, cmd, timeout=1200)
                logger.info(f"Ingestion completed: {cmd}")

            except Exception as e:
                logger.error(f"Ingestion failed for {cmd}: {e}")
                # Continue with other ingestion commands
                continue

        # Check resources after ingestion
        post_ingestion_report = resource_monitor.get_resource_report(".")
        logger.info(
            f"Post-ingestion memory: {post_ingestion_report['memory']['message']}"
        )

        # Step 2: Aggregate sources with resource management
        logger.info("=== STEP 2: Source Aggregation with Resource Management ===")

        if processing_mode == "daily":
            # Daily aggregation
            agg_cmd = f"python -m scripts.aggregate_sources --date {end_date}"
            if force:
                agg_cmd += " --force"

            try:
                retry_operation(_run_command_safely, agg_cmd, timeout=1800)
                logger.info("Daily aggregation completed successfully")
            except Exception as e:
                logger.error(f"Daily aggregation failed: {e}")
                raise

        elif processing_mode == "period":
            # Period-based aggregation with chunked processing
            period_chunks = get_period_chunks(start_date, end_date, period)

            logger.info(f"Processing {len(period_chunks)} period chunks")

            successful_chunks = 0
            failed_chunks = []

            for chunk_start, chunk_end, period_label in period_chunks:
                try:
                    # Check resources before processing each chunk
                    resource_report = resource_monitor.get_resource_report(".")

                    if not resource_report["overall_safe"]:
                        logger.warning(
                            f"Resource warning before chunk {period_label}: "
                            f"{resource_report['memory']['message']}"
                        )

                        # Try to free memory
                        freed = resource_monitor.trigger_gc()
                        if freed > 0:
                            logger.info(
                                f"Freed {freed / (1024**3):.2f}GB before "
                                f"processing chunk {period_label}"
                            )

                        # Re-check resources
                        resource_report = resource_monitor.get_resource_report(".")
                        if not resource_report["memory"]["is_safe"]:
                            if resource_report["memory"]["level"] == "ABORT":
                                logger.error(
                                    f"Memory usage too high to process chunk "
                                    f"{period_label}: "
                                    f"{resource_report['memory']['message']}"
                                )
                                failed_chunks.append(
                                    (period_label, "Memory exhaustion")
                                )
                                continue

                    logger.info(
                        f"Processing chunk: {period_label} "
                        f"({chunk_start} to {chunk_end})"
                    )

                    # Process daily aggregations for the chunk
                    for date in get_date_range(chunk_start, chunk_end):
                        agg_cmd = f"python -m scripts.aggregate_sources --date {date}"
                        if force:
                            agg_cmd += " --force"

                        try:
                            retry_operation(_run_command_safely, agg_cmd, timeout=900)
                        except Exception as e:
                            logger.warning(f"Daily aggregation failed for {date}: {e}")
                            # Continue with other dates in the chunk
                            continue

                    # Aggregate the period data
                    period_agg_cmd = (
                        f"python -m scripts.aggregate_sources "
                        f"--start-date {chunk_start} "
                        f"--end-date {chunk_end} --period {period}"
                    )
                    if force:
                        period_agg_cmd += " --force"

                    retry_operation(_run_command_safely, period_agg_cmd, timeout=1800)
                    successful_chunks += 1
                    logger.info(f"Chunk {period_label} completed successfully")

                except Exception as e:
                    logger.error(f"Chunk {period_label} failed: {e}")
                    failed_chunks.append((period_label, str(e)))
                    continue

            logger.info(
                f"Period aggregation completed: "
                f"{successful_chunks}/{len(period_chunks)} chunks successful"
            )
            if failed_chunks:
                logger.warning(f"Failed chunks: {failed_chunks}")

        # Check resources after aggregation
        post_aggregation_report = resource_monitor.get_resource_report(".")
        logger.info(
            f"Post-aggregation memory: "
            f"{post_aggregation_report['memory']['message']}"
        )

        # Step 3: AI Processing with resource management
        logger.info("=== STEP 3: AI Processing with Resource Management ===")

        # Generate briefings with memory monitoring
        if processing_mode == "daily":
            briefing_cmd = f"python -m scripts.generate_briefing --date {end_date}"
        else:
            briefing_cmd = (
                f"python -m scripts.generate_briefing --start-date {start_date} "
                f"--end-date {end_date} --period-summary"
            )

        if force:
            briefing_cmd += " --force"

        try:
            # Check resources before AI processing
            resource_report = resource_monitor.get_resource_report(".")
            if not resource_report["memory"]["is_safe"]:
                logger.warning(
                    f"Memory warning before AI processing: "
                    f"{resource_report['memory']['message']}"
                )

                # Free memory before AI processing
                freed = resource_monitor.trigger_gc()
                if freed > 0:
                    logger.info(f"Freed {freed / (1024**3):.2f}GB before AI processing")

            retry_operation(_run_command_safely, briefing_cmd, timeout=3600)
            logger.info("Briefing generation completed")
        except Exception as e:
            logger.error(f"Briefing generation failed: {e}")
            # Continue with other steps

        # Generate facts with memory monitoring
        if processing_mode == "daily":
            facts_cmd = f"python -m scripts.extract_facts --date {end_date}"
        else:
            facts_cmd = (
                f"python -m scripts.extract_facts --start-date {start_date} "
                f"--end-date {end_date} --period-summary"
            )

        if force:
            facts_cmd += " --force"

        try:
            retry_operation(_run_command_safely, facts_cmd, timeout=3600)
            logger.info("Facts extraction completed")
        except Exception as e:
            logger.error(f"Facts extraction failed: {e}")
            # Continue with other steps

        # Step 4: RAG Document Generation with resource management
        logger.info("=== STEP 4: RAG Document Generation with Resource Management ===")

        if processing_mode == "daily":
            rag_cmd = f"python -m scripts.generate_rag_document --date {end_date}"
        else:
            rag_cmd = (
                f"python -m scripts.generate_rag_document --start-date {start_date} "
                f"--end-date {end_date} --split-output"
            )

        if force:
            rag_cmd += " --force"

        try:
            # Final resource check before RAG generation
            resource_report = resource_monitor.get_resource_report(".")
            if not resource_report["overall_safe"]:
                logger.warning(
                    f"Resource warning before RAG generation: "
                    f"{resource_report['memory']['message']}"
                )

            retry_operation(_run_command_safely, rag_cmd, timeout=2400)
            logger.info("RAG document generation completed")
        except Exception as e:
            logger.error(f"RAG document generation failed: {e}")

        # Pipeline completion report with resource usage
        pipeline_end_time = time.time()
        total_time = pipeline_end_time - pipeline_start_time

        final_resource_report = resource_monitor.get_resource_report(".")

        logger.info("=== PIPELINE COMPLETION REPORT ===")
        logger.info(
            f"Total pipeline time: {total_time:.2f} seconds "
            f"({total_time/60:.1f} minutes)"
        )
        logger.info(
            f"Peak memory usage: {final_resource_report['memory']['peak_gb']:.2f}GB"
        )
        logger.info(
            f"Final memory status: {final_resource_report['memory']['message']}"
        )
        logger.info(f"Disk status: {final_resource_report['disk']['message']}")

        # Display period-based output structure
        if processing_mode == "period":
            _display_period_output_structure(start_date, end_date, period)
        else:
            _display_daily_output_structure(end_date)

        return "Pipeline completed successfully with resource management"

    except Exception as e:
        # Pipeline-level error handling
        logger.error(f"Pipeline failed with error: {e}")

        # Get final resource state for debugging
        try:
            error_resource_report = resource_monitor.get_resource_report(".")
            logger.error(
                f"Error state - Memory: {error_resource_report['memory']['message']}"
            )
            logger.error(
                f"Error state - Disk: {error_resource_report['disk']['message']}"
            )
        except Exception:
            logger.error(
                "Could not retrieve resource information during error handling"
            )

        raise


def _run_command_safely(command, timeout=300):
    """
    Run a command with resource monitoring and timeout.

    Args:
        command: Command string to execute
        timeout: Maximum execution time in seconds

    Returns:
        subprocess.CompletedProcess result

    Raises:
        Exception: If command fails or times out
    """
    logger.info(f"Executing: {command}")

    try:
        result = subprocess.run(
            command.split(), capture_output=True, text=True, timeout=timeout, check=True
        )

        if result.stdout:
            logger.debug(f"Command output: {result.stdout}")

        return result

    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {command}")
        raise Exception(f"Command timeout: {command}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}: {command}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr}")
        raise Exception(f"Command failed: {command} (exit code {e.returncode})")

    except Exception as e:
        logger.error(f"Unexpected error running command: {command} - {e}")
        raise


def run_ingestion_only(backfill=False, force=False, days_back=None):
    """Run only the data ingestion steps."""
    if backfill:
        print("\n🔄 Running ingestion-only pipeline - BACKFILL MODE")
        # Calculate days_back for comprehensive backfill
        if days_back is None:
            # Get available source date range for backfill
            start_date, end_date = get_backfill_date_range()
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            ingestion_days_back = (end_dt - start_dt).days + 1
            # Add buffer to ensure we capture all data
            ingestion_days_back = max(ingestion_days_back, 30)
        else:
            ingestion_days_back = days_back
    else:
        print("\n🔄 Running ingestion-only pipeline")
        ingestion_days_back = days_back if days_back is not None else 7

    force_flag = " --force" if force else ""
    days_back_flag = f" --days-back {ingestion_days_back}"

    print(f"📅 Using ingestion date range: {ingestion_days_back} days back")

    steps = [
        (
            (f"python -m scripts.medium_ingest" f"{force_flag}{days_back_flag}"),
            "Medium Articles Ingestion",
        ),
        (
            f"python -m scripts.telegram_ingest{force_flag}",
            "Telegram Group Ingestion",
        ),
        (
            (f"python -m scripts.github_ingest" f"{force_flag}{days_back_flag}"),
            "GitHub Repository Ingestion",
        ),
        (
            (f"python -m scripts.discourse_ingest" f"{force_flag}{days_back_flag}"),
            "Discourse Forum Ingestion",
        ),
    ]

    success_count = 0
    for command, description in steps:
        success, _ = run_command(command, description)
        if success:
            success_count += 1

    return success_count > 0


def run_aggregation_only(force=False, backfill=False, days_back=None, period="monthly"):
    """Run only the period-based aggregation step."""
    # Determine processing mode and date range
    if days_back is not None:
        start_date, end_date = get_backfill_date_range(days_back)
        print(f"\n🔄 Running aggregation-only pipeline - DAYS BACK ({days_back})")
    elif backfill:
        start_date, end_date = get_backfill_date_range()
        print("\n🔄 Running aggregation-only pipeline - BACKFILL MODE")
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        start_date, end_date = today, today
        print("\n🔄 Running aggregation-only pipeline - DAILY MODE")

    force_flag = " --force" if force else ""

    if start_date == end_date:
        # Daily mode
        success, _ = run_command(
            f"python -m scripts.aggregate_sources --date {start_date}{force_flag}",
            f"Raw Sources Aggregation for {start_date}",
        )
    else:
        # Period-based mode
        command = (
            f"python -m scripts.aggregate_sources --start-date {start_date} "
            f"--end-date {end_date} --period {period}{force_flag}"
        )
        success, _ = run_command(
            command,
            f"Period-based Raw Sources Aggregation ({period})",
        )

    return success


def run_ai_processing_only(
    force=False, backfill=False, days_back=None, period="monthly"
):
    """Run only the period-based AI processing steps."""
    # Determine processing mode and date range
    if days_back is not None:
        start_date, end_date = get_backfill_date_range(days_back)
        print(f"\n🔄 Running AI processing pipeline - DAYS BACK ({days_back})")
    elif backfill:
        start_date, end_date = get_backfill_date_range()
        print("\n🔄 Running AI processing pipeline - BACKFILL MODE")
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        start_date, end_date = today, today
        print("\n🔄 Running AI processing pipeline - DAILY MODE")

    force_flag = " --force" if force else ""

    if start_date == end_date:
        # Daily mode
        steps = [
            (
                (
                    f"python -m scripts.generate_briefing --date {start_date}"
                    f"{force_flag}"
                ),
                f"Daily Briefing Generation for {start_date}",
            ),
            (
                (
                    f"python -m scripts.extract_facts --date {start_date}"
                    f"{force_flag}"
                ),
                f"Daily Facts Extraction for {start_date}",
            ),
        ]
    else:
        # Period-based mode
        period_chunks = get_period_chunks(start_date, end_date, period)
        steps = []

        for period_start, period_end, period_label in period_chunks:
            steps.extend(
                [
                    (
                        (
                            f"python -m scripts.generate_briefing "
                            f"--date {period_label} --period-summary{force_flag}"
                        ),
                        f"Period Briefing Generation for {period_label}",
                    ),
                    (
                        (
                            f"python -m scripts.extract_facts "
                            f"--date {period_label} --period-summary{force_flag}"
                        ),
                        f"Period Facts Extraction for {period_label}",
                    ),
                ]
            )

    success_count = 0
    for command, description in steps:
        success, _ = run_command(command, description)
        if success:
            success_count += 1

    return success_count > 0


def run_rag_generation_only(
    force=False, date=None, backfill=False, days_back=None, period="monthly"
):
    """Run only the period-based RAG document generation steps."""
    # Determine processing mode and date range
    if date:
        # Use provided date
        start_date, end_date = date, date
        print(f"\n🔄 Running RAG document generation pipeline - DATE ({date})")
    elif days_back is not None:
        start_date, end_date = get_backfill_date_range(days_back)
        print(
            f"\n🔄 Running RAG document generation pipeline - DAYS BACK ({days_back})"
        )
    elif backfill:
        start_date, end_date = get_backfill_date_range()
        print("\n🔄 Running RAG document generation pipeline - BACKFILL MODE")
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        start_date, end_date = today, today
        print("\n🔄 Running RAG document generation pipeline - DAILY MODE")

    force_flag = " --force" if force else ""

    if start_date == end_date:
        # Daily/single date mode
        steps = [
            (
                f"python -m scripts.generate_rag_document --date {start_date} "
                f"--organization prioritized{force_flag}",
                f"Prioritized RAG Document Generation for {start_date}",
            ),
        ]
    else:
        # Period-based mode with split output
        period_chunks = get_period_chunks(start_date, end_date, period)
        steps = []

        for period_start, period_end, period_label in period_chunks:
            steps.append(
                (
                    (
                        f"python -m scripts.generate_rag_document "
                        f"--date {period_label} --organization prioritized"
                        f"{force_flag} --split-output"
                    ),
                    (
                        f"Prioritized RAG Document Generation for {period_label} "
                        "(Split Output)"
                    ),
                )
            )

    success_count = 0
    for command, description in steps:
        success, _ = run_command(command, description)
        if success:
            success_count += 1

    return success_count > 0


def _display_daily_output_structure(date: str):
    """Display the expected daily output structure."""
    logger.info("=== DAILY OUTPUT STRUCTURE ===")
    logger.info(f"📅 Date: {date}")
    logger.info("📁 Expected outputs:")
    logger.info(f"  • data/aggregated/{date}.json - Combined source data")
    logger.info(f"  • data/briefings/{date}.json - AI-generated briefing")
    logger.info(f"  • data/facts/{date}.json - Extracted facts")
    logger.info(f"  • data/rag-documents/{date}.md - RAG document")


def _display_period_output_structure(start_date: str, end_date: str, period: str):
    """Display the expected period-based output structure."""
    logger.info("=== PERIOD-BASED OUTPUT STRUCTURE ===")
    logger.info(f"📅 Period: {start_date} to {end_date} ({period})")
    logger.info("📁 Expected outputs:")

    # Calculate expected period labels
    period_chunks = get_period_chunks(start_date, end_date, period)

    for chunk_start, chunk_end, period_label in period_chunks:
        logger.info(f"  📊 Period: {period_label}")
        logger.info(f"    • data/aggregated/{period_label}-{period}.json")
        logger.info(f"    • data/briefings/{period_label}-{period}.json")
        logger.info(f"    • data/facts/{period_label}-{period}.json")
        logger.info(f"    • data/rag-documents/{period_label}-{period}.md")


def main():
    """Main entry point with command line argument support."""
    parser = argparse.ArgumentParser(
        description=(
            "Kaspa Knowledge Hub Data Pipeline Runner with Period-based Processing"
        )
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["ingest", "aggregate", "ai", "rag", "full"],
        default="full",
        help="Pipeline mode to run (default: full)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Force re-processing even if data already exists "
            "(bypasses deduplication checks)"
        ),
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date for RAG generation (YYYY-MM-DD format, default: today)",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help=(
            "Run in backfill mode (process all historical data in period-based chunks)"
        ),
    )
    parser.add_argument(
        "--days-back",
        type=int,
        help=("Number of days back to process data (processes in period-based chunks)"),
    )
    parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly"],
        default="monthly",
        help="Period type for aggregation and processing (default: monthly)",
    )

    args = parser.parse_args()

    if args.mode == "ingest":
        success = run_ingestion_only(
            backfill=args.backfill,
            force=args.force,
            days_back=getattr(args, "days_back", None),
        )
    elif args.mode == "aggregate":
        success = run_aggregation_only(
            force=args.force,
            backfill=args.backfill,
            days_back=getattr(args, "days_back", None),
            period=args.period,
        )
    elif args.mode == "ai":
        success = run_ai_processing_only(
            force=args.force,
            backfill=args.backfill,
            days_back=getattr(args, "days_back", None),
            period=args.period,
        )
    elif args.mode == "rag":
        success = run_rag_generation_only(
            force=args.force,
            date=args.date,
            backfill=args.backfill,
            days_back=getattr(args, "days_back", None),
            period=args.period,
        )
    elif args.mode == "full":
        success = run_full_pipeline(
            backfill=args.backfill,
            days_back=getattr(args, "days_back", None),
            period=args.period,
            force=args.force,
        )

    if success:
        print("\n🎯 Pipeline completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Pipeline completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
