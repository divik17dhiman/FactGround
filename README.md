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

This repository is currently in:

**Phase 5 — Evaluation and Improvement**

Phase 5 evaluated the Phase 4 pipeline against actual starter datasets (6 PDFs, 511 pages, 8,612 facts) and made targeted improvements to extraction quality. The system now handles diverse financial and economic documents with 100% validation success, improved subject extraction, and better unit filtering. All improvements are deterministic and generalize beyond the starter datasets.

See [docs/evaluation.md](docs/evaluation.md) for detailed evaluation methodology and results.

## Public APIs

```python
from superjoin_fact_knowledge import extract_facts, ingest_pdf, validate_facts

document = ingest_pdf("report.pdf")
facts = validate_facts(extract_facts(document), document)

for fact in facts:
    print(fact.fact_type, fact.raw_value, fact.page_number, fact.status)
```

The ingestion API returns a project-owned `Document` model rather than a raw PDF-library object. The fact extractor consumes that model and emits structured facts with page- and evidence-level provenance. Validation then checks whether each fact is actually grounded in the source document before treating it as fully trusted.

## Phase 4 Knowledge Layer and Phase 5 Improvements

Phase 4 adds a small in-memory knowledge layer over validated facts. It is deterministic, explainable, and intentionally independent of any database, vector index, or LLM.

Phase 5 improves the fact extraction layer through evaluation on real documents:
- Better subject extraction (removes repeated words like "Fiscal Fiscal")
- Unit filtering to eliminate document noise
- Real-document regression tests for quality assurance
- 100% validation success maintained across 8,612 facts from Delhivery and India macroeconomy datasets

Public usage looks like this:

```python
from superjoin_fact_knowledge import (
    KnowledgeBase,
    extract_facts,
    ingest_pdf,
    query_facts,
    validate_facts,
)

document = ingest_pdf("report.pdf")
validated_facts = validate_facts(extract_facts(document), document)
knowledge_base = KnowledgeBase.from_facts(validated_facts)
result = query_facts(knowledge_base, "revenue in 2025")
```

The knowledge layer returns grounded fact candidates in deterministic relevance order and preserves provenance on every result. It does not convert the facts into untraceable answer strings. Instead, callers receive the matching fact, its value, normalized value, page number, source document, evidence text, and grounding status.

Query behavior is intentionally conservative:

- grounded facts are preferred by default
- `needs_review` facts stay separate unless a caller explicitly asks to inspect them
- tied top candidates are reported as ambiguous rather than arbitrarily collapsed into one answer
- no sufficiently relevant fact produces an explicit no-answer result
- the answer formatter only summarizes a selected grounded fact and never invents unsupported details

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

## Limitations

- Table structure is not modeled explicitly, so ambiguous tables may only be grounded to page text and nearby sentence context.
- Sentence-level evidence is the current practical boundary for grounding; later phases may add richer span, table, or layout-aware grounding.
- The project does not attempt question answering, embeddings, vector search, or chat-style interfaces in this phase.
- Querying is still deterministic and pattern-based; it does not perform open-ended natural-language understanding.
