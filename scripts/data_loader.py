"""
JSON Data Loader and Validator for RAG Document Generation

This module provides robust loading and validation capabilities for the three
primary data sources: aggregated data, briefings, and facts.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import re

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a data validation error."""

    source_file: str
    error_type: str
    message: str
    field_path: Optional[str] = None
    severity: str = "error"  # error, warning, info


@dataclass
class DataValidationResult:
    """Results of data validation process."""

    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    loaded_data: Optional[Dict[str, Any]] = None

    def add_error(
        self,
        source_file: str,
        error_type: str,
        message: str,
        field_path: Optional[str] = None,
    ):
        """Add a validation error."""
        self.errors.append(
            ValidationError(source_file, error_type, message, field_path, "error")
        )
        self.is_valid = False

    def add_warning(
        self,
        source_file: str,
        error_type: str,
        message: str,
        field_path: Optional[str] = None,
    ):
        """Add a validation warning."""
        self.warnings.append(
            ValidationError(source_file, error_type, message, field_path, "warning")
        )


@dataclass
class LoadedData:
    """Container for all loaded and validated data."""

    date: str
    aggregated_data: Optional[Dict[str, Any]] = None
    briefings_data: Optional[Dict[str, Any]] = None
    facts_data: Optional[Dict[str, Any]] = None
    validation_results: Dict[str, DataValidationResult] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        """Check if any source has validation errors."""
        return any(not result.is_valid for result in self.validation_results.values())

    @property
    def has_warnings(self) -> bool:
        """Check if any source has validation warnings."""
        return any(result.warnings for result in self.validation_results.values())

    def get_available_sources(self) -> List[str]:
        """Get list of successfully loaded data sources."""
        sources = []
        if self.aggregated_data is not None:
            sources.append("aggregated")
        if self.briefings_data is not None:
            sources.append("briefings")
        if self.facts_data is not None:
            sources.append("facts")
        return sources


