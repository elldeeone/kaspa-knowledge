# scripts/telegram_ingest.py
import os
import json
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import Message, User
from telethon.errors import FloodWaitError

# --- Configuration ---
load_dotenv()
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "kaspa_knowledge_hub")
CONFIG_PATH = Path("config/sources.config.json")
STATE_PATH = Path("sources/telegram/state.json")


# --- State Management ---
def load_state():
    """Loads the last processed message IDs from the state file."""
    if STATE_PATH.exists():
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    """Saves the last processed message IDs to the state file."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def get_existing_telegram_messages():
    """
    Cross-file deduplication: Load all existing telegram messages from all files.
    Returns a set of unique message identifiers for O(1) lookup performance.
    """
    existing_messages = set()
    sources_dir = Path("sources/telegram")

    if not sources_dir.exists():
        return existing_messages

    # Get all JSON files in the telegram directory (including group subdirectories)
    json_files = list(sources_dir.rglob("*.json"))

    if not json_files:
        return existing_messages

    print(
        f"🔍 Checking for existing telegram messages across {len(json_files)} files..."
    )

    total_existing = 0
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Handle different data structures
                messages = []
                if isinstance(data, list):
                    # Direct list of messages (older format)
                    messages = data
                elif isinstance(data, dict):
                    # Check for messages in various keys
                    if "messages" in data:
                        messages = data.get("messages", [])
                    elif isinstance(data, dict) and any(
                        isinstance(v, list) for v in data.values()
                    ):
                        # Flatten all lists in the dict
                        for value in data.values():
                            if isinstance(value, list):
                                messages.extend(value)

                # Process messages to extract unique identifiers
                for message in messages:
                    if isinstance(message, dict) and "message_id" in message:
                        group = message.get("group", "unknown")
                        # Use group + message_id as unique identifier
                        existing_messages.add(f"{group}#{message['message_id']}")
                        total_existing += 1

        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Warning: Could not read {file_path}: {e}")
            continue

    print(
        f"📚 Found {total_existing} existing telegram messages for deduplication check"
    )
    return existing_messages


def filter_new_telegram_messages(all_messages, existing_messages):
    """
    Filter out telegram messages that already exist in our database.
    Returns only genuinely new messages.
    """
    if not existing_messages:
        return all_messages

    new_messages = []
    for message in all_messages:
        if isinstance(message, dict) and "message_id" in message:
            group = message.get("group", "unknown")
            message_key = f"{group}#{message['message_id']}"
            if message_key not in existing_messages:
                new_messages.append(message)
        else:
            # Include messages without message_id (though this shouldn't happen)
            new_messages.append(message)

    return new_messages


# --- Core Fetching Logic ---
async def fetch_messages(full_history=False):
    """Fetch messages from all configured Telegram groups."""
    if not all([API_ID, API_HASH, SESSION_NAME]):
        print("⚠️ Telegram API credentials not set. Skipping.")
        return None

    # Check for placeholder values
    if (
        API_ID.startswith("your_")
        or API_HASH.startswith("your_")
        or not API_ID.isdigit()
    ):
        print(
            "⚠️ Telegram API credentials are placeholder values. "
            "Please configure real credentials from https://my.telegram.org"
        )
        return None

    if not CONFIG_PATH.exists():
        print(f"⚠️ Config file not found at {CONFIG_PATH}. Skipping.")
        return None

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f).get("telegram_groups", [])

    # Check if there are any enabled groups
    enabled_groups = [g for g in config if g.get("enabled", False)]
    if not enabled_groups:
        print("⚠️ No enabled Telegram groups found in config. Skipping.")
        return None

    state = load_state()
    all_messages_data = []

    async with TelegramClient(SESSION_NAME, int(API_ID), API_HASH) as client:
        print(f"✅ Connected to Telegram as {SESSION_NAME}")

        for group_config in enabled_groups:

            username = group_config["username"]
            print(f"\n🔄 Processing Group: @{username}")

            try:
                target_group = await client.get_entity(username)
                group_state = state.setdefault(username, {"topics": {}})

                if group_config.get("has_topics", False):
                    # --- Handle Groups with Topics ---
                    result = await client(GetForumTopicsRequest(channel=target_group))
                    topics = result.topics
                    print(f"   - Found {len(topics)} topics.")
                    for topic in topics:
                        topic_id_str = str(topic.id)
                        topic_state = group_state["topics"].setdefault(topic_id_str, {})
                        last_message_id = topic_state.get("last_message_id", 0)

                        if full_history or (
                            group_config.get("backfill_on_first_run")
                            and not last_message_id
                        ):
                            print(
                                f"     - Topic '{topic.title}': "
                                f"Performing full history backfill."
                            )
                            last_message_id = 0

                        messages, new_last_id = await fetch_topic_messages(
                            client, target_group, topic, last_message_id
                        )
                        all_messages_data.extend(messages)
                        if new_last_id:
                            topic_state["last_message_id"] = new_last_id
                else:
                    # --- Handle Regular Groups/Channels ---
                    last_message_id = group_state.get("last_message_id", 0)
                    if full_history or (
                        group_config.get("backfill_on_first_run")
                        and not last_message_id
                    ):
                        print("     - Performing full history backfill for group.")
                        last_message_id = 0

                    messages, new_last_id = await fetch_group_messages(
                        client, target_group, last_message_id
                    )
                    all_messages_data.extend(messages)
                    if new_last_id:
                        group_state["last_message_id"] = new_last_id

            except Exception as e:
                print(f"   ❌ Error processing group @{username}: {e}")

    save_state(state)
    print(f"\n📊 Total new messages fetched: {len(all_messages_data)}")
    return all_messages_data


async def fetch_topic_messages(client, group, topic, last_id):
    """Fetch new messages from a specific topic with rate limiting."""
    messages_data = []
    new_last_id = last_id

    try:
        async for message in client.iter_messages(
            group, reply_to=topic.id, min_id=last_id
        ):
            if isinstance(message, Message) and message.text:
                sender = await message.get_sender()
                sender_username = "Unknown"
                if isinstance(sender, User):
                    sender_username = (
                        sender.username
                        or f"{sender.first_name} {sender.last_name or ''}".strip()
                    )

                messages_data.append(
                    {
                        "message_id": message.id,
                        "topic_id": topic.id,
                        "topic_title": topic.title,
                        "text": message.text,
                        "date": message.date.isoformat(),
                        "sender_username": sender_username,
                        "group": group.title,
                    }
                )
                new_last_id = max(new_last_id, message.id)
    except FloodWaitError as e:
        print(
            f"     ⏳ Rate limit hit for topic '{topic.title}', "
            f"waiting {e.seconds} seconds..."
        )
        await asyncio.sleep(e.seconds)
        # Retry the operation after waiting
        return await fetch_topic_messages(client, group, topic, last_id)
    except Exception as e:
        print(f"     ❌ Error fetching topic '{topic.title}': {e}")

    print(f"     - Topic '{topic.title}': Fetched {len(messages_data)} new messages.")
    return messages_data, new_last_id


async def fetch_group_messages(client, group, last_id):
    """Fetch new messages from a regular group or channel with rate limiting."""
    messages_data = []
    new_last_id = last_id

    try:
        async for message in client.iter_messages(group, min_id=last_id):
            if isinstance(message, Message) and message.text:
                sender = await message.get_sender()
                sender_username = "Unknown"
                if isinstance(sender, User):
                    sender_username = (
                        sender.username
                        or f"{sender.first_name} {sender.last_name or ''}".strip()
                    )

                messages_data.append(
                    {
                        "message_id": message.id,
                        "topic_id": None,
                        "topic_title": None,
                        "text": message.text,
                        "date": message.date.isoformat(),
                        "sender_username": sender_username,
                        "group": group.title,
                    }
                )
                new_last_id = max(new_last_id, message.id)
    except FloodWaitError as e:
        print(
            f"     ⏳ Rate limit hit for group '{group.title}', "
            f"waiting {e.seconds} seconds..."
        )
        await asyncio.sleep(e.seconds)
        # Retry the operation after waiting
        return await fetch_group_messages(client, group, last_id)
    except Exception as e:
        print(f"     ❌ Error fetching group '{group.title}': {e}")

    print(f"     - Fetched {len(messages_data)} new messages.")
    return messages_data, new_last_id


def save_raw_telegram_data(
    messages, force_save=False, full_history=False, output_path=None
):
    """Save raw Telegram messages to group-specific daily files grouped by message date.

    Args:
        messages: List of messages to save
        force_save: If True, save empty file with metadata even when no messages
        full_history: If True, save to full_history.json instead of dated file
        output_path: Optional custom output file path
    """
    if full_history:
        date_str = "full_history"

        if not messages and not force_save:
            print("⚠️ No messages to save")
            return

        # Handle empty messages case - save metadata file
        if not messages and force_save:
            print("📁 No messages found - saving empty file with metadata")

            # Create main telegram directory
            sources_dir = Path("sources/telegram")
            sources_dir.mkdir(parents=True, exist_ok=True)

            # Set processing mode based on full_history flag
            processing_mode = "full_history"

            # Save empty file with metadata
            empty_data_with_metadata = {
                "date": date_str,
                "generated_at": datetime.now().isoformat(),
                "source": "telegram",
                "status": "no_new_content",
                "messages": [],
                "metadata": {
                    "groups_processed": 0,
                    "total_messages_fetched": 0,
                    "credential_status": "placeholder_values",
                    "processing_mode": processing_mode,
                },
            }

            if output_path:
                # Use custom output path if provided
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                # Default behavior
                output_file = sources_dir / f"{date_str}.json"

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(empty_data_with_metadata, f, indent=2, ensure_ascii=False)

            print(f"📁 Saved empty data file to: {output_file}")
            return [output_file]

        # Group messages by group name
        messages_by_group = {}
        for message in messages:
            group_name = message.get("group", "unknown_group")
            if group_name not in messages_by_group:
                messages_by_group[group_name] = []
            messages_by_group[group_name].append(message)

        saved_files = []

        if output_path:
            # When custom output is specified, save all messages to a single file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Combine all messages with metadata
            all_messages = []
            for group_name, group_messages in messages_by_group.items():
                # Add group info to each message if not already present
                for msg in group_messages:
                    if "group" not in msg:
                        msg["group"] = group_name
                    all_messages.extend(group_messages)

            # Create output structure similar to other ingest scripts
            output_data = {
                "date": date_str,
                "generated_at": datetime.now().isoformat(),
                "source": "telegram",
                "status": "success",
                "messages": all_messages,
                "metadata": {
                    "groups_processed": len(messages_by_group),
                    "total_messages_fetched": len(all_messages),
                    "credential_status": (
                        "configured" if API_ID and API_HASH else "missing"
                    ),
                    "processing_mode": "full_history",
                },
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            print(f"✅ Saved {len(all_messages)} messages to: {output_file}")
            saved_files.append(output_file)
        else:
            # Default behavior - save to group-specific directories
            for group_name, group_messages in messages_by_group.items():
                # Create group-specific directory
                group_dir = Path("sources/telegram") / group_name
                group_dir.mkdir(parents=True, exist_ok=True)

                # Save file in group directory
                group_file = group_dir / f"{date_str}.json"

                with open(group_file, "w", encoding="utf-8") as f:
                    json.dump(group_messages, f, indent=2, ensure_ascii=False)

                print(
                    f"✅ Saved {len(group_messages)} messages from {group_name} "
                    f"to: {group_file}"
                )
                saved_files.append(group_file)

        return saved_files
    else:
        if not messages and not force_save:
            print("⚠️ No messages to save")
            return

        # Handle empty messages case - save metadata file
        if not messages and force_save:
            print("📁 No messages found - saving empty file with metadata")

            # Create main telegram directory
            sources_dir = Path("sources/telegram")
            sources_dir.mkdir(parents=True, exist_ok=True)

            # Set processing mode
            processing_mode = "daily_sync"

            # Save empty file with metadata
            empty_data_with_metadata = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "generated_at": datetime.now().isoformat(),
                "source": "telegram",
                "status": "no_new_content",
                "messages": [],
                "metadata": {
                    "groups_processed": 0,
                    "total_messages_fetched": 0,
                    "credential_status": "placeholder_values",
                    "processing_mode": processing_mode,
                },
            }

            output_path = sources_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(empty_data_with_metadata, f, indent=2, ensure_ascii=False)

            print(f"📁 Saved empty data file to: {output_path}")
            return [output_path]

        # Group messages by group name and date
        messages_by_group_and_date = {}
        messages_with_unknown_date = {}

        for message in messages:
            group_name = message.get("group", "unknown_group")
            message_date = message.get("date")

            if message_date:
                try:
                    # Parse the ISO timestamp and extract date
                    parsed_date = datetime.fromisoformat(
                        message_date.replace("Z", "+00:00")
                    )
                    date_str = parsed_date.strftime("%Y-%m-%d")

                    if group_name not in messages_by_group_and_date:
                        messages_by_group_and_date[group_name] = {}
                    if date_str not in messages_by_group_and_date[group_name]:
                        messages_by_group_and_date[group_name][date_str] = []

                    messages_by_group_and_date[group_name][date_str].append(message)
                except (ValueError, TypeError):
                    # If date parsing fails, use today's date
                    if group_name not in messages_with_unknown_date:
                        messages_with_unknown_date[group_name] = []
                    messages_with_unknown_date[group_name].append(message)
            else:
                if group_name not in messages_with_unknown_date:
                    messages_with_unknown_date[group_name] = []
                messages_with_unknown_date[group_name].append(message)

        # Handle messages with unknown dates - save them to today's file
        if messages_with_unknown_date:
            today_date = datetime.now().strftime("%Y-%m-%d")
            for group_name, unknown_messages in messages_with_unknown_date.items():
                if group_name not in messages_by_group_and_date:
                    messages_by_group_and_date[group_name] = {}
                if today_date not in messages_by_group_and_date[group_name]:
                    messages_by_group_and_date[group_name][today_date] = []
                messages_by_group_and_date[group_name][today_date].extend(
                    unknown_messages
                )

        saved_files = []
        total_messages = 0

        for group_name, date_data in messages_by_group_and_date.items():
            # Create group-specific directory
            group_dir = Path("sources/telegram") / group_name
            group_dir.mkdir(parents=True, exist_ok=True)

            for date_str, date_messages in date_data.items():
                # Save file in group directory
                output_path = group_dir / f"{date_str}.json"

                # Load existing data if file exists
                existing_messages = []
                if output_path.exists():
                    try:
                        with open(output_path, "r", encoding="utf-8") as f:
                            existing_messages = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        existing_messages = []

                # Combine with new messages, avoiding duplicates based on message_id
                existing_message_ids = {
                    msg.get("message_id") for msg in existing_messages
                }
                new_messages = [
                    msg
                    for msg in date_messages
                    if msg.get("message_id") not in existing_message_ids
                ]

                # Merge all messages
                all_messages = existing_messages + new_messages

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(all_messages, f, indent=2, ensure_ascii=False)

                if new_messages:
                    print(
                        f"✅ Saved {len(new_messages)} new messages from {group_name} "
                        f"to: {output_path} (total: {len(all_messages)})"
                    )
                else:
                    print(
                        f"📄 No new messages for {group_name} on {date_str} "
                        f"(existing: {len(all_messages)})"
                    )

                saved_files.append(output_path)
                total_messages += len(new_messages)

        print(
            f"📊 Total new messages saved: {total_messages} "
            f"across {len(saved_files)} files"
        )
        return saved_files


async def main():
    """Main async function to run Telegram message ingestion."""
    import sys

    parser = argparse.ArgumentParser(description="Fetch messages from Telegram groups.")
    parser.add_argument(
        "--full-history",
        action="store_true",
        help="Force a full history backfill for all enabled groups.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force processing even if no new messages found " "(bypass deduplication)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Custom output file path (optional). Uses default location if not set",
    )
    args = parser.parse_args()

    print("🔄 Starting Telegram message ingestion...")
    messages = await fetch_messages(full_history=args.full_history)

    if messages is None:  # This means we skipped due to missing credentials/config
        # Still save empty file with metadata for consistency
        save_raw_telegram_data(
            [], force_save=True, full_history=args.full_history, output_path=args.output
        )
        print("\n🎉 Telegram ingestion complete!")
        sys.exit(2)  # Exit code 2 indicates "no new content" like Medium
    elif messages:
        # Filter out existing messages (unless force flag is used)
        if not args.force:
            existing_messages = get_existing_telegram_messages()
            filtered_messages = filter_new_telegram_messages(
                messages, existing_messages
            )

            if len(filtered_messages) == 0 and len(messages) > 0:
                print("\n🎯 Smart deduplication result:")
                print(f"   - Total messages fetched: {len(messages)}")
                print("   - New messages (not in database): 0")
                print(
                    "\n✨ No new telegram messages found - "
                    "saving empty file with metadata!"
                )
                print("ℹ️  Use --force flag to bypass deduplication if needed.")

                # Save empty file with metadata for consistency
                save_raw_telegram_data(
                    [],
                    force_save=True,
                    full_history=args.full_history,
                    output_path=args.output,
                )
                print("\n🎉 Telegram ingestion complete!")
                sys.exit(2)  # Exit code 2 indicates "no new content"

            final_messages = filtered_messages
        else:
            print("⚠️  Force flag used - bypassing deduplication checks")
            final_messages = messages

        save_raw_telegram_data(
            final_messages, full_history=args.full_history, output_path=args.output
        )

        if not args.force and len(messages) > len(final_messages):
            print(
                f"📊 Duplicate messages filtered: {len(messages) - len(final_messages)}"
            )
        print(f"📊 New messages saved: {len(final_messages)}")

        print("\n🎉 Telegram ingestion complete!")
        sys.exit(0)  # Success with new content
    else:
        # No messages found, but save empty file with metadata
        save_raw_telegram_data(
            [], force_save=True, full_history=args.full_history, output_path=args.output
        )
        print("\n🎉 Telegram ingestion complete!")
        sys.exit(2)  # No messages found, exit code 2 for "no new content"


if __name__ == "__main__":
    asyncio.run(main())
