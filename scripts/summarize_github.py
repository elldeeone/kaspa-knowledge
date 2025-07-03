#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - GitHub Activity Summarizer

This script processes raw GitHub data and creates AI-generated
summaries suitable for knowledge extraction and daily briefings.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from scripts.llm_interface import LLMInterface
from scripts.prompt_loader import prompt_loader


class GitHubSummarizer:
    def __init__(
        self,
        input_dir: str = "sources/github",
        output_dir: str = "sources/github_summaries",
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize LLM interface
        self.llm = LLMInterface()

        # Track processing statistics
        self.stats = {
            "files_processed": 0,
            "repositories_processed": 0,
            "summaries_generated": 0,
            "errors": 0,
            "total_tokens": 0,
        }

    def log_info(self, message: str):
        """Log informational messages"""
        print(f"ℹ️  {message}")

    def log_error(self, message: str):
        """Log error messages"""
        print(f"❌ ERROR: {message}")
        self.stats["errors"] += 1

    def log_warning(self, message: str):
        """Log warning messages"""
        print(f"⚠️  WARNING: {message}")

    def prepare_activity_data(self, repo_data: Dict[str, Any]) -> str:
        """Prepare repository activity data for LLM processing"""

        # Extract key information in a clean format
        activity_summary = {
            "repository_info": {
                "name": repo_data.get("repository", {}).get("full_name", "Unknown"),
                "description": repo_data.get("repository", {}).get("description", ""),
                "stars": repo_data.get("repository", {}).get("stars", 0),
                "language": repo_data.get("repository", {}).get("language", "Unknown"),
            },
            "commits": [],
            "pull_requests": [],
            "issues": [],
        }

        # Process commits
        for commit in repo_data.get("commits", [])[:20]:  # Limit to 20 most recent
            activity_summary["commits"].append(
                {
                    "sha": commit.get("sha", "")[:8],  # Short SHA
                    "message": commit.get("message", "")[:100]
                    + ("..." if len(commit.get("message", "")) > 100 else ""),
                    "author": commit.get("author", "Unknown"),
                    "date": commit.get("date", ""),
                    "files_changed": commit.get("files_changed", 0),
                    "additions": commit.get("stats", {}).get("additions", 0),
                    "deletions": commit.get("stats", {}).get("deletions", 0),
                }
            )

        # Process pull requests
        for pr in repo_data.get("pull_requests", [])[:15]:  # Limit to 15 most recent
            activity_summary["pull_requests"].append(
                {
                    "number": pr.get("number", 0),
                    "title": pr.get("title", ""),
                    "author": pr.get("author", "Unknown"),
                    "state": pr.get("state", "unknown"),
                    "created_at": pr.get("created_at", ""),
                    "updated_at": pr.get("updated_at", ""),
                    "merged_at": pr.get("merged_at"),
                    "additions": pr.get("additions", 0),
                    "deletions": pr.get("deletions", 0),
                    "changed_files": pr.get("changed_files", 0),
                    "labels": pr.get("labels", []),
                }
            )

        # Process issues
        for issue in repo_data.get("issues", [])[:15]:  # Limit to 15 most recent
            activity_summary["issues"].append(
                {
                    "number": issue.get("number", 0),
                    "title": issue.get("title", ""),
                    "author": issue.get("author", "Unknown"),
                    "state": issue.get("state", "unknown"),
                    "created_at": issue.get("created_at", ""),
                    "updated_at": issue.get("updated_at", ""),
                    "closed_at": issue.get("closed_at"),
                    "labels": issue.get("labels", []),
                    "comments": issue.get("comments", 0),
                }
            )

        # Convert to JSON string for LLM processing
        return json.dumps(activity_summary, indent=2)

    def summarize_repository(
        self, repo_name: str, repo_data: Dict[str, Any]
    ) -> Optional[str]:
        """Generate a summary for a single repository"""
        self.log_info(f"Summarizing repository: {repo_name}")

        try:
            # Count activities
            commit_count = len(repo_data.get("commits", []))
            pr_count = len(repo_data.get("pull_requests", []))
            issue_count = len(repo_data.get("issues", []))
            total_activity = commit_count + pr_count + issue_count

            # Get metadata for summary
            metadata = repo_data.get("metadata", {})
            days_back = metadata.get("days_back", "unknown")
            repo_description = metadata.get("description", "")
            stars = metadata.get("stars", "unknown")
            language = metadata.get("language", "unknown")

            # If no activity, generate a concise summary without LLM
            if total_activity == 0:
                self.log_info(
                    f"  📝 No activity found for {repo_name} - "
                    "generating concise summary"
                )

                summary = f"# {repo_name} – Activity Summary\n"
                if repo_description:
                    summary += f"**{repo_description}**\n"
                summary += f"**Period:** Last {days_back} days\n\n"
                summary += (
                    "**Status:** No development activity detected "
                    "during this period.\n\n"
                )
                summary += f"**Repository Info:** {stars} stars"
                if language != "unknown":
                    summary += f" • {language}"
                summary += "\n"

                self.log_info(
                    f"  ✅ Generated concise summary ({len(summary)} characters)"
                )
                self.stats["summaries_generated"] += 1
                return summary

            # If there is activity, use LLM for detailed analysis
            self.log_info(
                f"  📝 Found activity ({total_activity} items) - "
                f"generating detailed AI summary for {repo_name}..."
            )

            # Prepare activity data
            activity_data = self.prepare_activity_data(repo_data)

            # Get metadata for prompt variables
            fetched_at = metadata.get("fetched_at", "unknown")

            # Generate summary using LLM
            prompt = prompt_loader.format_prompt(
                "summarize_github_activity",
                repo_name=repo_name,
                days_back=days_back,
                fetched_at=fetched_at,
                activity_data=activity_data,
                commit_count=commit_count,
                pr_count=pr_count,
                issue_count=issue_count,
            )

            system_prompt = prompt_loader.get_system_prompt("summarize_github_activity")

            summary = self.llm.call_llm(prompt=prompt, system_prompt=system_prompt)

            self.log_info(
                f"  ✅ Generated detailed summary ({len(summary)} characters)"
            )
            self.stats["summaries_generated"] += 1
            return summary

        except Exception as e:
            self.log_error(f"Failed to summarize {repo_name}: {e}")
            return None

    def process_github_file(self, file_path: Path) -> Dict[str, str]:
        """Process a single GitHub JSON file and generate summaries for all
        repositories"""
        self.log_info(f"📂 Processing file: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.log_error(f"Cannot read file {file_path}: {e}")
            return {}

        if not isinstance(data, dict):
            self.log_error(f"Invalid data format in {file_path}")
            return {}

        summaries = {}

        for repo_name, repo_data in data.items():
            if not isinstance(repo_data, dict):
                self.log_warning(f"Skipping invalid repository data: {repo_name}")
                continue

            summary = self.summarize_repository(repo_name, repo_data)
            if summary:
                summaries[repo_name] = summary
                self.stats["repositories_processed"] += 1

        self.stats["files_processed"] += 1
        return summaries

    def save_summaries(self, summaries: Dict[str, str], date: str) -> Path:
        """Save repository summaries to output file"""
        output_file = self.output_dir / f"{date}.md"

        # Check if all summaries are "no activity" summaries
        all_no_activity = all(
            "No development activity detected" in summary
            for summary in summaries.values()
        )

        if all_no_activity and len(summaries) > 0:
            # Create minimal summary when no repositories have activity
            content = f"# GitHub Activity Summary - {date}\n\n"
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            content += f"*Generated on {timestamp} UTC*\n\n"
            content += (
                f"**Status:** No development activity detected across "
                f"{len(summaries)} monitored Kaspa repositories.\n\n"
            )

            # List repositories briefly
            repo_names = list(summaries.keys())
            content += f"**Repositories Monitored:** {', '.join(repo_names)}\n"

        elif len(summaries) == 0:
            # Handle case where no summaries were generated at all
            content = f"# GitHub Activity Summary - {date}\n\n"
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            content += f"*Generated on {timestamp} UTC*\n\n"
            content += "**Status:** No GitHub data available for processing.\n"

        else:
            # Create comprehensive summary document when there is activity
            content = f"# GitHub Activity Summary - {date}\n\n"
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            content += f"*Generated on {timestamp} UTC*\n\n"
            content += "## Overview\n\n"
            content += (
                "This document contains summaries of recent GitHub activity "
                "across monitored Kaspa repositories.\n\n"
            )
            content += f"**Repositories Summarized:** {len(summaries)}\n\n"

            # Add individual repository summaries
            for repo_name, summary in summaries.items():
                content += "---\n\n"
                content += f"# Repository: {repo_name}\n\n"
                content += f"{summary}\n\n"

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)

            self.log_info(f"✅ Saved summaries to: {output_file}")
            return output_file

        except IOError as e:
            self.log_error(f"Failed to save summaries: {e}")
            return None

    def process_directory(self, specific_date: Optional[str] = None) -> bool:
        """Process all GitHub JSON files in the input directory"""
        if not self.input_dir.exists():
            self.log_error(f"Input directory does not exist: {self.input_dir}")
            return False

        # Find JSON files to process
        if specific_date:
            json_files = [self.input_dir / f"{specific_date}.json"]
            json_files = [f for f in json_files if f.exists()]
        else:
            json_files = list(self.input_dir.glob("*.json"))

        if not json_files:
            self.log_warning(f"No JSON files found in {self.input_dir}")
            return True

        self.log_info(f"🔍 Found {len(json_files)} JSON files to process")

        success = True
        for json_file in sorted(json_files):
            # Extract date from filename
            date = json_file.stem

            # Process the file
            summaries = self.process_github_file(json_file)

            if summaries:
                output_file = self.save_summaries(summaries, date)
                if not output_file:
                    success = False
            else:
                self.log_warning(f"No summaries generated for {json_file}")

        return success

    def print_summary(self):
        """Print processing summary"""
        print("\n" + "=" * 60)
        print("📊 GITHUB SUMMARIZATION SUMMARY")
        print("=" * 60)

        print(f"Files processed: {self.stats['files_processed']}")
        print(f"Repositories processed: {self.stats['repositories_processed']}")
        print(f"Summaries generated: {self.stats['summaries_generated']}")
        print(f"Errors encountered: {self.stats['errors']}")

        # Cost information if available
        cost_info = self.llm.get_cost_summary()
        if cost_info.get("total_tokens", 0) > 0:
            print(f"Total tokens used: {cost_info['total_tokens']}")
            if cost_info.get("total_cost", 0) > 0:
                print(f"Total cost: ${cost_info['total_cost']:.4f}")

        if self.stats["errors"] == 0:
            print("\n✅ All processing completed successfully!")
        else:
            print(f"\n⚠️  Completed with {self.stats['errors']} errors")


def main():
    """Main summarization function"""
    parser = argparse.ArgumentParser(
        description="Generate AI summaries of GitHub repository activity"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="sources/github",
        help="Directory containing raw GitHub JSON files (default: sources/github)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="sources/github_summaries",
        help="Directory to save summary files (default: sources/github_summaries)",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Process specific date only (YYYY-MM-DD format)",
    )

    args = parser.parse_args()

    print("🤖 Starting GitHub activity summarization...")
    print(f"   📂 Input directory: {args.input_dir}")
    print(f"   📁 Output directory: {args.output_dir}")

    # Initialize summarizer
    summarizer = GitHubSummarizer(input_dir=args.input_dir, output_dir=args.output_dir)

    # Process files
    success = summarizer.process_directory(args.date)

    # Print summary
    summarizer.print_summary()

    if success:
        print("\n🎉 GitHub summarization completed successfully!")
    else:
        print("\n❌ GitHub summarization completed with errors")
        exit(1)


if __name__ == "__main__":
    main()
