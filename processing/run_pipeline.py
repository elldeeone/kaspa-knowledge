#!/usr/bin/env python3
"""
Kaspa Knowledge Hub Data Pipeline Runner

This script orchestrates the full data pipeline following the elizaOS pattern:
1. Ingests data from various sources into sources/ folders (raw data)
2. Aggregates all sources into daily raw aggregated data (no AI processing)
3. Generates AI-processed outputs: briefings and facts (separate files)

Inspired by elizaOS/knowledge repository structure.
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
            command, 
            shell=True, 
            capture_output=True, 
            text=True,
            cwd=Path.cwd()
        )
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print(f"⚠️  stderr: {result.stderr}")
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed with return code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return False


def run_full_pipeline():
    """Run the complete data pipeline."""
    print(f"\n🚀 Starting Kaspa Knowledge Hub Pipeline")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🏗️  Pipeline Version: 2.0.0 (elizaOS-inspired)")
    
    success_count = 0
    total_steps = 0
    
    # Step 1: Ingest raw data from sources
    steps = [
        {
            "command": "python -m processing.medium_ingest",
            "description": "Medium Articles Ingestion",
            "required": True
        },
        # TODO: Add other source ingestion commands when available
        # {
        #     "command": "python -m processing.github_ingest",
        #     "description": "GitHub Activity Ingestion",
        #     "required": False
        # },
    ]
    
    print(f"\n📋 STAGE 1: RAW DATA INGESTION")
    print(f"{'='*60}")
    
    for step in steps:
        total_steps += 1
        if run_command(step["command"], step["description"]):
            success_count += 1
        elif step["required"]:
            print(f"\n❌ Required step failed: {step['description']}")
            print("🛑 Stopping pipeline due to critical failure")
            return False
    
    # Step 2: Aggregate raw sources (no AI processing)
    print(f"\n📋 STAGE 2: RAW DATA AGGREGATION")
    print(f"{'='*60}")
    
    total_steps += 1
    if run_command("python -m processing.aggregate_sources", "Raw Sources Aggregation"):
        success_count += 1
    else:
        print("\n❌ Raw aggregation failed")
        print("🛑 Stopping pipeline - cannot proceed without aggregated data")
        return False
    
    # Step 3: AI Processing (separate outputs)
    ai_steps = [
        {
            "command": "python -m processing.generate_briefing",
            "description": "Daily Briefing Generation",
            "required": False
        },
        {
            "command": "python -m processing.extract_facts",
            "description": "Daily Facts Extraction", 
            "required": False
        }
    ]
    
    print(f"\n📋 STAGE 3: AI PROCESSING")
    print(f"{'='*60}")
    
    for step in ai_steps:
        total_steps += 1
        if run_command(step["command"], step["description"]):
            success_count += 1
        elif step["required"]:
            print(f"\n❌ Required AI step failed: {step['description']}")
            return False
    
    # Pipeline summary
    print(f"\n🎉 PIPELINE COMPLETED")
    print(f"{'='*60}")
    print(f"✅ Successful steps: {success_count}/{total_steps}")
    print(f"📊 Success rate: {(success_count/total_steps)*100:.1f}%")
    
    if success_count == total_steps:
        print(f"🌟 All steps completed successfully!")
    elif success_count >= total_steps - 1:
        print(f"⚠️  Minor issues encountered, but pipeline mostly succeeded")
    else:
        print(f"⚠️  Several steps failed - check logs above")
    
    # Show output structure
    print(f"\n📁 OUTPUT STRUCTURE:")
    print(f"sources/           - Raw ingested data")
    print(f"data/aggregated/   - Raw daily aggregated data")
    print(f"data/briefings/    - AI-generated daily briefings")
    print(f"data/facts/        - AI-extracted daily facts")
    
    return success_count >= (total_steps - 1)  # Allow 1 failure


def run_ingestion_only():
    """Run only the data ingestion steps."""
    print(f"\n🔄 Running ingestion-only pipeline")
    return run_command("python -m processing.medium_ingest", "Medium Articles Ingestion")


def run_aggregation_only():
    """Run only the raw aggregation step."""
    print(f"\n🔄 Running aggregation-only pipeline")
    return run_command("python -m processing.aggregate_sources", "Raw Sources Aggregation")


def run_ai_processing_only():
    """Run only the AI processing steps."""
    print(f"\n🔄 Running AI processing pipeline")
    
    steps = [
        ("python -m processing.generate_briefing", "Daily Briefing Generation"),
        ("python -m processing.extract_facts", "Daily Facts Extraction")
    ]
    
    success_count = 0
    for command, description in steps:
        if run_command(command, description):
            success_count += 1
    
    return success_count > 0


def main():
    """Main entry point with command line argument support."""
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == "ingest":
            success = run_ingestion_only()
        elif mode == "aggregate":
            success = run_aggregation_only()
        elif mode == "ai":
            success = run_ai_processing_only()
        elif mode == "full":
            success = run_full_pipeline()
        else:
            print(f"❌ Unknown mode: {mode}")
            print(f"Available modes: ingest, aggregate, ai, full")
            sys.exit(1)
    else:
        # Default to full pipeline
        success = run_full_pipeline()
    
    if success:
        print(f"\n🎯 Pipeline completed successfully!")
        sys.exit(0)
    else:
        print(f"\n💥 Pipeline completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main() 