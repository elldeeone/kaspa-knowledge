# High-Signal Contributor Weighting System

## Overview

The High-Signal Contributor Weighting System is designed to identify, enrich, and prioritize contributions from high-signal sources (core developers, founders, researchers) in the Kaspa knowledge pipeline. This system ensures protocol-level insights are elevated above general community chatter while maintaining objectivity and capturing all voices.

## Architecture

The system follows a "signal over noise" principle through four main components:

1. **Configuration-based Contributor Identification**
2. **Signal Metadata Enrichment during Aggregation**
3. **Signal-aware Data Sorting and Analysis**
4. **AI Prompt Engineering for Signal Prioritization**

## Configuration Schema

### High-Signal Contributors Configuration

Add high-signal contributors to `config/sources.config.json`:

```json
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
    },
    {
      "name": "Ori Newman", 
      "aliases": ["someone235", "Ori Newman"],
      "role": "core_developer"
    }
  ]
}
```

### Schema Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Full name of the contributor |
| `aliases` | array[string] | Yes | List of aliases/usernames used by contributor |
| `role` | string | Yes | Role type (e.g., "core_developer", "founder_researcher") |
| `is_lead` | boolean | No | Marks the lead developer (default: false) |

### Supported Roles

- `core_developer`: Core development team members
- `founder_researcher`: Founders and research contributors  
- `researcher`: Independent researchers
- `maintainer`: Project maintainers
- *Extensible for future role types*

## Signal Metadata Enrichment

### Implementation

The enrichment process is handled by a dedicated `SignalEnrichmentService` class in `scripts/signal_enrichment.py`:

```python
from signal_enrichment import SignalEnrichmentService

# Initialize the service
service = SignalEnrichmentService("config/sources.config.json")

# Enrich individual items
enriched_item = service.enrich_item(item)

# Enrich multiple items
enriched_items = service.enrich_items(items_list)

# Sort by signal priority
sorted_items = service.sort_by_signal_priority(enriched_items)
```

### Architecture Benefits

- **Modularity**: Signal logic is separated from aggregation pipeline
- **Reusability**: Service can be used across multiple modules
- **Testability**: Isolated logic enables comprehensive unit testing
- **Extensibility**: Easy to extend with new signal types and roles
- **Backward Compatibility**: Convenience functions maintain legacy compatibility

### Signal Metadata Structure

When a contributor match is found, items are enriched with:

```json
{
  "signal": {
    "strength": "high",
    "contributor_role": "core_developer",
    "is_lead": false
  }
}
```

## Data Processing Pipeline

### 1. Signal-Based Sorting

Items are sorted by signal priority:
1. **Lead developer contributions** (highest priority)
2. **High-signal contributor contributions**
3. **Standard community contributions**

### 2. Signal Analysis Metadata

Each aggregated output includes comprehensive signal analysis:

```json
{
  "metadata": {
    "signal_analysis": {
      "total_items": 9,
      "high_signal_items": 3,
      "lead_developer_items": 0,
      "contributor_roles": {
        "core_developer": 3
      },
      "signal_distribution": {
        "high": 3,
        "standard": 6
      },
      "sources_with_signals": {
        "github_activities": {
          "total": 9,
          "high_signal": 3,
          "lead_developer": 0,
          "roles": {
            "core_developer": 3
          }
        }
      }
    }
  }
}
```

## AI Prompt Integration

### Fact Extraction Prompts

The system modifies `scripts/prompts/extract_kaspa_facts_system.txt` to:

- Treat lead developer insights as "most direct signal"
- Assign high impact to high-signal contributions
- Note contributor roles in context fields
- Prioritize protocol-level technical insights

### Daily Briefing Prompts  

The system modifies `scripts/prompts/generate_daily_briefing_system.txt` to:

- Create dedicated "Core Development Insights" section
- Give primary placement to lead developer contributions
- Provide specific phrasing guidance for key contributors
- Differentiate protocol developments from general discussion

## Usage Guidelines

### Adding New Contributors

1. Update `config/sources.config.json` with new contributor information
2. Include all known aliases/usernames
3. Assign appropriate role
4. Mark lead developer with `"is_lead": true` if applicable

### Extending Roles

1. Add new role types to the configuration
2. Update AI prompts if role-specific handling is needed
3. Update documentation with new role descriptions

### Data Source Integration

The system automatically processes these data sources:
- GitHub activities (commits, PRs, issues)
- Medium articles
- Telegram messages
- Discord messages  
- Forum posts
- News articles

