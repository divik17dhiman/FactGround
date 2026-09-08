"""Regression tests using real starter PDFs from Phase 5 evaluation."""

from pathlib import Path

import pytest

from superjoin_fact_knowledge import (
    KnowledgeBase,
    extract_facts,
    ingest_pdf,
    validate_facts,
)

STARTER_BASE = Path(__file__).parent.parent / "starter-datasets" / "starter-datasets"
pytestmark = pytest.mark.skipif(
    not STARTER_BASE.exists(),
    reason="Starter datasets not present in environment",
)


class TestDelhiveryProspectus:
    """Test extraction from Delhivery Prospectus 2022."""

    @pytest.fixture
    def document(self):
        """Load the prospectus document."""
        pdf_path = STARTER_BASE / "delhivery" / "01-delhivery-prospectus-2022-excerpt.pdf"
        return ingest_pdf(str(pdf_path))

    def test_ingestion_succeeds(self, document):
        """Verify the PDF ingests without errors."""
        assert document.diagnostics.page_count == 100
        assert document.diagnostics.pages_with_text > 0

    def test_extraction_produces_facts(self, document):
        """Verify fact extraction produces meaningful results."""
        facts = extract_facts(document)
        assert len(facts) > 0
        assert len(facts) > 500  # Should extract substantial number

    def test_all_facts_validate(self, document):
        """Verify all extracted facts pass validation."""
        facts = extract_facts(document)
        validated = validate_facts(facts, document)

        grounded = [f for f in validated if f.status == "grounded"]
        assert len(grounded) == len(validated)  # All should be grounded
        assert len(grounded) > 500

    def test_fact_types_present(self, document):
        """Verify expected fact types are extracted."""
        facts = extract_facts(document)
        fact_types = {f.fact_type for f in facts}

        assert "currency" in fact_types
        assert "date" in fact_types
        assert "percentage" in fact_types

    def test_subject_quality(self, document):
        """Verify subjects are not duplicated or truncated."""
        facts = extract_facts(document)

        # Check for repeated words like "Fiscal Fiscal"
        bad_subjects = [f.subject for f in facts if " " in f.subject]
        for subject in bad_subjects:
            words = subject.split()
            for i in range(len(words) - 1):
                assert words[i].lower() != words[i + 1].lower(), (
                    f"Subject has repeated words: {subject}"
                )

    def test_unit_quality(self, document):
        """Verify quantity units are valid and not noise."""
        facts = extract_facts(document)
        quantity_facts = [f for f in facts if f.fact_type == "quantity"]

        # Invalid units that should be filtered
        invalid_units = {"of", "to", "for", "from", "and", "or"}

        for fact in quantity_facts:
            unit_lower = (fact.unit or "").lower()
            assert unit_lower not in invalid_units, (
                f"Quantity has invalid unit: {fact.unit} for {fact.subject}"
            )


class TestDelhiveryAnnualReport:
    """Test extraction from Delhivery Annual Report FY24."""

    @pytest.fixture
    def document(self):
        """Load the annual report."""
        pdf_path = STARTER_BASE / "delhivery" / "02-delhivery-annual-report-fy24-excerpt.pdf"
        return ingest_pdf(str(pdf_path))

    def test_ingestion_succeeds(self, document):
        """Verify the PDF ingests without errors."""
        assert document.diagnostics.page_count == 100

    def test_extraction_produces_substantial_facts(self, document):
        """Verify significant fact extraction from financial statements."""
        facts = extract_facts(document)
        assert len(facts) > 1000  # Annual reports have many figures


class TestIndiaEconomicSurvey:
    """Test extraction from India Economic Survey 2024-25."""

    @pytest.fixture
    def document(self):
        """Load the economic survey."""
        pdf_path = (
            STARTER_BASE / "india-macroeconomy" / "01-india-economic-survey-2024-25-excerpt.pdf"
        )
        return ingest_pdf(str(pdf_path))

    def test_ingestion_succeeds(self, document):
        """Verify the PDF ingests without errors."""
        assert document.diagnostics.pages_with_text > 0

    def test_extraction_succeeds(self, document):
        """Verify extraction works on macroeconomic data."""
        facts = extract_facts(document)
        assert len(facts) > 500


class TestKnowledgeLayerOnRealData:
    """Test the knowledge layer with real starter PDFs."""

    @pytest.fixture
    def knowledge_base(self):
        """Create knowledge base from first Delhivery document."""
        pdf_path = STARTER_BASE / "delhivery" / "01-delhivery-prospectus-2022-excerpt.pdf"
        document = ingest_pdf(str(pdf_path))
        facts = extract_facts(document)
        validated = validate_facts(facts, document)
        return KnowledgeBase.from_facts(validated)

    def test_kb_creation_succeeds(self, knowledge_base):
        """Verify knowledge base creation."""
        assert len(knowledge_base.facts) > 0

    def test_grounded_facts_available(self, knowledge_base):
        """Verify grounded facts can be queried."""
        grounded = knowledge_base.grounded_facts()
        assert len(grounded) > 0

    def test_queries_produce_results(self, knowledge_base):
        """Verify queries return meaningful matches."""
        result = knowledge_base.query("shares")
        assert len(result.matches) > 0

    def test_query_preserves_provenance(self, knowledge_base):
        """Verify query results include provenance."""
        result = knowledge_base.query("percent")
        for match in result.matches[:1]:
            assert match.fact.page_number > 0
            assert len(match.fact.evidence_text) > 0


class TestBaselineMetrics:
    """Verify baseline metrics from Phase 5 evaluation."""

    def test_total_facts_extracted(self):
        """Verify approximately correct total facts extracted."""
        all_facts = []
        for domain in ["delhivery", "india-macroeconomy"]:
            domain_path = STARTER_BASE / domain
            for pdf_file in sorted(domain_path.glob("*.pdf")):
                doc = ingest_pdf(str(pdf_file))
                facts = extract_facts(doc)
                all_facts.extend(facts)

        # We expect 8612 facts after improvements (was 8714 before)
        # Allow ±100 variation for different systems
        assert 8500 < len(all_facts) < 8700, f"Expected ~8612 facts, got {len(all_facts)}"

    def test_validation_passes_for_all_pdfs(self):
        """Verify 100% validation pass rate across all PDFs."""
        for domain in ["delhivery", "india-macroeconomy"]:
            domain_path = STARTER_BASE / domain
            for pdf_file in sorted(domain_path.glob("*.pdf")):
                doc = ingest_pdf(str(pdf_file))
                facts = extract_facts(doc)
                validated = validate_facts(facts, doc)

                grounded = [f for f in validated if f.status == "grounded"]
                assert len(grounded) == len(validated), (
                    f"Not all facts validated in {pdf_file.name}"
                )
