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
├── processing/               # Pipeline processing scripts
│   ├── medium_ingest.py      # Medium RSS ingestion
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

- **Medium RSS Feeds**: Core developer blogs and articles
- **GitHub Repositories**: Commits, pull requests, issues from key Kaspa repos  
- **Discord Channels**: High-signal conversations from development channels
- **Research Forum**: Discussions from https://research.kas.pa/
- **On-Chain Data**: Daily network statistics (hashrate, BPS, transaction volume)
- **News Sources**: Industry news and announcements

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
   # MEDIUM_RSS_URL=https://hashdag.medium.com/feed
   ```

5. **Set up GitHub Actions secrets** (for automation):
   - `OPENROUTER_API_KEY`: For AI processing
   - Additional API keys as needed for data sources

## 🔧 Configuration

Configuration is managed through:

- **Environment variables** (`.env` file): OpenRouter API keys and RSS feed URLs
- **Script parameters**: Configurable within individual processing scripts  
- **Pipeline settings**: Located in `processing/run_pipeline.py`

## 🏃‍♂️ Usage

### Manual Execution

**Run the complete pipeline:**
```bash
python -m processing.run_pipeline
```

**Run individual stages:**
```bash
# Stage 1: Ingest raw data
python -m processing.medium_ingest

# Stage 2: Aggregate raw sources  
python -m processing.aggregate_sources

# Stage 3a: Generate briefings
python -m processing.generate_briefing

# Stage 3b: Extract facts
python -m processing.extract_facts
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