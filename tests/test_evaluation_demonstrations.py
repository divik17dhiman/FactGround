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
from superjoin_fact_knowledge.relationship import (
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
    assert "operating profit" in res["fact_a"]["subject"].lower()
    assert "38.5 million" in res["fact_a"]["raw_value"]
    assert "45.0 million" in res["fact_b"]["raw_value"]
    assert "Contradicting values" in res["relationship"]["explanation"]
    assert res["fact_a"]["status"] == "grounded"
    assert res["fact_b"]["status"] == "grounded"


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
