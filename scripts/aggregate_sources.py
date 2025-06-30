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

        # Define source mappings - which source folder maps to which aggregated key
        self.source_mappings = {
            "medium": "medium_articles",
            "github": "github_activity",
            "discord": "discord_messages",
            "forum": "forum_posts",
            "news": "news_articles",
        }

    def get_daily_file_path(self, date: str) -> Path:
        """Get the path for the daily aggregated file."""
        return self.output_dir / f"{date}.json"

    def load_source_data(self, source_name: str, date: str) -> List[Dict]:
        """Load data from a specific source for a given date."""
        source_path = self.sources_dir / source_name / f"{date}.json"

        if not source_path.exists():
            print(f"📁 No data found for {source_name} on {date}")
            return []

        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"📁 Loaded {len(data)} items from {source_name}")
                return data
        except Exception as e:
            print(f"⚠️  Error loading {source_name} data: {e}")
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
