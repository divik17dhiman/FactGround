# Case 2 — Contradiction Demonstration

## Purpose
Demonstrates that SuperJoin identifies two conflicting factual claims of the **same epistemic status** (both asserting reported actuals for the same corporate entity, metric, fiscal period, and unit) as **CONTRADICTED**.

> **Disclosure:** *Synthetic fixture used solely to demonstrate the contradiction reasoning path; it is not presented as real-world evidence.*

## Input Documents
1. `disclosure_doc_a.pdf` (Page 1):
   - Text: `"Company Alpha reported operating profit of $38.5 million in FY2024."`
2. `disclosure_doc_b.pdf` (Page 1):
   - Text: `"Company Alpha reported operating profit of $45.0 million in FY2024."`

## Extracted Facts
- **Fact A**:
  - Entity / Subject: `Alpha operating profit`
  - Raw Value: `$38.5 million`
  - Normalized Value: `38500000.0`
  - Unit: `USD / currency`
  - Period: `2024`
  - Document: `disclosure_doc_a.pdf` (Page 1)
  - Status: `grounded`
  - Epistemic Status: Reported corporate actual
- **Fact B**:
  - Entity / Subject: `Alpha operating profit`
  - Raw Value: `$45.0 million`
  - Normalized Value: `45000000.0`
  - Unit: `USD / currency`
  - Period: `2024`
  - Document: `disclosure_doc_b.pdf` (Page 1)
  - Status: `grounded`
  - Epistemic Status: Reported corporate actual

## Evaluation Result
- **Relationship State**: `CONTRADICTED`
- **Confidence**: `1.0`
- **Explanation**: `Contradicting values ($38.5 million vs $45.0 million) reported for the same period (2024).`

## Epistemic Integrity
Both documents share identical entity scope, metric definition, reporting period, and epistemic tier (both assert historical reported results). Neither is an analyst forecast or consensus estimate. Because the two reported values ($38.5M vs $45.0M) cannot simultaneously hold true for the same scope, the system correctly and deterministically classifies them as mutually contradictory.

## How to Run
```bash
python examples/run_demonstrations.py
```
