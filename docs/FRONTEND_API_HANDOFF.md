# Frontend API Handoff

This document describes the implemented FastAPI boundary. It is written for clients of the API; no UI-specific fields are added to backend responses.

## Uploads and routes

Send `multipart/form-data` with a single `file` field. Accepted formats are PDF, JPEG/JFIF, PNG, TIFF, BMP, and AVIF; the configured default size limit is 25 MB.

| Method and path | Description |
|---|---|
| `POST /process-invoice` | Historical invoice route retained for the committed static client. |
| `POST /api/invoices/analyze` | Invoice analysis route for new clients. |
| `POST /api/cdc/analyze` | General tender structure, requirements, annexes, and evidence. |
| `POST /api/cdc/male/analyze` | CDC analysis plus the specialized Ministry BOQ handoff/extractor. |
| `GET /api/documents/{opaque_id}` | Retrieve the uploaded PDF/image beside its result. |
| `GET /health` | Application health. |

The two invoice paths call the same handler and share a response model. `document_id` is the Document Intelligence content identity; `document_url` uses a separate opaque access ID. The document URL remains available only while the app process that accepted the upload is running.

## Invoice response

The response keeps the historical invoice fields and validation shape. The following values are from the API test's generated native-text invoice; the supplier value is not used as an asserted example because the historical extractor can classify that fixture imperfectly.

```json
{
  "document_id": "7e123aa2a48497dcacdd4294b42eaef515a3a0b3158603d89f321f0b131696f2",
  "document_url": "/api/documents/eff0c937a5f54b72b1092e95f920db98",
  "detected_fields": {
    "invoice_number": "INV-TEST-001",
    "invoice_date": "2026-06-10",
    "currency": "USD",
    "amount_ht": 250.0,
    "tva_amount": 50.0,
    "amount_ttc": 300.0,
    "tax_rate": 20.0,
    "line_items": []
  },
  "validation": {
    "is_valid": false,
    "status": "needs_review",
    "errors": [],
    "warnings": ["no line totals available"],
    "confidence": null
  },
  "erp_json": "<full historical ERP mapping omitted>",
  "erp_export": "<full historical export omitted>"
}
```

The two ERP values above are documentation placeholders and are not literal response values. The API returns their full historical objects, along with extraction details, candidates, validation explanation, line items, and review fields.

## General CDC response

The reference tender response includes 30 physical pages. Its content hash is `f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d`.

```json
{
  "document_id": "f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d",
  "document_url": "/api/documents/ad59b56d6abe4612b28e2bca84f4cf8b",
  "source_type": "pdf",
  "page_count": 30,
  "pages": [
    {"page_number": 25, "width": 1191, "height": 1684, "coordinate_space": "rendered_page_pixels"}
  ],
  "tender_document": {
    "schema_version": "1.0",
    "document_id": "f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d",
    "sections": [
      {"id": "section-1", "number": "A", "title": "CONDITIONS DE LA CONSULTATION / A.O", "start_page": 3, "end_page": 9}
    ],
    "annexes": [
      {"id": "annex-5", "number": "05", "title": "Bordereau des prix - devis estimatif", "page_start": 25, "page_end": 25, "annex_type": "boq"}
    ],
    "detected_special_documents": [
      {"document_type": "boq", "page_start": 25, "page_end": 25, "handoff": "boq_agent"}
    ],
    "requirements": [
      {"id": "requirement-1", "type": "lot", "text": "<requirement text omitted>", "source_page": 3, "extraction_status": "candidate_only", "review_status": "needs_review"}
    ],
    "diagnostics": []
  }
}
```

The response contains the complete `TenderDocument`: nested sections/articles/paragraphs, annexes, requirements, tables, handoff evidence, diagnostics, source order, and review collection. Evidence carries document identity, physical page, producer source-element IDs/text/types/confidences, bounding boxes, and coordinate space. Values in angle brackets are documentation placeholders; all other abbreviated collection fields reflect the response schema.

## Ministry specialized response

`POST /api/cdc/male/analyze` returns the same `tender_document` structure plus these fields. For the empty reference template, the detector recognizes all five anchors and the extractor emits five row slots. Article labels in this fixture are observed; blank financial values remain null with `MISSING` origin.

```json
{
  "template_detected": true,
  "template_family": "MALE_MUNICIPAL_MAINTENANCE_BOQ_V1",
  "boq_handoffs": [
    {"document_type": "boq", "page_start": 25, "page_end": 25, "handoff": "boq_agent"}
  ],
  "boq_results": [
    {
      "source_page": 25,
      "result": {
        "document_id": "f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d",
        "extractor_family": "MALE_MUNICIPAL_MAINTENANCE_BOQ_V1",
        "detected": true,
        "rows": [
          {
            "source_page": 25,
            "article": {"raw_value": "01", "normalized_value": "01", "parse_status": "PARSED", "value_origin": "OBSERVED"},
            "quantity": {"raw_value": null, "normalized_value": null, "parse_status": "MISSING", "value_origin": "MISSING", "evidence": []},
            "unit_price_ht": {"raw_value": null, "normalized_value": null, "parse_status": "MISSING", "value_origin": "MISSING", "evidence": []},
            "total_ht": {"raw_value": null, "normalized_value": null, "parse_status": "MISSING", "value_origin": "MISSING", "evidence": []}
          }
        ],
        "totals": {
          "total_ht": {"normalized_value": null, "parse_status": "MISSING", "value_origin": "OBSERVED"},
          "vat": {"normalized_value": null, "parse_status": "MISSING", "value_origin": "OBSERVED"},
          "total_ttc": {"normalized_value": null, "parse_status": "MISSING", "value_origin": "OBSERVED"}
        }
      }
    }
  ],
  "diagnostics": []
}
```

The actual rows also contain designation, unit, other HT/TTC values, validation, bounding boxes, and evidence. Totals may retain evidence for a printed blank placeholder, but their normalized financial value stays null. No zero amount is inferred.

If CDC produces no BOQ handoff or the specialized anchors do not match, the API returns HTTP 200 with `template_detected: false`, `template_family: null`, an empty `boq_results` array, and diagnostics. It does not fabricate a BOQ.

## Errors and document retrieval

Application errors use this envelope:

```json
{
  "error": {
    "code": "invalid_upload",
    "workflow": "cdc",
    "message": "Unsupported file format",
    "technical_detail": "Unsupported file format",
    "recoverable": true,
    "diagnostics": []
  }
}
```

Error codes include `invalid_upload`, `document_processing_failed`, `cdc_analysis_failed`, `boq_extraction_failed`, `invoice_extraction_failed`, and `document_not_found`. `GET /api/documents/{opaque_id}` returns the original file with its media type and a download filename. IDs resolve only inside the running process; restart removes all stored uploads. No local filesystem path is returned.
