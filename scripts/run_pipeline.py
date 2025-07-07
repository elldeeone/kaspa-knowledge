#!/usr/bin/env python3
"""
Kaspa Knowledge Hub Data Pipeline Runner

This script orchestrates the full data pipeline with comprehensive monitoring:
1. Ingests data from various sources into sources/ folders (raw data)
2. Aggregates all sources into period-based aggregated data (no AI processing)
3. Generates AI-processed outputs: briefings and facts (separate files)

Features:
- Period-based historical processing (monthly/weekly chunks)
- Comprehensive error handling and logging
- Performance monitoring and health tracking
- Retry mechanisms for failed operations
- Detailed pipeline execution reporting
- Configurable alerting system
"""

import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# Import the new monitoring system
from monitoring import (
    setup_monitoring_from_env,
    ErrorSeverity,
    ErrorCategory,
)


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


def run_full_pipeline(force=False, backfill=False, days_back=None, period="monthly"):
    """Run the complete data pipeline with period-based processing and monitoring."""
    # Initialize monitoring system
    if not LOGGER or not ERROR_HANDLER:
        initialize_monitoring()

    pipeline_start_time = time.time()

    # Determine processing mode and date range
    if days_back is not None:
        processing_mode = f"days_back_{days_back}"
        start_date, end_date = get_backfill_date_range(days_back)
        mode_description = (
            f"Processing last {days_back} days ({start_date} to {end_date})"
        )
    elif backfill:
        processing_mode = "backfill"
        start_date, end_date = get_backfill_date_range()
        mode_description = (
            f"Processing all historical data ({start_date} to {end_date})"
        )
    else:
        processing_mode = "daily"
        today = datetime.now().strftime("%Y-%m-%d")
        start_date, end_date = today, today
        mode_description = f"Processing daily data for {today}"

    # Header with processing mode information
    print(f"\n🚀 Starting Kaspa Knowledge Hub Pipeline - {processing_mode.upper()}")
    print(f"📅 {mode_description}")
    print(f"🔄 Period-based processing: {period}")
    LOGGER.logger.info(
        f"Pipeline started in {processing_mode} mode: {start_date} to {end_date}"
    )

    print("🏗️  Pipeline Version: 2.0.0 (with Enhanced Monitoring)")
    if force:
        print("⚠️  Force mode enabled - bypassing duplicate checks")
        LOGGER.logger.warning("Force mode enabled - bypassing duplicate checks")

    # Pipeline execution tracking
    success_count = 0
    total_steps = 0
    stage_results = {}
    pipeline_errors = []

    # Step 1: Ingest raw data from sources
    backfill_flag = " --full-history" if backfill else ""
    force_flag = " --force" if force else ""
    days_back_flag = f" --days-back {days_back}" if days_back is not None else ""

    if days_back is not None:
        print(f"📅 Using date filtering: {days_back} days back")

    ingestion_steps = [
        {
            "command": (
                f"python -m scripts.medium_ingest{backfill_flag}"
                f"{force_flag}{days_back_flag}"
            ),
            "description": "Medium Articles Ingestion",
            "component": "medium_ingest",
            "required": True,
            "timeout": 600,  # 10 minutes
        },
        {
            "command": f"python -m scripts.telegram_ingest{backfill_flag}{force_flag}",
            "description": "Telegram Group Ingestion",
            "component": "telegram_ingest",
            "required": False,
            "timeout": 600,
        },
        {
            "command": (
                f"python -m scripts.github_ingest --date {start_date}"
                f"{backfill_flag}{force_flag}{days_back_flag}"
            ),
            "description": "GitHub Repository Ingestion",
            "component": "github_ingest",
            "required": False,
            "timeout": 900,  # 15 minutes
        },
        {
            "command": (
                f"python -m scripts.discourse_ingest{backfill_flag}"
                f"{force_flag}{days_back_flag}"
            ),
            "description": "Discourse Forum Ingestion",
            "component": "discourse_ingest",
            "required": False,
            "timeout": 600,
        },
    ]

    print("\n📋 STAGE 1: RAW DATA INGESTION")
    print("=" * 60)

    stage_start_time = time.time()
    ingestion_found_new_content = False
    stage_success_count = 0
    stage_total_steps = len(ingestion_steps)

    for step in ingestion_steps:
        total_steps += 1
        success, status = run_command(
            step["command"],
            step["description"],
            component=step["component"],
            required=step["required"],
            timeout=step.get("timeout", 1800),
        )

        if success:
            success_count += 1
            stage_success_count += 1
            if status == "success":
                ingestion_found_new_content = True
            # Note: "no_new_content" is also considered success, but won't
            # trigger downstream processing
        else:
            pipeline_errors.append(
                {
                    "stage": "ingestion",
                    "step": step["description"],
                    "component": step["component"],
                    "required": step["required"],
                }
            )

            if step["required"]:
                stage_execution_time = time.time() - stage_start_time
                error_message = f"Required step failed: {step['description']}"
                print(f"\n❌ {error_message}")
                print("🛑 Stopping pipeline due to critical failure")

                # Log critical pipeline failure
                ERROR_HANDLER.create_error(
                    message=error_message,
                    severity=ErrorSeverity.CRITICAL,
                    category=ErrorCategory.PIPELINE_EXECUTION,
                    component="pipeline_runner",
                    context={
                        "stage": "ingestion",
                        "failed_step": step["description"],
                        "execution_time": stage_execution_time,
                        "successful_steps": stage_success_count,
                        "total_steps": stage_total_steps,
                    },
                    recovery_action=(
                        "Check ingestion system dependencies and configuration"
                    ),
                    user_impact="Pipeline halted - no data will be processed",
                )

                return False

    # Record stage completion
    stage_execution_time = time.time() - stage_start_time
    stage_results["ingestion"] = {
        "success_count": stage_success_count,
        "total_steps": stage_total_steps,
        "execution_time": stage_execution_time,
        "found_new_content": ingestion_found_new_content,
    }

    LOGGER.logger.info(
        f"Ingestion stage completed: {stage_success_count}/{stage_total_steps} "
        f"steps successful in {stage_execution_time:.2f}s"
    )

    # Continue processing to create placeholder files when no new content is found
    if not ingestion_found_new_content and not backfill:
        print("\n📊 NO NEW CONTENT FOUND - CONTINUING WITH PLACEHOLDER GENERATION")
        print("=" * 60)
        print("📊 No new content found during ingestion")
        print("📝 Continuing to create placeholder files for consistency")
        print("📋 Each stage will generate appropriate 'no content' placeholders")
        LOGGER.logger.info(
            "No new content found during ingestion - continuing with placeholder files"
        )

    # In backfill mode, continue processing even if no new content was found
    if backfill and not ingestion_found_new_content:
        print("\n📚 BACKFILL MODE: Continuing to process existing data")
        print("=" * 60)
        print("📊 No new content found, but processing existing data in backfill mode")
        LOGGER.logger.info(
            "Backfill mode: continuing to process existing data despite no new content"
        )

    # Step 1.5: Pre-processing/Summarization (GitHub Activity)
    print("\n📋 STAGE 1.5: DATA PRE-PROCESSING")
    print("=" * 60)

    preprocessing_steps = [
        {
            "command": f"python -m scripts.summarize_github --date {start_date}",
            "description": "GitHub Activity Summarization",
            "required": False,
        },
    ]

    for step in preprocessing_steps:
        total_steps += 1
        success, status = run_command(step["command"], step["description"])

        if success:
            success_count += 1
        elif step["required"]:
            print(f"\n❌ Required preprocessing step failed: {step['description']}")
            print("🛑 Stopping pipeline due to critical failure")
            return False

    # Step 2: Period-based Raw Sources Aggregation
    print("\n📋 STAGE 2: PERIOD-BASED RAW SOURCES AGGREGATION")
    print("=" * 60)

    force_flag = " --force" if force else ""

    if processing_mode == "daily":
        # For daily mode, use regular single-date aggregation
        total_steps += 1
        success, status = run_command(
            f"python -m scripts.aggregate_sources --date {start_date}{force_flag}",
            f"Raw Sources Aggregation for {start_date}",
        )
        if success:
            success_count += 1
        else:
            print("\n❌ Raw aggregation failed")
            print("🛑 Stopping pipeline - cannot proceed without aggregated data")
            return False
    else:
        # For backfill or days_back mode, use period-based aggregation
        total_steps += 1
        command = (
            f"python -m scripts.aggregate_sources --start-date {start_date} "
            f"--end-date {end_date} --period {period}{force_flag}"
        )
        success, status = run_command(
            command,
            f"Period-based Raw Sources Aggregation ({period})",
        )
        if success:
            success_count += 1
        else:
            print("\n❌ Period-based aggregation failed")
            print("🛑 Stopping pipeline - cannot proceed without aggregated data")
            return False

    # Step 3: Period-based AI Processing
    print("\n📋 STAGE 3: PERIOD-BASED AI PROCESSING")
    print("=" * 60)

    if processing_mode == "daily":
        # For daily mode, use regular AI processing
        ai_steps = [
            {
                "command": (
                    f"python -m scripts.generate_briefing --date {start_date}"
                    f"{force_flag}"
                ),
                "description": f"Daily Briefing Generation for {start_date}",
                "required": False,
            },
            {
                "command": (
                    f"python -m scripts.extract_facts --date {start_date}"
                    f"{force_flag}"
                ),
                "description": f"Daily Facts Extraction for {start_date}",
                "required": False,
            },
        ]
    else:
        # For period-based processing, generate AI outputs for each period
        period_chunks = get_period_chunks(start_date, end_date, period)
        ai_steps = []

        for period_start, period_end, period_label in period_chunks:
            ai_steps.extend(
                [
                    {
                        "command": (
                            f"python -m scripts.generate_briefing "
                            f"--date {period_label} --period-summary{force_flag}"
                        ),
                        "description": f"Period Briefing Generation for {period_label}",
                        "required": False,
                    },
                    {
                        "command": (
                            f"python -m scripts.extract_facts "
                            f"--date {period_label} --period-summary{force_flag}"
                        ),
                        "description": f"Period Facts Extraction for {period_label}",
                        "required": False,
                    },
                ]
            )

    for step in ai_steps:
        total_steps += 1
        success, status = run_command(step["command"], step["description"])
        if success:
            success_count += 1
        elif step["required"]:
            print(f"\n❌ Required AI step failed: {step['description']}")
            return False

    # Step 4: Period-based RAG Document Generation
    print("\n📋 STAGE 4: PERIOD-BASED RAG DOCUMENT GENERATION")
    print("=" * 60)

    if processing_mode == "daily":
        # For daily mode, use regular RAG generation
        rag_steps = [
            {
                "command": (
                    f"python -m scripts.generate_rag_document --date {start_date} "
                    f"--organization prioritized{force_flag}"
                ),
                "description": (
                    f"Prioritized RAG Document Generation for {start_date}"
                ),
                "required": False,
            },
        ]
    else:
        # For period-based processing, generate RAG documents for each period
        # with split output
        period_chunks = get_period_chunks(start_date, end_date, period)
        rag_steps = []

        for period_start, period_end, period_label in period_chunks:
            rag_steps.append(
                {
                    "command": (
                        f"python -m scripts.generate_rag_document "
                        f"--date {period_label} --organization prioritized"
                        f"{force_flag} --split-output"
                    ),
                    "description": (
                        f"Prioritized RAG Document Generation for {period_label} "
                        "(Split Output)"
                    ),
                    "required": False,
                }
            )

    for step in rag_steps:
        total_steps += 1
        success, status = run_command(step["command"], step["description"])
        if success:
            success_count += 1
        elif step["required"]:
            print(f"\n❌ Required RAG step failed: {step['description']}")
            return False

    # Comprehensive pipeline completion with monitoring
    pipeline_execution_time = time.time() - pipeline_start_time
    success_rate = (success_count / total_steps) * 100 if total_steps > 0 else 0

    print("\n🎉 PIPELINE COMPLETED")
    print("=" * 60)
    print(f"✅ Successful steps: {success_count}/{total_steps}")
    print(f"📊 Success rate: {success_rate:.1f}%")
    print(f"⏱️  Total execution time: {pipeline_execution_time:.2f}s")

    if success_count == total_steps:
        print("✅ All steps completed successfully")
        pipeline_status = "success"
    elif success_count >= total_steps - 1:
        print("⚠️  Minor issues encountered, but pipeline mostly succeeded")
        pipeline_status = "mostly_success"
    else:
        print("⚠️  Several steps failed - check logs above")
        pipeline_status = "partial_failure"

    # Log comprehensive pipeline completion
    LOGGER.logger.info(
        f"Pipeline completed with status: {pipeline_status}. "
        f"Success rate: {success_rate:.1f}% ({success_count}/{total_steps} steps) "
        f"in {pipeline_execution_time:.2f}s"
    )

    # Generate comprehensive pipeline report
    generate_pipeline_report(
        stage_results,
        success_count,
        total_steps,
        pipeline_execution_time,
        pipeline_errors,
        pipeline_status,
    )

    # Show health summary
    print("\n📊 PIPELINE HEALTH SUMMARY:")
    print("=" * 60)
    health_report = ERROR_HANDLER.get_health_report()
    overall_health = health_report.get("overall_health", {})
    print(f"🏥 Overall Health Score: {overall_health.get('score', 0):.1f}/100")
    healthy_count = overall_health.get("healthy_components", 0)
    total_count = overall_health.get("total_components", 0)
    print(f"💚 Healthy Components: {healthy_count}/{total_count}")

    error_summary = health_report.get("error_summary", {})
    if error_summary.get("critical_errors", 0) > 0:
        print(f"🚨 Critical Errors: {error_summary['critical_errors']}")
    if error_summary.get("recent_errors_1h", 0) > 0:
        print(f"⚠️  Recent Errors (1h): {error_summary['recent_errors_1h']}")

    # Show output structure
    print("\n📁 OUTPUT STRUCTURE:")
    print("sources/                - Raw ingested data")
    print("  ├─ github/            - Raw GitHub repository data")
    print("  ├─ github_summaries/  - AI-processed GitHub summaries")
    print("  ├─ medium/            - Raw Medium articles")
    print("  └─ telegram/          - Raw Telegram messages")

    if processing_mode == "daily":
        print("data/aggregated/        - Raw daily aggregated data")
        print(f"  └─ {start_date}.json  - Aggregated data for {start_date}")
        print("data/briefings/         - AI-generated daily briefings")
        print(f"  └─ {start_date}.json  - Daily briefing for {start_date}")
        print("data/facts/             - AI-extracted daily facts")
        print(f"  └─ {start_date}.json  - Daily facts for {start_date}")
        print("knowledge_base/         - RAG-optimized documents")
        print(f"  └─ {start_date}.md    - Prioritized RAG document for {start_date}")
    else:
        print("data/aggregated/        - Period-based aggregated data files")
        period_chunks = get_period_chunks(start_date, end_date, period)
        for _, _, period_label in period_chunks[:3]:  # Show first 3 examples
            print(
                f"  ├─ {period_label}-{period}.json - "
                f"Aggregated data for {period_label}"
            )
        if len(period_chunks) > 3:
            print(f"  └─ ... ({len(period_chunks) - 3} more {period} files)")

        print("data/briefings/         - AI-generated period briefings")
        for _, _, period_label in period_chunks[:3]:  # Show first 3 examples
            print(f"  ├─ {period_label}.json - Period briefing for {period_label}")
        if len(period_chunks) > 3:
            print(f"  └─ ... ({len(period_chunks) - 3} more {period} briefing files)")

        print("data/facts/             - AI-extracted period facts")
        for _, _, period_label in period_chunks[:3]:  # Show first 3 examples
            print(f"  ├─ {period_label}.json - Period facts for {period_label}")
        if len(period_chunks) > 3:
            print(f"  └─ ... ({len(period_chunks) - 3} more {period} facts files)")

        print("knowledge_base/         - RAG-optimized documents (SPLIT OUTPUT)")
        for _, _, period_label in period_chunks[:2]:  # Show first 2 examples
            print(f"  ├─ {period_label}_01_briefing.md     - Period briefing section")
            print(f"  ├─ {period_label}_02_facts.md        - Key facts section")
            print(f"  ├─ {period_label}_03_high_signal.md  - High-signal content")
            print(f"  ├─ {period_label}_04_general_activity.md - General activity")
        if len(period_chunks) > 2:
            print(f"  └─ ... ({len(period_chunks) - 2} more {period} document sets)")

    chunks_count = (
        len(get_period_chunks(start_date, end_date, period))
        if processing_mode != "daily"
        else 1
    )
    period_type = period if processing_mode != "daily" else "daily"
    print(f"\n🗓️  Processing Summary: {chunks_count} {period_type} period(s) processed")

    print("\n📋 Detailed reports available at: monitoring/reports/")
    print("📝 Logs available at: monitoring/logs/")

    return success_count >= (total_steps - 1)  # Allow 1 failure


