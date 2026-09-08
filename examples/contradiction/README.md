# Case 2 — Contradiction Demonstration

## Purpose
Demonstrates that SuperJoin identifies two conflicting factual claims for the same entity and reporting period as **CONTRADICTED**.

## Input Documents
1. `official_filing.pdf` (Page 1):
   - Text: `"Acme Corp reported operating profit of $38.5 million in FY2024."`
2. `analyst_estimate.pdf` (Page 1):
   - Text: `"Acme Corp reported operating profit of $45.0 million in FY2024."`

## Extracted Facts
- **Fact A**:
  - Subject: `Corp operating profit`
  - Raw Value: `$38.5 million`
  - Normalized Value: `38500000.0`
  - Unit: `USD / currency`
  - Period: `2024`
  - Document: `official_filing.pdf` (Page 1)
  - Status: `grounded`
- **Fact B**:
  - Subject: `Corp operating profit`
  - Raw Value: `$45.0 million`
  - Normalized Value: `45000000.0`
  - Unit: `USD / currency`
  - Period: `2024`
  - Document: `analyst_estimate.pdf` (Page 1)
  - Status: `grounded`

## Evaluation Result
- **Relationship State**: `CONTRADICTED`
- **Confidence**: `1.0`
- **Explanation**: `Contradicting values ($38.5 million vs $45.0 million) reported for the same period (2024).`

## How to Run
```bash
python examples/run_demonstrations.py
```
