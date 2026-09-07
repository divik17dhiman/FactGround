"""Domain model for ingested PDF documents and pages."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PageDiagnostic:
    """Basic extraction diagnostics for a single page."""

    page_number: int
    has_extractable_text: bool
    text_length: int


@dataclass(slots=True)
class DocumentDiagnostics:
    """High-level document-level extraction metadata."""

    page_count: int
    pages_with_text: int
    pages_without_text: int
    empty_pages: list[int] = field(default_factory=list)
    approximate_character_count: int = 0


@dataclass(slots=True)
class Page:
    """A single page in the domain model, carrying provenance and extracted text."""

    page_number: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    has_extractable_text: bool = False


@dataclass(slots=True)
class Document:
    """Represents a source PDF as a page-aware domain object."""

    document_id: str
    source_path: str
    source_name: str
    source_metadata: dict[str, Any]
    pages: list[Page]
    diagnostics: DocumentDiagnostics

    @classmethod
    def create(
        cls,
        *,
        source_path: str,
        source_name: str,
        source_metadata: dict[str, Any],
        pages: list[Page],
        diagnostics: DocumentDiagnostics,
    ) -> "Document":
        """Construct a document while generating a stable internal identifier."""
        return cls(
            document_id=uuid.uuid4().hex,
            source_path=source_path,
            source_name=source_name,
            source_metadata=source_metadata,
            pages=pages,
            diagnostics=diagnostics,
        )
