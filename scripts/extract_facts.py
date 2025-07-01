#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - Daily Facts Extractor

This script reads the raw aggregated daily data and extracts
key technical facts, insights, and important developments from ALL sources.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from scripts.llm_interface import LLMInterface
from scripts.prompt_loader import prompt_loader


class FactsExtractor:
    def __init__(
        self, input_dir: str = "data/aggregated", output_dir: str = "data/facts"
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize LLM interface
        self.llm = LLMInterface()

    def load_daily_data(self, date: str) -> Dict[str, Any]:
        """Load the raw aggregated data for a given date."""
        input_path = self.input_dir / f"{date}.json"

        if not input_path.exists():
            raise FileNotFoundError(
                f"No aggregated data found for {date} at {input_path}"
            )

        with open(input_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def extract_facts_from_content(
        self, content: str, source_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract facts from any content using the generic LLM prompt."""
        if not content or not content.strip():
            return []

        try:
            prompt = prompt_loader.format_prompt(
                "extract_kaspa_facts",
                source_type=source_info["type"],
                title=source_info.get("title", "N/A"),
                author=source_info.get("author", "N/A"),
                url=source_info.get("url", "N/A"),
                date=source_info.get("date", "N/A"),
                content=content[:4000] + ("..." if len(content) > 4000 else ""),
            )

            system_prompt = prompt_loader.get_system_prompt("extract_kaspa_facts")
            facts_response = self.llm.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
            )

            # Parse the facts
            facts = self.parse_facts_response(facts_response, source_info)
            return facts

        except Exception as e:
            print(f"    ⚠️  Failed to extract facts from {source_info['type']}: {e}")
            return []

    def extract_medium_facts(self, articles: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key facts from Medium articles."""
        if not articles:
            return []

        print(f"🔍 Extracting facts from {len(articles)} Medium articles...")

        all_facts = []

        for i, article in enumerate(articles, 1):
            print(f"  {i}/{len(articles)} - {article['title'][:60]}...")

            source_info = {
                "type": "medium_article",
                "title": article["title"],
                "author": article["author"],
                "url": article["link"],
                "date": article.get("published", "Unknown"),
            }

            facts = self.extract_facts_from_content(
                article.get("summary", ""), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")
            else:
                print("    ℹ️  No facts extracted")

        return all_facts

    def extract_github_facts(
        self, github_activities: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Extract key facts from individual GitHub activities with proper metadata."""
        if not github_activities:
            return []

        print(f"🔍 Extracting facts from {len(github_activities)} GitHub activities...")

        all_facts = []

        for i, activity in enumerate(github_activities, 1):
            activity_type = activity.get("type", "unknown")
            title_preview = activity.get("title", "untitled")[:60]
            print(
                f"  {i}/{len(github_activities)} - {activity_type}: "
                f"{title_preview}..."
            )

            source_info = {
                "type": activity_type,
                "title": activity.get("title", ""),
                "author": activity.get("author", "Unknown"),
                "url": activity.get("url", ""),
                "date": activity.get("date", ""),
                "repository": activity.get("repository", ""),
            }

            facts = self.extract_facts_from_content(
                activity.get("content", ""), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")
            else:
                print("    ℹ️  No facts extracted")

        return all_facts

    def extract_telegram_facts(self, messages: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key facts from Telegram messages."""
        if not messages:
            return []

        print(f"🔍 Extracting facts from {len(messages)} Telegram messages...")

        all_facts = []

        for i, message in enumerate(messages, 1):
            sender_name = message.get("sender_name", "unknown")
            print(f"  {i}/{len(messages)} - Message from {sender_name}...")

            source_info = {
                "type": "telegram_message",
                "title": f"Telegram Message - {message.get('sender_name', 'Unknown')}",
                "author": message.get("sender_name", "Unknown"),
                "url": message.get("url", ""),
                "date": message.get("date", ""),
            }

            facts = self.extract_facts_from_content(
                message.get("content", ""), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")
            else:
                print("    ℹ️  No facts extracted")

        return all_facts

    def extract_discord_facts(self, messages: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key facts from Discord messages."""
        if not messages:
            return []

        print(f"🔍 Extracting facts from {len(messages)} Discord messages...")

        all_facts = []

        for i, message in enumerate(messages, 1):
            author_name = message.get("author", "unknown")
            print(f"  {i}/{len(messages)} - Message from {author_name}...")

            source_info = {
                "type": "discord_message",
                "title": f"Discord Message - {message.get('author', 'Unknown')}",
                "author": message.get("author", "Unknown"),
                "url": message.get("url", ""),
                "date": message.get("date", ""),
            }

            facts = self.extract_facts_from_content(
                message.get("content", ""), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")
            else:
                print("    ℹ️  No facts extracted")

        return all_facts

    def extract_forum_facts(self, posts: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key facts from forum posts."""
        if not posts:
            return []

        print(f"🔍 Extracting facts from {len(posts)} forum posts...")

        all_facts = []

        for i, post in enumerate(posts, 1):
            print(f"  {i}/{len(posts)} - Post: {post.get('title', 'untitled')[:60]}...")

            source_info = {
                "type": "forum_post",
                "title": post.get("title", "Untitled Forum Post"),
                "author": post.get("author", "Unknown"),
                "url": post.get("url", "Unknown"),
                "date": post.get("date", "unknown"),
            }

            facts = self.extract_facts_from_content(
                post.get("content", ""), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")

        return all_facts

    def extract_news_facts(self, articles: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key facts from news articles."""
        if not articles:
            return []

        print(f"🔍 Extracting facts from {len(articles)} news articles...")

        all_facts = []

        for i, article in enumerate(articles, 1):
            print(f"  {i}/{len(articles)} - {article.get('title', 'untitled')[:60]}...")

            source_info = {
                "type": "news_article",
                "title": article.get("title", "Untitled News Article"),
                "author": article.get("author", "Unknown"),
                "url": article.get("url", "Unknown"),
                "date": article.get("published", "unknown"),
            }

            facts = self.extract_facts_from_content(
                article.get("content", article.get("summary", "")), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")

        return all_facts

    def extract_documentation_facts(self, docs: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key facts from documentation updates."""
        if not docs:
            return []

        print(f"🔍 Extracting facts from {len(docs)} documentation items...")

        all_facts = []

        for i, doc in enumerate(docs, 1):
            print(f"  {i}/{len(docs)} - {doc.get('title', 'untitled')[:60]}...")

            source_info = {
                "type": "documentation",
                "title": doc.get("title", "Documentation Update"),
                "author": doc.get("author", "Kaspa Team"),
                "url": doc.get("url", "Unknown"),
                "date": doc.get("updated", "unknown"),
            }

            facts = self.extract_facts_from_content(doc.get("content", ""), source_info)
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")

        return all_facts

    def parse_facts_response(
        self, response: str, source_info: Dict
    ) -> List[Dict[str, Any]]:
        """Parse the LLM response into structured facts."""
        facts = []

        # Simple parsing - look for FACT: patterns
        lines = response.split("\n")
        current_fact = {}

        for line in lines:
            line = line.strip()
            if line.startswith("- FACT:"):
                if current_fact:  # Save previous fact
                    facts.append(self.finalize_fact(current_fact, source_info))
                current_fact = {"fact": line[7:].strip()}
            elif line.startswith("- CATEGORY:"):
                current_fact["category"] = line[11:].strip()
            elif line.startswith("- IMPACT:"):
                current_fact["impact"] = line[9:].strip()
            elif line.startswith("- CONTEXT:"):
                current_fact["context"] = line[10:].strip()

        # Don't forget the last fact
        if current_fact:
            facts.append(self.finalize_fact(current_fact, source_info))

        return facts

    def finalize_fact(self, fact: Dict, source_info: Dict) -> Dict[str, Any]:
        """Finalize a fact with metadata."""
        source_data = {
            "type": source_info["type"],
            "title": source_info.get("title", ""),
            "author": source_info.get("author", ""),
            "url": source_info.get("url", ""),
            "date": source_info.get("date", ""),
        }

        # Add repository info for GitHub activities
        if source_info.get("repository"):
            source_data["repository"] = source_info["repository"]

        return {
            "fact": fact.get("fact", ""),
            "category": fact.get("category", "other"),
            "impact": fact.get("impact", "medium"),
            "context": fact.get("context", ""),
            "source": source_data,
            "extracted_at": datetime.now().isoformat(),
        }

    def extract_daily_facts(self, date: str = None) -> Dict[str, Any]:
        """Extract facts from all sources for a given date."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        print(f"\n🔍 Extracting daily facts for {date}")
        print("=" * 50)

        # Load raw data
        daily_data = self.load_daily_data(date)
        sources = daily_data.get("sources", {})

        # Extract facts from each source
        all_facts = []
        source_stats = {}

        # Medium articles
        medium_facts = self.extract_medium_facts(sources.get("medium_articles", []))
        all_facts.extend(medium_facts)
        source_stats["medium"] = len(medium_facts)

        # GitHub activities (individual activities with metadata)
        github_facts = self.extract_github_facts(sources.get("github_activities", []))
        all_facts.extend(github_facts)
        source_stats["github"] = len(github_facts)

        # Telegram messages
        telegram_facts = self.extract_telegram_facts(
            sources.get("telegram_messages", [])
        )
        all_facts.extend(telegram_facts)
        source_stats["telegram"] = len(telegram_facts)

        # Discord messages
        discord_facts = self.extract_discord_facts(sources.get("discord_messages", []))
        all_facts.extend(discord_facts)
        source_stats["discord"] = len(discord_facts)

        # Forum posts
        forum_facts = self.extract_forum_facts(sources.get("forum_posts", []))
        all_facts.extend(forum_facts)
        source_stats["forum"] = len(forum_facts)

        # News articles
        news_facts = self.extract_news_facts(sources.get("news_articles", []))
        all_facts.extend(news_facts)
        source_stats["news"] = len(news_facts)

        # Documentation
        doc_facts = self.extract_documentation_facts(sources.get("documentation", []))
        all_facts.extend(doc_facts)
        source_stats["documentation"] = len(doc_facts)

        # Organize facts by category
        facts_by_category = {}
        for fact in all_facts:
            category = fact["category"]
            if category not in facts_by_category:
                facts_by_category[category] = []
            facts_by_category[category].append(fact)

        # Generate summary statistics
        fact_stats = {
            "total_facts": len(all_facts),
            "by_category": {
                cat: len(facts) for cat, facts in facts_by_category.items()
            },
            "by_impact": {
                "high": len([f for f in all_facts if f["impact"] == "high"]),
                "medium": len([f for f in all_facts if f["impact"] == "medium"]),
                "low": len([f for f in all_facts if f["impact"] == "low"]),
            },
            "by_source": source_stats,
        }

        facts_data = {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "facts": all_facts,
            "facts_by_category": facts_by_category,
            "statistics": fact_stats,
            "metadata": {
                "extractor_version": "2.0.0",
                "llm_model": self.llm.model,
                "total_sources_processed": len([k for k, v in sources.items() if v]),
                "sources_with_data": [k for k, v in sources.items() if v],
            },
        }

        return facts_data

    def save_facts(self, facts_data: Dict[str, Any], date: str = None) -> Path:
        """Save the extracted facts to file."""
        if date is None:
            date = facts_data.get("date", datetime.now().strftime("%Y-%m-%d"))

        output_path = self.output_dir / f"{date}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(facts_data, f, indent=2, ensure_ascii=False)

        return output_path

    def run_facts_extraction(self, date: str = None) -> str:
        """Run the complete facts extraction pipeline."""
        try:
            # Extract facts
            facts_data = self.extract_daily_facts(date)

            # Save facts
            output_path = self.save_facts(facts_data, date)

            # Print summary
            all_facts = facts_data["facts"]
            facts_by_category = facts_data["facts_by_category"]
            fact_stats = facts_data["statistics"]
            source_stats = fact_stats["by_source"]

            print("\n" + "=" * 60)
            print("📊 FACTS EXTRACTION SUMMARY")
            print("=" * 60)
            print(f"📅 Date: {date}")
            print(f"📋 Total facts extracted: {len(all_facts)}")
            print(f"🏷️  Categories: {len(facts_by_category)}")
            sources_with_facts = len([k for k, v in source_stats.items() if v > 0])
            print(f"📁 Sources processed: {sources_with_facts}")

            print("\n📊 BY CATEGORY:")
            for category, count in sorted(facts_by_category.items()):
                print(f"  {category}: {count}")

            print("\n📊 BY IMPACT:")
            for impact, count in sorted(fact_stats["by_impact"].items()):
                print(f"  {impact}: {count}")

            print("\n📊 BY SOURCE:")
            for source, count in source_stats.items():
                print(f"  {source}: {count}")

            print(f"\n💾 Facts saved to: {output_path}")

            total_with_facts = len([k for k, v in source_stats.items() if v > 0])
            success_msg = (
                f"🎯 Facts extraction completed! {len(all_facts)} facts "
                f"extracted from {total_with_facts} sources."
            )
            print(f"\n{success_msg}")

            return success_msg

        except Exception as e:
            error_msg = f"Facts extraction failed: {e}"
            print(f"❌ {error_msg}")
            return error_msg


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract facts from aggregated Kaspa knowledge data"
    )
    parser.add_argument(
        "--date",
        help="Date to process (YYYY-MM-DD format). Defaults to today.",
        default=None,
    )

    args = parser.parse_args()

    extractor = FactsExtractor()
    result = extractor.run_facts_extraction(args.date)
    print(f"\n🎯 {result}")


if __name__ == "__main__":
    main()
