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
    metadata: dict | None = None,
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
        metadata=metadata or {},
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


def test_gate_test_a_same_value_same_context() -> None:
    """Test A: Same metric, same period, same value -> CORROBORATED."""
    fact_a = _fact(
        fact_id="fa",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Revenue was ₹100m in FY2024.",
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Revenue was ₹100m in FY2024.",
    )
    rel = compare_facts(fact_a, fact_b)
    assert rel.state == CORROBORATED
    assert "corroborate" in rel.explanation.lower()
    assert "100000000.0" in rel.explanation


def test_gate_test_b_same_metric_same_period_different_value() -> None:
    """Test B: Same metric, same period, different value -> CONTRADICTED."""
    fact_a = _fact(
        fact_id="fa",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Revenue was ₹100m in FY2024.",
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹120m",
        normalized_value=120_000_000.0,
        unit="currency",
        evidence_text="Revenue was ₹120m in FY2024.",
    )
    rel = compare_facts(fact_a, fact_b)
    assert rel.state == CONTRADICTED
    assert "contradict" in rel.explanation.lower()
    assert "FY2024" in rel.explanation


def test_gate_test_c_same_metric_different_period() -> None:
    """Test C: Same metric, different period -> CONTEXTUALLY_RECONCILED."""
    fact_a = _fact(
        fact_id="fa",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Revenue was ₹100m in FY2023.",
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹120m",
        normalized_value=120_000_000.0,
        unit="currency",
        evidence_text="Revenue was ₹120m in FY2024.",
    )
    rel = compare_facts(fact_a, fact_b)
    assert rel.state == CONTEXTUALLY_RECONCILED
    assert "different reporting periods" in rel.explanation.lower()
    assert "FY2023" in rel.explanation and "FY2024" in rel.explanation


def test_gate_test_d_same_metric_unknown_period() -> None:
    """Test D: Same metric, unknown period -> UNCERTAIN."""
    fact_a = _fact(
        fact_id="fa",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Revenue stands at ₹100m.",
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹120m",
        normalized_value=120_000_000.0,
        unit="currency",
        evidence_text="Revenue stands at ₹120m.",
    )
    rel = compare_facts(fact_a, fact_b)
    assert rel.state == UNCERTAIN
    assert "cannot be confirmed" in rel.explanation.lower()


def test_gate_test_e_different_scopes() -> None:
    """Test E: Different scopes (Fresh Issue vs Offer for Sale) -> INCOMPARABLE."""
    fact_a = _fact(
        fact_id="fa",
        subject="Fresh Issue",
        fact_type="currency",
        raw_value="₹40,000m",
        normalized_value=40_000_000_000.0,
        unit="currency",
        evidence_text="Fresh Issue of Equity Shares aggregating to ₹40,000m.",
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Offer for Sale",
        fact_type="currency",
        raw_value="₹12,350m",
        normalized_value=12_350_000_000.0,
        unit="currency",
        evidence_text="Offer for Sale of Equity Shares aggregating to ₹12,350m.",
    )
    rel = compare_facts(fact_a, fact_b)
    assert rel.state == INCOMPARABLE
    assert "different scopes" in rel.explanation.lower()


def test_gate_test_f_component_vs_aggregate() -> None:
    """Test F: Component vs aggregate (Fresh Issue vs Total Offer) -> INCOMPARABLE."""
    fact_a = _fact(
        fact_id="fa",
        subject="Fresh Issue",
        fact_type="currency",
        raw_value="₹40,000m",
        normalized_value=40_000_000_000.0,
        unit="currency",
        evidence_text="Fresh Issue of Equity Shares aggregating to ₹40,000m.",
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Total Offer",
        fact_type="currency",
        raw_value="₹52,350m",
        normalized_value=52_350_000_000.0,
        unit="currency",
        evidence_text="Total Offer size aggregating to ₹52,350m.",
    )
    rel = compare_facts(fact_a, fact_b)
    assert rel.state == INCOMPARABLE
    assert "different scopes" in rel.explanation.lower()


def test_gate_test_g_different_metrics() -> None:
    """Test G: Different metrics (Revenue vs Market Capitalization) -> INCOMPARABLE."""
    fact_a = _fact(
        fact_id="fa",
        subject="Revenue",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Revenue reached ₹100m.",
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Market Capitalization",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Market Capitalization reached ₹100m.",
    )
    rel = compare_facts(fact_a, fact_b)
    assert rel.state == INCOMPARABLE
    assert "distinct entities or metrics" in rel.explanation.lower()


