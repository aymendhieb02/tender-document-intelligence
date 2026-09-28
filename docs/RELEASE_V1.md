# Tender Intelligence V1 — Deterministic Foundation

## Included

- Document Intelligence Contract 1.0 and multi-page `DocumentProcessor`.
- Deterministic CDC Analyzer V2 structure, evidence and physical-page provenance, annex detection, and BOQ handoff.
- Specialized `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1` extraction.
- Integrated FastAPI backend, invoice, CDC, and Ministère des Affaires Locales workflows, plus the frontend workspaces.
- Compact, source-reviewed development benchmark metadata and V1/V2 metrics.

## Architecture

Uploaded documents pass once through `DocumentProcessor` and `DocumentResult`. Invoice consumes that result through its compatibility boundary; CDC creates a `TenderDocument` from the same evidence; CDC BOQ handoffs select pages for the specialized extractor. The application layer owns HTTP, upload handling, orchestration, serialization, and errors.

## Verified development benchmark

`CDC_DEVELOPMENT_CORPUS_V1` contains six documents with verified source-grounded labels and one scanned document still marked DRAFT. On the reviewed subsets, V2 measured 100% precision/recall for three complete major-section inventories, 19/19 selected article examples, 27/27 reviewed annexes, 14/26 requirement examples, 7/14 normalized values among detected examples, 14/14 page attributions, and BOQ presence/page overlap on 3/3 positive documents.

This is a **development corpus, not held-out evaluation**. Article and requirement annotations are positive examples rather than exhaustive inventories. These results do not estimate broad generalization accuracy.

## Known limitations

- No production-readiness or broad generalization claim is made.
- Requirement extraction is incomplete; financial value normalization remains partial.
- The scanned Arabic example is DRAFT and unscored; OCR and Arabic extraction need further work.
- BOQ results are limited to the reviewed development examples, not final BOQ generalization.
- The release changes add no raw tender PDFs, generated prediction payloads, or DocumentResult intermediates. The pre-existing main branch still contains reference and synthetic BOQ test PDFs plus baseline DocumentResult fixtures; those files are unchanged by this release and remain available for the current regression tests. The local development-corpus archive and generated V2 intermediates remain ignored and uncommitted.

## Test status

Release-candidate validation: **225 passed, 1 skipped, 0 failed**. The skip is the opt-in PaddleOCR model execution test. `pytesseract==0.3.13` is installed from the pinned project requirement; the Tesseract fallback tests pass. The upstream Starlette/httpx deprecation warning remains non-failing.

Focused results: V2 benchmark/structural tests 8 passed; CDC Analyzer 32 passed; Document Intelligence 42 passed, 1 skipped; BOQ 18 passed; integration 2 passed; API 9 passed; frontend/static 5 passed. `git diff --check` passed.

## Next development wave

Evaluate on a separately acquired held-out corpus. Expand complete section/article/requirement annotations; improve requirement and financial-value extraction; investigate scanned Arabic OCR; and measure BOQ generalization without treating development-corpus results as unseen performance.

## Reproducibility notes

The compact artifacts are `benchmarks/cdc_real_v1/metrics.json`, `results.json`, `metrics_v2.json`, and `results_v2.json`, with annotations and method notes alongside them. Generated predictions and per-page DocumentResults are ignored local outputs. With the source corpus available locally at `<corpus-root>` (matching the manifest's relative paths and SHA-256 values), regenerate V2 artifacts from the repository root:

```powershell
python scripts/run_cdc_real_v1_pilot.py <corpus-root> --prediction-dir predictions_v2 --document-results-dir document_results_v2 --results-file results_v2.json
python scripts/score_cdc_real_v1.py --prediction-dir predictions_v2 --metrics-file metrics_v2.json --results-file results_v2.json
```

The source corpus and generated predictions are not committed. The metrics/report describe development results only; a held-out evaluation requires a new corpus and independently reviewed labels.

### Post-V1 artifact correction

The immutable `tender-intelligence-v1` tag contains a generated CDC prediction JSON inherited from the pre-release regression baseline. Current `main` removes that generated snapshot and tests the consumer contract from the committed `DocumentResult` fixture instead. The tag remains unchanged; new generated CDC prediction files under `dataset/cdc/predictions/` are ignored.
