"""
Markdown Template Generator for RAG-Optimized Documents

This module provides comprehensive Markdown template generation with semantic chunking,
YAML metadata blocks, and structured output optimized for RAG systems.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import yaml
import re
from textwrap import dedent

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class MetadataBlock:
    """Represents a YAML metadata block for semantic chunks."""

    source: str
    date: str
    chunk_id: str
    section_type: str

    # Optional fields based on context
    author: Optional[str] = None
    signal_strength: Optional[str] = None
    contributor_role: Optional[str] = None
    repository: Optional[str] = None
    category: Optional[str] = None
    impact: Optional[str] = None
    confidence: Optional[str] = None
    sources_covered: Optional[List[str]] = None
    total_facts: Optional[int] = None
    fact_categories: Optional[List[str]] = None

    def to_yaml_block(self) -> str:
        """Convert metadata to YAML block format."""
        data = {
            "source": self.source,
            "date": self.date,
            "chunk_id": self.chunk_id,
            "section_type": self.section_type,
        }

        # Add optional fields if present
        optional_fields = [
            "author",
            "signal_strength",
            "contributor_role",
            "repository",
            "category",
            "impact",
            "confidence",
            "sources_covered",
            "total_facts",
            "fact_categories",
        ]

        for field_name in optional_fields:
            value = getattr(self, field_name, None)
            if value is not None:
                data[field_name] = value

        # Convert to YAML and format as code block
        yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        return f"```metadata\n{yaml_content.strip()}\n```"


@dataclass
class SemanticChunk:
    """Represents a semantic chunk with content and metadata."""

    content: str
    metadata: MetadataBlock
    token_count: Optional[int] = None

    def to_markdown(self) -> str:
        """Convert chunk to Markdown format with metadata block."""
        return f"{self.metadata.to_yaml_block()}\n\n{self.content}"


@dataclass
class DocumentSection:
    """Represents a section of the document with multiple chunks."""

    title: str
    heading_level: int
    chunks: List[SemanticChunk] = field(default_factory=list)

    def add_chunk(self, chunk: SemanticChunk) -> None:
        """Add a chunk to this section."""
        self.chunks.append(chunk)

    def to_markdown(self) -> str:
        """Convert section to Markdown format."""
        heading = "#" * self.heading_level + " " + self.title
        chunks_md = "\n\n".join(chunk.to_markdown() for chunk in self.chunks)
        return f"{heading}\n\n{chunks_md}"


class MarkdownTemplateGenerator:
    """Generates RAG-optimized Markdown documents from structured data."""

    def __init__(self, target_chunk_size: int = 400, max_chunk_size: int = 500):
        """
        Initialize the template generator.

        Args:
            target_chunk_size: Target token count for semantic chunks
            max_chunk_size: Maximum token count before forced chunking
        """
        self.target_chunk_size = target_chunk_size
        self.max_chunk_size = max_chunk_size
        self.chunk_counter = 0

    def generate_document(self, loaded_data: Any, date: str) -> str:
        """
        Generate a complete RAG-optimized Markdown document.

        Args:
            loaded_data: LoadedData object from data_loader
            date: Date string in YYYY-MM-DD format

        Returns:
            Complete Markdown document as string
        """
        logger.info(f"Generating RAG document for date: {date}")

        # Reset chunk counter for new document
        self.chunk_counter = 0

        # Create document sections
        sections = []

        # Header section
        header_section = self._create_header_section(date)
        sections.append(header_section)

        # Daily briefing section
        if loaded_data.briefings_data:
            briefing_section = self._create_briefing_section(
                loaded_data.briefings_data, date
            )
            sections.append(briefing_section)

        # Key facts section
        if loaded_data.facts_data:
            facts_section = self._create_facts_section(loaded_data.facts_data, date)
            sections.append(facts_section)

        # High-signal insights section
        if loaded_data.aggregated_data:
            high_signal_section = self._create_high_signal_section(
                loaded_data.aggregated_data, date
            )
            sections.append(high_signal_section)

        # General activity section
        if loaded_data.aggregated_data:
            general_section = self._create_general_activity_section(
                loaded_data.aggregated_data, date
            )
            sections.append(general_section)

        # Combine all sections
        document_parts = [section.to_markdown() for section in sections]
        full_document = "\n\n---\n\n".join(document_parts)

        logger.info(
            f"Generated document with {len(sections)} sections "
            f"and {self.chunk_counter} chunks"
        )
        return full_document

    def _create_header_section(self, date: str) -> DocumentSection:
        """Create the document header section."""
        header_section = DocumentSection("Kaspa Knowledge Digest: " + date, 1)

        # Header metadata
        header_metadata = MetadataBlock(
            source="generated",
            date=date,
            chunk_id=f"digest-{date}-header",
            section_type="document_header",
        )

        header_content = dedent(
            f"""
        This document contains curated knowledge from the Kaspa ecosystem for {date}.
        The content is semantically structured and optimized for RAG systems.
        """
        ).strip()

        header_chunk = SemanticChunk(header_content, header_metadata)
        header_section.add_chunk(header_chunk)

        return header_section

    def _create_briefing_section(
        self, briefings_data: Dict[str, Any], date: str
    ) -> DocumentSection:
        """Create the daily briefing section."""
        briefing_section = DocumentSection("Daily Briefing", 2)

        # Process each source's briefing
        for source_type, source_data in briefings_data.get("sources", {}).items():
            if not isinstance(source_data, dict):
                continue

            summary = source_data.get("summary", "")
            if not summary:
                continue

            # Create metadata for this briefing chunk
            metadata = MetadataBlock(
                source=f"data/briefings/{date}.json",
                date=date,
                chunk_id=f"briefing-{date}-{source_type}-{self._get_next_chunk_id()}",
                section_type="briefing_narrative",
                sources_covered=[source_type],
            )

            # Format content with source heading
            content = f"### {source_type.replace('_', ' ').title()}\n\n{summary}"

            # Handle semantic chunking if content is too large
            chunks = self._chunk_content(content, metadata, "briefing_narrative")
            for chunk in chunks:
                briefing_section.add_chunk(chunk)

        return briefing_section

    def _create_facts_section(
        self, facts_data: Dict[str, Any], date: str
    ) -> DocumentSection:
        """Create the key facts section."""
        facts_section = DocumentSection("Key Facts", 2)

        facts_list = facts_data.get("facts", [])
        if not facts_list:
            return facts_section

        # Group facts by category for better organization
        facts_by_category = {}
        for fact in facts_list:
            category = fact.get("category", "general")
            if category not in facts_by_category:
                facts_by_category[category] = []
            facts_by_category[category].append(fact)

        # Process each category
        for category, category_facts in facts_by_category.items():
            category_content = f"### {category.replace('_', ' ').title()}\n\n"

            for fact in category_facts:
                fact_content = self._format_fact(fact)
                category_content += fact_content + "\n\n"

            # Create metadata for this category chunk
            metadata = MetadataBlock(
                source=f"data/facts/{date}.json",
                date=date,
                chunk_id=f"facts-{date}-{category}-{self._get_next_chunk_id()}",
                section_type="extracted_facts",
                category=category,
                total_facts=len(category_facts),
            )

            # Handle semantic chunking
            chunks = self._chunk_content(category_content, metadata, "extracted_facts")
            for chunk in chunks:
                facts_section.add_chunk(chunk)

        return facts_section

    def _create_high_signal_section(
        self, aggregated_data: Dict[str, Any], date: str
    ) -> DocumentSection:
        """Create the high-signal insights section."""
        high_signal_section = DocumentSection("High-Signal Contributor Insights", 2)

        # Extract high-signal items from all sources
        high_signal_items = []
        for source_type, items in aggregated_data.get("sources", {}).items():
            if not isinstance(items, list):
                continue

            for item in items:
                signal_info = item.get("signal", {})
                if (
                    signal_info.get("strength") == "high"
                    or signal_info.get("is_lead")
                    or signal_info.get("is_founder")
                ):
                    high_signal_items.append((source_type, item))

        if not high_signal_items:
            return high_signal_section

        # Group by contributor role
        items_by_role = {}
        for source_type, item in high_signal_items:
            role = item.get("signal", {}).get("contributor_role", "contributor")
            if role not in items_by_role:
                items_by_role[role] = []
            items_by_role[role].append((source_type, item))

        # Process each role group
        for role, role_items in items_by_role.items():
            role_content = f"### {role.replace('_', ' ').title()}\n\n"

            for source_type, item in role_items:
                item_content = self._format_high_signal_item(item, source_type)
                role_content += item_content + "\n\n"

            # Create metadata for this role chunk
            metadata = MetadataBlock(
                source=f"data/aggregated/{date}.json",
                date=date,
                chunk_id=f"high-signal-{date}-{role}-{self._get_next_chunk_id()}",
                section_type="high_signal_insights",
                contributor_role=role,
                signal_strength="high",
            )

            # Handle semantic chunking
            chunks = self._chunk_content(role_content, metadata, "high_signal_insights")
            for chunk in chunks:
                high_signal_section.add_chunk(chunk)

        return high_signal_section

    def _create_general_activity_section(
        self, aggregated_data: Dict[str, Any], date: str
    ) -> DocumentSection:
        """Create the general activity section."""
        general_section = DocumentSection("General Activity", 2)

        # Process each source type
        for source_type, items in aggregated_data.get("sources", {}).items():
            if not isinstance(items, list) or not items:
                continue

            # Filter out high-signal items (already covered in previous section)
            regular_items = []
            for item in items:
                signal_info = item.get("signal", {})
                if (
                    signal_info.get("strength") != "high"
                    and not signal_info.get("is_lead")
                    and not signal_info.get("is_founder")
                ):
                    regular_items.append(item)

            if not regular_items:
                continue

            # Create content for this source type
            source_content = f"### {source_type.replace('_', ' ').title()}\n\n"

            for item in regular_items[:10]:  # Limit to prevent overwhelming content
                item_content = self._format_general_item(item, source_type)
                source_content += item_content + "\n\n"

            if len(regular_items) > 10:
                source_content += f"*... and {len(regular_items) - 10} more items*\n\n"

            # Create metadata for this source chunk
            metadata = MetadataBlock(
                source=f"data/aggregated/{date}.json",
                date=date,
                chunk_id=f"general-{date}-{source_type}-{self._get_next_chunk_id()}",
                section_type="general_activity",
                sources_covered=[source_type],
            )

            # Handle semantic chunking
            chunks = self._chunk_content(source_content, metadata, "general_activity")
            for chunk in chunks:
                general_section.add_chunk(chunk)

        return general_section

    def _format_fact(self, fact: Dict[str, Any]) -> str:
        """Format a single fact for display."""
        fact_text = fact.get("fact", "")
        impact = fact.get("impact", "unknown")
        category = fact.get("category", "general")
        context = fact.get("context", "")

        source_info = fact.get("source", {})
        source_title = source_info.get("title", "Unknown source")
        source_author = source_info.get("author", "Unknown author")
        source_url = source_info.get("url", "")

        content = f"**{fact_text}**\n\n"

        if context:
            content += f"*Context:* {context}\n\n"

        content += f"*Impact:* {impact.title()} | *Category:* {category.title()}\n\n"
        content += f"*Source:* {source_title} by {source_author}"

        if source_url:
            content += f" ([link]({source_url}))"

        return content

    def _format_high_signal_item(self, item: Dict[str, Any], source_type: str) -> str:
        """Format a high-signal item for display."""
        title = item.get("title", "Untitled")
        author = item.get("author", "Unknown")
        content = item.get("content", "")
        url = item.get("url", "")

        signal_info = item.get("signal", {})
        role = signal_info.get("contributor_role", "contributor")

        formatted = f"**{title}** by {author} ({role})\n\n"

        if content:
            # Truncate content if too long
            if len(content) > 300:
                content = content[:297] + "..."
            formatted += f"{content}\n\n"

        if url:
            formatted += f"[View source]({url})"

        return formatted

    def _format_general_item(self, item: Dict[str, Any], source_type: str) -> str:
        """Format a general activity item for display."""
        title = item.get("title", "Untitled")
        author = item.get("author", "Unknown")
        url = item.get("url", "")

        formatted = f"- **{title}** by {author}"

        if url:
            formatted += f" ([link]({url}))"

        return formatted

    def _chunk_content(
        self, content: str, base_metadata: MetadataBlock, section_type: str
    ) -> List[SemanticChunk]:
        """
        Split content into semantic chunks with appropriate metadata.

        Args:
            content: Content to chunk
            base_metadata: Base metadata to use for all chunks
            section_type: Type of section for consistent chunking

        Returns:
            List of semantic chunks
        """
        # Simple chunking strategy: split by paragraphs and headings
        chunks = []

        # Split by double newlines (paragraphs) and headings
        parts = re.split(r"\n\n+|(?=\n#{2,6}\s)", content)

        current_chunk = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Estimate token count (rough approximation: 1 token ≈ 4 characters)
            estimated_tokens = len(current_chunk + part) // 4

            if estimated_tokens > self.max_chunk_size and current_chunk:
                # Create chunk with current content
                chunk_metadata = MetadataBlock(
                    source=base_metadata.source,
                    date=base_metadata.date,
                    chunk_id=f"{base_metadata.chunk_id}-part-{len(chunks) + 1}",
                    section_type=section_type,
                    author=base_metadata.author,
                    signal_strength=base_metadata.signal_strength,
                    contributor_role=base_metadata.contributor_role,
                    repository=base_metadata.repository,
                    category=base_metadata.category,
                    impact=base_metadata.impact,
                    confidence=base_metadata.confidence,
                    sources_covered=base_metadata.sources_covered,
                    total_facts=base_metadata.total_facts,
                    fact_categories=base_metadata.fact_categories,
                )

                chunks.append(
                    SemanticChunk(
                        current_chunk.strip(), chunk_metadata, estimated_tokens
                    )
                )
                current_chunk = part
            else:
                current_chunk += "\n\n" + part if current_chunk else part

        # Add final chunk if there's remaining content
        if current_chunk.strip():
            chunk_metadata = MetadataBlock(
                source=base_metadata.source,
                date=base_metadata.date,
                chunk_id=(
                    f"{base_metadata.chunk_id}-part-{len(chunks) + 1}"
                    if chunks
                    else base_metadata.chunk_id
                ),
                section_type=section_type,
                author=base_metadata.author,
                signal_strength=base_metadata.signal_strength,
                contributor_role=base_metadata.contributor_role,
                repository=base_metadata.repository,
                category=base_metadata.category,
                impact=base_metadata.impact,
                confidence=base_metadata.confidence,
                sources_covered=base_metadata.sources_covered,
                total_facts=base_metadata.total_facts,
                fact_categories=base_metadata.fact_categories,
            )

            estimated_tokens = len(current_chunk) // 4
            chunks.append(
                SemanticChunk(current_chunk.strip(), chunk_metadata, estimated_tokens)
            )

        return chunks if chunks else [SemanticChunk(content, base_metadata)]

    def _get_next_chunk_id(self) -> str:
        """Get next sequential chunk ID."""
        self.chunk_counter += 1
        return f"{self.chunk_counter:03d}"


# Utility functions
def generate_rag_document(
    loaded_data: Any, date: str, output_path: Optional[str] = None
) -> str:
    """
    Generate a complete RAG-optimized Markdown document.

    Args:
        loaded_data: LoadedData object from data_loader
        date: Date string in YYYY-MM-DD format
        output_path: Optional path to save the document

    Returns:
        Generated Markdown document as string
    """
    generator = MarkdownTemplateGenerator()
    document = generator.generate_document(loaded_data, date)

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(document)

        logger.info(f"RAG document saved to: {output_file}")

    return document


if __name__ == "__main__":
    # CLI interface for testing
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Generate RAG-optimized Markdown documents"
    )
    parser.add_argument("date", help="Date in YYYY-MM-DD format")
    parser.add_argument("--data-dir", default="data", help="Data directory path")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    try:
        # Import and use data loader
        from data_loader import JSONDataLoader

        loader = JSONDataLoader(args.data_dir)
        loaded_data = loader.load_data_for_date(args.date)

        if loaded_data.has_errors:
            logger.error("Data loading errors detected. Cannot generate document.")
            sys.exit(1)

        # Generate document
        output_path = args.output or f"knowledge_base/{args.date}.md"
        document = generate_rag_document(loaded_data, args.date, output_path)

        if not args.output:
            print(document)

    except Exception as e:
        logger.error(f"Error generating document: {e}")
        sys.exit(1)
