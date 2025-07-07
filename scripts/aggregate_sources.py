import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Iterator, Tuple
from calendar import monthrange

# Add the scripts directory to Python path for imports
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from signal_enrichment import SignalEnrichmentService  # noqa: E402


class SourcesAggregator:
    def __init__(
        self,
        sources_dir: str = "sources",
        output_dir: str = "data/aggregated",
        force: bool = False,
    ):
        self.sources_dir = Path(sources_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.force = force

        # Mapping of source directories to aggregated data keys
        self.source_mappings = {
            "medium": "medium_articles",
            "telegram": "telegram_messages",
            "github_summaries": "github_activity",
            "discord": "discord_messages",
            "forum": "forum_posts",
            "news": "news_articles",
        }

        # Initialize signal enrichment service
        self.signal_service = SignalEnrichmentService()

    def get_daily_file_path(self, date: str) -> Path:
        """Get the file path for aggregated data for a given date."""
        if date == "full_history":
            return self.output_dir / "full_history_aggregated.json"
        else:
            return self.output_dir / f"{date}.json"

    def load_source_data(self, source_name: str, date: str) -> List[Dict]:
        """Load data from a specific source folder for a given date."""
        source_folder = Path(self.sources_dir) / source_name

        # For backfill mode, look for full_history.json files
        if date == "full_history":
            history_file = source_folder / "full_history.json"
            if history_file.exists():
                try:
                    with open(history_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Handle different data structures
                    if isinstance(data, dict):
                        if "data" in data:
                            return data["data"]
                        elif source_name in data:
                            return data[source_name]
                        elif "articles" in data and source_name == "medium":
                            return data["articles"]
                        elif "messages" in data and source_name == "telegram":
                            return data["messages"]
                        elif "posts" in data and source_name == "forum":
                            return data["posts"]
                        elif "forum_posts" in data and source_name == "forum":
                            # FIX: Handle forum_posts key in backfill mode
                            return data["forum_posts"]
                        else:
                            # If it's a dict but no expected keys, return empty
                            return []
                    elif isinstance(data, list):
                        return data
                    else:
                        return []
                except Exception as e:
                    print(f"Warning: Could not read {history_file}: {e}")
                    return []
            else:
                # No full_history.json file exists for this source
                return []

        # Regular dated file processing (existing logic)
        date_file = source_folder / f"{date}.json"
        if not date_file.exists():
            return []

        try:
            with open(date_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle different data structures that various sources might have
            if isinstance(data, dict):
                # Check for common data container keys
                if "data" in data:
                    return data["data"]
                elif source_name in data:
                    return data[source_name]
                elif "articles" in data and source_name == "medium":
                    return data["articles"]
                elif "messages" in data and source_name == "telegram":
                    return data["messages"]
                elif "posts" in data and source_name == "forum":
                    return data["posts"]
                elif "forum_posts" in data and source_name == "forum":
                    # FIX: Handle alternative forum data structure
                    return data["forum_posts"]
                else:
                    # FIX: Enhanced debugging for forum data structures
                    if source_name == "forum":
                        print(f"Debug: Forum data keys found: {list(data.keys())}")
                        # Try to find any list of forum-like data
                        for key, value in data.items():
                            if isinstance(value, list) and len(value) > 0:
                                first_item = value[0]
                                if isinstance(first_item, dict) and (
                                    "post_id" in first_item or "topic_id" in first_item
                                ):
                                    print(
                                        f"Found forum posts in key '{key}': "
                                        f"{len(value)} items"
                                    )
                                    return value

                    # FIX: Return as list if it's a dict with data
                    # (helps with briefing generation)
                    if isinstance(data, dict) and any(
                        isinstance(v, list) for v in data.values()
                    ):
                        # For sources like forum, convert dict values to flattened list
                        all_items = []
                        for key, value in data.items():
                            if isinstance(value, list):
                                all_items.extend(value)
                        return all_items

                    # If it's a dict but no expected keys, return empty
                    return []
            elif isinstance(data, list):
                # Direct list of items
                return data
            else:
                # Unexpected format
                return []

        except Exception as e:
            print(f"Warning: Could not read {date_file}: {e}")
            return []

    def load_telegram_data(self, date: str) -> List[Dict]:
        """Load Telegram data from all group directories for a given date."""
        telegram_dir = self.sources_dir / "telegram"
        all_messages = []

        if not telegram_dir.exists():
            print("No Telegram directory found")
            return []

        # Check for main telegram file first (new structure)
        main_file = telegram_dir / f"{date}.json"
        if main_file.exists():
            try:
                with open(main_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict) and data.get("status") == "no_new_content":
                    print(
                        f"No Telegram data found for {date} "
                        "(empty file with metadata)"
                    )
                    return []
                elif isinstance(data, dict) and "messages" in data:
                    messages = data.get("messages", [])
                    msg_count = len(messages)
                    print(f"Loaded {msg_count} Telegram messages from main")
                    return messages
                elif isinstance(data, list):
                    print(f"Loaded {len(data)} Telegram messages from main")
                    return data
            except Exception as e:
                print(f"Error loading main Telegram file: {e}")

        # Fallback: Check group subdirectories (legacy structure)
        group_count = 0
        for group_dir in telegram_dir.iterdir():
            if group_dir.is_dir():
                daily_file = group_dir / f"{date}.json"
                if daily_file.exists():
                    try:
                        with open(daily_file, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        # Handle new metadata structure or legacy structure
                        if (
                            isinstance(data, dict)
                            and data.get("status") == "no_new_content"
                        ):
                            print(
                                f"No new content found for "
                                f"{group_dir.name} on {date} "
                                f"(empty file with metadata)"
                            )
                            group_count += 1  # Still count as processed
                        elif isinstance(data, dict) and "messages" in data:
                            # New structure with metadata
                            group_data = data.get("messages", [])
                            all_messages.extend(group_data)
                            group_count += 1
                            group_msg_count = len(group_data)
                            print(
                                f"Loaded {group_msg_count} "
                                f"messages from {group_dir.name}"
                            )
                        elif isinstance(data, list):
                            # Legacy structure (list of messages)
                            all_messages.extend(data)
                            group_count += 1
                            print(
                                f"Loaded {len(data)} messages " f"from {group_dir.name}"
                            )
                        else:
                            print(f"Unexpected data in {group_dir.name}")

                    except Exception as e:
                        print(f"Error loading {group_dir.name} data: {e}")

        if group_count == 0:
            print(f"No Telegram data found for {date}")
        else:
            total_msgs = len(all_messages)
            print(
                f"Loaded {total_msgs} total Telegram messages "
                f"from {group_count} groups"
            )

        return all_messages

    def load_github_summaries(self, date: str) -> List[Dict]:
        """Load GitHub summaries from Markdown files for a given date."""
        github_summaries_dir = self.sources_dir / "github_summaries"
        summary_file = github_summaries_dir / f"{date}.md"

        if not summary_file.exists():
            print(f"No GitHub summaries found for {date}")
            return []

        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Convert Markdown content to a structured format for
            # aggregation
            summary_data = {
                "type": "github_summary",
                "date": date,
                "content": content,
                "format": "markdown",
                "generated_at": datetime.now().isoformat(),
                "source": "github_summaries",
            }

            print(f"Loaded GitHub summary ({len(content)} characters)")
            return [summary_data]  # Return as single-item list for consistency

        except Exception as e:
            print(f"Error loading GitHub summaries: {e}")
            return []

    def load_github_activities(self, date: str) -> List[Dict]:
        """Load processed GitHub activity data for a given date."""
        github_folder = Path(self.sources_dir) / "github"

        # For backfill mode, look for full_history.json
        if date == "full_history":
            history_file = github_folder / "full_history.json"
            if history_file.exists():
                try:
                    with open(history_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Process GitHub history data structure
                    if isinstance(data, dict):
                        activities = []
                        # GitHub full_history structure:
                        # { repo_name: { activity_type: [items] } }
                        for repo_name, repo_data in data.items():
                            if isinstance(repo_data, dict):
                                for activity_type, items in repo_data.items():
                                    if isinstance(items, list):
                                        for item in items:
                                            if isinstance(item, dict):
                                                # FIX: Add proper title mapping
                                                # for GitHub activities
                                                enriched_item = {
                                                    **item,
                                                    "repo": repo_name,
                                                    "activity_type": activity_type,
                                                }

                                                # Map proper titles based on
                                                # activity type
                                                if activity_type == "commits":
                                                    enriched_item["title"] = item.get(
                                                        "message", "Unknown commit"
                                                    )
                                                elif activity_type in [
                                                    "pull_requests",
                                                    "issues",
                                                ]:
                                                    enriched_item["title"] = item.get(
                                                        "title",
                                                        f"Unknown {activity_type[:-1]}",
                                                    )

                                                # Ensure content field exists
                                                # for facts extraction
                                                if "content" not in enriched_item:
                                                    if activity_type == "commits":
                                                        enriched_item["content"] = (
                                                            item.get("message", "")
                                                        )
                                                    elif (
                                                        activity_type == "pull_requests"
                                                    ):
                                                        enriched_item["content"] = (
                                                            item.get("body", "")
                                                        )
                                                    elif activity_type == "issues":
                                                        enriched_item["content"] = (
                                                            item.get("body", "")
                                                        )
                                                    else:
                                                        enriched_item["content"] = ""

                                                activities.append(enriched_item)
                        return activities
                    elif isinstance(data, list):
                        return data
                    return []
                except Exception as e:
                    print(f"Warning: Could not read GitHub history: {e}")
                    return []
            else:
                return []

        # Regular dated file processing (existing logic)
        date_file = github_folder / f"{date}.json"
        if not date_file.exists():
            return []

        try:
            with open(date_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            activities = []
            if isinstance(data, dict):
                # Process each repository's activities
                for repo_name, repo_data in data.items():
                    if isinstance(repo_data, dict):
                        for activity_type, items in repo_data.items():
                            if isinstance(items, list):
                                for item in items:
                                    if isinstance(item, dict):
                                        # FIX: Add proper title mapping
                                        # for GitHub activities
                                        enriched_item = {
                                            **item,
                                            "repo": repo_name,
                                            "activity_type": activity_type,
                                        }

                                        # Map proper titles based on activity type
                                        if activity_type == "commits":
                                            enriched_item["title"] = item.get(
                                                "message", "Unknown commit"
                                            )
                                        elif activity_type in [
                                            "pull_requests",
                                            "issues",
                                        ]:
                                            enriched_item["title"] = item.get(
                                                "title", f"Unknown {activity_type[:-1]}"
                                            )

                                        # Ensure content field exists
                                        # for facts extraction
                                        if "content" not in enriched_item:
                                            if activity_type == "commits":
                                                enriched_item["content"] = item.get(
                                                    "message", ""
                                                )
                                            elif activity_type == "pull_requests":
                                                enriched_item["content"] = item.get(
                                                    "body", ""
                                                )
                                            elif activity_type == "issues":
                                                enriched_item["content"] = item.get(
                                                    "body", ""
                                                )
                                            else:
                                                enriched_item["content"] = ""

                                        activities.append(enriched_item)
            return activities

        except Exception as e:
            print(f"Warning: Could not read GitHub activities: {e}")
            return []

    def aggregate_daily_sources(self, date: str = None) -> Dict[str, Any]:
        """Aggregate all sources for a given date into raw aggregated data."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        if date == "full_history":
            print("\n🔄 Aggregating comprehensive historical data (backfill mode)")
            print("📚 Processing full_history.json files from all sources")
        else:
            print(f"\n🔄 Aggregating raw sources for {date}")
        print("=" * 50)

        # Check if aggregated data already exists for this date (deduplication)
        # Skip this check for backfill mode to allow reprocessing
        if not self.force and date != "full_history":
            existing_aggregated_path = self.get_daily_file_path(date)
            if existing_aggregated_path.exists():
                try:
                    with open(existing_aggregated_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)

                    # Add flag to indicate this was loaded from existing file
                    existing_data["_loaded_from_existing"] = True

                    print(f"Found existing aggregated data for {date}")
                    print(f"   Using existing file: {existing_aggregated_path}")
                    print("   (Use --force to regenerate)")

                    return existing_data
                except Exception as e:
                    print(f"Warning: Could not read existing data: {e}")
                    print("   Proceeding with fresh aggregation...")

        # Create the aggregated data structure
        aggregated_data = {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "processing_mode": "backfill" if date == "full_history" else "daily_sync",
            "sources": {},
            "metadata": {
                "total_items": 0,
                "sources_processed": [],
                "pipeline_version": "2.0.0",
                "processing_notes": (
                    "Enhanced with intelligent scoring system"
                    if date == "full_history"
                    else "Raw aggregation with signal enrichment"
                ),
            },
        }

        # Load data from each source and apply signal enrichment with scoring
        for source_folder, aggregated_key in self.source_mappings.items():
            source_data = self.load_source_data(source_folder, date)

            # Apply signal enrichment and sorting with appropriate date fields
            if source_data:
                # Determine the date field based on source type
                date_field = self._get_date_field_for_source(source_folder)

                # Enrich items with signal metadata and scoring
                enriched_data = self.signal_service.enrich_items(
                    source_data, date_field=date_field
                )
                # Sort by signal priority using the new final_score
                sorted_data = self.signal_service.sort_by_signal_priority(enriched_data)
                aggregated_data["sources"][aggregated_key] = sorted_data
            else:
                aggregated_data["sources"][aggregated_key] = source_data

            if source_data:
                aggregated_data["metadata"]["total_items"] += len(source_data)
                aggregated_data["metadata"]["sources_processed"].append(
                    f"{source_folder}: {len(source_data)} items"
                )

        # Load GitHub activities separately (for facts extraction) and apply
        # signal enrichment with scoring
        github_activities = self.load_github_activities(date)
        if github_activities:
            # Apply signal enrichment to GitHub activities with appropriate date field
            enriched_github_activities = self.signal_service.enrich_items(
                github_activities, date_field="date"
            )
            # Sort GitHub activities by signal priority using final_score
            sorted_github_activities = self.signal_service.sort_by_signal_priority(
                enriched_github_activities
            )
            aggregated_data["sources"]["github_activities"] = sorted_github_activities

            aggregated_data["metadata"]["total_items"] += len(github_activities)
            aggregated_data["metadata"]["sources_processed"].append(
                f"github_activities: {len(github_activities)} items"
            )

        # Add empty structures for other data types
        aggregated_data["sources"]["onchain_data"] = {}
        aggregated_data["sources"]["documentation"] = []

        # Add enhanced signal analysis metadata if high-signal contributors are
        # configured
        if self.signal_service.is_enabled():
            signal_analysis = self.signal_service.analyze_signal_distribution(
                aggregated_data["sources"]
            )
            aggregated_data["metadata"]["signal_analysis"] = signal_analysis

            # Add enhanced summary to processing metadata including scoring info
            if signal_analysis["high_signal_items"] > 0:
                high_signal_count = signal_analysis["high_signal_items"]
                lead_count = signal_analysis["lead_developer_items"]
                founder_count = signal_analysis.get("founder_items", 0)

                # Build signal summary with scoring information
                signal_parts = [f"{high_signal_count} high-signal items"]
                if lead_count > 0:
                    signal_parts.append(f"{lead_count} from lead developer")
                if founder_count > 0:
                    signal_parts.append(f"{founder_count} from founder")

                # Add scoring information if available
                scoring_enabled = signal_analysis.get("scoring_enabled", False)
                if scoring_enabled:
                    avg_score = signal_analysis.get("average_final_score", 0)
                    max_score = signal_analysis.get("max_final_score", 0)
                    signal_parts.append(
                        f"avg score: {avg_score:.2f}, max: {max_score:.2f}"
                    )

                signal_summary = (
                    " (" + ", ".join(signal_parts[1:]) + ")"
                    if len(signal_parts) > 1
                    else ""
                )
                full_summary = signal_parts[0] + signal_summary

                aggregated_data["metadata"]["sources_processed"].append(
                    f"signal_analysis: {full_summary}"
                )

        return aggregated_data

    def _get_date_field_for_source(self, source_folder: str) -> str:
        """Get the appropriate date field name for a given source type."""
        date_field_mapping = {
            "medium": "published",
            "telegram": "date",
            "github_summaries": "date",
            "discord": "date",
            "forum": "created_at",
            "news": "date",
        }
        return date_field_mapping.get(source_folder, "date")

    def save_aggregated_data(self, data: Dict[str, Any], date: str = None) -> Path:
        """Save the aggregated data to file."""
        if date is None:
            date = data.get("date", datetime.now().strftime("%Y-%m-%d"))

        # For backfill mode, save to a special backfill file
        if date == "full_history":
            output_path = self.output_dir / "full_history_aggregated.json"
        else:
            output_path = self.get_daily_file_path(date)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def run_aggregation(self, date: str = None) -> str:
        """Main aggregation function - combines all sources into raw daily
        file."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Aggregate all sources
        aggregated_data = self.aggregate_daily_sources(date)

        # Check if data was loaded from existing file (deduplication)
        loaded_from_existing = aggregated_data.pop("_loaded_from_existing", False)

        # Save to file (only if new aggregation)
        if not loaded_from_existing:
            output_path = self.save_aggregated_data(aggregated_data, date)
        else:
            # Don't save, just reference existing path
            output_path = self.get_daily_file_path(date)

        # Show brief summary if loaded from existing, detailed if newly
        # aggregated
        if loaded_from_existing:
            print(
                "\nRaw Sources Aggregation found existing content - "
                "skipping downstream processing"
            )
            success_msg = (
                "Raw sources aggregation skipped - using existing " "aggregated data"
            )
        else:
            # Print detailed summary for new aggregations
            print("\nRaw aggregation complete!")
            print(f"Output: {output_path}")
            print(f"Total items: {aggregated_data['metadata']['total_items']}")
            print("Sources processed:")
            for source in aggregated_data["metadata"]["sources_processed"]:
                print(f"   - {source}")

            # Display signal analysis summary if available
            signal_analysis = aggregated_data.get("metadata", {}).get("signal_analysis")
            if signal_analysis:
                print("\nSignal Analysis Summary:")
                high_signal = signal_analysis["high_signal_items"]
                total_items = signal_analysis["total_items"]
                lead_items = signal_analysis["lead_developer_items"]
                founder_items = signal_analysis.get("founder_items", 0)
                print(f"   High-signal items: {high_signal}/{total_items}")
                print(f"   Lead developer items: {lead_items}")
                if founder_items > 0:
                    print(f"   Founder items: {founder_items}")
                if signal_analysis["contributor_roles"]:
                    roles = signal_analysis["contributor_roles"]
                    role_items = [f"{role}({count})" for role, count in roles.items()]
                    role_summary = ", ".join(role_items)
                    print(f"   Contributor roles: {role_summary}")
                if signal_analysis["sources_with_signals"]:
                    sources = signal_analysis["sources_with_signals"].keys()
                    sources_summary = ", ".join(sources)
                    print(f"   Sources with signals: {sources_summary}")

            success_msg = f"Raw sources aggregation completed! Saved to {output_path}"

        return success_msg

    def generate_date_range(self, start_date: str, end_date: str) -> Iterator[str]:
        """Generate a range of dates between start_date and end_date (inclusive)."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        current = start
        while current <= end:
            yield current.strftime("%Y-%m-%d")
            current += timedelta(days=1)

    def get_period_chunks(
        self, start_date: str, end_date: str, period: str
    ) -> List[Tuple[str, str, str]]:
        """
        Generate period chunks (weekly/monthly) between start_date and end_date.
        Returns list of tuples: (period_start, period_end, period_label)
        """
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

    def aggregate_period_data(
        self, start_date: str, end_date: str, period_label: str
    ) -> Dict[str, Any]:
        """
        Aggregate data across multiple daily files for a given period.
        Returns combined aggregated data for the period.
        """
        print(
            f"Aggregating data for period {period_label} ({start_date} to {end_date})"
        )

        # Initialize combined data structure
        combined_data = {
            "date_range": f"{start_date} to {end_date}",
            "period": period_label,
            "generated_at": datetime.now().isoformat(),
            "sources": {},
            "metadata": {
                "total_items": 0,
                "sources_processed": [],
                "date_range": f"{start_date} to {end_date}",
                "period_type": (
                    period_label.split("-")[0] if "-" in period_label else "custom"
                ),
                "days_processed": 0,
                "files_found": 0,
                "files_missing": 0,
            },
        }

        # Initialize source containers
        for source_name, aggregated_key in self.source_mappings.items():
            combined_data["sources"][aggregated_key] = []

        # Add containers for special sources
        combined_data["sources"]["github_activities"] = []
        combined_data["sources"]["onchain_data"] = {}
        combined_data["sources"]["documentation"] = []

        # Process each date in the range
        dates_processed = []
        files_found = 0
        files_missing = 0

        for date in self.generate_date_range(start_date, end_date):
            print(f"  Processing date: {date}")

            # Check if aggregated data exists for this date
            daily_file = self.get_daily_file_path(date)
            if daily_file.exists():
                try:
                    with open(daily_file, "r", encoding="utf-8") as f:
                        daily_data = json.load(f)

                    files_found += 1
                    dates_processed.append(date)

                    # Merge sources data
                    if "sources" in daily_data:
                        for source_key, source_data in daily_data["sources"].items():
                            if source_key in combined_data["sources"]:
                                if isinstance(source_data, list):
                                    combined_data["sources"][source_key].extend(
                                        source_data
                                    )
                                elif (
                                    isinstance(source_data, dict)
                                    and source_key == "onchain_data"
                                ):
                                    # For onchain_data, merge dict keys
                                    for key, value in source_data.items():
                                        if (
                                            key
                                            not in combined_data["sources"][source_key]
                                        ):
                                            combined_data["sources"][source_key][
                                                key
                                            ] = value
                                        else:
                                            # If it's a list, extend it
                                            if isinstance(
                                                combined_data["sources"][source_key][
                                                    key
                                                ],
                                                list,
                                            ):
                                                combined_data["sources"][source_key][
                                                    key
                                                ].extend(value)

                    # Add to metadata
                    if "metadata" in daily_data:
                        daily_meta = daily_data["metadata"]
                        if "total_items" in daily_meta:
                            combined_data["metadata"]["total_items"] += daily_meta[
                                "total_items"
                            ]

                        if "sources_processed" in daily_meta:
                            for source_info in daily_meta["sources_processed"]:
                                combined_data["metadata"]["sources_processed"].append(
                                    f"{date}: {source_info}"
                                )

                except Exception as e:
                    print(f"    Warning: Could not process {daily_file}: {e}")
                    files_missing += 1
            else:
                print(f"    No data file found for {date}")
                files_missing += 1

        # Update metadata
        combined_data["metadata"]["days_processed"] = len(dates_processed)
        combined_data["metadata"]["files_found"] = files_found
        combined_data["metadata"]["files_missing"] = files_missing
        combined_data["metadata"]["dates_processed"] = dates_processed

        # Apply signal enrichment to combined data if enabled
        if self.signal_service.is_enabled():
            print("  Applying signal enrichment to combined data...")
            for source_key, source_data in combined_data["sources"].items():
                if isinstance(source_data, list) and source_data:
                    # Get appropriate date field for this source
                    source_name = next(
                        (k for k, v in self.source_mappings.items() if v == source_key),
                        None,
                    )
                    if source_name:
                        date_field = self._get_date_field_for_source(source_name)
                        enriched_data = self.signal_service.enrich_items(
                            source_data, date_field=date_field
                        )
                        sorted_data = self.signal_service.sort_by_signal_priority(
                            enriched_data
                        )
                        combined_data["sources"][source_key] = sorted_data

            # Analyze signal distribution for the period
            signal_analysis = self.signal_service.analyze_signal_distribution(
                combined_data["sources"]
            )
            combined_data["metadata"]["signal_analysis"] = signal_analysis

        return combined_data

    def save_period_data(
        self, data: Dict[str, Any], period_label: str, period_type: str
    ) -> Path:
        """Save period-aggregated data to file with appropriate naming."""
        filename = f"{period_label}-{period_type}.json"
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def run_period_aggregation(
        self, start_date: str, end_date: str, period: str = "monthly"
    ) -> str:
        """
        Run period-based aggregation across a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            period: Period type - 'daily', 'weekly', or 'monthly'

        Returns:
            Success message with summary
        """
        if period == "daily":
            # For daily period, just process each date individually
            results = []
            for date in self.generate_date_range(start_date, end_date):
                result = self.run_aggregation(date)
                results.append(f"  {date}: {result}")

            return (
                f"Daily aggregation completed for {start_date} to {end_date}:\n"
                + "\n".join(results)
            )

        # Get period chunks
        chunks = self.get_period_chunks(start_date, end_date, period)

        if not chunks:
            return (
                f"No valid {period} periods found for date range "
                f"{start_date} to {end_date}"
            )

        print(f"Found {len(chunks)} {period} periods to process")

        results = []
        for period_start, period_end, period_label in chunks:
            # Aggregate data for this period
            period_data = self.aggregate_period_data(
                period_start, period_end, period_label
            )

            # Save period data
            output_path = self.save_period_data(period_data, period_label, period)

            # Create summary
            total_items = period_data["metadata"]["total_items"]
            files_found = period_data["metadata"]["files_found"]
            files_missing = period_data["metadata"]["files_missing"]

            result_summary = (
                f"{period_label}: {total_items} items from {files_found} files"
            )
            if files_missing > 0:
                result_summary += f" ({files_missing} missing)"

            results.append(result_summary)

            print(f"  Completed {period_label}: {output_path}")
            print(f"    Total items: {total_items}")
            print(f"    Files processed: {files_found}")
            if files_missing > 0:
                print(f"    Files missing: {files_missing}")

        return f"Period-based aggregation completed ({period}):\n" + "\n".join(
            f"  {r}" for r in results
        )


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Aggregate raw sources from Kaspa knowledge data"
    )

    # Original single-date arguments
    parser.add_argument(
        "--date",
        help="Date to process (YYYY-MM-DD format). Defaults to today.",
        default=None,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-aggregation even if data already exists for this date",
    )

    # New period-based arguments
    parser.add_argument(
        "--start-date",
        help="Start date for period aggregation (YYYY-MM-DD format)",
        default=None,
    )
    parser.add_argument(
        "--end-date",
        help="End date for period aggregation (YYYY-MM-DD format)",
        default=None,
    )
    parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly"],
        default="monthly",
        help="Period type for aggregation (daily, weekly, monthly). Default: monthly",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.start_date or args.end_date:
        # Period-based aggregation mode
        if not args.start_date:
            parser.error("--start-date is required when using period aggregation")
        if not args.end_date:
            parser.error("--end-date is required when using period aggregation")

        # Validate date format
        try:
            start_datetime = datetime.strptime(args.start_date, "%Y-%m-%d")
            end_datetime = datetime.strptime(args.end_date, "%Y-%m-%d")
        except ValueError as e:
            parser.error(f"Invalid date format: {e}")

        # Validate date range
        if start_datetime > end_datetime:
            parser.error("--start-date must be before or equal to --end-date")

        # Check for conflicting arguments
        if args.date:
            parser.error("Cannot use --date with --start-date/--end-date")

        # Run period-based aggregation
        aggregator = SourcesAggregator(force=args.force)
        result = aggregator.run_period_aggregation(
            args.start_date, args.end_date, args.period
        )
        print(f"\nPeriod aggregation completed:\n{result}")

    else:
        # Single-date aggregation mode (original behavior)
        aggregator = SourcesAggregator(force=args.force)
        result = aggregator.run_aggregation(args.date)
        print(f"\n{result}")


if __name__ == "__main__":
    main()
