# Kaspa Knowledge Hub

An automated knowledge aggregation and processing system for the Kaspa cryptocurrency ecosystem. This project creates a comprehensive, daily-updated knowledge corpus by ingesting, processing, and synthesizing information from multiple sources across the Kaspa community.

## Purpose

The Kaspa Knowledge Hub serves as a centralized intelligence system that:

- **Aggregates Information**: Automatically collects data from key Kaspa sources including developer blogs, GitHub repositories, Discourse research forums, Telegram channels, and news sources
- **Processes with AI**: Uses advanced language models to extract key facts, generate insights, and create structured summaries
- **Delivers Daily Briefings**: Produces concise, narrative-style briefings highlighting important developments and trends
- **Enables RAG Integration**: Optimizes all outputs for ingestion into vector databases and Retrieval-Augmented Generation (RAG) systems
- **Smart Deduplication**: Intelligent content filtering prevents duplicate processing and reduces resource consumption

## Architecture

The system operates with clean separation between raw data ingestion, aggregation, and AI processing:

```
kaspa-knowledge/
├── sources/                  # Raw data ingestion (no AI processing)
│   ├── medium/               # Raw Medium RSS article data
│   ├── github/               # Raw GitHub activity data
│   ├── github_summaries/     # AI-processed GitHub summaries
│   ├── telegram/             # Raw Telegram messages
│   ├── forum/                # Raw Discourse forum posts
│   ├── discord/              # Raw Discord messages (future)
│   └── news/                 # Raw news articles (future)
├── data/                     # Processed data outputs
│   ├── aggregated/           # Raw combined daily data (no AI)
│   ├── briefings/            # AI-generated executive briefings
│   └── facts/                # AI-extracted technical facts
├── scripts/                  # Pipeline processing scripts
│   ├── medium_ingest.py      # Multi-feed Medium RSS ingestion
│   ├── github_ingest.py      # GitHub repository activity ingestion
│   ├── discourse_ingest.py   # Discourse forum post ingestion
│   ├── telegram_ingest.py    # Telegram message ingestion
│   ├── summarize_github.py   # AI-powered GitHub activity summarization
│   ├── aggregate_sources.py  # Raw data aggregation
│   ├── generate_briefing.py  # AI briefing generation
│   ├── extract_facts.py      # AI fact extraction with deduplication
│   ├── run_pipeline.py       # Complete pipeline runner
│   └── llm_interface.py      # OpenRouter LLM integration
├── docs/                     # Static documentation
├── config/                   # Configuration files
├── .taskmaster/              # Taskmaster project management
├── .github/workflows/        # GitHub Actions automation
└── README.md
```

### Four-Stage Pipeline Process

**Stage 1: Raw Data Ingestion**
- Collects pure, unprocessed data from various sources
- Saves to `sources/` directory with date-stamped files
- Smart deduplication prevents processing duplicate content
- No AI processing or transformation

**Stage 1.5: Data Pre-Processing**
- GitHub Activity Summarization: AI-powered summaries of repository activity
- Processes GitHub data into human-readable summaries

**Stage 2: Raw Data Aggregation**  
- Combines all sources into daily aggregated files
- Creates single source of truth in `data/aggregated/daily.json`
- Still no AI processing - pure data combination

**Stage 3: AI Processing**
- Reads from raw aggregated data
- Generates separate outputs for different use cases:
  - **Briefings**: Executive summaries and high-level insights
  - **Facts**: Structured technical facts with categories and impact levels
- Smart deduplication avoids reprocessing existing content

### Data Sources

- **Medium RSS Feeds**: Multiple author feeds for comprehensive coverage of developer blogs and articles
- **GitHub Repositories**: Commits, pull requests, issues from key Kaspa repos with AI summarization
- **Discourse Forums**: Research discussions from https://research.kas.pa/ with incremental updates
- **Telegram Channels**: Community conversations and announcements (optional)
- **Discord Channels**: High-signal conversations from development channels (future)
- **News Sources**: Industry news and announcements (future)

### Externalized Prompt System

The system uses clean separation between application logic and AI prompts:

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

**Benefits:**
- **Maintainability**: Prompts can be modified without touching code
- **Flexibility**: Easy experimentation with different prompt strategies
- **Version Control**: Track prompt changes independently from code changes
- **Collaboration**: Non-technical users can contribute to prompt optimization

## Features

- **Clean Pipeline Architecture**: Separation between raw data and AI processing
- **Smart Deduplication**: Intelligent content filtering across all components
- **Automated Daily Workflow**: Fully automated via GitHub Actions  
- **Multi-Source Integration**: Comprehensive coverage of the Kaspa ecosystem
- **Multi-Model AI**: Access to OpenAI, Anthropic, Google, Mistral, and other models via OpenRouter
- **Incremental Processing**: Only processes new content, avoiding redundant operations
- **Modular Design**: Each pipeline stage can be run independently
- **Quality Controls**: Built-in validation and error handling
- **Rate Limiting**: Respectful API usage with comprehensive rate limiting
- **Code Quality**: Integrated black and flake8 formatting with CI validation
- **RAG Optimization**: All outputs optimized for vector database ingestion

