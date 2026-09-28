# Platform API Contract V2

## Purpose and compatibility policy

The application is one modular FastAPI service. Contract versions describe externally visible API payloads; they are separate from the application release version and from domain schema versions such as `TenderDocument.schema_version` and `document_intelligence_contract_version`.

V1 routes and their response shapes remain frozen for compatibility. Additive V2 routes use the explicit `/api/v2/` path prefix. A future incompatible change should use a new path version; additive fields and module additions may be made within V2 when consumers tolerate unknown fields. There are no per-module services or independently versioned APIs.

V2 responses use an envelope with a `contract_version`, document identity/access metadata, the existing serialized `TenderDocument`, and named module availability records. Each module record distinguishes data that was produced from data that was not run, not implemented, unavailable, or not applicable. An absent capability is represented by an explicit status and `data: null`; an empty array is reserved for a real, successfully produced empty result (for example, diagnostics when none were emitted).

## Actual V1 contract inspected at the V1 baseline

| Route | Request | Successful response |
|---|---|---|
| `POST /process-invoice` | multipart `file` | Historical invoice `ProcessInvoiceResponse`; delegates to `/api/invoices/analyze` |
| `POST /api/invoices/analyze` | multipart `file` | `ProcessInvoiceResponse`, including detected fields, validation, ERP output, review/OCR fields, `document_id` and `document_url` |
| `POST /api/cdc/analyze` | multipart `file` | `{document_id, document_url, source_type, page_count, pages[], tender_document}`; each page has page number, dimensions and coordinate space; `tender_document` is `TenderDocument.model_dump(mode="json")` |
| `POST /api/cdc/male/analyze` | multipart `file` | CDC document identity plus `tender_document`, `template_detected`, nullable `template_family`, `boq_handoffs[]`, `boq_results[]`, and `diagnostics[]`; page dimensions are not returned by this V1 endpoint |
| `GET /api/documents/{opaque_id}` | opaque upload ID | Original uploaded bytes with inline content disposition while the in-process temporary document store retains the upload |
| `GET /health` | none | `{status: "ok", service: <configured service name>}` |

`TenderDocument` has its own `schema_version` (currently `1.0`) and includes structural sections, articles, annexes, requirement candidates, handoffs, diagnostics and evidence. Those requirements are structural/candidate output and must not be presented as the future Requirements Intelligence product. Document Intelligence separately publishes `DocumentResult` under its `1.0` contract. Invoice models live in `app.core.schemas`; CDC domain models live in `app.cdc_analysis.schema`; BOQ extraction models live in `app.boq.models`.

### Existing error contract

Workflow API failures return `{error: {code, workflow, message, technical_detail, recoverable, diagnostics}}`. Workflow technical detail currently uses safe exception class names for processing errors; diagnostics are stable codes. The global HTTP and request-validation handlers use the same keys. Server stack traces are logged, not serialized. The document access endpoint returns a structured `document_not_found` workflow error for expired or unknown IDs. No response includes the temporary storage path.

### Existing frontend adapter

`app/static/app/api.js` posts to the two V1 CDC routes. It accepts the different V1 page shapes, synthesizes lightweight page-number entries for Ministry when only `page_count` is present, and exposes a UI convenience `boq_document`. This adapter is V1-specific; it does not define the server contract and must not be used to infer that an unrun module produced results.

## V2 routes and envelope

- `POST /api/v2/cdc/analyze`
- `POST /api/v2/cdc/male/analyze`

Both accept the same multipart `file` input and invoke the current deterministic V1 workflow implementation. V2 does not add extraction engines. The successful response contains:

- `contract_version: "2.0"`;
- `document`: content-derived `document_id`, the opaque `document_url`, `source_type`, and actual `page_count`;
- `tender_document`: the existing typed `TenderDocument` value, without a second copy of `DocumentResult`;
- `modules`: explicit availability records for `summary`, `requirements_intelligence`, `financial_deadline_intelligence`, `dossier`, `compliance`, `boq`, `evidence`, and `diagnostics`;
- top-level diagnostic codes emitted by the existing workflow.

A module record has `availability`, nullable `data`, optional `reason`, and `diagnostics`. `not_implemented` means no producer exists. `not_run` means the selected workflow did not invoke that producer. `unavailable` means a producer ran and did not find a supported result. `not_applicable` is reserved for a capability that does not apply to that request. `available` means the value was actually produced. `partial` is reserved for a producer that explicitly reports partial output; it is not inferred by this envelope.

The general CDC V2 route marks BOQ `not_run`; the Ministry V2 route exposes the existing BOQ result only when the supported template was detected, otherwise BOQ is `unavailable` with null data. Empty template slots emitted by the existing extractor remain valid observed template output; V2 does not synthesize them. Future summary, Requirements Intelligence, financial/deadline intelligence and compliance are `not_implemented`. Dossier is `not_run` for these single-document CDC routes. Candidate requirements remain only in the existing `tender_document.requirements` field.

## Evidence and provenance references

V2 evidence references are intentionally small and reusable. Each reference identifies `document_id`, 1-based `page_number`, stable `element_id` and `evidence_id`, plus optional `bbox`, `coordinate_space` and `source`. `evidence_id` is the deterministic composite `document_id:page_number:element_id`. Bounding boxes stay in the coordinate space named by `coordinate_space`; they are never implicitly normalized. References are derived from evidence actually present in `TenderDocument`, deduplicated by document/page/element, and do not repeat OCR text or the full `DocumentResult`.

Future module payloads should cite these references (or the same fields) instead of embedding page OCR or a full document result. A missing bbox or source is serialized as null when that provenance is not available; consumers must not infer coordinates or provenance. Page and element IDs must refer to the uploaded document represented by the envelope.

## Error model

V2 errors use the existing structured error shape and HTTP status behavior: `code`, `workflow`, `message`, nullable `technical_detail`, `recoverable`, and `diagnostics`. Technical detail is for safe error categories (such as exception type), not exception text, filesystem paths, secrets, or stack traces. Diagnostics are machine-readable codes. Validation details that could expose implementation internals are not copied into V2 payloads.

## Integration points for Agents 9–12

| Agent | Proposed integration boundary | Contract rule |
|---|---|---|
| Agent 9 — summary and requirements | Populate the summary and requirements-intelligence module records from typed domain results | Keep candidate requirements in the CDC structure distinct from reviewed/business interpretations; cite evidence references; use `not_implemented` or `not_run` until a real producer runs |
| Agent 10 — financial and deadline intelligence | Populate `financial_deadline_intelligence` | Preserve unknown values as null with explicit finding/status metadata; cite source evidence; do not infer missing deadlines or amounts |
| Agent 11 — dossier and compliance | Populate dossier and compliance records where the workflow applies | Use stable document IDs and cross-document relationships; report `not_applicable` only when justified by the request, not as a substitute for missing implementation |
| Agent 12 — BOQ | Adapt the existing BOQ V1 output into the V2 module when actually invoked | Keep BOQ V1 models intact; preserve Decimal-derived serialization, null/missing semantics, validation and source evidence; do not introduce BOQ V2 in this contract layer |

All module integrations should return domain models from application services and let the API boundary serialize them. New modules must not alter V1 responses, copy full `DocumentResult` objects into payloads, or silently reinterpret unavailable data as an empty successful result. Module-level diagnostics should remain codes with user-safe messages.

## Verification

Contract tests assert V1 route compatibility, V2 envelope serialization, truthful module availability, compact provenance references, and structured error serialization. Run the full test suite with `python -m pytest -q`, then `git diff --check`.