def test_gate_test_h_different_entities() -> None:
    """Test H: Different entities (Company A revenue vs Company B revenue) -> INCOMPARABLE."""
    fact_a = _fact(
        fact_id="fa",
        subject="Company A revenue",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Company A revenue was ₹100m in FY2024.",
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Company B revenue",
        fact_type="currency",
        raw_value="₹100m",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Company B revenue was ₹100m in FY2024.",
    )
    rel = compare_facts(fact_a, fact_b)
    assert rel.state == INCOMPARABLE
    assert "different entities" in rel.explanation.lower()
    assert "Company A" in rel.explanation and "Company B" in rel.explanation


def test_real_delhivery_prospectus_scopes_not_contradicted() -> None:
    """Section 15: Verify real Delhivery prospectus facts are not classified as contradictions."""
    starter_dir = Path("starter-datasets/starter-datasets/delhivery")
    prospectus_path = starter_dir / "01-delhivery-prospectus-2022-excerpt.pdf"
    if not prospectus_path.exists():
        return

    kb = build_knowledge_base(str(prospectus_path))
    grounded = kb.grounded_facts()

    f_fresh = [
        f
        for f in grounded
        if f.page_number == 1 and "40,000" in f.raw_value and f.fact_type == "currency"
    ]
    f_ofs = [
        f
        for f in grounded
        if f.page_number == 1 and "12,350" in f.raw_value and f.fact_type == "currency"
    ]
    f_total = [
        f
        for f in grounded
        if f.page_number == 1 and "52,350" in f.raw_value and f.fact_type == "currency"
    ]

    assert len(f_fresh) >= 1
    assert len(f_ofs) >= 1
    assert len(f_total) >= 1

    rel = compare_facts(f_fresh[0], f_ofs[0])
    assert rel.state != CONTRADICTED
    assert rel.state == INCOMPARABLE
    # Verify no false period list is reported in explanation
    assert "2011" not in rel.explanation
    assert "2013" not in rel.explanation
    assert "2018" not in rel.explanation
    assert "2022" not in rel.explanation

    rel_tot = compare_facts(f_fresh[0], f_total[0])
    assert rel_tot.state != CONTRADICTED
    assert rel_tot.state == INCOMPARABLE


# =========================================================================
# Local Temporal Association & Correctness Tests (Tests A through J)
# =========================================================================


def test_local_temporal_association_test_a_two_values_two_periods() -> None:
    """Test A: Two values, two periods in one sentence get separate local periods."""
    from superjoin_fact_knowledge.document import Document, DocumentDiagnostics, Page
    from superjoin_fact_knowledge.fact import _sentence_fact_candidates, validate_facts

    page = Page(page_number=1, text="")
    diag = DocumentDiagnostics(page_count=1, pages_with_text=1, pages_without_text=0)
    doc = Document.create(
        source_path="test.pdf",
        source_name="test.pdf",
        source_metadata={},
        pages=[page],
        diagnostics=diag,
    )

    text = "Revenue was $100 million in FY2023 and increased to $120 million in FY2024."
    facts = [f for f in _sentence_fact_candidates(text, page, doc) if f.fact_type == "currency"]
    facts = validate_facts(facts, doc)

    assert len(facts) == 2
    f100 = [f for f in facts if f.normalized_value == 100_000_000.0][0]
    f120 = [f for f in facts if f.normalized_value == 120_000_000.0][0]

    assert f100.period == "FY2023"
    assert f120.period == "FY2024"

    rel = compare_facts(f100, f120)
    assert rel.state == CONTEXTUALLY_RECONCILED


def test_local_temporal_association_test_b_from_to_construction() -> None:
    """Test B: From ... to ... construction associates correct period to each value."""
    from superjoin_fact_knowledge.document import Document, DocumentDiagnostics, Page
    from superjoin_fact_knowledge.fact import _sentence_fact_candidates, validate_facts

    page = Page(page_number=1, text="")
    diag = DocumentDiagnostics(page_count=1, pages_with_text=1, pages_without_text=0)
    doc = Document.create(
        source_path="test.pdf",
        source_name="test.pdf",
        source_metadata={},
        pages=[page],
        diagnostics=diag,
    )

    text = "Revenue increased from $100 million in FY2023 to $120 million in FY2024."
    facts = [f for f in _sentence_fact_candidates(text, page, doc) if f.fact_type == "currency"]
    facts = validate_facts(facts, doc)

    assert len(facts) == 2
    f100 = [f for f in facts if f.normalized_value == 100_000_000.0][0]
    f120 = [f for f in facts if f.normalized_value == 120_000_000.0][0]

    assert f100.period == "FY2023"
    assert f120.period == "FY2024"

    rel = compare_facts(f100, f120)
    assert rel.state == CONTEXTUALLY_RECONCILED


