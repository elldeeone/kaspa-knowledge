import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


class SourcesAggregator:
    def __init__(
        self, sources_dir: str = "sources", output_dir: str = "data/aggregated"
    ):
        self.sources_dir = Path(sources_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Mapping of source directories to aggregated data keys
        self.source_mappings = {
            "medium": "medium_articles",
            "telegram": "telegram_messages",
            "github_summaries": "github_activity",
            "discord": "discord_messages",
            "forum": "forum_posts",
            "news": "news_articles",
        }

    def get_daily_file_path(self, date: str) -> Path:
        """Get the path for the daily aggregated file."""
        return self.output_dir / f"{date}.json"

    def load_source_data(self, source_name: str, date: str) -> List[Dict]:
        """Load data from a specific source directory for a given date."""
        source_path = self.sources_dir / source_name / f"{date}.json"

        if not source_path.exists():
            print(f"📁 No data found for {source_name} on {date}")
            return []

        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle new "empty file with metadata" structure
            if isinstance(data, dict) and data.get("status") == "no_new_content":
                print(
                    f"📁 No new content found for {source_name} on {date} "
                    "(empty file with metadata)"
                )
                return []  # Return empty list but we know the source ran
            elif isinstance(data, dict) and "articles" in data:
                # Handle Medium's new structure with metadata
                items = data.get("articles", [])
                print(f"📁 Loaded {len(items)} items from {source_name}")
                return items
            elif isinstance(data, dict) and "messages" in data:
                # Handle Telegram's new structure with metadata
                items = data.get("messages", [])
                print(f"📁 Loaded {len(items)} items from {source_name}")
                return items
            elif isinstance(data, list):
                # Handle legacy structure (list of items)
                print(f"📁 Loaded {len(data)} items from {source_name}")
                return data
            else:
                print(f"⚠️  Unexpected data structure in {source_name}")
                return []

        except Exception as e:
            print(f"⚠️  Error loading {source_name} data: {e}")
            return []

    def load_telegram_data(self, date: str) -> List[Dict]:
        """Load Telegram data from all group directories for a given date."""
        telegram_dir = self.sources_dir / "telegram"
        all_messages = []

        if not telegram_dir.exists():
            print("📁 No Telegram directory found")
            return []

        # Check for main telegram file first (new structure)
        main_file = telegram_dir / f"{date}.json"
        if main_file.exists():
            try:
                with open(main_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict) and data.get("status") == "no_new_content":
                    print(
                        f"📁 No Telegram data found for {date} "
                        "(empty file with metadata)"
                    )
                    return []
                elif isinstance(data, dict) and "messages" in data:
                    messages = data.get("messages", [])
                    msg_count = len(messages)
                    print(f"📁 Loaded {msg_count} Telegram messages from main file")
                    return messages
                elif isinstance(data, list):
                    print(f"📁 Loaded {len(data)} Telegram messages from main file")
                    return data
            except Exception as e:
                print(f"⚠️  Error loading main Telegram file: {e}")

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
                                f"📁 No new content found for {group_dir.name} "
                                f"on {date} (empty file with metadata)"
                            )
                            group_count += 1  # Still count as processed
                        elif isinstance(data, dict) and "messages" in data:
                            # New structure with metadata
                            group_data = data.get("messages", [])
                            all_messages.extend(group_data)
                            group_count += 1
                            group_msg_count = len(group_data)
                            print(
                                f"📁 Loaded {group_msg_count} messages "
                                f"from {group_dir.name}"
                            )
                        elif isinstance(data, list):
                            # Legacy structure (list of messages)
                            all_messages.extend(data)
                            group_count += 1
                            print(
                                f"📁 Loaded {len(data)} messages "
                                f"from {group_dir.name}"
                            )
                        else:
                            print(f"⚠️  Unexpected data structure in {group_dir.name}")

                    except Exception as e:
                        print(f"⚠️  Error loading {group_dir.name} data: {e}")

        if group_count == 0:
            print(f"📁 No Telegram data found for {date}")
        else:
            total_msgs = len(all_messages)
            print(
                f"📁 Loaded {total_msgs} total Telegram messages "
                f"from {group_count} groups"
            )

        return all_messages

    def load_github_summaries(self, date: str) -> List[Dict]:
        """Load GitHub summaries from Markdown files for a given date."""
        github_summaries_dir = self.sources_dir / "github_summaries"
        summary_file = github_summaries_dir / f"{date}.md"

        if not summary_file.exists():
            print(f"📁 No GitHub summaries found for {date}")
            return []

        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Convert Markdown content to a structured format for aggregation
            summary_data = {
                "type": "github_summary",
                "date": date,
                "content": content,
                "format": "markdown",
                "generated_at": datetime.now().isoformat(),
                "source": "github_summaries",
            }

            print(f"📁 Loaded GitHub summary ({len(content)} characters)")
            return [summary_data]  # Return as single-item list for consistency

        except Exception as e:
            print(f"⚠️  Error loading GitHub summaries: {e}")
            return []

    def load_github_activities(self, date: str) -> List[Dict]:
        """Load raw GitHub activities with metadata for facts extraction."""
        github_dir = self.sources_dir / "github"
        github_file = github_dir / f"{date}.json"

        if not github_file.exists():
            print(f"📁 No raw GitHub data found for {date}")
            return []

        try:
            with open(github_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            activities = []

            # Process each repository's activities
            for repo_name, repo_data in data.items():
                if not isinstance(repo_data, dict):
                    continue

                repo_info = repo_data.get("repository", {})

                # Process commits
                for commit in repo_data.get("commits", []):
                    commit_msg = commit.get("message", "")
                    title = commit_msg.split("\n")[0]  # First line of commit
                    files_changed = commit.get("files_changed", 0)
                    additions = commit.get("stats", {}).get("additions", 0)
                    deletions = commit.get("stats", {}).get("deletions", 0)

                    content = (
                        f"Commit: {commit_msg}\n"
                        f"Files changed: {files_changed}\n"
                        f"Additions: {additions}\n"
                        f"Deletions: {deletions}"
                    )

                    activities.append(
                        {
                            "type": "github_commit",
                            "repository": repo_name,
                            "repository_url": repo_info.get(
                                "url", f"https://github.com/{repo_name}"
                            ),
                            "title": title,
                            "author": commit.get("author", "Unknown"),
                            "url": commit.get("url", ""),
                            "date": commit.get("date", ""),
                            "content": content,
                            "metadata": {
                                "sha": commit.get("sha", ""),
                                "stats": commit.get("stats", {}),
                                "files_changed": files_changed,
                            },
                        }
                    )

                # Process pull requests
                for pr in repo_data.get("pull_requests", []):
                    pr_number = pr.get("number", "")
                    pr_title = pr.get("title", "")
                    pr_body = pr.get("body", "")
                    pr_state = pr.get("state", "")
                    changed_files = pr.get("changed_files", 0)
                    additions = pr.get("additions", 0)
                    deletions = pr.get("deletions", 0)

                    content = (
                        f"PR #{pr_number}: {pr_title}\n"
                        f"{pr_body}\n"
                        f"State: {pr_state}\n"
                        f"Files changed: {changed_files}\n"
                        f"Additions: {additions}\n"
                        f"Deletions: {deletions}"
                    )

                    activities.append(
                        {
                            "type": "github_pull_request",
                            "repository": repo_name,
                            "repository_url": repo_info.get(
                                "url", f"https://github.com/{repo_name}"
                            ),
                            "title": pr_title,
                            "author": pr.get("author", "Unknown"),
                            "url": pr.get("url", ""),
                            "date": pr.get("created_at", ""),
                            "content": content,
                            "metadata": {
                                "number": pr_number,
                                "state": pr_state,
                                "draft": pr.get("draft", False),
                                "merged_at": pr.get("merged_at", ""),
                                "stats": {
                                    "additions": additions,
                                    "deletions": deletions,
                                    "changed_files": changed_files,
                                },
                            },
                        }
                    )

                # Process issues
                for issue in repo_data.get("issues", []):
                    issue_number = issue.get("number", "")
                    issue_title = issue.get("title", "")
                    issue_body = issue.get("body", "")
                    issue_state = issue.get("state", "")
                    comments = issue.get("comments", 0)

                    content = (
                        f"Issue #{issue_number}: {issue_title}\n"
                        f"{issue_body}\n"
                        f"State: {issue_state}\n"
                        f"Comments: {comments}"
                    )

                    activities.append(
                        {
                            "type": "github_issue",
                            "repository": repo_name,
                            "repository_url": repo_info.get(
                                "url", f"https://github.com/{repo_name}"
                            ),
                            "title": issue_title,
                            "author": issue.get("author", "Unknown"),
                            "url": issue.get("url", ""),
                            "date": issue.get("created_at", ""),
                            "content": content,
                            "metadata": {
                                "number": issue_number,
                                "state": issue_state,
                                "comments": comments,
                                "labels": issue.get("labels", []),
                                "assignees": issue.get("assignees", []),
                            },
                        }
                    )

            print(f"📁 Loaded {len(activities)} GitHub activities with metadata")
            return activities

        except Exception as e:
            print(f"⚠️  Error loading GitHub activities: {e}")
            return []

    def aggregate_daily_sources(self, date: str = None) -> Dict[str, Any]:
        """Aggregate all sources for a given date into raw aggregated data."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        print(f"\n🔄 Aggregating raw sources for {date}")
        print("=" * 50)

        # Initialize aggregated data structure
        aggregated_data = {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "sources": {},
            "metadata": {
                "total_items": 0,
                "processing_time": "0.00s",
                "pipeline_version": "2.0.0",
                "sources_processed": [],
            },
        }

        # Load data from each source
        for source_folder, aggregated_key in self.source_mappings.items():
            source_data = self.load_source_data(source_folder, date)
            aggregated_data["sources"][aggregated_key] = source_data

            if source_data:
                aggregated_data["metadata"]["total_items"] += len(source_data)
                aggregated_data["metadata"]["sources_processed"].append(
                    f"{source_folder}: {len(source_data)} items"
                )

        # Load GitHub activities separately (for facts extraction)
        github_activities = self.load_github_activities(date)
        if github_activities:
            aggregated_data["sources"]["github_activities"] = github_activities
            aggregated_data["metadata"]["total_items"] += len(github_activities)
            aggregated_data["metadata"]["sources_processed"].append(
                f"github_activities: {len(github_activities)} items"
            )

        # Add empty structures for other data types
        aggregated_data["sources"]["onchain_data"] = {}
        aggregated_data["sources"]["documentation"] = []

        return aggregated_data

    def save_aggregated_data(self, data: Dict[str, Any], date: str = None) -> Path:
        """Save the aggregated data to file."""
        if date is None:
            date = data.get("date", datetime.now().strftime("%Y-%m-%d"))

        output_path = self.get_daily_file_path(date)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def run_aggregation(self, date: str = None) -> str:
        """Main aggregation function - combines all sources into raw daily file."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Aggregate all sources
        aggregated_data = self.aggregate_daily_sources(date)

        # Save to file
        output_path = self.save_aggregated_data(aggregated_data, date)

        print("\n✅ Raw aggregation complete!")
        print(f"📁 Output: {output_path}")
        print(f"📊 Total items: {aggregated_data['metadata']['total_items']}")
        print("📋 Sources processed:")
        for source in aggregated_data["metadata"]["sources_processed"]:
            print(f"   - {source}")

        return str(output_path)


def main():
    aggregator = SourcesAggregator()
    result_path = aggregator.run_aggregation()
    print(f"\n🎉 Successfully aggregated raw sources to: {result_path}")


if __name__ == "__main__":
    main()
