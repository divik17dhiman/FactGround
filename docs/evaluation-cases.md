# Evaluator Verification Report: Four Required Evaluation Cases

This document provides independent quality-control verification for the four core assignment demonstration cases in the SuperJoin Fact Knowledge Layer.

Each case has been validated against source evidence, page provenance, and relationship reasoning invariants.

---

## Case 1: Corroboration

### Case Overview
Two independent documents report the same underlying financial metric for the same reporting period using different phrasing.

### Input Documents
- **Document A**: `filing_doc_a.pdf` (Page 1)
  - Text: `"Acme Logistics reported Express Parcel revenue of $650.0 million in FY2024."`
- **Document B**: `press_release_doc_b.pdf` (Page 1)
  - Text: `"Express Parcel revenue stood at $650.0 million in FY2024 across nationwide operations."`

### Source Evidence & Extracted Facts
- **Fact A**:
  - Entity / Subject: `Express Parcel revenue`
  - Raw Value: `$650.0 million`
  - Normalized Value: `650000000.0`
  - Metric / Unit: `currency (USD)`
  - Period: `2024`
  - Provenance: `filing_doc_a.pdf`, Page 1
  - Evidence Text: `"Acme Logistics reported Express Parcel revenue of $650.0 million in FY2024."`
  - Grounding Status: `grounded` (confirmed present on Page 1)
- **Fact B**:
  - Entity / Subject: `Express Parcel revenue`
  - Raw Value: `$650.0 million`
  - Normalized Value: `650000000.0`
  - Metric / Unit: `currency (USD)`
  - Period: `2024`
  - Provenance: `press_release_doc_b.pdf`, Page 1
  - Evidence Text: `"Express Parcel revenue stood at $650.0 million in FY2024 across nationwide operations."`
  - Grounding Status: `grounded` (confirmed present on Page 1)

### Observed Relationship Result
- **Relationship State**: `CORROBORATED`
- **Confidence**: `1.0`
- **Explanation**: `Facts corroborate with matching normalized value 650000000.0 in 2024.`
- **Real Starter Dataset Counterpart**:
  - Delhivery Annual Report FY24 (Page 36): Amortisation expense was `13.19%` of service revenue.
  - Delhivery Q4 FY24 Earnings Presentation (Page 17): Amortisation expense was `13.2%` of revenue.
  - State: `CORROBORATED` (matching normalized values within 0.1% rounding tolerance).

### Verification
- **Expected Behavior**: Two grounded facts with compatible subjects, identical reporting period (`2024`), and equal normalized monetary values must be classified as `CORROBORATED`.
- **Status**: **PASS**

---

## Case 2: Genuine or Likely Contradiction

### Case Overview
Two documents reporting on the same corporate entity and reporting period provide conflicting quantitative values for the same metric.

### Input Documents
- **Document A**: `official_filing.pdf` (Page 1)
  - Text: `"Acme Corp reported operating profit of $38.5 million in FY2024."`
- **Document B**: `analyst_estimate.pdf` (Page 1)
  - Text: `"Acme Corp reported operating profit of $45.0 million in FY2024."`

### Source Evidence & Extracted Facts
- **Fact A**:
  - Entity / Subject: `Corp operating profit`
  - Raw Value: `$38.5 million`
  - Normalized Value: `38500000.0`
  - Unit: `currency (USD)`
  - Period: `2024`
  - Provenance: `official_filing.pdf`, Page 1
  - Grounding Status: `grounded`
- **Fact B**:
  - Entity / Subject: `Corp operating profit`
  - Raw Value: `$45.0 million`
  - Normalized Value: `45000000.0`
  - Unit: `currency (USD)`
  - Period: `2024`
  - Provenance: `analyst_estimate.pdf`, Page 1
  - Grounding Status: `grounded`

### Observed Relationship Result
- **Relationship State**: `CONTRADICTED`
- **Confidence**: `1.0`
- **Explanation**: `Contradicting values ($38.5 million vs $45.0 million) reported for the same period (2024).`

### Verification
- **Expected Behavior**: Both facts share the same subject entity (`operating profit`) and same temporal window (`2024`), but report incompatible normalized numbers ($38.5M vs $45.0M). Must be classified as `CONTRADICTED` without guessing an artificial reconciliation.
- **Status**: **PASS**

---

## Case 3: Apparent Contradiction Reconciled by Context

### Case Overview
Two documents report differing numbers for the same metric, but the conflict is resolved because the facts pertain to distinct reporting periods (FY2023 vs FY2024).

