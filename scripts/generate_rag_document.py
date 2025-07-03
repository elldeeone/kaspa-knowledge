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
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

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
    """Validate that date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def generate_rag_document(
    date: str,
    force: bool = False,
    organization_style: str = "prioritized",
    data_dir: Path = Path("data"),
    output_dir: Path = Path("knowledge_base"),
) -> Tuple[bool, Optional[str]]:
    """
    Generate a single, well-organized RAG document from daily JSON data.

    Args:
        date: Date string in YYYY-MM-DD format
        force: Whether to overwrite existing files
        organization_style: How to organize content
            ("comprehensive", "prioritized", "minimal")
        data_dir: Directory containing source data
        output_dir: Directory for output files

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
        data_loader = JSONDataLoader(str(data_dir))

        loaded_data, load_error = run_with_error_handling(
            data_loader.load_data_for_date, "data_loader", error_handler, date=date
        )

        if load_error or not loaded_data:
            error_msg = load_error.message if load_error else "Failed to load data"
            return False, error_msg

        logger.logger.info(f"Successfully loaded data for {date}")
        if loaded_data.aggregated_data:
            source_count = len(loaded_data.aggregated_data.get("sources", {}))
            logger.logger.info(f"  - Aggregated: {source_count} sources")
        if loaded_data.briefings_data:
            summary_count = len(loaded_data.briefings_data.get("summaries", {}))
            logger.logger.info(f"  - Briefings: {summary_count} summaries")
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

        document_content, template_error = run_with_error_handling(
            template_generator.generate_document,
            "template_generator",
            error_handler,
            loaded_data=organized_data,
            date=date,
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

        # Basic content validation
        if not document_content or len(document_content) < 100:
            error = error_handler.create_error(
                "Generated document is empty or too short",
                ErrorSeverity.HIGH,
                ErrorCategory.DATA_VALIDATION,
                component="document_validator",
            )
            return False, error.message

        # Check for required sections
        required_sections = ["Kaspa Knowledge Digest", "metadata"]
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

        # Step 6: Write output file
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

    args = parser.parse_args()

    # Validate arguments
    if not validate_date_format(args.date):
        print(f"❌ Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD")
        sys.exit(1)

    if not args.data_dir.exists():
        print(f"❌ Error: Data directory does not exist: {args.data_dir}")
        sys.exit(1)

    # Run the generation
    print(f"🚀 Starting RAG document generation for {args.date}")
    print(f"📋 Organization style: {args.organization}")

    success, error_message = generate_rag_document(
        date=args.date,
        force=args.force,
        organization_style=args.organization,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )

    if success:
        print(f"✅ Successfully generated RAG document for {args.date}")
        print(f"📄 Output: {args.output_dir}/{args.date}.md")
        sys.exit(0)
    else:
        print(f"❌ Failed to generate RAG document: {error_message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
