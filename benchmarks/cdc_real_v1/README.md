# CDC_DEVELOPMENT_CORPUS_V1

This is a development corpus, not the future final unseen evaluation set. Any documents or failures used to guide Analyzer V2 must not later be presented as held-out test data. Final evaluation requires a separately acquired corpus.

## Artifacts

- `corpus_manifest.csv`: SHA-256, file metadata, source-relative paths, reconciliation, and source-reviewed curation.
- `reconciliation.json`: actual local file, validity, uniqueness, duplicate, and Agent 6 hash-match counts.
- `curation_review.json`: curated roles and evidence notes.
- `pilot_selection.json`: seven end-to-end pilot selections.
- `ground_truth/`: source-grounded manual annotations; `VERIFIED` and `DRAFT` are kept separate.
- `predictions/`: generated analyzer output; ignored and not committed.
- `results.json`, `metrics.json`, `failures.json`: compact per-document metadata, category-specific subset metrics, and source-linked failure examples. Prediction paths in results describe local regenerated outputs.
- `document_results/`: ignored local Document Intelligence intermediates; source PDFs and large intermediates are not committed.
- `metrics_v2.json`, `results_v2.json`, `docs/CDC_ANALYZER_V2_EVALUATION.md`: compact V2 development results and report. V2 prediction JSON files are generated locally under ignored `predictions_v2/`.

The earlier one-document, sidecar-only pilot remains documented as historical context in `docs/CDC_REAL_BASELINE_V1.md`. The continuation section in that report records the local-corpus end-to-end run and its annotation and scoring limits.
