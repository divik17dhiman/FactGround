#!/usr/bin/env python
"""
Detailed fact inspection for Phase 5 evaluation.

Inspect actual facts extracted to assess quality and identify patterns.
"""

import json
import sys
from collections import Counter
from pathlib import Path

# Handle Unicode properly on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from superjoin_fact_knowledge import extract_facts, ingest_pdf, validate_facts


def sample_facts(facts, count=20, sample_by_type=True):
    """Sample facts for inspection."""
    if sample_by_type:
        by_type = {}
        for fact in facts:
            if fact.fact_type not in by_type:
                by_type[fact.fact_type] = []
            by_type[fact.fact_type].append(fact)
        
        sampled = []
        per_type = max(1, count // len(by_type))
        for ftype, type_facts in by_type.items():
            sampled.extend(type_facts[:per_type])
        return sampled[:count]
    else:
        return facts[:count]


def analyze_pdf(pdf_path):
    """Analyze facts from one PDF."""
    pdf_path = Path(pdf_path)
    print(f"\n{'='*80}")
    print(f"Analyzing: {pdf_path.name}")
    print(f"{'='*80}")
    
    doc = ingest_pdf(pdf_path)
    facts = extract_facts(doc)
    validated = validate_facts(facts, doc)
    
    print(f"\nTotal facts: {len(facts)}")
    
    # Subject analysis
    subjects = Counter(f.subject for f in facts)
    print(f"\nMost common subjects (top 10):")
    for subject, count in subjects.most_common(10):
        print(f"  {count:4d}x: {subject[:60]}")
    
    # Sample facts for manual inspection
    print(f"\nSample facts ({min(15, len(facts))} from each type):")
    sampled = sample_facts(facts, count=15)
    
    for i, fact in enumerate(sampled, 1):
        print(f"\n  [{i}] {fact.fact_type.upper()}")
        print(f"      Subject: {fact.subject[:70]}")
        print(f"      Raw value: {fact.raw_value}")
        if fact.normalized_value is not None:
            print(f"      Normalized: {fact.normalized_value}")
        print(f"      Unit: {fact.unit}")
        print(f"      Page: {fact.page_number}")
        print(f"      Evidence: {fact.evidence_text[:80]}")
    
    # Check for obvious false positives
    print(f"\nChecking for common false positives:")
    
    # Page numbers incorrectly extracted as quantities
    page_number_facts = [
        f for f in facts 
        if f.fact_type == "quantity" and 
           f.unit and 
           f.unit.lower() in ("page", "pages")
    ]
    print(f"  - Page numbers extracted as quantities: {len(page_number_facts)}")
    
    # Years that are incorrectly extracted  
    wrong_year_facts = [
        f for f in facts 
        if f.fact_type == "date" and 
           "page" in f.evidence_text.lower()
    ]
    print(f"  - Years possibly from page headers: {len(wrong_year_facts)}")
    
    # Percentage checking
    zero_pct = [f for f in facts if f.fact_type == "percentage" and f.normalized_value == 0]
    huge_pct = [f for f in facts if f.fact_type == "percentage" and f.normalized_value and f.normalized_value > 100]
    print(f"  - 0% values: {len(zero_pct)}")
    print(f"  - Values > 100%: {len(huge_pct)}")
    
    # Currency checking
    currencies = Counter(f.metadata.get("currency_symbol", "unknown") for f in facts if f.fact_type == "currency")
    print(f"\nCurrency symbols found:")
    for symbol, count in currencies.most_common(10):
        print(f"  {count:4d}x: {symbol}")
    
    # Evidence text statistics
    avg_evidence_len = sum(len(f.evidence_text) for f in facts) / max(len(facts), 1)
    print(f"\nEvidence statistics:")
    print(f"  Average evidence length: {avg_evidence_len:.0f} chars")
    
    # Check validation details
    print(f"\nValidation summary:")
    validation_issues = Counter()
    for fact in validated:
        issues = fact.metadata.get("validation_issues", [])
        for issue in issues:
            validation_issues[issue] += 1
    
    if validation_issues:
        print(f"  Issues found:")
        for issue, count in validation_issues.most_common():
            print(f"    - {issue}: {count}")
    else:
        print(f"  All facts validated successfully")


def main():
    """Analyze all starter PDFs."""
    starter_base = Path("starter-datasets/starter-datasets")
    pdf_paths = sorted(starter_base.glob("*/*.pdf"))[:3]  # First 3 for detailed inspection
    
    for pdf_path in pdf_paths:
        analyze_pdf(pdf_path)


if __name__ == "__main__":
    main()
