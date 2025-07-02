# Kaspa Knowledge Hub

An automated knowledge aggregation and processing system for the Kaspa cryptocurrency ecosystem. This project creates a comprehensive, daily-updated knowledge corpus by ingesting, processing, and synthesizing information from multiple sources across the Kaspa community.

## 🎯 Purpose

The Kaspa Knowledge Hub serves as a centralized intelligence system that:

- **Aggregates Information**: Automatically collects data from key Kaspa sources including developer blogs, GitHub repositories, Discord channels, research forums, and on-chain metrics
- **Processes with AI**: Uses advanced language models to extract key facts, generate insights, and create structured summaries
- **Delivers Daily Briefings**: Produces concise, narrative-style briefings highlighting important developments and trends
- **Enables RAG Integration**: Optimizes all outputs for ingestion into vector databases and Retrieval-Augmented Generation (RAG) systems

## 🏗️ Architecture

The system operates with clean a separation between raw data ingestion, aggregation, and AI processing:

```
kaspa-knowledge/
├── sources/                  # Raw data ingestion (no AI processing)
│   ├── medium/               # Raw Medium RSS article data
│   ├── github/               # Raw GitHub activity data
│   ├── discord/              # Raw Discord messages
│   ├── forum/                # Raw research forum posts
│   └── news/                 # Raw news articles
├── data/                     # Processed data outputs
│   ├── aggregated/           # Raw combined daily data (no AI)
│   ├── briefings/            # AI-generated executive briefings
│   └── facts/                # AI-extracted technical facts
├── scripts/                  # Pipeline processing scripts
│   ├── medium_ingest.py      # Multi-feed Medium RSS ingestion with full history support
│   ├── aggregate_sources.py  # Raw data aggregation
│   ├── generate_briefing.py  # AI briefing generation
│   ├── extract_facts.py      # AI fact extraction
│   ├── run_pipeline.py       # Complete pipeline runner
│   └── llm_interface.py      # LLM integration
├── docs/                     # Static documentation
├── .taskmaster/              # Taskmaster project management
├── .github/workflows/        # GitHub Actions automation
└── README.md
```

### 🔄 Three-Stage Pipeline Process

**Stage 1: Raw Data Ingestion**
- Collects pure, unprocessed data from various sources
- Saves to `sources/` directory with date-stamped files
- No AI processing or transformation

**Stage 2: Raw Data Aggregation**  
- Combines all sources into daily aggregated files
- Creates single source of truth in `data/aggregated/daily.json`
- Still no AI processing - pure data combination

**Stage 3: AI Processing**
- Reads from raw aggregated data
- Generates separate outputs for different use cases:
  - **Briefings**: Executive summaries and high-level insights
  - **Facts**: Structured technical facts with categories and impact levels

### Data Sources

- **Medium RSS Feeds**: Multiple author feeds for comprehensive coverage of developer blogs and articles
- **GitHub Repositories**: Commits, pull requests, issues from key Kaspa repos  
- **Discord Channels**: High-signal conversations from development channels
- **Research Forum**: Discussions from https://research.kas.pa/
- **On-Chain Data**: Daily network statistics (hashrate, BPS, transaction volume)
- **News Sources**: Industry news and announcements

### 🎯 Externalized Prompt System

The system uses a clean separation between application logic and AI prompts:

```
scripts/prompts/
├── extract_kaspa_facts.txt         # Main facts extraction prompt
├── extract_kaspa_facts_system.txt  # System prompt for facts extraction
├── generate_article_summary.txt    # Article summarization prompt
├── generate_article_summary_system.txt
├── generate_daily_briefing.txt     # Daily briefing generation prompt
└── generate_daily_briefing_system.txt
```

**Benefits:**
- **Maintainability**: Prompts can be modified without touching code
- **Flexibility**: Easy experimentation with different prompt strategies
- **Version Control**: Track prompt changes independently from code changes
- **Collaboration**: Non-technical users can contribute to prompt optimization

