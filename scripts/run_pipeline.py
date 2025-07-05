#!/usr/bin/env python3
"""
Kaspa Knowledge Hub Data Pipeline Runner

This script orchestrates the full data pipeline with comprehensive monitoring:
1. Ingests data from various sources into sources/ folders (raw data)
2. Aggregates all sources into daily raw aggregated data (no AI processing)
3. Generates AI-processed outputs: briefings and facts (separate files)

Features:
- Comprehensive error handling and logging
- Performance monitoring and health tracking
- Retry mechanisms for failed operations
- Detailed pipeline execution reporting
- Configurable alerting system
"""

import subprocess
import sys
import time
from datetime import datetime
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


def run_full_pipeline(force=False, backfill=False, days_back=None):
    """Run the complete data pipeline with comprehensive monitoring."""
    # Initialize monitoring system
    if not LOGGER or not ERROR_HANDLER:
        initialize_monitoring()

    pipeline_start_time = time.time()

    # Define pipeline date for consistent file naming
    if backfill:
        pipeline_date = "full_history"
        print("\n🚀 Starting Kaspa Knowledge Hub Pipeline - BACKFILL MODE")
        print("📚 Backfill Mode: Processing comprehensive historical data")
        LOGGER.logger.info("Pipeline started in backfill mode")
    else:
        pipeline_date = datetime.now().strftime("%Y-%m-%d")
        print("\n🚀 Starting Kaspa Knowledge Hub Pipeline")
        print(
            f"📅 Pipeline Date: {pipeline_date} ({datetime.now().strftime('%H:%M:%S')})"
        )
        LOGGER.logger.info(f"Pipeline started for date: {pipeline_date}")

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
                f"python -m scripts.github_ingest --date {pipeline_date}"
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

    # Skip remaining stages if no new content was found AND not in backfill mode
    if not ingestion_found_new_content and not backfill:
        pipeline_execution_time = time.time() - pipeline_start_time

        print("\n🎉 PIPELINE COMPLETED - NO NEW CONTENT")
        print("=" * 60)
        print("📊 No new content found during ingestion")
        print("⚡ Skipping aggregation and AI processing stages")
        print(f"✅ Successful steps: {success_count}/{total_steps}")
        print(f"📊 Success rate: {(success_count/total_steps)*100:.1f}%")
        print(f"⏱️  Total execution time: {pipeline_execution_time:.2f}s")

        # Log pipeline completion
        LOGGER.logger.info(
            f"Pipeline completed with no new content. "
            f"Success rate: {(success_count/total_steps)*100:.1f}% "
            f"({success_count}/{total_steps} steps) in {pipeline_execution_time:.2f}s"
        )

        # Generate pipeline report
        generate_pipeline_report(
            stage_results,
            success_count,
            total_steps,
            pipeline_execution_time,
            pipeline_errors,
            "completed_no_content",
        )

        return True

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
            "command": f"python -m scripts.summarize_github --date {pipeline_date}",
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

    # Step 2: Aggregate raw sources (no AI processing)
    print("\n📋 STAGE 2: RAW DATA AGGREGATION")
    print("=" * 60)

    total_steps += 1
    force_flag = " --force" if force else ""
    aggregation_date = pipeline_date if not backfill else "full_history"
    success, status = run_command(
        f"python -m scripts.aggregate_sources --date {aggregation_date}{force_flag}",
        "Raw Sources Aggregation",
    )
    if success:
        success_count += 1
    else:
        print("\n❌ Raw aggregation failed")
        print("🛑 Stopping pipeline - cannot proceed without aggregated data")
        return False

    # Step 3: AI Processing (separate outputs)
    ai_date_flag = f" --date {aggregation_date}" if backfill else ""
    ai_steps = [
        {
            "command": f"python -m scripts.generate_briefing{ai_date_flag}{force_flag}",
            "description": "Daily Briefing Generation",
            "required": False,
        },
        {
            "command": f"python -m scripts.extract_facts{ai_date_flag}{force_flag}",
            "description": "Daily Facts Extraction",
            "required": False,
        },
    ]

    print("\n📋 STAGE 3: AI PROCESSING")
    print("=" * 60)

    for step in ai_steps:
        total_steps += 1
        success, status = run_command(step["command"], step["description"])
        if success:
            success_count += 1
        elif step["required"]:
            print(f"\n❌ Required AI step failed: {step['description']}")
            return False

    # Step 4: RAG Document Generation
    print("\n📋 STAGE 4: RAG DOCUMENT GENERATION")
    print("=" * 60)

    # Add split-output flag for backfill mode
    split_flag = " --split-output" if backfill else ""

    rag_steps = [
        {
            "command": (
                f"python -m scripts.generate_rag_document --date {aggregation_date} "
                f"--organization prioritized{force_flag}{split_flag}"
            ),
            "description": "Prioritized RAG Document Generation"
            + (" (Split Output)" if backfill else ""),
            "required": False,
        },
    ]

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
    if backfill:
        print("data/aggregated/        - Aggregated data files")
        print(
            "  └─ full_history_aggregated.json - Comprehensive historical aggregation"
        )
        print("data/briefings/         - AI-generated briefings")
        print("  └─ full_history.json  - Comprehensive historical briefing")
        print("data/facts/             - AI-extracted facts")
        print("  └─ full_history.json  - Comprehensive historical facts")
        print("knowledge_base/         - RAG-optimized documents (SPLIT OUTPUT)")
        print("  ├─ full_history_01_briefing.md     - Daily briefing section")
        print("  ├─ full_history_02_facts.md        - Key facts section")
        print("  ├─ full_history_03_high_signal.md  - High-signal content")
        print("  └─ full_history_04_general_activity.md - General activity")
    else:
        print("data/aggregated/        - Raw daily aggregated data")
        print("data/briefings/         - AI-generated daily briefings")
        print("data/facts/             - AI-extracted daily facts")
        print("knowledge_base/         - RAG-optimized documents")
        print(
            "  └─ YYYY-MM-DD.md      - Prioritized RAG documents "
            "(high-signal first, comprehensive)"
        )

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


