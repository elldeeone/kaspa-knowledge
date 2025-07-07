# Configuration Guide

## Overview

The Kaspa Knowledge Hub uses multiple configuration methods to provide flexibility and security:

- **Environment Variables**: API keys and sensitive data (`.env` file)
- **Config Files**: Source settings and high-signal contributors (`config/sources.config.json`)
- **AI Models**: Powered by OpenRouter for multi-model LLM access

## Environment Variables

Create a `.env` file in the project root with the following configuration:

### Required

```bash
# OpenRouter API access (provides access to all LLM providers)
OPENROUTER_API_KEY=your_openrouter_api_key
```

### Optional - Data Sources

```bash
# Medium RSS feeds (comma-separated)
MEDIUM_RSS_URLS=https://hashdag.medium.com/feed,https://kaspadev.medium.com/feed

# GitHub Personal Access Token
GITHUB_TOKEN=your_github_token

# Discourse forum access
DISCOURSE_API_USERNAME=your_username
DISCOURSE_API_KEY=your_api_key

# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token
```

### Optional - System Settings

```bash
# Logging level
LOG_LEVEL=INFO

# Rate limiting (requests per minute)
RATE_LIMIT=60

# Processing delays (seconds)
PROCESSING_DELAY=1
```

## Configuration Files

### Sources Configuration

The main configuration file is `config/sources.config.json`:

```json
{
  "github": {
    "repositories": [
      {
        "owner": "kaspanet",
        "repo": "rusty-kaspa",
        "enabled": true
      },
      {
        "owner": "kaspanet",
        "repo": "kaspad",
        "enabled": true
      }
    ]
  },
  "discourse": {
    "forums": [
      {
        "name": "kaspa_research",
        "url": "https://research.kas.pa",
        "enabled": true
      }
    ]
  },
  "high_signal_contributors": [
    {
      "name": "Michael Sutton",
      "aliases": ["msutton", "Michael Sutton"],
      "role": "core_developer",
      "is_lead": true
    },
    {
      "name": "Yonatan Sompolinsky",
      "aliases": ["hashdag", "Yonatan Sompolinsky"],
      "role": "founder_researcher"
    }
  ]
}
```

## AI Model Configuration

### LLM Integration via OpenRouter

All AI processing is handled through OpenRouter, which provides access to multiple LLM providers:

**Available Models:**
- **OpenAI**: GPT-3.5, GPT-4, GPT-4-turbo, GPT-4o
- **Anthropic**: Claude-3-haiku, Claude-3-sonnet, Claude-3-opus
- **Google**: Gemini Pro, Gemini Flash
- **Mistral**: Various models
- **Meta**: Llama models
- **And many other providers**

**Model Selection:**
The default model is `openai/gpt-4.1`, but you can specify any model available through OpenRouter in the LLM interface.

### Custom Model Configuration

You can override the default model by setting environment variables:

```bash
# Override default model for all AI operations
DEFAULT_MODEL=anthropic/claude-3-sonnet

# Specific models for different operations
BRIEFING_MODEL=openai/gpt-4
FACTS_MODEL=anthropic/claude-3-haiku
SUMMARY_MODEL=google/gemini-pro
```

## Data Source Configuration

### Medium RSS Feeds

Configure multiple Medium author RSS feeds:

```bash
# Multiple feeds (comma-separated)
MEDIUM_RSS_URLS=https://hashdag.medium.com/feed,https://kaspadev.medium.com/feed,https://medium.com/feed/@kaspa_currency
```

**Getting RSS Feed URLs:**
To get any Medium author's RSS feed URL, add `/feed` to their profile URL:
- Profile: `https://author-name.medium.com/`
- RSS Feed: `https://author-name.medium.com/feed`

### GitHub Repositories

Configure repositories in `config/sources.config.json`:

