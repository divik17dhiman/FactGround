"""Demonstration runners and fixtures for the four required evaluation cases:
1. Corroboration
2. Contradiction
3. Contextual Reconciliation
4. Extraction / Reasoning Failure

This module provides reproducible programmatic demonstrations and CLI execution.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pymupdf as fitz

from superjoin_fact_knowledge.ingestion import ingest_pdf
from superjoin_fact_knowledge.relationship import (
    CONTEXTUALLY_RECONCILED,
    CONTRADICTED,
    CORROBORATED,
    compare_facts,
)
from superjoin_fact_knowledge.workflow import build_knowledge_base, query


def create_demo_pdf(path: Path, text: str) -> Path:
    """Generate a clean single-page demonstration fixture PDF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


def create_scanned_image_pdf(path: Path) -> Path:
    """Generate a synthetic scanned image PDF with an embedded image and no extractable text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    # Create an in-memory pixmap (image) and insert it onto page without text
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 100), 1)
    pix.clear_with(240)  # light gray
    page.insert_image(fitz.Rect(72, 72, 272, 172), pixmap=pix)
    doc.save(str(path))
    doc.close()
    return path


def run_case_1_corroboration(base_dir: Path) -> dict[str, Any]:
    """Case 1: Corroboration between two separate documents."""
    dir_path = base_dir / "corroboration"
    doc_a_path = dir_path / "filing_doc_a.pdf"
    doc_b_path = dir_path / "press_release_doc_b.pdf"

    create_demo_pdf(
        doc_a_path,
        "Acme Logistics reported Express Parcel revenue of $650.0 million in FY2024.",
    )
    create_demo_pdf(
        doc_b_path,
        "Express Parcel revenue stood at $650.0 million in FY2024 across nationwide operations.",
    )

    kb_a = build_knowledge_base(str(doc_a_path))
    kb_b = build_knowledge_base(str(doc_b_path))

    fact_a = [f for f in kb_a.grounded_facts() if f.fact_type == "currency"][0]
    fact_b = [f for f in kb_b.grounded_facts() if f.fact_type == "currency"][0]

    rel = compare_facts(fact_a, fact_b)

    return {
        "case": "Case 1 — Corroboration",
        "fact_a": fact_a.to_dict(),
        "fact_b": fact_b.to_dict(),
        "relationship": rel.to_dict(),
        "passed": rel.state == CORROBORATED,
    }


def run_case_2_contradiction(base_dir: Path) -> dict[str, Any]:
    """Case 2: Contradiction between conflicting claims for the same period."""
    dir_path = base_dir / "contradiction"
    doc_a_path = dir_path / "official_filing.pdf"
    doc_b_path = dir_path / "analyst_estimate.pdf"

    create_demo_pdf(
        doc_a_path,
        "Acme Corp reported operating profit of $38.5 million in FY2024.",
    )
    create_demo_pdf(
        doc_b_path,
        "Acme Corp reported operating profit of $45.0 million in FY2024.",
    )

    kb_a = build_knowledge_base(str(doc_a_path))
    kb_b = build_knowledge_base(str(doc_b_path))

    fact_a = [f for f in kb_a.grounded_facts() if f.fact_type == "currency"][0]
    fact_b = [f for f in kb_b.grounded_facts() if f.fact_type == "currency"][0]

    rel = compare_facts(fact_a, fact_b)

    return {
        "case": "Case 2 — Contradiction",
        "fact_a": fact_a.to_dict(),
        "fact_b": fact_b.to_dict(),
        "relationship": rel.to_dict(),
        "passed": rel.state == CONTRADICTED,
    }


def run_case_3_contextual_reconciliation(base_dir: Path) -> dict[str, Any]:
    """Case 3: Apparent contradiction reconciled by reporting period context."""
    dir_path = base_dir / "contextual_reconciliation"
    doc_a_path = dir_path / "annual_report_fy23.pdf"
    doc_b_path = dir_path / "annual_report_fy24.pdf"

    create_demo_pdf(
        doc_a_path,
        "Global Logistics recorded total shipments of 740 million in FY2023.",
    )
    create_demo_pdf(
        doc_b_path,
        "Global Logistics recorded total shipments of 820 million in FY2024.",
    )

    kb_a = build_knowledge_base(str(doc_a_path))
    kb_b = build_knowledge_base(str(doc_b_path))

    fact_a = [f for f in kb_a.grounded_facts() if f.fact_type == "quantity"][0]
    fact_b = [f for f in kb_b.grounded_facts() if f.fact_type == "quantity"][0]

    rel = compare_facts(fact_a, fact_b)

    return {
        "case": "Case 3 — Contextual Reconciliation",
        "fact_a": fact_a.to_dict(),
        "fact_b": fact_b.to_dict(),
        "relationship": rel.to_dict(),
        "passed": rel.state == CONTEXTUALLY_RECONCILED,
    }


def run_case_4_extraction_failure(base_dir: Path) -> dict[str, Any]:
    """Case 4: Extraction failure on scanned/non-text PDF with conservative refusal."""
    dir_path = base_dir / "extraction_failure"
    scanned_path = dir_path / "scanned_receipt_image_only.pdf"

    create_scanned_image_pdf(scanned_path)

    doc = ingest_pdf(str(scanned_path))
    kb = build_knowledge_base(str(scanned_path))

    # Query attempting to find an answer in a non-text document
    result = query(kb, "invoice total amount")

    # Ingestion diagnostic flags that page has no extractable text
    has_text = doc.pages[0].has_extractable_text

    return {
        "case": "Case 4 — Extraction Failure & Conservative Refusal",
        "document_name": scanned_path.name,
        "has_extractable_text": has_text,
        "facts_extracted": len(kb.facts),
        "query": "invoice total amount",
        "query_status": result.status,
        "is_grounded": result.is_grounded,
        "answer": result.answer_text,
        "passed": (not has_text) and (len(kb.facts) == 0) and (not result.is_grounded),
    }


def run_all_demonstrations(base_dir: Path | None = None) -> list[dict[str, Any]]:
    """Run all four demonstrations and return results."""
    if base_dir is None:
        base_dir = Path(__file__).parent

    return [
        run_case_1_corroboration(base_dir),
        run_case_2_contradiction(base_dir),
        run_case_3_contextual_reconciliation(base_dir),
        run_case_4_extraction_failure(base_dir),
    ]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    results = run_all_demonstrations()
    print("=" * 68)
    print("SUPERJOIN EVALUATION DEMONSTRATIONS - 4 REQUIRED CASES")
    print("=" * 68)
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        print(f"\n[{status_str}] {r['case']}")
        if "relationship" in r:
            rel = r["relationship"]
            print(f"       State:       {rel['state']}")
            print(f"       Explanation: {rel['explanation']}")
            fa = rel["fact_a"]
            fb = rel["fact_b"]
            print(
                f"       Fact A:      {fa['subject']} -> {fa['raw_value']} "
                f"(Doc: {fa['document']}, Page {fa['page']})"
            )
            print(
                f"       Fact B:      {fb['subject']} -> {fb['raw_value']} "
                f"(Doc: {fb['document']}, Page {fb['page']})"
            )
        else:
            print(f"       Doc Text:    Extractable Text = {r['has_extractable_text']}")
            print(f"       Facts Found: {r['facts_extracted']}")
            print(
                f"       Query Refusal: Status = '{r['query_status']}', "
                f"Grounded = {r['is_grounded']}, Answer = {r['answer']}"
            )
    print("\n" + "=" * 68)
