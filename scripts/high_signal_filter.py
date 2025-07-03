"""
High-Signal Insight Filtering and Prioritization System

This module provides sophisticated algorithms for identifying, scoring, and prioritizing
high-signal insights from aggregated data sources for RAG optimization.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

# Removed unused import: re

# Configure logging
logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Enumeration of signal strength levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class ContributorRole(Enum):
    """Enumeration of contributor roles with associated weights."""

    FOUNDER = ("founder", 100)
    CORE_DEVELOPER = ("core_developer", 90)
    LEAD = ("lead", 80)
    MAINTAINER = ("maintainer", 70)
    COMMUNITY_CONTRIBUTOR = ("community_contributor", 50)
    CONTRIBUTOR = ("contributor", 30)
    USER = ("user", 10)
    UNKNOWN = ("unknown", 5)

    def __init__(self, role_name: str, weight: int):
        self.role_name = role_name
        self.weight = weight


@dataclass
class SignalScore:
    """Represents a signal score with detailed breakdown."""

    total_score: float
    base_score: float
    contributor_bonus: float
    content_bonus: float
    recency_bonus: float
    impact_bonus: float
    engagement_bonus: float
    signal_strength: SignalStrength
    explanation: List[str] = field(default_factory=list)

    def add_explanation(self, text: str) -> None:
        """Add an explanation for score calculation."""
        self.explanation.append(text)


@dataclass
class FilteredItem:
    """Represents a filtered item with enhanced metadata."""

    original_item: Dict[str, Any]
    source_type: str
    signal_score: SignalScore
    prioritization_rank: int = 0

    @property
    def title(self) -> str:
        """Get item title."""
        return self.original_item.get("title", "Untitled")

    @property
    def author(self) -> str:
        """Get item author."""
        return self.original_item.get("author", "Unknown")

    @property
    def content(self) -> str:
        """Get item content."""
        return self.original_item.get("content", "")

    @property
    def url(self) -> str:
        """Get item URL."""
        return self.original_item.get("url", "")


@dataclass
class FilterConfig:
    """Configuration for high-signal filtering."""

    # Score thresholds
    minimum_score: float = 50.0
    high_signal_threshold: float = 70.0
    critical_signal_threshold: float = 90.0

    # Content scoring weights
    contributor_weight: float = 0.4
    content_weight: float = 0.3
    recency_weight: float = 0.15
    impact_weight: float = 0.1
    engagement_weight: float = 0.05

    # Content analysis parameters
    min_content_length: int = 50
    high_value_keywords: Set[str] = field(
        default_factory=lambda: {
            "security",
            "vulnerability",
            "bug",
            "fix",
            "release",
            "update",
            "breaking",
            "consensus",
            "protocol",
            "upgrade",
            "migration",
            "performance",
            "optimization",
            "announcement",
            "roadmap",
            "milestone",
            "integration",
            "partnership",
        }
    )

    # Filtering options
    max_items_per_category: int = 10
    include_medium_signal: bool = True
    prioritize_recent: bool = True

    # Contributor role mappings
    role_mappings: Dict[str, ContributorRole] = field(
        default_factory=lambda: {
            "founder": ContributorRole.FOUNDER,
            "core_developer": ContributorRole.CORE_DEVELOPER,
            "lead": ContributorRole.LEAD,
            "maintainer": ContributorRole.MAINTAINER,
            "community_contributor": ContributorRole.COMMUNITY_CONTRIBUTOR,
            "contributor": ContributorRole.CONTRIBUTOR,
            "user": ContributorRole.USER,
        }
    )


class HighSignalFilter:
    """Advanced high-signal insight filtering and prioritization system."""

    def __init__(self, config: Optional[FilterConfig] = None):
        """
        Initialize the high-signal filter.

        Args:
            config: Configuration for filtering behavior
        """
        self.config = config or FilterConfig()

    def filter_and_prioritize(
        self, aggregated_data: Dict[str, Any]
    ) -> List[FilteredItem]:
        """
        Filter and prioritize high-signal insights from aggregated data.

        Args:
            aggregated_data: Aggregated data containing sources and signal metadata

        Returns:
            List of filtered and prioritized items
        """
        logger.info("Starting high-signal filtering and prioritization")

        # Extract all items with signal metadata
        all_items = self._extract_signal_items(aggregated_data)
        logger.info(f"Extracted {len(all_items)} items with signal metadata")

        # Score each item
        scored_items = []
        for source_type, item in all_items:
            score = self._calculate_signal_score(item, source_type)
            if score.total_score >= self.config.minimum_score:
                filtered_item = FilteredItem(item, source_type, score)
                scored_items.append(filtered_item)

        logger.info(
            f"Filtered to {len(scored_items)} items above minimum score threshold"
        )

        # Sort by score (highest first)
        scored_items.sort(key=lambda x: x.signal_score.total_score, reverse=True)

        # Apply prioritization ranking
        for i, item in enumerate(scored_items):
            item.prioritization_rank = i + 1

        # Apply category limits if configured
        if self.config.max_items_per_category > 0:
            scored_items = self._apply_category_limits(scored_items)

        logger.info(f"Final filtered set: {len(scored_items)} high-signal items")
        return scored_items

    def _extract_signal_items(
        self, aggregated_data: Dict[str, Any]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Extract items that have signal metadata or can be scored."""
        signal_items = []

        for source_type, items in aggregated_data.get("sources", {}).items():
            if not isinstance(items, list):
                continue

            for item in items:
                # Include items with explicit signal metadata
                if "signal" in item and isinstance(item["signal"], dict):
                    signal_items.append((source_type, item))
                # Fallback: include items that can be scored based on available metadata
                elif self._can_score_item(item, source_type):
                    signal_items.append((source_type, item))

        return signal_items

    def _can_score_item(self, item: Dict[str, Any], source_type: str) -> bool:
        """Check if an item can be scored based on available metadata."""
        # Must have basic required fields
        required_fields = ["title", "author"]
        if not all(field in item for field in required_fields):
            return False

        # Include GitHub activities with meaningful content
        if source_type in ["github_activity", "github_activities"]:
            return True

        # Include other source types with content
        if "content" in item and len(item.get("content", "")) > 20:
            return True

        return False

    def _calculate_signal_score(
        self, item: Dict[str, Any], source_type: str
    ) -> SignalScore:
        """
        Calculate comprehensive signal score for an item.

        Args:
            item: Item data with signal metadata
            source_type: Type of source (github_activities, medium_articles, etc.)

        Returns:
            Detailed signal score
        """
        signal_data = item.get("signal", {})
        if not signal_data:
            signal_data = self._create_fallback_signal_metadata(item, source_type)

        # Base score from existing signal strength
        base_score = self._get_base_score(signal_data)

        # Contributor-based scoring
        contributor_bonus = self._calculate_contributor_score(signal_data)

        # Content quality scoring
        content_bonus = self._calculate_content_score(item)

        # Recency scoring
        recency_bonus = self._calculate_recency_score(item)

        # Impact scoring
        impact_bonus = self._calculate_impact_score(item, source_type)

        # Engagement scoring
        engagement_bonus = self._calculate_engagement_score(item)

        # Calculate weighted total
        total_score = (
            base_score
            + (contributor_bonus * self.config.contributor_weight * 100)
            + (content_bonus * self.config.content_weight * 100)
            + (recency_bonus * self.config.recency_weight * 100)
            + (impact_bonus * self.config.impact_weight * 100)
            + (engagement_bonus * self.config.engagement_weight * 100)
        )

        # Determine signal strength
        if total_score >= self.config.critical_signal_threshold:
            strength = SignalStrength.CRITICAL
        elif total_score >= self.config.high_signal_threshold:
            strength = SignalStrength.HIGH
        elif total_score >= self.config.minimum_score:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.LOW

        # Create score object with explanation
        score = SignalScore(
            total_score=total_score,
            base_score=base_score,
            contributor_bonus=contributor_bonus * self.config.contributor_weight * 100,
            content_bonus=content_bonus * self.config.content_weight * 100,
            recency_bonus=recency_bonus * self.config.recency_weight * 100,
            impact_bonus=impact_bonus * self.config.impact_weight * 100,
            engagement_bonus=engagement_bonus * self.config.engagement_weight * 100,
            signal_strength=strength,
        )

        self._add_score_explanations(score, item, signal_data, source_type)

        return score

    def _create_fallback_signal_metadata(
        self, item: Dict[str, Any], source_type: str
    ) -> Dict[str, Any]:
        """Create fallback signal metadata for items without explicit signal data."""
        fallback_signal = {}

        # Infer contributor role from author and context
        author = item.get("author", "").lower()
        contributor_role = self._infer_contributor_role(author, item, source_type)
        fallback_signal["contributor_role"] = contributor_role

        # Infer signal strength from content and type
        signal_strength = self._infer_signal_strength(item, source_type)
        fallback_signal["strength"] = signal_strength

        # Add source metadata
        fallback_signal["source_type"] = source_type
        fallback_signal["inferred"] = True

        return fallback_signal

    def _infer_contributor_role(
        self, author: str, item: Dict[str, Any], source_type: str
    ) -> str:
        """Infer contributor role from available metadata."""
        # Known core contributors (this could be expanded with a configuration file)
        core_contributors = {
            "someone235": "core_developer",
            "ori newman": "core_developer",
            "freshair18": "maintainer",
            "smartgoo": "contributor",
            "9igeeky": "user",
            "iziodev": "community_contributor",
            "danwt": "community_contributor",
        }

        if author in core_contributors:
            return core_contributors[author]

        # Infer from GitHub activity patterns
        if source_type in ["github_activity", "github_activities"]:
            # Check if it's a major change (many files, high impact)
            if "metadata" in item and isinstance(item["metadata"], dict):
                stats = item["metadata"].get("stats", {})
                files_changed = stats.get("changed_files", 0) or item["metadata"].get(
                    "files_changed", 0
                )

                # Large commits/PRs suggest contributor or higher
                if files_changed > 20:
                    return "contributor"
                elif files_changed > 5:
                    return "community_contributor"

        return "user"

    def _infer_signal_strength(self, item: Dict[str, Any], source_type: str) -> str:
        """Infer signal strength from content and type."""
        content = item.get("content", "").lower()
        title = item.get("title", "").lower()

        # High-impact keywords
        critical_keywords = [
            "security",
            "vulnerability",
            "consensus",
            "protocol",
            "breaking",
        ]
        high_keywords = [
            "release",
            "update",
            "fix",
            "bug",
            "performance",
            "optimization",
        ]
        medium_keywords = ["feature", "improvement", "enhancement", "documentation"]

        combined_text = f"{title} {content}"

        if any(keyword in combined_text for keyword in critical_keywords):
            return "high"
        elif any(keyword in combined_text for keyword in high_keywords):
            return "medium"
        elif any(keyword in combined_text for keyword in medium_keywords):
            return "medium"

        # Default based on source type and activity
        if source_type in ["github_activity", "github_activities"]:
            item_type = item.get("type", "")
            if "commit" in item_type and "merged" in content:
                return "medium"
            elif "pull_request" in item_type:
                return "medium"
            elif "issue" in item_type:
                return "low"

        return "low"

    def _get_base_score(self, signal_data: Dict[str, Any]) -> float:
        """Get base score from signal strength."""
        strength = signal_data.get("strength", "").lower()

        score_map = {"critical": 90.0, "high": 70.0, "medium": 50.0, "low": 30.0}

        return score_map.get(strength, 20.0)

    def _calculate_contributor_score(self, signal_data: Dict[str, Any]) -> float:
        """Calculate score based on contributor role and flags."""
        score = 0.0

        # Role-based scoring
        role = signal_data.get("contributor_role", "unknown").lower()
        if role in self.config.role_mappings:
            contributor_role = self.config.role_mappings[role]
            score += contributor_role.weight / 100.0

        # Special flags
        if signal_data.get("is_founder", False):
            score += 1.0
        elif signal_data.get("is_lead", False):
            score += 0.8

        return min(score, 1.0)  # Cap at 1.0

    def _calculate_content_score(self, item: Dict[str, Any]) -> float:
        """Calculate score based on content quality indicators."""
        content = item.get("content", "")
        title = item.get("title", "")

        score = 0.0

        # Length bonus
        content_length = len(content)
        if content_length >= self.config.min_content_length:
            score += min(content_length / 1000.0, 0.5)  # Up to 0.5 for content length

        # Keyword matching
        text_to_analyze = (title + " " + content).lower()
        keyword_matches = sum(
            1
            for keyword in self.config.high_value_keywords
            if keyword in text_to_analyze
        )

        if keyword_matches > 0:
            score += min(keyword_matches * 0.1, 0.5)  # Up to 0.5 for keywords

        return min(score, 1.0)

    def _calculate_recency_score(self, item: Dict[str, Any]) -> float:
        """Calculate score based on recency."""
        if not self.config.prioritize_recent:
            return 0.0

        date_str = item.get("date", "")
        if not date_str:
            return 0.0

        try:
            # Parse ISO format date
            item_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            now = datetime.now(item_date.tzinfo)

            # Calculate hours since publication
            hours_diff = (now - item_date).total_seconds() / 3600

            # More recent = higher score, decay over time
            if hours_diff <= 24:
                return 1.0  # Within 24 hours
            elif hours_diff <= 168:  # Within 1 week
                return 0.7
            elif hours_diff <= 720:  # Within 1 month
                return 0.4
            else:
                return 0.1

        except (ValueError, TypeError):
            return 0.0

    def _calculate_impact_score(self, item: Dict[str, Any], source_type: str) -> float:
        """Calculate score based on potential impact indicators."""
        score = 0.0

        # Source type impact
        source_impact = {
            "github_activities": 0.9,  # Code changes have high impact
            "medium_articles": 0.7,  # Official articles have good impact
            "news_articles": 0.8,  # News has high visibility
            "forum_posts": 0.6,  # Forum discussions are valuable
            "telegram_messages": 0.4,  # Telegram is more informal
            "discord_messages": 0.3,  # Discord is most informal
            "documentation": 0.8,  # Documentation is important
        }

        score += source_impact.get(source_type, 0.5)

        # GitHub-specific impact indicators
        if source_type == "github_activities":
            metadata = item.get("metadata", {})

            # Large changes have more impact
            stats = metadata.get("stats", {})
            total_changes = stats.get("additions", 0) + stats.get("deletions", 0)
            if total_changes > 100:
                score += 0.3
            elif total_changes > 10:
                score += 0.1

            # Pull requests and issues have impact
            if metadata.get("number"):
                score += 0.2

        return min(score, 1.0)

    def _calculate_engagement_score(self, item: Dict[str, Any]) -> float:
        """Calculate score based on engagement indicators."""
        # This is a placeholder for future engagement metrics
        # Could include: likes, comments, shares, views, etc.
        return 0.0

    def _apply_category_limits(
        self, scored_items: List[FilteredItem]
    ) -> List[FilteredItem]:
        """Apply per-category item limits."""
        category_counts = {}
        filtered_items = []

        for item in scored_items:
            source_type = item.source_type
            count = category_counts.get(source_type, 0)

            if count < self.config.max_items_per_category:
                filtered_items.append(item)
                category_counts[source_type] = count + 1

        return filtered_items

    def _add_score_explanations(
        self,
        score: SignalScore,
        item: Dict[str, Any],
        signal_data: Dict[str, Any],
        source_type: str,
    ) -> None:
        """Add detailed explanations for score calculation."""
        strength = signal_data.get("strength", "unknown")
        score.add_explanation(
            f"Base signal strength: {strength} (+{score.base_score:.1f})"
        )

        role = signal_data.get("contributor_role", "unknown")
        if role != "unknown":
            score.add_explanation(
                f"Contributor role: {role} (+{score.contributor_bonus:.1f})"
            )

        if signal_data.get("is_founder"):
            score.add_explanation("Founder status (+bonus)")
        elif signal_data.get("is_lead"):
            score.add_explanation("Lead status (+bonus)")

        content_length = len(item.get("content", ""))
        if content_length >= self.config.min_content_length:
            score.add_explanation(
                f"Content quality: {content_length} chars (+{score.content_bonus:.1f})"
            )

        if score.recency_bonus > 0:
            score.add_explanation(f"Recency bonus (+{score.recency_bonus:.1f})")

        score.add_explanation(f"Source type: {source_type} (+{score.impact_bonus:.1f})")


