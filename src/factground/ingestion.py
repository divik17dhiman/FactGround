"""PDF ingestion layer that isolates third-party PDF details behind a domain model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf as fitz

from .document import Document, DocumentDiagnostics, Page


class PDFIngestionError(ValueError):
    """Raised when a source file is invalid or cannot be ingested."""


def ingest_pdf(path: str | Path) -> Document:
    """Load a PDF and return a page-aware domain representation.

    The public API deliberately returns the project-owned document model rather than
    a third-party PDF object so future extractors can depend on stable domain types.
    """
    source = Path(path)

    if not source.exists():
        raise PDFIngestionError(f"PDF file does not exist: {source}")
    if source.is_dir():
        raise PDFIngestionError(f"Input path is a directory, not a PDF file: {source}")
    if source.suffix.lower() != ".pdf":
        raise PDFIngestionError(f"Unsupported file type for PDF ingestion: {source}")

    document = None
    try:
        document = fitz.open(str(source))
    except Exception as exc:  # pragma: no cover - platform-specific failure handling
        raise PDFIngestionError(f"Unable to open PDF file {source}: {exc}") from exc

    try:
        pages: list[Page] = []
        page_texts = 0
        empty_pages: list[int] = []
        approx_chars = 0

        for page_index in range(len(document)):
            fitz_page = document.load_page(page_index)
            page_number = page_index + 1
            page_text = fitz_page.get_text("text")
            text = page_text or ""
            has_text = bool(text.strip())

            if not has_text:
                empty_pages.append(page_number)
            else:
                page_texts += 1
                approx_chars += len(text)

            pages.append(
                Page(
                    page_number=page_number,
                    text=text,
                    metadata={
                        "page_index": page_index,
                        "rotation": fitz_page.rotation,
                        "mediabox": list(fitz_page.mediabox),
                    },
                    has_extractable_text=has_text,
                )
            )

        if not pages:
            raise PDFIngestionError(f"PDF file is empty and contains no pages: {source}")

        diagnostics = DocumentDiagnostics(
            page_count=len(pages),
            pages_with_text=page_texts,
            pages_without_text=len(empty_pages),
            empty_pages=empty_pages,
            approximate_character_count=approx_chars,
        )

        source_metadata: dict[str, Any] = {
            "file_size_bytes": source.stat().st_size,
            "page_count": len(document),
            "encrypted": document.is_encrypted,
            "is_pdf": source.suffix.lower() == ".pdf",
        }

        return Document.create(
            source_path=str(source),
            source_name=source.name,
            source_metadata=source_metadata,
            pages=pages,
            diagnostics=diagnostics,
        )
    except PDFIngestionError:
        raise
    except Exception as exc:  # pragma: no cover - library-specific failure handling
        raise PDFIngestionError(f"PDF file is invalid or unreadable: {source}") from exc
    finally:
        if document is not None:
            document.close()
