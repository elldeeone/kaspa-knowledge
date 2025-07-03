#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - Discourse Forum Ingestion

Fetches topics and posts from configured Discourse forums using the API.
Implements topic-centric ingestion with stateful tracking to prevent data loss.
Follows the three-stage pipeline: Ingest → Aggregate → AI Process
"""

import os
import json
import requests
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DISCOURSE_API_USERNAME = os.getenv("DISCOURSE_API_USERNAME")
DISCOURSE_API_KEY = os.getenv("DISCOURSE_API_KEY")
CONFIG_PATH = Path("config/sources.config.json")
OUTPUT_DIR = Path("sources/forum")
STATE_PATH = Path("sources/forum/state.json")


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
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Error loading state file: {e}")
            return {}
    return {}


def save_state(state):
    """Save the state tracking per-topic last post numbers"""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        print(f"💾 State saved to {STATE_PATH}")
    except IOError as e:
        print(f"❌ Error saving state: {e}")


def make_api_request(url, headers, timeout=30):
    """Make a rate-limited API request with error handling"""
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"   ❌ API request failed for {url}: {e}")
        return None


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
        topics.append(
            {
                "id": topic_data.get("id"),
                "title": topic_data.get("title"),
                "slug": topic_data.get("slug"),
                "posts_count": topic_data.get("posts_count", 0),
                "last_posted_at": topic_data.get("last_posted_at"),
                "category_id": topic_data.get("category_id"),
            }
        )

    print(f"   📋 Found {len(topics)} recent topics")
    return topics


def fetch_new_posts_for_topic(
    forum_config, topic_id, last_post_number=0, topic_info=None
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

    for post in posts:
        post_number = post.get("post_number", 0)

        # Only process posts after our last tracked post number
        if post_number > last_post_number:
            post_info = {
                "post_id": post.get("id"),
                "post_number": post_number,
                "topic_id": topic_id,
                "topic_title": topic_title,
                "topic_slug": topic_slug,
                "content": post.get("cooked", ""),  # HTML content
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
    return new_posts, highest_post_number


def process_forum(forum_config, state):
    """Process a single Discourse forum"""
    forum_name = forum_config.get("name", "unknown")
    base_url = forum_config["base_url"]

    print(f"\n🏛️ Processing forum: {forum_name} ({base_url})")

    # Initialize forum state if not exists
    forum_state = state.setdefault(base_url, {"topics": {}})

    # Fetch recent topics
    recent_topics = fetch_recent_topics(forum_config)
    if not recent_topics:
        print(f"   ⚠️ No recent topics found for {forum_name}")
        return []

    all_posts = []
    rate_limit_delay = forum_config.get("rate_limit_seconds", 0.5)

    for topic in recent_topics:
        topic_id = topic["id"]
        topic_state = forum_state["topics"].setdefault(
            str(topic_id), {"last_post_number": 0}
        )
        last_post_number = topic_state["last_post_number"]

        # Fetch new posts for this topic, passing topic info for title/slug
        new_posts, new_last_post_number = fetch_new_posts_for_topic(
            forum_config, topic_id, last_post_number, topic_info=topic
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


def save_forum_data(all_posts, date=None):
    """Save forum posts data to dated JSON file"""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{date}.json"

    # Determine status based on data
    if all_posts:
        status = "success"
    else:
        status = "no_new_content"

    # Check credential status
    credential_status = (
        "configured" if (DISCOURSE_API_USERNAME and DISCOURSE_API_KEY) else "missing"
    )
    if credential_status == "configured" and (
        DISCOURSE_API_USERNAME.startswith("your_")
        or DISCOURSE_API_KEY.startswith("your_")
    ):
        credential_status = "placeholder_values"

    output_data = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "discourse_forum",
        "status": status,
        "forum_posts": all_posts,
        "metadata": {
            "forums_processed": len(load_discourse_config()),
            "total_posts_fetched": len(all_posts),
            "credential_status": credential_status,
            "processing_mode": "topic_centric",
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

    args = parser.parse_args()

    print("🏛️ Starting Discourse Forum Ingestion")
    print("=" * 50)

    # Check API credentials
    if not DISCOURSE_API_USERNAME or not DISCOURSE_API_KEY:
        print("⚠️ Discourse API credentials not configured.")
        print("   Please set DISCOURSE_API_USERNAME and DISCOURSE_API_KEY in .env")
        print("   Skipping forum ingestion.")
        # Still create an empty file for pipeline consistency
        save_forum_data([], args.date)
        sys.exit(2)  # Exit code 2 indicates "no new content"

    if DISCOURSE_API_USERNAME.startswith("your_") or DISCOURSE_API_KEY.startswith(
        "your_"
    ):
        print("⚠️ Discourse API credentials are placeholder values.")
        print("   Please configure real credentials in .env file")
        # Still create an empty file for pipeline consistency
        save_forum_data([], args.date)
        sys.exit(2)  # Exit code 2 indicates "no new content"

    # Load configuration
    forum_configs = load_discourse_config()
    if not forum_configs:
        print("⚠️ No enabled Discourse forums found in configuration")
        save_forum_data([], args.date)
        sys.exit(2)  # Exit code 2 indicates "no new content"

    # Load/reset state
    if args.full_history:
        print("🔄 Full history mode: Ignoring existing state")
        state = {}
    else:
        state = load_state()

    # Process all configured forums
    all_posts = []

    try:
        for forum_config in forum_configs:
            forum_posts = process_forum(forum_config, state)
            all_posts.extend(forum_posts)

        # Save results
        success = save_forum_data(all_posts, args.date)
        if success:
            save_state(state)
            print("\n✅ Discourse ingestion completed successfully")
            print(f"📊 Total posts fetched: {len(all_posts)}")

            # Exit with code 2 if no new content found (for pipeline optimization)
            if len(all_posts) == 0:
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
