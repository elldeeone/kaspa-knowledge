#!/usr/bin/env python3
"""
RAG Document Generation Script

This script integrates all components of the Canonical Ingestion Document system
to generate semantically structured Markdown documents optimized for RAG systems.

It combines:
- JSON data loading and validation (data_loader.py)
- Markdown template generation (markdown_template_generator.py)
- High-signal filtering (high_signal_filter.py)
- Error handling and validation (error_handler.py)

Usage:
    python scripts/generate_rag_document.py [--date YYYY-MM-DD] [--force] \\
    [--organization comprehensive|prioritized|minimal]

Examples:
    python scripts/generate_rag_document.py
    # Process today's data with prioritized organization
    python scripts/generate_rag_document.py --date 2025-07-01
    # Process specific date
    python scripts/generate_rag_document.py --force
    # Force overwrite existing files
    python scripts/generate_rag_document.py --organization comprehensive
    # Include all content in original order
    python scripts/generate_rag_document.py --organization minimal
    # Most selective, high-signal content only
"""

import argparse
import sys
import tempfile
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# Add the scripts directory to Python path for imports
scripts_dir = Path(__file__).parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

# Import local modules
from data_loader import JSONDataLoader  # noqa: E402
from markdown_template_generator import MarkdownTemplateGenerator  # noqa: E402
from high_signal_filter import HighSignalFilter, FilterConfig  # noqa: E402
from error_handler import (  # noqa: E402
    create_pipeline_logger,
    create_error_handler,
    create_validator,
    run_with_error_handling,
    ErrorSeverity,
    ErrorCategory,
)


def validate_date_format(date_string: str) -> bool:
    """Validate date string in YYYY-MM-DD, period-based format, or 'full_history'."""
    # Allow 'full_history' for backfill mode
    if date_string == "full_history":
        return True

    # Try standard daily format first
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        pass

    # Try period-based formats
    period_patterns = [
        "%Y-%m-monthly",  # 2025-01-monthly
        "%Y-%m-%d-weekly",  # 2025-01-15-weekly
        "%Y-%m-quarterly",  # 2025-01-quarterly
        "%Y-%m-%d-historical",  # 2025-01-15-historical
    ]

    for pattern in period_patterns:
        try:
            # Extract the base date part and validate it
            if pattern.endswith("-monthly") or pattern.endswith("-quarterly"):
                # Monthly/quarterly: validate YYYY-MM part
                base_date = date_string.split("-")[0] + "-" + date_string.split("-")[1]
                datetime.strptime(base_date, "%Y-%m")
                return True
            elif pattern.endswith("-weekly") or pattern.endswith("-historical"):
                # Weekly/historical: validate YYYY-MM-DD part
                base_date = "-".join(date_string.split("-")[0:3])
                datetime.strptime(base_date, "%Y-%m-%d")
                return True
        except (ValueError, IndexError):
            continue

    return False


