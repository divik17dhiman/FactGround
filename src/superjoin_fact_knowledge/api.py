"""FastAPI application exposing the SuperJoin Fact Knowledge Layer.

Provides endpoints for:
- Uploading and ingesting PDF documents into the KnowledgeBase (POST /documents)
- Inspecting extracted and validated facts (GET /facts)
- Querying grounded facts with deterministic scoring (POST /query)
- Comparing facts and evaluating relationships (GET /relationships, POST /relationships/compare)
- Resetting in-memory state (POST /reset)
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field, GetJsonSchemaHandler

from .ingestion import PDFIngestionError
from .knowledge import KnowledgeBase
from .relationship import (
    FactRelationship,
    compare_facts,
)
from .workflow import build_knowledge_base

# Global in-memory KnowledgeBase instance
_kb = KnowledgeBase.empty()


def get_knowledge_base() -> KnowledgeBase:
    """Return the current global KnowledgeBase instance."""
    return _kb


def set_knowledge_base(kb: KnowledgeBase) -> None:
    """Set the global KnowledgeBase instance (useful for testing)."""
    global _kb
    _kb = kb


def reset_knowledge_base() -> None:
    """Reset the global KnowledgeBase to empty state."""
    global _kb
    _kb = KnowledgeBase.empty()


class PDFUploadFile(UploadFile):
    """UploadFile subclass that emits format: binary in OpenAPI JSON schema for Swagger UI."""

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Mapping[str, Any], handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        return {"type": "string", "format": "binary"}


app = FastAPI(
    title="SuperJoin Fact Knowledge Layer API",
    description=(
        "Evaluator API for ingesting financial/business PDFs, extracting grounded facts, "
        "querying verifiable evidence, and reasoning about cross-fact relationships."
    ),
    version="0.1.0",
)


def custom_openapi() -> dict[str, Any]:
    """Custom OpenAPI schema generator ensuring array file uploads have format: binary."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    for schema_val in openapi_schema.get("components", {}).get("schemas", {}).values():
        props = schema_val.get("properties", {})
        if "files" in props and props["files"].get("type") == "array":
            items = props["files"].setdefault("items", {})
            items["type"] = "string"
            items["format"] = "binary"
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


class QueryRequest(BaseModel):
    """Request payload for querying the knowledge base."""

    query: str = Field(..., min_length=1, description="Natural language or keyword query")
    limit: int = Field(5, ge=1, le=50, description="Maximum candidate matches to return")
    include_needs_review: bool = Field(
        False, description="Whether to include ungrounded review facts"
    )


class CompareRequest(BaseModel):
    """Request payload for comparing two specific facts."""

    fact_a_id: str = Field(..., description="ID of the first fact")
    fact_b_id: str = Field(..., description="ID of the second fact")


@app.get("/", tags=["System"])
def root_info() -> dict[str, Any]:
    """Root metadata endpoint."""
    return {
        "service": "SuperJoin Fact Knowledge Layer API",
        "version": "0.1.0",
        "total_facts": len(_kb.facts),
        "grounded_facts": len(_kb.grounded_facts()),
        "endpoints": {
            "documents": "POST /documents",
            "facts": "GET /facts",
            "query": "POST /query",
            "relationships": "GET /relationships",
            "compare": "POST /relationships/compare",
            "docs": "/docs",
        },
    }


@app.post("/reset", tags=["System"])
def reset_endpoint() -> dict[str, Any]:
    """Reset the in-memory knowledge base to empty state."""
    reset_knowledge_base()
    return {"message": "Knowledge base successfully reset", "total_facts": 0}


@app.post("/documents", status_code=status.HTTP_201_CREATED, tags=["Documents"])
async def upload_documents(
    files: Annotated[
        list[PDFUploadFile],
        File(description="One or more PDF document files to upload and ingest"),
    ],
) -> dict[str, Any]:
    """Upload one or more PDF files and ingest their facts into the KnowledgeBase.

    Validates:
    - Non-empty file list
    - Every file has a non-empty filename with .pdf extension
    - Every file contains non-empty content
    - PDF contents are valid and readable

    Adapts the uploaded files into temporary paths, passes them as a batch to the
    existing path-based workflow, preserves original filenames for provenance, and
    cleans up all temporary files safely.
    """
    global _kb

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided in upload request.",
        )

    # 1. Validate every upload before any processing or temporary file creation
    file_contents: list[tuple[str, bytes]] = []
    for file in files:
        filename = file.filename or ""
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing filename in upload request.",
            )

        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"File '{filename}' is not a valid PDF document. Only .pdf files are supported."
                ),
            )

        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{filename}' is empty.",
            )
        file_contents.append((filename, content))

    # 2. Safely create temporary files for all valid PDFs
    temp_paths: list[str] = []
    temp_to_orig: dict[str, str] = {}
    try:
        for filename, content in file_contents:
            fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            temp_paths.append(temp_path)
            # Map both basename and full path to the original filename
            temp_to_orig[Path(temp_path).name] = filename
            temp_to_orig[temp_path] = filename

        # 3. Process the complete upload set as one logical ingestion operation
        try:
            new_kb = build_knowledge_base(temp_paths)
        except PDFIngestionError as exc:
            # Map temporary path back to original filename if present in exception
            failed_name = None
            for p, orig in temp_to_orig.items():
                if p in str(exc):
                    failed_name = orig
                    break
            detail = (
                f"Failed to ingest PDF '{failed_name}': "
                "Document is malformed, corrupted, or not a readable PDF."
                if failed_name
                else (
                    "Failed to ingest uploaded document(s): "
                    "One or more PDF files are malformed, corrupted, or not readable."
                )
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process uploaded documents.",
            ) from exc

        # 4. Preserve original uploaded filenames in fact provenance
        renamed_facts = [
            replace(fact, document_name=temp_to_orig.get(fact.document_name, fact.document_name))
            if fact.document_name in temp_to_orig
            else fact
            for fact in new_kb.facts
        ]

        _kb = _kb.add_facts(renamed_facts)

        # 5. Build structured per-document response
        processed_docs: list[dict[str, Any]] = []
        for filename, _ in file_contents:
            doc_facts = [f for f in renamed_facts if f.document_name == filename]
            grounded_count = sum(1 for f in doc_facts if f.status == "grounded")
            review_count = len(doc_facts) - grounded_count
            processed_docs.append(
                {
                    "document_name": filename,
                    "facts_extracted": len(doc_facts),
                    "grounded_facts": grounded_count,
                    "review_facts": review_count,
                }
            )

        return {
            "message": f"Successfully processed {len(processed_docs)} document(s).",
            "documents": processed_docs,
            "total_facts_in_kb": len(_kb.facts),
            "grounded_facts_in_kb": len(_kb.grounded_facts()),
        }

    finally:
        for p in temp_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


