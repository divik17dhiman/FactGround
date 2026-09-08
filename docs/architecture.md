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

## Phase 3 Evidence Validation

```text
Fact[]
  ↓
validate_fact / validate_facts
  ↓
Grounded fact or needs_review status
```

Phase 3 keeps the existing deterministic extractor and adds a small validation step that decides whether a fact is actually grounded in source evidence. Validation is intentionally lightweight: it checks that the document and page exist, that evidence text is present, that the evidence contains the extracted value or a recognizable equivalent, and that the normalized value is consistent with the raw representation.

## Fact model

Each fact retains both the original representation and any internal normalized value. For example, a document sentence such as "Revenue increased to $12.4 million" should produce a fact that keeps `raw_value = "$12.4 million"` and `normalized_value = 12400000.0` while still storing the page number and evidence sentence.

A fact becomes grounded when validation confirms the evidence path is internally consistent. The project expresses that outcome through the fact `status` field and validation diagnostics in metadata rather than by discarding the original fact object.

## Provenance strategy

Every extracted fact keeps:

- document identifier and source name
- page number
- evidence text
- raw extracted value
- optional normalized value
- confidence and status metadata

This ensures later validation and comparison stages can trace back to the PDF evidence rather than relying only on interpreted values.

The raw source representation is never replaced by normalization. If a value cannot be safely normalized, the implementation should preserve the raw value instead of guessing.

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
- table and layout structure are not modeled explicitly, so ambiguous tables may only be grounded to page text and nearby sentence context
- sentence-level evidence is the current practical boundary for grounding; later phases may add richer span, table, or layout-aware grounding

## Validation behavior

Validation is intentionally permissive and diagnostic rather than brittle.

- Missing evidence or an invalid page number marks a fact for review.
- A normalization mismatch marks a fact for review rather than throwing away the extraction.
- Empty pages and malformed page text are tolerated by the validation layer.
- Facts that are uncertain or weakly grounded remain available with their original raw source values intact.

## Phase 4 Knowledge Querying

```text
Grounded facts
  ↓
KnowledgeBase
  ↓
deterministic query scoring
  ↓
ranked fact candidates
  ↓
structured grounded result
```

Phase 4 introduces a small in-memory knowledge layer over validated facts. It stores facts without mutating them, preserves provenance, and ranks query candidates using transparent matching signals such as subject overlap, fact-type overlap, unit overlap, and year/date overlap.

The query layer is conservative by design:

- grounded facts are preferred over `needs_review` facts
- tied top candidates are returned as ambiguous rather than collapsed into one answer
- queries without a sufficiently relevant grounded fact return an explicit no-answer result
- the formatted answer, when present, is only a summary of the selected grounded fact and not a new inference

The query API remains library-independent and in-memory so a later semantic search or LLM layer can be added behind the same contract without replacing the deterministic baseline.

## Phase 6 End-to-End Workflow and Evaluator Contract

```text
PDF file(s)
  ↓
build_knowledge_base()
  [ingest_pdf → extract_facts → validate_facts]
  ↓
KnowledgeBase (multi-document, immutable)
  ↓
query() / kb.query()
  ↓
QueryResult (status, is_grounded, answer, evidence, to_dict())
  ↓
CLI (`python -m superjoin_fact_knowledge` or `superjoin`)
```

Phase 6 integrates the entire pipeline into a clean, minimal public interface:

1. **High-Level Workflow**: `build_knowledge_base(pdf_paths)` handles ingestion, fact extraction, and grounding validation across one or multiple PDFs, returning an aggregated, queryable `KnowledgeBase`.
2. **Multi-Document Support**: Facts retain `document_name` and `document_id` so cross-document provenance is always explicit.
3. **Structured Result Contract**: `QueryResult` provides `.is_grounded`, `.top_fact`, and `.to_dict()` methods, producing a JSON-serializable dictionary with answers, candidates, and full evidence provenance.
4. **Evaluator CLI**: A command-line interface (`superjoin` or `python -m superjoin_fact_knowledge`) allowing evaluators to query arbitrary PDFs from terminal with human-readable or `--json` structured output.

## Phase 7 Cross-Fact Relationship Reasoning

```text
Fact A  ──┐
          ├──> compare_facts() ──> FactRelationship (CORROBORATED, CONTRADICTED,
Fact B  ──┘                                          CONTEXTUALLY_RECONCILED,
                                                     INCOMPARABLE, UNCERTAIN)
```

Phase 7 implements the deterministic cross-fact comparison engine required by the hiring assignment specification:

1. **Grounding Validation**: Non-grounded or review facts result in `UNCERTAIN` state.
2. **Dimensional & Unit Compatibility**: Incompatible metrics or units (e.g. tonnes vs shipments) are classified as `INCOMPARABLE`.
3. **Entity Compatibility**: Unrelated subjects are classified as `INCOMPARABLE`.
4. **Value & Temporal Comparison**:
   - Matching values in matching periods $\rightarrow$ `CORROBORATED`
   - Conflicting values in matching periods $\rightarrow$ `CONTRADICTED`
   - Different values explained by different reporting periods $\rightarrow$ `CONTEXTUALLY_RECONCILED`
   - Differing values without confirmed period context $\rightarrow$ `UNCERTAIN`

## Why we keep the model simple

The architecture separates ingestion, fact extraction, evidence validation, knowledge querying, cross-fact relationship reasoning, and the evaluator interface. That keeps the package explainable and testable while preserving a clear path toward future extensions.