def generate_pipeline_report(
    stage_results: Dict,
    success_count: int,
    total_steps: int,
    execution_time: float,
    errors: List[Dict],
    status: str,
) -> None:
    """Generate comprehensive pipeline execution report."""
    if not LOGGER or not ERROR_HANDLER:
        return

    report = {
        "pipeline_execution": {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "execution_time_seconds": round(execution_time, 2),
            "success_count": success_count,
            "total_steps": total_steps,
            "success_rate": round(
                (success_count / total_steps * 100) if total_steps > 0 else 0, 2
            ),
        },
        "stage_results": stage_results,
        "errors": errors,
        "health_report": ERROR_HANDLER.get_health_report(),
        "performance_stats": LOGGER.get_operation_stats(),
    }

    # Save report to file
    try:
        import json

        report_dir = Path("monitoring/reports")
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"pipeline_execution_{timestamp}.json"

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        LOGGER.logger.info(f"Pipeline execution report saved to: {report_file}")

    except Exception as e:
        LOGGER.logger.error(f"Failed to save pipeline report: {e}")


def run_ingestion_only(backfill=False, force=False, days_back=None):
    """Run only the data ingestion steps."""
    if backfill:
        print("\n🔄 Running ingestion-only pipeline - BACKFILL MODE")
        backfill_flag = " --full-history"
    else:
        print("\n🔄 Running ingestion-only pipeline")
        backfill_flag = ""

    force_flag = " --force" if force else ""

    # Add days_back flag for Medium and GitHub if specified
    days_back_flag = f" --days-back {days_back}" if days_back is not None else ""

    if days_back is not None:
        print(f"📅 Using date filtering: {days_back} days back")

    steps = [
        (
            (
                f"python -m scripts.medium_ingest{backfill_flag}"
                f"{force_flag}{days_back_flag}"
            ),
            "Medium Articles Ingestion",
        ),
        (
            f"python -m scripts.telegram_ingest{backfill_flag}{force_flag}",
            "Telegram Group Ingestion",
        ),
        (
            (
                f"python -m scripts.github_ingest{backfill_flag}"
                f"{force_flag}{days_back_flag}"
            ),
            "GitHub Repository Ingestion",
        ),
        (
            (
                f"python -m scripts.discourse_ingest{backfill_flag}"
                f"{force_flag}{days_back_flag}"
            ),
            "Discourse Forum Ingestion",
        ),
    ]

    success_count = 0
    for command, description in steps:
        success, status = run_command(command, description)
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
        success, status = run_command(
            f"python -m scripts.aggregate_sources --date {start_date}{force_flag}",
            f"Raw Sources Aggregation for {start_date}",
        )
    else:
        # Period-based mode
        command = (
            f"python -m scripts.aggregate_sources --start-date {start_date} "
            f"--end-date {end_date} --period {period}{force_flag}"
        )
        success, status = run_command(
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
        success, status = run_command(command, description)
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
        success, status = run_command(command, description)
        if success:
            success_count += 1

    return success_count > 0


def main():
    """Main entry point with command line argument support."""
    import argparse

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
            force=args.force,
            backfill=args.backfill,
            days_back=getattr(args, "days_back", None),
            period=args.period,
        )

    if success:
        print("\n🎯 Pipeline completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Pipeline completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
