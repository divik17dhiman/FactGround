"""Tests for deterministic fact extraction from a Phase 1 document model."""

from __future__ import annotations

from superjoin_fact_knowledge import Document, DocumentDiagnostics, Page, extract_facts


def _make_document(*, pages: list[Page]) -> Document:
    """Build a minimal document for fact extraction tests."""
    return Document(
        document_id="doc-123",
        source_path="/tmp/sample.pdf",
        source_name="sample.pdf",
        source_metadata={"file_size_bytes": 1024},
        pages=pages,
        diagnostics=DocumentDiagnostics(
            page_count=len(pages),
            pages_with_text=sum(1 for page in pages if page.has_extractable_text),
            pages_without_text=sum(1 for page in pages if not page.has_extractable_text),
            empty_pages=[page.page_number for page in pages if not page.has_extractable_text],
            approximate_character_count=sum(len(page.text) for page in pages),
        ),
    )


def test_extracts_currency_and_percentage_facts() -> None:
    """A sentence containing a currency and a percentage should yield structured facts."""
    document = _make_document(
        pages=[
            Page(
                page_number=1,
                text="Revenue increased to $12.4 million in FY2025. Operating margin was 18.2%.",
                metadata={},
                has_extractable_text=True,
            )
        ]
    )

    facts = extract_facts(document)

    currency_fact = next(f for f in facts if f.fact_type == "currency")
    percentage_fact = next(f for f in facts if f.fact_type == "percentage")

    assert currency_fact.subject.lower() == "revenue"
    assert currency_fact.raw_value == "$12.4 million"
    assert currency_fact.normalized_value == 12400000.0
    assert currency_fact.page_number == 1
    assert "Revenue increased" in currency_fact.evidence_text

    assert percentage_fact.subject.lower() == "operating margin"
    assert percentage_fact.raw_value == "18.2%"
    assert percentage_fact.normalized_value == 18.2


def test_extracts_date_and_quantity_facts() -> None:
    """Dates and quantities should retain their original raw representation and page provenance."""
    document = _make_document(
        pages=[
            Page(
                page_number=2,
                text="The company had 4,500 employees. Acquisition completed in March 2025.",
                metadata={},
                has_extractable_text=True,
            )
        ]
    )

    facts = extract_facts(document)

    quantity_fact = next(f for f in facts if f.fact_type == "quantity")
    date_fact = next(f for f in facts if f.fact_type == "date")

    assert quantity_fact.subject.lower() == "company"
    assert quantity_fact.raw_value == "4,500"
    assert quantity_fact.unit == "employees"
    assert quantity_fact.normalized_value == 4500.0
    assert quantity_fact.page_number == 2

    assert date_fact.subject.lower() == "acquisition"
    assert date_fact.raw_value == "March 2025"
    assert date_fact.page_number == 2
    assert date_fact.evidence_text


def test_ignores_page_numbers_and_handles_empty_pages() -> None:
    """Irrelevant page numbers should not become facts, and empty pages should be ignored."""
    document = _make_document(
        pages=[
            Page(
                page_number=1,
                text="Page 7 of the report.",
                metadata={},
                has_extractable_text=True,
            ),
            Page(page_number=2, text="", metadata={}, has_extractable_text=False),
        ]
    )

    facts = extract_facts(document)

    assert facts == []


def test_preserves_raw_representation_and_evidence() -> None:
    """Facts should retain raw text and page provenance for later validation and grounding."""
    document = _make_document(
        pages=[
            Page(
                page_number=3,
                text="Operating margin was 18.2% in FY2025.",
                metadata={},
                has_extractable_text=True,
            )
        ]
    )

    facts = extract_facts(document)
    fact = facts[0]

    assert fact.raw_value == "18.2%"
    assert fact.normalized_value == 18.2
    assert fact.evidence_text == "Operating margin was 18.2% in FY2025."
    assert fact.page_number == 3
    assert fact.document_name == "sample.pdf"