```json
{
  "github": {
    "repositories": [
      {
        "owner": "kaspanet",
        "repo": "rusty-kaspa",
        "enabled": true,
        "priority": "high"
      },
      {
        "owner": "kaspanet",
        "repo": "kaspad",
        "enabled": true,
        "priority": "medium"
      },
      {
        "owner": "kaspanet",
        "repo": "kaspa-wallet",
        "enabled": false
      }
    ],
    "rate_limit": 5000,
    "days_back": 7
  }
}
```

**Options:**
- `enabled`: Whether to process this repository
- `priority`: Processing priority (high, medium, low)
- `rate_limit`: API rate limit for this source
- `days_back`: How many days of history to fetch

### Discourse Forums

Configure forum access in `config/sources.config.json`:

```json
{
  "discourse": {
    "forums": [
      {
        "name": "kaspa_research",
        "url": "https://research.kas.pa",
        "enabled": true,
        "categories": ["development", "research"],
        "min_posts": 5
      }
    ],
    "rate_limit": 100,
    "max_posts_per_run": 1000
  }
}
```

**Authentication for Private Forums:**
```bash
DISCOURSE_API_USERNAME=your_username
DISCOURSE_API_KEY=your_api_key
```

### Telegram Configuration

```json
{
  "telegram": {
    "channels": [
      {
        "name": "kaspa_official",
        "id": "@kaspa_currency",
        "enabled": true
      },
      {
        "name": "kaspa_dev",
        "id": "@kaspa_dev",
        "enabled": true
      }
    ],
    "max_messages_per_run": 1000
  }
}
```

**Telegram API Setup:**
```bash
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token  # Alternative method
```

## High-Signal Contributors

Configure high-signal contributors for prioritization:

```json
{
  "high_signal_contributors": [
    {
      "name": "Michael Sutton",
      "aliases": ["msutton", "Michael Sutton", "sutton"],
      "role": "core_developer",
      "is_lead": true,
      "weight": 100
    },
    {
      "name": "Yonatan Sompolinsky",
      "aliases": ["hashdag", "Yonatan Sompolinsky", "yonatan"],
      "role": "founder_researcher",
      "weight": 95
    },
    {
      "name": "Ori Newman",
      "aliases": ["someone235", "Ori Newman"],
      "role": "core_developer",
      "weight": 90
    }
  ]
}
```

**Fields:**
- `name`: Full name of the contributor
- `aliases`: List of usernames/aliases used across platforms
- `role`: Role type (core_developer, founder_researcher, researcher, maintainer)
- `is_lead`: Boolean indicating lead developer status
- `weight`: Signal strength weight (0-100)

## AI Prompt Configuration

### Externalized Prompts

All AI prompts are stored in `scripts/prompts/` for easy modification:

```
scripts/prompts/
├── extract_kaspa_facts.txt                 # Main facts extraction prompt
├── extract_kaspa_facts_system.txt          # System prompt for facts extraction
├── generate_article_summary.txt            # Article summarization prompt
├── generate_article_summary_system.txt     # System prompt for article summaries
├── generate_daily_briefing.txt             # Daily briefing generation prompt
├── generate_daily_briefing_system.txt      # System prompt for briefings
├── summarize_github_activity.txt           # GitHub activity summarization prompt
└── summarize_github_activity_system.txt    # System prompt for GitHub summaries
```

### Custom Prompts

You can create custom prompt configurations:

```json
{
  "prompts": {
    "facts_extraction": {
      "system_prompt": "path/to/custom_facts_system.txt",
      "user_prompt": "path/to/custom_facts.txt",
      "model": "anthropic/claude-3-sonnet"
    },
    "briefing_generation": {
      "system_prompt": "path/to/custom_briefing_system.txt",
      "user_prompt": "path/to/custom_briefing.txt",
      "model": "openai/gpt-4"
    }
  }
}
```

## Processing Configuration

### Pipeline Settings

Configure pipeline behavior in `config/pipeline.config.json`:

