# Setup Guide

## Prerequisites

- Python 3.8+
- Git
- GitHub repository with Actions enabled
- OpenRouter API key (provides access to OpenAI, Anthropic, Google, Mistral, and other LLM providers)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/kaspa-knowledge.git
cd kaspa-knowledge
```

### 2. Create and activate virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your OpenRouter API key and configuration
```

### 5. Set up GitHub Actions secrets (for automation)

See the [GitHub Actions Setup](#github-actions-setup) section below for required secrets.

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following:

```bash
# OpenRouter API access (provides access to all LLM providers)
OPENROUTER_API_KEY=your_openrouter_api_key

# Medium RSS feeds (comma-separated)
MEDIUM_RSS_URLS=https://hashdag.medium.com/feed,https://kaspadev.medium.com/feed

# GitHub Personal Access Token (optional, for private repos)
GITHUB_TOKEN=your_github_token

# Discourse forum access (optional)
DISCOURSE_API_USERNAME=your_username
DISCOURSE_API_KEY=your_api_key

# Telegram API (optional)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token
```

### Configuration Files

#### Medium RSS Configuration

The system supports multiple Medium author RSS feeds. To get any Medium author's RSS feed URL, simply add `/feed` to their profile URL:

- Profile: `https://author-name.medium.com/`
- RSS Feed: `https://author-name.medium.com/feed`

#### GitHub Repository Configuration

Configure GitHub repositories in `config/sources.config.json`:

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
  }
}
```

#### Discourse Forum Configuration

Configure access to Discourse forums in `config/sources.config.json`:

```json
{
  "discourse": {
    "forums": [
      {
        "name": "kaspa_research",
        "url": "https://research.kas.pa",
        "enabled": true
      }
    ]
  }
}
```

## GitHub Actions Setup

For the automated daily pipeline to work correctly, configure these repository secrets:

### Required Secrets

- `OPENROUTER_API_KEY` - OpenRouter API key (provides access to OpenAI, Anthropic, Google, Mistral, and other LLM providers)

### Optional Secrets (enable specific features)

- `GH_TOKEN` - GitHub Personal Access Token for repository data access
- `DISCOURSE_API_USERNAME` - Discourse forum username for private forum access
- `DISCOURSE_API_KEY` - Discourse API key for authenticated forum access
- `TELEGRAM_API_ID` - Telegram API ID for message ingestion
- `TELEGRAM_API_HASH` - Telegram API hash for message ingestion
- `TELEGRAM_BOT_TOKEN` - Telegram bot token (alternative auth method)
- `MEDIUM_RSS_URLS` - Medium RSS feed URLs (comma-separated)

### Configuration Sources

- `SOURCES_CONFIG` - JSON configuration for sources (optional, uses defaults if not provided)

**To add secrets**: Go to your repository → Settings → Secrets and variables → Actions → New repository secret

**Note**: The pipeline gracefully handles missing optional credentials by skipping those data sources while continuing to process available sources.

## Development Setup

### Code Quality Tools

```bash
# Install development dependencies
pip install black flake8

# Set up pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Testing

```bash
# Run the complete pipeline in test mode
python -m scripts.run_pipeline

# Test individual components
python -m scripts.medium_ingest --test
python -m scripts.github_ingest --test
```

## Troubleshooting

### Common Issues

1. **Missing API Keys**: Ensure all required API keys are set in your `.env` file
2. **Permission Errors**: Check that your GitHub token has appropriate permissions
3. **Rate Limiting**: The system includes built-in rate limiting, but you may need to adjust timing for your use case
4. **Memory Issues**: For large datasets, consider running individual pipeline stages separately

### Getting Help

- Check the [FAQ](FAQ.md) for common questions
- Review the [GitHub Integration Testing](GITHUB_INTEGRATION_TESTING.md) guide
- Open an issue on GitHub for specific problems

## Next Steps

After setup, check out:

- [Usage Guide](USAGE.md) for command reference
- [Architecture](ARCHITECTURE.md) to understand system design
- [Configuration Guide](CONFIGURATION.md) for advanced configuration options 