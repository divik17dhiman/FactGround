# Superjoin Fact Knowledge Layer

## Project

The Superjoin Fact Knowledge Layer is a Python-based project designed to process arbitrary financial and business PDFs, extract meaningful numerical and semantic facts, preserve source evidence, and make those facts comparable across documents.

The goal is not to memorize a few sample reports, but to build a reusable system that can generalize to unseen PDFs while keeping every published fact grounded in verifiable evidence from the source document.

## Problem

Given an arbitrary financial or business PDF, the system must identify meaningful facts, preserve their provenance, normalize them into a consistent representation, and allow comparison and explanation without silently inventing missing details.

This is a difficult challenge because real-world documents vary in structure, terminology, formatting, and quality. The architecture therefore needs to separate document parsing, fact detection, normalization, evidence grounding, validation, and structured output.

## Goals

- PDF ingestion for heterogeneous business and financial documents
- numerical fact extraction and validation
- semantic fact extraction from narrative and tabular content
- evidence grounding to source text and page-level provenance
- structured fact representation for comparison and explanation
- robustness to unseen PDFs rather than hardcoded sample behavior
- reproducible evaluation and auditability of extracted facts

## Current Status

This repository is in:

**Phase 6 — End-to-End Evaluator Workflow & Usability Integration**

Phase 6 integrates the entire pipeline into a clean, evaluator-facing end-to-end workflow:
- High-level public workflow: `build_knowledge_base(pdf_paths)` and `query(knowledge_base, question)`
- Single and multi-document knowledge base aggregation with preserved source document provenance
- Stable structured result representation (`QueryResult.to_dict()`, `.is_grounded`, `.top_fact`, and evidence list)
- Command-line interface (`superjoin` or `python -m superjoin_fact_knowledge`) supporting human-readable and `--json` structured output
- 58 passing tests covering unit parsing, integration workflows, multi-document querying, real PDF evaluation, and CLI execution

## Quick Start for Evaluators

### 1. Installation

From a fresh checkout of the repository:

```bash
# Create virtual environment
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install package with development tools
python -m pip install -e ".[dev]"
```

### 2. Evaluator Python Workflow

```python
from superjoin_fact_knowledge import build_knowledge_base, query

# 1. Build knowledge base from one or multiple PDFs
# Ingestion -> Fact Extraction -> Evidence Validation -> In-Memory Knowledge Base
kb = build_knowledge_base("report.pdf")
# Or multi-document:
# kb = build_knowledge_base(["report1.pdf", "report2.pdf"])

# 2. Query with natural language or keywords
result = query(kb, "operating margin in FY2024")

# 3. Inspect grounded answer
if result.is_grounded:
    print("Answer:", result.answer_text)
    print("Document:", result.top_fact.document_name)
    print("Page:", result.top_fact.page_number)
    print("Evidence:", result.top_fact.evidence_text)
else:
    print("Status:", result.status)  # 'ambiguous' or 'no_grounded_answer'

# 4. Access full structured serialization
structured_data = result.to_dict()
print(structured_data)
```

### 3. Command-Line Interface (CLI)

The package provides a built-in CLI via `superjoin` or `python -m superjoin_fact_knowledge`:

**Human-Readable Terminal Output:**
```bash
python -m superjoin_fact_knowledge report.pdf -q "revenue in FY2024"
```

**Structured JSON Output:**
```bash
python -m superjoin_fact_knowledge report.pdf -q "revenue in FY2024" --json
```

**Multi-Document Querying:**
```bash
python -m superjoin_fact_knowledge doc1.pdf doc2.pdf -q "total shipments"
```

### 4. Structured Output Contract

Query results return structured objects with `.to_dict()` serialization:

```json
{
  "query": "operating margin in FY2024",
  "status": "answer_found",
  "is_grounded": true,
  "answer": "Operating margin was 21.5%.",
  "explanation": "subject_phrase_match; year_match:2024; grounded_fact",
  "matches": [
    {
      "score": 18.5,
      "reasons": ["subject_phrase_match", "year_match:2024", "grounded_fact"],
      "fact": {
        "fact_id": "8f3a...",
        "subject": "Operating margin",
        "fact_type": "percentage",
        "raw_value": "21.5%",
        "normalized_value": 21.5,
        "unit": "percent",
        "metric": "percentage",
        "evidence": "Operating margin improved to 21.5% in FY2024.",
        "page": 3,
        "document": "report.pdf",
        "document_id": "e4b1...",
        "confidence": 1.0,
        "status": "grounded"
      }
    }
  ],
  "evidence": [
    {
      "document": "report.pdf",
      "page": 3,
      "text": "Operating margin improved to 21.5% in FY2024.",
      "raw_value": "21.5%",
      "normalized_value": 21.5,
      "unit": "percent"
    }
  ]
}
```

