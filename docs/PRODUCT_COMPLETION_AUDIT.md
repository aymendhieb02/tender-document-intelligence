# Product completion audit

Audit date: 2026-10-04 (Africa/Lagos)
Workspace: `tender-document-intelligence`

## Scope and baseline

Inspected the FastAPI entry points, upload and document stores, Document Intelligence schemas/processor/recognizer, CDC analyzer and adapters, v2 response composition, requirements and financial extractors, specialized BOQ modules, Ask Tender retrieval, UI routing and workspace components, test inventory, fixtures, settings, and existing design reports. The neighboring invoice repository was not modified.

The first literal `pytest -q` invocation failed during collection because this checkout is not installed and pytest did not add the repository root to imports. With the supported local invocation `PYTHONPATH=. pytest -q`, baseline was **282 passed, 1 skipped, 0 failed in 29.28s**. The initial collection failure is an invocation/environment issue, not a set of product test failures.

## Architecture observed

`DocumentProcessor` is the single PDF/image reader. It emits page-numbered `DocumentResult` evidence, selects native extraction on usable PDF pages, and uses the local OCR recognizer as fallback. `CDCAnalyzer` consumes that result; v2 contracts compose summary, requirements, financial/deadline, dossier, BOQ status, evidence references and diagnostics. The specialized BOQ adapter consumes selected `DocumentResult` pages. Ask Tender consumes the already analyzed `TenderDocument`, uses deterministic token/phrase retrieval, and optionally asks a configured local Ollama model.

FastAPI serves the bundled frontend and JSON endpoints. The UI has a primary navigation for overview, requirements, finances/deadlines, BOQ, sources and Ask Tender, with technical views in a secondary menu. Local OCR caches exist; analysis itself previously relied on process memory and a temporary source store.

## Status by workstream

| Area | Status from code and tests | Evidence / limitation |
| --- | --- | --- |
| Upload and validation | Implemented | Extension allow-list, byte cap, random storage IDs, safe basename, PDF/image decoder errors and stable error envelopes. MIME now derives from the allow-listed filename extension rather than client headers. |
| Document Intelligence | Implemented, with real-corpus gaps | Native text, page geometry, per-page path selection, OCR fallback, caching, diagnostics and versioned schema are present. The current reference tender exercises native extraction only; OCR quality is not demonstrated by that benchmark. |
| CDC structure and requirements | Implemented but heuristic | Sections, annexes, requirement candidates, evidence and financial/deadline facts are emitted. Real reference produces 5 sections, 6 annexes and 54 requirement candidates but no title and no top-level articles; candidates require review. |
| BOQ | Partially implemented | One geometry/terminology family (`MALE_MUNICIPAL_MAINTENANCE_BOQ_V1`) is recognized. The reference page yields five NOT_CHECKABLE row slots, with empty values. It is explicitly an empty template and provides no completed-BOQ accuracy measure. General-purpose table/BOQ extraction is not present. |
| Ask Tender | Implemented MVP | Evidence-ranked deterministic retrieval, structured financial facts, citations and optional local Ollama are present. It can report matching evidence while generation is unavailable. Retrieval is lexical and may miss paraphrases. |
| Persistence | Was broken; repaired in this pass | Before changes, source bytes lived in `TemporaryDirectory`, structured analysis lived in `_tender_results`, and result routes told users to re-upload after refresh. The app now persists the source and versioned JSON records under ignored `outputs/tender_workspace`, exposes GET result/BOQ export routes, and reloads Ask Tender from saved `TenderDocument` JSON. |
| Exports/review | Partial | BOQ CSV retains empty cells as empty strings and page/status columns; formula-like text is neutralized. Review states exist in models, but there is no durable human-edit workflow. No requirements CSV or general structured export is exposed. |
| UI/UX | Improved, still partial | French tender workspace, accessible Ask Tender CTA and primary tabs are present. Processing feedback reports elapsed time, not fake percentage. Upload/result state is browser-driven. Stage-by-stage progress and document history are not implemented. |
| Performance | Measured for one reference | Timings are recorded in `docs/PERFORMANCE_REPORT.md`; one native-text reference cannot represent scanned documents or typical OCR cost. |
| Security/reliability | Basic controls present | User-facing exceptions avoid tracebacks; file size/page/pixel limits exist. Disk retention/quota, CORS scope, archive/zip bombs and resource isolation are not managed as a multi-user production service. |

## Defects addressed in the completion pass

- Replaced process-lifetime temporary source storage with a local persistent per-document directory and atomic JSON metadata/analysis writes. Record IDs are strictly 32-character lowercase hex, and source filenames are reduced to a basename.
- Persisted the compact structured tender response and evidence-bearing `TenderDocument`, not the much larger transient `DocumentResult` page/elements graph.
- Added GET `/api/v2/cdc/{document_id}` and saved BOQ CSV GET endpoint. Reloaded Ask Tender now reads saved evidence instead of OCRing/reanalyzing the PDF.
- Repaired the result URL to use the stored-source ID extracted from the document URL; the Document Intelligence content hash is a separate ID and is not a storage key.
- Hardened CSV formula handling while preserving numeric negative values and nulls.
- Added timing logs for Ask Tender retrieval and optional local generation.

## Test and fixture inventory

The test tree covers document contracts, native/OCR processing, CDC structure and financial/date normalization, requirements classification, specialized BOQ detection/extraction/validation/export, Ask Tender service/API, tender UI/API and invoice regressions. The only baseline skip must be rechecked at final test time with `pytest -rs` and is not counted as a pass. Existing benchmark documentation distinguishes real, synthetic and empty-template BOQ material correctly.

## Remaining risks and gaps

- No representative completed BOQ set with independent labels; do not present reference-template row recognition as extraction accuracy.
- No durable retention policy, deletion interface, quotas, or multi-user access control for persisted tender records. Local disk contents remain until removed by an operator.
- A missing/corrupt source is handled as unavailable; legacy source-only records may be recovered by one reprocessing pass when a user asks a question.
- Invoice result views remain session-only; this completion work covers tender analysis persistence.
- CORS currently permits wildcard origins with credentials in the application setup; a deployment exposed beyond loopback should constrain origins.
- The local browser flow was verified on the reference upload: workspace reload after server restart, Ask Tender citations, and source-page navigation. The automated restart regression independently verifies API recovery without reprocessing.
