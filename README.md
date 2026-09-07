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

Phase 1 — PDF Ingestion and Document Representation

The project now includes a lightweight PDF ingestion layer that loads source PDFs, preserves page-level provenance, and exposes a structured domain model for downstream fact extraction. This phase does not implement financial fact extraction or semantic reasoning; it focuses on robust ingestion and representation.

## Ingestion API

```python
from superjoin_fact_knowledge import ingest_pdf

document = ingest_pdf("report.pdf")
print(document.pages[0].page_number)
print(document.pages[0].text)
```

The public API returns a domain model rather than a raw PDF-library object, keeping the rest of the pipeline decoupled from the underlying PDF parser.

## Architecture

The ingestion pipeline follows this flow:

```text
PDF file
  ↓
PDF adapter (PyMuPDF)
  ↓
Document
  ↓
Page[]
  ↓
Page text + page provenance + diagnostics
```

The domain model preserves the original PDF page number separately from any internal indexing, ensuring later fact-extraction stages can cite evidence precisely.

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
