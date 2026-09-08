# Case 4 — Extraction Failure & Conservative Refusal Demonstration

## Purpose
Demonstrates a genuine, honest limitation of the current deterministic pipeline and how SuperJoin conservatively refuses to hallucinate an unsupported answer.

## Input Document
`scanned_receipt_image_only.pdf` (Page 1):
- A scanned PDF document containing a raster image of a receipt with no extractable text stream.

## System Behavior & Limitation
1. **Ingestion Diagnostic**:
   - `Page.has_extractable_text` evaluates to `False`.
   - The ingestion layer detects that the page contains zero character streams.
2. **Fact Extraction**:
   - `0` facts extracted.
3. **Query Attempt**:
   - Query: `"invoice total amount"`
   - Result Status: `no_grounded_answer`
   - `is_grounded`: `False`
   - `answer`: `None`
4. **Why this is a limitation**:
   - The current baseline does not bundle external OCR engines (such as Tesseract) to keep the project lightweight and free of heavy C-binary system dependencies.
5. **How SuperJoin handles it safely**:
   - Rather than guessing or hallucinating an answer, SuperJoin flags that no extractable text exists and explicitly returns `no_grounded_answer`.
6. **Future improvement**:
   - An optional OCR adapter (e.g. `pytesseract` or an OCR vision API) can be hooked behind the existing ingestion interface without modifying downstream fact extraction or query logic.

## How to Run
```bash
python examples/run_demonstrations.py
```
