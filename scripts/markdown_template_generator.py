"""
Markdown Template Generator for RAG-Optimized Documents

This module provides comprehensive Markdown template generation with semantic chunking,
natural language context blocks, and structured output optimized for RAG systems.
Specifically optimized for plugin-knowledge and similar RAG processing systems.
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
    """
    Represents contextual metadata for semantic chunks, formatted as
    natural language for optimal RAG processing.
    """

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

    def to_context_block(self) -> str:
        """
        Convert metadata to natural language context block format
        for optimal RAG processing.
        """
        # Build context information as natural language
        context_parts = []

        # Main context description based on section type
        section_descriptions = {
            "document_header": (
                "This is the document header providing overview information"
            ),
            "briefing_narrative": (
                "This section contains executive briefing and analysis"
            ),
            "extracted_facts": (
                "This section contains key facts and technical information"
            ),
            "high_signal_insights": (
                "This section contains high-priority insights and developments"
            ),
            "general_activity": (
                "This section contains general community and development activity"
            ),
            "github_summary": (
                "This section contains GitHub repository activity and code changes"
            ),
            "forum_discussion": (
                "This section contains forum discussions and community topics"
            ),
            "telegram_activity": (
                "This section contains Telegram community discussions"
            ),
            "medium_articles": (
                "This section contains Medium articles and publications"
            ),
        }

        base_description = section_descriptions.get(
            self.section_type,
            f"This section contains {self.section_type.replace('_', ' ')}",
        )
        context_parts.append(f"**CONTEXT:** {base_description}")

        # Add category if present
        if self.category:
            category_display = self.category.replace("_", " ").title()
            context_parts.append(f"**Topic:** {category_display}")

        # Add impact level if present
        if self.impact:
            context_parts.append(f"**Impact Level:** {self.impact.title()}")

        # Add signal strength for high-signal content
        if self.signal_strength:
            context_parts.append(f"**Signal Strength:** {self.signal_strength.title()}")

        # Add author/contributor info if present
        if self.author:
            if self.contributor_role:
                context_parts.append(
                    f"**Contributor:** {self.author} ({self.contributor_role})"
                )
            else:
                context_parts.append(f"**Author:** {self.author}")

        # Add repository info for GitHub content
        if self.repository:
            context_parts.append(f"**Repository:** `{self.repository}`")

        # Add sources covered for multi-source briefings
        if self.sources_covered and len(self.sources_covered) > 1:
            sources_display = ", ".join(self.sources_covered)
            context_parts.append(f"**Sources:** {sources_display}")

        # Add fact statistics if present
        if self.total_facts:
            context_parts.append(f"**Facts Count:** {self.total_facts}")

        # Add source file reference (more subtle, at the end)
        context_parts.append(f"**Source:** `{self.source}`")

        # Format as blockquote with line breaks
        context_text = "  \n> ".join(context_parts)
        return f"> {context_text}"

    def to_yaml_block(self) -> str:
        """
        Legacy method - kept for backward compatibility but not used
        in RAG-optimized output.
        """
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
        """Convert chunk to Markdown format with natural language context block."""
        return f"{self.metadata.to_context_block()}\n\n{self.content}"


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
    """
    Generates RAG-optimized Markdown documents from structured data.

    CRITICAL OPTIMIZATION: Uses natural language context blocks instead of YAML metadata
    to ensure semantic meaning is preserved during RAG chunking. This prevents metadata
    pollution in vector embeddings and improves search accuracy for plugin-knowledge
    and similar RAG processing systems.
    """

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
        """Create the high-signal insights section using the new scoring system."""
        high_signal_section = DocumentSection("High-Signal Contributor Insights", 2)

        # Extract and score items from all sources
        scored_items = []
        for source_type, items in aggregated_data.get("sources", {}).items():
            if not isinstance(items, list):
                continue

            for item in items:
                signal_info = item.get("signal", {})

                # NEW: Use final_score when available
                if "final_score" in signal_info:
                    final_score = signal_info.get("final_score", 0.0)
                    # Convert 0-1 range to 0-100 for comparison
                    score_out_of_100 = final_score * 100

                    # Use score-based thresholds for high-signal content
                    if score_out_of_100 >= 50.0:  # Minimum threshold for high-signal
                        scored_items.append(
                            (source_type, item, final_score, score_out_of_100)
                        )

                # LEGACY: Fall back to existing logic for backward compatibility
                elif (
                    signal_info.get("strength") == "high"
                    or signal_info.get("is_lead")
                    or signal_info.get("is_founder")
                ):
                    # Estimate score for legacy items
                    legacy_score = 0.7 if signal_info.get("is_founder") else 0.6
                    scored_items.append(
                        (source_type, item, legacy_score, legacy_score * 100)
                    )

        if not scored_items:
            return high_signal_section

        # Sort by final_score (highest first)
        scored_items.sort(key=lambda x: x[2], reverse=True)

        # Create score-based tiers
        tiers = {
            "Critical Insights": [],  # 90+
            "High Priority": [],  # 70-89
            "Elevated": [],  # 50-69
        }

        for source_type, item, final_score, score_out_of_100 in scored_items:
            if score_out_of_100 >= 90:
                tiers["Critical Insights"].append((source_type, item, final_score))
            elif score_out_of_100 >= 70:
                tiers["High Priority"].append((source_type, item, final_score))
            else:
                tiers["Elevated"].append((source_type, item, final_score))

        # Process each tier
        for tier_name, tier_items in tiers.items():
            if not tier_items:
                continue

            tier_content = f"### {tier_name}\n\n"

            for source_type, item, final_score in tier_items:
                item_content = self._format_scored_item(item, source_type, final_score)
                tier_content += item_content + "\n\n"

            # Create metadata for this tier
            tier_slug = tier_name.lower().replace(" ", "-")
            chunk_id = f"high-signal-{date}-{tier_slug}-{self._get_next_chunk_id()}"
            metadata = MetadataBlock(
                source=f"data/aggregated/{date}.json",
                date=date,
                chunk_id=chunk_id,
                section_type="high_signal_insights",
                contributor_role=signal_info.get("contributor_role", "unknown"),
                signal_strength=tier_name.lower(),
            )

            # Handle semantic chunking
            chunks = self._chunk_content(tier_content, metadata, "high_signal_insights")
            for chunk in chunks:
                high_signal_section.add_chunk(chunk)

        return high_signal_section

    def _format_scored_item(
        self, item: Dict[str, Any], source_type: str, final_score: float
    ) -> str:
        """Format an item with scoring information for display."""
        title = self._get_item_title(item)
        author = item.get("author", "Unknown")
        content = self._clean_html_content(item.get("content", ""))
        url = item.get("url", "")

        signal_info = item.get("signal", {})
        role = signal_info.get("contributor_role", "contributor")
        author_weight = signal_info.get("author_weight", 0.0)
        recency_weight = signal_info.get("recency_weight", 0.0)

        # Create priority indicator based on score (text-based, no emojis)
        if final_score >= 0.9:
            priority_text = "[CRITICAL]"
        elif final_score >= 0.7:
            priority_text = "[HIGH]"
        else:
            priority_text = "[ELEVATED]"

        formatted = f"{priority_text} **{title}** by {author}"

        # Add role and scoring information
        if role != "contributor":
            formatted += f" ({role.replace('_', ' ').title()})"

        formatted += f" | Score: {final_score:.2f}"

        # Add scoring breakdown if available
        if author_weight > 0 or recency_weight > 0:
            formatted += (
                f" (Authority: {author_weight:.2f}, " f"Recency: {recency_weight:.2f})"
            )

        formatted += "\n\n"

        if content:
            # Truncate content if too long
            if len(content) > 300:
                content = content[:297] + "..."
            formatted += f"{content}\n\n"

        if url:
            formatted += f"[View source]({url})"

        return formatted

    def _create_general_activity_section(
        self, aggregated_data: Dict[str, Any], date: str
    ) -> DocumentSection:
        """Create the general activity section, excluding high-signal items."""
        general_section = DocumentSection("General Activity", 2)

        # Process each source type
        for source_type, items in aggregated_data.get("sources", {}).items():
            if not isinstance(items, list) or not items:
                continue

            # Filter out high-signal items (already covered in previous section)
            regular_items = []
            for item in items:
                signal_info = item.get("signal", {})

                # NEW: Use final_score when available
                if "final_score" in signal_info:
                    final_score = signal_info.get("final_score", 0.0)
                    score_out_of_100 = final_score * 100

                    # Only include items below high-signal threshold
                    if score_out_of_100 < 50.0:
                        regular_items.append(item)

                # LEGACY: Use existing logic for items without final_score
                elif not (
                    signal_info.get("strength") == "high"
                    or signal_info.get("is_lead")
                    or signal_info.get("is_founder")
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

    def _format_general_item(self, item: Dict[str, Any], source_type: str) -> str:
        """Format a general activity item for display."""
        title = self._get_item_title(item)
        author = item.get("author", "Unknown")
        url = item.get("url", "")

        formatted = f"- **{title}** by {author}"

        if url:
            formatted += f" ([link]({url}))"

        return formatted

    def _get_item_title(self, item: Dict[str, Any]) -> str:
        """Extract the proper title from an item, handling different data structures."""
        # For forum posts, check topic_title first
        if "topic_title" in item:
            return item["topic_title"]

        # For other items, use title field
        return item.get("title", "Untitled")

    def _clean_html_content(self, content: str) -> str:
        """Clean HTML content by stripping tags and converting to clean text."""
        if not content:
            return ""

        # Remove HTML comments
        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

        # Convert common HTML entities
        html_entities = {
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&apos;": "'",
            "&nbsp;": " ",
            "&#39;": "'",
        }
        for entity, replacement in html_entities.items():
            content = content.replace(entity, replacement)

        # Remove HTML tags but preserve content
        content = re.sub(
            r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(
            r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        content = re.sub(r"<[^>]+>", "", content)

        # Clean up whitespace
        content = re.sub(r"\s+", " ", content)
        content = content.strip()

        return content

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