def test_local_temporal_association_test_c_compared_with_construction() -> None:
    """Test C: Compared-with construction associates correct 4-digit year to each value."""
    from superjoin_fact_knowledge.document import Document, DocumentDiagnostics, Page
    from superjoin_fact_knowledge.fact import _sentence_fact_candidates, validate_facts

    page = Page(page_number=1, text="")
    diag = DocumentDiagnostics(page_count=1, pages_with_text=1, pages_without_text=0)
    doc = Document.create(
        source_path="test.pdf",
        source_name="test.pdf",
        source_metadata={},
        pages=[page],
        diagnostics=diag,
    )

    text = "The company generated $500 million in 2023, compared with $450 million in 2022."
    facts = [f for f in _sentence_fact_candidates(text, page, doc) if f.fact_type == "currency"]
    facts = validate_facts(facts, doc)

    assert len(facts) == 2
    f500 = [f for f in facts if f.normalized_value == 500_000_000.0][0]
    f450 = [f for f in facts if f.normalized_value == 450_000_000.0][0]

    assert f500.period == "2023"
    assert f450.period == "2022"

    rel = compare_facts(f500, f450)
    assert rel.state == CONTEXTUALLY_RECONCILED


def test_local_temporal_association_test_d_forecast_growth_construction() -> None:
    """Test D: Forecast/growth construction associates periods and captures qualifier."""
    from superjoin_fact_knowledge.document import Document, DocumentDiagnostics, Page
    from superjoin_fact_knowledge.fact import _sentence_fact_candidates, validate_facts

    page = Page(page_number=1, text="")
    diag = DocumentDiagnostics(page_count=1, pages_with_text=1, pages_without_text=0)
    doc = Document.create(
        source_path="test.pdf",
        source_name="test.pdf",
        source_metadata={},
        pages=[page],
        diagnostics=diag,
    )

    text = (
        "Direct spend was $216 billion in Fiscal 2020 and is expected to grow to "
        "$365 billion by Fiscal 2026."
    )
    facts = [f for f in _sentence_fact_candidates(text, page, doc) if f.fact_type == "currency"]
    facts = validate_facts(facts, doc)

    assert len(facts) == 2
    f216 = [f for f in facts if f.normalized_value == 216_000_000_000.0][0]
    f365 = [f for f in facts if f.normalized_value == 365_000_000_000.0][0]

    assert f216.period == "FY2020"
    assert f365.period == "FY2026"
    assert f365.temporal_qualifier == "expected"

    rel = compare_facts(f216, f365)
    assert rel.state == CONTEXTUALLY_RECONCILED
    assert rel.state != CONTRADICTED


def test_local_temporal_association_test_e_existing_delhivery_regression() -> None:
    """Test E: Real Delhivery prospectus extract associates FY2020 and FY2026 and reconciles."""
    starter_dir = Path("starter-datasets/starter-datasets/delhivery")
    prospectus_path = starter_dir / "01-delhivery-prospectus-2022-excerpt.pdf"
    if not prospectus_path.exists():
        return

    kb = build_knowledge_base(str(prospectus_path))
    grounded = kb.grounded_facts()

    f216_list = [
        f for f in grounded if f.page_number == 3 and f.normalized_value == 216_000_000_000.0
    ]
    f365_list = [
        f for f in grounded if f.page_number == 3 and f.normalized_value == 365_000_000_000.0
    ]

    assert len(f216_list) >= 1
    assert len(f365_list) >= 1

    f216 = f216_list[0]
    f365 = f365_list[0]

    assert f216.period == "FY2020"
    assert f365.period == "FY2026"
    assert f365.temporal_qualifier == "expected"

    rel = compare_facts(f216, f365)
    assert rel.state == CONTEXTUALLY_RECONCILED
    assert rel.state != CONTRADICTED


def test_local_temporal_association_test_f_same_period_genuine_contradiction() -> None:
    """Test F: Same entity, same period, different values genuinely contradict."""
    fact_a = _fact(
        fact_id="fa",
        subject="Company Alpha revenue",
        fact_type="currency",
        raw_value="$100 million",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Company Alpha reported revenue of $100 million in FY2024.",
        metadata={"period": "FY2024"},
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Company Alpha revenue",
        fact_type="currency",
        raw_value="$120 million",
        normalized_value=120_000_000.0,
        unit="currency",
        evidence_text="Company Alpha reported revenue of $120 million in FY2024.",
        metadata={"period": "FY2024"},
    )

    rel = compare_facts(fact_a, fact_b)
    assert rel.state == CONTRADICTED


def test_local_temporal_association_test_g_same_value_different_periods() -> None:
    """Test G: Same value across different periods preserves existing semantics."""
    fact_a = _fact(
        fact_id="fa",
        subject="Revenue",
        fact_type="currency",
        raw_value="$100 million",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Revenue was $100 million in FY2023.",
        metadata={"period": "FY2023"},
    )
    fact_b = _fact(
        fact_id="fb",
        subject="Revenue",
        fact_type="currency",
        raw_value="$100 million",
        normalized_value=100_000_000.0,
        unit="currency",
        evidence_text="Revenue was $100 million in FY2024.",
        metadata={"period": "FY2024"},
    )

    rel = compare_facts(fact_a, fact_b)
    # Under existing relationship semantics, matching normalized values corroborate
    assert rel.state == CORROBORATED


