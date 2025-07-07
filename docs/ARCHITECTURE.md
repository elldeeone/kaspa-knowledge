# Architecture Guide

## System Overview

The Kaspa Knowledge Hub operates with clean separation between raw data ingestion, aggregation, and AI processing:

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

## Four-Stage Pipeline Process

### Stage 1: Raw Data Ingestion

- Collects pure, unprocessed data from various sources
- Saves to `sources/` directory with date-stamped files
- Smart deduplication prevents processing duplicate content
- No AI processing or transformation

**Key Scripts:**
- `medium_ingest.py` - Multi-feed Medium RSS ingestion
- `github_ingest.py` - GitHub repository activity ingestion
- `discourse_ingest.py` - Discourse forum post ingestion
- `telegram_ingest.py` - Telegram message ingestion

### Stage 1.5: Data Pre-Processing

- GitHub Activity Summarization: AI-powered summaries of repository activity
- Processes GitHub data into human-readable summaries

**Key Scripts:**
- `summarize_github.py` - AI-powered GitHub activity summarization

### Stage 2: Raw Data Aggregation

- Combines all sources into daily aggregated files
- Creates single source of truth in `data/aggregated/daily.json`
- Still no AI processing - pure data combination

**Key Scripts:**
- `aggregate_sources.py` - Raw data aggregation

### Stage 3: AI Processing

- Reads from raw aggregated data
- Generates separate outputs for different use cases:
  - **Briefings**: Executive summaries and high-level insights
  - **Facts**: Structured technical facts with categories and impact levels
- Smart deduplication avoids reprocessing existing content

**Key Scripts:**
- `generate_briefing.py` - AI briefing generation
- `extract_facts.py` - AI fact extraction with deduplication

### Stage 4: Knowledge Base Generation

- Transforms processed data into RAG-optimized documents
- Creates semantically chunked content with metadata
- Generates final knowledge base files

**Key Scripts:**
- `generate_rag_document.py` - RAG document generation

## Data Sources

### Medium RSS Feeds
- Multiple author feeds for comprehensive coverage of developer blogs and articles
- Smart deduplication prevents duplicate processing
- Automatic content extraction and metadata preservation

### GitHub Repositories
- Commits, pull requests, issues from key Kaspa repos
- AI summarization for human-readable insights
- Rate limiting and smart pagination

### Discourse Forums
- Research discussions from https://research.kas.pa/
- Incremental updates with state management
- Support for both public and private forums

### Telegram Channels
- Community conversations and announcements
- Optional integration with flexible configuration
- Real-time message ingestion

### Discord Channels (Future)
- High-signal conversations from development channels
- Planned integration for comprehensive coverage

### News Sources (Future)
- Industry news and announcements
- Automated content aggregation

## AI Processing Architecture

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

### LLM Integration via OpenRouter

All AI processing is handled through OpenRouter, which provides access to multiple LLM providers:

**Available Models:**
- OpenAI (GPT-3.5, GPT-4, GPT-4-turbo, GPT-4o)
- Anthropic (Claude-3-haiku, Claude-3-sonnet, Claude-3-opus)
- Google (Gemini Pro, Gemini Flash)
- Mistral (Various models)
- Meta (Llama models)
- And many other providers

## High-Signal Processing

### Signal Detection System

The system includes a sophisticated High-Signal Contributor Weighting System:

- **Configuration-based Contributor Identification**
- **Signal Metadata Enrichment during Aggregation**
- **Signal-aware Data Sorting and Analysis**
- **AI Prompt Engineering for Signal Prioritization**

See [High-Signal System Documentation](HIGH_SIGNAL_CONTRIBUTOR_SYSTEM.md) for details.

## Data Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Raw Sources   │    │   Aggregation   │    │  AI Processing  │
│                 │    │                 │    │                 │
│ • Medium RSS    │───▶│ • Combine all   │───▶│ • Generate      │
│ • GitHub API    │    │   sources       │    │   briefings     │
│ • Discourse     │    │ • Apply signal  │    │ • Extract facts │
│ • Telegram      │    │   weighting     │    │ • Create        │
│ • Discord       │    │ • Deduplication │    │   summaries     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                        │                        │
          ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ sources/        │    │ data/aggregated/│    │ data/briefings/ │
│ • Daily files   │    │ • Daily JSON    │    │ • Daily facts   │
│ • Full history  │    │ • Metadata      │    │ • Summaries     │
│ • State files   │    │ • Signal data   │    │ • Insights      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                 │
                                 ▼
                       ┌─────────────────┐
                       │ knowledge_base/ │
                       │ • RAG documents │
                       │ • Chunked data  │
                       │ • Metadata      │
                       └─────────────────┘
```

## Automation Architecture

### GitHub Actions Workflow

The system runs automatically via GitHub Actions:

1. **Scheduled Execution**: Daily at specified time
2. **Complete Pipeline**: Runs all stages in sequence
3. **Error Handling**: Graceful failure handling with notifications
4. **Code Quality**: Automated black and flake8 validation
5. **Artifact Storage**: Preserves generated outputs

### Modular Execution

Each stage can be run independently:

```bash
# Individual stages
python scripts/medium_ingest.py
python scripts/github_ingest.py
python scripts/aggregate_sources.py
python scripts/generate_briefing.py

# Or use the pipeline runner
python scripts/run_pipeline.py ingest  # Stage 1 only
python scripts/run_pipeline.py ai      # Stage 3 only
python scripts/run_pipeline.py full    # All stages
```

## Performance Considerations

### Smart Deduplication

- **Content-Based**: Compares URLs, titles, and content hashes
- **Temporal**: Tracks processing timestamps
- **State Management**: Maintains processing state between runs
- **Force Override**: Option to bypass deduplication when needed

### Rate Limiting

- **API Respect**: Built-in rate limiting for all external APIs
- **Configurable**: Adjustable timing based on API limits
- **Graceful Degradation**: Continues processing if rate limits hit

### Memory Management

- **Streaming**: Processes large files in chunks
- **Lazy Loading**: Loads data only when needed
- **Cleanup**: Automatic cleanup of temporary files

## Error Handling

### Graceful Degradation

- **Optional Sources**: Continues processing if some sources fail
- **Partial Processing**: Generates output with available data
- **Detailed Logging**: Comprehensive error reporting

### Recovery Mechanisms

- **State Persistence**: Maintains processing state
- **Retry Logic**: Automatic retry for transient failures
- **Manual Recovery**: Tools for manual intervention when needed

## Extensibility

### Adding New Sources

1. Create ingestion script following existing patterns
2. Add to pipeline configuration
3. Update aggregation logic
4. Test end-to-end processing

### Custom AI Models

1. Configure OpenRouter model access
2. Update prompt files as needed
3. Test with representative data

### New Output Formats

1. Create generation script
2. Add to pipeline stages
3. Update documentation

## Security Considerations

- **API Key Management**: Secure environment variable handling
- **Rate Limiting**: Respectful API usage
- **Data Privacy**: No sensitive information in outputs
- **Access Control**: Proper permissions for all integrations 