class JSONDataLoader:
    """Robust JSON data loader with comprehensive validation."""

    def __init__(self, data_directory: str = "data"):
        """
        Initialize the data loader.

        Args:
            data_directory: Base directory containing the data subdirectories
        """
        self.data_dir = Path(data_directory)
        self.aggregated_dir = self.data_dir / "aggregated"
        self.briefings_dir = self.data_dir / "briefings"
        self.facts_dir = self.data_dir / "facts"

        # Ensure directories exist
        self._validate_directory_structure()

    def _validate_directory_structure(self) -> None:
        """Validate that required directories exist."""
        for dir_path, name in [
            (self.aggregated_dir, "aggregated"),
            (self.briefings_dir, "briefings"),
            (self.facts_dir, "facts"),
        ]:
            if not dir_path.exists():
                logger.warning(f"Directory '{name}' does not exist at {dir_path}")
            elif not dir_path.is_dir():
                raise ValueError(f"Path '{dir_path}' exists but is not a directory")

    def load_data_for_date(self, date: str) -> LoadedData:
        """
        Load and validate all data sources for a specific date.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            LoadedData object containing all loaded data and validation results
        """
        if not self._validate_date_format(date):
            raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD")

        logger.info(f"Loading data for date: {date}")

        loaded_data = LoadedData(date=date)

        # Load each data source
        self._load_aggregated_data(date, loaded_data)
        self._load_briefings_data(date, loaded_data)
        self._load_facts_data(date, loaded_data)

        # Log summary
        self._log_loading_summary(loaded_data)

        return loaded_data

    def _validate_date_format(self, date: str) -> bool:
        """Validate date format (YYYY-MM-DD)."""
        pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(pattern, date):
            return False

        try:
            datetime.strptime(date, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _load_aggregated_data(self, date: str, loaded_data: LoadedData) -> None:
        """Load and validate aggregated data."""
        file_path = self.aggregated_dir / f"{date}.json"
        source_name = "aggregated"

        result = self._load_and_validate_json_file(file_path, source_name)
        loaded_data.validation_results[source_name] = result

        if result.is_valid and result.loaded_data:
            loaded_data.aggregated_data = result.loaded_data
            self._validate_aggregated_schema(result.loaded_data, result, str(file_path))

    def _load_briefings_data(self, date: str, loaded_data: LoadedData) -> None:
        """Load and validate briefings data."""
        file_path = self.briefings_dir / f"{date}.json"
        source_name = "briefings"

        result = self._load_and_validate_json_file(file_path, source_name)
        loaded_data.validation_results[source_name] = result

        if result.is_valid and result.loaded_data:
            loaded_data.briefings_data = result.loaded_data
            self._validate_briefings_schema(result.loaded_data, result, str(file_path))

    def _load_facts_data(self, date: str, loaded_data: LoadedData) -> None:
        """Load and validate facts data."""
        file_path = self.facts_dir / f"{date}.json"
        source_name = "facts"

        result = self._load_and_validate_json_file(file_path, source_name)
        loaded_data.validation_results[source_name] = result

        if result.is_valid and result.loaded_data:
            loaded_data.facts_data = result.loaded_data
            self._validate_facts_schema(result.loaded_data, result, str(file_path))

    def _load_and_validate_json_file(
        self, file_path: Path, source_name: str
    ) -> DataValidationResult:
        """Load and perform basic validation on a JSON file."""
        result = DataValidationResult(is_valid=True)

        # Check if file exists
        if not file_path.exists():
            result.add_error(
                str(file_path), "file_missing", f"File does not exist: {file_path}"
            )
            return result

        # Try to load JSON
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            result.loaded_data = data
            logger.debug(f"Successfully loaded {source_name} data from {file_path}")
        except json.JSONDecodeError as e:
            result.add_error(
                str(file_path), "json_parse_error", f"Invalid JSON format: {e}"
            )
            return result
        except Exception as e:
            result.add_error(
                str(file_path), "file_read_error", f"Error reading file: {e}"
            )
            return result

        # Basic structure validation
        if not isinstance(data, dict):
            result.add_error(
                str(file_path),
                "invalid_structure",
                "Root element must be a JSON object",
            )
            return result

        return result

    def _validate_aggregated_schema(
        self, data: Dict[str, Any], result: DataValidationResult, file_path: str
    ) -> None:
        """Validate aggregated data schema."""
        # Required fields
        required_fields = ["date", "generated_at", "sources", "metadata"]
        for field_name in required_fields:
            if field_name not in data:
                result.add_error(
                    file_path, "missing_field", f"Required field missing: {field_name}"
                )

        # Validate date field
        if "date" in data:
            if not isinstance(data["date"], str) or not self._validate_date_format(
                data["date"]
            ):
                result.add_error(
                    file_path, "invalid_date", "Date field must be in YYYY-MM-DD format"
                )

        # Validate sources structure
        if "sources" in data:
            if not isinstance(data["sources"], dict):
                result.add_error(
                    file_path, "invalid_sources", "Sources field must be an object"
                )
            else:
                self._validate_sources_structure(data["sources"], result, file_path)

        # Validate metadata
        if "metadata" in data:
            if not isinstance(data["metadata"], dict):
                result.add_error(
                    file_path, "invalid_metadata", "Metadata field must be an object"
                )
            else:
                self._validate_aggregated_metadata(data["metadata"], result, file_path)

    def _validate_sources_structure(
        self, sources: Dict[str, Any], result: DataValidationResult, file_path: str
    ) -> None:
        """Validate the sources structure in aggregated data."""
        expected_source_types = [
            "github_activities",
            "medium_articles",
            "telegram_messages",
            "discord_messages",
            "forum_posts",
            "news_articles",
            "documentation",
        ]

        for source_type in expected_source_types:
            if source_type in sources:
                if not isinstance(sources[source_type], list):
                    result.add_warning(
                        file_path,
                        "invalid_source_type",
                        f"Source '{source_type}' should be a list",
                    )
                else:
                    # Validate individual items
                    self._validate_source_items(
                        sources[source_type], source_type, result, file_path
                    )

    def _validate_source_items(
        self,
        items: List[Any],
        source_type: str,
        result: DataValidationResult,
        file_path: str,
    ) -> None:
        """Validate individual items within a source type."""
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                result.add_warning(
                    file_path,
                    "invalid_item",
                    f"Item {i} in {source_type} is not an object",
                )
                continue

            # Check for common required fields
            common_fields = ["type", "title", "author", "url", "date", "content"]
            for field_name in common_fields:
                if field_name not in item:
                    result.add_warning(
                        file_path,
                        "missing_item_field",
                        f"Item {i} in {source_type} missing field: {field_name}",
                    )

            # Validate signal metadata if present
            if "signal" in item:
                self._validate_signal_metadata(
                    item["signal"], result, file_path, f"{source_type}[{i}].signal"
                )

    def _validate_signal_metadata(
        self,
        signal: Dict[str, Any],
        result: DataValidationResult,
        file_path: str,
        field_path: str,
    ) -> None:
        """Validate signal metadata structure."""
        required_signal_fields = ["strength", "contributor_role"]
        for field_name in required_signal_fields:
            if field_name not in signal:
                result.add_warning(
                    file_path,
                    "missing_signal_field",
                    f"Signal metadata missing field: {field_name} at {field_path}",
                )

        # Validate signal strength values
        if "strength" in signal:
            valid_strengths = ["high", "medium", "low"]
            if signal["strength"] not in valid_strengths:
                result.add_warning(
                    file_path,
                    "invalid_signal_strength",
                    f"Invalid signal strength '{signal['strength']}' at {field_path}",
                )

    def _validate_aggregated_metadata(
        self, metadata: Dict[str, Any], result: DataValidationResult, file_path: str
    ) -> None:
        """Validate aggregated data metadata."""
        expected_fields = ["total_items", "processing_time", "pipeline_version"]
        for field_name in expected_fields:
            if field_name not in metadata:
                result.add_warning(
                    file_path,
                    "missing_metadata_field",
                    f"Metadata missing field: {field_name}",
                )

    def _validate_briefings_schema(
        self, data: Dict[str, Any], result: DataValidationResult, file_path: str
    ) -> None:
        """Validate briefings data schema."""
        # Required fields
        required_fields = ["date", "generated_at", "sources", "metadata"]
        for field_name in required_fields:
            if field_name not in data:
                result.add_error(
                    file_path, "missing_field", f"Required field missing: {field_name}"
                )

        # Validate date
        if "date" in data and not self._validate_date_format(data["date"]):
            result.add_error(
                file_path, "invalid_date", "Date field must be in YYYY-MM-DD format"
            )

        # Validate sources structure
        if "sources" in data and isinstance(data["sources"], dict):
            source_types = ["medium", "github", "telegram", "discord", "forum", "news"]
            for source_type in source_types:
                if source_type in data["sources"]:
                    source_data = data["sources"][source_type]
                    if not isinstance(source_data, dict):
                        result.add_warning(
                            file_path,
                            "invalid_source_structure",
                            f"Source '{source_type}' should be an object",
                        )
                    elif "summary" not in source_data:
                        result.add_warning(
                            file_path,
                            "missing_summary",
                            f"Source '{source_type}' missing summary field",
                        )

    def _validate_facts_schema(
        self, data: Dict[str, Any], result: DataValidationResult, file_path: str
    ) -> None:
        """Validate facts data schema."""
        # Required fields
        required_fields = ["date", "generated_at", "facts", "statistics", "metadata"]
        for field_name in required_fields:
            if field_name not in data:
                result.add_error(
                    file_path, "missing_field", f"Required field missing: {field_name}"
                )

        # Validate date
        if "date" in data and not self._validate_date_format(data["date"]):
            result.add_error(
                file_path, "invalid_date", "Date field must be in YYYY-MM-DD format"
            )

        # Validate facts array
        if "facts" in data:
            if not isinstance(data["facts"], list):
                result.add_error(
                    file_path, "invalid_facts", "Facts field must be an array"
                )
            else:
                self._validate_individual_facts(data["facts"], result, file_path)

        # Validate statistics
        if "statistics" in data and isinstance(data["statistics"], dict):
            expected_stats = ["total_facts", "by_category", "by_impact", "by_source"]
            for stat in expected_stats:
                if stat not in data["statistics"]:
                    result.add_warning(
                        file_path,
                        "missing_statistic",
                        f"Statistics missing field: {stat}",
                    )

    def _validate_individual_facts(
        self, facts: List[Any], result: DataValidationResult, file_path: str
    ) -> None:
        """Validate individual fact entries."""
        for i, fact in enumerate(facts):
            if not isinstance(fact, dict):
                result.add_warning(
                    file_path, "invalid_fact", f"Fact {i} is not an object"
                )
                continue

            # Required fact fields
            required_fact_fields = [
                "fact",
                "category",
                "impact",
                "context",
                "source",
                "extracted_at",
            ]
            for field_name in required_fact_fields:
                if field_name not in fact:
                    result.add_warning(
                        file_path,
                        "missing_fact_field",
                        f"Fact {i} missing field: {field_name}",
                    )

            # Validate impact levels
            if "impact" in fact:
                valid_impacts = ["high", "medium", "low"]
                if fact["impact"] not in valid_impacts:
                    result.add_warning(
                        file_path,
                        "invalid_impact",
                        f"Fact {i} has invalid impact level: {fact['impact']}",
                    )

            # Validate source structure
            if "source" in fact and isinstance(fact["source"], dict):
                source_fields = ["type", "title", "author", "url", "date"]
                for field_name in source_fields:
                    if field_name not in fact["source"]:
                        result.add_warning(
                            file_path,
                            "missing_source_field",
                            f"Fact {i} source missing field: {field_name}",
                        )

    def _log_loading_summary(self, loaded_data: LoadedData) -> None:
        """Log a summary of the loading results."""
        available_sources = loaded_data.get_available_sources()
        logger.info(f"Data loading summary for {loaded_data.date}:")
        sources_text = ", ".join(available_sources) if available_sources else "None"
        logger.info(f"  Available sources: {sources_text}")

        if loaded_data.has_errors:
            total_errors = sum(
                len(result.errors) for result in loaded_data.validation_results.values()
            )
            logger.warning(f"  Total validation errors: {total_errors}")

        if loaded_data.has_warnings:
            total_warnings = sum(
                len(result.warnings)
                for result in loaded_data.validation_results.values()
            )
            logger.info(f"  Total validation warnings: {total_warnings}")

        # Log specific issues
        for source_name, result in loaded_data.validation_results.items():
            if result.errors:
                logger.error(f"  {source_name}: {len(result.errors)} errors")
                for error in result.errors[:3]:  # Show first 3 errors
                    logger.error(f"    - {error.error_type}: {error.message}")
                if len(result.errors) > 3:
                    logger.error(f"    ... and {len(result.errors) - 3} more errors")

            if result.warnings:
                logger.warning(f"  {source_name}: {len(result.warnings)} warnings")


def validate_and_load_data(date: str, data_directory: str = "data") -> LoadedData:
    """
    Convenience function to load and validate data for a specific date.

    Args:
        date: Date string in YYYY-MM-DD format
        data_directory: Base directory containing data subdirectories

    Returns:
        LoadedData object with validation results

    Raises:
        ValueError: If date format is invalid
    """
    loader = JSONDataLoader(data_directory)
    return loader.load_data_for_date(date)


if __name__ == "__main__":
    import sys

    # Simple CLI for testing
    if len(sys.argv) != 2:
        print("Usage: python data_loader.py YYYY-MM-DD")
        sys.exit(1)

    date = sys.argv[1]

    # Configure logging for CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        data = validate_and_load_data(date)
        print(f"\nLoading completed for {date}")
        print(f"Available sources: {', '.join(data.get_available_sources())}")

        if data.has_errors:
            print("\n❌ Validation errors found:")
            for source, result in data.validation_results.items():
                for error in result.errors:
                    print(f"  {source}: {error.error_type} - {error.message}")

        if data.has_warnings:
            print("\n⚠️  Validation warnings:")
            for source, result in data.validation_results.items():
                for warning in result.warnings:
                    print(f"  {source}: {warning.error_type} - {warning.message}")

        if not data.has_errors and not data.has_warnings:
            print("\n✅ All data loaded successfully with no issues")

    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        sys.exit(1)
