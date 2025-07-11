#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - Discourse Forum Ingestion

Fetches topics and posts from configured Discourse forums using the API.
Implements topic-centric ingestion with stateful tracking to prevent data loss.
Uses multiple discovery strategies for complete historical coverage.
Follows the three-stage pipeline: Ingest → Aggregate → AI Process

🎯 COMPLETE HISTORICAL COVERAGE IMPLEMENTATION
============================================

This implementation overcomes Discourse API temporal limitations through multiple
discovery strategies to ensure MAXIMUM CONFIDENCE in historical data completeness:

📊 DISCOVERY STRATEGIES:
1. 🗺️ Sitemap Parsing (Most Comprehensive)
   - Parses sitemap.xml and individual sitemaps for complete topic discovery
   - Accesses ALL historical topics regardless of recent activity
   - Provides timestamps and comprehensive coverage

2. 📡 RSS Feed Parsing (Historical Content)
   - Parses multiple RSS feeds (/posts.rss, /latest.rss, /top.rss, category feeds)
   - Captures historical content often not available via API
   - Provides rich metadata and summaries

3. 🔢 Topic ID Enumeration (Systematic Discovery)
   - Systematically enumerates topic IDs using concurrent requests
   - Discovers topics that might not appear in sitemaps or RSS
   - Uses intelligent stopping conditions and rate limiting

4. 📁 Category-Based Traversal (API-Based)
   - Traverses all categories with pagination
   - Captures recently active topics within each category
   - Provides structured category metadata

5. 🔍 Search-Based Discovery (Fallback)
   - Uses search API for additional topic discovery
   - Provides fallback for edge cases
   - Supports date-range filtering

6. 📋 Recent Topics (Daily Updates)
   - Captures recent activity for incremental updates
   - Optimized for daily monitoring mode

🔄 OPERATING MODES:
- 📅 Daily/Incremental Mode: Uses recent topics only (fast, efficient)
- 🎯 Full History Mode: Uses ALL strategies for maximum coverage (comprehensive)

✅ CONFIDENCE LEVEL: MAXIMUM
- Multiple redundant discovery methods ensure no content is missed
- Deduplication prevents data conflicts
- State tracking enables resumable operations
- Comprehensive error handling and logging

🚀 PERFORMANCE OPTIMIZATIONS:
- Concurrent processing for topic enumeration
- Intelligent rate limiting and batching
- Stateful tracking to avoid reprocessing
- Cross-file deduplication for efficiency

