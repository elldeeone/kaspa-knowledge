"""
Signal Enrichment Service for High-Signal Contributor Weighting System.

This module provides signal enrichment functionality to identify and prioritize
contributions from high-signal sources (core developers, founders, researchers)
in the Kaspa knowledge pipeline.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


class SignalEnrichmentService:
    """Service class for enriching data items with high-signal contributor
    metadata and intelligent scoring."""

    def __init__(self, config_path: str = "config/sources.config.json"):
        """
        Initialize the SignalEnrichmentService.

        Args:
            config_path: Path to the sources configuration file
        """
        self.config_path = Path(config_path)
        self.contributors = self._load_contributors_config()
        self.scoring_config = self._load_scoring_config()

        # Default signal schema - can be extended
        self.signal_schema = {
            "strength": "high",
            "contributor_role": "",
            "is_lead": False,
        }

    def _load_contributors_config(self) -> List[Dict]:
        """Load high-signal contributors configuration from config file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            contributors = config.get("high_signal_contributors", [])
            print(f"📋 Loaded {len(contributors)} high-signal contributors")
            return contributors
        except FileNotFoundError:
            print(
                f"⚠️  Warning: {self.config_path} not found - "
                "no contributor weighting applied"
            )
            return []
        except Exception as e:
            print(f"⚠️  Warning: Error loading contributors config: {e}")
            return []

    def _load_scoring_config(self) -> Dict[str, Any]:
        """Load scoring configuration from config file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            scoring_config = config.get("scoring_config", {})
            if scoring_config.get("enabled", False):
                formula_desc = scoring_config.get("formula", {}).get(
                    "description", "N/A"
                )
                print(f"🧮 Scoring system enabled with formula: {formula_desc}")
            else:
                print("🧮 Scoring system disabled")
            return scoring_config
        except Exception as e:
            print(f"⚠️  Warning: Error loading scoring config: {e}")
            return {"enabled": False}

    def reload_config(self) -> None:
        """Reload the contributors and scoring configuration (useful for runtime
        updates)."""
        self.contributors = self._load_contributors_config()
        self.scoring_config = self._load_scoring_config()

    def is_enabled(self) -> bool:
        """Check if signal enrichment is enabled (has contributors
        configured)."""
        return len(self.contributors) > 0

    def is_scoring_enabled(self) -> bool:
        """Check if scoring system is enabled."""
        return self.scoring_config.get("enabled", False)

    def calculate_recency_weight(self, publication_date: Union[str, datetime]) -> float:
        """
        Calculate recency weight based on publication date using exponential decay.

        Args:
            publication_date: Publication date as string or datetime object

        Returns:
            Recency weight between 0.0 and 1.0
        """
        if not self.is_scoring_enabled():
            return 1.0

        try:
            # Parse publication date if it's a string
            if isinstance(publication_date, str):
                # Try common date formats
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S%z",  # ISO format with timezone
                    "%Y-%m-%dT%H:%M:%SZ",  # ISO format UTC
                    "%Y-%m-%dT%H:%M:%S",  # ISO format without timezone
                    "%Y-%m-%d %H:%M:%S",  # Standard format
                    "%Y-%m-%d",  # Date only
                ]:
                    try:
                        pub_date = datetime.strptime(publication_date, fmt)
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    # If no format worked, return default weight
                    return 1.0
            else:
                pub_date = publication_date
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)

            # Calculate age in days
            now = datetime.now(timezone.utc)
            age_days = (now - pub_date).days

            # Get decay configuration
            decay_config = self.scoring_config.get("recency_decay", {})
            if not decay_config.get("enabled", True):
                return 1.0

            max_age = decay_config.get("max_age_days", 365)
            half_life = decay_config.get("half_life_days", 90)

            # Cap age at max_age
            age_days = min(age_days, max_age)

            # Calculate exponential decay: weight = 0.5^(age_days / half_life)
            if age_days <= 0:
                return 1.0

            recency_weight = 0.5 ** (age_days / half_life)
            return max(0.0, min(1.0, recency_weight))

        except Exception as e:
            print(f"⚠️  Warning: Error calculating recency weight: {e}")
            return 1.0

    def get_author_weight(self, author: str) -> float:
        """
        Get author weight based on contributor configuration.

        Args:
            author: Author name to look up

        Returns:
            Author weight between 0.0 and 1.0
        """
        if not self.contributors:
            return self.scoring_config.get("weight_ranges", {}).get("default", 0.30)

        # Check if the author matches any contributor aliases (case-insensitive)
        for contributor in self.contributors:
            aliases = contributor.get("aliases", [])
            if author.lower() in [alias.lower() for alias in aliases]:
                return contributor.get("weight", 0.30)

        # Return default weight if no match found
        return self.scoring_config.get("weight_ranges", {}).get("default", 0.30)

    def calculate_final_score(
        self, author_weight: float, recency_weight: float
    ) -> float:
        """
        Calculate final score using the configured formula.

        Args:
            author_weight: Weight based on author authority (0.0-1.0)
            recency_weight: Weight based on content recency (0.0-1.0)

        Returns:
            Final score between 0.0 and 1.0
        """
        if not self.is_scoring_enabled():
            return author_weight  # Fallback to author weight only

        formula = self.scoring_config.get("formula", {})
        author_factor = formula.get("author_weight_factor", 0.7)
        recency_factor = formula.get("recency_weight_factor", 0.3)

        # Calculate final score: (author_weight * 0.7) + (recency_weight * 0.3)
        final_score = (author_weight * author_factor) + (
            recency_weight * recency_factor
        )

        # Ensure score is between 0.0 and 1.0
        return max(0.0, min(1.0, final_score))

    def enrich_item(
        self, item: Dict, author_field: str = "author", date_field: str = "date"
    ) -> Dict:
        """
        Enrich a data item with high-signal contributor metadata and scoring.

        Args:
            item: The data item to enrich
            author_field: The field name containing the author information
            date_field: The field name containing the publication date

        Returns:
            The enriched item (original item is not modified)
        """
        if not self.contributors:
            return item

        author = item.get(author_field)
        if not author:
            return item

        # Create a copy to avoid modifying the original item
        enriched_item = item.copy()

        # Get author weight
        author_weight = self.get_author_weight(author)

        # Calculate recency weight
        pub_date = item.get(date_field)
        recency_weight = self.calculate_recency_weight(pub_date) if pub_date else 1.0

        # Calculate final score
        final_score = self.calculate_final_score(author_weight, recency_weight)

        # Check if the item's author matches any contributor aliases
        # (case-insensitive)
        for contributor in self.contributors:
            aliases = contributor.get("aliases", [])
            if author.lower() in [alias.lower() for alias in aliases]:
                enriched_item["signal"] = {
                    "strength": "high",
                    "contributor_role": contributor.get("role", "unknown"),
                    "is_lead": contributor.get("is_lead", False),
                    "is_founder": contributor.get("is_founder", False),
                    "author_weight": author_weight,
                    "recency_weight": recency_weight,
                    "final_score": final_score,
                }
                break  # Stop after finding the first match
        else:
            # Even if not a high-signal contributor, add scoring information
            if self.is_scoring_enabled():
                enriched_item["signal"] = {
                    "strength": "standard",
                    "contributor_role": "contributor",
                    "is_lead": False,
                    "is_founder": False,
                    "author_weight": author_weight,
                    "recency_weight": recency_weight,
                    "final_score": final_score,
                }

        return enriched_item

    def enrich_items(
        self, items: List[Dict], author_field: str = "author", date_field: str = "date"
    ) -> List[Dict]:
        """
        Enrich a list of data items with signal metadata and scoring.

        Args:
            items: List of data items to enrich
            author_field: The field name containing the author information
            date_field: The field name containing the publication date

        Returns:
            List of enriched items
        """
        if not self.contributors or not items:
            return items

        return [self.enrich_item(item, author_field, date_field) for item in items]

    def sort_by_signal_priority(self, items: List[Dict]) -> List[Dict]:
        """
        Sort items by signal priority using final_score when available,
        falling back to role-based priority.

        Args:
            items: List of items to sort

        Returns:
            Sorted list of items (highest scores first)
        """

        def signal_priority(item):
            signal = item.get("signal", {})

            # If scoring is enabled and final_score is available, use it
            if self.is_scoring_enabled() and "final_score" in signal:
                # Return negative score for descending order (highest first)
                return -signal["final_score"]

            # Fallback to role-based priority for backward compatibility
            # Lead developers and founders get highest priority (1)
            if signal.get("is_lead") or signal.get("is_founder"):
                return 1
            # High-signal contributors get second priority (2)
            elif signal.get("strength") == "high":
                return 2
            # Standard items get lowest priority (3)
            else:
                return 3

        return sorted(items, key=signal_priority)

    def sort_by_final_score(self, items: List[Dict]) -> List[Dict]:
        """
        Sort items by final_score in descending order (highest scores first).

        Args:
            items: List of items to sort

        Returns:
            Sorted list of items
        """

        def get_final_score(item):
            signal = item.get("signal", {})
            return signal.get("final_score", 0.0)

        return sorted(items, key=get_final_score, reverse=True)

    def get_items_by_score_threshold(
        self, items: List[Dict], threshold: float
    ) -> List[Dict]:
        """
        Filter items by final_score threshold.

        Args:
            items: List of items to filter
            threshold: Minimum score threshold

        Returns:
            Filtered list of items
        """
        return [
            item
            for item in items
            if item.get("signal", {}).get("final_score", 0.0) >= threshold
        ]

    def categorize_items_by_score(self, items: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Categorize items by score ranges for tiered processing.

        Args:
            items: List of items to categorize

        Returns:
            Dictionary with categorized items
        """
        categories = {
            "top_insights": [],  # >0.85
            "recent_developments": [],  # 0.70-0.85
            "from_archive": [],  # <0.40
            "standard": [],  # 0.40-0.70
        }

        for item in items:
            score = item.get("signal", {}).get("final_score", 0.0)

            if score > 0.85:
                categories["top_insights"].append(item)
            elif score >= 0.70:
                categories["recent_developments"].append(item)
            elif score < 0.40:
                categories["from_archive"].append(item)
            else:
                categories["standard"].append(item)

        return categories

    def analyze_signal_distribution(
        self, data_sources: Dict[str, List]
    ) -> Dict[str, Any]:
        """
        Analyze the distribution of signal metadata and scoring across data sources.

        Args:
            data_sources: Dictionary mapping source names to lists of items

        Returns:
            Signal analysis metadata including scoring statistics
        """
        signal_stats = {
            "total_items": 0,
            "high_signal_items": 0,
            "lead_developer_items": 0,
            "founder_items": 0,
            "contributor_roles": {},
            "signal_distribution": {"high": 0, "standard": 0},
            "sources_with_signals": {},
            "scoring_enabled": self.is_scoring_enabled(),
            "scoring_stats": {
                "items_with_scores": 0,
                "average_score": 0.0,
                "score_distribution": {
                    "top_insights": 0,  # >0.85
                    "recent_developments": 0,  # 0.70-0.85
                    "standard": 0,  # 0.40-0.70
                    "from_archive": 0,  # <0.40
                },
                "average_author_weight": 0.0,
                "average_recency_weight": 0.0,
            },
        }

        total_scores = 0.0
        total_author_weights = 0.0
        total_recency_weights = 0.0
        scored_items = 0

        for source_name, items in data_sources.items():
            if not isinstance(items, list):
                continue

            source_stats = {
                "total": len(items),
                "high_signal": 0,
                "lead_developer": 0,
                "founder": 0,
                "roles": {},
                "average_score": 0.0,
                "score_distribution": {
                    "top_insights": 0,
                    "recent_developments": 0,
                    "standard": 0,
                    "from_archive": 0,
                },
            }

            source_total_score = 0.0
            source_scored_items = 0

            for item in items:
                signal_stats["total_items"] += 1
                signal = item.get("signal")

                if signal:
                    if signal.get("strength") == "high":
                        signal_stats["high_signal_items"] += 1
                        source_stats["high_signal"] += 1
                        signal_stats["signal_distribution"]["high"] += 1

                    if signal.get("is_lead"):
                        signal_stats["lead_developer_items"] += 1
                        source_stats["lead_developer"] += 1

                    if signal.get("is_founder"):
                        signal_stats["founder_items"] += 1
                        source_stats["founder"] += 1

                    role = signal.get("contributor_role")
                    if role:
                        signal_stats["contributor_roles"][role] = (
                            signal_stats["contributor_roles"].get(role, 0) + 1
                        )
                        source_stats["roles"][role] = (
                            source_stats["roles"].get(role, 0) + 1
                        )

                    # Scoring statistics
                    if "final_score" in signal:
                        score = signal["final_score"]
                        total_scores += score
                        source_total_score += score
                        scored_items += 1
                        source_scored_items += 1
                        signal_stats["scoring_stats"]["items_with_scores"] += 1

                        # Score distribution
                        if score > 0.85:
                            signal_stats["scoring_stats"]["score_distribution"][
                                "top_insights"
                            ] += 1
                            source_stats["score_distribution"]["top_insights"] += 1
                        elif score >= 0.70:
                            signal_stats["scoring_stats"]["score_distribution"][
                                "recent_developments"
                            ] += 1
                            source_stats["score_distribution"][
                                "recent_developments"
                            ] += 1
                        elif score < 0.40:
                            signal_stats["scoring_stats"]["score_distribution"][
                                "from_archive"
                            ] += 1
                            source_stats["score_distribution"]["from_archive"] += 1
                        else:
                            signal_stats["scoring_stats"]["score_distribution"][
                                "standard"
                            ] += 1
                            source_stats["score_distribution"]["standard"] += 1

                        # Author and recency weights
                        if "author_weight" in signal:
                            total_author_weights += signal["author_weight"]
                        if "recency_weight" in signal:
                            total_recency_weights += signal["recency_weight"]

                else:
                    signal_stats["signal_distribution"]["standard"] += 1

            # Calculate source average score
            if source_scored_items > 0:
                source_stats["average_score"] = source_total_score / source_scored_items

            if (
                source_stats["high_signal"] > 0
                or source_stats["lead_developer"] > 0
                or source_stats["founder"] > 0
                or source_scored_items > 0
            ):
                signal_stats["sources_with_signals"][source_name] = source_stats

        # Calculate overall scoring averages
        if scored_items > 0:
            signal_stats["scoring_stats"]["average_score"] = total_scores / scored_items
            signal_stats["average_final_score"] = total_scores / scored_items
            signal_stats["max_final_score"] = max(
                (
                    item.get("signal", {}).get("final_score", 0.0)
                    for source_items in data_sources.values()
                    for item in source_items
                    if isinstance(source_items, list)
                ),
                default=0.0,
            )
            signal_stats["scoring_stats"]["average_author_weight"] = (
                total_author_weights / scored_items
            )
            signal_stats["scoring_stats"]["average_recency_weight"] = (
                total_recency_weights / scored_items
            )

        return signal_stats

    def get_contributors_summary(self) -> Dict[str, Any]:
        """
        Get a summary of configured contributors including scoring information.

        Returns:
            Summary information about configured contributors
        """
        if not self.contributors:
            return {"enabled": False, "count": 0}

        summary = {
            "enabled": True,
            "count": len(self.contributors),
            "contributors": [],
            "roles": {},
            "lead_developers": [],
            "founders": [],
            "scoring_enabled": self.is_scoring_enabled(),
            "weight_distribution": {
                "min_weight": 1.0,
                "max_weight": 0.0,
                "average_weight": 0.0,
                "weights_by_role": {},
            },
        }

        total_weight = 0.0

        for contributor in self.contributors:
            name = contributor.get("name", "Unknown")
            role = contributor.get("role", "unknown")
            is_lead = contributor.get("is_lead", False)
            is_founder = contributor.get("is_founder", False)
            aliases = contributor.get("aliases", [])
            weight = contributor.get("weight", 0.30)

            summary["contributors"].append(
                {
                    "name": name,
                    "role": role,
                    "is_lead": is_lead,
                    "is_founder": is_founder,
                    "alias_count": len(aliases),
                    "weight": weight,
                }
            )

            # Weight statistics
            total_weight += weight
            summary["weight_distribution"]["min_weight"] = min(
                summary["weight_distribution"]["min_weight"], weight
            )
            summary["weight_distribution"]["max_weight"] = max(
                summary["weight_distribution"]["max_weight"], weight
            )

            # Weight by role
            if role not in summary["weight_distribution"]["weights_by_role"]:
                summary["weight_distribution"]["weights_by_role"][role] = {
                    "weights": [],
                    "average": 0.0,
                    "count": 0,
                }
            summary["weight_distribution"]["weights_by_role"][role]["weights"].append(
                weight
            )
            summary["weight_distribution"]["weights_by_role"][role]["count"] += 1

            # Count roles
            summary["roles"][role] = summary["roles"].get(role, 0) + 1

            # Track lead developers
            if is_lead:
                summary["lead_developers"].append(name)

            # Track founders
            if is_founder:
                summary["founders"].append(name)

        # Calculate averages
        if len(self.contributors) > 0:
            summary["weight_distribution"]["average_weight"] = total_weight / len(
                self.contributors
            )

        # Calculate role averages
        for role_data in summary["weight_distribution"]["weights_by_role"].values():
            if role_data["count"] > 0:
                role_data["average"] = sum(role_data["weights"]) / role_data["count"]

        return summary


