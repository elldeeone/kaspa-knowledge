# GitHub Integration End-to-End Testing

This document outlines the comprehensive testing strategy for the Kaspa Knowledge Hub GitHub integration, ensuring the complete two-stage pipeline works correctly from raw data ingestion through AI summarization to final aggregation.

## Testing Overview

The GitHub integration testing validates:
- **Environment Setup** and configuration validation
- **GitHub API Authentication** and repository access
- **Raw Data Ingestion** with structured JSON output
- **Data Validation** ensuring schema compliance
- **AI Summarization** generating clean Markdown summaries
- **Pipeline Integration** with complete end-to-end flow
- **Edge Cases** and error handling scenarios

## Test Environment Setup

### Prerequisites

1. **GitHub Personal Access Token**
   ```bash
   # Add to .env file
   GITHUB_TOKEN=your_github_personal_access_token_here
   ```

2. **AI API Key (Optional for full testing)**
   ```bash
   # Add to .env file for AI summarization tests
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

3. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Running Tests

### Quick Test Run
```bash
# Run the comprehensive test suite
python scripts/test_github_integration.py
```

### Manual Component Testing

#### 1. Test GitHub Ingestion Only
```bash
# Ingest data for today
python -m scripts.github_ingest

# Ingest data for specific date
python -m scripts.github_ingest --date 2025-07-01

# Minimal ingestion (1 day back)
python -m scripts.github_ingest --days-back 1
```

#### 2. Test Data Validation
```bash
# Validate today's data
python scripts/validate_github_data.py

# Validate specific file
python scripts/validate_github_data.py --file sources/github/2025-07-01.json

# Validate with detailed output
python scripts/validate_github_data.py --verbose
```

#### 3. Test AI Summarization
```bash
# Summarize today's data
python -m scripts.summarize_github

# Summarize specific date
python -m scripts.summarize_github --date 2025-07-01

# Force regeneration
python -m scripts.summarize_github --force
```

#### 4. Test Pipeline Integration
```bash
# Run full pipeline with GitHub integration
python scripts/run_pipeline.py full

