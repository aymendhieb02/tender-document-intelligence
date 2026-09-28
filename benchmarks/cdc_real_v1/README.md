# CDC_DEVELOPMENT_CORPUS_V1

This is a development corpus, not the future final unseen evaluation set. Any documents or failures used to guide Analyzer V2 must not later be presented as held-out test data. Final evaluation requires a separately acquired corpus.

## Artifacts

- `corpus_manifest.csv`: SHA-256, file metadata, source-relative paths, reconciliation, and source-reviewed curation.
- `reconciliation.json`: actual local file, validity, uniqueness, duplicate, and Agent 6 hash-match counts.
- `curation_review.json`: curated roles and evidence notes.
- `pilot_selection.json`: seven end-to-end pilot selections.
- `ground_truth/`: source-grounded manual annotations; `VERIFIED` and `DRAFT` are kept separate.
- `predictions/`: analyzer output for the pilot.
- `results.json`, `metrics.json`, `failures.json`: per-document results, category-specific subset metrics, and concrete source-linked failure examples.
- `document_results/`: ignored local Document Intelligence intermediates; the source PDFs and these large intermediates are not committed.

The earlier one-document, sidecar-only pilot remains documented as historical context in `docs/CDC_REAL_BASELINE_V1.md`. The continuation section in that report records the local-corpus end-to-end run and its annotation and scoring limits.
