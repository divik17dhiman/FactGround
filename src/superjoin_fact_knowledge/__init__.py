"""Superjoin Fact Knowledge Layer package."""

from .document import Document, DocumentDiagnostics, Page, PageDiagnostic
from .fact import Fact, extract_facts
from .ingestion import PDFIngestionError, ingest_pdf

__all__ = [
    "Document",
    "DocumentDiagnostics",
    "Fact",
    "Page",
    "PageDiagnostic",
    "PDFIngestionError",
    "__version__",
    "extract_facts",
    "ingest_pdf",
]

__version__ = "0.1.0"
