"""Integration test for the Phase 1 to Phase 4 contract."""

from __future__ import annotations

from pathlib import Path

import fitz

from superjoin_fact_knowledge import KnowledgeBase, extract_facts, ingest_pdf, validate_facts


def _write_pdf(path: Path, page_texts: list[str]) -> None:
    """Create a deterministic PDF for integration coverage."""
    pdf = fitz.open()
    for text in page_texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


def test_pdf_to_grounded_query_pipeline(tmp_path: Path) -> None:
    """The end-to-end pipeline should preserve value, page, evidence, and grounding state."""
    pdf_path = tmp_path / "report.pdf"
    _write_pdf(
        pdf_path,
        [
            "Revenue increased to $12.4 million in FY2025.",
            "Operating margin was 18.2% in FY2025.",
        ],
    )

    document = ingest_pdf(pdf_path)
    facts = extract_facts(document)
    validated_facts = validate_facts(facts, document)
    knowledge_base = KnowledgeBase.from_facts(validated_facts)

    result = knowledge_base.query("operating margin")

    assert result.status == "answer_found"
    assert result.answer_text == "Operating margin was 18.2%."
    assert result.matches[0].fact.raw_value == "18.2%"
    assert result.matches[0].fact.unit == "percent"
    assert result.matches[0].fact.page_number == 2
    assert result.matches[0].fact.evidence_text == "Operating margin was 18.2% in FY2025."
    assert result.matches[0].fact.status == "grounded"
