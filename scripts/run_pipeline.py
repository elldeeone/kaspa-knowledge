#!/usr/bin/env python3
"""
Kaspa Knowledge Hub Data Pipeline Runner

This script orchestrates the full data pipeline:
1. Ingests data from various sources into sources/ folders (raw data)
2. Aggregates all sources into daily raw aggregated data (no AI processing)
3. Generates AI-processed outputs: briefings and facts (separate files)
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(command, description):
    """Run a command and handle output."""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, cwd=Path.cwd()
        )

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(f"⚠️  stderr: {result.stderr}")

        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True, "success"
        elif result.returncode == 2 and (
            "medium_ingest" in command or "telegram_ingest" in command
        ):
            print(
                f"ℹ️  {description} found no new content - "
                "skipping downstream processing"
            )
            return True, "no_new_content"
        else:
            print(f"❌ {description} failed with return code {result.returncode}")
            return False, "failed"

    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return False, "failed"


def run_full_pipeline(force=False):
    """Run the complete data pipeline."""
    # Define pipeline date for consistent file naming
    pipeline_date = datetime.now().strftime("%Y-%m-%d")

    print("\n🚀 Starting Kaspa Knowledge Hub Pipeline")
    print(f"📅 Pipeline Date: {pipeline_date} ({datetime.now().strftime('%H:%M:%S')})")
    print("🏗️  Pipeline Version: 2.0.0")
    if force:
        print("⚠️  Force mode enabled - bypassing duplicate checks")

    success_count = 0
    total_steps = 0

    # Step 1: Ingest raw data from sources
    steps = [
        {
            "command": "python -m scripts.medium_ingest",
            "description": "Medium Articles Ingestion",
            "required": True,
        },
        {
            "command": "python -m scripts.telegram_ingest",
            "description": "Telegram Group Ingestion",
            "required": False,
        },
        {
            "command": f"python -m scripts.github_ingest --date {pipeline_date}",
            "description": "GitHub Repository Ingestion",
            "required": False,
        },
        {
            "command": "python -m scripts.discourse_ingest",
            "description": "Discourse Forum Ingestion",
            "required": False,
        },
    ]

    print("\n📋 STAGE 1: RAW DATA INGESTION")
    print("=" * 60)

    # Check if ingestion found new content
    ingestion_found_new_content = False

    for step in steps:
        total_steps += 1
        success, status = run_command(step["command"], step["description"])

        if success:
            success_count += 1
            if status == "success":
                ingestion_found_new_content = True
            # Note: "no_new_content" is also considered success, but won't
            # trigger downstream processing
        elif step["required"]:
            print(f"\n❌ Required step failed: {step['description']}")
            print("🛑 Stopping pipeline due to critical failure")
            return False

    # Skip remaining stages if no new content was found
    if not ingestion_found_new_content:
        print("\n🎯 PIPELINE OPTIMIZATION")
        print("=" * 60)
        print("📊 No new content found during ingestion")
        print("⚡ Skipping aggregation and AI processing to save resources")
        print("✨ This is the smart deduplication working as intended!")

        print("\n🎉 PIPELINE COMPLETED (OPTIMIZED)")
        print("=" * 60)
        print(f"✅ Successful steps: {success_count}/{total_steps}")
        print(f"📊 Success rate: {(success_count/total_steps)*100:.1f}%")
        print("🌟 Pipeline completed efficiently - no duplicate processing!")
        print("\n🎯 Pipeline completed successfully!")
        return True

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
    success, status = run_command(
        f"python -m scripts.aggregate_sources{force_flag}", "Raw Sources Aggregation"
    )
    if success:
        success_count += 1
    else:
        print("\n❌ Raw aggregation failed")
        print("🛑 Stopping pipeline - cannot proceed without aggregated data")
        return False

    # Step 3: AI Processing (separate outputs)
    ai_steps = [
        {
            "command": f"python -m scripts.generate_briefing{force_flag}",
            "description": "Daily Briefing Generation",
            "required": False,
        },
        {
            "command": f"python -m scripts.extract_facts{force_flag}",
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

    # Pipeline summary
    print("\n🎉 PIPELINE COMPLETED")
    print("=" * 60)
    print(f"✅ Successful steps: {success_count}/{total_steps}")
    print(f"📊 Success rate: {(success_count/total_steps)*100:.1f}%")

    if success_count == total_steps:
        print("🌟 All steps completed successfully!")
    elif success_count >= total_steps - 1:
        print("⚠️  Minor issues encountered, but pipeline mostly succeeded")
    else:
        print("⚠️  Several steps failed - check logs above")

    # Show output structure
    print("\n📁 OUTPUT STRUCTURE:")
    print("sources/                - Raw ingested data")
    print("  ├─ github/            - Raw GitHub repository data")
    print("  ├─ github_summaries/  - AI-processed GitHub summaries")
    print("  ├─ medium/            - Raw Medium articles")
    print("  └─ telegram/          - Raw Telegram messages")
    print("data/aggregated/        - Raw daily aggregated data")
    print("data/briefings/         - AI-generated daily briefings")
    print("data/facts/             - AI-extracted daily facts")

    return success_count >= (total_steps - 1)  # Allow 1 failure


def run_ingestion_only():
    """Run only the data ingestion steps."""
    print("\n🔄 Running ingestion-only pipeline")

    steps = [
        ("python -m scripts.medium_ingest", "Medium Articles Ingestion"),
        ("python -m scripts.telegram_ingest", "Telegram Group Ingestion"),
        ("python -m scripts.github_ingest", "GitHub Repository Ingestion"),
    ]

    success_count = 0
    for command, description in steps:
        success, status = run_command(command, description)
        if success:
            success_count += 1

    return success_count > 0


def run_aggregation_only(force=False):
    """Run only the raw aggregation step."""
    print("\n🔄 Running aggregation-only pipeline")
    force_flag = " --force" if force else ""
    success, status = run_command(
        f"python -m scripts.aggregate_sources{force_flag}", "Raw Sources Aggregation"
    )
    return success


def run_ai_processing_only(force=False):
    """Run only the AI processing steps."""
    print("\n🔄 Running AI processing pipeline")

    force_flag = " --force" if force else ""
    steps = [
        (
            f"python -m scripts.generate_briefing{force_flag}",
            "Daily Briefing Generation",
        ),
        (f"python -m scripts.extract_facts{force_flag}", "Daily Facts Extraction"),
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
        choices=["ingest", "aggregate", "ai", "full"],
        default="full",
        help="Pipeline mode to run (default: full)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-processing even if data already exists",
    )

    args = parser.parse_args()

    if args.mode == "ingest":
        success = run_ingestion_only()
    elif args.mode == "aggregate":
        success = run_aggregation_only(force=args.force)
    elif args.mode == "ai":
        success = run_ai_processing_only(force=args.force)
    elif args.mode == "full":
        success = run_full_pipeline(force=args.force)

    if success:
        print("\n🎯 Pipeline completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Pipeline completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
