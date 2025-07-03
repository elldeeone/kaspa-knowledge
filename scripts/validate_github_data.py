#!/usr/bin/env python3
"""
Kaspa Knowledge Hub - GitHub Data Validation

Validates the structure and completeness of GitHub ingestion JSON files.
Ensures data quality for downstream processing and AI summarization.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

# Expected schema structure
REQUIRED_REPO_FIELDS = {
    "repository": {
        "owner": str,
        "name": str,
        "full_name": str,
        "description": (str, type(None)),
        "url": str,
        "stars": int,
        "forks": int,
        "language": (str, type(None)),
        "updated_at": str,
        "created_at": str,
    },
    "commits": list,
    "pull_requests": list,
    "issues": list,
    "metadata": {"fetched_at": str, "days_back": int, "total_items": int},
}


class GitHubDataValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.stats = {
            "files_validated": 0,
            "repositories_validated": 0,
            "commits_validated": 0,
            "pull_requests_validated": 0,
            "issues_validated": 0,
            "total_errors": 0,
            "total_warnings": 0,
        }

    def log_error(self, message: str, context: str = ""):
        error_msg = f"❌ ERROR: {message}"
        if context:
            error_msg += f" (Context: {context})"
        self.errors.append(error_msg)
        print(error_msg)

    def log_warning(self, message: str, context: str = ""):
        warning_msg = f"⚠️  WARNING: {message}"
        if context:
            warning_msg += f" (Context: {context})"
        self.warnings.append(warning_msg)
        print(warning_msg)

    def log_info(self, message: str):
        print(f"ℹ️  {message}")

    def validate_iso_timestamp(
        self, timestamp: str, field_name: str, context: str
    ) -> bool:
        """Validate ISO 8601 timestamp format"""
        if not timestamp:
            return True  # Allow null timestamps for optional fields

        try:
            # Try to parse the timestamp
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return True
        except ValueError:
            self.log_error(
                f"Invalid timestamp format in {field_name}: {timestamp}",
                context,
            )
            return False

    def validate_required_fields(
        self, data: Dict, required_fields: Dict, context: str
    ) -> bool:
        """Validate that all required fields are present and have correct types"""
        valid = True

        for field_name, expected_type in required_fields.items():
            if field_name not in data:
                self.log_error(f"Missing required field: {field_name}", context)
                valid = False
                continue

            if isinstance(expected_type, dict):
                # Nested object validation
                if not isinstance(data[field_name], dict):
                    self.log_error(f"Field {field_name} should be an object", context)
                    valid = False
                else:
                    nested_valid = self.validate_required_fields(
                        data[field_name],
                        expected_type,
                        f"{context}.{field_name}",
                    )
                    valid = valid and nested_valid
            else:
                # Simple field validation
                if isinstance(expected_type, tuple):
                    # Handle optional fields (e.g., (str, type(None)))
                    if type(data[field_name]) not in expected_type:
                        self.log_error(
                            f"Field {field_name} has incorrect type. "
                            f"Expected {expected_type}, got {type(data[field_name])}",
                            context,
                        )
                        valid = False
                else:
                    if not isinstance(data[field_name], expected_type):
                        self.log_error(
                            f"Field {field_name} has incorrect type. "
                            f"Expected {expected_type}, got {type(data[field_name])}",
                            context,
                        )
                        valid = False

                # Special validation for timestamp fields
                if field_name.endswith("_at") and data[field_name] is not None:
                    timestamp_valid = self.validate_iso_timestamp(
                        data[field_name], field_name, context
                    )
                    valid = valid and timestamp_valid

        return valid

    def validate_repository_data(self, repo_data: Dict, repo_name: str) -> bool:
        """Validate a complete repository data object"""
        self.log_info(f"Validating repository: {repo_name}")

        # Validate top-level structure
        valid = self.validate_required_fields(
            repo_data, REQUIRED_REPO_FIELDS, repo_name
        )

        # Count items
        if "commits" in repo_data:
            self.stats["commits_validated"] += len(repo_data["commits"])
        if "pull_requests" in repo_data:
            self.stats["pull_requests_validated"] += len(repo_data["pull_requests"])
        if "issues" in repo_data:
            self.stats["issues_validated"] += len(repo_data["issues"])

        self.stats["repositories_validated"] += 1
        return valid

    def validate_file(self, file_path: Path) -> bool:
        """Validate a single GitHub JSON file"""
        self.log_info(f"📂 Validating file: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.log_error(f"Invalid JSON in file {file_path}: {e}")
            return False
        except IOError as e:
            self.log_error(f"Cannot read file {file_path}: {e}")
            return False

        if not isinstance(data, dict):
            self.log_error(
                f"Root data should be an object, got {type(data)}",
                str(file_path),
            )
            return False

        if not data:
            self.log_warning("File contains no repository data", str(file_path))
            return True

        file_valid = True
        for repo_name, repo_data in data.items():
            if not isinstance(repo_data, dict):
                self.log_error(
                    f"Repository data should be an object, got {type(repo_data)}",
                    f"{file_path}:{repo_name}",
                )
                file_valid = False
                continue

            repo_valid = self.validate_repository_data(repo_data, repo_name)
            file_valid = file_valid and repo_valid

        self.stats["files_validated"] += 1
        return file_valid

    def validate_directory(self, directory: Path) -> bool:
        """Validate all JSON files in the GitHub sources directory"""
        if not directory.exists():
            self.log_error(f"Directory does not exist: {directory}")
            return False

        json_files = list(directory.glob("*.json"))
        if not json_files:
            self.log_warning(f"No JSON files found in directory: {directory}")
            return True

        self.log_info(f"🔍 Found {len(json_files)} JSON files to validate")

        overall_valid = True
        for json_file in sorted(json_files):
            file_valid = self.validate_file(json_file)
            overall_valid = overall_valid and file_valid

        return overall_valid

    def print_summary(self):
        """Print validation summary"""
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)

        print(f"Files validated: {self.stats['files_validated']}")
        print(f"Repositories validated: {self.stats['repositories_validated']}")
        print(f"Commits validated: {self.stats['commits_validated']}")
        print(f"Pull requests validated: {self.stats['pull_requests_validated']}")
        print(f"Issues validated: {self.stats['issues_validated']}")

        self.stats["total_errors"] = len(self.errors)
        self.stats["total_warnings"] = len(self.warnings)

        print(f"\n❌ Total errors: {self.stats['total_errors']}")
        print(f"⚠️  Total warnings: {self.stats['total_warnings']}")

        if self.stats["total_errors"] == 0:
            print("\n✅ All validations passed!")
        else:
            print(f"\n❌ Validation failed with {self.stats['total_errors']} errors")

        return self.stats["total_errors"] == 0


def main():
    """Main validation function"""
    parser = argparse.ArgumentParser(description="Validate GitHub ingestion JSON files")
    parser.add_argument(
        "--directory",
        type=str,
        default="sources/github",
        help="Directory containing GitHub JSON files (default: sources/github)",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Validate a specific file instead of entire directory",
    )

    args = parser.parse_args()

    validator = GitHubDataValidator()

    print("🔍 Starting GitHub data validation...")

    if args.file:
        # Validate single file
        file_path = Path(args.file)
        validator.validate_file(file_path)
    else:
        # Validate entire directory
        directory = Path(args.directory)
        validator.validate_directory(directory)

    # Print summary
    overall_success = validator.print_summary()

    # Exit with appropriate code
    exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()
