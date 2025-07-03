# Canonical Ingestion Document: Requirements Analysis and Schema Design

## Overview

This document defines the requirements and schema design for generating a semantically structured Markdown document optimized for Retrieval-Augmented Generation (RAG) systems. The system transforms daily JSON artifacts from multiple sources into a single, chunked, and metadata-rich document suitable for vector embedding and retrieval.

## Requirements Analysis

### 1. Functional Requirements

#### 1.1 Data Sources Integration
- **Aggregated Data**: Load from `data/aggregated/YYYY-MM-DD.json` containing all enriched items with signal metadata
- **Briefings Data**: Load from `data/briefings/YYYY-MM-DD.json` containing narrative summaries by source
- **Facts Data**: Load from `data/facts/YYYY-MM-DD.json` containing AI-extracted structured facts
- **Date Range**: Support processing for any valid date within the data directory

#### 1.2 Document Structure Requirements
- **Hierarchical Structure**: Use consistent Markdown heading hierarchy for semantic organization
- **Metadata Preservation**: Attach YAML metadata blocks to each semantic chunk
- **Attribution**: Maintain complete traceability to original sources
- **Semantic Chunking**: Optimize for 200-500 token chunks with semantic completeness

#### 1.3 High-Signal Content Prioritization
- **Signal Detection**: Identify and prioritize content with `signal` metadata blocks
- **Contributor Role Awareness**: Differentiate content based on contributor roles (core_developer, lead, founder)
- **Dedicated Section**: Create separate section for high-signal contributor insights

### 2. Non-Functional Requirements

#### 2.1 Performance
- **Processing Time**: Complete generation within 30 seconds for typical daily data volumes
- **Memory Efficiency**: Process large JSON files without excessive memory usage
- **Error Recovery**: Graceful handling of missing or malformed input files

#### 2.2 Maintainability
- **Schema Consistency**: Enforce strict template adherence across all generated documents
- **Version Control**: Include generation metadata for tracking and debugging
- **Documentation**: Comprehensive inline documentation and usage examples

#### 2.3 Scalability
- **Extensible Design**: Support addition of new data sources without schema changes
- **Parallel Processing**: Design for potential future parallelization of chunk generation

## Data Schema Analysis

### 3. Input Data Structures

#### 3.1 Aggregated Data Schema
```json
{
  "date": "YYYY-MM-DD",
  "generated_at": "ISO8601 timestamp",
  "sources": {
    "github_activities": [
      {
        "type": "github_commit|github_pull_request|github_issue",
        "repository": "owner/repo-name",
        "title": "Human readable title",
        "author": "GitHub username",
        "url": "Full GitHub URL",
        "date": "ISO8601 timestamp",
        "content": "Detailed description/content",
        "metadata": {
          "sha": "commit_hash",
          "number": "pr/issue_number",
          "state": "open|closed|merged",
          "stats": {
            "additions": int,
            "deletions": int,
            "changed_files": int
          }
        },
        "signal": {
          "strength": "high|medium|low",
          "contributor_role": "core_developer|community_contributor|...",
          "is_lead": boolean,
          "is_founder": boolean
        }
      }
    ],
    "medium_articles": [...],
    "telegram_messages": [...],
    "discord_messages": [...],
    "forum_posts": [...],
    "news_articles": [...],
    "documentation": [...]
  },
  "metadata": {
    "total_items": int,
    "processing_time": "duration string",
    "pipeline_version": "version string",
    "signal_analysis": {
      "total_items": int,
      "high_signal_items": int,
      "contributor_roles": {}
    }
  }
}
```

#### 3.2 Briefings Data Schema
```json
{
  "date": "YYYY-MM-DD",
  "generated_at": "ISO8601 timestamp",
  "sources": {
    "medium": {
      "summary": "Narrative summary text",
      "key_topics": ["topic1", "topic2"],
      "article_summaries": [...]
    },
    "github": {
      "summary": "Narrative summary text",
      "repositories": ["repo1", "repo2"],
      "activity_summary": {}
    },
    "telegram": { "summary": "..." },
    "discord": { "summary": "..." },
    "forum": { "summary": "...", "post_count": int },
    "news": { "summary": "..." }
  },
  "metadata": {
    "total_sources_processed": int,
    "briefing_version": "version string",
    "llm_model": "model identifier"
  }
}
```

#### 3.3 Facts Data Schema
```json
{
  "date": "YYYY-MM-DD",
  "generated_at": "ISO8601 timestamp",
  "facts": [
    {
      "fact": "Factual statement text",
      "category": "technical|security|development|consensus|...",
      "impact": "high|medium|low",
      "context": "Contextual explanation",
      "source": {
        "type": "github_commit|github_pull_request|...",
        "title": "Source title",
        "author": "Author name",
        "url": "Source URL",
        "date": "ISO8601 timestamp",
        "repository": "owner/repo-name"
      },
      "extracted_at": "ISO8601 timestamp"
    }
  ],
  "statistics": {
    "total_facts": int,
    "by_category": {},
    "by_impact": {},
    "by_source": {}
  }
}
```

### 4. Output Document Schema