def test_local_temporal_association_test_h_ambiguous_period_returns_none() -> None:
    """Test H: Ambiguous periods leave period as None, avoiding false contradiction."""
    from superjoin_fact_knowledge.document import Document, DocumentDiagnostics, Page
    from superjoin_fact_knowledge.fact import _sentence_fact_candidates

    page = Page(page_number=1, text="")
    diag = DocumentDiagnostics(page_count=1, pages_with_text=1, pages_without_text=0)
    doc = Document.create(
        source_path="test.pdf",
        source_name="test.pdf",
        source_metadata={},
        pages=[page],
        diagnostics=diag,
    )

    text = "Between 2021 and 2022, revenue was $100 million."
    facts = _sentence_fact_candidates(text, page, doc)

    assert len(facts) >= 1
    f100 = facts[0]
    # Period must not be guessed when ambiguous
    assert f100.period is None


def test_local_temporal_association_test_i_scope_regression_fresh_issue_vs_offer_for_sale() -> None:
    """Test I: Fresh Issue vs Offer for Sale and Total Offer must remain INCOMPARABLE."""
    fact_fresh = _fact(
        fact_id="f1",
        subject="Fresh Issue",
        fact_type="currency",
        raw_value="₹40,000 million",
        normalized_value=40_000_000_000.0,
        unit="currency",
        evidence_text="Fresh Issue of up to ₹40,000 million",
        metadata={"scope": "Fresh Issue"},
    )
    fact_ofs = _fact(
        fact_id="f2",
        subject="Offer for Sale",
        fact_type="currency",
        raw_value="₹12,350 million",
        normalized_value=12_350_000_000.0,
        unit="currency",
        evidence_text="Offer for Sale of up to ₹12,350 million",
        metadata={"scope": "Offer for Sale"},
    )
    fact_total = _fact(
        fact_id="f3",
        subject="Total Offer",
        fact_type="currency",
        raw_value="₹52,350 million",
        normalized_value=52_350_000_000.0,
        unit="currency",
        evidence_text="Total Offer of up to ₹52,350 million",
        metadata={"scope": "Total Offer"},
    )

    rel_ofs = compare_facts(fact_fresh, fact_ofs)
    assert rel_ofs.state == INCOMPARABLE
    assert rel_ofs.state != CONTRADICTED

    rel_tot = compare_facts(fact_fresh, fact_total)
    assert rel_tot.state == INCOMPARABLE
    assert rel_tot.state != CONTRADICTED


def test_local_temporal_association_test_j_existing_relationship_demonstrations() -> None:
    """Test J: Existing relationship types remain valid."""
    # 1. Corroborated
    f_corr_a = _fact(
        fact_id="c1",
        subject="Revenue",
        fact_type="currency",
        raw_value="$10M",
        normalized_value=10_000_000.0,
        unit="currency",
        metadata={"period": "FY2024"},
    )
    f_corr_b = _fact(
        fact_id="c2",
        subject="Revenue",
        fact_type="currency",
        raw_value="$10.0 million",
        normalized_value=10_000_000.0,
        unit="currency",
        metadata={"period": "FY2024"},
    )
    assert compare_facts(f_corr_a, f_corr_b).state == CORROBORATED

    # 2. Contradicted
    f_contra_b = _fact(
        fact_id="c3",
        subject="Revenue",
        fact_type="currency",
        raw_value="$15M",
        normalized_value=15_000_000.0,
        unit="currency",
        metadata={"period": "FY2024"},
    )
    assert compare_facts(f_corr_a, f_contra_b).state == CONTRADICTED

    # 3. Contextually Reconciled
    f_recon_b = _fact(
        fact_id="c4",
        subject="Revenue",
        fact_type="currency",
        raw_value="$15M",
        normalized_value=15_000_000.0,
        unit="currency",
        metadata={"period": "FY2025"},
    )
    assert compare_facts(f_corr_a, f_recon_b).state == CONTEXTUALLY_RECONCILED

    # 4. Uncertain (missing period)
    f_unc_a = _fact(
        fact_id="u1",
        subject="Revenue",
        fact_type="currency",
        raw_value="$10M",
        normalized_value=10_000_000.0,
        unit="currency",
    )
    f_unc_b = _fact(
        fact_id="u2",
        subject="Revenue",
        fact_type="currency",
        raw_value="$15M",
        normalized_value=15_000_000.0,
        unit="currency",
    )
    assert compare_facts(f_unc_a, f_unc_b).state == UNCERTAIN
