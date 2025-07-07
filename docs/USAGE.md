# Usage Guide

## Quick Start

```bash
# Run the complete pipeline
python scripts/run_pipeline.py

# Run with historical data processing
python scripts/run_pipeline.py --backfill

# Force re-processing
python scripts/run_pipeline.py --force
```

## Pipeline Runner

The `run_pipeline.py` script is the main entry point for the system.

### Pipeline Modes

```bash
# Complete pipeline (default)
python scripts/run_pipeline.py full

# Data ingestion only
python scripts/run_pipeline.py ingest

# Raw data aggregation only
python scripts/run_pipeline.py aggregate

# AI processing only (briefings + facts)
python scripts/run_pipeline.py ai

# RAG document generation only
python scripts/run_pipeline.py rag
```

### Advanced Options

```bash
# Force re-processing even if data exists
python scripts/run_pipeline.py --force

# Run in comprehensive historical mode
python scripts/run_pipeline.py --backfill

# Process specific date (for RAG generation)
python scripts/run_pipeline.py rag --date 2025-01-15

# Combine options
python scripts/run_pipeline.py --backfill --force
```

## Individual Components

### Medium RSS Ingestion

```bash
# Daily sync (default)
python -m scripts.medium_ingest

# Full history backfill (run once)
python -m scripts.medium_ingest --full-history

# Manual URL scraping
python -m scripts.medium_ingest --manual-urls https://hashdag.medium.com/article1

# Force processing (override deduplication)
python -m scripts.medium_ingest --force
```

### GitHub Repository Processing

```bash
# Standard processing
python -m scripts.github_ingest

# Specify days back
python -m scripts.github_ingest --days-back 7

# Process specific date
python -m scripts.github_ingest --date 2025-01-15

# AI summarization
python -m scripts.summarize_github

# Force regeneration of summaries
python -m scripts.summarize_github --force
```

### Discourse Forum Processing

```bash
# Standard processing (incremental)
python -m scripts.discourse_ingest

# Force full re-processing
python -m scripts.discourse_ingest --force

# Process specific forum
python -m scripts.discourse_ingest --forum kaspa_research
```

### Telegram Message Processing

```bash
# Standard processing
python -m scripts.telegram_ingest

# Process specific channels
python -m scripts.telegram_ingest --channels channel1,channel2

# Historical backfill
python -m scripts.telegram_ingest --full-history
```

### Data Aggregation

```bash
# Aggregate all sources for today
python -m scripts.aggregate_sources

# Aggregate for specific date
python -m scripts.aggregate_sources --date 2025-01-15

# Force re-aggregation
python -m scripts.aggregate_sources --force

# Backfill mode (uses full_history.json files)
python -m scripts.aggregate_sources --backfill
```

### AI Processing

```bash
# Generate daily briefing
python -m scripts.generate_briefing

# Extract facts with deduplication
python -m scripts.extract_facts

# Force fact extraction (override deduplication)
python -m scripts.extract_facts --force

# Process specific date
python -m scripts.generate_briefing --date 2025-01-15
```

### RAG Document Generation

```bash
# Generate for today
python -m scripts.generate_rag_document

# Generate for specific date
python -m scripts.generate_rag_document --date 2025-01-15

# Generate enhanced version with high-signal filtering
python -m scripts.generate_rag_document --enhanced

# Force overwrite existing files
python -m scripts.generate_rag_document --force
```

## Smart Deduplication

The system includes intelligent deduplication across all components:

### Automatic Deduplication

- **Medium**: Compares article URLs and publication dates
- **GitHub**: Tracks processed commits, PRs, and issues
- **Forum**: Incremental post fetching with state management
- **Facts**: Detects existing facts files to avoid reprocessing

### Override Deduplication

```bash
# Force processing for any component
python -m scripts.extract_facts --force
python -m scripts.medium_ingest --force
python -m scripts.github_ingest --force
```

## Configuration Examples

### Multiple RSS Feeds

```bash
# Set in .env file
MEDIUM_RSS_URLS=https://hashdag.medium.com/feed,https://kaspadev.medium.com/feed,https://medium.com/feed/@kaspa_currency
```

### GitHub Repositories