@app.get("/facts", tags=["Facts"])
def get_facts(
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status: 'grounded' or 'needs_review'"
    ),
    document: str | None = Query(None, description="Filter by document name"),
    fact_type: str | None = Query(None, description="Filter by fact type"),
    limit: int = Query(50, ge=1, le=200, description="Max facts to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict[str, Any]:
    """Retrieve structured facts from the KnowledgeBase with optional filtering."""
    facts = _kb.facts

    if status_filter:
        facts = tuple(f for f in facts if f.status == status_filter)
    if document:
        doc_lower = document.lower()
        facts = tuple(f for f in facts if doc_lower in f.document_name.lower())
    if fact_type:
        facts = tuple(f for f in facts if f.fact_type == fact_type)

    total_count = len(facts)
    paginated = facts[offset : offset + limit]

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "facts": [f.to_dict() for f in paginated],
    }


@app.post("/query", tags=["Query"])
def query_endpoint(req: QueryRequest) -> dict[str, Any]:
    """Query the KnowledgeBase using deterministic keyword and entity scoring.

    Returns the structured QueryResult containing status, answer, candidate matches,
    provenance, and grounding validation.
    """
    clean_query = req.query.strip()
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty.",
        )

    result = _kb.query(
        clean_query,
        limit=req.limit,
        include_needs_review=req.include_needs_review,
    )

    return result.to_dict()


@app.get("/relationships", tags=["Relationships"])
def get_relationships(
    fact_a_id: str | None = Query(None, description="Optional ID for first fact"),
    fact_b_id: str | None = Query(None, description="Optional ID for second fact"),
    state: str | None = Query(None, description="Filter by state"),
    limit: int = Query(50, ge=1, le=200, description="Max relationships to return"),
) -> dict[str, Any]:
    """Inspect evaluated relationships between facts in the KnowledgeBase.

    If fact_a_id and fact_b_id are provided, compares those two specific facts.
    Otherwise, evaluates pairwise relationships among grounded facts in the KnowledgeBase.
    """
    fact_map = {f.fact_id: f for f in _kb.facts}

    # Targeted comparison between two specific facts
    if fact_a_id and fact_b_id:
        fact_a = fact_map.get(fact_a_id)
        fact_b = fact_map.get(fact_b_id)
        if not fact_a:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fact A with ID '{fact_a_id}' not found in knowledge base.",
            )
        if not fact_b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fact B with ID '{fact_b_id}' not found in knowledge base.",
            )
        rel = compare_facts(fact_a, fact_b)
        return {"total": 1, "relationships": [rel.to_dict()]}

    # Pairwise evaluation over grounded facts
    grounded = _kb.grounded_facts()
    relationships: list[FactRelationship] = []

    # Compare pairs (capped to prevent quadratic explosion on large datasets)
    max_candidates = min(len(grounded), 40)
    for i in range(max_candidates):
        for j in range(i + 1, max_candidates):
            fa = grounded[i]
            fb = grounded[j]
            # Focus on facts that share subjects or metrics
            if fa.fact_type == fb.fact_type:
                rel = compare_facts(fa, fb)
                if state is None or rel.state == state:
                    relationships.append(rel)
                    if len(relationships) >= limit:
                        break
        if len(relationships) >= limit:
            break

    return {
        "total": len(relationships),
        "limit": limit,
        "relationships": [r.to_dict() for r in relationships[:limit]],
    }


@app.post("/relationships/compare", tags=["Relationships"])
def compare_endpoint(req: CompareRequest) -> dict[str, Any]:
    """Compare two facts by ID and classify their relationship state."""
    fact_map = {f.fact_id: f for f in _kb.facts}
    fact_a = fact_map.get(req.fact_a_id)
    fact_b = fact_map.get(req.fact_b_id)

    if not fact_a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact A with ID '{req.fact_a_id}' not found.",
        )
    if not fact_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact B with ID '{req.fact_b_id}' not found.",
        )

    rel = compare_facts(fact_a, fact_b)
    return rel.to_dict()
