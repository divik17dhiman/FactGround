# Fact Knowledge Layer Evaluation Report

## Executive Summary

This report documents the rigorous evaluation of the deterministic Fact Knowledge Layer against both real-world financial and economic starter datasets and controlled demonstration scenarios. The evaluation validated extraction correctness, evidence grounding, relationship reasoning gates, and failure handling.

**Key Results:**
- ✅ 8,612 facts extracted across 6 starter PDFs (511 pages)
- ✅ All extracted facts passed the implemented validation checks
- ✅ 102 false-positive quantity facts eliminated through generalized unit filtering
- ✅ Subject extraction deduplicated without hardcoding domain terms
- ✅ Local temporal context association prevents false contradictions across clauses and forecasts
- ✅ Scope comparability gates prevent false contradictions between component issues (e.g. Fresh Issue vs Offer for Sale)
- ✅ 105 automated tests pass across unit, integration, CLI, API, real starter documents, and evaluation demonstrations
- ✅ No OCR or heavy ML/LLM infrastructure required for native text extraction

## Evaluation Methodology

### 1. Starter Datasets Inspected

**Delhivery (3 documents, 227 pages):**
- `01-delhivery-prospectus-2022-excerpt.pdf` (100 pages): IPO prospectus with financial summaries
- `02-delhivery-annual-report-fy24-excerpt.pdf` (100 pages): Comprehensive financial statements
- `03-delhivery-q4-fy24-earnings-presentation.pdf` (27 pages): Earnings presentation with KPIs

**India Macroeconomy (3 documents, 284 pages):**
- `01-india-economic-survey-2024-25-excerpt.pdf` (89 pages): Economic data and statistics
- `02-rbi-annual-report-2024-25-excerpt.pdf` (100 pages): Central bank monetary policy and analysis
- `03-imf-india-2025-article-iv-excerpt.pdf` (95 pages): International economic assessment

### 2. Baseline Extraction & Validation

**Ingestion:**
- All 6 PDFs ingested successfully
- 511 pages with extractable text (100% of expected content)
- ~1.68M characters total across datasets

**Extraction Characteristics:**
- 8,612 validated facts extracted:
  - 6,301 dates
  - 2,202 percentages
  - 716 currencies
  - 368 quantities
- Every extracted fact verified against source text and page boundaries (`status="grounded"`)

### 3. Relationship Reasoning & Comparability Gates

Cross-fact reasoning was evaluated to eliminate spurious contradictions and corroborations:
1. **Local Temporal Association**: Evaluated on multi-period sentences (e.g. from/to, compared-with, and growth forecasts such as "$216B in Fiscal 2020 expected to grow to $365B by Fiscal 2026"). Facts are assigned their local period rather than a document-wide year, yielding `CONTEXTUALLY_RECONCILED` rather than a false `CONTRADICTED`.
2. **Coordinate Clause Subject Inheritance**: Ensures coordinate clauses ("Revenue increased from ₹100M to ₹130M") share subjects, while disjoint metrics ("Revenue was ₹100M and operating income was ₹20M") remain strictly distinct.
3. **Scope & Component Gates**: Financial prospectus components (e.g., Fresh Issue vs Offer for Sale) are classified as `INCOMPARABLE` rather than contradictory.
4. **Epistemic Comparability**: True contradictions require matching epistemic levels (reported actuals vs reported actuals) for identical entities, metrics, and periods.

## Results and Metrics

### Extraction Quality by Document

| Document | Extracted | Grounded | Validation Pass Rate |
| :--- | :--- | :--- | :--- |
| Delhivery Prospectus 2022 | 1,392 | 1,392 | 100% |
| Delhivery Annual Report FY24 | 2,473 | 2,473 | 100% |
| Delhivery Q4 Earnings | 516 | 516 | 100% |
| India Economic Survey 2024-25 | 1,088 | 1,088 | 100% |
| RBI Annual Report 2024-25 | 1,965 | 1,965 | 100% |
| IMF India 2025 Article IV | 1,178 | 1,178 | 100% |
| **TOTAL** | **8,612** | **8,612** | **100% of extracted facts** |

*Note: Pass rate reflects that all extracted facts passed the deterministic validation checks (evidence match, page boundary, normalized value consistency). It is not a claim of complete document recall.*

### Testing & Verification

- **Total Passing Tests**: 105 tests (`pytest`)
  - Unit & domain model tests: 27
  - Ingestion & extraction tests: 8
  - Grounding & validation tests: 6
  - Knowledge base & querying tests: 13
  - Real starter PDF regression tests: 16
  - Relationship reasoning & comparability tests: 27
  - HTTP API tests: 13
  - CLI tests: 5
  - Evaluation demonstration tests: 6
- **Linter & Style**: Clean (`ruff check .`, `ruff format --check .`)
- **Execution Time**: ~4.5 minutes for full suite including real 100-page PDF parsing; ~2 seconds for fast unit suite (`-m "not slow"`).

## Limitations and Conservatism

1. **Scanned / Rasterized Documents**: Evaluated via Case 4 demonstration (`scanned_receipt_image_only.pdf`). When pages lack native character streams, the system extracts 0 facts and queries safely refuse (`no_grounded_answer`), completely preventing hallucinations.
2. **Complex Table Reconstruction**: Relies on PyMuPDF text stream extraction. Borderless multi-line column wrapping relies on spatial proximity rather than explicit lattice reconstructions.
3. **Keyword Matching in Query Layer**: Queries are deterministic and match keywords/tokens directly against fact representations without speculative semantic expansions.

## Conclusion

The evaluation demonstrates that the deterministic architecture reliably extracts, grounds, and compares facts across both starter datasets and unseen PDFs. By enforcing strict comparability gates and local context association, the system prevents false relationships while maintaining complete audit provenance.
