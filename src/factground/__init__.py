"""FactGround package: an evidence-grounded fact knowledge layer."""

from .api import app
from .document import Document, DocumentDiagnostics, Page, PageDiagnostic
from .fact import Fact, extract_facts, validate_fact, validate_facts
from .ingestion import PDFIngestionError, ingest_pdf
from .knowledge import KnowledgeBase, QueryMatch, QueryResult, query_facts
from .relationship import (
    CONTEXTUALLY_RECONCILED,
    CONTRADICTED,
    CORROBORATED,
    INCOMPARABLE,
    UNCERTAIN,
    FactRelationship,
    compare_facts,
)
from .workflow import build_knowledge_base, query

__all__ = [
    "CONTEXTUALLY_RECONCILED",
    "CONTRADICTED",
    "CORROBORATED",
    "Document",
    "DocumentDiagnostics",
    "Fact",
    "FactRelationship",
    "INCOMPARABLE",
    "KnowledgeBase",
    "Page",
    "PageDiagnostic",
    "PDFIngestionError",
    "QueryMatch",
    "QueryResult",
    "UNCERTAIN",
    "__version__",
    "app",
    "build_knowledge_base",
    "compare_facts",
    "extract_facts",
    "ingest_pdf",
    "query",
    "query_facts",
    "validate_fact",
    "validate_facts",
]

__version__ = "0.1.0"