## Tech Stack

- **Python**: Core data processing and AI integration
- **GitHub Actions**: Automation and orchestration with comprehensive CI/CD
- **OpenRouter API**: Unified access to multiple LLM providers (OpenAI, Anthropic, Google, Mistral, etc.)
- **Feedparser**: RSS feed processing
- **Requests**: HTTP client for API interactions
- **JSON**: Structured data storage and exchange
- **Black & Flake8**: Code formatting and quality assurance

## Prerequisites

- Python 3.8+
- Git
- GitHub repository with Actions enabled
- OpenRouter API key (provides access to OpenAI, Anthropic, Google, Mistral, and other LLM providers)

## Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/kaspa-knowledge.git
   cd kaspa-knowledge
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenRouter API key and configuration
   ```

5. **Set up GitHub Actions secrets** (for automation):
   See the GitHub Actions Setup section below for required secrets.

## Configuration

Configuration is managed through:

- **Environment variables** (`.env` file): OpenRouter API key and source URLs
- **Config files** (`config/sources.config.json`): Source-specific settings
- **Script parameters**: Configurable within individual processing scripts  
- **Pipeline settings**: Located in `scripts/run_pipeline.py`

### LLM Integration via OpenRouter

All AI processing is handled through OpenRouter, which provides access to multiple LLM providers:

**Available Models via OpenRouter:**
- OpenAI (GPT-3.5, GPT-4, GPT-4-turbo, GPT-4o)
- Anthropic (Claude-3-haiku, Claude-3-sonnet, Claude-3-opus)
- Google (Gemini Pro, Gemini Flash)
- Mistral (Various models)
- Meta (Llama models)
- And many other providers

**Configuration:**
```bash
# OpenRouter API access (provides access to all LLM providers)
OPENROUTER_API_KEY=your_openrouter_api_key

# Medium RSS feeds (comma-separated)
MEDIUM_RSS_URLS=https://hashdag.medium.com/feed,https://kaspadev.medium.com/feed
```

**Model Selection:**
The default model is `openai/gpt-4.1`, but you can specify any model available through OpenRouter in the LLM interface.

### Enhanced Medium RSS Configuration

The system supports multiple Medium author RSS feeds:

**Multiple RSS Feeds:**
```bash
MEDIUM_RSS_URLS=https://hashdag.medium.com/feed,https://kaspadev.medium.com/feed,https://medium.com/feed/@kaspa_currency
```

**Getting RSS Feed URLs:**
To get any Medium author's RSS feed URL, simply add `/feed` to their profile URL:
- Profile: `https://author-name.medium.com/` 
- RSS Feed: `https://author-name.medium.com/feed`

### Discourse Forum Configuration

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

**Optional Authentication:**
For private forums, set environment variables:
```bash
DISCOURSE_API_USERNAME=your_username
DISCOURSE_API_KEY=your_api_key
```

### GitHub Repository Configuration

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

## Usage

### Manual Execution

**Run the complete pipeline:**
```bash
python -m scripts.run_pipeline
```

**Run individual stages:**
```bash
# Stage 1: Ingest raw data
python -m scripts.medium_ingest
python -m scripts.github_ingest
python -m scripts.discourse_ingest
python -m scripts.telegram_ingest

# Stage 1.5: Pre-process data
python -m scripts.summarize_github

# Stage 2: Aggregate raw sources  
python -m scripts.aggregate_sources

# Stage 3: AI processing
python -m scripts.generate_briefing
python -m scripts.extract_facts
```

### Smart Deduplication

All components include intelligent deduplication:

**Automatic Deduplication:**
- Medium: Compares article URLs and publication dates
- GitHub: Tracks processed commits, PRs, and issues
- Forum: Incremental post fetching with state management
- Facts: Detects existing facts files to avoid reprocessing

**Force Processing:**
```bash
# Override deduplication for any component
python -m scripts.extract_facts --force
python -m scripts.medium_ingest --force
```

### Medium Ingestion Options

**Daily Sync (Default):**
```bash
python -m scripts.medium_ingest
```
- Fetches articles from configured RSS feeds
- Smart deduplication prevents duplicate processing
- Saves to `sources/medium/YYYY-MM-DD.json`

**Full History Backfill:**
```bash
python -m scripts.medium_ingest --full-history
```
- Fetches all available articles from RSS feeds
- Saves to `sources/medium/full_history.json`
- **Run only once** to establish historical baseline

