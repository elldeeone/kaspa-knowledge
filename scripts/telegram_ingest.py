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


def save_raw_telegram_data(messages):
    """Save raw Telegram messages to group-specific daily files."""
    if not messages:
        print("⚠️ No messages to save")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")

    # Group messages by group name
    messages_by_group = {}
    for message in messages:
        group_name = message.get("group", "unknown_group")
        if group_name not in messages_by_group:
            messages_by_group[group_name] = []
        messages_by_group[group_name].append(message)

    saved_files = []
    for group_name, group_messages in messages_by_group.items():
        # Create group-specific directory
        group_dir = Path("sources/telegram") / group_name
        group_dir.mkdir(parents=True, exist_ok=True)

        # Save daily file in group directory
        output_path = group_dir / f"{date_str}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(group_messages, f, indent=2, ensure_ascii=False)

        print(
            f"✅ Saved {len(group_messages)} messages from {group_name} "
            f"to: {output_path}"
        )
        saved_files.append(output_path)

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
    args = parser.parse_args()

    print("🔄 Starting Telegram message ingestion...")
    messages = await fetch_messages(full_history=args.full_history)

    if messages is None:  # This means we skipped due to missing credentials/config
        print("\n🎉 Telegram ingestion complete!")
        sys.exit(2)  # Exit code 2 indicates "no new content" like Medium
    elif messages:
        save_raw_telegram_data(messages)
        print("\n🎉 Telegram ingestion complete!")
        sys.exit(0)  # Success with new content
    else:
        print("\n🎉 Telegram ingestion complete!")
        sys.exit(2)  # No messages found, exit code 2 for "no new content"


if __name__ == "__main__":
    asyncio.run(main())
