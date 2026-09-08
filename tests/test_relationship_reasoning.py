"""Tests for cross-fact relationship classification and reasoning."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

from superjoin_fact_knowledge import (
    CONTEXTUALLY_RECONCILED,
    CONTRADICTED,
    CORROBORATED,
    INCOMPARABLE,
    UNCERTAIN,
    Fact,
    build_knowledge_base,
    compare_facts,
)


def _fact(
    *,
    fact_id: str,
    subject: str,
    fact_type: str,
    raw_value: str,
    normalized_value: float | int | str | None,
    unit: str | None = None,
    page_number: int = 1,
    status: str = "grounded",
    document_name: str = "doc.pdf",
    evidence_text: str = "",
) -> Fact:
    return Fact(
        fact_id=fact_id,
        subject=subject,
        fact_type=fact_type,
        raw_value=raw_value,
        normalized_value=normalized_value,
        unit=unit,
        metric=fact_type,
        evidence_text=evidence_text or f"{subject} {raw_value}".strip(),
        page_number=page_number,
        document_id="doc-id",
        document_name=document_name,
        confidence=1.0,
        status=status,
        metadata={},
    )


def test_corroborated_facts_same_period() -> None:
    """Facts with same entity, same period, and matching normalized value corroborate."""
    fact_a = _fact(
        fact_id="f1",
        subject="Consolidated Revenue",
        fact_type="currency",
        raw_value="$10.0 million",
        normalized_value=10_000_000.0,
        unit="currency",
        evidence_text="Consolidated Revenue reached $10.0 million in FY2024.",
    )
    fact_b = _fact(
        fact_id="f2",
        subject="Revenue",
        fact_type="currency",
        raw_value="$10.0M",
        normalized_value=10_000_000.0,
        unit="currency",
        evidence_text="Revenue was reported at $10.0M in FY2024.",
    )

    rel = compare_facts(fact_a, fact_b)
    assert rel.state == CORROBORATED
    assert rel.confidence == 1.0
    assert "corroborate" in rel.explanation.lower()


def test_contradicted_facts_same_period() -> None:
    """Facts with same entity and same period but conflicting values contradict."""
    fact_a = _fact(
        fact_id="f1",
        subject="Operating Margin",
        fact_type="percentage",
        raw_value="18.5%",
        normalized_value=18.5,
        unit="percent",
        evidence_text="Operating Margin stood at 18.5% in 2024.",
    )
    fact_b = _fact(
        fact_id="f2",
        subject="Operating Margin",
        fact_type="percentage",
        raw_value="14.2%",
        normalized_value=14.2,
        unit="percent",
        evidence_text="Operating Margin was revised to 14.2% in 2024.",
    )

    rel = compare_facts(fact_a, fact_b)
    assert rel.state == CONTRADICTED
    assert "contradict" in rel.explanation.lower()


def test_contextually_reconciled_different_periods() -> None:
    """Facts with same entity but different periods reconcile contextually."""
    fact_2023 = _fact(
        fact_id="f1",
        subject="Express Parcel revenue",
        fact_type="currency",
        raw_value="$4,552 million",
        normalized_value=4_552_000_000.0,
        unit="currency",
        evidence_text="Express Parcel revenue was $4,552 million in FY2023.",
    )
    fact_2024 = _fact(
        fact_id="f2",
        subject="Express Parcel revenue",
        fact_type="currency",
        raw_value="$5,077 million",
        normalized_value=5_077_000_000.0,
        unit="currency",
        evidence_text="Express Parcel revenue grew to $5,077 million in FY2024.",
    )

    rel = compare_facts(fact_2023, fact_2024)
    assert rel.state == CONTEXTUALLY_RECONCILED
    assert "different reporting periods" in rel.explanation.lower()


def test_incomparable_due_to_incompatible_units() -> None:
    """Facts with incompatible units cannot be compared (e.g. tonnes vs shipments)."""
    fact_tonnes = _fact(
        fact_id="f1",
        subject="Freight volume",
        fact_type="quantity",
        raw_value="5 million",
        normalized_value=5_000_000.0,
        unit="tonnes",
        evidence_text="Freight volume was 5 million tonnes in 2024.",
    )
    fact_shipments = _fact(
        fact_id="f2",
        subject="Freight volume",
        fact_type="quantity",
        raw_value="5 million",
        normalized_value=5_000_000.0,
        unit="shipments",
        evidence_text="Freight volume reached 5 million shipments in 2024.",
    )

    rel = compare_facts(fact_tonnes, fact_shipments)
    assert rel.state == INCOMPARABLE
    assert "incompatible measurement units" in rel.explanation.lower()


def test_incomparable_due_to_different_entities() -> None:
    """Facts referring to unrelated entities or metrics are incomparable."""
    fact_revenue = _fact(
        fact_id="f1",
        subject="Revenue",
        fact_type="currency",
        raw_value="$10 million",
        normalized_value=10_000_000.0,
        unit="currency",
        evidence_text="Revenue was $10 million in 2024.",
    )
    fact_headcount = _fact(
        fact_id="f2",
        subject="Employees headcount",
        fact_type="quantity",
        raw_value="1,200",
        normalized_value=1200.0,
        unit="employees",
        evidence_text="Employees headcount was 1,200 in 2024.",
    )

    rel = compare_facts(fact_revenue, fact_headcount)
    assert rel.state == INCOMPARABLE


def test_uncertain_when_fact_is_needs_review() -> None:
    """If either fact is ungrounded or needs review, relationship is uncertain."""
    fact_grounded = _fact(
        fact_id="f1",
        subject="Revenue",
        fact_type="currency",
        raw_value="$10M",
        normalized_value=10_000_000.0,
        unit="currency",
        status="grounded",
        evidence_text="Revenue was $10M in 2024.",
    )
    fact_review = _fact(
        fact_id="f2",
        subject="Revenue",
        fact_type="currency",
        raw_value="$10M",
        normalized_value=10_000_000.0,
        unit="currency",
        status="needs_review",
        evidence_text="Revenue was $10M in 2024.",
    )

    rel = compare_facts(fact_grounded, fact_review)
    assert rel.state == UNCERTAIN
    assert "not validated as grounded" in rel.explanation.lower()


def test_relationship_serialization() -> None:
    """FactRelationship should cleanly serialize to a structured dictionary."""
    fact_a = _fact(
        fact_id="f1",
        subject="GDP Growth",
        fact_type="percentage",
        raw_value="7.2%",
        normalized_value=7.2,
        unit="percent",
        evidence_text="GDP Growth was 7.2% in 2024.",
    )
    fact_b = _fact(
        fact_id="f2",
        subject="GDP Growth",
        fact_type="percentage",
        raw_value="7.2%",
        normalized_value=7.2,
        unit="percent",
        evidence_text="GDP Growth was 7.2% in 2024.",
    )

    rel = compare_facts(fact_a, fact_b)
    data = rel.to_dict()

    assert data["state"] == CORROBORATED
    assert data["fact_a_id"] == "f1"
    assert data["fact_b_id"] == "f2"
    assert "fact_a" in data
    assert "fact_b" in data
    assert "explanation" in data


def test_cross_document_comparison_via_knowledge_base(tmp_path: Path) -> None:
    """Test comparing facts extracted from two distinct PDFs via KnowledgeBase."""
    pdf1 = tmp_path / "prospectus.pdf"
    doc1 = fitz.open()
    page1 = doc1.new_page()
    page1.insert_text((72, 72), "Total revenue stood at $50.0 million in FY2023.")
    doc1.save(str(pdf1))
    doc1.close()

    pdf2 = tmp_path / "annual_report.pdf"
    doc2 = fitz.open()
    page2 = doc2.new_page()
    page2.insert_text((72, 72), "Total revenue reached $65.0 million in FY2024.")
    doc2.save(str(pdf2))
    doc2.close()

    kb = build_knowledge_base([pdf1, pdf2])
    res_2023 = kb.query("Total revenue in FY2023")
    res_2024 = kb.query("Total revenue in FY2024")

    assert res_2023.top_fact is not None
    assert res_2024.top_fact is not None

    rel = kb.compare_facts(res_2023.top_fact, res_2024.top_fact)
    assert rel.state == CONTEXTUALLY_RECONCILED
    assert res_2023.top_fact.document_name == "prospectus.pdf"
    assert res_2024.top_fact.document_name == "annual_report.pdf"
