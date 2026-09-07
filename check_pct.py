#!/usr/bin/env python
"""Check for percentage outliers."""

import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from superjoin_fact_knowledge import extract_facts, ingest_pdf

pdf_path = r"starter-datasets\starter-datasets\delhivery\01-delhivery-prospectus-2022-excerpt.pdf"
doc = ingest_pdf(pdf_path)
facts = extract_facts(doc)

pct_facts = [f for f in facts if f.fact_type == "percentage"]
zero_pct = [f for f in pct_facts if f.normalized_value == 0]
huge_pct = [f for f in pct_facts if f.normalized_value and f.normalized_value > 100]

print(f"Total percentage facts: {len(pct_facts)}")
print(f"Zero percent values: {len(zero_pct)}")
print(f"Values > 100%: {len(huge_pct)}")

if huge_pct:
    print(f"\nExamples of >100%:")
    for fact in huge_pct[:3]:
        print(f"  - {fact.raw_value}: {fact.normalized_value}% ({fact.subject})")

if zero_pct:
    print(f"\nExamples of 0%:")
    for fact in zero_pct[:3]:
        print(f"  - {fact.raw_value}: {fact.normalized_value}% ({fact.subject})")
