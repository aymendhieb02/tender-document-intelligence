# Ask Tender report

Date: 2026-10-04

## Behavior and architecture

Ask Tender is a single-turn local feature at `POST /api/v2/cdc/{document_id}/ask`. It ranks tender titles, articles, clauses, paragraphs, requirement candidates and financial facts with normalized lexical overlap and small boosts for structured evidence. Results are bounded to six passages and include page/evidence references. Supported deadline, guarantee, execution-period and payment queries can use deterministic structured-fact responses. Other evidence-backed questions may use an optional Ollama endpoint configured by `ASK_TENDER_OLLAMA_URL` and `ASK_TENDER_OLLAMA_MODEL`; no remote model or API is introduced. The local-model prompt constrains the answer to supplied tender evidence.

When no passage matches, the service returns `insufficient_evidence`. When evidence exists but local generation is unavailable, it returns `generation_unavailable` and citations. It does not claim a generated answer in that state.

## Persistence repair

Previously the API kept CDC results in a process dictionary, source uploads in a temporary directory, and reprocessed the source when the cache was absent. The current implementation persists source bytes and a versioned JSON record under `outputs/tender_workspace/<storage-id>/`. The structured result is restored for browser refresh and Ask Tender without a second Document Intelligence pass. Only the compact CDC/v2 response and evidence-bearing tender model are persisted; transient page-level OCR/layout objects are not.

The UI exposes Ask Tender in the primary workspace navigation and at the page header. Its submit state, empty-evidence response and generation-unavailable state remain explicit.

## Verification and measured behavior

- Unit/API coverage includes known evidence, missing evidence, Ollama unavailable, citations, invalid IDs and reuse.
- A restart-like regression creates a second store instance, retrieves the full tender result, loads the source, asks a cited question, and fails if `DocumentProcessor` runs again.
- The real 30-page reference produced six cited passages for “Quelle est la caution provisoire ?”; local answer generation was unavailable during measurement, so the status correctly remained `generation_unavailable`.
- For that run, retrieval took 568 ms, the attempted local Ollama call took 2,030 ms, and total Ask Tender wall time was 2,598 ms. These vary with the host and local model availability.

## Limitations

Lexical matching can miss paraphrases and broad questions can surface adjacent passages. The reference test has no OCR pages and is not a broad question-answer quality benchmark. There is no conversation history, answer review workflow, semantic index, or durable feedback loop. Ollama is optional and quality depends on an installed local model; the application does not download one.
