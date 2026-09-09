# FactGround

> **FactGround**<br>
> *An evidence-grounded fact knowledge layer for extracting, validating, querying, and reasoning over structured facts from documents.*

---

## Video Demo Link

> **Video Demo:** https://youtu.be/W6qP0wAaIpU

---

## Project Overview

**FactGround** is an evidence-grounded fact knowledge layer designed to ingest arbitrary financial and business PDFs, extract structured numerical and semantic facts, validate them strictly against source page evidence, query them deterministically without hallucination, and classify cross-fact relationships across documents.

Importantly, FactGround is **not** a chatbot, conversational wrapper, or generic RAG application. It treats facts as first-class, verifiable entities grounded to source provenance and reasons over them through an explicit pipeline:

$$\text{PDF} \longrightarrow \text{Facts} \longrightarrow \text{Validation} \longrightarrow \text{Provenance} \longrightarrow \text{Knowledge} \longrightarrow \text{Reasoning}$$

The core design philosophy is **evidence-first and deterministic**:
- Every published answer is grounded in verbatim page text and provenance metadata (document ID, page number).
- Ambiguous queries or ungrounded claims result in explicit refusal rather than generative invention.
- Cross-fact comparison deterministically categorizes relationships into **CORROBORATED**, **CONTRADICTED**, **CONTEXTUALLY_RECONCILED**, **UNCERTAIN**, and **INCOMPARABLE**.
- Fully operational on fresh checkouts with standard Python and PyMuPDF (no proprietary LLM APIs, vector databases, or complex external dependencies required).

---

## Setup and Run Instructions

### Prerequisites
- Python 3.11, 3.12, 3.13, or 3.14
- Virtual environment tool (`venv`)

### Installation

From a fresh checkout of the repository:

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Upgrade pip and install package with development & API dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

---

### Running the Evaluator HTTP API

The application exposes a complete REST API powered by FastAPI for uploading PDFs, inspecting facts, querying evidence, and evaluating cross-document relationships.

#### 1. Start the API Server

```bash
# Using uvicorn directly:
uvicorn factground.api:app --host 127.0.0.1 --port 8000 --reload

# Or via Python module:
python -m uvicorn factground.api:app --port 8000
```

Once running, interactive **Swagger / OpenAPI documentation** is available at:
`http://localhost:8000/docs`

#### 2. Upload and Ingest PDFs (`POST /documents`)

Upload one or more PDF files to ingest, extract, and ground facts:

```bash
# Upload a single document:
curl -X POST "http://localhost:8000/documents" \
  -F "files=@report.pdf"

# Upload multiple documents simultaneously:
curl -X POST "http://localhost:8000/documents" \
  -F "files=@annual_report_2024.pdf" \
  -F "files=@annual_report_2025.pdf"
```

*Response (201 Created):*
```json
{
  "message": "Successfully processed 2 document(s).",
  "documents": [
    {
      "document_name": "annual_report_2024.pdf",
      "facts_extracted": 42,
      "grounded_facts": 42,
      "review_facts": 0
    },
    {
      "document_name": "annual_report_2025.pdf",
      "facts_extracted": 38,
      "grounded_facts": 38,
      "review_facts": 0
    }
  ],
  "total_facts_in_kb": 80,
  "grounded_facts_in_kb": 80
}
```

#### 3. Query Grounded Facts (`POST /query`)

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "revenue in FY2024", "limit": 5}'
```

*Response:*
```json
{
  "query": "revenue in FY2024",
  "status": "answer_found",
  "is_grounded": true,
  "answer": "Example Company revenue was $10.5 million.",
  "explanation": "subject_token_overlap:revenue; year_match:2024; grounded_fact",
  "matches": [...],
  "evidence": [
    {
      "document": "report.pdf",
      "page": 1,
      "text": "Example Company reported revenue of $10.5 million in FY2024.",
      "raw_value": "$10.5 million",
      "normalized_value": 10500000.0,
      "unit": "currency"
    }
  ]
}
```

#### 4. Inspect Facts (`GET /facts`)

```bash
# Retrieve all facts (with pagination)
curl "http://localhost:8000/facts?limit=10&offset=0"

