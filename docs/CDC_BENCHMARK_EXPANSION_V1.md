# CDC benchmark expansion V1

## Scope and review

This measurement-only update uses the locally available, 30-page source PDF for CDC-DEV-001, `MM_Cahier-des-charges-type-Entretien.pdf` (SHA-256 `f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d`). The printed table of contents on physical page 2 and article headings on pages 3-11 were reviewed against rendered source pages. Financial and deadline facts on pages 7-9 were visually checked against the PDF. Ground truth was extended without changing the document's existing VERIFIED status or any extraction code.

The current analyzer V2 prediction was scored against this new scope. These results describe one development-corpus document, not a held-out evaluation or corpus-wide accuracy estimate.

## What became measurable

Before this update, article labels were positive examples only, so article precision and exhaustive recall were unavailable. CDC-DEV-001 now has a complete, source-page-verified inventory of all 36 article headings: 27 in Section A and 9 in Section B. Against the saved V2 prediction, article precision is 36/36 (100%) and recall is 36/36 (100%) for this one document.

Before this update, requirement labels were also positive examples only. The new inventory exhaustively covers the stated numeric financial, guarantee, deadline, penalty, warranty, and operational-period facts in Articles 16, 19-22, 24-25 (pages 7-9). It contains 14 facts with populated values and one unresolved execution-period blank, which is retained as unscored evidence. V2 has a candidate of the expected type and article for 10/14 facts (71.4% coverage); the candidates are on the verified physical page for 10/10. Nine of the 10 located candidates have the correct normalized value. Exact normalized fact recall within this declared subset is 9/14 (64.3%). Requirement precision remains unavailable because predicted requirement candidates have not been exhaustively labeled as true or false positives.

Three focused negative-candidate measurements are new: 8/8 Lot headings were correctly excluded from major sections; 6/6 in-text annex mentions on page 5 were not treated as annex headings there; and the 20% order-volume variation was not classified as a guarantee or penalty. These are candidate rejection rates on reviewed examples, not general specificity estimates.

No negative BOQ example became measurable. The available source PDF has a positive BOQ, and no locally available, source-reviewed PDF without a BOQ was found in this checkout. The manifest's other entries were not used to invent source-verified labels.

## Scanned Arabic investigation: CDC-DEV-009

**Primary attribution: OCR_LIMITATION (provisional, medium confidence).** The saved full-document run has 1,192 PaddleOCR elements across all 37 pages. The extracted strings are predominantly noisy Latin-like transliterations of Arabic, with low-to-moderate confidence values in the inspected sample; the OCR output does not preserve readable Arabic article or part headings that would let the analyzer recognize them. This makes OCR the primary observed blocker. An analyzer limitation cannot be isolated while its input lacks readable source headings.

This is not a scored failure attribution: the source-grounded annotation for CDC-DEV-009 remains **DRAFT**, the cover is the only source page previously visually reviewed, and no OCR or analyzer behavior was changed. Its labels remain excluded from metrics.

## Artifacts and limits

- `benchmarks/cdc_real_v1/ground_truth/CDC-DEV-001.json`: complete article inventory, scoped exhaustive financial/deadline facts, and reviewable negative candidates. Blank source values remain unresolved.
- `benchmarks/cdc_real_v1/metrics_expansion_v1.json`: newly measurable metrics and explicit scope.
- `scripts/score_cdc_expansion_v1.py`: reproducible scorer; pass `--prediction <relative-path>` to a local saved prediction. The official V1 release does not commit generated predictions, so the script does not recreate or add them.
- `tests/test_cdc_benchmark_expansion_v1.py`: guards the inventory, metric scope, negative examples, and DRAFT gate.

Benchmark artifact and V2 structure tests passed: `10 passed`. The full project suite passed with `226 passed, 2 skipped`, using `pytesseract==0.3.13` from the local package cache and Tesseract `5.4.0`. The temporary test dependency path was not committed.

The earlier positive-example hit rates, the three complete section inventories, and the six verified documents remain unchanged. No production analyzer, OCR, raw PDF, OCR cache, or generated prediction was added or modified by this update. The corpus still has no negative BOQ inventory, document-role precision/recall, or scored Arabic scan.
