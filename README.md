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

Phase 0 — Repository Foundation

No extraction pipeline, OCR layer, or document-specific fact logic has been implemented yet. The current focus is establishing a clean, professional project baseline that is ready for implementation work in Phase 1.

## Planned Architecture

The eventual system is expected to follow this high-level flow:

```text
PDF
  ↓
Document Ingestion
  ↓
Text / Layout Extraction
  ↓
Document Representation
  ↓
Fact Detection
  ↓
Fact Normalization
  ↓
Evidence Grounding
  ↓
Validation
  ↓
Structured Fact Knowledge Layer
```

This architecture is intentionally conceptual. It defines the major concerns without locking the repository into a premature implementation choice.

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