**Manual URL Scraping:**
```bash
python -m scripts.medium_ingest --manual-urls https://hashdag.medium.com/article1 https://hashdag.medium.com/article2
```
- Bypasses RSS limitations
- Can scrape any accessible Medium article
- Automatically extracts title, author, content, and publication date

### GitHub Repository Processing

**Standard Processing:**
```bash
python -m scripts.github_ingest
```
- Fetches commits, PRs, and issues from configured repositories
- Includes rate limiting and smart pagination
- Saves raw data to `sources/github/YYYY-MM-DD.json`

**AI Summarization:**
```bash
python -m scripts.summarize_github
```
- Processes raw GitHub data into human-readable summaries
- Generates concise summaries for repositories with activity
- Saves to `sources/github_summaries/YYYY-MM-DD.md`

### Discourse Forum Processing

**Standard Processing:**
```bash
python -m scripts.discourse_ingest
```
- Incremental fetching of new posts only
- Maintains state to track processed content
- Smart pagination and rate limiting
- Saves to `sources/forum/YYYY-MM-DD.json`

### Automated Execution

The system runs automatically via GitHub Actions on a daily schedule. The workflow includes:
- Complete pipeline execution
- Code quality validation (black, flake8)
- Artifact generation and storage
- Error handling and notifications

## Output Structure

### Raw Aggregated Data (`data/aggregated/`)
- **Purpose**: Complete daily dataset combining all sources
- **Format**: JSON with metadata and source attribution
- **Use Case**: Source of truth for all downstream processing

### AI-Generated Briefings (`data/briefings/`)
- **Purpose**: Executive summaries and strategic insights
- **Format**: JSON with article summaries and overall briefing
- **Use Case**: High-level stakeholder updates

### Extracted Facts (`data/facts/`)
- **Purpose**: Structured technical facts and insights
- **Format**: JSON with categorized facts, impact levels, and source attribution
- **Use Case**: Knowledge base building, RAG applications
- **Features**: Smart deduplication prevents reprocessing existing facts

### GitHub Summaries (`sources/github_summaries/`)
- **Purpose**: Human-readable summaries of repository activity
- **Format**: Markdown with structured summaries per repository
- **Use Case**: Quick understanding of development progress

## AI Processing

The system uses advanced language models to:

- **Extract Key Facts**: Automatically identify and categorize important technical information
- **Generate Summaries**: Create concise, readable summaries of complex technical content  
- **Assess Impact**: Classify information by relevance and importance
- **Maintain Context**: Preserve source attribution and publication dates
- **Ensure Quality**: Validate and structure all extracted information
- **Avoid Duplication**: Smart processing prevents redundant AI operations

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

## Code Quality

The project maintains high code quality standards:

**Automated Formatting:**
```bash
# Format code with black
black scripts/

# Check code quality with flake8  
flake8 scripts/
```

**CI Integration:**
- GitHub Actions automatically validates code formatting
- All commits must pass black and flake8 checks
- Consistent code style across the entire project

## Development

**Setup Development Environment:**
```bash
# Install development dependencies
pip install black flake8

# Set up pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

**Testing:**
```bash
# Run the complete pipeline in test mode
python -m scripts.run_pipeline

# Test individual components
python -m scripts.medium_ingest --test
python -m scripts.github_ingest --test
```

## Documentation

### High-Signal Contributor Weighting System

The project includes a sophisticated **High-Signal Contributor Weighting System** that prioritizes contributions from core developers, founders, and researchers. This system ensures protocol-level insights are elevated while maintaining comprehensive coverage.

📖 **[Complete Documentation](docs/HIGH_SIGNAL_CONTRIBUTOR_SYSTEM.md)**

**Key Features:**
- **Smart Contributor Recognition**: Automatically identifies high-signal contributors by name/alias
- **Signal-Based Prioritization**: Sorts data to surface protocol-level insights first
- **AI Prompt Integration**: Instructs LLMs to prioritize high-authority sources
- **Comprehensive Analysis**: Provides detailed signal distribution metrics

**Quick Start:**
```json
// config/sources.config.json
{
  "high_signal_contributors": [
    {
      "name": "Michael Sutton",
      "aliases": ["msutton", "Michael Sutton"],
      "role": "core_developer",
      "is_lead": true
    }
  ]
}
```

### Additional Documentation

- **Pipeline Architecture**: See the Architecture section above
- **AI Prompt System**: Review the Externalized Prompt System section
- **Configuration Guide**: Check the Configuration section
- **Development Setup**: Follow the Setup & Installation section

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Ensure code quality (`black scripts/ && flake8 scripts/`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

**Code Standards:**
- Follow PEP 8 style guidelines
- Use black for code formatting
- Ensure flake8 validation passes
- Include appropriate documentation
- Add tests for new functionality