```json
{
  "processing": {
    "max_parallel_sources": 3,
    "timeout_minutes": 30,
    "retry_attempts": 3,
    "backoff_factor": 2
  },
  "deduplication": {
    "enabled": true,
    "similarity_threshold": 0.85,
    "time_window_hours": 24
  },
  "outputs": {
    "keep_raw_data": true,
    "compress_old_files": true,
    "retention_days": 365
  }
}
```

### Rate Limiting

Configure rate limiting for different sources:

```json
{
  "rate_limits": {
    "github": {
      "requests_per_hour": 5000,
      "burst_limit": 100
    },
    "medium": {
      "requests_per_minute": 60,
      "delay_between_requests": 1
    },
    "discourse": {
      "requests_per_minute": 100,
      "pages_per_request": 50
    },
    "openrouter": {
      "requests_per_minute": 20,
      "tokens_per_minute": 100000
    }
  }
}
```

## GitHub Actions Configuration

For automated execution, configure these secrets in your GitHub repository:

### Required Secrets

```
OPENROUTER_API_KEY=your_openrouter_api_key
```

### Optional Secrets

```
GH_TOKEN=your_github_token
DISCOURSE_API_USERNAME=your_discourse_username
DISCOURSE_API_KEY=your_discourse_api_key
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
MEDIUM_RSS_URLS=comma,separated,rss,urls
SOURCES_CONFIG=json_string_of_sources_config
```

### Workflow Configuration

Customize the GitHub Actions workflow in `.github/workflows/daily-pipeline.yml`:

```yaml
name: Daily Knowledge Pipeline
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  workflow_dispatch:     # Allow manual triggering

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run pipeline
        run: python scripts/run_pipeline.py
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          # Add other secrets as needed
```

## Validation and Testing

### Configuration Validation

The system includes built-in configuration validation:

```bash
# Validate configuration files
python scripts/validate_config.py

# Test specific configurations
python scripts/validate_config.py --config config/sources.config.json

# Validate environment variables
python scripts/validate_config.py --env
```

### Testing Configuration Changes

```bash
# Test with new configuration
python scripts/run_pipeline.py --config config/test.config.json --dry-run

# Validate specific source configurations
python -m scripts.github_ingest --test --config config/sources.config.json
python -m scripts.medium_ingest --test
```

## Advanced Configuration

### Custom Data Processing

```json
{
  "processing_rules": {
    "github": {
      "exclude_bots": true,
      "min_commit_size": 10,
      "exclude_patterns": ["docs/", "test/"]
    },
    "medium": {
      "min_word_count": 100,
      "exclude_tags": ["sponsored", "advertisement"]
    },
    "facts": {
      "min_impact_level": "medium",
      "exclude_categories": ["social", "marketing"]
    }
  }
}
```

### Output Customization

```json
{
  "outputs": {
    "briefing": {
      "max_length": 2000,
      "include_metrics": true,
      "format": "markdown"
    },
    "facts": {
      "group_by_category": true,
      "include_source_links": true,
      "max_facts_per_category": 10
    },
    "rag_documents": {
      "chunk_size": 500,
      "overlap": 50,
      "include_metadata": true
    }
  }
}
```

## Troubleshooting Configuration

### Common Issues

1. **Invalid JSON**: Validate syntax with online JSON validators
2. **Missing API Keys**: Check `.env` file exists and has correct keys
3. **Permission Errors**: Ensure GitHub token has repository access
4. **Rate Limit Issues**: Adjust rate limiting settings

### Debug Configuration

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Validate configuration
python scripts/validate_config.py --verbose

# Test individual components
python -m scripts.github_ingest --test --verbose
```

### Configuration Examples

See the `config/examples/` directory for complete configuration examples:

- `config/examples/minimal.config.json` - Minimal setup
- `config/examples/full.config.json` - Complete configuration
- `config/examples/high-volume.config.json` - High-volume processing setup 