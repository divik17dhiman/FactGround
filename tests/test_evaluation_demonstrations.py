"""Automated test suite verifying the four required evaluation cases:
1. Corroboration
2. Contradiction
3. Contextual Reconciliation
4. Extraction / Reasoning Failure
"""

from __future__ import annotations

from pathlib import Path

from examples.run_demonstrations import (
    run_case_1_corroboration,
    run_case_2_contradiction,
    run_case_3_contextual_reconciliation,
    run_case_4_extraction_failure,
)
from factground.relationship import (
    CONTEXTUALLY_RECONCILED,
    CONTRADICTED,
    CORROBORATED,
)


def test_case_1_corroboration(tmp_path: Path) -> None:
    res = run_case_1_corroboration(tmp_path)
    assert res["passed"] is True
    assert res["relationship"]["state"] == CORROBORATED
    assert "Express Parcel" in res["fact_a"]["subject"]
    assert "650.0 million" in res["fact_a"]["raw_value"]
    assert "650.0 million" in res["fact_b"]["raw_value"]
    assert res["fact_a"]["document"] == "filing_doc_a.pdf"
    assert res["fact_b"]["document"] == "press_release_doc_b.pdf"
    assert res["fact_a"]["status"] == "grounded"
    assert res["fact_b"]["status"] == "grounded"


def test_case_2_contradiction(tmp_path: Path) -> None:
    res = run_case_2_contradiction(tmp_path)
    assert res["passed"] is True
    assert res["relationship"]["state"] == CONTRADICTED

    # Verify same entity, metric, period, unit
    assert "Alpha operating profit" in res["fact_a"]["subject"]
    assert "Alpha operating profit" in res["fact_b"]["subject"]
    assert res["fact_a"]["unit"] == res["fact_b"]["unit"]

    # Verify both are grounded actual reported claims
    assert res["fact_a"]["status"] == "grounded"
    assert res["fact_b"]["status"] == "grounded"
    assert res["fact_a"]["page"] == 1
    assert res["fact_b"]["page"] == 1
    assert res["fact_a"]["document"] == "disclosure_doc_a.pdf"
    assert res["fact_b"]["document"] == "disclosure_doc_b.pdf"

    # Verify conflicting values
    assert "38.5 million" in res["fact_a"]["raw_value"]
    assert "45.0 million" in res["fact_b"]["raw_value"]
    assert "Contradicting values" in res["relationship"]["explanation"]

    # Regression: Ensure no epistemic mismatch (no analyst estimate or forecast language)
    assert "analyst" not in res["fact_a"]["document"].lower()
    assert "analyst" not in res["fact_b"]["document"].lower()
    assert "estimate" not in res["fact_a"]["document"].lower()
    assert "estimate" not in res["fact_b"]["document"].lower()
    assert "estimate" not in res["fact_a"]["evidence"].lower()
    assert "estimate" not in res["fact_b"]["evidence"].lower()


def test_case_3_contextual_reconciliation(tmp_path: Path) -> None:
    res = run_case_3_contextual_reconciliation(tmp_path)
    assert res["passed"] is True
    assert res["relationship"]["state"] == CONTEXTUALLY_RECONCILED
    assert "shipments" in res["fact_a"]["subject"].lower()
    assert "740" in res["fact_a"]["raw_value"]
    assert res["fact_a"]["unit"] == "million"
    assert "820" in res["fact_b"]["raw_value"]
    assert res["fact_b"]["unit"] == "million"
    assert "different reporting periods" in res["relationship"]["explanation"]
    assert res["fact_a"]["status"] == "grounded"
    assert res["fact_b"]["status"] == "grounded"


def test_case_4_extraction_failure_and_refusal(tmp_path: Path) -> None:
    res = run_case_4_extraction_failure(tmp_path)
    assert res["passed"] is True
    assert res["has_extractable_text"] is False
    assert res["facts_extracted"] == 0
    assert res["query_status"] == "no_grounded_answer"
    assert res["is_grounded"] is False
    assert res["answer"] is None


def test_evidence_provenance_and_grounding_invariants(tmp_path: Path) -> None:
    """Verify that every grounded fact retains valid evidence text and respects the invariant."""
    for case_fn in (
        run_case_1_corroboration,
        run_case_2_contradiction,
        run_case_3_contextual_reconciliation,
    ):
        res = case_fn(tmp_path)
        for key in ("fact_a", "fact_b"):
            fact_dict = res[key]
            assert fact_dict["status"] == "grounded"
            assert fact_dict["page"] >= 1
            assert len(fact_dict["evidence"]) > 0
            # Confirm raw_value appears in the cited evidence
            assert fact_dict["raw_value"] in fact_dict["evidence"]


def test_real_starter_document_corroboration() -> None:
    """Verify genuine corroboration between Delhivery Annual Report and Earnings Presentation."""
    from factground import build_knowledge_base, compare_facts

    starter_dir = Path("starter-datasets/starter-datasets/delhivery")
    ar_path = starter_dir / "02-delhivery-annual-report-fy24-excerpt.pdf"
    q4_path = starter_dir / "03-delhivery-q4-fy24-earnings-presentation.pdf"

    if not ar_path.exists() or not q4_path.exists():
        return  # Gracefully skip if starter datasets are absent

    kb_ar = build_knowledge_base(str(ar_path))
    kb_q4 = build_knowledge_base(str(q4_path))

    # Amortisation expense on page 36 of Annual Report (13.19%) vs page 17 of Q4 Earnings (13.2%)
    facts_ar = [
        f
        for f in kb_ar.grounded_facts()
        if "amortisation" in f.subject.lower()
        and f.page_number == 36
        and f.fact_type == "percentage"
    ]
    facts_q4 = [
        f
        for f in kb_q4.grounded_facts()
        if "amortisation" in f.subject.lower() and f.page_number == 17 and "13.2" in f.raw_value
    ]

    assert len(facts_ar) >= 1
    assert len(facts_q4) >= 1

    rel = compare_facts(facts_ar[0], facts_q4[0])
    assert rel.state == CORROBORATED
    assert "13.19" in str(facts_ar[0].normalized_value)
    assert "13.2" in str(facts_q4[0].raw_value)
