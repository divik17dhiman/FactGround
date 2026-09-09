# FactGround Required Evaluation Cases

This directory contains reproducible demonstration fixtures, documentation, and a test runner for the four evaluation cases required by the assignment specification:

| Case | Category | Input Documents | Evaluated State | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Case 1** | **Corroboration** | `filing_doc_a.pdf`, `press_release_doc_b.pdf` | `CORROBORATED` | **PASS** |
| **Case 2** | **Contradiction** | `disclosure_doc_a.pdf`, `disclosure_doc_b.pdf` | `CONTRADICTED` | **PASS** |
| **Case 3** | **Contextual Reconciliation** | `annual_report_fy23.pdf`, `annual_report_fy24.pdf` | `CONTEXTUALLY_RECONCILED` | **PASS** |
| **Case 4** | **Extraction Failure & Refusal** | `scanned_receipt_image_only.pdf` | `no_grounded_answer` | **PASS** |

## Running Demonstrations

To execute all four demonstrations and view their detailed evaluation output:

```bash
python examples/run_demonstrations.py
```

To run the automated pytest assertions across all four cases:

```bash
pytest tests/test_evaluation_demonstrations.py -v
```
