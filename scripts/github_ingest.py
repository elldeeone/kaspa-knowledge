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


def fetch_recent_commits(repo, days_back=7):
    """Fetch recent commits from a repository"""
    try:
        since_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        commits = repo.get_commits(since=since_date)

        commit_data = []
        commit_count = 0

        for commit in commits:
            if commit_count >= 100:  # Limit to prevent excessive API calls
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


def fetch_recent_pull_requests(repo, days_back=30):
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

            if pr_count >= 100:  # Safety limit
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


def fetch_recent_issues(repo, days_back=30):
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
            if issue_count >= 60:  # Total limit to prevent excessive data
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

        # Fetch different types of data
        commits = fetch_recent_commits(repo, days_back)
        pull_requests = fetch_recent_pull_requests(repo, days_back)
        issues = fetch_recent_issues(repo, days_back)

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


def check_existing_data(date=None):
    """Check if GitHub data already exists for the given date"""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    output_file = OUTPUT_DIR / f"{date}.json"
    return output_file.exists()


def save_github_data(all_repo_data, date=None):
    """Save raw GitHub data to JSON file"""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / f"{date}.json"

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
    parser = argparse.ArgumentParser(description="Ingest GitHub repository data")
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="Number of days back to fetch data (default: 7)",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Specific date to use for output file (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force processing even if data already exists (bypass deduplication)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation after ingestion to verify data quality",
    )

    args = parser.parse_args()

    print("🚀 Starting GitHub repository ingestion...")
    print(f"   📅 Fetching data from the last {args.days_back} days")

    # Check for existing data (smart deduplication)
    target_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if check_existing_data(target_date) and not args.force:
        print(f"📋 GitHub data already exists for {target_date}")
        print("⚡ Skipping ingestion to avoid duplicates")
        print("ℹ️  Use --force flag to override this behavior")

        # Use existing data
        output_file = OUTPUT_DIR / f"{target_date}.json"
        print("\n💾 Using existing GitHub data")
        print(f"   📁 {output_file}")

        print(
            "\nℹ️  GitHub Repository Ingestion found existing content - "
            "skipping downstream processing"
        )
        print("\n🎯 GitHub ingestion skipped - using existing data")
        print("\n✅ GitHub Repository Ingestion completed successfully")

        import sys

        sys.exit(2)  # Exit code 2 indicates "no new content"

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

    # Save all data
    save_github_data(all_repo_data, args.date)

    # Optional validation step
    if args.validate:
        print("\n🔍 Running data validation...")
        try:
            from validate_github_data import GitHubDataValidator

            validator = GitHubDataValidator()
            output_file = (
                OUTPUT_DIR
                / f"{args.date or datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
            )

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
