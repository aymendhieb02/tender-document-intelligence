# Historical Application Migration

## Source verification

- **Source repository:** `https://github.com/aymendhieb02/Smart-OCR-to-ERP-Platform.git`
- **Source commit:** `446e576fa391d84f7e00461b7dd1be36cf717265`
- **Source tag:** `page1-inv01-verified-baseline`
- **Verification:** the annotated tag resolves to commit `446e576` (`test(evaluation): add Page-1 verified baseline comparator support`).

The original working checkout was dirty and was left untouched. Its `.git` directory is read-only in this environment, so Git could not create a worktree or local clone. Source files were materialized with `git archive` from the verified commit into a separate temporary snapshot; only committed files from that snapshot were copied.

## Migrated historical files

All paths below came from the committed snapshot. `app/main.py` and `app/api/routes.py` were then adapted for the integrated workflows; other listed files were copied unchanged.

**FastAPI and invoice import closure**

```text
app/api/__init__.py
app/api/routes.py (ADAPTED)
app/core/canonical_parties.py
app/main.py (ADAPTED)
app/services/bbox_contract.py
app/services/confidence_engine.py
app/services/confidence_normalizer.py
app/services/correction_identity.py
app/services/correction_store.py
app/services/correction_suggestions.py
app/services/document_classifier.py
app/services/document_graph.py
app/services/document_layout.py
app/services/dossier_reconciler.py
app/services/dossier_segmentation.py
app/services/duplicate_detector.py
app/services/dynamic_tables.py
app/services/erp_mapper.py
app/services/erp_readiness.py
app/services/extraction_quality.py
app/services/field_enricher.py
app/services/field_extractor.py
app/services/file_loader.py
app/services/financial_reasoner.py
app/services/fraud_indicators.py
app/services/graph_field_extractor.py
app/services/invoice_validation_report.py
app/services/json_writer.py
app/services/layout_analyzer.py
app/services/layout_model/__init__.py
app/services/layout_model/layout_model_detector.py
app/services/layout_model/layout_model_loader.py
app/services/layout_model/layout_model_router.py
app/services/line_item_extractor.py
app/services/ocr_fallback_planner.py
app/services/party_resolver.py
app/services/pipeline_runner.py
app/services/preview_generator.py
app/services/producer_invoice_review.py
app/services/producer_table_reader.py
app/services/review_assistant.py
app/services/review_explanation_builder.py
app/services/row_validation_engine.py
app/services/ruspina_field_extractor.py
app/services/semantic_classifier.py
app/services/table_reconstruction_engine.py
app/services/tradenet_field_extractor.py
app/services/validation_explainer.py
app/services/validator.py
app/utils/fuzzy_keywords.py
```

**Historical static application shell**

```text
app/static/app.js
app/static/dossier-navigation.js
app/static/index.html
app/static/strings.js
app/static/styles.css
```

These are the older committed frontend assets needed for the existing root/invoice application. No Agent 4 dashboard, shell, CSS, JavaScript, or Ministry presentation files were copied.

## Reused, adapted, replaced, and omitted files

| Classification | Files / decision |
|---|---|
| **UNCHANGED** (already in integration) | `app/core/config.py`, `app/services/ocr_profiles.py`, `app/services/performance_timer.py`, `app/services/table_regions.py`, `app/utils/helpers.py`; their bytes matched the historical source at the verified commit. |
| **ADAPTED** | `app/main.py` includes workflow routes and structured error handlers. `app/api/routes.py` preserves `/process-invoice` and delegates it to the DocumentResult-backed handler. `app/core/schemas.py` adds optional invoice response fields `document_id` and `document_url`. |
| **REPLACED / NOT COPIED** | Historical `app/services/ocr_engine.py` and `app/services/preprocessing.py` differ from the integrated DI-owned files. The DI versions remain authoritative; the historical OCR implementation was not copied over them. |
| **NEW application files** | `app/api/document_store.py`, `app/api/workflow_routes.py`, and `app/invoice/document_result_adapter.py` implement upload/access, HTTP orchestration, and the invoice compatibility boundary. |
| **NOT MIGRATED** | `.env.example`, credentials/configuration, virtual environments, OCR caches/model weights, generated outputs, sample invoice binaries, optional layout/table model weights, and unrelated datasets/experiments. The official dependency files were retained. |

No file was sourced from the historical working tree's uncommitted changes.

## OCR reconciliation and invoice compatibility

The historical invoice pipeline expects the old `OCRResult`/`OCRLine` input. `DocumentResultInvoiceAdapter` maps each Contract 1.0 evidence element to that established invoice boundary, preserving physical page, confidence, rendered-page bounding box, coordinate space, and source. The existing invoice extractor, validators, correction/review services, and response model remain the invoice semantics owner.

Normal invoice analysis runs `DocumentProcessor` once, then passes its result through the adapter to the historical invoice pipeline. The pipeline's document loader still renders source pages for invoice layout and preview work, but it does not run another full OCR pass. The adapter permits existing invoice-only targeted recovery calls when the invoice pipeline explicitly requests them. CDC and BOQ consume one shared `DocumentResult`; BOQ extraction is driven by CDC's handoff page range.

## API and document access

- `POST /process-invoice` retains the historical path for the committed static client.
- `POST /api/invoices/analyze` exposes the same invoice response contract for new clients.
- `POST /api/cdc/analyze` returns page metadata and a serialized `TenderDocument`.
- `POST /api/cdc/male/analyze` returns CDC structure, BOQ handoffs, template detection, BOQ results, and diagnostics.
- `GET /api/documents/{id}` serves the uploaded source using an opaque process-local ID.
- `GET /health` reports application availability.

Uploads are size/extension checked and stored under a process-local temporary directory. API responses never include local filesystem paths. Documents are available only until the app process exits; durable storage is out of scope for V1.

Errors use a structured envelope with code, workflow, message, optional technical class, recoverability, and safe diagnostics. An unrecognized Ministry template returns `template_detected: false` with diagnostics and no fabricated rows. For the empty reference template, the API returns five structural slots and leaves financial values null.

## Historical invoice regression test disposition

Twelve committed test modules were copied unchanged to `tests/invoice_regression/` and run against the integrated code: `test_extractor.py`, `test_validator.py`, `test_line_items.py`, `test_schema.py`, `test_correction_workflow.py`, `test_ocr_engine.py`, `test_ocr_profiles.py`, `test_producer_invoice_reader_v2.py`, `test_release_blocker_invoice.py`, `test_dossier_api.py`, `test_dossier_pipeline.py`, and `test_file_loader_formats.py`. Result: **83 passed**. No assertions were reduced.

No historical tests were adapted. The new `tests/test_platform_api.py` covers startup, all three workflows, errors, empty/unrecognized Ministry cases, document retrieval, and physical-page rejection. Historical browser/UI tests remain with Agent 4's frontend work. Model/benchmark tests requiring separately provisioned weights or labeled evaluation data were not imported into the V1 backend regression subset; they are not represented as passing or obsolete.

## Known limits

- Document retrieval is temporary and process-local.
- Real PaddleOCR model execution is still a separate opt-in workflow (`RUN_REAL_OCR=1`); native-text and deterministic API tests do not download OCR models.
- Invoice-only targeted OCR recovery remains a legacy compatibility path; ordinary invoice processing consumes the generic DocumentResult directly.
- No claim of completed ground-truth review or invoice accuracy is made.