## 🚀 Features

- **Clean Pipeline Architecture**: Separation between raw data and AI processing
- **Automated Daily Workflow**: Fully automated via GitHub Actions  
- **Multi-Source Integration**: Comprehensive coverage of the Kaspa ecosystem
- **AI-Powered Analysis**: Advanced fact extraction and summarization
- **Modular Design**: Each pipeline stage can be run independently
- **Quality Controls**: Built-in validation and error handling
- **Rate Limiting**: Respectful API usage with comprehensive rate limiting
- **RAG Optimization**: All outputs optimized for vector database ingestion

## 🛠️ Tech Stack

- **Python**: Core data processing and AI integration
- **GitHub Actions**: Automation and orchestration  
- **OpenRouter API**: AI processing and analysis (supports OpenAI, Anthropic, and other models)
- **Feedparser**: RSS feed processing
- **JSON**: Structured data storage and exchange

## 📋 Prerequisites

- Python 3.8+
- Git
- GitHub repository with Actions enabled
- OpenRouter API key (supports OpenAI, Anthropic, and other models)

## ⚙️ Setup & Installation

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
   # Edit .env with your API keys:
   # OPENROUTER_API_KEY=your_openrouter_api_key
   # MEDIUM_RSS_URLS=https://hashdag.medium.com/feed,https://kaspadev.medium.com/feed
   ```

5. **Set up GitHub Actions secrets** (for automation):
   - `OPENROUTER_API_KEY`: For AI processing
   - Additional API keys as needed for data sources

## 🔧 Configuration

Configuration is managed through:

- **Environment variables** (`.env` file): OpenRouter API keys and RSS feed URLs
- **Script parameters**: Configurable within individual processing scripts  
- **Pipeline settings**: Located in `scripts/run_pipeline.py`

### Enhanced Medium RSS Configuration

The system supports multiple Medium author RSS feeds and full history backfill:

**Multiple RSS Feeds:**
```bash
# Configure multiple Medium authors (comma-separated)
MEDIUM_RSS_URLS=https://hashdag.medium.com/feed,https://kaspadev.medium.com/feed,https://medium.com/feed/@kaspa_currency
```

**Getting RSS Feed URLs:**
To get any Medium author's RSS feed URL, simply add `/feed` to their profile URL:
- Profile: `https://author-name.medium.com/` 
- RSS Feed: `https://author-name.medium.com/feed`

**Backward Compatibility:**
The system still supports the legacy single URL format (`MEDIUM_RSS_URL`) for existing configurations.

## 🏃‍♂️ Usage

### Manual Execution

**Run the complete pipeline:**
```bash
python -m scripts.run_pipeline
```

**Run individual stages:**
```bash
# Stage 1: Ingest raw data
python -m scripts.medium_ingest                    # Daily sync (saves to dated file)
python -m scripts.medium_ingest --full-history     # Full history backfill (saves to full_history.json)
python -m scripts.medium_ingest --manual-urls URL1 URL2  # Manual scraping (bypasses RSS limit)

# Stage 2: Aggregate raw sources  
python -m scripts.aggregate_sources

# Stage 3a: Generate briefings
python -m scripts.generate_briefing

# Stage 3b: Extract facts
python -m scripts.extract_facts
```

### Medium Ingestion Options

**Daily Sync (Default):**
```bash
python -m scripts.medium_ingest
```
- Fetches all articles available in RSS feeds (limited to 10 most recent per author by Medium)
- Saves to `sources/medium/YYYY-MM-DD.json`
- Used by daily automated pipeline

**Full History Backfill:**
```bash
python -m scripts.medium_ingest --full-history
```
- Fetches all articles available in RSS feeds (same 10-article limit applies)
- Saves to `sources/medium/full_history.json`
- **Run only once** to establish historical baseline  
- Intended for comprehensive backfill operations
- Processes multiple feeds simultaneously
- Automatically removes duplicates across feeds

