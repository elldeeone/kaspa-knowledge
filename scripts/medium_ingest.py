#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - Medium RSS Ingestion

Enhanced script that supports multiple author RSS feeds and full history backfill.
Follows the three-stage pipeline: Ingest → Aggregate → AI Process
"""

import os
import json
import feedparser
import argparse
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re

# Load environment variables
load_dotenv()

# Read multiple RSS URLs from environment variables
# Primary: MEDIUM_RSS_URLS (comma-separated list)
# Fallback: MEDIUM_RSS_URL (single URL for backward compatibility)
RSS_URLS_STR = os.getenv("MEDIUM_RSS_URLS")
if not RSS_URLS_STR:
    # Backward compatibility with single URL
    single_url = os.getenv("MEDIUM_RSS_URL", "https://hashdag.medium.com/feed")
    RSS_URLS_STR = single_url

RSS_URLS = [url.strip() for url in RSS_URLS_STR.split(",") if url.strip()]


def get_existing_article_links():
    """
    Fast deduplication: Load all existing article links from all medium files.
    Returns a set of links for O(1) lookup performance.
    """
    existing_links = set()
    sources_dir = Path("sources/medium")

    if not sources_dir.exists():
        return existing_links

    # Get all JSON files in the medium directory
    json_files = list(sources_dir.glob("*.json"))

    if not json_files:
        return existing_links

    print(f"🔍 Checking for existing articles across {len(json_files)} files...")

    total_existing = 0
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                articles = json.load(f)
                if isinstance(articles, list):
                    for article in articles:
                        if isinstance(article, dict) and "link" in article:
                            existing_links.add(article["link"])
                            total_existing += 1
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Warning: Could not read {file_path}: {e}")
            continue

    print(f"📚 Found {total_existing} existing articles for deduplication check")
    return existing_links


def filter_new_articles(all_articles, existing_links):
    """
    Filter out articles that already exist in our database.
    Returns only genuinely new articles.
    """
    if not existing_links:
        return all_articles

    new_articles = []
    for article in all_articles:
        if article.get("link") not in existing_links:
            new_articles.append(article)

    return new_articles


def scrape_individual_article(article_url):
    """Scrape a single Medium article directly from its URL."""
    print(f"🔗 Scraping individual article: {article_url}")

    try:
        # Set headers to avoid blocking
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }

        response = requests.get(article_url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Extract title - try multiple approaches
        title = "Unknown Title"

        # Try meta tags first (most reliable)
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            title = meta_title.get("content").strip()
        else:
            meta_title = soup.find("meta", property="twitter:title")
            if meta_title and meta_title.get("content"):
                title = meta_title.get("content").strip()

        # If meta tags don't work, try extracting from URL slug (fallback)
        if title == "Unknown Title":
            url_parts = article_url.split("/")
            if url_parts:
                slug = url_parts[-1]
                # Remove the hash part (last segment after last hyphen)
                slug_parts = slug.split("-")[
                    :-1
                ]  # Remove last part which is usually the hash
                if slug_parts:
                    title = " ".join(slug_parts).replace("-", " ").title()

        # Final fallback: try HTML title/h1
        if title == "Unknown Title":
            title_element = soup.find("h1") or soup.find("title")
            if title_element:
                title = title_element.get_text().strip()
                # Remove " - Medium" suffix if present
                title = re.sub(r"\s*-\s*Medium\s*$", "", title)

        # Extract author - try multiple approaches
        author = "Unknown Author"

        # Try meta tags first
        meta_author = soup.find("meta", property="article:author")
        if meta_author and meta_author.get("content"):
            author = meta_author.get("content").strip()

        # Try CSS selectors
        if author == "Unknown Author":
            author_selectors = [
                'a[rel="author"]',
                '[data-testid="authorName"]',
                ".author-name",
                'a[href*="/@"]',
            ]

            for selector in author_selectors:
                author_element = soup.select_one(selector)
                if author_element:
                    author = author_element.get_text().strip()
                    break

        # Extract from URL pattern (very reliable for Medium)
        if author == "Unknown Author":
            # Try both patterns: hashdag.medium.com and medium.com/@hashdag
            url_author_match = re.search(r"https://([^.]+)\.medium\.com", article_url)
            if url_author_match:
                author = url_author_match.group(1).replace("-", " ").title()
            else:
                url_author_match = re.search(r"/@([^/]+)", article_url)
                if url_author_match:
                    author = url_author_match.group(1).replace("-", " ").title()

        # Extract content
        content = ""
        # Try to find the main article content
        content_selectors = [
            "article",
            '[data-testid="storyContent"]',
            ".postArticle-content",
            "section",
            "main",
        ]

        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                # Get text content, preserving some structure
                paragraphs = content_element.find_all(
                    ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
                )
                if paragraphs:
                    content = "\n\n".join(
                        [
                            p.get_text().strip()
                            for p in paragraphs
                            if p.get_text().strip()
                        ]
                    )
                    break

        # Fallback: get all text if no structured content found
        if not content:
            content = soup.get_text()
            # Clean up excessive whitespace
            content = re.sub(r"\n\s*\n", "\n\n", content).strip()

        # Extract publication date
        pub_date = "Unknown"
        # Try multiple date selectors
        date_selectors = [
            "time[datetime]",
            '[data-testid="storyPublishDate"]',
            ".publication-date",
        ]

        for selector in date_selectors:
            date_element = soup.select_one(selector)
            if date_element:
                datetime_attr = date_element.get("datetime")
                if datetime_attr:
                    try:
                        parsed_date = datetime.fromisoformat(
                            datetime_attr.replace("Z", "+00:00")
                        )
                        pub_date = parsed_date.strftime("%Y-%m-%d")
                        break
                    except (ValueError, TypeError):
                        pass

                # Try parsing the text content if datetime attr doesn't work
                date_text = date_element.get_text().strip()
                if date_text:
                    try:
                        # Try common date formats
                        for fmt in ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
                            try:
                                parsed_date = datetime.strptime(date_text, fmt)
                                pub_date = parsed_date.strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                continue
                        if pub_date != "Unknown":
                            break
                    except (ValueError, TypeError):
                        pass

        article = {
            "title": title,
            "link": article_url,
            "summary": content,  # Full article content
            "author": author,
            "published": pub_date,
            "ingested_at": datetime.now().isoformat(),
            "source_type": "medium_manual",
            "rss_url": "manual_scrape",
        }

        print(f"  ✅ Successfully scraped: {title[:50]}...")
        return article

    except requests.RequestException as e:
        print(f"  ❌ Network error scraping {article_url}: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Error scraping {article_url}: {e}")
        return None


def fetch_articles_from_feed(rss_url, full_history=False):
    """Fetch articles from a single Medium RSS feed."""
    print(f"📡 Fetching from: {rss_url}")

    try:
        feed = feedparser.parse(rss_url)
        articles = []

        # Fetch all available entries from the RSS feed
        # RSS feeds are naturally limited, so we process all entries they provide
        entries_to_process = feed.entries

        if not entries_to_process:
            print(f"⚠️  No articles found in feed: {rss_url}")
            return []

        for entry in entries_to_process:
            # Extract publication date with multiple format fallbacks
            pub_date = "Unknown"
            if hasattr(entry, "published"):
                try:
                    pub_date = datetime.strptime(
                        entry.published, "%a, %d %b %Y %H:%M:%S %Z"
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    try:
                        pub_date = datetime.strptime(
                            entry.published, "%a, %d %b %Y %H:%M:%S %z"
                        ).strftime("%Y-%m-%d")
                    except ValueError:
                        pub_date = "Unknown"

            # Extract author
            author = getattr(entry, "author", "Unknown")

            article = {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary,  # Full article content from RSS
                "author": author,
                "published": pub_date,
                "ingested_at": datetime.now().isoformat(),
                "source_type": "medium_rss",
                "rss_url": rss_url,
            }

            articles.append(article)

        print(f"📄 Found {len(articles)} articles from this feed")
        return articles

    except Exception as e:
        print(f"❌ Error fetching from {rss_url}: {e}")
        return []


def save_raw_medium_data(articles, full_history=False):
    """Save raw Medium articles to sources/medium/ directory."""
    if full_history:
        date_str = "full_history"
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Create sources/medium directory
    sources_dir = Path("sources/medium")
    sources_dir.mkdir(parents=True, exist_ok=True)

    output_path = sources_dir / f"{date_str}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(articles)} raw articles to: {output_path}")
    return output_path


def main():
    """Main function to run Medium article ingestion from multiple feeds."""
    parser = argparse.ArgumentParser(
        description="Fetch articles from Medium RSS feeds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.medium_ingest                    # Daily sync (dated file)
  python -m scripts.medium_ingest --full-history     # Backfill (full_history.json)

  # Manual URL scraping (bypasses RSS limitation)
  python -m scripts.medium_ingest --manual-urls \\
    https://hashdag.medium.com/article1 \\
    https://hashdag.medium.com/article2

  # Combined: RSS feeds + manual URLs
  python -m scripts.medium_ingest --full-history \\
    --manual-urls https://hashdag.medium.com/old-article

IMPORTANT LIMITATION: Medium RSS feeds are limited to the 10 most recent articles per
author by Medium's platform design. Use --manual-urls to scrape specific older articles
that aren't available via RSS feeds.

The difference between modes is in output filename and intended usage: daily sync for
regular operations, full-history for comprehensive backfill operations.
        """,
    )
    parser.add_argument(
        "--full-history",
        action="store_true",
        help="Backfill mode - saves to 'full_history.json' (10 articles/author).",
    )
    parser.add_argument(
        "--manual-urls",
        nargs="+",
        help="Additional article URLs to scrape manually (bypasses RSS limitation).",
        metavar="URL",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force processing even if no new articles found (bypass deduplication).",
    )
    args = parser.parse_args()

    print("🔄 Starting Medium article ingestion...")

    if args.full_history:
        print("📚 Full history mode: Comprehensive backfill from RSS feeds")
    else:
        print("📰 Daily sync mode: Standard RSS feed processing")

    print("⚠️  Note: Medium RSS feeds limited to 10 most recent articles per author")

    print(f"🔗 Configured RSS feeds: {len(RSS_URLS)}")
    for i, url in enumerate(RSS_URLS, 1):
        print(f"  {i}. {url}")

    # Get existing articles for deduplication (unless force flag is used)
    existing_links = set()
    if not args.force:
        existing_links = get_existing_article_links()

    all_articles = []
    successful_feeds = 0
    successful_manual = 0

    # Process RSS feeds
    for url in RSS_URLS:
        articles = fetch_articles_from_feed(url, full_history=args.full_history)
        if articles:
            all_articles.extend(articles)
            successful_feeds += 1

    # Process manual URLs if provided
    if args.manual_urls:
        print(f"\n🔗 Manual URLs to scrape: {len(args.manual_urls)}")
        for i, url in enumerate(args.manual_urls, 1):
            print(f"  {i}. {url}")

        manual_articles = []
        successful_manual = 0

        for url in args.manual_urls:
            article = scrape_individual_article(url)
            if article:
                manual_articles.append(article)
                successful_manual += 1

        if manual_articles:
            all_articles.extend(manual_articles)
            print(
                f"✅ Successfully scraped {successful_manual}/"
                f"{len(args.manual_urls)} manual articles"
            )

    if not all_articles:
        if args.manual_urls:
            print("⚠️ No articles found from RSS feeds or manual URLs.")
        else:
            print("⚠️ No articles found across all RSS feeds.")
        return

    # Remove duplicates within this run based on the article link
    articles_by_link = {}
    for article in all_articles:
        link = article["link"]
        # Keep the article with the most recent ingestion time if duplicates exist
        if (
            link not in articles_by_link
            or article["ingested_at"] > articles_by_link[link]["ingested_at"]
        ):
            articles_by_link[link] = article

    unique_articles_this_run = list(articles_by_link.values())

    # Filter out articles that already exist in our database
    if not args.force:
        new_articles = filter_new_articles(unique_articles_this_run, existing_links)

        # Handle case when no new articles found - still save file with metadata
        if not new_articles:
            print("\n🎯 Smart deduplication result:")
            print(f"   - Articles fetched: {len(all_articles)}")
            print(f"   - Unique in this run: {len(unique_articles_this_run)}")
            print("   - New articles (not in database): 0")
            print("\n✨ No new articles found - saving empty file with metadata!")
            print("ℹ️  Use --force flag to bypass deduplication if needed.")

            # Create empty file with metadata to maintain consistency
            empty_data_with_metadata = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "generated_at": datetime.now().isoformat(),
                "source": "medium",
                "status": "no_new_content",
                "articles": [],
                "metadata": {
                    "total_feeds_checked": len(RSS_URLS),
                    "successful_feeds": successful_feeds,
                    "articles_fetched_total": len(all_articles),
                    "unique_articles_this_run": len(unique_articles_this_run),
                    "existing_articles_in_database": len(existing_links),
                    "processing_mode": (
                        "full_history" if args.full_history else "daily_sync"
                    ),
                    "deduplication_enabled": True,
                },
            }

            # Save empty file following the same pattern as save_raw_medium_data
            if args.full_history:
                date_str = "full_history"
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")

            sources_dir = Path("sources/medium")
            sources_dir.mkdir(parents=True, exist_ok=True)
            output_path = sources_dir / f"{date_str}.json"

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(empty_data_with_metadata, f, indent=2, ensure_ascii=False)

            print(f"📁 Saved empty data file to: {output_path}")
            import sys

            sys.exit(2)  # Exit code 2 indicates "no new content"

        final_articles = new_articles
    else:
        print("⚠️  Force flag used - bypassing deduplication checks")
        final_articles = unique_articles_this_run

    # Sort articles by publication date (newest first)
    final_articles.sort(
        key=lambda x: (x["published"] if x["published"] != "Unknown" else "1900-01-01"),
        reverse=True,
    )

    print("\n📊 Processing Summary:")
    print(f"   - Successful feeds: {successful_feeds}/{len(RSS_URLS)}")
    if args.manual_urls:
        print(f"   - Manual articles: {successful_manual}/{len(args.manual_urls)}")
    print(f"   - Total articles fetched: {len(all_articles)}")
    print(f"   - Unique articles this run: {len(unique_articles_this_run)}")

    if not args.force:
        existing_count = len(existing_links)
        skipped_count = len(unique_articles_this_run) - len(final_articles)
        print(f"   - Existing articles in database: {existing_count}")
        print(f"   - Duplicate articles skipped: {skipped_count}")
        print(f"   - New articles to save: {len(final_articles)}")
    else:
        print(f"   - Articles to save (force mode): {len(final_articles)}")

    if len(all_articles) > len(unique_articles_this_run):
        duplicates_removed = len(all_articles) - len(unique_articles_this_run)
        print(f"   - Within-run duplicates removed: {duplicates_removed}")

    # Display article titles (limit to first 10 for readability)
    display_limit = min(10, len(final_articles))
    print(
        f"\n📄 New articles to save (showing {display_limit} of {len(final_articles)}):"
    )
    for i, article in enumerate(final_articles[:display_limit], 1):
        author = (
            article["author"] if article["author"] != "Unknown" else "Unknown Author"
        )
        print(f"  {i}. {article['title']} - {author}")

    if len(final_articles) > display_limit:
        print(f"  ... and {len(final_articles) - display_limit} more articles")

    # Save the articles
    output_path = save_raw_medium_data(final_articles, full_history=args.full_history)

    print("\n🎉 Medium ingestion complete!")
    print(f"📁 Raw data saved to: {output_path}")

    if args.full_history:
        print(
            "ℹ️  Full history backfill completed. "
            "Future daily runs will capture new articles."
        )
    else:
        print(
            "ℹ️  Daily sync completed. "
            "LLM processing will happen during aggregation step."
        )


if __name__ == "__main__":
    main()
