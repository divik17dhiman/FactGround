"""Tests for evidence grounding and validation of extracted facts."""

from __future__ import annotations

from superjoin_fact_knowledge import (
    Document,
    DocumentDiagnostics,
    Fact,
    Page,
    extract_facts,
    validate_fact,
    validate_facts,
)


def _make_document(*, pages: list[Page]) -> Document:
    """Build a minimal document for grounding tests."""
    return Document(
        document_id="doc-456",
        source_path="/tmp/grounded.pdf",
        source_name="grounded.pdf",
        source_metadata={"file_size_bytes": 2048},
        pages=pages,
        diagnostics=DocumentDiagnostics(
            page_count=len(pages),
            pages_with_text=sum(1 for page in pages if page.has_extractable_text),
            pages_without_text=sum(1 for page in pages if not page.has_extractable_text),
            empty_pages=[page.page_number for page in pages if not page.has_extractable_text],
            approximate_character_count=sum(len(page.text) for page in pages),
        ),
    )


def test_extracts_multiple_facts_from_one_sentence_with_local_evidence() -> None:
    """Multiple facts in one sentence should each keep the shared local evidence and page."""
    document = _make_document(
        pages=[
            Page(
                page_number=1,
                text=(
                    "Revenue increased to $12.4 million and EBITDA was $8.1 million. "
                    "Operating margin was 18.2% and cash conversion was 19.1%."
                ),
                metadata={},
                has_extractable_text=True,
            )
        ]
    )

    facts = extract_facts(document)
    currency_facts = [fact for fact in facts if fact.fact_type == "currency"]
    percentage_facts = [fact for fact in facts if fact.fact_type == "percentage"]

    assert [fact.raw_value for fact in currency_facts] == ["$12.4 million", "$8.1 million"]
    assert [fact.page_number for fact in currency_facts] == [1, 1]
    assert [fact.raw_value for fact in percentage_facts] == ["18.2%", "19.1%"]
    assert [fact.page_number for fact in percentage_facts] == [1, 1]
    assert all(fact.evidence_text.startswith("Revenue increased") for fact in currency_facts)
    assert all("Operating margin was 18.2%" in fact.evidence_text for fact in percentage_facts)


def test_validate_fact_marks_grounded_facts_without_altering_raw_source() -> None:
    """Validated facts should stay traceable to the original raw source text."""
    document = _make_document(
        pages=[
            Page(
                page_number=2,
                text="Revenue increased to $12.4 million in FY2025.",
                metadata={},
                has_extractable_text=True,
            )
        ]
    )

    fact = extract_facts(document)[0]
    validated_fact = validate_fact(fact, document)

    assert validated_fact.status == "grounded"
    assert validated_fact.metadata["validation_issues"] == []
    assert validated_fact.raw_value == "$12.4 million"
    assert validated_fact.normalized_value == 12400000.0
    assert validated_fact.document_id == document.document_id
    assert validated_fact.document_name == document.source_name
    assert validated_fact.page_number == 2


def test_validate_fact_detects_invalid_page_and_missing_evidence() -> None:
    """Facts with missing evidence or impossible pages should be marked for review."""
    document = _make_document(
        pages=[
            Page(
                page_number=1,
                text="Revenue increased to $12.4 million.",
                metadata={},
                has_extractable_text=True,
            )
        ]
    )

    fact = Fact.create(
        subject="revenue",
        fact_type="currency",
        raw_value="$12.4 million",
        normalized_value=12400000.0,
        unit="currency",
        evidence_text="",
        page_number=99,
        document_id=document.document_id,
        document_name=document.source_name,
        metric="currency_value",
    )

    validated_fact = validate_fact(fact, document)

    assert validated_fact.status == "needs_review"
    assert validated_fact.metadata["validation_issues"] == [
        "invalid_page_number",
        "missing_evidence",
    ]


def test_validate_fact_detects_normalization_mismatch() -> None:
    """A mismatched normalized value should be surfaced as a validation issue."""
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

    fact = Fact.create(
        subject="operating margin",
        fact_type="percentage",
        raw_value="18.2%",
        normalized_value=18.0,
        unit="percent",
        evidence_text="Operating margin was 18.2% in FY2025.",
        page_number=3,
        document_id=document.document_id,
        document_name=document.source_name,
        metric="percentage",
    )

    validated_fact = validate_fact(fact, document)

    assert validated_fact.status == "needs_review"
    assert "normalized_value_mismatch" in validated_fact.metadata["validation_issues"]
    assert validated_fact.raw_value == "18.2%"


def test_validate_facts_handles_empty_pages_and_malformed_text() -> None:
    """Validation should not crash when pages are empty or contain malformed text."""
    document = _make_document(
        pages=[
            Page(page_number=1, text="", metadata={}, has_extractable_text=False),
            Page(
                page_number=2,
                text="@@@ ??? Revenue was approximately 12 to 14 million.",
                metadata={},
                has_extractable_text=True,
            ),
        ]
    )

    facts = extract_facts(document)
    validated_facts = validate_facts(facts, document)

    assert facts == []
    assert validated_facts == []
    assert document.diagnostics.empty_pages == [1]


def test_ambiguous_values_are_not_silently_fabricated() -> None:
    """Ambiguous text without a grounded value should not produce a fabricated fact."""
    document = _make_document(
        pages=[
            Page(
                page_number=1,
                text="Revenue was approximately 12 to 14 million.",
                metadata={},
                has_extractable_text=True,
            )
        ]
    )

    assert extract_facts(document) == []
