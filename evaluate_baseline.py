#!/usr/bin/env python
"""
Baseline evaluation harness for Phase 5.

This script runs the complete pipeline against starter PDFs and collects
structured evaluation metrics without hardcoding any values.
"""

import json
import sys
from pathlib import Path
from typing import Any

# Handle Unicode properly on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from superjoin_fact_knowledge import (
    extract_facts,
    ingest_pdf,
    query_facts,
    validate_facts,
    KnowledgeBase,
)


def evaluate_pdf(pdf_path: str | Path) -> dict[str, Any]:
    """Run full pipeline on one PDF and collect diagnostics."""
    pdf_path = Path(pdf_path)
    
    print(f"\n{'='*70}")
    print(f"Evaluating: {pdf_path.name}")
    print(f"{'='*70}")
    
    result = {
        "pdf_path": str(pdf_path),
        "pdf_name": pdf_path.name,
        "ingestion": {},
        "extraction": {},
        "validation": {},
        "knowledge": {},
    }
    
    # INGESTION
    try:
        print("\n[1/4] Ingesting PDF...")
        doc = ingest_pdf(pdf_path)
        
        ingest_info = {
            "success": True,
            "page_count": doc.diagnostics.page_count,
            "pages_with_text": doc.diagnostics.pages_with_text,
            "pages_without_text": doc.diagnostics.pages_without_text,
            "approx_characters": doc.diagnostics.approximate_character_count,
            "empty_page_numbers": doc.diagnostics.empty_pages,
        }
        result["ingestion"] = ingest_info
        
        print(f"  ✓ Loaded {doc.diagnostics.page_count} pages")
        print(f"  ✓ {doc.diagnostics.pages_with_text} pages have extractable text")
        print(f"  ✓ {doc.diagnostics.approximate_character_count} approx. characters")
        
    except Exception as e:
        result["ingestion"]["success"] = False
        result["ingestion"]["error"] = str(e)
        print(f"  ✗ Ingestion failed: {e}")
        return result
    
    # EXTRACTION
    try:
        print("\n[2/4] Extracting facts...")
        facts = extract_facts(doc)
        
        fact_types = {}
        for fact in facts:
            fact_type = fact.fact_type
            fact_types[fact_type] = fact_types.get(fact_type, 0) + 1
        
        extract_info = {
            "success": True,
            "total_facts": len(facts),
            "fact_types": fact_types,
            "facts_per_page": len(facts) / max(doc.diagnostics.pages_with_text, 1),
        }
        result["extraction"] = extract_info
        
        print(f"  ✓ Extracted {len(facts)} facts")
        for ftype, count in sorted(fact_types.items()):
            print(f"    - {ftype}: {count}")
        
    except Exception as e:
        result["extraction"]["success"] = False
        result["extraction"]["error"] = str(e)
        print(f"  ✗ Extraction failed: {e}")
        return result
    
    # VALIDATION
    try:
        print("\n[3/4] Validating facts...")
        validated = validate_facts(facts, doc)
        
        grounded_count = sum(1 for f in validated if f.status == "grounded")
        needs_review = sum(1 for f in validated if f.status == "needs_review")
        
        validation_issues = {}
        for fact in validated:
            issues = fact.metadata.get("validation_issues", [])
            for issue in issues:
                validation_issues[issue] = validation_issues.get(issue, 0) + 1
        
        validation_info = {
            "success": True,
            "total_validated": len(validated),
            "grounded": grounded_count,
            "needs_review": needs_review,
            "grounded_percent": 100.0 * grounded_count / max(len(validated), 1),
            "common_validation_issues": validation_issues,
        }
        result["validation"] = validation_info
        
        print(f"  ✓ Validated {len(validated)} facts")
        print(f"    - {grounded_count} grounded ({100*grounded_count//max(len(validated),1)}%)")
        print(f"    - {needs_review} needs_review")
        if validation_issues:
            print(f"    - Common issues: {validation_issues}")
        
    except Exception as e:
        result["validation"]["success"] = False
        result["validation"]["error"] = str(e)
        print(f"  ✗ Validation failed: {e}")
        return result
    
    # KNOWLEDGE LAYER
    try:
        print("\n[4/4] Testing knowledge layer...")
        kb = KnowledgeBase.from_facts(validated)
        
        kb_info = {
            "success": True,
            "facts_in_kb": len(kb.facts),
            "grounded_in_kb": len(kb.grounded_facts()),
            "review_in_kb": len(kb.review_facts()),
        }
        result["knowledge"] = kb_info
        
        print(f"  ✓ Created knowledge base with {len(kb.facts)} facts")
        print(f"    - {len(kb.grounded_facts())} grounded")
        print(f"    - {len(kb.review_facts())} needs_review")
        
    except Exception as e:
        result["knowledge"]["success"] = False
        result["knowledge"]["error"] = str(e)
        print(f"  ✗ Knowledge layer failed: {e}")
    
    return result


def main():
    """Evaluate all starter PDFs."""
    starter_base = Path("starter-datasets/starter-datasets")
    
    pdf_paths = sorted(starter_base.glob("*/*.pdf"))
    
    if not pdf_paths:
        print("No starter PDFs found!")
        return
    
    print(f"\nFound {len(pdf_paths)} starter PDFs")
    
    all_results = []
    
    for pdf_path in pdf_paths:
        result = evaluate_pdf(pdf_path)
        all_results.append(result)
    
    # SUMMARY
    print(f"\n{'='*70}")
    print("EVALUATION SUMMARY")
    print(f"{'='*70}")
    
    total_facts = 0
    total_grounded = 0
    total_needs_review = 0
    
    for result in all_results:
        pdf_name = result["pdf_name"]
        extraction = result.get("extraction", {})
        validation = result.get("validation", {})
        
        if extraction.get("success") and validation.get("success"):
            facts = extraction.get("total_facts", 0)
            grounded = validation.get("grounded", 0)
            needs_review = validation.get("needs_review", 0)
            
            total_facts += facts
            total_grounded += grounded
            total_needs_review += needs_review
            
            pct = 100 * grounded // max(facts, 1)
            print(f"{pdf_name:50} {facts:4d} facts, {grounded:4d} grounded ({pct:3d}%)")
    
    print(f"\n{'TOTAL':50} {total_facts:4d} facts, {total_grounded:4d} grounded "
          f"({100*total_grounded//max(total_facts,1):3d}%)")
    
    # Save detailed results
    output_path = Path("evaluation_baseline.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