# Filter by status or fact type
curl "http://localhost:8000/facts?status=grounded&fact_type=currency"
```

#### 5. Inspect Cross-Fact Relationships (`GET /relationships`)

```bash
# Evaluate pairwise relationships in the KnowledgeBase
curl "http://localhost:8000/relationships?limit=20"

# Compare two specific facts by ID:
curl "http://localhost:8000/relationships?fact_a_id=<ID_A>&fact_b_id=<ID_B>"

# Or via POST:
curl -X POST "http://localhost:8000/relationships/compare" \
  -H "Content-Type: application/json" \
  -d '{"fact_a_id": "<ID_A>", "fact_b_id": "<ID_B>"}'
```

---

### Running the Command-Line Interface (CLI)

The package provides a fast CLI via `factground` or `python -m factground`:

**Human-Readable Terminal Output:**
```bash
python -m factground report.pdf -q "revenue in FY2024"
```

**Structured JSON Output:**
```bash
python -m factground report.pdf -q "revenue in FY2024" --json
```

**Multi-Document Querying:**
```bash
python -m factground doc1.pdf doc2.pdf -q "operating margin"
```

---

### Python Library Usage

```python
from factground import build_knowledge_base, query, compare_facts

# 1. Build knowledge base from single or multiple PDFs
kb = build_knowledge_base(["filing_2023.pdf", "filing_2024.pdf"])

# 2. Query knowledge base
result = query(kb, "operating profit in FY2024")

if result.is_grounded:
    print(f"Answer: {result.answer_text}")
    print(f"Document: {result.top_fact.document_name}, Page: {result.top_fact.page_number}")
    print(f"Evidence: {result.top_fact.evidence_text}")
else:
    print(f"Refusal status: {result.status}")

# 3. Compare facts across documents
facts = kb.grounded_facts()
if len(facts) >= 2:
    relationship = compare_facts(facts[0], facts[1])
    print("Relationship:", relationship.state)
    print("Explanation:", relationship.explanation)
```

---

## Required Evaluation Cases

The assignment specification explicitly mandates demonstration of four core evaluation cases. These are fully implemented and verified via automated test fixtures:

| Case | Category | Input Documents | Evaluated State | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Case 1** | **Corroboration** | `filing_doc_a.pdf`, `press_release_doc_b.pdf` | `CORROBORATED` | **PASS** |
| **Case 2** | **Contradiction** | `disclosure_doc_a.pdf`, `disclosure_doc_b.pdf` | `CONTRADICTED` | **PASS** |
| **Case 3** | **Contextual Reconciliation** | `annual_report_fy23.pdf`, `annual_report_fy24.pdf` | `CONTEXTUALLY_RECONCILED` | **PASS** |
| **Case 4** | **Extraction Failure & Refusal** | `scanned_receipt_image_only.pdf` | `no_grounded_answer` | **PASS** |

### Running the Demonstrations

To execute all four cases interactively and view the detailed evaluation breakdown:

```bash
python examples/run_demonstrations.py
```

To run the automated pytest verification suite covering all four cases:

```bash
pytest tests/test_evaluation_demonstrations.py -v
```

For complete analysis and source evidence records for each case, see:
- [docs/evaluation-cases.md](docs/evaluation-cases.md)
- [examples/README.md](examples/README.md)
- [examples/corroboration/](examples/corroboration/)
- [examples/contradiction/](examples/contradiction/)
- [examples/contextual_reconciliation/](examples/contextual_reconciliation/)
- [examples/extraction_failure/](examples/extraction_failure/)

---

## Approach & Architectural Design

The pipeline follows a clean, modular architectural progression where each stage has a distinct, independently testable responsibility:

```text
PDF File(s)
    ↓
