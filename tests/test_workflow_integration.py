"""End-to-end integration tests for the public evaluator-facing workflow."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
import pytest

from superjoin_fact_knowledge import (
    PDFIngestionError,
    build_knowledge_base,
    query,
)

STARTER_BASE = Path(__file__).parent.parent / "starter-datasets" / "starter-datasets"


def _create_test_pdf(path: Path, pages: list[str]) -> Path:
    """Helper to generate a clean PDF with specified page text."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


class TestSingleDocumentWorkflow:
    """Test the single-document end-to-end pipeline."""

    def test_single_document_query_grounded(self, tmp_path: Path) -> None:
        pdf_path = _create_test_pdf(
            tmp_path / "annual_report.pdf",
            [
                "Company Overview. We had 15,000 employees worldwide.",
                "Consolidated Revenue grew to $85.5 million in FY2024.",
                "Operating margin improved to 21.5% in FY2024.",
            ],
        )

        kb = build_knowledge_base(pdf_path)
        assert len(kb.grounded_facts()) >= 3

        result = query(kb, "operating margin in FY2024")
        assert result.status == "answer_found"
        assert result.is_grounded is True
        assert result.answer_text is not None
        assert "21.5%" in result.answer_text

        # Verify provenance fields
        assert result.top_fact is not None
        assert result.top_fact.document_name == "annual_report.pdf"
        assert result.top_fact.page_number == 3
        assert result.top_fact.raw_value == "21.5%"
        assert result.top_fact.normalized_value == 21.5
        assert result.top_fact.unit == "percent"
        assert "21.5%" in result.top_fact.evidence_text

        # Verify structured dictionary serialization
        data = result.to_dict()
        assert data["is_grounded"] is True
        assert data["status"] == "answer_found"
        assert len(data["evidence"]) >= 1
        assert data["evidence"][0]["document"] == "annual_report.pdf"
        assert data["evidence"][0]["page"] == 3


class TestMultiDocumentWorkflow:
    """Test the multi-document aggregation and query pipeline."""

    def test_multi_document_provenance_retained(self, tmp_path: Path) -> None:
        pdf_a = _create_test_pdf(
            tmp_path / "alpha_corp.pdf",
            ["Alpha Corp reported net revenue of $10.5 million in FY2024."],
        )
        pdf_b = _create_test_pdf(
            tmp_path / "beta_inc.pdf",
            ["Beta Inc had total shipments of 4.2 million units in FY2024."],
        )

        kb = build_knowledge_base([pdf_a, pdf_b])

        # Verify facts from both documents exist
        doc_names = {fact.document_name for fact in kb.grounded_facts()}
        assert doc_names == {"alpha_corp.pdf", "beta_inc.pdf"}

        # Query fact from Document A
        result_a = kb.query("Alpha Corp revenue")
        assert result_a.status == "answer_found"
        assert result_a.top_fact is not None
        assert result_a.top_fact.document_name == "alpha_corp.pdf"
        assert "$10.5 million" in result_a.top_fact.raw_value

        # Query fact from Document B
        result_b = kb.query("Beta Inc shipments")
        assert result_b.status == "answer_found"
        assert result_b.top_fact is not None
        assert result_b.top_fact.document_name == "beta_inc.pdf"
        assert result_b.top_fact.raw_value == "4.2"
        assert result_b.top_fact.unit in ("million", "units")


class TestQueryEdgeCases:
    """Test ambiguous, missing, and empty queries."""

    @pytest.fixture
    def sample_kb(self, tmp_path: Path):
        pdf = _create_test_pdf(
            tmp_path / "report.pdf",
            [
                "Growth rate was 15.0% for Region North.",
                "Growth rate was 15.0% for Region South.",
            ],
        )
        return build_knowledge_base(pdf)

    def test_ambiguous_query_reports_ambiguity(self, sample_kb) -> None:
        # Both Region North and South share the identical score for "growth rate"
        result = sample_kb.query("growth rate")
        assert result.status == "ambiguous"
        assert result.is_grounded is False
        assert result.answer_text is None
        assert len(result.matches) >= 2

    def test_no_grounded_answer_when_unmatched(self, sample_kb) -> None:
        result = sample_kb.query("quantum semiconductor patents")
        assert result.status == "no_grounded_answer"
        assert result.is_grounded is False
        assert result.answer_text is None

    def test_empty_query_handled_cleanly(self, sample_kb) -> None:
        result = sample_kb.query("")
        assert result.status == "no_grounded_answer"
        assert result.is_grounded is False
        assert result.explanation == "Empty query string provided"


class TestErrorHandling:
    """Verify clean errors on invalid inputs."""

    def test_missing_pdf_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(PDFIngestionError, match="does not exist"):
            build_knowledge_base(tmp_path / "non_existent.pdf")

    def test_non_pdf_file_raises_error(self, tmp_path: Path) -> None:
        text_file = tmp_path / "test.txt"
        text_file.write_text("Hello world")
        with pytest.raises(PDFIngestionError, match="Unsupported file type"):
            build_knowledge_base(text_file)

    def test_empty_pdf_list_raises_error(self) -> None:
        with pytest.raises(ValueError, match="At least one PDF path"):
            build_knowledge_base([])

    def test_invalid_type_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Expected path or sequence of paths"):
            build_knowledge_base(12345)  # type: ignore


class TestRealStarterPDFWorkflow:
    """Test high-level public workflow with actual starter PDF."""

    @pytest.mark.skipif(not STARTER_BASE.exists(), reason="Starter datasets not present")
    def test_real_pdf_workflow(self) -> None:
        pdf_path = STARTER_BASE / "delhivery" / "03-delhivery-q4-fy24-earnings-presentation.pdf"
        kb = build_knowledge_base(pdf_path)
        assert len(kb.grounded_facts()) > 100

        result = kb.query("Express Parcel revenue FY24")
        assert result.matches
        assert any(
            "FY24" in m.fact.raw_value or "revenue" in m.fact.subject.lower()
            for m in result.matches
        )
        assert result.matches[0].fact.document_name == pdf_path.name
        assert result.matches[0].fact.page_number > 0