# Convenience functions for backward compatibility
def create_signal_service(
    config_path: str = "config/sources.config.json",
) -> SignalEnrichmentService:
    """Create a SignalEnrichmentService instance."""
    return SignalEnrichmentService(config_path)


def enrich_items_with_signal(
    items: List[Dict],
    contributors: Optional[List[Dict]] = None,
    config_path: str = "config/sources.config.json",
    author_field: str = "author",
    date_field: str = "date",
) -> List[Dict]:
    """
    Convenience function to enrich items with signal metadata and scoring.

    Args:
        items: List of items to enrich
        contributors: List of contributors (if None, loads from config)
        config_path: Path to config file (used if contributors is None)
        author_field: Field name containing author information
        date_field: Field name containing publication date

    Returns:
        List of enriched items
    """
    if contributors is not None:
        # Use provided contributors (for backward compatibility)
        service = SignalEnrichmentService.__new__(SignalEnrichmentService)
        service.contributors = contributors
        service.scoring_config = {"enabled": False}  # Disable scoring for legacy mode
        service.signal_schema = {
            "strength": "high",
            "contributor_role": "",
            "is_lead": False,
        }
        return service.enrich_items(items, author_field, date_field)
    else:
        # Load from config
        service = SignalEnrichmentService(config_path)
        return service.enrich_items(items, author_field, date_field)