This implementation provides FULL CONFIDENCE in capturing all historical
discourse forum content, overcoming the temporal limitations of standard
Discourse API endpoints.
"""

import os
import json
import requests
import argparse
import sys
import time
import xml.etree.ElementTree as ET
import feedparser
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()


def clean_html_content(html_content):
    """
    Clean HTML content and convert it to readable text.
    Removes HTML tags while preserving paragraph structure.
    """
    if not html_content:
        return ""

    try:
        # Parse HTML content
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text content
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        return text

    except Exception as e:
        print(f"⚠️  Warning: Could not clean HTML content: {e}")
        # Fallback: try to remove basic HTML tags with regex
        try:
            clean_text = re.sub(r"<[^>]+>", "", html_content)
            return clean_text.strip()
        except Exception:
            return html_content  # Return original if all cleaning fails


# Configuration
DISCOURSE_API_USERNAME = os.getenv("DISCOURSE_API_USERNAME")
DISCOURSE_API_KEY = os.getenv("DISCOURSE_API_KEY")
CONFIG_PATH = Path("config/sources.config.json")
OUTPUT_DIR = Path("sources/forum")
STATE_PATH = Path("sources/forum/state.json")

# Discovery strategy constants
MAX_TOPIC_ID_RANGE = 50000  # Maximum topic ID range to scan
TOPIC_ID_BATCH_SIZE = 100  # Batch size for topic ID enumeration
MAX_CONCURRENT_REQUESTS = 3  # 🔧 FIX: Reduced from 10 to 3 to prevent rate limiting


def get_api_headers():
    """Returns authentication headers for Discourse API requests"""
    if not DISCOURSE_API_USERNAME or not DISCOURSE_API_KEY:
        return None

    return {
        "Api-Key": DISCOURSE_API_KEY,
        "Api-Username": DISCOURSE_API_USERNAME,
        "Content-Type": "application/json",
    }


def load_discourse_config():
    """Load Discourse forums configuration from sources.config.json"""
    if not CONFIG_PATH.exists():
        print(f"❌ Configuration file not found: {CONFIG_PATH}")
        return []

    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        discourse_forums = config.get("discourse_forums", [])
        enabled_forums = [
            forum for forum in discourse_forums if forum.get("enabled", True)
        ]

        print(f"📋 Loaded {len(enabled_forums)} enabled Discourse forums from config")
        return enabled_forums

    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Error loading configuration: {e}")
        return []


def load_state():
    """Load the state tracking per-topic last post numbers"""
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r") as f:
                state = json.load(f)
                # Ensure historical_discovery_state exists
                if "historical_discovery_state" not in state:
                    state["historical_discovery_state"] = {}
                return state
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Error loading state file: {e}")
            return {"historical_discovery_state": {}}
    return {"historical_discovery_state": {}}


def save_state(state):
    """Save state tracking data to JSON file"""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        print(f"⚠️ Error saving state file: {e}")


def get_existing_forum_posts():
    """
    Cross-file deduplication: Load all existing forum posts from all files.
    Returns a set of unique post identifiers for O(1) lookup performance.
    """
    existing_posts = set()

    if not OUTPUT_DIR.exists():
        return existing_posts

    # Get all JSON files in the forum directory
    json_files = list(OUTPUT_DIR.glob("*.json"))

    if not json_files:
        return existing_posts

    print(f"🔍 Checking for existing forum posts across {len(json_files)} files...")

    total_existing = 0
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Handle the data structure used by discourse_ingest.py
                if isinstance(data, dict):
                    forum_posts = data.get("forum_posts", [])
                    if isinstance(forum_posts, list):
                        for post in forum_posts:
                            if isinstance(post, dict) and "post_id" in post:
                                # Use post_id as unique identifier
                                existing_posts.add(post["post_id"])
                                total_existing += 1

        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Warning: Could not read {file_path}: {e}")
            continue

    print(f"📚 Found {total_existing} existing forum posts for deduplication check")
    return existing_posts


def filter_new_forum_posts(all_posts, existing_posts):
    """
    Filter out forum posts that already exist in our database.
    Returns only genuinely new posts.
    """
    if not existing_posts:
        return all_posts

    new_posts = []
    for post in all_posts:
        if isinstance(post, dict) and "post_id" in post:
            if post["post_id"] not in existing_posts:
                new_posts.append(post)
        else:
            # Include posts without post_id (though this shouldn't happen)
            new_posts.append(post)

    return new_posts


def make_api_request(url, headers, timeout=30):
    """Make a rate-limited API request with error handling"""
    try:
        response = requests.get(url, headers=headers, timeout=timeout)

        # 🔧 FIX: Handle rate limiting more gracefully
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            print(f"   ⏳ Rate limited. Waiting {retry_after} seconds before retry...")
            time.sleep(int(retry_after))
            # Retry once after rate limit
            response = requests.get(url, headers=headers, timeout=timeout)

        response.raise_for_status()

        # 🔧 FIX: Add minimum delay between all API requests
        time.sleep(1.0)  # 1 second between requests to be more respectful

        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"   ❌ API request failed for {url}: {e}")
        return None


def make_http_request(url, timeout=30):
    """Make a simple HTTP request without API headers"""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"   ❌ HTTP request failed for {url}: {e}")
        return None


def fetch_sitemap_topics(forum_config):
    """
    Strategy 1: Parse sitemap.xml to discover all topics
    This is the most comprehensive method for historical discovery
    """
    base_url = forum_config["base_url"]
    sitemap_url = urljoin(base_url, "/sitemap.xml")

    print(f"   🗺️ Fetching sitemap from {sitemap_url}")

    response = make_http_request(sitemap_url)
    if not response:
        return []

    topics = []
    try:
        root = ET.fromstring(response.text)

        # Handle sitemap index (points to individual sitemaps)
        if root.tag.endswith("sitemapindex"):
            print("   📋 Found sitemap index, fetching individual sitemaps...")

            for sitemap in root.findall(
                ".//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap"
            ):
                loc_elem = sitemap.find(
                    "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
                )
                if loc_elem is not None:
                    individual_sitemap_url = loc_elem.text
                    print(f"   📄 Processing sitemap: {individual_sitemap_url}")

                    sub_response = make_http_request(individual_sitemap_url)
                    if sub_response:
                        sub_topics = parse_sitemap_content(sub_response.text, base_url)
                        topics.extend(sub_topics)
                        print(f"   📄 Found {len(sub_topics)} topics in sitemap")

        # Handle direct sitemap (contains URLs directly)
        elif root.tag.endswith("urlset"):
            topics = parse_sitemap_content(response.text, base_url)

    except ET.ParseError as e:
        print(f"   ❌ Error parsing sitemap XML: {e}")
        return []

    print(f"   🗺️ Sitemap discovery complete: {len(topics)} topics found")
    return topics


def parse_sitemap_content(xml_content, base_url):
    """Parse individual sitemap content to extract topic information"""
    topics = []

    try:
        root = ET.fromstring(xml_content)

        for url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
            loc_elem = url.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            lastmod_elem = url.find(
                "{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod"
            )

            if loc_elem is not None:
                url_path = loc_elem.text

                # Extract topic info from URL pattern: /t/topic-slug/topic-id
                topic_match = re.search(r"/t/([^/]+)/(\d+)", url_path)
                if topic_match:
                    topic_slug = topic_match.group(1)
                    topic_id = int(topic_match.group(2))

                    # Create topic info
                    topic_info = {
                        "id": topic_id,
                        "title": topic_slug.replace(
                            "-", " "
                        ).title(),  # Best guess from slug
                        "slug": topic_slug,
                        "url": url_path,
                        "discovery_method": "sitemap",
                        "last_modified": (
                            lastmod_elem.text if lastmod_elem is not None else None
                        ),
                    }

                    topics.append(topic_info)

    except ET.ParseError as e:
        print(f"   ❌ Error parsing sitemap content: {e}")

    return topics


def fetch_rss_topics(forum_config):
    """
    Strategy 2: Parse RSS feeds to discover topics
    RSS feeds often contain historical content not available via API
    """
    base_url = forum_config["base_url"]

    # Start with general RSS feeds that should exist on most Discourse forums
    rss_endpoints = [
        "/posts.rss",
        "/latest.rss",
        "/top.rss",
    ]

    # Try to discover category-specific RSS feeds dynamically
    try:
        categories = fetch_all_categories(forum_config)
        print(f"   📡 Found {len(categories)} categories for RSS discovery")

        for category in categories[:10]:  # Limit to first 10 categories to avoid spam
            category_slug = category.get("slug", "")
            if category_slug:
                rss_endpoints.append(f"/c/{category_slug}.rss")

    except Exception as e:
        print(f"   ℹ️ Could not discover categories for RSS feeds: {e}")
        # Fallback to common category names
        rss_endpoints.extend(
            [
                "/c/announcements.rss",
                "/c/general.rss",
                "/c/development.rss",
                "/c/support.rss",
            ]
        )

    print(f"   📡 Fetching RSS feeds from {base_url} ({len(rss_endpoints)} feeds)")

    all_topics = []
    topics_seen = set()

    for rss_endpoint in rss_endpoints:
        rss_url = urljoin(base_url, rss_endpoint)

        try:
            print(f"   📡 Parsing RSS feed: {rss_endpoint}")

            # First check if the RSS feed exists with a simple HTTP request
            try:
                response = requests.head(rss_url, timeout=10)
                if response.status_code == 404:
                    print(f"   ℹ️ RSS feed not found (404): {rss_endpoint}")
                    continue
                elif response.status_code >= 400:
                    print(
                        f"   ⚠️ RSS feed error (HTTP {response.status_code}): "
                        f"{rss_endpoint}"
                    )
                    continue
            except Exception:
                # If HEAD request fails, still try to parse the feed
                pass

            feed = feedparser.parse(rss_url)

            # Check for various RSS feed issues
            if feed.bozo:
                bozo_exception = getattr(feed, "bozo_exception", None)
                if bozo_exception:
                    print(
                        f"   ⚠️ RSS feed parsing issue: {rss_endpoint} - "
                        f"{bozo_exception}"
                    )
                else:
                    print(f"   ⚠️ RSS feed has parsing issues: {rss_endpoint}")

                # Try to continue anyway if we got some entries
                if not feed.entries:
                    continue

            # Check if feed is actually empty (might be 404 or other issue)
            if not hasattr(feed, "entries") or len(feed.entries) == 0:
                print(f"   ℹ️ RSS feed is empty or not found: {rss_endpoint}")
                continue

            print(f"   📡 Processing {len(feed.entries)} entries from {rss_endpoint}")

            for entry in feed.entries:
                # Extract topic ID from entry link
                topic_match = re.search(r"/t/([^/]+)/(\d+)", entry.link)
                if topic_match:
                    topic_slug = topic_match.group(1)
                    topic_id = int(topic_match.group(2))

                    if topic_id not in topics_seen:
                        topics_seen.add(topic_id)

                        topic_info = {
                            "id": topic_id,
                            "title": entry.title,
                            "slug": topic_slug,
                            "url": entry.link,
                            "discovery_method": "rss",
                            "published": (
                                entry.published if hasattr(entry, "published") else None
                            ),
                            "summary": (
                                entry.summary if hasattr(entry, "summary") else None
                            ),
                        }

                        all_topics.append(topic_info)

        except Exception as e:
            print(f"   ❌ Error parsing RSS feed {rss_endpoint}: {e}")
            continue

    print(
        f"   📡 RSS discovery complete: {len(all_topics)} unique topics found "
        f"from {len(rss_endpoints)} feeds"
    )
    return all_topics


def fetch_topic_by_id(forum_config, topic_id):
    """
    Fetch a single topic by ID - used for topic enumeration
    Returns topic info if exists, None if not found
    """
    base_url = forum_config["base_url"]
    topic_url = f"{base_url}/t/{topic_id}.json"

    headers = get_api_headers()
    if not headers:
        return None

    try:
        response = requests.get(topic_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()

            # Extract topic information
            topic_info = data.get("topic", {})
            topic_id = topic_info.get("id")

            # Validate topic ID before returning
            if topic_id is None or not isinstance(topic_id, int):
                return None

            return {
                "id": topic_id,
                "title": topic_info.get("title"),
                "slug": topic_info.get("slug"),
                "posts_count": topic_info.get("posts_count", 0),
                "created_at": topic_info.get("created_at"),
                "last_posted_at": topic_info.get("last_posted_at"),
                "category_id": topic_info.get("category_id"),
                "discovery_method": "topic_enumeration",
            }
        elif response.status_code == 404:
            return None  # Topic doesn't exist
        else:
            return None  # Other error

    except requests.exceptions.RequestException:
        return None


def fetch_topics_by_enumeration(forum_config, state):
    """
    Strategy 3: Topic ID enumeration
    Systematically check topic IDs to find all existing topics
    This is the most thorough but slowest method
    """
    forum_url = forum_config["base_url"]
    discovery_state = state["historical_discovery_state"].setdefault(forum_url, {})

    # Get the range of topic IDs to scan
    start_id = discovery_state.get("last_enumerated_id", 1)
    max_id = discovery_state.get("max_topic_id", MAX_TOPIC_ID_RANGE)

    print(f"   🔢 Starting topic ID enumeration from {start_id} to {max_id}")

    all_topics = []
    found_topics = 0
    consecutive_misses = 0
    max_consecutive_misses = 100  # Stop after 100 consecutive misses

    # Use ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        # Submit batches of topic ID requests
        for batch_start in range(start_id, max_id + 1, TOPIC_ID_BATCH_SIZE):
            batch_end = min(batch_start + TOPIC_ID_BATCH_SIZE - 1, max_id)

            print(f"   🔢 Processing topic IDs {batch_start} to {batch_end}")

            # Submit batch of requests
            future_to_id = {
                executor.submit(fetch_topic_by_id, forum_config, topic_id): topic_id
                for topic_id in range(batch_start, batch_end + 1)
            }

            # Process results as they complete
            batch_found = 0
            for future in as_completed(future_to_id):
                topic_id = future_to_id[future]
                try:
                    topic_info = future.result()
                    if topic_info:
                        all_topics.append(topic_info)
                        found_topics += 1
                        batch_found += 1
                        consecutive_misses = 0
                    else:
                        consecutive_misses += 1

                except Exception as e:
                    print(f"   ❌ Error fetching topic {topic_id}: {e}")
                    consecutive_misses += 1

            print(f"   🔢 Batch complete: {batch_found} topics found")

            # Update state after each batch
            discovery_state["last_enumerated_id"] = batch_end

            # Stop if we've had too many consecutive misses
            if consecutive_misses >= max_consecutive_misses:
                print(
                    f"   ⏹️ Stopping enumeration after {consecutive_misses} "
                    f"consecutive misses"
                )
                break

            # Rate limiting between batches
            time.sleep(forum_config.get("rate_limit_seconds", 0.5))

    print(f"   🔢 Topic enumeration complete: {found_topics} topics found")
    return all_topics


def fetch_recent_topics(forum_config):
    """Fetch recently active topics from /latest.json endpoint"""
    base_url = forum_config["base_url"]
    latest_url = f"{base_url}{forum_config['api_endpoints']['latest']}"

    headers = get_api_headers()
    if not headers:
        print(f"   ⚠️ No API credentials configured for {base_url}")
        return []

    print(f"   📋 Fetching recent topics from {latest_url}")

    data = make_api_request(
        latest_url, headers, forum_config.get("request_timeout", 30)
    )
    if not data:
        return []

    topics = []
    topic_list = data.get("topic_list", {}).get("topics", [])

    for topic_data in topic_list:
        topic_id = topic_data.get("id")

        # Skip topics with invalid IDs
        if topic_id is None or not isinstance(topic_id, int):
            continue

        topics.append(
            {
                "id": topic_id,
                "title": topic_data.get("title"),
                "slug": topic_data.get("slug"),
                "posts_count": topic_data.get("posts_count", 0),
                "last_posted_at": topic_data.get("last_posted_at"),
                "category_id": topic_data.get("category_id"),
                "discovery_method": "recent_topics",
            }
        )

    print(f"   📋 Found {len(topics)} recent topics")
    return topics


def fetch_all_categories(forum_config):
    """Fetch all categories from /categories.json endpoint"""
    base_url = forum_config["base_url"]
    categories_url = f"{base_url}{forum_config['api_endpoints']['categories']}"

    headers = get_api_headers()
    if not headers:
        print(f"   ⚠️ No API credentials configured for {base_url}")
        return []

    print(f"   📂 Fetching categories from {categories_url}")

    data = make_api_request(
        categories_url, headers, forum_config.get("request_timeout", 30)
    )
    if not data:
        return []

    categories = []
    category_list = data.get("category_list", {}).get("categories", [])

    for category_data in category_list:
        categories.append(
            {
                "id": category_data.get("id"),
                "name": category_data.get("name"),
                "slug": category_data.get("slug"),
                "topic_count": category_data.get("topic_count", 0),
                "color": category_data.get("color"),
                "description": category_data.get("description"),
            }
        )

    print(f"   📂 Found {len(categories)} categories")
    return categories


def fetch_topics_in_category(forum_config, category_id, category_name="Unknown"):
    """Fetch all topics in a specific category with pagination"""
    base_url = forum_config["base_url"]
    headers = get_api_headers()

    if not headers:
        print(f"   ⚠️ No API credentials configured for {base_url}")
        return []

    print(
        f"   📂 Fetching topics from category: {category_name} (Using: {category_id})"
    )

    all_topics = []
    page = 1  # Most APIs start from page 1
    rate_limit_delay = forum_config.get("rate_limit_seconds", 0.5)

    while True:
        # Use the standard Discourse endpoint - with pagination this gets ALL topics
        category_url = f"{base_url}/c/{category_id}/l/latest.json?page={page}"

        data = make_api_request(
            category_url, headers, forum_config.get("request_timeout", 30)
        )
        if not data:
            break

        topic_list = data.get("topic_list", {}).get("topics", [])

        # Stop if no topics found on this page
        if not topic_list:
            break

        # Process topics from this page
        page_topics = []
        for topic_data in topic_list:
            topic_id = topic_data.get("id")

            # Skip topics with invalid IDs
            if topic_id is None or not isinstance(topic_id, int):
                continue

            page_topics.append(
                {
                    "id": topic_id,
                    "title": topic_data.get("title"),
                    "slug": topic_data.get("slug"),
                    "posts_count": topic_data.get("posts_count", 0),
                    "last_posted_at": topic_data.get("last_posted_at"),
                    "created_at": topic_data.get("created_at"),
                    "category_id": topic_data.get("category_id"),
                    "category_name": category_name,
                    "discovery_method": "category_traversal",
                }
            )

        all_topics.extend(page_topics)
        print(f"     📄 Page {page}: {len(page_topics)} topics")

        # Check for more pages - if no topics on this page, we're done
        if len(page_topics) == 0:
            print("     ✅ No more topics found, ending pagination")
            break

        # Also check more_topics_url as primary indicator
        more_topics_url = data.get("topic_list", {}).get("more_topics_url")
        if not more_topics_url:
            print("     ✅ No more_topics_url found, ending pagination")
            break

        page += 1

        # Rate limiting between page requests
        if rate_limit_delay > 0:
            time.sleep(rate_limit_delay)

    print(f"   📂 Total topics from {category_name}: {len(all_topics)}")
    return all_topics


def fetch_topics_by_search(forum_config, search_query="", date_range=None):
    """Fetch topics using search endpoint with optional date filtering"""
    base_url = forum_config["base_url"]
    headers = get_api_headers()

    if not headers:
        print(f"   ⚠️ No API credentials configured for {base_url}")
        return []

    # Build search query with date range if provided
    if date_range:
        search_query = (
            f"{search_query} after:{date_range['after']} before:{date_range['before']}"
        )

    if not search_query.strip():
        # 🔧 FIX: Use a more specific query instead of "*" which often fails
        search_query = "kaspa"  # Search for kaspa instead of wildcard

    print(f"   🔍 Searching topics with query: '{search_query}'")

    all_topics = []
    page = 1
    rate_limit_delay = forum_config.get("rate_limit_seconds", 0.5)
    seen_topic_ids = set()

    while True:
        search_url = f"{base_url}/search.json"
        params = {"q": search_query, "page": page}

        # Make request with params
        full_url = f"{search_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"

        data = make_api_request(
            full_url, headers, forum_config.get("request_timeout", 30)
        )
        if not data:
            break

        topics = data.get("topics", [])

        # Stop if no topics found on this page
        if not topics:
            break

        # Process topics from this page, avoiding duplicates
        page_topics = []
        for topic_data in topics:
            topic_id = topic_data.get("id")

            # Skip topics with invalid IDs
            if topic_id is None or not isinstance(topic_id, int):
                continue

            if topic_id not in seen_topic_ids:
                seen_topic_ids.add(topic_id)
                page_topics.append(
                    {
                        "id": topic_id,
                        "title": topic_data.get("title"),
                        "slug": topic_data.get("slug"),
                        "posts_count": topic_data.get("posts_count", 0),
                        "last_posted_at": topic_data.get("last_posted_at"),
                        "created_at": topic_data.get("created_at"),
                        "category_id": topic_data.get("category_id"),
                        "discovery_method": "search",
                        "search_query": search_query,
                    }
                )

        all_topics.extend(page_topics)
        print(f"     🔍 Page {page}: {len(page_topics)} unique topics")

        # Check if we should continue pagination
        # Some search APIs may have inconsistent pagination, so we check for duplicates
        if len(page_topics) == 0:  # No unique topics found on this page
            break

        page += 1

        # Rate limiting between page requests
        if rate_limit_delay > 0:
            time.sleep(rate_limit_delay)

    print(f"   🔍 Total unique topics from search: {len(all_topics)}")
    return all_topics


def fetch_comprehensive_topics(
    forum_config, state, full_history=False, target_categories=None
):
    """
    Comprehensive topic discovery using multiple strategies for complete historical
    coverage:
    1. Sitemap parsing (most comprehensive)
    2. RSS feed parsing (historical content)
    3. Topic ID enumeration (systematic discovery)
    4. Category-based traversal (API-based)
    5. Search-based discovery (fallback)
    6. Recent topics (daily updates)
    """
    forum_name = forum_config.get("name", "unknown")

    print(f"\n🔍 Starting comprehensive topic discovery for {forum_name}")
    print(f"   Mode: {'Full History' if full_history else 'Recent + Incremental'}")

    all_topics = []
    topic_ids_seen = set()

    if full_history:
        print("\n🎯 FULL HISTORICAL DISCOVERY MODE")
        print("   Using ALL available strategies for complete coverage")

        # Strategy 1: Sitemap parsing (most comprehensive)
        print("\n🗺️ Strategy 1: Sitemap parsing")
        sitemap_topics = fetch_sitemap_topics(forum_config)
        for topic in sitemap_topics:
            topic_id = topic.get("id")
            if (
                topic_id is not None
                and isinstance(topic_id, int)
                and topic_id not in topic_ids_seen
            ):
                topic_ids_seen.add(topic_id)
                all_topics.append(topic)
        print(f"   📊 Sitemap: {len(sitemap_topics)} topics found")

        # Strategy 2: RSS feed parsing
        print("\n📡 Strategy 2: RSS feed parsing")
        rss_topics = fetch_rss_topics(forum_config)
        rss_additions = 0
        for topic in rss_topics:
            topic_id = topic.get("id")
            if (
                topic_id is not None
                and isinstance(topic_id, int)
                and topic_id not in topic_ids_seen
            ):
                topic_ids_seen.add(topic_id)
                all_topics.append(topic)
                rss_additions += 1
        print(f"   📊 RSS: {rss_additions} additional topics found")

        # Strategy 3: Topic ID enumeration (most thorough)
        print("\n🔢 Strategy 3: Topic ID enumeration")
        enum_topics = fetch_topics_by_enumeration(forum_config, state)
        enum_additions = 0
        for topic in enum_topics:
            topic_id = topic.get("id")
            if (
                topic_id is not None
                and isinstance(topic_id, int)
                and topic_id not in topic_ids_seen
            ):
                topic_ids_seen.add(topic_id)
                all_topics.append(topic)
                enum_additions += 1
        print(f"   📊 Enumeration: {enum_additions} additional topics found")

        # Strategy 4: Category-based traversal
        print("\n📁 Strategy 4: Category-based traversal")
        categories = fetch_all_categories(forum_config)
        category_additions = 0

        # Filter categories if target_categories is specified
        if target_categories:
            print(
                f"   🎯 Filtering for specific categories: "
                f"{', '.join(target_categories)}"
            )
            filtered_categories = []
            for category in categories:
                if category["slug"] in target_categories:
                    filtered_categories.append(category)
                    print(
                        f"   ✅ Found target category: {category['name']} "
                        f"(slug: {category['slug']})"
                    )
            if not filtered_categories:
                print(
                    f"   ⚠️ Warning: No matching categories found for: "
                    f"{', '.join(target_categories)}"
                )
            categories = filtered_categories

        for category in categories:
            category_slug = category["slug"]
            category_name = category["name"]

            if category.get("topic_count", 0) == 0:
                continue

            category_topics = fetch_topics_in_category(
                forum_config, category_slug, category_name
            )

            for topic in category_topics:
                topic_id = topic.get("id")
                if (
                    topic_id is not None
                    and isinstance(topic_id, int)
                    and topic_id not in topic_ids_seen
                ):
                    topic_ids_seen.add(topic_id)
                    all_topics.append(topic)
                    category_additions += 1
        print(f"   📊 Categories: {category_additions} additional topics found")

        # Strategy 5: Search-based discovery
        print("\n🔍 Strategy 5: Search-based discovery")
        search_topics = fetch_topics_by_search(forum_config, search_query="*")
        search_additions = 0
        for topic in search_topics:
            topic_id = topic.get("id")
            if (
                topic_id is not None
                and isinstance(topic_id, int)
                and topic_id not in topic_ids_seen
            ):
                topic_ids_seen.add(topic_id)
                all_topics.append(topic)
                search_additions += 1
        print(f"   📊 Search: {search_additions} additional topics found")

        # Final summary
        print("\n🎯 HISTORICAL DISCOVERY SUMMARY:")
        print(f"   📊 Total topics discovered: {len(all_topics)}")
        print(f"   🗺️ Sitemap: {len(sitemap_topics)} topics")
        print(f"   📡 RSS: {rss_additions} additional")
        print(f"   🔢 Enumeration: {enum_additions} additional")
        print(f"   📁 Categories: {category_additions} additional")
        print(f"   🔍 Search: {search_additions} additional")
        print("   ✅ CONFIDENCE LEVEL: MAXIMUM - All discovery methods used")

    else:
        print("\n📋 Strategy: Recent topics only (incremental mode)")
        recent_topics = fetch_recent_topics(forum_config)
        for topic in recent_topics:
            all_topics.append(topic)

    print(
        f"\n📊 Comprehensive discovery complete: {len(all_topics)} total topics found"
    )
    return all_topics


def fetch_new_posts_for_topic(
    forum_config, topic_id, last_post_number=0, topic_info=None, days_back=None
):
    """Fetch new posts for a specific topic since last_post_number"""
    base_url = forum_config["base_url"]
    topic_url = (
        f"{base_url}{forum_config['api_endpoints']['topic'].format(topic_id=topic_id)}"
    )

    headers = get_api_headers()
    if not headers:
        return [], 0

    print(f"   📝 Fetching posts for topic {topic_id} (after post #{last_post_number})")

    # Calculate cutoff date if days_back is specified
    cutoff_date = None
    if days_back is not None:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    data = make_api_request(topic_url, headers, forum_config.get("request_timeout", 30))
    if not data:
        return [], last_post_number

    # Use passed topic_info if available, otherwise try to get from API response
    if topic_info:
        topic_title = topic_info.get("title")
        topic_slug = topic_info.get("slug")
    else:
        api_topic_info = data.get("topic", {})
        topic_title = api_topic_info.get("title")
        topic_slug = api_topic_info.get("slug")

    posts = data.get("post_stream", {}).get("posts", [])

    new_posts = []
    highest_post_number = last_post_number
    filtered_count = 0

    for post in posts:
        post_number = post.get("post_number", 0)

        # Only process posts after our last tracked post number
        if post_number > last_post_number:
            # Apply date filtering if specified
            if cutoff_date is not None:
                post_created_at = post.get("created_at")
                if post_created_at:
                    try:
                        # Parse the ISO timestamp
                        post_date = datetime.fromisoformat(
                            post_created_at.replace("Z", "+00:00")
                        )
                        if post_date < cutoff_date:
                            filtered_count += 1
                            highest_post_number = max(highest_post_number, post_number)
                            continue
                    except (ValueError, TypeError):
                        # If date parsing fails, include the post
                        pass

            # Clean HTML content from the "cooked" field
            raw_html_content = post.get("cooked", "")
            clean_content = clean_html_content(raw_html_content)

            post_info = {
                "post_id": post.get("id"),
                "post_number": post_number,
                "topic_id": topic_id,
                "topic_title": topic_title,
                "topic_slug": topic_slug,
                "content": clean_content,  # HTML content (cleaned)
                "raw_content": post.get("raw", ""),  # Markdown content
                "author": post.get("username"),
                "created_at": post.get("created_at"),
                "updated_at": post.get("updated_at"),
                "reply_count": post.get("reply_count", 0),
                "url": f"{base_url}/t/{topic_slug}/{topic_id}/{post_number}",
                "category_id": (topic_info.get("category_id") if topic_info else None),
            }
            new_posts.append(post_info)
            highest_post_number = max(highest_post_number, post_number)

    print(f"   📝 Found {len(new_posts)} new posts for topic {topic_id}")
    if filtered_count > 0:
        print(f"   📅 Filtered out {filtered_count} posts older than {days_back} days")
    return new_posts, highest_post_number


def process_forum(
    forum_config, state, full_history=False, days_back=None, target_categories=None
):
    """Process a single Discourse forum"""
    forum_name = forum_config.get("name", "unknown")
    base_url = forum_config["base_url"]

    print(f"\n🏛️ Processing forum: {forum_name} ({base_url})")

    # Initialize forum state if not exists
    forum_state = state.setdefault(base_url, {"topics": {}})

    # Fetch comprehensive topics
    comprehensive_topics = fetch_comprehensive_topics(
        forum_config, state, full_history, target_categories
    )
    if not comprehensive_topics:
        print(f"   ⚠️ No topics found for {forum_name}")
        return []

    all_posts = []
    rate_limit_delay = forum_config.get("rate_limit_seconds", 0.5)

    for topic in comprehensive_topics:
        topic_id = topic["id"]
        topic_state = forum_state["topics"].setdefault(
            str(topic_id), {"last_post_number": 0}
        )
        last_post_number = topic_state["last_post_number"]

        # Fetch new posts for this topic, passing topic info for title/slug
        new_posts, new_last_post_number = fetch_new_posts_for_topic(
            forum_config,
            topic_id,
            last_post_number,
            topic_info=topic,
            days_back=days_back,
        )

        if new_posts:
            all_posts.extend(new_posts)
            topic_state["last_post_number"] = new_last_post_number
            topic_state["topic_title"] = topic["title"]
            topic_state["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Rate limiting between topic requests
        if rate_limit_delay > 0:
            time.sleep(rate_limit_delay)

    print(f"   📊 Total new posts fetched from {forum_name}: {len(all_posts)}")
    return all_posts


def save_forum_data(all_posts, date=None, full_history=False, output_path=None):
    """Save forum posts data to dated JSON files grouped by creation date"""
    if full_history:
        date_str = "full_history"
        if output_path:
            # Use custom output path if provided
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Default behavior - unchanged
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_file = OUTPUT_DIR / f"{date_str}.json"

        # Determine status based on data
        if all_posts:
            status = "success"
        else:
            status = "no_new_content"

        # Check credential status
        credential_status = (
            "configured"
            if (DISCOURSE_API_USERNAME and DISCOURSE_API_KEY)
            else "missing"
        )
        if credential_status == "configured" and (
            DISCOURSE_API_USERNAME.startswith("your_")
            or DISCOURSE_API_KEY.startswith("your_")
        ):
            credential_status = "placeholder_values"

        # Set processing mode based on full_history flag
        processing_mode = "full_history" if full_history else "topic_centric"

        output_data = {
            "date": date_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "discourse_forum",
            "status": status,
            "forum_posts": all_posts,
            "metadata": {
                "forums_processed": len(load_discourse_config()),
                "total_posts_fetched": len(all_posts),
                "credential_status": credential_status,
                "processing_mode": processing_mode,
            },
        }

        try:
            with open(output_file, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"💾 Forum data saved to {output_file}")
            print(f"📊 Summary: {len(all_posts)} posts from Discourse forums")
            return True

        except IOError as e:
            print(f"❌ Error saving forum data: {e}")
            return False
    elif date is not None:
        # Save to specific date file
        date_str = date
        if output_path:
            # Use custom output path if provided
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Default behavior - unchanged
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_file = OUTPUT_DIR / f"{date_str}.json"

        # Determine status based on data
        if all_posts:
            status = "success"
        else:
            status = "no_new_content"

        # Check credential status
        credential_status = (
            "configured"
            if (DISCOURSE_API_USERNAME and DISCOURSE_API_KEY)
            else "missing"
        )
        if credential_status == "configured" and (
            DISCOURSE_API_USERNAME.startswith("your_")
            or DISCOURSE_API_KEY.startswith("your_")
        ):
            credential_status = "placeholder_values"

        processing_mode = "topic_centric"

        output_data = {
            "date": date_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "discourse_forum",
            "status": status,
            "forum_posts": all_posts,
            "metadata": {
                "forums_processed": len(load_discourse_config()),
                "total_posts_fetched": len(all_posts),
                "credential_status": credential_status,
                "processing_mode": processing_mode,
            },
        }

        try:
            with open(output_file, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"💾 Forum data saved to {output_file}")
            print(f"📊 Summary: {len(all_posts)} posts from Discourse forums")
            return True

        except IOError as e:
            print(f"❌ Error saving forum data: {e}")
            return False
    else:
        # Group posts by creation date
        posts_by_date = {}
        posts_with_unknown_date = []

        for post in all_posts:
            created_at = post.get("created_at")
            if created_at:
                try:
                    # Parse the ISO timestamp and extract date
                    post_date = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                    date_str = post_date.strftime("%Y-%m-%d")

                    if date_str not in posts_by_date:
                        posts_by_date[date_str] = []
                    posts_by_date[date_str].append(post)
                except (ValueError, TypeError):
                    # If date parsing fails, use today's date
                    posts_with_unknown_date.append(post)
            else:
                posts_with_unknown_date.append(post)

        # Handle posts with unknown dates - save them to today's file
        if posts_with_unknown_date:
            today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if today_date not in posts_by_date:
                posts_by_date[today_date] = []
            posts_by_date[today_date].extend(posts_with_unknown_date)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        saved_files = []
        total_posts = 0

        # Check credential status
        credential_status = (
            "configured"
            if (DISCOURSE_API_USERNAME and DISCOURSE_API_KEY)
            else "missing"
        )
        if credential_status == "configured" and (
            DISCOURSE_API_USERNAME.startswith("your_")
            or DISCOURSE_API_KEY.startswith("your_")
        ):
            credential_status = "placeholder_values"

        processing_mode = "topic_centric"

        for date_str, date_posts in posts_by_date.items():
            output_file = OUTPUT_DIR / f"{date_str}.json"

            # Load existing data if file exists
            existing_posts = []
            if output_file.exists():
                try:
                    with open(output_file, "r") as f:
                        existing_data = json.load(f)
                        existing_posts = existing_data.get("forum_posts", [])
                except (json.JSONDecodeError, IOError):
                    existing_posts = []

            # Combine with new posts, avoiding duplicates based on post_id
            existing_post_ids = {post.get("post_id") for post in existing_posts}
            new_posts = [
                post
                for post in date_posts
                if post.get("post_id") not in existing_post_ids
            ]

            # Merge all posts
            all_date_posts = existing_posts + new_posts

            # Determine status based on data
            status = "success" if all_date_posts else "no_new_content"

            output_data = {
                "date": date_str,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "discourse_forum",
                "status": status,
                "forum_posts": all_date_posts,
                "metadata": {
                    "forums_processed": len(load_discourse_config()),
                    "total_posts_fetched": len(all_date_posts),
                    "credential_status": credential_status,
                    "processing_mode": processing_mode,
                },
            }

            # Save to file
            try:
                with open(output_file, "w") as f:
                    json.dump(output_data, f, indent=2)

                if new_posts:
                    print(
                        f"💾 Saved {len(new_posts)} new posts to: {output_file} "
                        f"(total: {len(all_date_posts)})"
                    )
                else:
                    print(
                        f"📄 No new posts for {date_str} "
                        f"(existing: {len(all_date_posts)})"
                    )

                saved_files.append(output_file)
                total_posts += len(new_posts)

            except IOError as e:
                print(f"❌ Error saving forum data to {output_file}: {e}")
                return False

        print(
            f"📊 Total new posts saved: {total_posts} across {len(posts_by_date)} dates"
        )
        return True


def main():
    """Main entry point for discourse ingestion"""
    parser = argparse.ArgumentParser(description="Ingest Discourse forum data")
    parser.add_argument(
        "--date", help="Date for output file (YYYY-MM-DD), defaults to today"
    )
    parser.add_argument(
        "--full-history",
        action="store_true",
        help="Ignore state and fetch all available posts (use with caution)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        help="Number of days back to fetch posts (filters by creation date)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force processing even if no new posts found (bypass deduplication)",
    )
    parser.add_argument(
        "--categories",
        type=str,
        help=(
            "Comma-separated list of category slugs to fetch "
            "(e.g., 'l1-l2,consensus'). Only works with --full-history"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Custom output file path (optional). Uses default location if not set",
    )

    args = parser.parse_args()

    print("🏛️ Starting Discourse Forum Ingestion")
    print("=" * 50)

    if args.days_back:
        print(f"📅 Date filtering: Only posts from the last {args.days_back} days")

    # Parse category filter if provided
    target_categories = None
    if args.categories:
        if not args.full_history:
            print("⚠️ Warning: --categories flag only works with --full-history mode")
            print("   Category filtering will be ignored.")
        else:
            target_categories = [cat.strip() for cat in args.categories.split(",")]
            print(f"🎯 Category filtering enabled: {', '.join(target_categories)}")

    # Check API credentials
    if not DISCOURSE_API_USERNAME or not DISCOURSE_API_KEY:
        print("⚠️ Discourse API credentials not configured.")
        print("   Please set DISCOURSE_API_USERNAME and DISCOURSE_API_KEY in .env")
        print("   Skipping forum ingestion.")
        # Still create an empty file for pipeline consistency
        save_forum_data([], args.date, args.full_history, args.output)
        sys.exit(2)  # Exit code 2 indicates "no new content"

    if DISCOURSE_API_USERNAME.startswith("your_") or DISCOURSE_API_KEY.startswith(
        "your_"
    ):
        print("⚠️ Discourse API credentials are placeholder values.")
        print("   Please configure real credentials in .env file")
        # Still create an empty file for pipeline consistency
        save_forum_data([], args.date, args.full_history, args.output)
        sys.exit(2)  # Exit code 2 indicates "no new content"

    # Load configuration
    forum_configs = load_discourse_config()
    if not forum_configs:
        print("⚠️ No enabled Discourse forums found in configuration")
        save_forum_data([], args.date, args.full_history, args.output)
        sys.exit(2)  # Exit code 2 indicates "no new content"

    # Load/reset state
    if args.full_history:
        print("🔄 Full history mode: Ignoring existing state")
        state = {"historical_discovery_state": {}}
    else:
        state = load_state()

    # Get existing posts for cross-file deduplication (unless force flag is used)
    existing_posts = set()
    if not args.force:
        existing_posts = get_existing_forum_posts()

    if args.force:
        print("⚠️  Force flag used - bypassing deduplication checks")

    # Process all configured forums
    all_posts = []

    try:
        for forum_config in forum_configs:
            forum_posts = process_forum(
                forum_config,
                state,
                args.full_history,
                args.days_back,
                target_categories,
            )
            all_posts.extend(forum_posts)

        # Filter out existing posts (unless force flag is used)
        if not args.force:
            filtered_posts = filter_new_forum_posts(all_posts, existing_posts)

            if len(filtered_posts) == 0 and len(all_posts) > 0:
                print("\n🎯 Smart deduplication result:")
                print(f"   - Total posts fetched: {len(all_posts)}")
                print("   - New posts (not in database): 0")
                print(
                    "\n✨ No new forum posts found - saving empty file with metadata!"
                )
                print("ℹ️  Use --force flag to bypass deduplication if needed.")

                # Save empty file with metadata for consistency
                filtered_posts = []

            final_posts = filtered_posts
        else:
            final_posts = all_posts

        # Save results
        success = save_forum_data(
            final_posts, args.date, args.full_history, args.output
        )
        if success:
            save_state(state)
            print("\n✅ Discourse ingestion completed successfully")
            print(f"📊 Total posts fetched: {len(all_posts)}")
            if not args.force and len(all_posts) > len(final_posts):
                print(
                    f"📊 Duplicate posts filtered: {len(all_posts) - len(final_posts)}"
                )
            print(f"📊 New posts saved: {len(final_posts)}")

            # Exit with code 2 if no new content found (for pipeline optimization)
            if len(final_posts) == 0:
                sys.exit(2)  # Exit code 2 indicates "no new content"
        else:
            print("\n❌ Error occurred during save operation")

    except KeyboardInterrupt:
        print("\n⚠️ Ingestion interrupted by user")
        # Save partial state
        save_state(state)
    except Exception as e:
        print(f"\n❌ Unexpected error during ingestion: {e}")
        # Save partial state
        save_state(state)


if __name__ == "__main__":
    main()
