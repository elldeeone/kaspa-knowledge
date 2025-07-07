#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - Daily Facts Extractor

This script reads the raw aggregated daily data and extracts
key technical facts, insights, and important developments from ALL sources.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Set
from scripts.llm_interface import LLMInterface
from scripts.prompt_loader import prompt_loader


class FactsExtractor:
    def __init__(
        self,
        input_dir: str = "data/aggregated",
        output_dir: str = "data/facts",
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

    def load_processed_source_urls(self, days_back: int = 7) -> Set[str]:
        """Load URLs processed in the last N days to avoid duplication."""
        processed_urls = set()

        # Get the current date
        current_date = datetime.now()

        for i in range(1, days_back + 1):  # Check previous N days
            check_date = (current_date - timedelta(days=i)).strftime("%Y-%m-%d")
            facts_file = self.output_dir / f"{check_date}.json"

            if facts_file.exists():
                try:
                    with open(facts_file, "r", encoding="utf-8") as f:
                        facts_data = json.load(f)

                    # Extract URLs from all facts
                    for fact in facts_data.get("facts", []):
                        source = fact.get("source", {})
                        url = source.get("url", "")
                        if url:
                            processed_urls.add(url)

                except (json.JSONDecodeError, IOError) as e:
                    print(f"⚠️  Warning: Could not read facts file {facts_file}: {e}")
                    continue

        if processed_urls:
            print(
                f"🔍 Loaded {len(processed_urls)} previously processed source URLs "
                f"from last {days_back} days"
            )

        return processed_urls

    def is_duplicate_source(
        self, source_info: Dict[str, Any], processed_urls: Set[str]
    ) -> bool:
        """Check if a source has already been processed based on URL."""
        url = source_info.get("url", "")
        return url in processed_urls if url else False

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
            return "extract_kaspa_facts"

        # For facts extraction, we use the same kaspa facts prompt
        # but may enhance context. All period types use the same core
        # facts extraction prompt
        return "extract_kaspa_facts"

    def extract_facts_from_content(
        self, content: str, source_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract facts from any content using the generic LLM prompt."""
        if not content or not content.strip():
            return []

        try:
            # Enhance source_info with period context if available
            enhanced_source_info = source_info.copy()
            if self.period_summary and hasattr(self, "_current_period_metadata"):
                enhanced_source_info["period_context"] = (
                    self._current_period_metadata.get("period_label", "")
                )

            prompt = prompt_loader.format_prompt(
                "extract_kaspa_facts",
                source_type=enhanced_source_info["type"],
                title=enhanced_source_info.get("title", "N/A"),
                author=enhanced_source_info.get("author", "N/A"),
                url=enhanced_source_info.get("url", "N/A"),
                date=enhanced_source_info.get("date", "N/A"),
                content=content[:4000] + ("..." if len(content) > 4000 else ""),
            )

            system_prompt = prompt_loader.get_system_prompt("extract_kaspa_facts")
            facts_response = self.llm.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
            )

            # Parse the facts
            facts = self.parse_facts_response(facts_response, enhanced_source_info)
            return facts

        except Exception as e:
            print(f"    ⚠️  Failed to extract facts from {source_info['type']}: {e}")
            return []

    def extract_facts_from_batch(
        self, batch_items: List[Dict[str, Any]], source_type: str
    ) -> List[Dict[str, Any]]:
        """Extract facts from a batch of items using a single LLM call."""
        if not batch_items:
            return []

        # Build a combined prompt for the batch
        batch_content = f"BATCH PROCESSING: {len(batch_items)} {source_type} items\n\n"

        for i, item in enumerate(batch_items, 1):
            source_info = item["source_info"]
            content = item["content"]

            batch_content += f"=== ITEM {i} ===\n"
            batch_content += f"Title: {source_info.get('title', 'N/A')}\n"
            batch_content += f"Author: {source_info.get('author', 'N/A')}\n"
            batch_content += f"Date: {source_info.get('date', 'N/A')}\n"
            batch_content += f"URL: {source_info.get('url', 'N/A')}\n"
            truncated_content = content[:2000] + ("..." if len(content) > 2000 else "")
            batch_content += f"Content: {truncated_content}\n\n"

        try:
            # Create batch prompt
            count = len(batch_items)
            prompt = (
                f"""Extract key technical facts from this batch of {count} """
                f"""{source_type} items:

{batch_content}

Please extract and list technical facts, announcements, or insights related to Kaspa.
For each fact, format as:
- ITEM: [item number from above]
- FACT: [specific technical fact or announcement]
- CATEGORY: [technical|governance|development|security|mining|consensus|community|
  performance|other]
- IMPACT: [high|medium|low]
- CONTEXT: [brief explanation of why this matters to Kaspa]

Only include factual, verifiable information. Skip opinions or speculation.
Focus on information that is technically relevant to Kaspa's development,
ecosystem, or technology."""
            )

            system_prompt = prompt_loader.get_system_prompt("extract_kaspa_facts")
            facts_response = self.llm.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
            )

            # Parse the batch facts response
            facts = self.parse_batch_facts_response(facts_response, batch_items)
            return facts

        except Exception as e:
            print(
                f"    ⚠️  Failed to extract facts from batch of "
                f"{len(batch_items)} {source_type}: {e}"
            )
            # Fallback to individual processing for this batch
            print("    🔄 Falling back to individual processing for this batch...")
            all_facts = []
            for item in batch_items:
                individual_facts = self.extract_facts_from_content(
                    item["content"], item["source_info"]
                )
                all_facts.extend(individual_facts)
            return all_facts

    def extract_medium_facts(
        self, articles: List[Dict], processed_urls: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract key facts from Medium articles."""
        if not articles:
            return []

        print(f"🔍 Extracting facts from {len(articles)} Medium articles...")

        all_facts = []
        skipped_count = 0

        for i, article in enumerate(articles, 1):
            print(f"  {i}/{len(articles)} - {article['title'][:60]}...")

            source_info = {
                "type": "medium_article",
                "title": article["title"],
                "author": article["author"],
                "url": article["link"],
                "date": article.get("published", "Unknown"),
            }

            # Check for duplicates
            if self.is_duplicate_source(source_info, processed_urls):
                print("    ⏭️  Skipping - already processed this URL")
                skipped_count += 1
                continue

            facts = self.extract_facts_from_content(
                article.get("summary", ""), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")
            else:
                print("    ℹ️  No facts extracted")

        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} duplicate Medium articles")

        return all_facts

    def extract_github_facts(
        self, github_activities: List[Dict], processed_urls: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract key facts from GitHub activities using efficient batching."""
        if not github_activities:
            return []

        print(f"🔍 Extracting facts from {len(github_activities)} GitHub activities...")

        # Filter out duplicates first
        valid_activities = []
        skipped_count = 0

        for activity in github_activities:
            activity_type = activity.get("activity_type", "unknown")

            source_info = {
                "type": activity_type,
                "title": activity.get("title", ""),
                "author": activity.get("author", "Unknown"),
                "url": activity.get("url", ""),
                "date": activity.get("date", ""),
                "repository": activity.get("repo", ""),
            }

            # Check for duplicates
            if self.is_duplicate_source(source_info, processed_urls):
                skipped_count += 1
                continue

            valid_activities.append(
                {
                    "activity": activity,
                    "source_info": source_info,
                    "content": activity.get("content", ""),
                }
            )

        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} duplicate GitHub activities")

        print(f"📦 Processing {len(valid_activities)} valid activities in batches...")

        # Process in batches of 10 for GitHub activities (they tend to be shorter)
        BATCH_SIZE = 10
        all_facts = []

        for i in range(0, len(valid_activities), BATCH_SIZE):
            batch = valid_activities[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(valid_activities) + BATCH_SIZE - 1) // BATCH_SIZE

            print(
                f"  📦 Processing batch {batch_num}/{total_batches} "
                f"({len(batch)} activities)..."
            )

            # Prepare batch items for processing
            batch_items = []
            for item in batch:
                batch_items.append(
                    {"source_info": item["source_info"], "content": item["content"]}
                )

            # Process batch
            batch_facts = self.extract_facts_from_batch(batch_items, "github_activity")
            all_facts.extend(batch_facts)

            if batch_facts:
                print(f"    ✅ Extracted {len(batch_facts)} facts from batch")
            else:
                print("    ℹ️  No facts extracted from batch")

        print(f"🐙 GitHub processing complete: {len(all_facts)} total facts extracted")
        return all_facts

    def extract_telegram_facts(
        self, messages: List[Dict], processed_urls: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract key facts from Telegram messages."""
        if not messages:
            return []

        print(f"🔍 Extracting facts from {len(messages)} Telegram messages...")

        all_facts = []
        skipped_count = 0

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

            # Check for duplicates
            if self.is_duplicate_source(source_info, processed_urls):
                print("    ⏭️  Skipping - already processed this URL")
                skipped_count += 1
                continue

            facts = self.extract_facts_from_content(
                message.get("content", ""), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")
            else:
                print("    ℹ️  No facts extracted")

        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} duplicate Telegram messages")

        return all_facts

    def extract_discord_facts(
        self, messages: List[Dict], processed_urls: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract key facts from Discord messages."""
        if not messages:
            return []

        print(f"🔍 Extracting facts from {len(messages)} Discord messages...")

        all_facts = []
        skipped_count = 0

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

            # Check for duplicates
            if self.is_duplicate_source(source_info, processed_urls):
                print("    ⏭️  Skipping - already processed this URL")
                skipped_count += 1
                continue

            facts = self.extract_facts_from_content(
                message.get("content", ""), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")
            else:
                print("    ℹ️  No facts extracted")

        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} duplicate Discord messages")

        return all_facts

    def extract_forum_facts(
        self, posts: List[Dict], processed_urls: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract key facts from forum posts using efficient batching."""
        if not posts:
            return []

        print(f"🔍 Extracting facts from {len(posts)} forum posts...")

        # Filter out duplicates first
        valid_posts = []
        skipped_count = 0

        for post in posts:
            post_author = post.get("author", "Unknown")
            post_topic = post.get("topic_title") or post.get("title") or "untitled"

            source_info = {
                "type": "forum_post",
                "title": post_topic,
                "author": post_author,
                "url": post.get("url", "Unknown"),
                "date": post.get("created_at", post.get("date", "unknown")),
            }

            # Check for duplicates
            if self.is_duplicate_source(source_info, processed_urls):
                skipped_count += 1
                continue

            valid_posts.append(
                {
                    "post": post,
                    "source_info": source_info,
                    "content": post.get("content", ""),
                }
            )

        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} duplicate forum posts")

        print(f"📦 Processing {len(valid_posts)} valid posts in batches...")

        # Process in batches of 5 to balance efficiency with context limits
        BATCH_SIZE = 5
        all_facts = []

        for i in range(0, len(valid_posts), BATCH_SIZE):
            batch = valid_posts[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(valid_posts) + BATCH_SIZE - 1) // BATCH_SIZE

            print(
                f"  📦 Processing batch {batch_num}/{total_batches} "
                f"({len(batch)} posts)..."
            )

            # Prepare batch items for processing
            batch_items = []
            for item in batch:
                batch_items.append(
                    {"source_info": item["source_info"], "content": item["content"]}
                )

            # Process batch
            batch_facts = self.extract_facts_from_batch(batch_items, "forum_post")
            all_facts.extend(batch_facts)

            if batch_facts:
                print(f"    ✅ Extracted {len(batch_facts)} facts from batch")
            else:
                print("    ℹ️  No facts extracted from batch")

        print(f"🏛️ Forum processing complete: {len(all_facts)} total facts extracted")
        return all_facts

    def extract_news_facts(
        self, articles: List[Dict], processed_urls: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract key facts from news articles."""
        if not articles:
            return []

        print(f"🔍 Extracting facts from {len(articles)} news articles...")

        all_facts = []
        skipped_count = 0

        for i, article in enumerate(articles, 1):
            print(f"  {i}/{len(articles)} - {article.get('title', 'untitled')[:60]}...")

            source_info = {
                "type": "news_article",
                "title": article.get("title", "Untitled News Article"),
                "author": article.get("author", "Unknown"),
                "url": article.get("url", "Unknown"),
                "date": article.get("published", "unknown"),
            }

            # Check for duplicates
            if self.is_duplicate_source(source_info, processed_urls):
                print("    ⏭️  Skipping - already processed this URL")
                skipped_count += 1
                continue

            facts = self.extract_facts_from_content(
                article.get("content", article.get("summary", "")), source_info
            )
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")

        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} duplicate news articles")

        return all_facts

    def extract_documentation_facts(
        self, docs: List[Dict], processed_urls: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract key facts from documentation updates."""
        if not docs:
            return []

        print(f"🔍 Extracting facts from {len(docs)} documentation items...")

        all_facts = []
        skipped_count = 0

        for i, doc in enumerate(docs, 1):
            print(f"  {i}/{len(docs)} - {doc.get('title', 'untitled')[:60]}...")

            source_info = {
                "type": "documentation",
                "title": doc.get("title", "Documentation Update"),
                "author": doc.get("author", "Kaspa Team"),
                "url": doc.get("url", "Unknown"),
                "date": doc.get("updated", "unknown"),
            }

            # Check for duplicates
            if self.is_duplicate_source(source_info, processed_urls):
                print("    ⏭️  Skipping - already processed this URL")
                skipped_count += 1
                continue

            facts = self.extract_facts_from_content(doc.get("content", ""), source_info)
            all_facts.extend(facts)

            if facts:
                print(f"    ✅ Extracted {len(facts)} facts")

        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} duplicate documentation items")

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

    def parse_batch_facts_response(
        self, response: str, batch_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Parse batch facts response into structured facts."""
        facts = []
        lines = response.split("\n")
        current_fact = {}
        current_item_index = None

        for line in lines:
            line = line.strip()
            if line.startswith("- ITEM:"):
                # Extract item number
                try:
                    item_num = int(line[7:].strip())
                    current_item_index = item_num - 1  # Convert to 0-based index
                except (ValueError, IndexError):
                    current_item_index = None
            elif line.startswith("- FACT:"):
                if current_fact and current_item_index is not None:
                    # Save previous fact
                    if current_item_index < len(batch_items):
                        source_info = batch_items[current_item_index]["source_info"]
                        facts.append(self.finalize_fact(current_fact, source_info))
                current_fact = {"fact": line[7:].strip()}
            elif line.startswith("- CATEGORY:"):
                current_fact["category"] = line[11:].strip()
            elif line.startswith("- IMPACT:"):
                current_fact["impact"] = line[9:].strip()
            elif line.startswith("- CONTEXT:"):
                current_fact["context"] = line[10:].strip()

        # Don't forget the last fact
        if current_fact and current_item_index is not None:
            if current_item_index < len(batch_items):
                source_info = batch_items[current_item_index]["source_info"]
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
        """Extract facts from daily/period aggregated data."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        period_type = "period" if self.period_summary else "daily"
        print(f"\n🔍 Extracting facts from {period_type} data for {date}")
        print("=" * 60)

        # Check if facts already exist for this date (deduplication)
        if not self.force:
            existing_facts_path = self.output_dir / f"{date}.json"
            if existing_facts_path.exists():
                try:
                    with open(existing_facts_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)

                    # Check if existing facts file has substantial content
                    if existing_data and existing_data.get("facts"):
                        print("📋 Facts already exist for this date")
                        print("⚡ Skipping extraction to avoid duplicates")
                        print("ℹ️  Use --force flag to override this behavior")

                        # Return existing data to maintain consistency
                        print("\n💾 Using existing facts")
                        print(f"   📁 {existing_facts_path}")

                        # Mark this data as loaded from existing file for summary logic
                        existing_data["_loaded_from_existing"] = True
                        return existing_data

                except (json.JSONDecodeError, IOError) as e:
                    print(f"⚠️  Warning: Could not read existing facts file: {e}")
                    print("🔄 Proceeding with fresh extraction...")
        else:
            print("⚠️  Force flag used - bypassing deduplication checks")

        # Load aggregated data (daily or period-based)
        try:
            aggregated_data = self.load_daily_data(date)
        except FileNotFoundError as e:
            print(f"❌ Error loading data: {e}")
            raise

        # Extract period metadata if in period summary mode
        period_metadata = self.extract_period_metadata(aggregated_data)

        # Store period metadata for use in fact extraction
        if self.period_summary and period_metadata:
            self._current_period_metadata = period_metadata
            print(f"📊 Period: {period_metadata.get('period_label', 'Unknown')}")
            print(f"📅 Range: {period_metadata.get('date_range', 'Unknown')}")
            print(f"📈 Total items: {period_metadata.get('total_items', 0)}")

        sources = aggregated_data.get("sources", {})
        all_facts = []
        source_stats = {}

        # Load processed URLs to avoid duplicate fact extraction
        # For period summaries, expand the lookback window
        lookback_days = 30 if self.period_summary else 7
        processed_urls = self.load_processed_source_urls(days_back=lookback_days)

        # Extract facts from each source type
        print(f"\n🔍 Processing {len(sources)} source types...")

        # Medium articles
        medium_facts = self.extract_medium_facts(
            sources.get("medium_articles", []), processed_urls
        )
        all_facts.extend(medium_facts)
        source_stats["medium"] = len(medium_facts)

        # GitHub activities (individual activities with metadata)
        github_facts = self.extract_github_facts(
            sources.get("github_activities", []), processed_urls
        )
        all_facts.extend(github_facts)
        source_stats["github"] = len(github_facts)

        # Telegram messages
        telegram_facts = self.extract_telegram_facts(
            sources.get("telegram_messages", []), processed_urls
        )
        all_facts.extend(telegram_facts)
        source_stats["telegram"] = len(telegram_facts)

        # Discord messages
        discord_facts = self.extract_discord_facts(
            sources.get("discord_messages", []), processed_urls
        )
        all_facts.extend(discord_facts)
        source_stats["discord"] = len(discord_facts)

        # Forum posts
        forum_facts = self.extract_forum_facts(
            sources.get("forum_posts", []), processed_urls
        )
        all_facts.extend(forum_facts)
        source_stats["forum"] = len(forum_facts)

        # News articles
        news_facts = self.extract_news_facts(
            sources.get("news_articles", []), processed_urls
        )
        all_facts.extend(news_facts)
        source_stats["news"] = len(news_facts)

        # Documentation
        doc_facts = self.extract_documentation_facts(
            sources.get("documentation", []), processed_urls
        )
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
                "is_period_summary": self.period_summary,
            },
        }

        # Add period metadata to facts data if in period summary mode
        if self.period_summary and period_metadata:
            facts_data["period_metadata"] = period_metadata

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

            # Check if facts were loaded from existing file (deduplication)
            loaded_from_existing = facts_data.pop("_loaded_from_existing", False)

            # Save facts (only if new extraction)
            if not loaded_from_existing:
                output_path = self.save_facts(facts_data, date)
            else:
                # Don't save, just reference existing path
                if date is None:
                    date = datetime.now().strftime("%Y-%m-%d")
                output_path = self.output_dir / f"{date}.json"

            all_facts = facts_data["facts"]

            # Show brief summary if loaded from existing, detailed if newly extracted
            if loaded_from_existing:
                print(
                    "\nℹ️  Daily Facts Extraction found existing content - "
                    "skipping downstream processing"
                )
                success_msg = (
                    f"Facts extraction skipped - using {len(all_facts)} existing facts"
                )
            else:
                # Print detailed summary for new extractions
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
                for category, count in sorted(fact_stats["by_category"].items()):
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-extraction even if facts already exist for this date",
    )
    parser.add_argument(
        "--period-summary",
        action="store_true",
        help="Extract facts from period-based aggregated data "
        "(weekly, monthly, historical) instead of daily data",
    )

    args = parser.parse_args()

    extractor = FactsExtractor(force=args.force, period_summary=args.period_summary)
    result = extractor.run_facts_extraction(args.date)
    print(f"\n🎯 {result}")


if __name__ == "__main__":
    main()