def extract_period_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract period-specific metadata from aggregated data."""
    metadata = {}

    # Extract period information
    metadata["period_label"] = data.get("period", "Unknown Period")
    metadata["date_range"] = data.get("date_range", "Unknown Range")

    # Parse date range for start and end dates
    date_range = metadata["date_range"]
    if " to " in date_range:
        start_date, end_date = date_range.split(" to ")
        metadata["start_date"] = start_date.strip()
        metadata["end_date"] = end_date.strip()

        # Calculate duration in days
        try:
            start = datetime.strptime(start_date.strip(), "%Y-%m-%d")
            end = datetime.strptime(end_date.strip(), "%Y-%m-%d")
            metadata["duration_days"] = (end - start).days + 1
        except ValueError:
            metadata["duration_days"] = "Unknown"
    else:
        metadata["start_date"] = "Unknown"
        metadata["end_date"] = "Unknown"
        metadata["duration_days"] = "Unknown"

    # Count total items across all sources
    sources = data.get("sources", {})
    total_items = 0
    sources_processed = []

    for source_name, source_data in sources.items():
        if source_data and len(source_data) > 0:
            total_items += len(source_data)
            sources_processed.append(source_name)

    metadata["total_items"] = total_items
    metadata["sources_processed"] = ", ".join(sources_processed)

    return metadata


def load_period_based_data(
    date: str, data_dir: Path, period_summary: bool = False
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Load period-based data files following the same pattern as extract_facts.py.

    Args:
        date: Date string (could be period-based format)
        data_dir: Directory containing source data
        period_summary: Whether to look for period-based files

    Returns:
        Tuple of (LoadedData object or None, error_message or None)
    """
    if not period_summary:
        # Use standard data loader for daily data
        data_loader = JSONDataLoader(str(data_dir))
        try:
            loaded_data = data_loader.load_data_for_date(date)
            return loaded_data, None
        except Exception as e:
            return None, f"Failed to load daily data: {str(e)}"

    # For period-based data, we need to handle different file patterns
    aggregated_dir = data_dir / "aggregated"
    briefings_dir = data_dir / "briefings"
    facts_dir = data_dir / "facts"

    # Try different period-based file patterns
    period_patterns = [
        f"{date}.json",  # Direct match first
        f"{date}-monthly.json",  # Monthly pattern
        f"{date}-weekly.json",  # Weekly pattern
        f"{date}-quarterly.json",  # Quarterly pattern
        f"{date}-historical.json",  # Historical pattern
    ]

    # Try to find aggregated data file
    aggregated_data = None
    aggregated_path = None
    for pattern in period_patterns:
        potential_path = aggregated_dir / pattern
        if potential_path.exists():
            aggregated_path = potential_path
            break

    if aggregated_path is None:
        return (
            None,
            f"No period-based aggregated data found for {date}. "
            f"Checked patterns: {period_patterns}",
        )

    try:
        # Load aggregated data
        with open(aggregated_path, "r", encoding="utf-8") as f:
            aggregated_data = json.load(f)

        # Try to load briefings data (optional)
        briefings_data = None
        for pattern in period_patterns:
            briefings_path = briefings_dir / pattern
            if briefings_path.exists():
                with open(briefings_path, "r", encoding="utf-8") as f:
                    briefings_data = json.load(f)
                break

        # Try to load facts data (optional)
        facts_data = None
        for pattern in period_patterns:
            facts_path = facts_dir / pattern
            if facts_path.exists():
                with open(facts_path, "r", encoding="utf-8") as f:
                    facts_data = json.load(f)
                break

        # Create a LoadedData-like object
        from data_loader import LoadedData

        loaded_data = LoadedData(
            date=date,
            aggregated_data=aggregated_data,
            briefings_data=briefings_data,
            facts_data=facts_data,
        )

        return loaded_data, None

    except Exception as e:
        return None, f"Failed to load period-based data: {str(e)}"


