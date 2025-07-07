#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - Daily Briefing Generator

This script reads the raw aggregated daily data and generates
high-level summaries and briefings using LLM processing.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from scripts.llm_interface import LLMInterface
from scripts.prompt_loader import prompt_loader


class BriefingGenerator:
    def __init__(
        self,
        input_dir: str = "data/aggregated",
        output_dir: str = "data/briefings",
        force: bool = False,
        period_summary: bool = False,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.force = force
        self.period_summary = period_summary

        # Initialize LLM interface
        self.llm = LLMInterface()

    def load_daily_data(self, date: str) -> Dict[str, Any]:
        """Load the raw aggregated data for a given date or period."""
        # Handle both regular dates and backfill mode
        if date == "full_history":
            input_path = self.input_dir / f"{date}_aggregated.json"
        elif self.period_summary:
            # For period summary mode, look for period-based files
            # Try different patterns: YYYY-MM-monthly.json, YYYY-MM-DD-weekly.json, etc.
            potential_paths = [
                self.input_dir / f"{date}.json",  # Direct match first
                self.input_dir / f"{date}-monthly.json",
                self.input_dir / f"{date}-weekly.json",
                self.input_dir / f"{date}-quarterly.json",
                self.input_dir / f"{date}-historical.json",
            ]

            input_path = None
            for path in potential_paths:
                if path.exists():
                    input_path = path
                    break

            if input_path is None:
                raise FileNotFoundError(
                    f"No period-based aggregated data found for {date}. "
                    f"Checked paths: {[str(p) for p in potential_paths]}"
                )
        else:
            input_path = self.input_dir / f"{date}.json"

        if not input_path.exists():
            raise FileNotFoundError(
                f"No aggregated data found for {date} at {input_path}"
            )

        with open(input_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def extract_period_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract period-specific metadata from aggregated data."""
        if not self.period_summary:
            return {}

        metadata = {}

        # Extract period information
        metadata["period_label"] = data.get("period", "Unknown Period")
        metadata["date_range"] = data.get("date_range", "Unknown Range")

        # Parse date range for start and end dates
        date_range = metadata["date_range"]
        if " to " in date_range:
            start_date, end_date = date_range.split(" to ")
            metadata["start_date"] = start_date.strip()
            metadata["end_date"] = end_date.strip()

            # Calculate duration in days
            try:
                start = datetime.strptime(start_date.strip(), "%Y-%m-%d")
                end = datetime.strptime(end_date.strip(), "%Y-%m-%d")
                metadata["duration_days"] = (end - start).days + 1
            except ValueError:
                metadata["duration_days"] = "Unknown"
        else:
            metadata["start_date"] = "Unknown"
            metadata["end_date"] = "Unknown"
            metadata["duration_days"] = "Unknown"

        # Count total items across all sources
        sources = data.get("sources", {})
        total_items = 0
        sources_processed = []

        for source_name, source_data in sources.items():
            if source_data and len(source_data) > 0:
                total_items += len(source_data)
                sources_processed.append(source_name)

        metadata["total_items"] = total_items
        metadata["sources_processed"] = ", ".join(sources_processed)

        return metadata

    def select_period_prompt(self, period_metadata: Dict[str, Any]) -> str:
        """Select appropriate prompt based on period type and duration."""
        if not self.period_summary:
            return "generate_daily_briefing"

        period_label = period_metadata.get("period_label", "").lower()
        duration_days = period_metadata.get("duration_days", 0)

        # Determine prompt based on period type or duration
        if "monthly" in period_label or (
            isinstance(duration_days, int) and duration_days >= 28
        ):
            return "generate_monthly_summary"
        elif "weekly" in period_label or (
            isinstance(duration_days, int) and 7 <= duration_days < 28
        ):
            return "generate_weekly_summary"
        elif "historical" in period_label or (
            isinstance(duration_days, int) and duration_days > 90
        ):
            return "generate_historical_summary"
        else:
            # Default to historical summary for period mode
            return "generate_historical_summary"

    def generate_medium_briefing(self, articles: List[Dict]) -> Dict[str, Any]:
        """Generate a briefing for Medium articles."""
        if not articles:
            return {
                "summary": "No Medium articles found for this date.",
                "key_topics": [],
                "article_summaries": [],
            }

        # If in period summary mode, use period-aware generation
        if self.period_summary:
            # We'll need period metadata here, but for now use existing logic
            # This will be enhanced when period metadata is available at this level
            pass

        print(f"🤖 Generating briefing for {len(articles)} Medium articles...")

        # Create article summaries
        article_summaries = []
        for i, article in enumerate(articles, 1):
            print(f"  {i}/{len(articles)} - {article['title'][:60]}...")

            try:
                prompt = prompt_loader.format_prompt(
                    "generate_article_summary",
                    title=article["title"],
                    author=article["author"],
                    url=article["link"],
                    content=article["summary"][:4000] + "...",
                )

                system_prompt = prompt_loader.get_system_prompt(
                    "generate_article_summary"
                )
                summary = self.llm.call_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                )

                article_summaries.append(
                    {
                        "title": article["title"],
                        "author": article["author"],
                        "url": article["link"],
                        "published": article.get("published", "Unknown"),
                        "summary": summary,
                    }
                )

                print(f"    ✅ Generated summary ({len(summary)} chars)")

            except Exception as e:
                print(f"    ⚠️  Failed to summarize: {e}")
                article_summaries.append(
                    {
                        "title": article["title"],
                        "author": article["author"],
                        "url": article["link"],
                        "published": article.get("published", "Unknown"),
                        "summary": f"[Summary generation failed: {str(e)}]",
                    }
                )

        # Generate overall briefing
        print("🤖 Generating overall Medium briefing...")

        titles_and_authors = "\n".join(
            [f"- {art['title']} (by {art['author']})" for art in articles]
        )

        briefing_prompt = prompt_loader.format_prompt(
            "generate_daily_briefing",
            article_count=len(articles),
            articles_list=titles_and_authors,
        )

        try:
            system_prompt = prompt_loader.get_system_prompt("generate_daily_briefing")
            overall_summary = self.llm.call_llm(
                prompt=briefing_prompt,
                system_prompt=system_prompt,
            )
        except Exception as e:
            overall_summary = f"[Briefing generation failed: {str(e)}]"

        # Extract key topics (simple keyword extraction for now)
        key_topics = []
        for article in articles:
            title_words = article["title"].lower().split()
            technical_terms = [
                "dagknight",
                "kaspa",
                "consensus",
                "pow",
                "mining",
                "asic",
                "optical",
                "blockchain",
                "cryptocurrency",
            ]
            for term in technical_terms:
                if term in " ".join(title_words) and term not in key_topics:
                    key_topics.append(term)

        return {
            "summary": overall_summary,
            "key_topics": key_topics,
            "article_summaries": article_summaries,
            "article_count": len(articles),
        }

    def generate_github_briefing(self, github_activity: List[Dict]) -> Dict[str, Any]:
        """Generate a briefing for GitHub activity."""
        if not github_activity:
            return {
                "summary": "No GitHub activity found for this date.",
                "repositories": [],
                "activity_summary": {},
            }

        print(f"🤖 Generating briefing for {len(github_activity)} GitHub summaries...")

        # Extract content from GitHub summaries
        combined_content = ""
        repo_count = 0

        for item in github_activity:
            if item.get("type") == "github_summary":
                combined_content += item.get("content", "")
                # Count repositories by looking for "Repository:" headers
                repo_count += item.get("content", "").count("# Repository:")

        if not combined_content:
            return {
                "summary": "No GitHub activity content available for processing.",
                "repositories": [],
                "activity_summary": {},
            }

        # Generate AI briefing from GitHub summaries
        try:
            github_summary = self.llm.call_llm(
                prompt=(
                    f"Summarize this GitHub activity data:\n\n"
                    f"{combined_content[:4000]}"
                ),
                system_prompt=(
                    "You are a technical project manager. Summarize GitHub "
                    "development activity focusing on key changes, contributors, "
                    "and trends. Keep it concise and actionable."
                ),
            )

            print(f"    ✅ Generated GitHub briefing ({len(github_summary)} chars)")

        except Exception as e:
            print(f"    ⚠️  Failed to generate GitHub briefing: {e}")
            github_summary = f"[GitHub briefing generation failed: {str(e)}]"

        return {
            "summary": github_summary,
            "repositories": repo_count,
            "activity_summary": {
                "summaries_processed": len(github_activity),
                "repositories_covered": repo_count,
            },
        }

    def generate_forum_briefing(self, forum_posts: List[Dict]) -> Dict[str, Any]:
        """Generate a briefing for forum posts from Discourse."""
        if not forum_posts:
            return {
                "summary": "No forum activity found for this date.",
                "post_count": 0,
                "topics": [],
                "key_discussions": [],
            }

        print(f"🤖 Generating briefing for {len(forum_posts)} forum posts...")

        # Group posts by topic for better analysis
        topics = {}
        for post in forum_posts:
            topic_id = post.get("topic_id")
            topic_title = post.get("topic_title", "Unknown Topic")

            if topic_id not in topics:
                topics[topic_id] = {
                    "title": topic_title,
                    "posts": [],
                    "authors": set(),
                }

            topics[topic_id]["posts"].append(post)
            if post.get("author"):
                topics[topic_id]["authors"].add(post.get("author"))

        # Convert sets to lists for JSON serialization
        for topic_data in topics.values():
            topic_data["authors"] = list(topic_data["authors"])

        # Prepare content for AI summarization (focus on most active topics)
        most_active_topics = sorted(
            topics.items(), key=lambda x: len(x[1]["posts"]), reverse=True
        )[
            :5
        ]  # Top 5 most active topics

        forum_content = ""
        for topic_id, topic_data in most_active_topics:
            forum_content += f"\n## Topic: {topic_data['title']}\n"
            forum_content += (
                f"Posts: {len(topic_data['posts'])}, "
                f"Authors: {len(topic_data['authors'])}\n"
            )

            # Include content from recent posts in this topic
            recent_posts = topic_data["posts"][:3]  # Most recent posts
            for post in recent_posts:
                content = post.get("raw_content") or post.get("content", "")
                if content:
                    # Truncate very long posts
                    if len(content) > 500:
                        content = content[:500] + "..."
                    forum_content += f"- {post.get('author', 'Unknown')}: {content}\n"

        # Generate AI briefing
        try:
            forum_summary = self.llm.call_llm(
                prompt=(
                    f"Summarize this Discourse forum activity, focusing on key "
                    f"discussions, technical topics, and community insights:\n\n"
                    f"{forum_content[:4000]}"
                ),
                system_prompt=(
                    "You are a community manager and technical analyst. Summarize "
                    "forum discussions focusing on key technical topics, important "
                    "questions, solutions shared, and community sentiment. "
                    "Highlight any significant developments or trends."
                ),
            )

            print(f"    ✅ Generated forum briefing ({len(forum_summary)} chars)")

        except Exception as e:
            print(f"    ⚠️  Failed to generate forum briefing: {e}")
            forum_summary = f"[Forum briefing generation failed: {str(e)}]"

        # Extract key topics and discussions
        key_discussions = []
        for topic_id, topic_data in most_active_topics:
            key_discussions.append(
                {
                    "title": topic_data["title"],
                    "post_count": len(topic_data["posts"]),
                    "author_count": len(topic_data["authors"]),
                    "topic_id": topic_id,
                }
            )

        # Extract technical terms mentioned
        all_content = " ".join(
            [
                post.get("raw_content", "") or post.get("content", "")
                for post in forum_posts
            ]
        ).lower()

        technical_terms = [
            "dagknight",
            "kaspa",
            "consensus",
            "pow",
            "mining",
            "asic",
            "optical",
            "blockchain",
            "cryptocurrency",
            "ghostdag",
            "research",
            "protocol",
            "scalability",
            "throughput",
            "finality",
        ]

        key_topics = [term for term in technical_terms if term in all_content]

        return {
            "summary": forum_summary,
            "post_count": len(forum_posts),
            "topic_count": len(topics),
            "key_discussions": key_discussions,
            "key_topics": key_topics,
            "most_active_topics": [
                {
                    "title": topic_data["title"],
                    "posts": len(topic_data["posts"]),
                }
                for _, topic_data in most_active_topics
            ],
        }

    def generate_daily_briefing(self, date: str = None) -> Dict[str, Any]:
        """Generate a comprehensive daily briefing from all sources."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        briefing_type = "period" if self.period_summary else "daily"
        print(f"\n🔄 Generating {briefing_type} briefing for {date}")
        print("=" * 50)

        # Check if briefing already exists for this date (deduplication)
        if not self.force:
            existing_briefing_path = self.output_dir / f"{date}.json"
            if existing_briefing_path.exists():
                try:
                    with open(existing_briefing_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)

                    # Check if existing briefing file has substantial content
                    if existing_data and existing_data.get("sources"):
                        print("📋 Briefing already exists for this date")
                        print("⚡ Skipping generation to avoid duplicates")
                        print("ℹ️  Use --force flag to override this behavior")

                        # Return existing data to maintain consistency
                        print("\n💾 Using existing briefing")
                        print(f"   📁 {existing_briefing_path}")

                        # Mark this data as loaded from existing file for summary logic
                        existing_data["_loaded_from_existing"] = True
                        return existing_data

                except (json.JSONDecodeError, IOError) as e:
                    print(f"⚠️  Warning: Could not read existing briefing file: {e}")
                    print("🔄 Proceeding with fresh generation...")
        else:
            print("⚠️  Force flag used - bypassing deduplication checks")

        # Load raw data
        daily_data = self.load_daily_data(date)

        # Extract period metadata if in period summary mode
        period_metadata = self.extract_period_metadata(daily_data)

        briefing = {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "sources": {
                "medium": self.generate_medium_briefing(
                    daily_data["sources"].get("medium_articles", [])
                ),
                "github": self.generate_github_briefing(
                    daily_data["sources"].get("github_activity", [])
                ),
                "telegram": {"summary": "Telegram processing not yet implemented."},
                "discord": {"summary": "Discord processing not yet implemented."},
                "forum": self.generate_forum_briefing(
                    daily_data["sources"].get("forum_posts", [])
                ),
                "news": {"summary": "News articles processing not yet implemented."},
            },
            "metadata": {
                "total_sources_processed": len(
                    [k for k, v in daily_data["sources"].items() if v]
                ),
                "briefing_version": "1.0.0",
                "llm_model": self.llm.model,
                "is_period_summary": self.period_summary,
            },
        }

        # Add period metadata to briefing if in period summary mode
        if self.period_summary and period_metadata:
            briefing["period_metadata"] = period_metadata

        return briefing

    def save_briefing(self, briefing: Dict[str, Any], date: str = None) -> Path:
        """Save the briefing to file."""
        if date is None:
            date = briefing.get("date", datetime.now().strftime("%Y-%m-%d"))

        output_path = self.output_dir / f"{date}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(briefing, f, indent=2, ensure_ascii=False)

        return output_path

    def run_briefing_generation(self, date: str = None) -> str:
        """Main function to generate and save daily briefing."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Generate briefing
        briefing = self.generate_daily_briefing(date)

        # Check if briefing was loaded from existing file (deduplication)
        loaded_from_existing = briefing.pop("_loaded_from_existing", False)

        # Save to file (only if new generation)
        if not loaded_from_existing:
            output_path = self.save_briefing(briefing, date)
        else:
            # Don't save, just reference existing path
            output_path = self.output_dir / f"{date}.json"

        # Show brief summary if loaded from existing, detailed if newly generated
        if loaded_from_existing:
            print(
                "\nℹ️  Daily Briefing Generation found existing content - "
                "skipping downstream processing"
            )
            success_msg = "Briefing generation skipped - using existing briefing"
        else:
            # Print detailed summary for new generations
            print("\n✅ Briefing generation complete!")
            print(f"📁 Output: {output_path}")
            print(f"📊 Sources: {briefing['metadata']['total_sources_processed']}")

            # Print summary stats
            medium_briefing = briefing["sources"]["medium"]
            if isinstance(medium_briefing, dict) and "article_count" in medium_briefing:
                print(f"📰 Medium articles: {medium_briefing['article_count']}")
                print(f"🏷️  Key topics: {', '.join(medium_briefing['key_topics'][:5])}")

            forum_briefing = briefing["sources"]["forum"]
            if isinstance(forum_briefing, dict) and "post_count" in forum_briefing:
                print(
                    f"🏛️  Forum posts: {forum_briefing['post_count']} across "
                    f"{forum_briefing.get('topic_count', 0)} topics"
                )
                if forum_briefing.get("key_topics"):
                    print(
                        f"🔬 Forum topics: {', '.join(forum_briefing['key_topics'][:5])}"
                    )

            success_msg = f"🎯 Briefing generation completed! Saved to {output_path}"

        return success_msg

    def generate_period_briefing(
        self, articles: List[Dict], period_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate period-based briefing for Medium articles."""
        if not articles:
            return {
                "summary": f"No Medium articles found for "
                f"{period_metadata.get('period_label', 'this period')}.",
                "key_topics": [],
                "article_summaries": [],
            }

        print(f"🤖 Generating period briefing for {len(articles)} Medium articles...")

        # Select appropriate prompt based on period
        prompt_name = self.select_period_prompt(period_metadata)

        # Create article summaries (using existing logic)
        article_summaries = []
        for i, article in enumerate(articles, 1):
            print(f"  {i}/{len(articles)} - {article['title'][:60]}...")

            try:
                prompt = prompt_loader.format_prompt(
                    "generate_article_summary",
                    title=article["title"],
                    author=article["author"],
                    url=article["link"],
                    content=article["summary"][:4000] + "...",
                )

                system_prompt = prompt_loader.get_system_prompt(
                    "generate_article_summary"
                )
                summary = self.llm.call_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                )

                article_summaries.append(
                    {
                        "title": article["title"],
                        "author": article["author"],
                        "url": article["link"],
                        "published": article.get("published", "Unknown"),
                        "summary": summary,
                    }
                )

                print(f"    ✅ Generated summary ({len(summary)} chars)")

            except Exception as e:
                print(f"    ⚠️  Failed to summarize: {e}")
                article_summaries.append(
                    {
                        "title": article["title"],
                        "author": article["author"],
                        "url": article["link"],
                        "published": article.get("published", "Unknown"),
                        "summary": f"[Summary generation failed: {str(e)}]",
                    }
                )

        # Generate overall period briefing using period-specific prompts
        print(f"🤖 Generating overall period briefing using {prompt_name}...")

        # Prepare content for period summary
        titles_and_authors = "\n".join(
            [f"- {art['title']} (by {art['author']})" for art in articles]
        )

        try:
            # Use period-specific prompt with metadata
            period_prompt = prompt_loader.format_prompt(
                prompt_name,
                period_label=period_metadata.get("period_label", "Unknown Period"),
                start_date=period_metadata.get("start_date", "Unknown"),
                end_date=period_metadata.get("end_date", "Unknown"),
                total_items=period_metadata.get("total_items", len(articles)),
                sources_processed=period_metadata.get("sources_processed", "Medium"),
                duration_days=period_metadata.get("duration_days", "Unknown"),
                article_count=len(articles),
                articles_list=titles_and_authors,
            )

            system_prompt = prompt_loader.get_system_prompt(prompt_name)
            overall_summary = self.llm.call_llm(
                prompt=period_prompt,
                system_prompt=system_prompt,
            )
        except Exception as e:
            overall_summary = f"[Period briefing generation failed: {str(e)}]"

        # Extract key topics (enhanced for period analysis)
        key_topics = []
        for article in articles:
            title_words = article["title"].lower().split()
            technical_terms = [
                "dagknight",
                "kaspa",
                "consensus",
                "pow",
                "mining",
                "asic",
                "optical",
                "blockchain",
                "cryptocurrency",
                "protocol",
                "scalability",
                "decentralization",
            ]
            for term in technical_terms:
                if term in " ".join(title_words) and term not in key_topics:
                    key_topics.append(term)

        return {
            "summary": overall_summary,
            "key_topics": key_topics,
            "article_summaries": article_summaries,
            "article_count": len(articles),
            "period_metadata": period_metadata,
        }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate daily briefings from aggregated Kaspa knowledge data"
    )
    parser.add_argument(
        "--date",
        help="Date to process (YYYY-MM-DD format). Defaults to today.",
        default=None,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-generation even if briefing already exists for this date",
    )
    parser.add_argument(
        "--period-summary",
        action="store_true",
        help="Generate period-based summary (weekly, monthly, historical) "
        "instead of daily briefing",
    )

    args = parser.parse_args()

    generator = BriefingGenerator(force=args.force, period_summary=args.period_summary)
    result = generator.run_briefing_generation(args.date)
    print(f"\n🎯 {result}")


if __name__ == "__main__":
    main()
