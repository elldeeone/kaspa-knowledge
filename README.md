# Kaspa Knowledge Hub

> **Automated knowledge aggregation and AI-powered insights for the Kaspa cryptocurrency ecosystem**

An intelligent system that automatically collects, processes, and synthesizes information from multiple Kaspa community sources to create comprehensive daily briefings and structured knowledge bases.

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/elldeeone/kaspa-knowledge.git
cd kaspa-knowledge
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure (copy .env.example to .env and add your keys)
cp .env.example .env

# 3. Run the pipeline
python scripts/run_pipeline.py
```

**Need help?** Check the [Setup Guide](docs/SETUP.md) for detailed installation instructions.

## What It Does

- **Automated Data Collection**: Ingests from GitHub, Medium, Telegram, Discord, and research forums
- **AI-Powered Processing**: Extracts key facts, generates insights, and creates executive briefings
- **Smart Prioritization**: Elevates contributions from core developers and researchers
- **RAG-Optimized Output**: Generates structured documents perfect for vector databases
- **Daily Automation**: Runs automatically via GitHub Actions

## Architecture

```
Sources → Raw Data → AI Processing → Knowledge Base
   ↓         ↓           ↓             ↓
GitHub    sources/   data/briefings  knowledge_base/
Medium    telegram/  data/facts      (RAG-ready)
Forums    github/    data/aggregated
...       medium/
```

**[Full Architecture Guide](docs/ARCHITECTURE.md)**

## Key Features

- **Multi-Source Integration**: Comprehensive coverage of Kaspa ecosystem
- **Smart Deduplication**: Avoids processing duplicate content
- **High-Signal Detection**: Prioritizes core developer contributions
- **Modular Pipeline**: Run individual stages independently
- **Quality Controls**: Built-in validation and error handling

## Quick Usage

```bash
# Run complete daily pipeline
python scripts/run_pipeline.py

# Process historical data
python scripts/run_pipeline.py --backfill

# Generate briefings only
python scripts/run_pipeline.py ai

# Process specific date
python scripts/run_pipeline.py --date 2025-01-15
```

## Documentation

| Topic | Description |
|-------|-------------|
| **[Setup Guide](docs/SETUP.md)** | Detailed installation and configuration |
| **[Architecture](docs/ARCHITECTURE.md)** | System design and data flow |
| **[Usage Guide](docs/USAGE.md)** | Command reference and workflows |
| **[High-Signal System](docs/HIGH_SIGNAL_CONTRIBUTOR_SYSTEM.md)** | Core developer prioritization |
| **[RAG Integration](docs/rag-document-generation.md)** | Vector database optimization |
| **[Testing Guide](docs/GITHUB_INTEGRATION_TESTING.md)** | End-to-end testing procedures |

## Sample Output

The system generates several types of structured outputs:

- **Daily Briefings**: Executive summaries of key developments
- **Structured Facts**: Categorized technical insights with impact levels
- **RAG Documents**: Chunked, metadata-rich content for vector databases
- **GitHub Summaries**: Human-readable development activity reports

## Configuration

Multiple configuration methods available:

- **Environment Variables**: API keys and sensitive data (`.env` file)
- **Config Files**: Source settings (`config/sources.config.json`)
- **AI Models**: Powered by OpenRouter (OpenAI, Anthropic, Google, Mistral)

**[Configuration Guide](docs/CONFIGURATION.md)**

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes (ensure code quality with `scripts/verify_formatting.sh`)
4. Submit a pull request

## Tech Stack

- **Python 3.8+** with comprehensive data processing
- **OpenRouter API** for multi-model LLM access
- **GitHub Actions** for automated workflows
- **JSON/Markdown** for structured data storage

## Support

**Need help?** 
- Check the [Setup Guide](docs/SETUP.md) for installation issues
- Review the [Usage Guide](docs/USAGE.md) for command help
- [Open an issue](https://github.com/elldeeone/kaspa-knowledge/issues) for bugs or feature requests

---

**Star this repo** if you find it helpful!