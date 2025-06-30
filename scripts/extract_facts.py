#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - Daily Facts Extractor

This script reads the raw aggregated daily data and extracts
key technical facts, insights, and important developments.

Inspired by elizaOS daily facts extraction.
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

    def extract_medium_facts(self, articles: List[Dict]) -> List[Dict[str, Any]]:
        """Extract key facts from Medium articles."""
        if not articles:
            return []

        print(f"🔍 Extracting facts from {len(articles)} Medium articles...")

        all_facts = []

        for i, article in enumerate(articles, 1):
            print(f"  {i}/{len(articles)} - {article['title'][:60]}...")

            try:
                prompt = prompt_loader.format_prompt(
                    "extract_kaspa_facts",
                    title=article['title'],
                    author=article['author'],
                    url=article['link'],
                    content=article['summary'][:4000] + "..."
                )

                system_prompt = prompt_loader.get_system_prompt("extract_kaspa_facts")
                facts_response = self.llm.call_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                )

                # Parse the facts (simple parsing for now)
                facts = self.parse_facts_response(facts_response, article)
                all_facts.extend(facts)

                print(f"    ✅ Extracted {len(facts)} facts")

            except Exception as e:
                print(f"    ⚠️  Failed to extract facts: {e}")

        return all_facts

    def parse_facts_response(
        self, response: str, article: Dict
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
                    facts.append(self.finalize_fact(current_fact, article))
                current_fact = {"fact": line[7:].strip()}
            elif line.startswith("- CATEGORY:"):
                current_fact["category"] = line[11:].strip()
            elif line.startswith("- IMPACT:"):
                current_fact["impact"] = line[9:].strip()
            elif line.startswith("- CONTEXT:"):
                current_fact["context"] = line[10:].strip()

        # Don't forget the last fact
        if current_fact:
            facts.append(self.finalize_fact(current_fact, article))

        return facts

    def finalize_fact(self, fact: Dict, article: Dict) -> Dict[str, Any]:
        """Finalize a fact with metadata."""
        return {
            "fact": fact.get("fact", ""),
            "category": fact.get("category", "other"),
            "impact": fact.get("impact", "medium"),
            "context": fact.get("context", ""),
            "source": {
                "type": "medium_article",
                "title": article["title"],
                "author": article["author"],
                "url": article["link"],
                "published": article.get("published", "Unknown"),
            },
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

        # Extract facts from each source
        all_facts = []

        # Medium articles
        medium_facts = self.extract_medium_facts(
            daily_data["sources"].get("medium_articles", [])
        )
        all_facts.extend(medium_facts)

        # TODO: Add other sources (GitHub, Discord, Forum, News)

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
            "sources": {
                "medium": len(medium_facts)
                # TODO: Add other sources
            },
        }

        facts_data = {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "facts": all_facts,
            "facts_by_category": facts_by_category,
            "statistics": fact_stats,
            "metadata": {
                "extractor_version": "1.0.0",
                "llm_model": self.llm.model,
                "total_sources_processed": len(
                    [k for k, v in daily_data["sources"].items() if v]
                ),
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
        """Main function to extract and save daily facts."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Extract facts
        facts_data = self.extract_daily_facts(date)

        # Save to file
        output_path = self.save_facts(facts_data, date)

        print("\n✅ Facts extraction complete!")
        print(f"📁 Output: {output_path}")
        print(f"📊 Total facts extracted: {facts_data['statistics']['total_facts']}")

        # Print category breakdown
        if facts_data["statistics"]["by_category"]:
            print("📋 Facts by category:")
            for category, count in facts_data["statistics"]["by_category"].items():
                print(f"   - {category}: {count}")

        # Print impact breakdown
        impact_stats = facts_data["statistics"]["by_impact"]
        print(
            f"🎯 By impact: High: {impact_stats['high']}, "
            f"Medium: {impact_stats['medium']}, Low: {impact_stats['low']}"
        )

        return str(output_path)


def main():
    extractor = FactsExtractor()
    result_path = extractor.run_facts_extraction()
    print(f"\n🎉 Successfully extracted facts: {result_path}")


if __name__ == "__main__":
    main()
