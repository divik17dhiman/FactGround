"""Superjoin Fact Knowledge Layer package."""

from .document import Document, DocumentDiagnostics, Page, PageDiagnostic
from .fact import Fact, extract_facts, validate_fact, validate_facts
from .ingestion import PDFIngestionError, ingest_pdf
from .knowledge import KnowledgeBase, QueryMatch, QueryResult, query_facts

__all__ = [
    "Document",
    "DocumentDiagnostics",
    "Fact",
    "KnowledgeBase",
    "Page",
    "PageDiagnostic",
    "PDFIngestionError",
    "QueryMatch",
    "QueryResult",
    "__version__",
    "extract_facts",
    "ingest_pdf",
    "query_facts",
    "validate_fact",
    "validate_facts",
]

__version__ = "0.1.0"