New data sources require:
1. Author field mapping
2. Integration in `aggregate_sources.py` source mappings
3. Signal enrichment application

## Testing

### Unit Tests

The system includes comprehensive unit tests in `scripts/test_signal_enrichment.py`:

```bash
# Run all tests
python scripts/test_signal_enrichment.py
```

**Test Coverage:**
- Signal enrichment functionality
- Backward compatibility
- Error handling and graceful degradation  
- System extensibility
- Contributors summary functionality

### Integration Testing

Test the full pipeline integration:

```bash
# Test with real data
python scripts/aggregate_sources.py --date=2025-07-02 --force

# Verify signal analysis in output
```

## Console Output

The system provides real-time feedback during aggregation:

```
📋 Loaded 3 high-signal contributors

🎯 Signal Analysis Summary:
   📈 High-signal items: 3/9
   👑 Lead developer items: 0
   👥 Contributor roles: core_developer(3)
   📊 Sources with signals: github_activities
```

## Backward Compatibility

The system is designed for backward compatibility:

- **Graceful degradation**: Works without contributor configuration
- **Optional metadata**: Signal metadata is added only when matches are found
- **Non-breaking changes**: Existing pipeline stages handle enriched data transparently
- **Legacy support**: Original data structure remains unchanged

## Performance Considerations

- **Configuration caching**: Contributors loaded once at initialization
- **Efficient matching**: Simple alias lookup with early termination
- **Minimal overhead**: Signal enrichment adds minimal processing time
- **Memory efficient**: Signal metadata adds small footprint per item

## Security Considerations

- **Input validation**: Configuration loading includes error handling
- **Author verification**: Only exact alias matches trigger enrichment
- **Data integrity**: Original data preserved during enrichment
- **Fail-safe operation**: System operates normally if configuration is missing

## Testing

### Manual Testing

1. Run aggregation with test data containing high-signal contributors:
   ```bash
   python scripts/aggregate_sources.py --date=2025-07-02 --force
   ```

2. Verify signal metadata in output:
   ```bash
   cat data/aggregated/2025-07-02.json | jq '.metadata.signal_analysis'
   ```

3. Check signal-based sorting in data sources:
   ```bash  
   cat data/aggregated/2025-07-02.json | jq '.sources.github_activities[0:3] | .[].signal'
   ```

### Expected Results

- High-signal items appear first in data sources
- Signal metadata properly attached to contributor items
- Console output shows signal analysis summary
- Aggregated metadata includes comprehensive signal analysis

## Troubleshooting

### Common Issues

**Issue**: No high-signal items detected
- **Solution**: Verify contributor aliases match author fields exactly
- **Check**: Ensure `config/sources.config.json` is present and valid

**Issue**: Contributors not loading
- **Solution**: Check JSON syntax in configuration file
- **Check**: Verify file path and permissions

**Issue**: Signal metadata missing
- **Solution**: Confirm contributor aliases include all variations used in data
- **Check**: Review author field values in source data

## Future Enhancements

### Planned Improvements

1. **Dynamic confidence scoring** based on contribution content analysis
2. **Time-based signal decay** for historical contributor activity
3. **Machine learning-based contributor identification**
4. **Cross-platform alias resolution** for consistent identity matching
5. **Signal strength gradation** beyond binary high/standard classification

### Extension Points

- **Custom role definitions** with specific AI prompt behaviors  
- **Source-specific signal processing** for different data types
- **Signal aggregation metrics** for contributor influence analysis
- **Integration APIs** for external contributor databases

## Maintenance

### Regular Tasks

1. **Update contributor lists** as team changes occur
2. **Review alias coverage** when new platforms are integrated  
3. **Monitor signal distribution** to ensure appropriate balance
4. **Test prompt effectiveness** with changing contributor patterns

### Configuration Updates

When updating contributor information:
1. Update `config/sources.config.json`
2. Test aggregation with recent data
3. Verify AI prompt outputs reflect changes
4. Update documentation if new roles are added

## Example Workflows

### Adding a New Core Developer

```json
{
  "name": "New Developer",
  "aliases": ["newdev", "new.developer", "New Developer"],
  "role": "core_developer"
}
```

### Marking Lead Developer Change

```json
{
  "name": "Former Lead",
  "aliases": ["oldlead", "Former Lead"],
  "role": "core_developer",
  "is_lead": false
},
{
  "name": "New Lead", 
  "aliases": ["newlead", "New Lead"],
  "role": "core_developer",
  "is_lead": true
}
```

This documentation provides comprehensive guidance for understanding, using, and extending the High-Signal Contributor Weighting System. 