### Input Documents
- **Document A**: `annual_report_fy23.pdf` (Page 1)
  - Text: `"Global Logistics recorded total shipments of 740 million in FY2023."`
- **Document B**: `annual_report_fy24.pdf` (Page 1)
  - Text: `"Global Logistics recorded total shipments of 820 million in FY2024."`

### Source Evidence & Extracted Facts
- **Fact A**:
  - Entity / Subject: `Logistics total shipments`
  - Raw Value: `740`
  - Unit: `million`
  - Normalized Value: `740000000.0`
  - Period: `2023`
  - Provenance: `annual_report_fy23.pdf`, Page 1
  - Grounding Status: `grounded`
- **Fact B**:
  - Entity / Subject: `Logistics total shipments`
  - Raw Value: `820`
  - Unit: `million`
  - Normalized Value: `820000000.0`
  - Period: `2024`
  - Provenance: `annual_report_fy24.pdf`, Page 1
  - Grounding Status: `grounded`

### Observed Relationship Result
- **Relationship State**: `CONTEXTUALLY_RECONCILED`
- **Confidence**: `1.0`
- **Explanation**: `Values differ (740 vs 820) due to different reporting periods (2023 vs 2024).`

### Verification
- **Expected Behavior**: Rather than reporting a false contradiction, the system must recognize that both facts describe the same operational metric across successive fiscal periods and explain the discrepancy via temporal context.
- **Status**: **PASS**

---

## Case 4: Extraction Failure & Conservative Refusal

### Case Overview
A scanned or image-only PDF containing no extractable character stream is supplied to the pipeline.

### Input Document
- **Document**: `scanned_receipt_image_only.pdf` (Page 1)
  - A rasterized image of an invoice rendered into a PDF container without OCR or text font objects.

### Observed System Behavior
1. **Ingestion Layer Diagnostics**:
   - `Page.has_extractable_text`: `False`
   - `PageDiagnostic.text_length`: `0`
   - Ingestion succeeds gracefully without unhandled exceptions.
2. **Fact Extraction Layer**:
   - Facts Extracted: `0`
   - KnowledgeBase Fact Count: `0`
3. **Query Refusal**:
   - Evaluator Query: `"invoice total amount"`
   - Query Status: `no_grounded_answer`
   - `QueryResult.is_grounded`: `False`
   - `QueryResult.answer_text`: `None`

### Limitation Analysis & Future Roadmap
- **Why this is a limitation**:
  - Ingestion relies on native text extraction streams via PyMuPDF. It does not bundle heavy OCR engines (e.g. Tesseract or cloud OCR APIs) to keep checkout and runtime dependencies lightweight and zero-dependency.
- **How SuperJoin handles it safely**:
  - The system detects the lack of extractable text, marks the diagnostic cleanly, extracts zero speculative facts, and refuses to hallucinate answers.
- **Future Improvement**:
  - Integrate an optional OCR plugin into `ingest_pdf()` for image-only pages when system OCR libraries are available.

### Verification
- **Expected Behavior**: Document with zero extractable text must yield zero grounded facts, and any query against it must explicitly refuse with `no_grounded_answer` and `is_grounded=False`.
- **Status**: **PASS**

---

## Grounding Invariant Verification

All answers exposed across the Python API, CLI, and HTTP API strictly adhere to the grounding invariant:

```python
result.is_grounded == (
    result.status == "answer_found"
    and result.top_fact is not None
    and result.top_fact.status == "grounded"
)
```

No fact marked as `needs_review` or ungrounded can become an authoritative answer.

---

## Summary of Verification Results

| Case | Expected State | Observed State | Grounding Preserved | Provenance Verified | Test Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Case 1 (Corroboration)** | `CORROBORATED` | `CORROBORATED` | Yes (`grounded`) | Document & Page 1 | **PASS** |
| **Case 2 (Contradiction)** | `CONTRADICTED` | `CONTRADICTED` | Yes (`grounded`) | Document & Page 1 | **PASS** |
| **Case 3 (Reconciliation)** | `CONTEXTUALLY_RECONCILED` | `CONTEXTUALLY_RECONCILED` | Yes (`grounded`) | Document & Page 1 | **PASS** |
| **Case 4 (Failure/Refusal)**| `no_grounded_answer` | `no_grounded_answer` | Yes (`is_grounded=False`) | Empty Diagnostics | **PASS** |
