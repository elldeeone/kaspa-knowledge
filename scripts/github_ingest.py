#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - GitHub Repository Ingestion

Fetches commits, pull requests, and issues from configured GitHub repositories.
Stage 1 of the two-stage GitHub integration: Raw Data Ingestion.
Follows the three-stage pipeline: Ingest → Aggregate → AI Process
"""

import os
import json
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from github import Github, GithubException
import time

# Load environment variables
load_dotenv()

# Configuration
GITHUB_TOKEN = os.getenv("GH_TOKEN")
CONFIG_PATH = Path("config/sources.config.json")
OUTPUT_DIR = Path("sources/github")

# 🔧 FIX: Configurable API limits - these can be overridden in sources.config.json
DEFAULT_MAX_COMMITS = 100
DEFAULT_MAX_PULL_REQUESTS = 250  # Increased from 100
DEFAULT_MAX_ISSUES = 150  # Increased from 60


def load_github_config():
    """Load GitHub repositories configuration from sources.config.json"""
    if not CONFIG_PATH.exists():
        print(f"❌ Configuration file not found: {CONFIG_PATH}")
        return []

    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        github_repos = config.get("github_repositories", [])
        enabled_repos = [repo for repo in github_repos if repo.get("enabled", True)]

        # 🔧 FIX: Add default limits to repos that don't specify them
        for repo in enabled_repos:
            repo.setdefault("max_commits", DEFAULT_MAX_COMMITS)
            repo.setdefault("max_pull_requests", DEFAULT_MAX_PULL_REQUESTS)
            repo.setdefault("max_issues", DEFAULT_MAX_ISSUES)

        print(f"📋 Loaded {len(enabled_repos)} enabled GitHub repositories from config")
        return enabled_repos

    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Error loading configuration: {e}")
        return []


def authenticate_github():
    """Authenticate with GitHub API using personal access token"""
    if not GITHUB_TOKEN:
        print("❌ GH_TOKEN environment variable not set")
        print("   Please add your GitHub Personal Access Token to .env file")
        print("   Generate one at: https://github.com/settings/tokens")
        return None

    try:
        g = Github(GITHUB_TOKEN)
        # Test authentication by getting rate limit info
        rate_limit = g.get_rate_limit()
        print("✅ GitHub API authenticated successfully")
        print(
            f"   Rate limit: {rate_limit.core.remaining}/"
            f"{rate_limit.core.limit} requests remaining"
        )
        print(f"   Reset time: {rate_limit.core.reset}")
        return g

    except GithubException as e:
        print(f"❌ GitHub authentication failed: {e}")
        return None


def fetch_recent_commits(repo, days_back=7, max_commits=DEFAULT_MAX_COMMITS):
    """Fetch recent commits from a repository"""
    try:
        since_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        commits = repo.get_commits(since=since_date)

        commit_data = []
        commit_count = 0

        for commit in commits:
            if commit_count >= max_commits:  # 🔧 FIX: Use configurable limit
                break

            commit_info = {
                "sha": commit.sha,
                "message": commit.commit.message,
                "author": (
                    commit.commit.author.name if commit.commit.author else "Unknown"
                ),
                "author_email": (
                    commit.commit.author.email if commit.commit.author else "Unknown"
                ),
                "date": (
                    commit.commit.author.date.isoformat()
                    if commit.commit.author
                    else None
                ),
                "url": commit.html_url,
                "stats": {
                    "additions": commit.stats.additions if commit.stats else 0,
                    "deletions": commit.stats.deletions if commit.stats else 0,
                    "total": commit.stats.total if commit.stats else 0,
                },
                "files_changed": (commit.files.totalCount if commit.files else 0),
            }
            commit_data.append(commit_info)
            commit_count += 1

        print(f"   📝 Found {len(commit_data)} recent commits")
        return commit_data

    except GithubException as e:
        print(f"   ⚠️ Error fetching commits: {e}")
        return []


def fetch_recent_pull_requests(
    repo, days_back=30, max_pull_requests=DEFAULT_MAX_PULL_REQUESTS
):
    """Fetch recent pull requests from a repository with optimal filtering"""
    try:
        since_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        print(f"   🔀 Fetching PRs updated since {since_date.strftime('%Y-%m-%d')}...")

        # Get all PRs (open and closed) sorted by update date
        # Note: GitHub API doesn't support 'since' parameter for PRs like it
        # does for issues,
        # but we can still optimize by getting them sorted and breaking early
        all_prs = repo.get_pulls(state="all", sort="updated", direction="desc")

        pr_data = []
        pr_count = 0
        processed_count = 0

        print("   🔀 Processing PRs (will stop when past date threshold)...")
        for pr in all_prs:
            processed_count += 1

            # Early termination: if we encounter a PR older than our date threshold,
            # we can stop since they're sorted by updated date
            if pr.updated_at < since_date:
                print(
                    f"   ⏭️  Reached date threshold after processing "
                    f"{processed_count} PRs"
                )
                break

            if pr_count >= max_pull_requests:  # 🔧 FIX: Use configurable limit
                break

            # Progress indicator for very active repos
            if processed_count > 0 and processed_count % 50 == 0:
                print(
                    f"   📊 Processed {processed_count} PRs, found "
                    f"{pr_count} recent ones..."
                )

            pr_info = {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body or "",
                "state": pr.state,
                "author": pr.user.login if pr.user else "Unknown",
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "merged_at": (pr.merged_at.isoformat() if pr.merged_at else None),
                "url": pr.html_url,
                "draft": pr.draft,
                "mergeable": pr.mergeable,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "commits": pr.commits,
                "labels": ([label.name for label in pr.labels] if pr.labels else []),
            }
            pr_data.append(pr_info)
            pr_count += 1

        print(f"   🔀 Found {len(pr_data)} recent pull requests")
        return pr_data

    except GithubException as e:
        print(f"   ⚠️ Error fetching pull requests: {e}")
        return []


def fetch_recent_issues(repo, days_back=30, max_issues=DEFAULT_MAX_ISSUES):
    """Fetch recent issues from a repository using API-side filtering"""
    try:
        since_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        print(
            f"   📋 Fetching issues updated since {since_date.strftime('%Y-%m-%d')}..."
        )

        # Use GitHub API's built-in filtering with 'since' parameter
        # This filters server-side, dramatically reducing API calls and processing time
        all_recent_issues = repo.get_issues(
            state="all",  # Get both open and closed
            since=since_date,  # Server-side date filtering!
            sort="updated",
            direction="desc",
        )

        issue_data = []
        issue_count = 0

        print("   📋 Processing filtered issues...")
        for issue in all_recent_issues:
            if issue_count >= max_issues:  # 🔧 FIX: Use configurable limit
                break

            # Skip pull requests (they show up in issues API)
            if issue.pull_request:
                continue

            # Progress indicator (much less needed now!)
            if issue_count > 0 and issue_count % 10 == 0:
                print(f"   📊 Processed {issue_count} recent issues so far...")

            issue_info = {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body or "",
                "state": issue.state,
                "author": issue.user.login if issue.user else "Unknown",
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
                "closed_at": (issue.closed_at.isoformat() if issue.closed_at else None),
                "url": issue.html_url,
                "labels": (
                    [label.name for label in issue.labels] if issue.labels else []
                ),
                "assignees": (
                    [assignee.login for assignee in issue.assignees]
                    if issue.assignees
                    else []
                ),
                "comments": issue.comments,
            }
            issue_data.append(issue_info)
            issue_count += 1

        print(f"   🐛 Found {len(issue_data)} recent issues")
        return issue_data

    except GithubException as e:
        print(f"   ⚠️ Error fetching issues: {e}")
        return []


def fetch_repository_data(github_client, repo_config, days_back=7):
    """Fetch all data for a single repository"""
    owner = repo_config["owner"]
    repo_name = repo_config["repo"]
    repo_full_name = f"{owner}/{repo_name}"

    print(f"\n🔍 Processing repository: {repo_full_name}")

    try:
        repo = github_client.get_repo(repo_full_name)

        # Verify repository exists and is accessible
        print(
            f"   📊 Repository info: {repo.full_name} "
            f"({repo.description or 'No description'})"
        )
        print(f"   ⭐ Stars: {repo.stargazers_count}, Forks: {repo.forks_count}")

        # Fetch different types of data with configurable limits
        commits = fetch_recent_commits(
            repo, days_back, repo_config.get("max_commits", DEFAULT_MAX_COMMITS)
        )
        pull_requests = fetch_recent_pull_requests(
            repo,
            days_back,
            repo_config.get("max_pull_requests", DEFAULT_MAX_PULL_REQUESTS),
        )
        issues = fetch_recent_issues(
            repo, days_back, repo_config.get("max_issues", DEFAULT_MAX_ISSUES)
        )

        # Aggregate repository data
        repo_data = {
            "repository": {
                "owner": owner,
                "name": repo_name,
                "full_name": repo_full_name,
                "description": repo.description,
                "url": repo.html_url,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "language": repo.language,
                "updated_at": repo.updated_at.isoformat(),
                "created_at": repo.created_at.isoformat(),
            },
            "commits": commits,
            "pull_requests": pull_requests,
            "issues": issues,
            "metadata": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "days_back": days_back,
                "total_items": len(commits) + len(pull_requests) + len(issues),
            },
        }

        return repo_data

    except GithubException as e:
        print(f"   ❌ Error accessing repository {repo_full_name}: {e}")
        return None


def get_existing_github_data():
    """
    Cross-file deduplication: Load all existing GitHub data from all files.
    Returns a dictionary with unique identifiers for O(1) lookup performance.
    """
    existing_data = {"commits": set(), "pull_requests": set(), "issues": set()}

    if not OUTPUT_DIR.exists():
        return existing_data

    # Get all JSON files in the github directory
    json_files = list(OUTPUT_DIR.glob("*.json"))

    if not json_files:
        return existing_data

    print(f"🔍 Checking for existing GitHub data across {len(json_files)} files...")

    total_existing = 0
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Handle both new format (dict with repo names) and old format (list)
                if isinstance(data, dict):
                    # New format: iterate through repositories
                    for repo_name, repo_data in data.items():
                        if isinstance(repo_data, dict):
                            # Process commits
                            for commit in repo_data.get("commits", []):
                                if isinstance(commit, dict) and "sha" in commit:
                                    existing_data["commits"].add(commit["sha"])
                                    total_existing += 1

                            # Process pull requests
                            for pr in repo_data.get("pull_requests", []):
                                if isinstance(pr, dict) and "number" in pr:
                                    # Use repo_name + PR number as unique identifier
                                    existing_data["pull_requests"].add(
                                        f"{repo_name}#{pr['number']}"
                                    )
                                    total_existing += 1

                            # Process issues
                            for issue in repo_data.get("issues", []):
                                if isinstance(issue, dict) and "number" in issue:
                                    # Use repo_name + issue number as unique identifier
                                    existing_data["issues"].add(
                                        f"{repo_name}#{issue['number']}"
                                    )
                                    total_existing += 1

        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Warning: Could not read {file_path}: {e}")
            continue

    print(f"📚 Found {total_existing} existing GitHub items for deduplication check")
    return existing_data


def filter_new_github_data(all_repo_data, existing_data):
    """
    Filter out GitHub data that already exists in our database.
    Returns only genuinely new data.
    """
    if not existing_data or not any(existing_data.values()):
        return all_repo_data

    filtered_data = {}

    for repo_name, repo_data in all_repo_data.items():
        if not isinstance(repo_data, dict):
            continue

        filtered_repo_data = {}

        # Filter commits
        if "commits" in repo_data:
            new_commits = []
            for commit in repo_data["commits"]:
                if isinstance(commit, dict) and "sha" in commit:
                    if commit["sha"] not in existing_data["commits"]:
                        new_commits.append(commit)
            filtered_repo_data["commits"] = new_commits

        # Filter pull requests
        if "pull_requests" in repo_data:
            new_prs = []
            for pr in repo_data["pull_requests"]:
                if isinstance(pr, dict) and "number" in pr:
                    pr_key = f"{repo_name}#{pr['number']}"
                    if pr_key not in existing_data["pull_requests"]:
                        new_prs.append(pr)
            filtered_repo_data["pull_requests"] = new_prs

        # Filter issues
        if "issues" in repo_data:
            new_issues = []
            for issue in repo_data["issues"]:
                if isinstance(issue, dict) and "number" in issue:
                    issue_key = f"{repo_name}#{issue['number']}"
                    if issue_key not in existing_data["issues"]:
                        new_issues.append(issue)
            filtered_repo_data["issues"] = new_issues

        # Only include repo if it has new data
        if any(filtered_repo_data.values()):
            filtered_data[repo_name] = filtered_repo_data

    return filtered_data


def check_existing_data(date=None):
    """Check if GitHub data already exists for the given date"""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    output_file = OUTPUT_DIR / f"{date}.json"
    return output_file.exists()


def save_github_data(all_repo_data, date=None, full_history=False):
    """Save raw GitHub data to JSON file"""
    if full_history:
        date_str = "full_history"
    elif date is not None:
        date_str = date
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / f"{date_str}.json"

    # Create final data structure
    final_data = {}
    for repo_name, repo_data in all_repo_data.items():
        if repo_data:  # Only include successful fetches
            final_data[repo_name] = repo_data

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Saved GitHub data to: {output_file}")
        print(f"   📊 Repositories processed: {len(final_data)}")

        # Summary stats
        total_commits = sum(
            len(data.get("commits", [])) for data in final_data.values()
        )
        total_prs = sum(
            len(data.get("pull_requests", [])) for data in final_data.values()
        )
        total_issues = sum(len(data.get("issues", [])) for data in final_data.values())
        print(
            f"   📝 Total items: {total_commits} commits, {total_prs} PRs, "
            f"{total_issues} issues"
        )

    except IOError as e:
        print(f"❌ Error saving GitHub data: {e}")


def main():
    """Main ingestion function"""
    parser = argparse.ArgumentParser(
        description="Ingest GitHub repository data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.github_ingest                    # Daily sync (dated file)
  python -m scripts.github_ingest --full-history     # Backfill (full_history.json)
  python -m scripts.github_ingest --days-back 30     # Fetch last 30 days of data
  python -m scripts.github_ingest --force            # Force processing

The difference between modes is in output filename and intended usage: daily sync for
regular operations, full-history for comprehensive backfill operations.
        """,
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="Number of days back to fetch data (default: 7, automatically "
        "set to 730 in backfill mode)",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Specific date to use for output file (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--full-history",
        action="store_true",
        help="Backfill mode - saves to 'full_history.json' for comprehensive data collection",  # noqa: E501
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force processing even if data already exists (bypass deduplication)",  # noqa: E501
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation after ingestion to verify data quality",
    )

    args = parser.parse_args()

    # 🔧 FIX: Auto-set days_back for backfill mode if not explicitly specified
    if args.full_history and args.days_back == 7:  # Default value
        args.days_back = 730  # 2 years for comprehensive backfill
        print(
            f"🔧 Full history mode: Auto-increased days_back to "
            f"{args.days_back} days (2 years)"
        )

    print("🚀 Starting GitHub repository ingestion...")

    if args.full_history:
        print(
            "📚 Full history mode: Comprehensive backfill from GitHub repositories"
        )  # noqa: E501
        print(f"   📅 Fetching data from the last {args.days_back} days")
    else:
        print("📰 Daily sync mode: Standard GitHub repository processing")
        print(f"   📅 Fetching data from the last {args.days_back} days")

    # Get existing data for cross-file deduplication (unless force flag is used)
    existing_data = {}
    if not args.force:
        existing_data = get_existing_github_data()

    if args.force:
        print("⚠️  Force flag used - bypassing deduplication checks")

    # Load configuration
    repo_configs = load_github_config()
    if not repo_configs:
        print("❌ No repositories configured or configuration error")
        return

    # Authenticate with GitHub
    github_client = authenticate_github()
    if not github_client:
        print("❌ GitHub authentication failed")
        return

    # Fetch data from all repositories
    all_repo_data = {}

    for repo_config in repo_configs:
        repo_name = f"{repo_config['owner']}/{repo_config['repo']}"
        repo_data = fetch_repository_data(github_client, repo_config, args.days_back)
        all_repo_data[repo_name] = repo_data

        # Small delay to be respectful to the API
        time.sleep(0.5)

    # Filter out existing data (unless force flag is used)
    if not args.force:
        filtered_data = filter_new_github_data(all_repo_data, existing_data)

        # Check if any new data was found
        total_new_items = 0
        for repo_data in filtered_data.values():
            total_new_items += (
                len(repo_data.get("commits", []))
                + len(repo_data.get("pull_requests", []))
                + len(repo_data.get("issues", []))
            )

        if total_new_items == 0:
            print("\n🎯 Smart deduplication result:")
            print(f"   - Repositories processed: {len(all_repo_data)}")

            total_fetched = 0
            for repo_data in all_repo_data.values():
                if repo_data:
                    total_fetched += (
                        len(repo_data.get("commits", []))
                        + len(repo_data.get("pull_requests", []))
                        + len(repo_data.get("issues", []))
                    )

            print(f"   - Total items fetched: {total_fetched}")
            print("   - New items (not in database): 0")
            print("\n✨ No new GitHub data found - saving empty file with metadata!")
            print("ℹ️  Use --force flag to bypass deduplication if needed.")

            # Save empty file with metadata for consistency
            save_github_data({}, args.date, args.full_history)

            import sys

            sys.exit(2)  # Exit code 2 indicates "no new content"

        final_data = filtered_data
    else:
        print("⚠️  Force flag used - bypassing deduplication checks")
        final_data = all_repo_data

    # Save all data
    save_github_data(final_data, args.date, args.full_history)

    # Optional validation step
    if args.validate:
        print("\n🔍 Running data validation...")
        try:
            from validate_github_data import GitHubDataValidator

            validator = GitHubDataValidator()
            if args.full_history:
                output_file = OUTPUT_DIR / "full_history.json"
            else:
                date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                output_file = OUTPUT_DIR / f"{date_str}.json"

            if output_file.exists():
                validation_success = validator.validate_file(output_file)
                validator.print_summary()

                if validation_success:
                    print("✅ Data validation passed!")
                else:
                    print("❌ Data validation failed - check output above")
            else:
                print(f"⚠️  Output file not found for validation: {output_file}")

        except ImportError:
            print(
                "⚠️  Validation module not found. "
                "Run: python scripts/validate_github_data.py"
            )
        except Exception as e:
            print(f"⚠️  Validation error: {e}")

    print("\n🎉 GitHub ingestion completed successfully!")


if __name__ == "__main__":
    main()
