# Case 3 — Contextual Reconciliation Demonstration

## Purpose
Demonstrates that SuperJoin explains an apparent contradiction between two different values as **CONTEXTUALLY_RECONCILED** when the difference is accounted for by reporting period context (e.g. FY2023 vs FY2024).

## Input Documents
1. `annual_report_fy23.pdf` (Page 1):
   - Text: `"Global Logistics recorded total shipments of 740 million in FY2023."`
2. `annual_report_fy24.pdf` (Page 1):
   - Text: `"Global Logistics recorded total shipments of 820 million in FY2024."`

## Extracted Facts
- **Fact A**:
  - Subject: `Logistics total shipments`
  - Raw Value: `740`
  - Unit: `million`
  - Normalized Value: `740000000.0`
  - Period: `2023`
  - Document: `annual_report_fy23.pdf` (Page 1)
  - Status: `grounded`
- **Fact B**:
  - Subject: `Logistics total shipments`
  - Raw Value: `820`
  - Unit: `million`
  - Normalized Value: `820000000.0`
  - Period: `2024`
  - Document: `annual_report_fy24.pdf` (Page 1)
  - Status: `grounded`

## Evaluation Result
- **Relationship State**: `CONTEXTUALLY_RECONCILED`
- **Confidence**: `1.0`
- **Explanation**: `Values differ (740 vs 820) due to different reporting periods (2023 vs 2024).`

## How to Run
```bash
python examples/run_demonstrations.py
```
