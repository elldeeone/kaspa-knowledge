# Terah Sync Setup Guide

This guide explains how to set up automated synchronization of Kaspa knowledge base content to the Terah AI agent repository.

## Overview

The Terah sync feature automatically extracts specific content from the Kaspa knowledge base and pushes it to the [terah repository](https://github.com/elldeeone/terah/tree/main/docs) for AI agent consumption.

## GitHub Actions Setup

### Repository Secrets

The Terah sync workflow uses the same secrets that are already configured for your existing ingestion scripts. No additional secrets need to be added if you already have:

1. **GH_TOKEN** - Used for GitHub API access and pushing to the terah repository
2. **DISCOURSE_API_USERNAME** and **DISCOURSE_API_KEY** - For Discourse forum content
3. **TELEGRAM_API_ID** and **TELEGRAM_API_HASH** - For Telegram messages
4. **MEDIUM_RSS_URLS** - For Medium articles

### Important Note About GH_TOKEN

The only requirement is that your existing `GH_TOKEN` must have write access to the terah repository. Since the token owner needs access to push to elldeeone/terah, ensure that:

- The GitHub account that created the token has write access to the terah repository
- The token has the `repo` scope (which it should already have for GitHub ingestion)

## Configuration

The sync behavior is configured in `config/terah_sync.json`:

```json
{
  "output_dir": "../terah/docs",
  "sources": {
    "discourse": {
      "enabled": true,
      "categories": ["l1-l2", "consensus"],
      "forums": ["research.kas.pa"]
    },
    "github": {
      "enabled": true,
      "repos": ["kaspanet/rusty-kaspa", "kaspanet/kaspad"]
    },
    "telegram": {
      "enabled": true,
      "groups": ["all"]
    },
    "medium": {
      "enabled": true,
      "authors": ["all"]
    }
  },
  "sync_interval_days": 7,
  "full_history_on_first_run": true
}
```

## Automated Sync Schedule

The GitHub Action runs:
- **Daily at 2 AM UTC** (automatic)
- **On manual trigger** via GitHub Actions UI

## Manual Sync

You can manually trigger a sync from the GitHub Actions tab:

1. Go to Actions → "Sync to Terah" workflow
2. Click "Run workflow"
3. Optionally select:
   - Specific source to sync (leave empty for all)
   - Force full resync option
4. Click "Run workflow"

## Output Files

Synced files are saved to the terah repository with descriptive names:

- `discourse_research-kas-pa_l1-l2_consensus_2023-01-01_2025-01-10.json`
- `github_rusty-kaspa_kaspad_2024-12-01_2025-01-10.json`
- `telegram_kaspa-groups_2023-01-01_2025-01-10.json`
- `medium_kaspa-authors_2023-01-01_2025-01-10.json`

## Monitoring

- Check the Actions tab for workflow run status
- Sync state is preserved in workflow artifacts
- Each run shows what was synced in the logs

## Troubleshooting

### No changes pushed
- Check if there's actually new content since last sync
- Verify API credentials are set correctly
- Check the workflow logs for errors

### Permission denied errors
- Ensure GH_TOKEN has `repo` scope
- Verify the token hasn't expired
- Check that the token owner has write access to both kaspa-knowledge and terah repos

### Missing content
- Verify the source is enabled in config
- Check that API credentials are set for that source
- Review the specific source filters/categories