#### 4.1 Target Markdown Structure
```markdown
# Kaspa Knowledge Digest: YYYY-MM-DD

```metadata
document_type: "kaspa_knowledge_digest"
date: "YYYY-MM-DD"
generated_at: "ISO8601 timestamp"
schema_version: "1.0.0"
chunk_id: "digest-YYYY-MM-DD-header"
```

## Daily Briefing

```metadata
source: "data/briefings/YYYY-MM-DD.json"
date: "YYYY-MM-DD"
section_type: "briefing_narrative"
chunk_id: "briefing-YYYY-MM-DD-001"
sources_covered: ["github", "medium", "telegram", "discord", "forum", "news"]
```

[Narrative summary content from briefings JSON]

---

## Key Facts

```metadata
source: "data/facts/YYYY-MM-DD.json"
date: "YYYY-MM-DD"
section_type: "extracted_facts"
chunk_id: "facts-YYYY-MM-DD-001"
total_facts: int
fact_categories: ["technical", "security", "development"]
```

### Fact: [Fact Statement]

- **Impact**: High/Medium/Low
- **Category**: Technical/Security/Development/etc.
- **Context**: [Contextual explanation]
- **Source**: [Source Title](Source URL)

```metadata
fact_id: "fact-YYYY-MM-DD-001"
category: "technical"
impact: "high"
source_type: "github_pull_request"
author: "author_name"
source_url: "https://..."
extracted_at: "ISO8601"
```

---

## SIGNAL: High-Signal Contributor Insights

```metadata
source: "data/aggregated/YYYY-MM-DD.json"
date: "YYYY-MM-DD"
section_type: "high_signal_insights"
chunk_id: "signal-YYYY-MM-DD-001"
signal_threshold: "high"
contributor_roles: ["core_developer", "founder"]
```

### [Content Title]

```metadata
source_type: "github_pull_request|medium_article|..."
author: "Author Name"
date: "YYYY-MM-DD"
signal_strength: "high"
contributor_role: "core_developer|founder|..."
is_lead: boolean
is_founder: boolean
url: "https://..."
chunk_id: "signal-YYYY-MM-DD-item-001"
```

[Full content or summary]

---

## General Activity

### GitHub Activity

```metadata
source: "data/aggregated/YYYY-MM-DD.json"
date: "YYYY-MM-DD"
section_type: "github_activity"
chunk_id: "github-YYYY-MM-DD-001"
activity_types: ["commit", "pull_request", "issue"]
```

#### [Activity Title]

```metadata
source_type: "github_pull_request"
author: "Author Name"
date: "YYYY-MM-DD"
signal_strength: "medium|low|none"
contributor_role: "community_contributor"
repository: "kaspanet/rusty-kaspa"
url: "https://..."
chunk_id: "github-YYYY-MM-DD-item-001"
activity_stats: {
  "additions": int,
  "deletions": int,
  "files_changed": int
}
```

[Activity content]
```

#### 4.2 Metadata Block Standard

Each semantic chunk MUST include a YAML metadata block with the following standard fields:

**Required Fields:**
- `source`: Source file path or identifier
- `date`: Processing date (YYYY-MM-DD)
- `chunk_id`: Unique identifier for the chunk
- `section_type`: Type of content section

**Conditional Fields:**
- `author`: Content author (when available)
- `signal_strength`: Signal level (high/medium/low/none)
- `contributor_role`: Role of the contributor
- `source_type`: Type of source content
- `url`: Original source URL
- `impact`: Impact level for facts
- `category`: Content category

**Optional Fields:**
- `is_lead`: Boolean for lead developer status
- `is_founder`: Boolean for founder status
- `repository`: GitHub repository name
- `activity_stats`: Statistics for GitHub activities
- `extraction_metadata`: Additional processing metadata

### 5. Chunking Strategy

#### 5.1 Semantic Boundaries
- **Primary**: Split at major Markdown headings (`#`, `##`, `###`)
- **Secondary**: Split long sections at paragraph boundaries
- **Preserve Structure**: Keep tables, lists, and code blocks intact within chunks

#### 5.2 Chunk Size Guidelines
- **Target Range**: 200-500 tokens per chunk
- **Priority**: Semantic completeness over strict token limits
- **Maximum**: 800 tokens for complex technical content
- **Minimum**: 50 tokens to avoid fragmented content

#### 5.3 Metadata Propagation
- Each chunk inherits document-level metadata
- Section-specific metadata is added to relevant chunks
- Item-specific metadata is preserved for individual content pieces

### 6. Error Handling Requirements

#### 6.1 Missing Files
- Graceful degradation when source files are missing
- Generate document with available data and note missing sources
- Log warnings for missing files with specific file paths

#### 6.2 Malformed Data
- Validate JSON structure before processing
- Skip malformed items with detailed error logging
- Continue processing valid items when encountering errors

#### 6.3 Empty Data Sets
- Handle empty facts, briefings, or aggregated data gracefully
- Generate appropriate placeholder content with metadata
- Maintain document structure even with minimal content

### 7. Integration Requirements

#### 7.1 Pipeline Integration
- Execute after aggregation, facts extraction, and briefing generation
- Add to `run_pipeline.py` as final processing step
- Support command-line execution with date parameter

#### 7.2 Output Management
- Save to `knowledge_base/YYYY-MM-DD.md`
- Create directory structure if it doesn't exist
- Overwrite existing files with confirmation option

#### 7.3 Validation
- Validate generated Markdown syntax
- Verify all metadata blocks are properly formatted
- Check chunk size distribution and optimization

## Implementation Notes

### 8.1 Performance Optimizations
- Stream processing for large JSON files
- Lazy loading of data sections
- Efficient string building for Markdown generation

### 8.2 Future Extensibility
- Plugin architecture for new data sources
- Configurable chunking strategies
- Template customization support

### 8.3 Testing Strategy
- Unit tests for each data source parser
- Integration tests with sample data
- Validation tests for output format compliance 