**Manual URL Scraping (NEW):**
```bash
# Scrape specific articles that aren't in RSS feeds
python -m scripts.medium_ingest --manual-urls https://hashdag.medium.com/article1 https://hashdag.medium.com/article2

# Combine with RSS feeds for comprehensive collection
python -m scripts.medium_ingest --full-history --manual-urls https://hashdag.medium.com/old-article1 https://hashdag.medium.com/old-article2
```
- **Bypasses RSS limitation** - can scrape any accessible Medium article
- Perfect for capturing older articles not available in RSS feeds
- Can be combined with regular RSS ingestion
- Automatically extracts title, author, content, and publication date
- Integrates seamlessly with existing data structure

**IMPORTANT LIMITATION:** Medium RSS feeds are hard-limited to the **10 most recent articles per author** by Medium's platform design. **Solution**: Use `--manual-urls` to scrape specific older articles that aren't available via RSS feeds.

### Working Around RSS Limitations

**Strategy 1: Manual URL Scraping (RECOMMENDED)**
```bash
# For Yonatan (hashdag) who has 13 total articles but RSS only shows 10:
# 1. Visit https://hashdag.medium.com/ to find older articles
# 2. Copy URLs of the 3 missing articles
# 3. Scrape them manually:
python -m scripts.medium_ingest --manual-urls \
  https://hashdag.medium.com/older-article-1 \
  https://hashdag.medium.com/older-article-2 \
  https://hashdag.medium.com/older-article-3
```

**Strategy 2: Regular Historical Collection**
```bash
# Run weekly/monthly to capture articles before they disappear from RSS
python -m scripts.medium_ingest --full-history
# Manually merge with previous full_history.json files to build complete archive
```

**Strategy 3: Timeline Reconstruction**
```bash
# If you've been running daily, older articles might be in dated files
ls sources/medium/  # Check for articles in previous YYYY-MM-DD.json files
```

### Automated Execution
The system runs automatically via GitHub Actions on a daily schedule. Check the `.github/workflows/` directory for automation configuration.

## 📊 Output Structure

The system generates several types of structured output:

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

## 🤖 AI Processing

The system uses advanced language models (via OpenRouter) to:

- **Extract Key Facts**: Automatically identify and categorize important technical information
- **Generate Summaries**: Create concise, readable summaries of complex technical content  
- **Assess Impact**: Classify information by relevance and importance
- **Maintain Context**: Preserve source attribution and publication dates
- **Ensure Quality**: Validate and structure all extracted information

## GitHub Actions Setup

For the automated daily pipeline to work correctly, you need to configure the following repository secrets in GitHub:

### Required Secrets
- `OPENROUTER_API_KEY` - Your OpenRouter API key for LLM access
- `GH_TOKEN` - GitHub Personal Access Token for repository data access

### Optional Secrets (enable specific features)
- `DISCOURSE_API_USERNAME` - Your Discourse forum username
- `DISCOURSE_API_KEY` - Your Discourse API key for forum access
- `MEDIUM_RSS_URL` - Medium RSS feed URLs (comma-separated)

**To add secrets**: Go to your repository → Settings → Secrets and variables → Actions → New repository secret

**Note**: Without the Discourse credentials, forum ingestion will be skipped but the pipeline will continue running other sources.

## Configuration

See `.env.example` for all available configuration options including:
- AI model selection (OpenRouter, OpenAI, Anthropic, etc.)
- Source-specific API credentials
- Pipeline timing and processing limits

## Architecture

```
Sources → Raw Data → Aggregation → AI Processing → Outputs
  ↓         ↓           ↓             ↓            ↓
GitHub    sources/   data/        data/        Facts &
Medium      ↓       aggregated/  briefings/   Briefings
Forums    JSON        JSON         JSON         JSON
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.