### 5. Modular Low-Level APIs

For granular pipeline access:

```python
from superjoin_fact_knowledge import extract_facts, ingest_pdf, validate_facts, KnowledgeBase

doc = ingest_pdf("report.pdf")
facts = extract_facts(doc)
validated_facts = validate_facts(facts, doc)
kb = KnowledgeBase.from_facts(validated_facts)
result = kb.query("revenue")
```

### 6. Cross-Fact Relationship Reasoning

Compare facts across documents to determine whether they corroborate, contradict, or contextually reconcile:

```python
from superjoin_fact_knowledge import compare_facts

# Compare two facts deterministically
rel = compare_facts(fact_1, fact_2)
print("Relationship State:", rel.state)
# Outputs: 'CORROBORATED', 'CONTRADICTED', 'CONTEXTUALLY_RECONCILED', 'INCOMPARABLE', or 'UNCERTAIN'
print("Explanation:", rel.explanation)
```

## Architecture

The current pipeline follows this flow:

```text
PDF file
  ↓
PyMuPDF adapter
  ↓
Document
  ↓
Page[]
  ↓
Deterministic fact extraction
  ↓
Structured Facts
  ↓
Evidence validation
  ↓
Grounded facts with provenance
```

The fact model keeps both the raw value as it appeared in the PDF and any normalized internal representation, while retaining the page number and evidence text needed for later validation and grounding. Validation does not replace the raw source representation; it only records whether the evidence is strong enough to treat the fact as grounded.

## Grounded Facts

A grounded fact answers four questions without losing source traceability:

- What value was extracted?
- How was it normalized?
- Which page did it come from?
- What source evidence supports it?

In this repository, a fact is considered grounded when the document exists, the page number is valid, the evidence text is present, the evidence contains the extracted value or an equivalent representation, and the normalized value is consistent with the raw source text.

Validated facts surface grounding state through `status` and validation diagnostics in metadata. Facts that fail validation are not discarded; they are marked for review instead.

The Phase 4 knowledge layer treats grounded facts as authoritative candidates and keeps `needs_review` facts out of default answer selection. Review facts remain queryable for inspection, but they are never silently promoted to grounded answers.

## Development

This project uses a lightweight Python toolchain with `pytest` for tests and `ruff` for formatting and linting.

### Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

### Lint the project

```bash
ruff check .
```

### Format the project

```bash
ruff format .
```

## Repository Structure

- `src/` — source package for the project implementation
- `tests/` — project smoke tests and future validation tests
- `docs/` — architecture and design documentation
- `.github/` — repository workflow and Copilot guidance
- `starter-datasets/` — assignment reference datasets that are treated as fixtures rather than templates
- `README.md` — project overview and local development workflow

## Notes

This repository is intentionally being structured as a production-quality foundation rather than a collection of ad hoc scripts. The objective is to create a clean engineering baseline suitable for future implementation work while preserving the assignment's requirement to remain generalizable across unseen PDFs.

## Scope and Limitations

- **Tables**: Table text is extracted via page text streams; multi-column cell-to-header relationships in complex borderless tables without layout cues are not parsed into structured grids.
- **Charts and Graphs**: Text elements (labels, legends, titles) are extracted from page text streams; graphical vector/raster curve interpretation is not parsed via computer vision.
- **Scanned / Image-Only PDFs**: Non-text pages are detected through diagnostics (`has_extractable_text=False`); OCR binary engines (e.g. Tesseract) are not bundled to ensure zero external system dependencies on fresh checkout.
- **Derived Calculations**: The system retrieves stated factual values directly; speculative arithmetic formulas or derived answers are not computed dynamically to avoid hallucination.
- **Semantic Facts**: Structured entities and qualifiers associated with values are extracted deterministically; open-ended qualitative narrative claims without metrics or dates are reserved for future LLM phases.
- **Sentence-Level Provenance**: Evidence grounding is established at sentence and page level; bounding-box span coordinates are preserved in metadata when provided by the ingestion layer.
