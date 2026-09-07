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

The Phase 1 ingestion layer provides the stable foundation for later extraction work. It preserves page-level provenance and exposes empty-page information without introducing PDF-library coupling into downstream stages.

## Phase 2 Fact Extraction

```text
Document
  ↓
Page text
  ↓
Deterministic fact extraction
  ↓
Fact[]
  ↓
Evidence + provenance + normalized value
```

Phase 2 adds a lightweight fact model built from the Phase 1 document representation. The extractor is intentionally deterministic and explainable rather than model-driven. It recognizes general business facts such as currencies, percentages, dates, and quantities when they appear in sentence-level text.

## Fact model

Each fact retains both the original representation and any internal normalized value. For example, a document sentence such as "Revenue increased to $12.4 million" should produce a fact that keeps `raw_value = "$12.4 million"` and `normalized_value = 12400000.0` while still storing the page number and evidence sentence.

## Provenance strategy

Every extracted fact keeps:

- document identifier and source name
- page number
- evidence text
- raw extracted value
- optional normalized value
- confidence and status metadata

This ensures later validation and comparison stages can trace back to the PDF evidence rather than relying only on interpreted values.

## Supported extraction categories

The current deterministic baseline supports:

- currency values
- percentages
- dates and fiscal years
- quantities and associated units
- simple metric/value relationships inferred from nearby text

This is intentionally a general-purpose baseline rather than a document-specific extractor.

## Known limitations

The current fact extractor is intentionally narrow and transparent:

- it does not solve complex table extraction
- it does not attempt full semantic understanding of every sentence
- it may ignore values that lack surrounding context
- it does not yet perform entity resolution or relationship reasoning across the full document
- OCR is not introduced here because the current Phase 2 scope is general text extraction from the existing document representation

## Why we keep the model simple

The architecture separates ingestion, fact extraction, and later normalization/evidence validation. That keeps the package explainable and testable while preserving a clear path toward future phases such as fact normalization, entity matching, and relationships between facts.
