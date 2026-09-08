# Case 1 — Corroboration Demonstration

## Purpose
Demonstrates that SuperJoin identifies two independent documents reporting the same underlying fact as **CORROBORATED**, even when phrased with different wording.

## Input Documents
1. `filing_doc_a.pdf` (Page 1):
   - Text: `"Acme Logistics reported Express Parcel revenue of $650.0 million in FY2024."`
2. `press_release_doc_b.pdf` (Page 1):
   - Text: `"Express Parcel revenue stood at $650.0 million in FY2024 across nationwide operations."`

## Extracted Facts
- **Fact A**:
  - Subject: `Express Parcel revenue`
  - Raw Value: `$650.0 million`
  - Normalized Value: `650000000.0`
  - Unit: `USD / currency`
  - Period: `2024`
  - Document: `filing_doc_a.pdf` (Page 1)
  - Status: `grounded`
- **Fact B**:
  - Subject: `Express Parcel revenue`
  - Raw Value: `$650.0 million`
  - Normalized Value: `650000000.0`
  - Unit: `USD / currency`
  - Period: `2024`
  - Document: `press_release_doc_b.pdf` (Page 1)
  - Status: `grounded`

## Evaluation Result
- **Relationship State**: `CORROBORATED`
- **Confidence**: `1.0`
- **Explanation**: `Facts corroborate with matching normalized value 650000000.0 in 2024.`

## How to Run
```bash
python examples/run_demonstrations.py
# Or inspect via CLI:
python -m superjoin_fact_knowledge examples/corroboration/filing_doc_a.pdf examples/corroboration/press_release_doc_b.pdf -q "Express Parcel revenue"
```
