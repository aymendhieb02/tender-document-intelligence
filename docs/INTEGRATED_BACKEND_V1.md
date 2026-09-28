# Integrated Backend V1

## Current integration

`integration/backend-v1` combines the official Document Intelligence, CDC Analyzer, and specialized BOQ branches. Their common Git merge base is `b160eb6fa60ca1ad9aaa83462dc313c215837fef`. The integration retains the public Document Intelligence Contract `1.0`, `CDC_ANALYZER_BASELINE_V1`, and `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1`.

The current runnable backend boundary is the Python module API. The repository does not yet include `app/main.py`, `app/api/`, a FastAPI route layer, or the historical invoice workflow. No historical files have been copied. The historical checkout available during integration has broad uncommitted changes to its app shell, API routes, requirements, and frontend; copying from that working tree would mix unreviewed work into this branch. The immutable historical `HEAD` also uses an invoice OCR engine/API contract that must be reconciled with the DI-owned `app/services/ocr_engine.py` before the invoice workflow can be restored safely. Thus the application shell and invoice workflow remain explicit blockers for declaring Backend V1 complete or creating `main`.

## Ownership and data flow

```text
PDF or image
    │
    ▼
Document Intelligence Contract 1.0
    │  DocumentResult: document ID, 1-based physical pages,
    │  evidence IDs, rendered-page boxes, source and confidence
    ├──────────────► Invoice semantics (not present in this checkout)
    │
    ▼
CDC Analyzer V1
    │  TenderDocument, structure, evidence, diagnostics
    │  BOQ annex handoff points to the actual physical page range
    ▼
Specialized BOQ extractor
       MALE_MUNICIPAL_MAINTENANCE_BOQ_V1
       deterministic family detection, Decimal parsing,
       provenance and null financial values
```

Document Intelligence owns generic evidence and page truth. CDC owns tender sections, articles, annexes, and BOQ handoff classification; it does not read PDFs or run OCR. BOQ owns the supported template's table semantics and provenance; it is not a general BOQ extractor. Invoice-specific semantics belong to the invoice workflow. A future application/API layer must own upload validation, orchestration, and result delivery, while the UI owns presentation.

The cross-module test uses the same in-memory `DocumentResult` for CDC and BOQ. The real 30-page PDF has usable native text, so `DocumentProcessor(mode="native")` needs no OCR pass. It verifies that document identity is retained, CDC locates the Annex 05 handoff on the fixture's physical page 25, and the specialized extractor keeps blank financials null and source evidence linked. Page 25 is a test result, not a production rule.

## `DocumentPage` compatibility report

The integrated source does not define or import a public `DocumentPage` class. The BOQ adapter validates and consumes the Contract 1.0 page shape (`page_number`, `width`, `height`, `elements`), and its document entry point accepts the actual `DocumentResult` and selects a 1-based physical page. The merged BOQ tests and cross-module test use those current public producer types. No obsolete `DocumentPage` alias was added to Document Intelligence.

## Validation

Run the deterministic producer, consumer, and cross-module checks with:

```powershell
python -m pytest tests/document_intelligence tests/cdc_analysis tests/boq tests/integration -q
```

The real PaddleOCR model test remains opt-in via `RUN_REAL_OCR=1`. The ordinary CI workflow installs the deterministic runtime dependencies only and does not download OCR model weights. See `.github/workflows/ci.yml`.

## Outstanding integration work

- Restore the minimal validated FastAPI application and invoice backend from a clean historical baseline, reconcile the invoice OCR engine boundary, and record the exact migrated-file manifest.
- Add application routes that orchestrate the workflows while reusing a single `DocumentResult` for CDC and BOQ.
- Validate invoice tests and API startup alongside the module suites.
- Reproduce or close the reported phantom-page issue against the integrated API/application layer; the CDC consumer currently iterates only loaded physical pages and rejects element/page mismatches.
- Push this integration branch, and create `main` only after the missing application and invoice validation is complete.