def create_default_config() -> FilterConfig:
    """Create a default filter configuration."""
    return FilterConfig()


def filter_high_signal_insights(
    aggregated_data: Dict[str, Any], config: Optional[FilterConfig] = None
) -> List[FilteredItem]:
    """
    Convenience function for filtering high-signal insights.

    Args:
        aggregated_data: Aggregated data containing signal metadata
        config: Optional configuration for filtering

    Returns:
        List of filtered and prioritized high-signal items
    """
    filter_instance = HighSignalFilter(config)
    return filter_instance.filter_and_prioritize(aggregated_data)


if __name__ == "__main__":
    # CLI interface for testing
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="High-signal insight filtering and prioritization"
    )
    parser.add_argument("data_file", help="JSON file containing aggregated data")
    parser.add_argument(
        "--min-score", type=float, default=50.0, help="Minimum signal score"
    )
    parser.add_argument(
        "--max-items", type=int, default=10, help="Maximum items per category"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    try:
        # Load data
        with open(args.data_file, "r") as f:
            data = json.load(f)

        # Configure filter
        config = FilterConfig(
            minimum_score=args.min_score, max_items_per_category=args.max_items
        )

        # Filter insights
        filtered_items = filter_high_signal_insights(data, config)

        # Display results
        print(f"Found {len(filtered_items)} high-signal insights:")
        print("=" * 60)

        for i, item in enumerate(filtered_items[:20], 1):  # Show top 20
            print(f"{i}. {item.title} by {item.author}")
            score_value = item.signal_score.total_score
            strength_value = item.signal_score.signal_strength.value
            print(f"   Score: {score_value:.1f} ({strength_value})")
            print(f"   Source: {item.source_type}")
            if args.verbose:
                print(f"   Explanations: {'; '.join(item.signal_score.explanation)}")
            print()

    except Exception as e:
        logger.error(f"Error processing data: {e}")
        sys.exit(1)
