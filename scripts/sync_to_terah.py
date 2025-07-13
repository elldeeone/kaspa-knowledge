#!/usr/bin/env python3
"""
Sync to Terah - Export filtered knowledge base content to Terah AI agent

This script orchestrates the extraction of specific content from various sources
and exports it to the Terah repository for AI agent consumption. It maintains
its own state and configuration separate from the main pipeline.
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
CONFIG_PATH = Path("config/terah_sync.json")
STATE_PATH = Path(".terah/sync_state.json")
DEFAULT_OUTPUT_DIR = Path("/tmp/terah_sync")  # Fallback if not configured


def load_config() -> Dict:
    """Load Terah sync configuration"""
    if not CONFIG_PATH.exists():
        logger.warning(f"Configuration file not found: {CONFIG_PATH}")
        logger.info("Creating default configuration...")

        # Create default config
        default_config = {
            "output_dir": str(DEFAULT_OUTPUT_DIR),
            "sources": {
                "discourse": {
                    "enabled": True,
                    "categories": ["l1-l2", "consensus"],
                    "forums": ["research.kas.pa"],
                },
                "github": {
                    "enabled": True,
                    "repos": ["kaspanet/rusty-kaspa", "kaspanet/kaspad"],
                },
                "telegram": {
                    "enabled": True,
                    "groups": ["all"],  # "all" means all configured groups
                },
                "medium": {
                    "enabled": True,
                    "authors": ["all"],  # "all" means all configured RSS feeds
                },
            },
            "sync_interval_days": 7,  # How often to sync each source
            "full_history_on_first_run": True,
        }

        # Save default config
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(default_config, f, indent=2)

        return default_config

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def load_state() -> Dict:
    """Load sync state tracking"""
    if not STATE_PATH.exists():
        return {}

    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_state(state: Dict):
    """Save sync state tracking"""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def get_date_range(start_date: str, end_date: str) -> str:
    """Format date range for filename"""
    return f"{start_date}_{end_date}"


def get_source_identifier(source: str, filters: List[str]) -> str:
    """Generate source identifier for filename"""
    if not filters or filters == ["all"]:
        return source
    # Sanitize filter names for filenames
    safe_filters = [f.replace("/", "-").replace(":", "-") for f in filters]
    return f"{source}_{'_'.join(safe_filters)}"


def run_discourse_sync(config: Dict, state: Dict, output_dir: Path) -> Optional[str]:
    """Run Discourse forum sync"""
    discourse_config = config["sources"]["discourse"]
    if not discourse_config.get("enabled", True):
        logger.info("Discourse sync disabled in configuration")
        return None

    categories = discourse_config.get("categories", [])
    if not categories:
        logger.warning("No Discourse categories configured")
        return None

    # Determine sync mode
    sync_mode = discourse_config.get("sync_mode", "incremental")
    last_sync = state.get("discourse", {}).get("last_sync")
    is_first_run = last_sync is None
    use_full_history = is_first_run and config.get("full_history_on_first_run", True)

    # Calculate date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    if is_first_run:
        start_date = "2023-01-01"  # Kaspa research forum started around this time
    else:
        if sync_mode == "incremental":
            # Sync from last sync date (daily incremental)
            start_date = last_sync
        else:
            # Default to last sync
            start_date = last_sync

    # Build output filename
    source_id = get_source_identifier("discourse_research-kas-pa", categories)
    date_range = get_date_range(start_date, end_date)
    output_file = output_dir / f"{source_id}_{date_range}.json"

    # Build command
    cmd = [
        "python3",
        "-m",
        "scripts.discourse_ingest",
        "--categories",
        ",".join(categories),
        "--output",
        str(output_file),
    ]

    if use_full_history and not categories:
        # Only use full-history if no specific categories are requested
        cmd.append("--full-history")
    elif use_full_history and categories:
        # When categories are specified, don't use full-history as it pulls everything
        logger.info(
            "Note: Not using --full-history mode since "
            "specific categories are requested"
        )

    logger.info(f"Running Discourse sync: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ Discourse sync successful: {output_file}")
            # Update state
            if "discourse" not in state:
                state["discourse"] = {}
            state["discourse"]["last_sync"] = end_date
            state["discourse"]["last_output"] = str(output_file)
            return str(output_file)
        elif result.returncode == 2:
            logger.info("📭 No new Discourse content found")
            return None
        else:
            logger.error(f"❌ Discourse sync failed: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"❌ Error running Discourse sync: {e}")
        return None


def run_github_sync(config: Dict, state: Dict, output_dir: Path) -> Optional[str]:
    """Run GitHub repository sync"""
    github_config = config["sources"]["github"]
    if not github_config.get("enabled", True):
        logger.info("GitHub sync disabled in configuration")
        return None

    repos = github_config.get("repos", [])
    if not repos:
        logger.warning("No GitHub repositories configured")
        return None

    # Determine sync mode
    sync_mode = github_config.get("sync_mode", "rolling")
    rolling_days = github_config.get("rolling_days", 7)

    # Calculate date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    last_sync = state.get("github", {}).get("last_sync")

    if sync_mode == "rolling":
        # Always sync the last N days
        days_back = rolling_days
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    elif last_sync:
        # Incremental mode - sync from last sync date
        last_sync_date = datetime.strptime(last_sync, "%Y-%m-%d")
        days_back = (datetime.now() - last_sync_date).days + 1
        start_date = last_sync
    else:
        # First run - get last 30 days
        days_back = 30
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Build output filename
    repo_names = [r.split("/")[-1] for r in repos[:2]]  # First 2 repo names
    source_id = get_source_identifier("github", repo_names)
    date_range = get_date_range(start_date, end_date)
    output_file = output_dir / f"{source_id}_{date_range}.json"

    # Build command
    cmd = [
        "python3",
        "-m",
        "scripts.github_ingest",
        "--days-back",
        str(days_back),
        "--output",
        str(output_file),
        "--force",  # Always use force to ensure file creation
    ]

    # Log the sync mode being used
    logger.info(f"Using {sync_mode} sync mode for GitHub (days_back={days_back})")

    logger.info(f"Running GitHub sync: {' '.join(cmd)}")
    logger.info(f"Expected output file: {output_file}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            # Verify the file actually exists before declaring success
            if output_file.exists():
                logger.info(f"✅ GitHub sync successful: {output_file}")
                # Update state
                if "github" not in state:
                    state["github"] = {}
                state["github"]["last_sync"] = end_date
                state["github"]["last_output"] = str(output_file)
                return str(output_file)
            else:
                logger.error(
                    f"❌ GitHub sync reported success but output file not found: "
                    f"{output_file}"
                )
                return None
        elif result.returncode == 2:
            logger.info("📭 No new GitHub content found")
            # Even with no content, the file should exist with metadata
            if output_file.exists():
                return str(output_file)
            return None
        else:
            logger.error(f"❌ GitHub sync failed: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"❌ Error running GitHub sync: {e}")
        return None


def run_telegram_sync(config: Dict, state: Dict, output_dir: Path) -> Optional[str]:
    """Run Telegram group sync"""
    telegram_config = config["sources"]["telegram"]
    if not telegram_config.get("enabled", True):
        logger.info("Telegram sync disabled in configuration")
        return None

    # Determine if we need full history
    last_sync = state.get("telegram", {}).get("last_sync")
    is_first_run = last_sync is None
    use_full_history = is_first_run and config.get("full_history_on_first_run", True)

    # Calculate date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    if is_first_run:
        start_date = "2023-01-01"
    else:
        start_date = last_sync

    # Build output filename
    source_id = "telegram_kaspa-groups"
    date_range = get_date_range(start_date, end_date)
    output_file = output_dir / f"{source_id}_{date_range}.json"

    # Build command
    cmd = ["python3", "-m", "scripts.telegram_ingest", "--output", str(output_file)]

    if use_full_history:
        cmd.append("--full-history")

    logger.info(f"Running Telegram sync: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ Telegram sync successful: {output_file}")
            # Update state
            if "telegram" not in state:
                state["telegram"] = {}
            state["telegram"]["last_sync"] = end_date
            state["telegram"]["last_output"] = str(output_file)
            return str(output_file)
        elif result.returncode == 2:
            logger.info("📭 No new Telegram content found")
            return None
        else:
            logger.error(f"❌ Telegram sync failed: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"❌ Error running Telegram sync: {e}")
        return None


def run_medium_sync(config: Dict, state: Dict, output_dir: Path) -> Optional[str]:
    """Run Medium articles sync"""
    medium_config = config["sources"]["medium"]
    if not medium_config.get("enabled", True):
        logger.info("Medium sync disabled in configuration")
        return None

    # Determine sync mode
    sync_mode = medium_config.get("sync_mode", "incremental")
    last_sync = state.get("medium", {}).get("last_sync")
    is_first_run = last_sync is None
    use_full_history = is_first_run and config.get("full_history_on_first_run", True)

    # Calculate date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    if is_first_run:
        start_date = "2023-01-01"
    else:
        if sync_mode == "incremental":
            # For incremental, we'll let the ingest script handle date filtering
            start_date = last_sync
        else:
            start_date = last_sync

    # Build output filename
    source_id = "medium_kaspa-authors"
    date_range = get_date_range(start_date, end_date)
    output_file = output_dir / f"{source_id}_{date_range}.json"

    # Build command
    cmd = ["python3", "-m", "scripts.medium_ingest", "--output", str(output_file)]

    if use_full_history:
        cmd.append("--full-history")
    elif not is_first_run and sync_mode == "incremental":
        # For incremental updates after first run, don't use full-history
        logger.info(f"Using incremental sync mode for Medium from {start_date}")

    logger.info(f"Running Medium sync: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ Medium sync successful: {output_file}")
            # Update state
            if "medium" not in state:
                state["medium"] = {}
            state["medium"]["last_sync"] = end_date
            state["medium"]["last_output"] = str(output_file)
            return str(output_file)
        elif result.returncode == 2:
            logger.info("📭 No new Medium content found")
            return None
        else:
            logger.error(f"❌ Medium sync failed: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"❌ Error running Medium sync: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Sync filtered knowledge base content to Terah AI agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script extracts specific content from the Kaspa knowledge base and exports it
to the Terah repository for AI agent consumption. It maintains its own state and
configuration separate from the main pipeline.

Configuration: config/terah_sync.json
State tracking: .terah/sync_state.json

Examples:
  python scripts/sync_to_terah.py              # Run sync for all configured sources
  python scripts/sync_to_terah.py --source discourse  # Sync only Discourse forums
  python scripts/sync_to_terah.py --force      # Force full resync
  python scripts/sync_to_terah.py --dry-run    # Show what would be synced
""",
    )

    parser.add_argument(
        "--source",
        choices=["discourse", "github", "telegram", "medium"],
        help="Sync only a specific source",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full resync, ignoring previous state",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without actually running",
    )
    parser.add_argument(
        "--output-dir", type=str, help="Override output directory from config"
    )

    args = parser.parse_args()

    print("🤖 Terah Knowledge Sync")
    print("=" * 50)

    # Load configuration and state
    config = load_config()
    state = load_state() if not args.force else {}

    # Determine output directory
    output_dir = (
        Path(args.output_dir) if args.output_dir else Path(config["output_dir"])
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Output directory: {output_dir}")
    print(f"🔧 Configuration: {CONFIG_PATH}")
    print(f"📊 State tracking: {STATE_PATH}")

    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No actual sync will be performed")

    print()

    # Track synced files
    synced_files = []

    # Run syncs based on configuration
    sources = ["discourse", "github", "telegram", "medium"]
    if args.source:
        sources = [args.source]

    for source in sources:
        if not config["sources"].get(source, {}).get("enabled", True):
            continue

        print(f"\n📥 Syncing {source.upper()}...")

        if args.dry_run:
            print(f"   Would sync {source} to {output_dir}")
            continue

        output_file = None
        if source == "discourse":
            output_file = run_discourse_sync(config, state, output_dir)
        elif source == "github":
            output_file = run_github_sync(config, state, output_dir)
        elif source == "telegram":
            output_file = run_telegram_sync(config, state, output_dir)
        elif source == "medium":
            output_file = run_medium_sync(config, state, output_dir)

        if output_file:
            synced_files.append(output_file)

    # Save updated state
    if not args.dry_run and synced_files:
        save_state(state)
        print(f"\n💾 State updated: {STATE_PATH}")

    # Summary
    print("\n" + "=" * 50)
    print("📊 Sync Summary:")
    if synced_files:
        print(f"✅ Successfully synced {len(synced_files)} sources:")
        for f in synced_files:
            print(f"   - {Path(f).name}")
    else:
        print("📭 No new content to sync")

    print("\n✨ Terah sync complete!")

    # Exit with appropriate code
    # 0 = success with files synced
    # 2 = success but no new content (following ingest script convention)
    # 1 = error (default for exceptions)
    sys.exit(0 if synced_files else 2)


if __name__ == "__main__":
    main()
