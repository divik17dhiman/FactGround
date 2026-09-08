"""Focused unit and integration tests for the evaluator-facing FastAPI application."""

from __future__ import annotations

import io

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

from superjoin_fact_knowledge.api import app, get_knowledge_base, reset_knowledge_base
from superjoin_fact_knowledge.relationship import CORROBORATED


def _generate_test_pdf_bytes(text: str) -> bytes:
    """Helper to generate an in-memory PDF with test text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture(autouse=True)
def clean_api_state() -> None:
    """Ensure in-memory KnowledgeBase is reset before and after each test."""
    reset_knowledge_base()
    yield
    reset_knowledge_base()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_root_endpoint_metadata(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "SuperJoin Fact Knowledge Layer API"
    assert "endpoints" in data
    assert data["total_facts"] == 0


def test_openapi_schema_documents_upload_control(client: TestClient) -> None:
    """Verify OpenAPI schema provides a multi-file 'files' upload control."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    doc_post = schema["paths"]["/documents"]["post"]
    req_body_schema = doc_post["requestBody"]["content"]["multipart/form-data"]["schema"]
    ref = req_body_schema.get("$ref")
    if ref:
        schema_name = ref.split("/")[-1]
        body_def = schema["components"]["schemas"][schema_name]
    else:
        body_def = req_body_schema

    assert "files" in body_def["properties"]
    files_prop = body_def["properties"]["files"]
    assert files_prop["type"] == "array"
    assert files_prop["items"]["type"] == "string"
    assert files_prop["items"]["format"] == "binary"
    assert "files" in body_def["required"]


def test_multiple_pdf_upload_success(client: TestClient) -> None:
    """Test 1: Multiple PDF upload.

    Uploads multiple PDFs in one request, verifies HTTP 201, both documents processed,
    facts extracted for each document, and structured response returned.
    """
    pdf_a = _generate_test_pdf_bytes("Acme Corp reported revenue of $50.0 million in FY2024.")
    pdf_b = _generate_test_pdf_bytes("Beta Corp reported shipments of 100000 units in FY2024.")
    files = [
        ("files", ("report_a.pdf", io.BytesIO(pdf_a), "application/pdf")),
        ("files", ("report_b.pdf", io.BytesIO(pdf_b), "application/pdf")),
    ]

    response = client.post("/documents", files=files)
    assert response.status_code == 201
    data = response.json()
    assert "Successfully processed 2 document(s)" in data["message"]
    assert len(data["documents"]) == 2

    doc_names = {d["document_name"] for d in data["documents"]}
    assert doc_names == {"report_a.pdf", "report_b.pdf"}
    assert data["total_facts_in_kb"] >= 2
    assert data["grounded_facts_in_kb"] >= 2


def test_query_facts_from_both_documents(client: TestClient) -> None:
    """Test 2: Query facts from both documents.

    Uploads two PDFs in one request, then queries for facts unique to document A
    and document B to confirm both entered the same KnowledgeBase.
    """
    pdf_a = _generate_test_pdf_bytes("Acme Corp reported operating profit of $12.5 million.")
    pdf_b = _generate_test_pdf_bytes("Beta Corp achieved gross margin of 22.5% in FY2024.")
    files = [
        ("files", ("doc_a.pdf", io.BytesIO(pdf_a), "application/pdf")),
        ("files", ("doc_b.pdf", io.BytesIO(pdf_b), "application/pdf")),
    ]
    upload_res = client.post("/documents", files=files)
    assert upload_res.status_code == 201

    # Query fact from doc A
    query_a = client.post("/query", json={"query": "Acme operating profit"})
    assert query_a.status_code == 200
    data_a = query_a.json()
    assert data_a["status"] == "answer_found"
    assert "$12.5 million" in data_a["answer"]
    assert data_a["evidence"][0]["document"] == "doc_a.pdf"

    # Query fact from doc B
    query_b = client.post("/query", json={"query": "Beta gross margin"})
    assert query_b.status_code == 200
    data_b = query_b.json()
    assert data_b["status"] == "answer_found"
    assert "22.5%" in data_b["answer"]
    assert data_b["evidence"][0]["document"] == "doc_b.pdf"


def test_provenance_preserves_original_filenames_multiple(client: TestClient) -> None:
    """Test 3: Provenance preservation for multiple documents.

    Verifies facts and evidence preserve original document filenames and do not
    expose generated server-side temporary filenames.
    """
    target_a = "annual_report_2024.pdf"
    target_b = "annual_report_2025.pdf"
    pdf_a = _generate_test_pdf_bytes("Acme Corp revenue reached $40.0 million in FY2024.")
    pdf_b = _generate_test_pdf_bytes("Acme Corp revenue reached $60.0 million in FY2025.")
    files = [
        ("files", ("annual_report_2024.pdf", io.BytesIO(pdf_a), "application/pdf")),
        ("files", ("annual_report_2025.pdf", io.BytesIO(pdf_b), "application/pdf")),
    ]

    upload_res = client.post("/documents", files=files)
    assert upload_res.status_code == 201

    facts_res = client.get("/facts")
    assert facts_res.status_code == 200
    facts = facts_res.json()["facts"]
    assert len(facts) >= 2

    provenance_docs = {f["document"] for f in facts}
    assert target_a in provenance_docs
    assert target_b in provenance_docs
    for doc_name in provenance_docs:
        assert "tmp" not in doc_name.lower() or doc_name in {target_a, target_b}


