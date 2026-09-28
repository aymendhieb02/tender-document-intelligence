# Integrated Backend V1

## Architecture

`integration/backend-v1` combines Document Intelligence Contract `1.0`, `CDC_ANALYZER_BASELINE_V1`, and `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1`, preserving the official module histories. Their common Git merge base is `b160eb6fa60ca1ad9aaa83462dc313c215837fef`.

```text
PDF or image upload
        │
        ▼
DocumentProcessor ──► DocumentResult (identity, physical pages, evidence)
        │                       │
        │                       ├──► invoice compatibility adapter
        │                       │       └──► historical invoice semantics/validation
        │                       │
        │                       └──► CDCAnalyzer ──► TenderDocument
        │                                             │
        │                                             └──► BOQ handoff page range
        │                                                    └──► specialized BOQ extractor
        ▼
Application API owns upload validation, workflow orchestration, serialization,
structured errors, and short-lived access to the uploaded source document.
```

Document Intelligence owns generic evidence and physical page truth. The invoice adapter maps the existing `DocumentResult` evidence to the historical invoice pipeline's `OCRLine` boundary; invoice-specific extraction and validation remain outside Document Intelligence. The adapter does not run a second full OCR pass. Existing invoice-only targeted recovery remains available where the legacy invoice pipeline explicitly requests it. CDC owns tender structure and BOQ classification, and consumes the same `DocumentResult`. BOQ owns the specialized template's financial/table semantics, Decimal parsing, provenance, and null values.

## HTTP API

| Route | Workflow | Result |
|---|---|---|
| `POST /process-invoice` | Historical invoice route retained for the old static client | Existing invoice fields, line items, validation, ERP output, document ID and retrieval URL |
| `POST /api/invoices/analyze` | Invoice workflow | Same response contract as the retained route |
| `POST /api/cdc/analyze` | General tender analysis | Document identity/pages and serialized `TenderDocument` |
| `POST /api/cdc/male/analyze` | Ministry-specific BOQ | `TenderDocument`, handoffs, template detection, extracted results and diagnostics |
| `GET /api/documents/{id}` | Uploaded source retrieval | Original PDF or image while the server process remains alive |
| `GET /health` | Health check | Service name and `ok` status |

All routes accept a multipart field named `file`. Supported formats and the upload size limit are enforced before processing. Errors use `{error: {code, workflow, message, technical_detail, recoverable, diagnostics}}`; stack traces and server filesystem paths are not returned. An unrecognized Ministry template is a successful structured response with `template_detected: false`, not a fabricated extraction or server error.

Uploads are kept in a process-local temporary directory and removed when the application exits. The API exposes only an opaque document ID and retrieval URL, never a local path. Retrieval is unavailable after restart; persistent document storage is outside V1.

## Cross-module behavior

The reference PDF has 30 pages and usable native text. `DocumentProcessor(mode="native")` creates one `DocumentResult`; CDC then locates the BOQ handoff, and the specialized extractor consumes that same result. The cross-module and API tests verify physical page 25 for this fixture, preserved document identity, five empty-template slots, null financials, and evidence provenance. Page 25 is fixture output, not application logic.

At the application boundary, invoice evidence must have contiguous 1-based pages and each evidence element must agree with its containing page. CDC independently rejects a mismatched element/page reference. The historical phantom-page issue was not reproduced; an API regression test verifies that invalid evidence is rejected without creating a page.

## Run and validate

Start the app:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run all deterministic, API, and selected historical invoice regressions:

```powershell
python -m pytest -q
```

The heavy real PaddleOCR test remains opt-in with `RUN_REAL_OCR=1` via `.github/workflows/ocr-integration.yml`. The normal CI installs no Paddle model weights and runs the complete test suite.

## `DocumentPage` compatibility

The integrated source does not define or import a public `DocumentPage` class. The BOQ adapter consumes the Contract 1.0 page shape (`page_number`, `width`, `height`, `elements`), and its document entry point accepts the actual `DocumentResult`. Tests use the current producer types; no obsolete alias was added to Document Intelligence.