# Run ingestion only (includes GitHub)
python scripts/run_pipeline.py ingest
```

## Test Scenarios

### Test 1: Environment and Configuration Setup
**Purpose**: Verify all required components are properly configured

**Validates**:
- GitHub token presence in environment
- Configuration file exists and contains GitHub repositories
- Required scripts exist (`github_ingest.py`, `summarize_github.py`, `validate_github_data.py`)

**Expected Results**:
- All environment variables are set
- Configuration file is valid JSON with `github_repositories` section
- All required scripts are present

### Test 2: GitHub API Authentication
**Purpose**: Ensure GitHub API access is working correctly

**Validates**:
- Authentication with GitHub API
- Rate limit status and availability
- Repository access (tests with `kaspanet/rusty-kaspa`)

**Expected Results**:
- Successful authentication with user details
- Adequate rate limit remaining
- Ability to access target repositories

### Test 3: Raw Data Ingestion
**Purpose**: Test the core data ingestion functionality

**Validates**:
- GitHub ingestion command execution
- Output file creation in `sources/github/`
- Data structure validation (repository, commits, pull_requests, issues, metadata)

**Expected Results**:
- JSON file created with current date
- Valid data structure for all configured repositories
- Proper error handling for API issues

### Test 4: Data Validation
**Purpose**: Ensure ingested data meets quality standards

**Validates**:
- JSON schema compliance
- Required field validation
- Data type verification
- Timestamp format validation

**Expected Results**:
- All validation checks pass
- No schema violations
- Proper data types throughout

### Test 5: AI Summarization
**Purpose**: Test AI-powered summary generation

**Validates**:
- AI API availability (OpenRouter)
- Summarization script execution
- Markdown output generation in `sources/github_summaries/`
- Content quality (minimum length check)

**Expected Results**:
- Markdown file created with structured summary
- Content includes repository activity overview
- Proper formatting with sections and emoji

**Note**: This test is skipped if AI API key is not available, with a warning message.

### Test 6: Pipeline Integration
**Purpose**: Validate complete end-to-end pipeline

**Validates**:
- Full pipeline execution with GitHub integration
- Data aggregation including GitHub summaries
- Proper sequencing (Ingestion → Summarization → Aggregation)

**Expected Results**:
- Pipeline completes successfully
- Aggregated data file contains GitHub activity
- GitHub summaries properly integrated into aggregated output

### Test 7: Edge Cases and Error Handling
**Purpose**: Test system robustness and error handling

**Validates**:
- Invalid date format handling
- Missing file error handling
- API failure graceful degradation

**Expected Results**:
- Invalid inputs properly rejected
- Error messages are informative
- System fails gracefully without crashes

## Test Results and Reporting

### Automated Test Results
The test script generates comprehensive results saved to:
```
.taskmaster/test_results/github_integration_test_YYYY-MM-DD.json
```

### Result Structure
```json
{
  "test_started": "2025-07-01T05:00:00Z",
  "test_completed": "2025-07-01T05:05:00Z",
  "tests": {
    "test_name": {
      "status": "PASS|FAIL|WARN",
      "message": "Test result description",
      "details": "Additional context",
      "timestamp": "2025-07-01T05:01:00Z"
    }
  },
  "summary": {
    "total_tests": 15,
    "passed": 14,
    "failed": 0,
    "warnings": 1
  }
}
```

### Success Criteria
- **All Pass**: All tests pass (100% success rate)
- **Mostly Pass**: ≤2 failures (≥87% success rate) - Minor issues
- **Multiple Failures**: >2 failures (<87% success rate) - Requires attention

## Troubleshooting Common Issues

### GitHub Authentication Failures
```bash
# Check token validity
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Verify token scopes (should include 'public_repo')
curl -H "Authorization: token $GITHUB_TOKEN" -I https://api.github.com/user
```

### Rate Limit Issues
```bash
# Check current rate limit
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
```

### Missing Configuration
```bash
# Verify configuration structure
cat config/sources.config.json | jq '.github_repositories'
```

### AI Summarization Issues
```bash
# Test AI API connectivity
curl -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4.1", "messages": [{"role": "user", "content": "test"}]}'
```

## Manual Testing Checklist

For manual verification, follow this checklist:

### Pre-Test Setup
- [ ] Environment variables configured (.env file)
- [ ] GitHub token has appropriate permissions
- [ ] All dependencies installed
- [ ] Configuration file is valid

### Functional Testing
- [ ] GitHub ingestion creates valid JSON files
- [ ] Data validation passes without errors
- [ ] AI summarization generates readable content
- [ ] Pipeline integration includes GitHub data
- [ ] Aggregated output contains GitHub summaries

### Quality Testing
- [ ] Generated summaries are coherent and informative
- [ ] Data structure matches expected schema
- [ ] Error messages are helpful and specific
- [ ] Performance is acceptable (< 2 minutes for full pipeline)

### Integration Testing
- [ ] GitHub data appears in final aggregated output
- [ ] Briefings and facts include GitHub information
- [ ] Pipeline optimization works (skips when no new data)
- [ ] Multiple repository processing works correctly

## Continuous Testing

### Automated Testing in CI/CD
```bash
# Add to CI/CD pipeline
python scripts/test_github_integration.py
if [ $? -eq 0 ]; then
  echo "GitHub integration tests passed"
else
  echo "GitHub integration tests failed"
  exit 1
fi
```

### Regular Health Checks
```bash
# Weekly health check (minimal ingestion)
python -m scripts.github_ingest --days-back 1 --validate

# Monthly full pipeline test
python scripts/test_github_integration.py
```

## Performance Benchmarks

### Expected Performance
- **Ingestion**: < 30 seconds for 4 repositories (1 day of data)
- **Validation**: < 5 seconds for typical daily output
- **AI Summarization**: < 60 seconds for 4 repositories
- **Full Pipeline**: < 2 minutes end-to-end

### Performance Testing
```bash
# Time the ingestion process
time python -m scripts.github_ingest --days-back 1

# Time the full pipeline
time python scripts/run_pipeline.py full
```

## 🛡️ Security Testing

### Token Security
- [ ] GitHub token has minimal required permissions (`public_repo`)
- [ ] Token is not logged or exposed in output
- [ ] Environment variables are properly secured

### Data Privacy
- [ ] Only public repository data is accessed
- [ ] No sensitive information is stored in outputs
- [ ] Generated summaries don't expose private details

---

## Support and Debugging

For issues with the GitHub integration testing:

1. **Check Prerequisites**: Ensure all environment variables and dependencies are set
2. **Run Individual Tests**: Use manual component testing to isolate issues
3. **Review Logs**: Check test results JSON for detailed error information
4. **Verify API Status**: Ensure GitHub and AI APIs are accessible
5. **Check Documentation**: Review GitHub API rate limits and permissions

The comprehensive testing ensures the GitHub integration is robust, reliable, and ready for production use in the Kaspa Knowledge Hub pipeline. 