def test_cross_document_relationship_after_multi_upload(client: TestClient) -> None:
    """Test 4: Cross-document relationship after multiple PDF upload.

    Uploads two PDFs with corroborated facts in a single request and verifies
    the relationship reasoning system operates across the two documents.
    """
    pdf1 = _generate_test_pdf_bytes("Alpha Corp revenue was $50.0 million in FY2024.")
    pdf2 = _generate_test_pdf_bytes("Alpha Corp revenue stood at $50.0 million in FY2024.")
    files = [
        ("files", ("filing_a.pdf", io.BytesIO(pdf1), "application/pdf")),
        ("files", ("filing_b.pdf", io.BytesIO(pdf2), "application/pdf")),
    ]

    upload_res = client.post("/documents", files=files)
    assert upload_res.status_code == 201

    facts_res = client.get("/facts?fact_type=currency")
    facts = facts_res.json()["facts"]
    assert len(facts) >= 2

    fact_a_id = facts[0]["fact_id"]
    fact_b_id = facts[1]["fact_id"]

    compare_res = client.post(
        "/relationships/compare",
        json={"fact_a_id": fact_a_id, "fact_b_id": fact_b_id},
    )
    assert compare_res.status_code == 200
    assert compare_res.json()["state"] == CORROBORATED


def test_mixed_valid_invalid_upload_rejected(client: TestClient) -> None:
    """Test 5: Mixed valid/invalid upload rejected cleanly without partial ingestion."""
    valid_pdf = _generate_test_pdf_bytes("Acme Corp revenue was $10M in FY2024.")
    files = [
        ("files", ("valid.pdf", io.BytesIO(valid_pdf), "application/pdf")),
        ("files", ("invalid.txt", io.BytesIO(b"Just plain text notes"), "text/plain")),
    ]

    response = client.post("/documents", files=files)
    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]
    assert len(get_knowledge_base().facts) == 0


def test_empty_or_malformed_upload_set_rejected(client: TestClient) -> None:
    """Test 6: Validation handling for empty uploads and malformed PDFs."""
    # Empty file
    files_empty = [("files", ("empty.pdf", io.BytesIO(b""), "application/pdf"))]
    res_empty = client.post("/documents", files=files_empty)
    assert res_empty.status_code == 400
    assert "is empty" in res_empty.json()["detail"]
    assert len(get_knowledge_base().facts) == 0

    # Malformed PDF
    corrupt_bytes = b"This is random corrupt data not starting with %PDF"
    files_corrupt = [("files", ("corrupt.pdf", io.BytesIO(corrupt_bytes), "application/pdf"))]
    res_corrupt = client.post("/documents", files=files_corrupt)
    assert res_corrupt.status_code == 422
    detail = res_corrupt.json()["detail"]
    assert "Failed to ingest PDF 'corrupt.pdf'" in detail
    assert "AppData" not in detail
    assert "Temp" not in detail
    assert len(get_knowledge_base().facts) == 0


def test_single_pdf_upload_backward_compatibility(client: TestClient) -> None:
    """Test 7: Existing single-file behavior is preserved."""
    pdf_bytes = _generate_test_pdf_bytes("Delta Corp revenue was $75.0 million in FY2024.")
    files = [("files", ("delta_report.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]

    response = client.post("/documents", files=files)
    assert response.status_code == 201
    data = response.json()
    assert "Successfully processed 1 document(s)" in data["message"]
    assert len(data["documents"]) == 1
    assert data["documents"][0]["document_name"] == "delta_report.pdf"
    assert data["total_facts_in_kb"] >= 1


def test_query_unmatched_returns_refusal(client: TestClient) -> None:
    raw = "Acme Corp reported operating profit of $12.5 million in FY2024."
    pdf_bytes = _generate_test_pdf_bytes(raw)
    files = [("files", ("report_fy24.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    client.post("/documents", files=files)

    query_res = client.post("/query", json={"query": "nonexistent metric unrelated 99999"})
    assert query_res.status_code == 200
    data = query_res.json()

    assert data["status"] == "no_grounded_answer"
    assert data["is_grounded"] is False
    assert data["answer"] is None


def test_query_empty_string_rejected(client: TestClient) -> None:
    response = client.post("/query", json={"query": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_facts_endpoint_filtering_and_pagination(client: TestClient) -> None:
    raw = "Revenue was $10 million in FY2023. Margin reached 15% in FY2024."
    pdf_bytes = _generate_test_pdf_bytes(raw)
    files = [("files", ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    client.post("/documents", files=files)

    # Get all facts
    res_all = client.get("/facts")
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert data_all["total"] >= 2

    # Filter by fact_type
    res_currency = client.get("/facts?fact_type=currency")
    assert res_currency.status_code == 200
    for f in res_currency.json()["facts"]:
        assert f["fact_type"] == "currency"

    # Filter by status
    res_grounded = client.get("/facts?status=grounded")
    assert res_grounded.status_code == 200
    for f in res_grounded.json()["facts"]:
        assert f["status"] == "grounded"

    # Pagination
    res_page = client.get("/facts?limit=1&offset=0")
    assert res_page.status_code == 200
    assert len(res_page.json()["facts"]) == 1


def test_reset_endpoint(client: TestClient) -> None:
    pdf = _generate_test_pdf_bytes("Beta Corp shipments were 100000 units in FY2024.")
    files = [("files", ("beta.pdf", io.BytesIO(pdf), "application/pdf"))]
    client.post("/documents", files=files)
    assert len(get_knowledge_base().facts) >= 1

    res = client.post("/reset")
    assert res.status_code == 200
    assert res.json()["total_facts"] == 0
    assert len(get_knowledge_base().facts) == 0
