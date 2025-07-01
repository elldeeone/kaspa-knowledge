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
        self, input_dir: str = "data/aggregated", output_dir: str = "data/briefings"
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

    def generate_medium_briefing(self, articles: List[Dict]) -> Dict[str, Any]:
        """Generate a briefing for Medium articles."""
        if not articles:
            return {
                "summary": "No Medium articles found for this date.",
                "key_topics": [],
                "article_summaries": [],
            }

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

    def generate_daily_briefing(self, date: str = None) -> Dict[str, Any]:
        """Generate a comprehensive daily briefing from all sources."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        print(f"\n🔄 Generating daily briefing for {date}")
        print("=" * 50)

        # Load raw data
        daily_data = self.load_daily_data(date)

        briefing = {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "sources": {
                "medium": self.generate_medium_briefing(
                    daily_data["sources"].get("medium_articles", [])
                ),
                "github": {
                    "summary": "GitHub activity processing not yet implemented."
                },
                "discord": {
                    "summary": "Discord messages processing not yet implemented."
                },
                "forum": {"summary": "Forum posts processing not yet implemented."},
                "news": {"summary": "News articles processing not yet implemented."},
            },
            "metadata": {
                "total_sources_processed": len(
                    [k for k, v in daily_data["sources"].items() if v]
                ),
                "briefing_version": "1.0.0",
                "llm_model": self.llm.model,
            },
        }

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

        # Save to file
        output_path = self.save_briefing(briefing, date)

        print("\n✅ Briefing generation complete!")
        print(f"📁 Output: {output_path}")
        print(
            f"📊 Sources processed: {briefing['metadata']['total_sources_processed']}"
        )

        # Print summary stats
        medium_briefing = briefing["sources"]["medium"]
        if isinstance(medium_briefing, dict) and "article_count" in medium_briefing:
            print(f"📰 Medium articles: {medium_briefing['article_count']}")
            print(f"🏷️  Key topics: {', '.join(medium_briefing['key_topics'][:5])}")

        return str(output_path)


def main():
    generator = BriefingGenerator()
    result_path = generator.run_briefing_generation()
    print(f"\n🎉 Successfully generated briefing: {result_path}")


if __name__ == "__main__":
    main()
