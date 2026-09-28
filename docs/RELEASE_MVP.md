# Tender Intelligence MVP

## Purpose

The MVP combines the frozen deterministic V2 tender analysis with a unified workspace for tender structure, obligations, financial facts and deadlines, source evidence, supported BOQ extraction, and evidence-grounded questions. It retains the existing Invoice application and APIs.

## Baseline and routes

The integration starts from `tender-intelligence-v2` at `a69be4b6ff3ea95033a7bdf4398508495c839081`. V1 and V2 contracts remain available. Important routes include `POST /process-invoice`, `POST /api/invoices/analyze`, `POST /api/cdc/analyze`, `POST /api/cdc/male/analyze`, `POST /api/v2/cdc/analyze`, `POST /api/v2/cdc/male/analyze`, `POST /api/v2/cdc/{document_id}/ask`, `POST /api/cdc/male/export.csv`, `GET /api/documents/{opaque_id}`, and `GET /health`.

## Workspace features

- Overview and recursive tender structure, with evidence references to physical source pages.
- Requirements and financial/deadline facts from deterministic V2 modules, with truthful empty states.
- Specialized five-row Ministry maintenance BOQ extraction, validation, and CSV export. The family identifier is internal. Unavailable commercial values stay null in the API, display as an em dash, and export as blank CSV cells. Physical units and unit-price wording are separate fields.
- Ask Tender retrieves matching evidence and reports insufficient evidence without inventing an answer. Ollama is optional; when available, set `ASK_TENDER_OLLAMA_URL` (default `http://127.0.0.1:11434`) and `ASK_TENDER_OLLAMA_MODEL` (default `llama3.2:3b`).
- The BOQ export is UTF-8 CSV and retains French and Arabic text.

## Limitations

- Result pages require re-upload after refresh; results are not persisted.
- Ask Tender reruns document analysis for each question.
- Specialized BOQ extraction supports only the recognized five-row family; ambiguous values are not inferred.
- Ollama availability is optional and local generation may be unavailable.
- Existing PDF redistribution provenance remains unresolved. No redistribution rights are asserted here.
- Accuracy beyond the documented deterministic behavior and tests is not claimed.

## Release verification

Release status is recorded in the integration task report and CI for the exact release commit. A green local suite alone does not establish a release; remote CI and a fresh-checkout validation are required before creating the MVP tag.
