# Telegram Configuration Guide

This document explains how to configure Telegram integration for the Kaspa Knowledge Hub.

## Configuration Files

### 1. config/sources.config.json

The main configuration file that defines which Telegram groups/channels to monitor:

```json
{
  "telegram_groups": [
    {
      "username": "KaspaCoreRD",
      "has_topics": true,
      "backfill_on_first_run": true,
      "enabled": true
    }
  ]
}
```

#### Field Descriptions:

- **username**: The public @username of the group/channel (without the @ symbol)
- **has_topics**: `true` if it's a group with the "Topics" feature enabled, `false` for regular groups or channels
- **backfill_on_first_run**: `true` to fetch all historical messages the first time this group is processed, `false` to only start from the current date
- **enabled**: `true` to include this group in the daily sync, `false` to temporarily disable it

### 2. Environment Variables (.env)

Required API credentials that must be obtained from https://my.telegram.org:

```bash
# Telegram API Configuration (get from my.telegram.org)
TELEGRAM_API_ID="your_telegram_api_id_here"           # Required: Numeric API ID
TELEGRAM_API_HASH="your_telegram_api_hash_here"       # Required: API hash string
TELEGRAM_SESSION_NAME="kaspa_knowledge_hub"           # Optional: Session name
```

## Getting API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application if you haven't already
5. Copy the `api_id` and `api_hash` values
6. Update your `.env` file with these values

## Usage Examples

### Basic Group (No Topics)
```json
{
  "username": "kaspa_community",
  "has_topics": false,
  "backfill_on_first_run": false,
  "enabled": true
}
```

### Group with Topics (Forum-style)
```json
{
  "username": "KaspaCoreRD", 
  "has_topics": true,
  "backfill_on_first_run": true,
  "enabled": true
}
```

### Temporarily Disabled Group
```json
{
  "username": "test_channel",
  "has_topics": false,
  "backfill_on_first_run": false,
  "enabled": false
}
```

## Data Output

Messages are saved to group-specific daily files with the following directory structure:

```
sources/telegram/
├── state.json                 # Tracks last processed message IDs for all groups
├── KaspaCoreRD/
│   ├── 2025-07-01.json       # Daily messages from KaspaCoreRD group
│   ├── 2025-07-02.json
│   └── ...
├── AnotherKaspaGroup/
│   ├── 2025-07-01.json       # Daily messages from AnotherKaspaGroup
│   └── ...
└── SomeOtherChannel/
    └── ...
```

Each message has the following JSON structure:

```json
{
  "message_id": 12345,
  "topic_id": 67890,
  "topic_title": "Development Discussion",
  "text": "Message content here...",
  "date": "2025-07-01T10:30:00Z",
  "sender_username": "developer_user",
  "group": "KaspaCoreRD"
}
```

## State Management

The integration maintains state in `sources/telegram/state.json` to track the last processed message ID for each group and topic, ensuring no duplicates and enabling incremental syncing. 