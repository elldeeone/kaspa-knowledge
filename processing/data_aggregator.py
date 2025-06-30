import json
import os
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path


class DataAggregator:
    def __init__(self, output_dir: str = "data/aggregated"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def get_daily_file_path(self, date: str = None) -> Path:
        """Get the file path for a specific date's aggregated data."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return self.output_dir / f"{date}.json"
    
    def load_daily_data(self, date: str = None) -> Dict[str, Any]:
        """Load existing daily data, return empty structure if file doesn't exist."""
        file_path = self.get_daily_file_path(date)
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Return empty daily structure
        return {
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat(),
            "sources": {
                "medium_articles": [],
                "github_activity": [],
                "discord_messages": [],
                "forum_posts": [],
                "onchain_data": {},
                "documentation": []
            },
            "metadata": {
                "total_items": 0,
                "processing_time": None,
                "pipeline_version": "1.0.0"
            }
        }
    
    def save_daily_data(self, data: Dict[str, Any], date: str = None) -> Path:
        """Save daily aggregated data to JSON file."""
        file_path = self.get_daily_file_path(date)
        
        # Update metadata
        data["metadata"]["total_items"] = sum(
            len(v) if isinstance(v, list) else 1 if v else 0 
            for v in data["sources"].values()
        )
        data["generated_at"] = datetime.now().isoformat()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return file_path
    
    def add_medium_article(self, article: Dict[str, Any], date: str = None) -> bool:
        """Add a Medium article to daily data, avoiding duplicates."""
        daily_data = self.load_daily_data(date)
        
        # Check for duplicates by URL
        existing_urls = {item.get("link") for item in daily_data["sources"]["medium_articles"]}
        if article.get("link") in existing_urls:
            print(f"Article already exists: {article.get('title', 'Unknown')}")
            return False
        
        # Add article with timestamp
        article_with_meta = {
            **article,
            "processed_at": datetime.now().isoformat(),
            "source_type": "medium_rss"
        }
        
        daily_data["sources"]["medium_articles"].append(article_with_meta)
        self.save_daily_data(daily_data, date)
        print(f"Added article: {article.get('title', 'Unknown')}")
        return True
    
    def get_article_count(self, date: str = None) -> int:
        """Get the number of Medium articles for a specific date."""
        daily_data = self.load_daily_data(date)
        return len(daily_data["sources"]["medium_articles"])


# Example usage
if __name__ == "__main__":
    aggregator = DataAggregator()
    
    # Test adding an article
    sample_article = {
        "title": "Test Article",
        "author": "Test Author",
        "published": "2023-01-01",
        "link": "https://example.com/test",
        "summary": "Test summary",
        "llm_summary": "Test LLM summary"
    }
    
    aggregator.add_medium_article(sample_article)
    print(f"Total articles today: {aggregator.get_article_count()}") 