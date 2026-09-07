# Architecture Overview

## Purpose

The Superjoin Fact Knowledge Layer is intended to process previously unseen financial and business PDFs and convert them into a structured, evidence-grounded fact model that can be compared across documents.

## Core Principles

### Generalization

The system must operate on arbitrary PDFs rather than special-casing benchmark documents or starter files. The repository is designed around generic extraction and normalization logic, not fixed answers for a known dataset.

### Evidence-first extraction

Every fact should ultimately be traceable to source evidence. The architecture keeps raw text, page provenance, and source snippets alongside any normalized or interpreted representation.

### Provenance

Facts should retain the document identity, page number, and supporting text that justify the extraction. Where layout information is available, it should be retained as additional provenance metadata.

### Separation of concerns

The following responsibilities remain independently testable:

- PDF ingestion and document handling
- layout/text extraction
- fact detection and candidate extraction
- normalization and validation
- evidence grounding
- relationship reasoning and comparison
- structured output generation

### Deterministic where possible

When a task can be solved reliably with deterministic parsing or normalization, the architecture favors that approach over model-driven guessing. Model assistance is used when semantic interpretation genuinely requires it.

### Model-assisted where useful

LLMs or other semantic models may support interpretation and explanation, but the architecture is not built around hardcoded extractor behavior or answer templates.

### Evaluator reproducibility

A reviewer should be able to understand how the project is installed, how it is tested, how facts are represented, and how evidence is preserved. This document intentionally stays at the high-level architecture layer until the implementation phases formalize the actual processing components.

## Phase 1 Pipeline

```text
PDF file
  ↓
PDF adapter (PyMuPDF)
  ↓
Document
  ↓
Page[]
  ↓
Page text + provenance + diagnostics
```

This phase implements the document ingestion and representation layer. It does not yet perform financial fact extraction or semantic reasoning.

## Why page provenance is preserved

Every page in the domain model keeps its original PDF page number as a first-class field. Downstream fact extraction can cite evidence by page number without needing to rediscover the page in the PDF library. This is essential for auditability and evidence grounding.

## Separation from the PDF library

The project owns a small domain model (`Document` and `Page`) that is independent from PyMuPDF objects. The ingestion adapter translates raw PDF content into stable project types, so a future backend change would only require updating the adapter rather than rewriting extraction logic.

## Empty and textless pages

Pages are always represented in the document, even when no text can be extracted. For such pages, the `text` field is empty and `has_extractable_text` is set to `False`. Diagnostics expose the page as empty so future OCR or fallback extraction stages can decide whether additional work is needed.

## Exposure of diagnostics

The ingestion result exposes document-level information such as:

- total page count
- number of pages with extractable text
- number of empty pages
- list of empty page numbers
- approximate character count

This is intentionally lightweight but useful for deciding whether a PDF page is text-bearing, empty, or likely to require OCR later.

## Future phases

Phase 2 and beyond can consume this representation as the trusted source of truth for extraction work. The expected downstream flow is:

```text
Document representation
  ↓
Fact candidate extraction
  ↓
Evidence validation
  ↓
Normalization and comparison
  ↓
Structured fact knowledge layer
```

The core principle is that every downstream stage reads from the domain model and keeps source evidence attached to the page and text it came from.

## PDF library choice

PyMuPDF is used as the PDF extraction engine because it is mature, lightweight, widely adopted, and well-suited to extracting text from business and financial PDFs in a straightforward way. Its text extraction is adequate for this phase and keeps the architecture simple while preserving explicit provenance. The project intentionally does not add OCR or other heavy dependencies at this stage.
