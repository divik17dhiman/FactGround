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

## Planned Pipeline

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

This is a conceptual blueprint for future implementation rather than a completed system definition.
