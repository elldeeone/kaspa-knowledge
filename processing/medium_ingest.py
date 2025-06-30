import os
import json
import feedparser
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

# Load environment variables
load_dotenv()

# Default to Yonatan Sompolinsky's Medium RSS feed
MEDIUM_RSS_URL = os.getenv("MEDIUM_RSS_URL", "https://hashdag.medium.com/feed")


def fetch_medium_articles(rss_url, max_articles=10):
    """Fetch articles from Medium RSS feed."""
    feed = feedparser.parse(rss_url)
    articles = []
    
    for entry in feed.entries[:max_articles]:
        # Extract publication date
        pub_date = "Unknown"
        if hasattr(entry, 'published'):
            try:
                pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
            except ValueError:
                try:
                    pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y-%m-%d")
                except ValueError:
                    pub_date = "Unknown"
        
        # Extract author
        author = getattr(entry, 'author', 'Unknown')
        
        article = {
            "title": entry.title,
            "link": entry.link,
            "summary": entry.summary,  # This contains the full article content from RSS
            "author": author,
            "published": pub_date,
            "ingested_at": datetime.now().isoformat(),
            "source_type": "medium_rss",
            "rss_url": rss_url
        }
        
        articles.append(article)
    
    return articles


def save_raw_medium_data(articles, date=None):
    """Save raw Medium articles to sources/medium/ directory."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Create sources/medium directory
    sources_dir = Path("sources/medium")
    sources_dir.mkdir(parents=True, exist_ok=True)
    
    # Save to daily file
    output_path = sources_dir / f"{date}.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(articles)} raw articles to: {output_path}")
    return output_path


def main():
    """Main function to run Medium article ingestion."""
    print("🔄 Starting Medium article ingestion...")
    print(f"📡 RSS URL: {MEDIUM_RSS_URL}")
    
    try:
        # Fetch articles from RSS feed
        articles = fetch_medium_articles(MEDIUM_RSS_URL, max_articles=10)
        
        if not articles:
            print("⚠️  No articles found in RSS feed")
            return
        
        print(f"📄 Found {len(articles)} articles")
        
        # Display article titles
        for i, article in enumerate(articles, 1):
            print(f"  {i}. {article['title']}")
        
        # Save raw data to sources directory
        output_path = save_raw_medium_data(articles)
        
        print(f"\n🎉 Medium ingestion complete!")
        print(f"📁 Raw data saved to: {output_path}")
        print(f"ℹ️  LLM processing will happen during aggregation step")
        
    except Exception as e:
        print(f"❌ Error during Medium ingestion: {e}")
        raise


if __name__ == "__main__":
    main() 