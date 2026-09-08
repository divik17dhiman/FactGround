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


def test_upload_valid_pdf(client: TestClient) -> None:
    pdf_bytes = _generate_test_pdf_bytes("Acme Corp reported revenue of $25.0 million in FY2024.")
    files = [("files", ("annual_report.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]

    response = client.post("/documents", files=files)
    assert response.status_code == 201
    data = response.json()
    assert "Successfully processed 1 document(s)" in data["message"]
    assert data["total_facts_in_kb"] >= 1
    assert data["grounded_facts_in_kb"] >= 1

    doc_meta = data["documents"][0]
    assert doc_meta["document_name"] == "annual_report.pdf"
    assert doc_meta["facts_extracted"] >= 1


def test_upload_invalid_non_pdf_file(client: TestClient) -> None:
    files = [("files", ("notes.txt", io.BytesIO(b"Just some text"), "text/plain"))]
    response = client.post("/documents", files=files)
    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]


def test_upload_empty_file(client: TestClient) -> None:
    files = [("files", ("empty.pdf", io.BytesIO(b""), "application/pdf"))]
    response = client.post("/documents", files=files)
    assert response.status_code == 400
    assert "is empty" in response.json()["detail"]


def test_query_after_upload(client: TestClient) -> None:
    raw = "Acme Corp reported operating profit of $12.5 million in FY2024."
    pdf_bytes = _generate_test_pdf_bytes(raw)
    files = [("files", ("report_fy24.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    upload_res = client.post("/documents", files=files)
    assert upload_res.status_code == 201

    # Query matching currency fact
    query_res = client.post("/query", json={"query": "operating profit amount in FY2024"})
    assert query_res.status_code == 200
    data = query_res.json()

    assert data["status"] == "answer_found"
    assert data["is_grounded"] is True
    assert "$12.5 million" in data["answer"]
    assert len(data["matches"]) >= 1
    assert len(data["evidence"]) >= 1
    assert data["evidence"][0]["document"] == "report_fy24.pdf"
    assert data["evidence"][0]["page"] == 1


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


def test_relationships_endpoints(client: TestClient) -> None:
    # Upload doc 1
    pdf1 = _generate_test_pdf_bytes("Alpha Corp revenue was $50.0 million in FY2024.")
    client.post("/documents", files=[("files", ("doc1.pdf", io.BytesIO(pdf1), "application/pdf"))])

    # Upload doc 2 with corroborated revenue
    pdf2 = _generate_test_pdf_bytes("Alpha Corp revenue stood at $50.0 million in FY2024.")
    client.post("/documents", files=[("files", ("doc2.pdf", io.BytesIO(pdf2), "application/pdf"))])

    # Get facts to find their IDs
    facts_res = client.get("/facts?fact_type=currency")
    facts = facts_res.json()["facts"]
    assert len(facts) >= 2

    fact_a_id = facts[0]["fact_id"]
    fact_b_id = facts[1]["fact_id"]

    # Test GET /relationships with targeted IDs
    rel_res = client.get(f"/relationships?fact_a_id={fact_a_id}&fact_b_id={fact_b_id}")
    assert rel_res.status_code == 200
    rel_data = rel_res.json()["relationships"][0]
    assert rel_data["state"] == CORROBORATED

    # Test POST /relationships/compare
    post_comp = client.post(
        "/relationships/compare",
        json={"fact_a_id": fact_a_id, "fact_b_id": fact_b_id},
    )
    assert post_comp.status_code == 200
    assert post_comp.json()["state"] == CORROBORATED

    # Test GET /relationships pairwise scan
    res_scan = client.get("/relationships")
    assert res_scan.status_code == 200
    assert "relationships" in res_scan.json()


def test_reset_endpoint(client: TestClient) -> None:
    pdf = _generate_test_pdf_bytes("Beta Corp shipments were 100000 units in FY2024.")
    client.post("/documents", files=[("files", ("beta.pdf", io.BytesIO(pdf), "application/pdf"))])
    assert len(get_knowledge_base().facts) >= 1

    res = client.post("/reset")
    assert res.status_code == 200
    assert res.json()["total_facts"] == 0
    assert len(get_knowledge_base().facts) == 0
