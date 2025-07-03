# RAG Document Generation System

This document describes the Canonical Ingestion Document Generation System that transforms daily JSON artifacts into semantically structured Markdown documents optimized for RAG (Retrieval-Augmented Generation) systems.

## Overview

The RAG Document Generation System is a comprehensive pipeline that processes aggregated data, briefings, and facts to create semantically structured documents with YAML metadata blocks for optimal RAG system performance.

### Key Features

- **Semantic Chunking**: Intelligent content chunking targeting 200-500 tokens per chunk
- **YAML Metadata Blocks**: Rich metadata for each semantic chunk including source, date, section type, and content-specific attributes
- **High-Signal Filtering**: Advanced filtering system to prioritize content from core developers, founders, and high-impact sources
- **Error Handling & Validation**: Comprehensive error tracking, retry mechanisms, and validation systems
- **Multiple Output Modes**: Standard and enhanced (filtered) document generation

## Architecture

### Core Components

1. **Data Loader** (`scripts/data_loader.py`)
   - Loads and validates JSON data from aggregated, briefings, and facts directories
   - Comprehensive schema validation
   - Error reporting and data structure verification

2. **Markdown Template Generator** (`scripts/markdown_template_generator.py`)
   - Generates semantically structured Markdown documents
   - Creates YAML metadata blocks for each chunk
   - Handles content formatting and attribution

3. **High-Signal Filter** (`scripts/high_signal_filter.py`)
   - Multi-factor scoring algorithm for content prioritization
   - Contributor role weighting (founder=100, core_developer=90, etc.)
   - Content quality analysis and recency scoring

4. **Error Handler** (`scripts/error_handler.py`)
   - Comprehensive error tracking and logging
   - Pipeline health monitoring
   - Retry mechanisms with exponential backoff

5. **Integration Script** (`scripts/generate_rag_document.py`)
   - Main orchestrator combining all components
   - Command-line interface for standalone usage
   - Integration with main pipeline

## Document Structure

Generated documents follow this semantic structure:

```
# Kaspa Knowledge Digest: YYYY-MM-DD

```metadata
source: generated
date: YYYY-MM-DD
chunk_id: digest-YYYY-MM-DD-header
section_type: document_header
```

Introduction and overview content...

---

## Daily Briefing

```metadata
source: data/briefings/YYYY-MM-DD.json
date: YYYY-MM-DD
chunk_id: briefing-YYYY-MM-DD-github_activities-001
section_type: briefing_narrative
sources_covered: ["github_activities"]
```

### GitHub Activities

Briefing content for GitHub activities...

---

## Key Facts

```metadata
source: data/facts/YYYY-MM-DD.json
date: YYYY-MM-DD
chunk_id: facts-YYYY-MM-DD-development-002
section_type: extracted_facts
category: development
total_facts: 5
```

### Development

- **Fact**: Description with proper attribution
- **Fact**: Another important development fact

---

## High-Signal Contributor Insights

```metadata
source: data/aggregated/YYYY-MM-DD.json
date: YYYY-MM-DD
chunk_id: insights-YYYY-MM-DD-founder-003
section_type: high_signal_insights
contributor_role: founder
```

### Founder

Content from founders and core contributors...

---

## General Activity

```metadata
source: data/aggregated/YYYY-MM-DD.json
date: YYYY-MM-DD
chunk_id: activity-YYYY-MM-DD-general-004
section_type: general_activity
```

All other relevant activity and updates...
```

## Usage

### Command Line Interface

```bash
# Generate standard RAG document for today
python scripts/generate_rag_document.py

# Generate for specific date
python scripts/generate_rag_document.py --date 2025-07-01

# Generate enhanced document with high-signal filtering
python scripts/generate_rag_document.py --date 2025-07-01 --enhanced

# Force overwrite existing files
python scripts/generate_rag_document.py --date 2025-07-01 --force

# Custom input/output directories
python scripts/generate_rag_document.py --data-dir /path/to/data --output-dir /path/to/output
```

### Pipeline Integration

The RAG document generation is integrated into the main pipeline as Stage 4:

```bash
# Run full pipeline (includes RAG generation)
python scripts/run_pipeline.py

# Run only RAG generation
python scripts/run_pipeline.py rag

# Run RAG generation for specific date
python scripts/run_pipeline.py rag --date 2025-07-01

# Force regeneration
python scripts/run_pipeline.py rag --force
```

## Configuration

### High-Signal Filtering Configuration

The high-signal filtering system uses configurable parameters:

```python
FilterConfig(
    minimum_score=50.0,              # Minimum score threshold
    high_signal_threshold=70.0,      # High signal threshold
    critical_signal_threshold=90.0,  # Critical signal threshold
    max_items_per_category=20,       # Max items per category
    contributor_weight=0.4,          # Weight for contributor scoring
    content_weight=0.3,              # Weight for content quality
    recency_weight=0.15,             # Weight for recency
    impact_weight=0.1,               # Weight for impact
    engagement_weight=0.05           # Weight for engagement
)
```

### Contributor Role Weights

- **Founder**: 100 points
- **Core Developer**: 90 points  
- **Lead**: 80 points
- **Maintainer**: 70 points
- **Community Contributor**: 50 points
- **Contributor**: 30 points
- **User**: 10 points

## Output Files

### Standard Mode
- **Location**: `knowledge_base/YYYY-MM-DD.md`
- **Content**: All available content organized semantically
- **Target**: General RAG system usage

### Enhanced Mode
- **Location**: `knowledge_base/YYYY-MM-DD_enhanced.md`
- **Content**: High-signal filtered content prioritized by contributor importance
- **Target**: Focused RAG responses from authoritative sources

## Error Handling

The system includes comprehensive error handling:

- **Retry Mechanisms**: Exponential backoff for transient failures
- **Validation**: Input data, directory structure, and output validation
- **Health Monitoring**: Component health tracking with success rates
- **Structured Logging**: Detailed error reporting with context

### Error Categories

- `DATA_LOADING`: Issues loading JSON files
- `DATA_VALIDATION`: Schema or structure validation failures
- `TEMPLATE_GENERATION`: Document generation errors
- `SIGNAL_FILTERING`: High-signal filtering errors
- `FILE_OPERATIONS`: File I/O operations
- `PIPELINE_EXECUTION`: General pipeline execution errors

## Testing

### Component Testing

Each component includes comprehensive test coverage:

```bash
# Test data loader
python test_data_loader.py

# Test template generator
python test_markdown_template_generator.py

# Test high-signal filter
python test_high_signal_filter.py

# Test error handling system
python test_error_handling.py
```

### Integration Testing

```bash
# Test full integration
python scripts/generate_rag_document.py --date 2025-07-01 --force
```

## Maintenance

### Adding New Metadata Fields

To add new metadata fields to semantic chunks:

1. Update `MetadataBlock` dataclass in `markdown_template_generator.py`
2. Add field to `to_yaml_block()` method
3. Update template generation logic to populate the field
4. Update documentation

### Extending High-Signal Filtering

To add new filtering criteria:

1. Update `FilterConfig` with new parameters
2. Add scoring method in `HighSignalFilter`
3. Update `_calculate_signal_score()` to include new factor
4. Add tests for new filtering logic

### Custom Content Sections

To add new document sections:

1. Create section generation method in `MarkdownTemplateGenerator`
2. Update `generate_document()` to include new section
3. Define appropriate metadata structure
4. Update validation logic if needed

## Performance Considerations

- **Memory Usage**: System processes data incrementally to manage memory
- **Processing Time**: Typical generation time: 1-3 seconds per document
- **File Sizes**: Generated documents typically range from 10KB to 50KB
- **Scalability**: Designed to handle daily processing with minimal resource usage

## Troubleshooting

### Common Issues

1. **Missing Data Files**: Ensure aggregated, briefings, and facts directories exist with proper JSON files
2. **Schema Validation Errors**: Check JSON structure matches expected format
3. **Empty Documents**: Verify input data contains valid content
4. **Permission Errors**: Ensure write permissions to output directory

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
logger = create_pipeline_logger("DEBUG")
```

## Future Enhancements

### Planned Features

- **Incremental Updates**: Support for updating existing documents with new data
- **Custom Templates**: Configurable document templates for different use cases
- **Multi-format Output**: Support for JSON, XML, and other structured formats
- **Advanced Analytics**: Content quality metrics and document performance tracking
- **API Integration**: REST API for programmatic document generation

### Research Areas

- **Optimal Chunk Sizes**: Research into optimal token counts for different RAG systems
- **Semantic Similarity**: Content similarity detection for duplicate prevention
- **Dynamic Metadata**: Automatic metadata extraction from content analysis
- **Quality Scoring**: Advanced algorithms for content quality assessment

## References

- [RAG System Best Practices](docs/rag-best-practices.md)
- [JSON Schema Specifications](docs/json-schemas.md)
- [Pipeline Architecture](docs/pipeline-architecture.md)
- [Error Handling Guide](docs/error-handling.md) 