```json
// config/sources.config.json
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

### High-Signal Contributors

```json
// config/sources.config.json
{
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

## Output Files

### Daily Files

```bash
# Raw data
sources/medium/2025-01-15.json
sources/github/2025-01-15.json
sources/forum/2025-01-15.json
sources/telegram/2025-01-15.json

# Processed data
data/aggregated/2025-01-15.json
data/briefings/2025-01-15.json
data/facts/2025-01-15.json

# AI summaries
sources/github_summaries/2025-01-15.md

# RAG documents
knowledge_base/2025-01-15.md
```

### Historical Files

```bash
# Full history backfill
sources/medium/full_history.json
sources/github/full_history.json
sources/forum/full_history.json
sources/telegram/full_history.json
```

## Workflow Examples

### Daily Processing

```bash
# Standard daily workflow
python scripts/run_pipeline.py

# With force regeneration
python scripts/run_pipeline.py --force

# Only new data processing
python scripts/run_pipeline.py ingest
python scripts/run_pipeline.py aggregate
python scripts/run_pipeline.py ai
```

### Historical Backfill

```bash
# Initial setup - backfill all historical data
python scripts/run_pipeline.py --backfill --force

# Process only specific sources
python -m scripts.medium_ingest --full-history
python -m scripts.github_ingest --days-back 30
python scripts/run_pipeline.py aggregate --backfill
```

### Targeted Processing

```bash
# Process only GitHub for specific date
python -m scripts.github_ingest --date 2025-01-10
python -m scripts.summarize_github --date 2025-01-10

# Generate briefing for specific date
python -m scripts.generate_briefing --date 2025-01-10

# Create RAG document for specific date
python -m scripts.generate_rag_document --date 2025-01-10
```

## Monitoring and Debugging

### Verbose Output

```bash
# Enable verbose logging
export PYTHONPATH=.
python -m scripts.run_pipeline --verbose

# Check specific component
python -m scripts.github_ingest --verbose
```

### Validation

```bash
# Validate GitHub data
python scripts/validate_github_data.py

# Validate specific file
python scripts/validate_github_data.py --file sources/github/2025-01-15.json

# Validate with detailed output
python scripts/validate_github_data.py --verbose
```

### Testing

```bash
# Run integration tests
python scripts/test_github_integration.py

# Test specific components
python -m scripts.medium_ingest --test
python -m scripts.github_ingest --test
```

## Performance Tips

### Incremental Processing

- Use default settings for daily processing
- Only use `--force` when necessary
- Leverage smart deduplication

### Resource Management

```bash
# For large datasets, process stages separately
python scripts/run_pipeline.py ingest
python scripts/run_pipeline.py aggregate
python scripts/run_pipeline.py ai
```

### Rate Limiting

The system includes built-in rate limiting, but you can adjust:

```bash
# Slower processing for strict rate limits
python -m scripts.github_ingest --rate-limit 2
```

## Common Use Cases

### Setup New Instance

```bash
# 1. Initial backfill
python scripts/run_pipeline.py --backfill --force

# 2. Daily processing
python scripts/run_pipeline.py
```

### Recover from Failure

```bash
# 1. Check what's missing
ls data/aggregated/
ls data/briefings/
ls data/facts/

# 2. Regenerate missing data
python scripts/run_pipeline.py --force --date 2025-01-15
```

### Custom Analysis

```bash
# 1. Get raw data
python scripts/run_pipeline.py ingest

# 2. Create custom aggregation
python -m scripts.aggregate_sources --custom-config config/custom.json

# 3. Generate insights
python -m scripts.generate_briefing --custom-prompt prompts/custom.txt
```

## Error Handling

### Common Issues

1. **Missing API Keys**: Check `.env` file
2. **Rate Limits**: Use `--rate-limit` flag
3. **Network Issues**: Retry with `--force`
4. **Disk Space**: Clean up old files

### Recovery Commands

```bash
# Restart from specific stage
python scripts/run_pipeline.py aggregate --date 2025-01-15
python scripts/run_pipeline.py ai --date 2025-01-15

# Force regeneration
python scripts/run_pipeline.py --force --date 2025-01-15
```

## Automation

### GitHub Actions

The system runs automatically via GitHub Actions. You can also trigger manually:

```bash
# Trigger via GitHub CLI
gh workflow run daily-pipeline.yml

# Trigger specific workflow
gh workflow run daily-pipeline.yml --ref main
```

### Cron Jobs

```bash
# Daily at 2 AM
0 2 * * * cd /path/to/kaspa-knowledge && python scripts/run_pipeline.py

# Weekly full backfill
0 3 * * 0 cd /path/to/kaspa-knowledge && python scripts/run_pipeline.py --backfill --force
``` 