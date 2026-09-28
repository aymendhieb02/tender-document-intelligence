# Ask Tender MVP

Ask Tender provides single-turn, evidence-grounded questions over a document already uploaded through the CDC workflow.

## Architecture and endpoint

`POST /api/v2/cdc/{document_id}/ask` accepts `{"question": "..."}`. The document ID comes from an existing CDC upload response. The process-local document store holds the source for the life of the server process; Ask Tender reruns the existing document and CDC analysis over that source. No document paths or OCR payloads are returned.

Retrieval ranks article, clause, paragraph, title, requirement candidate, and normalized financial fact text using normalized token overlap, exact phrase matching, and small boosts for structured evidence. Results are limited to six passages and bounded in size. It uses no vector database or embeddings.

## Ollama configuration

Generation is optional and runs only after retrieval (except for supported deadline, guarantee, execution-period, and payment fact queries answered deterministically). Configure `ASK_TENDER_OLLAMA_URL` (default `http://127.0.0.1:11434`) and `ASK_TENDER_OLLAMA_MODEL` (default `llama3.2:3b`). The service never downloads a model. Calls use a 12-second timeout. Ollama is not checked at startup.

If no evidence matches, the response says the information was not found. If local generation fails after evidence was retrieved, the API returns `generation_unavailable` and identifies the retrieved citations rather than fabricating an answer.

## Evidence and limitations

Each evidence item contains a source label, bounded text passage, status where available, and the V2 `EvidenceReferenceV2` pointer (document ID, physical page, element ID, and optional bounding box). Requirement candidates retain their `NEEDS_REVIEW` status. References are derived from source evidence and page numbers are never inferred.

This is a lightweight single-turn MVP. Ranking can miss paraphrases; asking an ambiguous question may return broad passages. The document store is process-local and temporary. V2 analysis output/BOQ results are not persisted, so source analysis is rerun for each question. Future improvements may cache structured V2 output and add local embeddings for candidate retrieval, while retaining deterministic evidence checks and citations as the source of truth.
