# Ask Tender MVP

Ask Tender provides single-turn, evidence-grounded questions over a tender uploaded through the CDC workflow.

## Architecture and endpoint

`POST /api/v2/cdc/{document_id}/ask` accepts `{"question": "..."}`. The document ID comes from a CDC upload response. Source bytes and a compact, versioned analysis record persist under `outputs/tender_workspace/<storage-id>/`; Ask Tender restores the saved evidence after a browser refresh or application restart without running Document Intelligence again. A legacy source-only record can be reprocessed once to recover the structured result. No document paths or OCR payloads are returned.

Retrieval ranks article, clause, paragraph, title, requirement candidate, and normalized financial fact text using normalized token overlap, exact phrase matching, and small boosts for structured evidence. Results are limited to six passages and bounded in size. Duplicate evidence entries are removed. It uses no vector database or embeddings.

## Ollama configuration

Generation is optional and runs only after retrieval (except for supported deadline, guarantee, execution-period, and payment fact queries answered deterministically). Configure `ASK_TENDER_OLLAMA_URL` (default `http://127.0.0.1:11434`) and `ASK_TENDER_OLLAMA_MODEL` (default `llama3.2:3b`). The service never downloads a model. Calls use a 12-second timeout. Ollama is not checked at startup.

If no evidence matches, the response says the information was not found. If local generation fails after evidence was retrieved, the API returns `generation_unavailable` with citations. The UI keeps those passages usable without presenting a generated answer.

## Evidence and limitations

Each evidence item contains a source label, bounded text passage, status where available, and the V2 `EvidenceReferenceV2` pointer (document ID, physical page, element ID, and optional bounding box). Requirement candidates retain their `NEEDS_REVIEW` status. References are derived from source evidence and page numbers are never inferred.

This remains a lightweight single-turn MVP. Lexical ranking can miss paraphrases; ambiguous questions may return broad passages. There is no conversation history, semantic index, answer review workflow, or durable feedback loop. Ollama is optional; the application does not download a model. See `ASK_TENDER_REPORT.md` for implementation and verification details.
