# CDC_DEVELOPMENT_CORPUS_V1 baseline pilot

This is a development corpus and a reproducible baseline record, not a final benchmark, a production accuracy dataset, or a representative sample of Tunisian tenders. Reusing these files or their failure examples for development makes this corpus unsuitable as an unseen final test set. A held-out evaluation needs new documents.

## What is available

Agent 6's acquisition metadata reports 26 PDF rows, one exact duplicate, and 25 unique PDFs. The acquisition raw-PDF directory is empty in this checkout. The only seed PDF present is the separate 30-page MALE generic maintenance specification template (`dataset/cdc/raw/MM_Cahier-des-charges-type-Entretien.pdf`), also represented in the seed inventory. Thus 1 of 25 unique seed documents is locally available; 24 are unavailable. The manifest preserves the available acquisition metadata as hints and marks absent-file labels as pending review; it is not a canonical human-curated inventory of absent documents.

The available file is a real PDF and its SHA-256 matches the seed inventory. It is native-text, French, and its title page says “Cahiers de charge type.” This supports a CDC/template classification for this file. It is not a specific live procurement dossier. No other seed PDF was available for content review or dossier grouping.

## Pilot and execution boundary

The pilot has one usable document, below the requested 5–8. The existing `DocumentResult` sidecar was passed to the current CDC Analyzer CLI, and the emitted prediction is preserved under `predictions/`. This measures the CDC Analyzer consumer on that frozen input. Document Intelligence/OCR was not rerun from the PDF, and the output is not an end-to-end PDF-to-CDC measurement.

The existing structure annotation remains `human_review_required`; its authoring note says it needs page-by-page visual verification. Therefore all accuracy metrics are null / not measurable. Existing predictions and sidecar labels are not ground truth. No LLM judging was used. Requirement-level labels and a page-verified structural subset are deferred until source review.

See `docs/CDC_REAL_BASELINE_V1.md` for the full findings, limitations, version freeze, and next steps. Machine-readable files in this directory are `corpus_manifest.csv`, `results.json`, `metrics.json`, and `failures.json`.
