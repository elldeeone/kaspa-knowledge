"""
Signal Enrichment Service for High-Signal Contributor Weighting System.

This module provides signal enrichment functionality to identify and prioritize
contributions from high-signal sources (core developers, founders, researchers)
in the Kaspa knowledge pipeline.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class SignalEnrichmentService:
    """Service class for enriching data items with high-signal contributor
    metadata."""

    def __init__(self, config_path: str = "config/sources.config.json"):
        """
        Initialize the SignalEnrichmentService.

        Args:
            config_path: Path to the sources configuration file
        """
        self.config_path = Path(config_path)
        self.contributors = self._load_contributors_config()

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

    def reload_config(self) -> None:
        """Reload the contributors configuration (useful for runtime
        updates)."""
        self.contributors = self._load_contributors_config()

    def is_enabled(self) -> bool:
        """Check if signal enrichment is enabled (has contributors
        configured)."""
        return len(self.contributors) > 0

    def enrich_item(self, item: Dict, author_field: str = "author") -> Dict:
        """
        Enrich a data item with high-signal contributor metadata if applicable.

        Args:
            item: The data item to enrich
            author_field: The field name containing the author information

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

        # Check if the item's author matches any contributor aliases
        # (case-insensitive)
        for contributor in self.contributors:
            aliases = contributor.get("aliases", [])
            # Convert both author and aliases to lowercase for
            # case-insensitive matching
            if author.lower() in [alias.lower() for alias in aliases]:
                enriched_item["signal"] = {
                    "strength": "high",
                    "contributor_role": contributor.get("role", "unknown"),
                    "is_lead": contributor.get("is_lead", False),
                    "is_founder": contributor.get("is_founder", False),
                }
                break  # Stop after finding the first match

        return enriched_item

    def enrich_items(
        self, items: List[Dict], author_field: str = "author"
    ) -> List[Dict]:
        """
        Enrich a list of data items with signal metadata.

        Args:
            items: List of data items to enrich
            author_field: The field name containing the author information

        Returns:
            List of enriched items
        """
        if not self.contributors or not items:
            return items

        return [self.enrich_item(item, author_field) for item in items]

    def sort_by_signal_priority(self, items: List[Dict]) -> List[Dict]:
        """
        Sort items by signal priority: lead developers first, then high-signal,
        then standard.

        Args:
            items: List of items to sort

        Returns:
            Sorted list of items
        """

        def signal_priority(item):
            signal = item.get("signal", {})

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

    def analyze_signal_distribution(
        self, data_sources: Dict[str, List]
    ) -> Dict[str, Any]:
        """
        Analyze the distribution of signal metadata across data sources.

        Args:
            data_sources: Dictionary mapping source names to lists of items

        Returns:
            Signal analysis metadata
        """
        signal_stats = {
            "total_items": 0,
            "high_signal_items": 0,
            "lead_developer_items": 0,
            "founder_items": 0,
            "contributor_roles": {},
            "signal_distribution": {"high": 0, "standard": 0},
            "sources_with_signals": {},
        }

        for source_name, items in data_sources.items():
            if not isinstance(items, list):
                continue

            source_stats = {
                "total": len(items),
                "high_signal": 0,
                "lead_developer": 0,
                "founder": 0,
                "roles": {},
            }

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
                else:
                    signal_stats["signal_distribution"]["standard"] += 1

            if (
                source_stats["high_signal"] > 0
                or source_stats["lead_developer"] > 0
                or source_stats["founder"] > 0
            ):
                signal_stats["sources_with_signals"][
                    source_name
                ] = source_stats

        return signal_stats

    def get_contributors_summary(self) -> Dict[str, Any]:
        """
        Get a summary of configured contributors.

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
        }

        for contributor in self.contributors:
            name = contributor.get("name", "Unknown")
            role = contributor.get("role", "unknown")
            is_lead = contributor.get("is_lead", False)
            is_founder = contributor.get("is_founder", False)
            aliases = contributor.get("aliases", [])

            summary["contributors"].append(
                {
                    "name": name,
                    "role": role,
                    "is_lead": is_lead,
                    "is_founder": is_founder,
                    "alias_count": len(aliases),
                }
            )

            # Count roles
            summary["roles"][role] = summary["roles"].get(role, 0) + 1

            # Track lead developers
            if is_lead:
                summary["lead_developers"].append(name)

            # Track founders
            if is_founder:
                summary["founders"].append(name)

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
) -> List[Dict]:
    """
    Convenience function to enrich items with signal metadata.

    Args:
        items: List of items to enrich
        contributors: List of contributors (if None, loads from config)
        config_path: Path to config file (used if contributors is None)

    Returns:
        List of enriched items
    """
    if contributors is not None:
        # Use provided contributors (for backward compatibility)
        service = SignalEnrichmentService.__new__(SignalEnrichmentService)
        service.contributors = contributors
        service.signal_schema = {
            "strength": "high",
            "contributor_role": "",
            "is_lead": False,
        }
        return service.enrich_items(items)
    else:
        # Load from config
        service = SignalEnrichmentService(config_path)
        return service.enrich_items(items)