[Ingestion Layer] (PyMuPDF adapter)
    ↓
Document & Page[] Representation (provenance + page diagnostics)
    ↓
[Fact Extraction Layer] (Deterministic regexes: currency, %, quantities, dates, scales)
    ↓
Candidate Facts
    ↓
[Validation & Grounding Layer] (Source text presence, raw presence, normalization checks)
    ↓
Grounded Facts (with Document ID, Document Name, Page Number, Evidence Snippet)
    ↓
[KnowledgeBase] (In-memory aggregation, multi-document support)
    ↓
[Deterministic Query Engine] (Token scoring, subject matching, unit/period alignment)
    ↓
QueryResult (Answer, Grounding Invariant, Matches, Evidence Provenance)
    ↓
[Relationship Reasoning Engine] (compare_facts: CORROBORATED, CONTRADICTED, RECONCILED)
    ↓
Evaluator Interfaces (REST API, CLI, Python Library)
```

### Why the System Does Not Require an LLM
The assignment allows any framework, library, or model, but explicitly emphasizes deterministic engineering and hallucination prevention. The current architecture deliberately avoids speculative LLM integration because:
1. **Verifiability:** Deterministic regexes, normalization routines, and mathematical tolerance checks produce 100% explainable results with exact line/page references.
2. **Zero Hallucination:** If evidence is missing, ambiguous, or ungrounded, the system guarantees an explicit refusal (`no_grounded_answer` or `ambiguous`), whereas generative models risk inventing plausible numbers.
3. **Reproducibility & Zero Cost:** Evaluators can run the entire test suite and API locally without API keys, token budgets, network dependencies, or nondeterministic temperature drift.

### Core Invariant: Grounded Query Results
An answer is only presented as grounded if it satisfies:
```python
result.is_grounded == (
    result.status == "answer_found"
    and result.top_fact is not None
    and result.top_fact.status == "grounded"
)
```
Facts marked as `needs_review` are quarantined and can never be promoted to an authoritative answer.

---

## Limitations and Next Steps

1. **Scanned & Image-Only PDFs**:
   - *Current Behavior*: Non-text pages are detected via `Page.has_extractable_text == False` and yield zero facts. Queries safely refuse with `no_grounded_answer`.
   - *Next Step*: Add an optional OCR plugin (e.g. Tesseract) behind the ingestion interface for image-only pages.
2. **Complex Table Grid Reconstruction**:
   - *Current Behavior*: Tables are parsed via PyMuPDF text streams. Cell token order is preserved, but borderless tables lacking text spacing rely on nearby sentence context.
   - *Next Step*: Integrate a layout-aware table parser (e.g. `pdfplumber` or `camelot`) to construct explicit row-column coordinate matrices.
3. **Unanchored Qualitative Narrative**:
   - *Current Behavior*: Facts are extracted when anchored to quantitative metrics, currencies, percentages, or dates. Pure qualitative narrative statements ("company maintained strong market reputation") are omitted.
   - *Next Step*: Introduce a targeted semantic NLP extractor for non-numeric corporate claims.
4. **State Persistence**:
   - *Current Behavior*: The HTTP API maintains an in-memory `KnowledgeBase` instance during the server process lifecycle.
   - *Next Step*: Add an optional SQLite persistence backend for saving and loading knowledge bases across server restarts.

---

## Additional Evaluator Notes

- **Starter Dataset Independence**: The implementation contains zero hardcoded company names, numbers, or starter filenames. It executes identically on arbitrary unseen business reports.
- **Cross-Document Provenance**: Multi-document ingestion (`build_knowledge_base([pdf1, pdf2])`) preserves the distinct originating document name and SHA-256 identifier for every fact.
- **Robust Test Coverage**: The project includes 105 unit, integration, CLI, API, real starter document, and evaluation demonstration tests.

```bash
# Run the complete test suite:
pytest -v

# Run lint and format checks:
ruff check .
ruff format --check .
```