def generate_rag_document(
    date: str,
    force: bool = False,
    organization_style: str = "prioritized",
    data_dir: Path = Path("data"),
    output_dir: Path = Path("knowledge_base"),
    split_output: bool = False,
    period_summary: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Generate a single, well-organized RAG document from daily or period-based JSON data.

    Args:
        date: Date string in YYYY-MM-DD format or period-based format
            (e.g., "2025-01-monthly", "2025-01-15-weekly")
        force: Whether to overwrite existing files
        organization_style: How to organize content
            ("comprehensive", "prioritized", "minimal")
        data_dir: Directory containing source data
        output_dir: Directory for output files
        split_output: Whether to split output into multiple files by section
        period_summary: Whether to process period-based data files instead of daily

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Create necessary directories
        output_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging and error handling
        logger = create_pipeline_logger("INFO")
        error_handler = create_error_handler(logger)

        # Set output file path (single file, no dual versions)
        output_file = output_dir / f"{date}.md"

        # Check if file exists and handle force flag
        if output_file.exists() and not force:
            error = error_handler.create_error(
                f"Output file already exists: {output_file}. Use --force to overwrite.",
                ErrorSeverity.MEDIUM,
                ErrorCategory.FILE_OPERATIONS,
                component="file_checker",
            )
            return False, error.message

        logger.logger.info(f"Starting RAG document generation for date: {date}")
        logger.logger.info(f"Organization style: {organization_style}")
        logger.logger.info(
            f"Processing mode: {'period-based' if period_summary else 'daily'}"
        )

        # Step 1: Validate data directory structure
        logger.logger.info("Validating data directory structure...")
        data_validator = create_validator(error_handler)
        validation_result = data_validator.validate_data_directory(data_dir)
        is_valid = validation_result.is_valid

        if not is_valid:
            error_messages = [error.message for error in validation_result.errors]
            return (
                False,
                f"Data directory validation failed: {'; '.join(error_messages)}",
            )

        # Step 2: Load and validate JSON data
        logger.logger.info("Loading and validating JSON data...")

        # Use period-aware data loading
        loaded_data, load_error_msg = load_period_based_data(
            date, data_dir, period_summary
        )

        if load_error_msg or not loaded_data:
            error_msg = load_error_msg if load_error_msg else "Failed to load data"
            return False, error_msg

        logger.logger.info(f"Successfully loaded data for {date}")
        if loaded_data.aggregated_data:
            source_count = len(loaded_data.aggregated_data.get("sources", {}))
            logger.logger.info(f"  - Aggregated: {source_count} sources")
        if loaded_data.briefings_data:
            source_count = len(loaded_data.briefings_data.get("sources", {}))
            logger.logger.info(f"  - Briefings: {source_count} summaries")
        if loaded_data.facts_data:
            facts_count = len(loaded_data.facts_data.get("facts", []))
            logger.logger.info(f"  - Facts: {facts_count} facts")

        # Step 3: Organize content based on style (instead of filtering)
        organized_data = loaded_data
        if (
            organization_style in ["prioritized", "minimal"]
            and loaded_data.aggregated_data
        ):
            logger.logger.info(f"Applying {organization_style} organization...")

            # Use high-signal filter for prioritization, not exclusion
            filter_config = FilterConfig(
                minimum_score=20.0,  # Lower threshold to include most content
                max_items_per_category=15 if organization_style == "prioritized" else 5,
            )

            high_signal_filter = HighSignalFilter(filter_config)

            high_signal_items, filter_error = run_with_error_handling(
                high_signal_filter.filter_and_prioritize,
                "high_signal_filter",
                error_handler,
                aggregated_data=loaded_data.aggregated_data,
            )

            if filter_error:
                logger.logger.warning(
                    f"High-signal filtering failed: {filter_error.message}"
                )
                # Continue with original data if filtering fails
            else:
                logger.logger.info(
                    f"Content organization completed: "
                    f"{len(high_signal_items)} items prioritized"
                )

                # Reorganize data to put high-signal items first, but keep all content
                from copy import deepcopy

                organized_data = deepcopy(loaded_data)
                if organized_data.aggregated_data:
                    # Create prioritized organization: high-signal first, then remaining
                    original_sources = organized_data.aggregated_data.get("sources", {})
                    prioritized_sources = {}

                    # First, add high-signal items
                    for filtered_item in high_signal_items:
                        source_type = f"high_signal_{filtered_item.source_type}"
                        if source_type not in prioritized_sources:
                            prioritized_sources[source_type] = []
                        prioritized_sources[source_type].append(
                            filtered_item.original_item
                        )

                    # Then add remaining items (non-high-signal)
                    high_signal_originals = {
                        id(item.original_item) for item in high_signal_items
                    }
                    for source_type, items in original_sources.items():
                        remaining_items = [
                            item
                            for item in items
                            if id(item) not in high_signal_originals
                        ]
                        if remaining_items:
                            remaining_source_type = f"general_{source_type}"
                            prioritized_sources[remaining_source_type] = remaining_items

                    organized_data.aggregated_data["sources"] = prioritized_sources
                    logger.logger.info("Content reorganized into prioritized structure")

        # Step 4: Generate single, well-organized Markdown document
        logger.logger.info("Generating Markdown document...")
        template_generator = MarkdownTemplateGenerator()

        # Add period metadata to template generator if processing period-based data
        if period_summary and organized_data.aggregated_data:
            template_generator.period_summary = True
            # Extract period metadata similar to extract_facts.py
            period_metadata = extract_period_metadata(organized_data.aggregated_data)
            template_generator.period_metadata = period_metadata

        document_content, template_error = run_with_error_handling(
            template_generator.generate_document,
            "template_generator",
            error_handler,
            loaded_data=organized_data,
            date=date,
            split_output=split_output,
        )

        if template_error or not document_content:
            error_msg = (
                template_error.message
                if template_error
                else "Failed to generate document"
            )
            return False, error_msg

        # Step 5: Validate generated document
        logger.logger.info("Validating generated document...")

        if split_output:
            # Handle multiple files validation with comprehensive edge case handling
            if not isinstance(document_content, dict):
                error = error_handler.create_error(
                    f"Split output mode expected dictionary, got "
                    f"{type(document_content).__name__}",
                    ErrorSeverity.HIGH,
                    ErrorCategory.DATA_VALIDATION,
                    component="document_validator",
                )
                return False, error.message

            if not document_content:
                logger.logger.warning(
                    "No sections generated for split output - creating minimal document"
                )
                # Fallback: Create a minimal document with just header
                document_content = {
                    "01_minimal": (
                        f"# Kaspa Knowledge Digest: {date}\n\n"
                        f"**CONTEXT:** No content sections were generated for this "
                        f"date.\n\n"
                        f"This may indicate:\n"
                        f"- No data available for the specified date\n"
                        f"- Data processing issues\n"
                        f"- Empty source files\n\n"
                        f"Please check the source data and logs for more information."
                    )
                }

            # Validate and sanitize each split document
            valid_sections = {}
            empty_sections = []
            problematic_sections = []

            for filename, content in document_content.items():
                # Sanitize filename for safety
                safe_filename = (
                    filename.replace("/", "_").replace("\\", "_").replace("..", "_")
                )
                if safe_filename != filename:
                    logger.logger.warning(
                        f"Sanitized filename: {filename} -> {safe_filename}"
                    )
                    filename = safe_filename

                # Handle various content issues
                if not content:
                    empty_sections.append(filename)
                    logger.logger.warning(f"Empty section detected: {filename}")
                    continue

                # Convert content to string if needed
                if not isinstance(content, str):
                    try:
                        content = str(content)
                        logger.logger.warning(
                            f"Converted non-string content for section: {filename}"
                        )
                    except Exception as e:
                        problematic_sections.append(
                            (filename, f"Cannot convert to string: {e}")
                        )
                        continue

                # Check minimum content length with more flexible threshold
                if len(content.strip()) < 50:
                    logger.logger.warning(
                        f"Very short section content for: {filename} "
                        f"({len(content)} chars)"
                    )
                    # Still include short sections, but log the warning

                # Check for encoding issues
                try:
                    # Test encoding by attempting to encode/decode
                    content.encode("utf-8").decode("utf-8")
                except UnicodeError as e:
                    problematic_sections.append((filename, f"Encoding issue: {e}"))
                    logger.logger.error(
                        f"Unicode encoding issue in section {filename}: {e}"
                    )
                    continue

                # Check for extremely large content (>10MB)
                if len(content) > 10 * 1024 * 1024:
                    logger.logger.warning(
                        f"Very large section detected: {filename} "
                        f"({len(content):,} chars)"
                    )
                    # Optionally truncate or continue with warning

                valid_sections[filename] = content

            # Handle edge cases in section validation results
            if not valid_sections:
                if empty_sections or problematic_sections:
                    error_details = []
                    if empty_sections:
                        error_details.append(
                            f"Empty sections: {', '.join(empty_sections)}"
                        )
                    if problematic_sections:
                        problem_list = [
                            f"{name} ({issue})" for name, issue in problematic_sections
                        ]
                        error_details.append(
                            f"Problematic sections: {', '.join(problem_list)}"
                        )

                    error = error_handler.create_error(
                        f"No valid sections for split output. "
                        f"{'; '.join(error_details)}",
                        ErrorSeverity.HIGH,
                        ErrorCategory.DATA_VALIDATION,
                        component="document_validator",
                    )
                    return False, error.message
                else:
                    # Fallback to minimal content
                    logger.logger.warning(
                        "No valid sections found - creating fallback content"
                    )
                    valid_sections = {
                        "01_fallback": (
                            f"# Kaspa Knowledge Digest: {date}\n\n"
                            f"**CONTEXT:** Document generation completed but no valid "
                            f"content sections were produced.\n\n"
                            f"This may indicate data processing issues or empty files."
                        )
                    }

            # Log section summary
            if empty_sections:
                logger.logger.info(
                    f"Skipped empty sections: {', '.join(empty_sections)}"
                )
            if problematic_sections:
                logger.logger.warning(
                    f"Skipped problematic sections: "
                    f"{', '.join([name for name, _ in problematic_sections])}"
                )

            logger.logger.info(
                f"Proceeding with {len(valid_sections)} valid sections out of "
                f"{len(document_content)} total"
            )

            # Update document_content to only include valid sections
            document_content = valid_sections

            # Step 6: Write multiple output files atomically
            logger.logger.info(
                f"Writing {len(document_content)} split documents to: {output_dir}"
            )
            temp_files = []
            written_files = []
            total_size = 0

            try:
                # Phase 1: Pre-flight checks and preparation
                final_files = []
                total_content_size = 0

                # Check output directory permissions
                if not os.access(output_dir, os.W_OK):
                    error = error_handler.create_error(
                        f"No write permission to output directory: {output_dir}",
                        ErrorSeverity.CRITICAL,
                        ErrorCategory.FILE_OPERATIONS,
                        component="permission_checker",
                    )
                    return False, error.message

                # Prepare file operations and calculate total size
                for filename, content in document_content.items():
                    # Sanitize filename again for final output
                    safe_filename = "".join(
                        c for c in filename if c.isalnum() or c in "._-"
                    )
                    if not safe_filename:
                        safe_filename = f"section_{len(final_files)}"

                    split_output_file = output_dir / f"{date}_{safe_filename}.md"

                    # Check for filename conflicts within this batch
                    existing_paths = [path for _, _, path in final_files]
                    if split_output_file in existing_paths:
                        # Add counter to avoid conflicts
                        counter = 1
                        while True:
                            conflicted_file = (
                                output_dir / f"{date}_{safe_filename}_{counter}.md"
                            )
                            if conflicted_file not in existing_paths:
                                split_output_file = conflicted_file
                                logger.logger.warning(
                                    f"Resolved filename conflict: {safe_filename} -> "
                                    f"{safe_filename}_{counter}"
                                )
                                break
                            counter += 1

                    final_files.append((filename, content, split_output_file))
                    total_content_size += len(content.encode("utf-8"))

                    # Check if file exists and handle force flag
                    if split_output_file.exists() and not force:
                        error = error_handler.create_error(
                            f"Output file already exists: {split_output_file}. "
                            f"Use --force to overwrite.",
                            ErrorSeverity.MEDIUM,
                            ErrorCategory.FILE_OPERATIONS,
                            component="file_checker",
                        )
                        return False, error.message

                # Check available disk space (if possible)
                try:
                    if hasattr(os, "statvfs"):  # Unix-like systems
                        stat = os.statvfs(output_dir)
                        free_space = stat.f_bavail * stat.f_frsize
                        # Add 50% buffer for temp files and overhead
                        required_space = int(total_content_size * 2.5)

                        if free_space < required_space:
                            error = error_handler.create_error(
                                f"Insufficient space. Required: {required_space:,} "
                                f"bytes, Available: {free_space:,} bytes",
                                ErrorSeverity.CRITICAL,
                                ErrorCategory.FILE_OPERATIONS,
                                component="disk_space_checker",
                            )
                            return False, error.message

                        logger.logger.debug(
                            f"Disk space check passed: {free_space:,} bytes available, "
                            f"{required_space:,} bytes required"
                        )
                except (OSError, AttributeError) as e:
                    # Disk space check failed, but continue with warning
                    logger.logger.warning(f"Could not check disk space: {e}")

                logger.logger.info(
                    f"Pre-flight checks passed for {len(final_files)} files "
                    f"({total_content_size:,} bytes total)"
                )

                # Phase 2: Write all content to temporary files with error handling
                logger.logger.info("Writing content to temporary files...")
                for filename, content, final_path in final_files:
                    temp_fd = None
                    temp_path = None

                    try:
                        # Create temporary file in the same directory as the final file
                        temp_fd, temp_path = tempfile.mkstemp(
                            suffix=".tmp",
                            prefix=f"{date}_{filename}_"[:50],  # Limit prefix length
                            dir=output_dir,
                            text=True,
                        )

                        # Write content to temporary file with progress tracking
                        bytes_written = 0
                        chunk_size = 8192  # Write in 8KB chunks for large files

                        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
                            temp_fd = (
                                None  # File descriptor is now managed by temp_file
                            )

                            # For large content, write in chunks for memory efficiency
                            if len(content) > chunk_size:
                                for i in range(0, len(content), chunk_size):
                                    chunk = content[i : i + chunk_size]
                                    temp_file.write(chunk)
                                    bytes_written += len(chunk.encode("utf-8"))

                                    # Flush periodically to ensure data is written
                                    if bytes_written % (chunk_size * 10) == 0:
                                        temp_file.flush()
                                        os.fsync(temp_file.fileno())
                            else:
                                temp_file.write(content)
                                bytes_written = len(content.encode("utf-8"))

                            # Final flush and sync
                            temp_file.flush()
                            os.fsync(temp_file.fileno())

                        # Validate temporary file was written correctly
                        temp_file_path = Path(temp_path)
                        if not temp_file_path.exists():
                            raise IOError(f"Temporary file not created: {temp_path}")

                        actual_size = temp_file_path.stat().st_size
                        if actual_size == 0:
                            raise IOError(f"Temporary file is empty: {temp_path}")

                        # Verify content integrity by reading back key portions
                        try:
                            with open(
                                temp_file_path, "r", encoding="utf-8"
                            ) as verify_file:
                                # For small files, read entire content and compare
                                if actual_size < 1000:
                                    read_content = verify_file.read()
                                    if read_content != content:
                                        raise IOError(
                                            f"Content verification failed for: "
                                            f"{temp_path}"
                                        )
                                else:
                                    # For larger files, verify start and end
                                    read_start = verify_file.read(100)
                                    if not content.startswith(read_start):
                                        raise IOError(
                                            f"Content verification failed (start) for: "
                                            f"{temp_path}"
                                        )

                                    # For end verification, use a more reliable approach
                                    # Read the last portion by seeking from the end
                                    verify_file.seek(0, 2)  # Seek to end
                                    file_size_bytes = verify_file.tell()

                                    if file_size_bytes > 200:
                                        # Read last 100 bytes worth of characters
                                        verify_file.seek(max(0, file_size_bytes - 200))
                                        verify_file.read(
                                            100
                                        )  # Skip initial partial characters
                                        read_end = verify_file.read()

                                        # Get expected end (last 100 chars)
                                        expected_end = (
                                            content[-100:]
                                            if len(content) > 100
                                            else content
                                        )

                                        if not read_end or not expected_end.endswith(
                                            read_end[-50:]
                                        ):
                                            # Less strict verification for large files
                                            if (
                                                len(content) < 50000
                                            ):  # Only strict check for medium files
                                                raise IOError(
                                                    f"Content verify failed (end): "
                                                    f"{temp_path}"
                                                )
                        except (OSError, UnicodeDecodeError) as verify_error:
                            raise IOError(
                                f"Content verification error for {temp_path}: "
                                f"{verify_error}"
                            )

                        # Track temporary file for atomic operation
                        temp_files.append((temp_file_path, final_path))
                        logger.logger.debug(
                            f"Successfully wrote temp file: {temp_path} "
                            f"({actual_size:,} bytes)"
                        )

                    except Exception as e:
                        # Enhanced cleanup for failed temporary file creation
                        cleanup_success = True

                        # Close file descriptor if still open
                        if temp_fd is not None:
                            try:
                                os.close(temp_fd)
                            except Exception as fd_error:
                                logger.logger.debug(
                                    f"Error closing file descriptor: {fd_error}"
                                )
                                cleanup_success = False

                        # Remove temp file if it exists
                        if temp_path and os.path.exists(temp_path):
                            try:
                                os.unlink(temp_path)
                                logger.logger.debug(
                                    f"Cleaned up failed temp file: {temp_path}"
                                )
                            except Exception as cleanup_error:
                                logger.logger.warning(
                                    f"Failed to cleanup temp file {temp_path}: "
                                    f"{cleanup_error}"
                                )
                                cleanup_success = False

                        # Re-raise with context about cleanup
                        cleanup_msg = (
                            " (cleanup successful)"
                            if cleanup_success
                            else " (cleanup failed)"
                        )
                        raise IOError(
                            f"Failed to write section '{filename}' to temporary file: "
                            f"{e}{cleanup_msg}"
                        ) from e

                # Phase 3: Atomically move all temp files to final locations
                logger.logger.info("Committing files atomically...")
                for temp_path, final_path in temp_files:
                    # Atomic rename operation
                    temp_path.rename(final_path)

                    # Validate final file
                    if not final_path.exists():
                        raise IOError(f"Atomic rename failed: {final_path}")

                    file_size = final_path.stat().st_size
                    written_files.append(final_path.name)
                    total_size += file_size
                    logger.logger.debug(f"Successfully committed: {final_path}")

                # Clear temp_files list since all were successfully renamed
                temp_files.clear()

                logger.logger.info(
                    f"Successfully generated {len(written_files)} split documents "
                    f"atomically"
                )
                logger.logger.info(f"Files: {', '.join(written_files)}")
                logger.logger.info(f"Total size: {total_size:,} bytes")

            except Exception as e:
                # Phase 4: Cleanup temporary files on any failure
                logger.logger.error(f"Error during atomic file writing: {e}")
                cleanup_errors = []

                for temp_path, final_path in temp_files:
                    try:
                        if temp_path.exists():
                            temp_path.unlink()
                            logger.logger.debug(f"Cleaned up temp file: {temp_path}")
                    except Exception as cleanup_error:
                        cleanup_errors.append(
                            f"Failed to cleanup {temp_path}: {cleanup_error}"
                        )

                # Log cleanup errors but don't mask original error
                if cleanup_errors:
                    logger.logger.warning(
                        f"Cleanup errors: {'; '.join(cleanup_errors)}"
                    )

                # Create comprehensive error message
                error = error_handler.create_error(
                    f"Atomic file writing failed: {e}. All temporary files cleaned up.",
                    ErrorSeverity.CRITICAL,
                    ErrorCategory.FILE_OPERATIONS,
                    component="atomic_file_writer",
                )
                return False, error.message

        else:
            # Handle single file validation (original behavior)
            if not document_content or len(document_content) < 100:
                error = error_handler.create_error(
                    "Generated document is empty or too short",
                    ErrorSeverity.HIGH,
                    ErrorCategory.DATA_VALIDATION,
                    component="document_validator",
                )
                return False, error.message

            # Check for required sections
            required_sections = ["Kaspa Knowledge Digest", "CONTEXT:"]
            missing_sections = []
            for section in required_sections:
                if section not in document_content:
                    missing_sections.append(section)

            if missing_sections:
                error = error_handler.create_error(
                    f"Generated document missing required sections: "
                    f"{', '.join(missing_sections)}",
                    ErrorSeverity.MEDIUM,
                    ErrorCategory.DATA_VALIDATION,
                    component="document_validator",
                )
                logger.logger.warning(error.message)  # Log as warning but continue

            # Step 6: Write single output file
            logger.logger.info(f"Writing document to: {output_file}")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(document_content)

            # Final validation that file was written correctly
            if not output_file.exists():
                error = error_handler.create_error(
                    f"Output file was not created: {output_file}",
                    ErrorSeverity.CRITICAL,
                    ErrorCategory.FILE_OPERATIONS,
                    component="file_writer",
                )
                return False, error.message

            file_size = output_file.stat().st_size
            logger.logger.info(f"Successfully generated RAG document: {output_file}")
            logger.logger.info(f"Document size: {file_size:,} bytes")

        # Log health report
        health_report = error_handler.get_health_report()
        healthy_components = sum(
            1 for comp in health_report["components"].values() if comp["is_healthy"]
        )
        total_components = len(health_report["components"])
        logger.logger.info(
            f"Pipeline health: {healthy_components}/{total_components} "
            f"components healthy"
        )

        return True, None

    except Exception as e:
        context_data = {"date": date, "organization_style": organization_style}
        error = error_handler.handle_exception(
            e, "rag_document_generator", context=context_data
        )
        logger.logger.error(f"RAG generation error: {error.message}")
        return False, error.message


def main():
    """Main entry point for the RAG document generation script."""
    parser = argparse.ArgumentParser(
        description="Generate RAG-optimized documents from daily JSON data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                               # Prioritized organization (default)
  %(prog)s --date 2025-07-01             # Process specific date
  %(prog)s --force                       # Force overwrite existing files
  %(prog)s --organization comprehensive  # Include all content in order
  %(prog)s --organization minimal        # High-signal content only
        """,
    )

    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date to process in YYYY-MM-DD format (default: today)",
    )

    parser.add_argument(
        "--force", action="store_true", help="Force overwrite existing output files"
    )

    parser.add_argument(
        "--organization",
        choices=["comprehensive", "prioritized", "minimal"],
        default="prioritized",
        help="Content organization style (default: prioritized)",
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing input data (default: data)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("knowledge_base"),
        help="Directory for output files (default: knowledge_base)",
    )

    parser.add_argument(
        "--split-output",
        action="store_true",
        help="Split output into multiple files by section "
        "(recommended for full history)",
    )

    parser.add_argument(
        "--period-summary",
        action="store_true",
        help="Process period-based data files (weekly, monthly, etc.) "
        "instead of daily data",
    )

    args = parser.parse_args()

    # Validate arguments
    if not validate_date_format(args.date):
        if args.period_summary:
            print(
                f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD or "
                f"period-based format (e.g., YYYY-MM-monthly, YYYY-MM-DD-weekly)"
            )
        else:
            print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD")
        sys.exit(1)

    if not args.data_dir.exists():
        print(f"Error: Data directory does not exist: {args.data_dir}")
        sys.exit(1)

    # Run the generation
    mode = "period-based" if args.period_summary else "daily"
    print(f"Starting RAG document generation for {args.date} ({mode} mode)")
    print(f"Organization style: {args.organization}")
    if args.split_output:
        print("Split output mode: Multiple files will be created")

    success, error_message = generate_rag_document(
        date=args.date,
        force=args.force,
        organization_style=args.organization,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        split_output=args.split_output,
        period_summary=args.period_summary,
    )

    if success:
        if args.split_output:
            print(f"Successfully generated split RAG documents for {args.date}")
            print(f"Output directory: {args.output_dir}")
            print(f"Files: {args.date}_*.md")
        else:
            print(f"Successfully generated RAG document for {args.date}")
            print(f"Output: {args.output_dir}/{args.date}.md")
        sys.exit(0)
    else:
        print(f"Failed to generate RAG document: {error_message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