def run_aggregation_only(force=False, backfill=False):
    """Run only the raw aggregation step."""
    if backfill:
        print("\n🔄 Running aggregation-only pipeline - BACKFILL MODE")
        aggregation_date = "full_history"
    else:
        print("\n🔄 Running aggregation-only pipeline")
        aggregation_date = datetime.now().strftime("%Y-%m-%d")

    force_flag = " --force" if force else ""
    success, status = run_command(
        f"python -m scripts.aggregate_sources --date {aggregation_date}{force_flag}",
        "Raw Sources Aggregation",
    )
    return success


def run_ai_processing_only(force=False, backfill=False):
    """Run only the AI processing steps."""
    if backfill:
        print("\n🔄 Running AI processing pipeline - BACKFILL MODE")
        ai_date_flag = " --date full_history"
    else:
        print("\n🔄 Running AI processing pipeline")
        ai_date_flag = ""

    force_flag = " --force" if force else ""
    steps = [
        (
            f"python -m scripts.generate_briefing{ai_date_flag}{force_flag}",
            "Daily Briefing Generation",
        ),
        (
            f"python -m scripts.extract_facts{ai_date_flag}{force_flag}",
            "Daily Facts Extraction",
        ),
    ]

    success_count = 0
    for command, description in steps:
        success, status = run_command(command, description)
        if success:
            success_count += 1

    return success_count > 0


def run_rag_generation_only(force=False, date=None, backfill=False):
    """Run only the RAG document generation steps."""
    if backfill or date == "full_history":
        print("\n🔄 Running RAG document generation pipeline - BACKFILL MODE")
        rag_date = "full_history"
    else:
        print("\n🔄 Running RAG document generation pipeline")
        rag_date = date if date else datetime.now().strftime("%Y-%m-%d")

    force_flag = " --force" if force else ""
    split_flag = " --split-output" if backfill or rag_date == "full_history" else ""

    steps = [
        (
            f"python -m scripts.generate_rag_document --date {rag_date} "
            f"--organization prioritized{force_flag}{split_flag}",
            "Prioritized RAG Document Generation"
            + (" (Split Output)" if split_flag else ""),
        ),
    ]

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
        description="Kaspa Knowledge Hub Data Pipeline Runner"
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
            "Run in backfill mode (process comprehensive historical data, "
            "saves to full_history files)"
        ),
    )
    parser.add_argument(
        "--days-back",
        type=int,
        help=(
            "Number of days back to fetch data for Medium, GitHub, and Discourse "
            "ingestion (filters by publication/update/creation date)"
        ),
    )

    args = parser.parse_args()

    if args.mode == "ingest":
        success = run_ingestion_only(
            backfill=args.backfill,
            force=args.force,
            days_back=getattr(args, "days_back", None),
        )
    elif args.mode == "aggregate":
        success = run_aggregation_only(force=args.force, backfill=args.backfill)
    elif args.mode == "ai":
        success = run_ai_processing_only(force=args.force, backfill=args.backfill)
    elif args.mode == "rag":
        success = run_rag_generation_only(
            force=args.force, date=args.date, backfill=args.backfill
        )
    elif args.mode == "full":
        success = run_full_pipeline(
            force=args.force,
            backfill=args.backfill,
            days_back=getattr(args, "days_back", None),
        )

    if success:
        print("\n🎯 Pipeline completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Pipeline completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
