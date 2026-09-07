"""Superjoin Fact Knowledge Layer package."""

from .document import Document, DocumentDiagnostics, Page, PageDiagnostic
from .ingestion import PDFIngestionError, ingest_pdf

__all__ = [
    "Document",
    "DocumentDiagnostics",
    "Page",
    "PageDiagnostic",
    "PDFIngestionError",
    "__version__",
    "ingest_pdf",
]

__version__ = "0.1.0"
