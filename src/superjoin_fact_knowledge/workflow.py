"""High-level evaluator-facing workflow for building and querying the knowledge base."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from .fact import Fact, extract_facts, validate_facts
from .ingestion import ingest_pdf
from .knowledge import KnowledgeBase, QueryResult, query_facts


def build_knowledge_base(
    pdf_paths: str | Path | Sequence[str | Path],
) -> KnowledgeBase:
    """Build a grounded knowledge base from one or more PDF files.

    Pipeline:
        PDF file(s)
          ↓
        ingest_pdf (per document)
          ↓
        extract_facts (deterministic)
          ↓
        validate_facts (grounding check)
          ↓
        KnowledgeBase (in-memory, multi-document aggregation)

    Args:
        pdf_paths: A single PDF path or a sequence of PDF paths.

    Returns:
        An immutable KnowledgeBase containing all validated facts across all documents.

    Raises:
        ValueError: If pdf_paths is empty or of invalid type.
        PDFIngestionError: If any PDF file cannot be found or read.
    """
    if isinstance(pdf_paths, (str, Path)):
        paths = [Path(pdf_paths)]
    elif isinstance(pdf_paths, Iterable):
        paths = [Path(p) for p in pdf_paths]
    else:
        raise ValueError(f"Expected path or sequence of paths, got {type(pdf_paths).__name__}")

    if not paths:
        raise ValueError("At least one PDF path must be provided to build a knowledge base.")

    all_validated_facts: list[Fact] = []

    for path in paths:
        document = ingest_pdf(path)
        facts = extract_facts(document)
        validated = validate_facts(facts, document)
        all_validated_facts.extend(validated)

    return KnowledgeBase.from_facts(all_validated_facts)


def query(
    knowledge_base: KnowledgeBase,
    query_text: str,
    *,
    limit: int = 5,
    include_needs_review: bool = False,
) -> QueryResult:
    """Query a knowledge base with a natural-language or keyword question.

    Args:
        knowledge_base: The KnowledgeBase to query.
        query_text: Natural language or keyword question string.
        limit: Maximum number of candidate matches to return.
        include_needs_review: Whether to include ungrounded review-only facts.

    Returns:
        QueryResult containing answer status, top answer text, and evidence citations.
    """
    return query_facts(
        knowledge_base,
        query_text,
        limit=limit,
        include_needs_review=include_needs_review,
    )
