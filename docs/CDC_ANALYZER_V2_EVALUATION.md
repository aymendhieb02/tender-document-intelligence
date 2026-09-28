# CDC Analyzer V2 evaluation

## Scope and reproducibility

This is a deterministic, failure-driven structural update measured on `CDC_DEVELOPMENT_CORPUS_V1`. The seven-document pilot was run end to end from PDF through Document Intelligence `DocumentResult` into the CDC Analyzer. Six documents have verified source-grounded labels; scanned Arabic `CDC-DEV-009` remains DRAFT and is excluded from accuracy metrics. Contract version 1.0 and the same verified ground-truth files and metric scope as V1 were used. No OCR, Document Intelligence, requirement-value parsing, or ground-truth rules were changed. These are development results, not a held-out evaluation.

The compact machine-readable V2 artifacts are `benchmarks/cdc_real_v1/results_v2.json` and `metrics_v2.json`. Full prediction JSON and per-page intermediate DocumentResults are generated locally under ignored `predictions_v2/` and `document_results_v2/`; they are not part of the release payload. They can be regenerated with the commands in `docs/RELEASE_V1.md` when the development corpus is available.

## V1 and V2 on the same labels

| Measure | V1 | V2 | Interpretation |
|---|---:|---:|---|
| Major sections, precision / recall | 71.4% / 55.6% (5 TP, 2 FP, 4 FN) | 100% / 100% (9 TP, 0 FP, 0 FN) | Three complete inventories; V2 recognizes the reviewed Partie boundaries and no longer counts the two Lot headings as sections. |
| Article heading examples | 12/19 matched | 19/19 matched | Positive examples only; not precision or exhaustive recall. |
| Reviewed annexes, precision / recall | 100% / 100% (27/27) | 100% / 100% (27/27) | Preserved. |
| Requirement fact examples | 14/26 matched | 14/26 matched | Positive examples only; requirement extraction was not modified. |
| Normalized values among detected examples | 5/14 (35.7%) | 7/14 (50.0%) | Two additional correct values; no general value parser change. |
| Physical-page provenance among detected examples | 14/14 (100%) | 14/14 (100%) | Preserved. |
| BOQ presence / page overlap | 3/3 / 3/3 | 3/3 / 3/3 | Preserved. |

Precision and exhaustive recall for articles and requirements are not measurable because those annotations are curated positive examples, not complete inventories. The two extra normalized-value hits coincide with facts surfaced correctly after the structural changes; the value extraction rules themselves are unchanged.

## Per-document results

Counts below describe prediction output; only the listed reviewed categories are scored.

| Document | V2 sections | Article positive examples | Annexes | Requirement examples found / expected | Value correct / detected | Page correct / detected | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| CDC-DEV-001 | 5 | — | 6 | 5/5 | 5/5 | 5/5 | Template fixture; eight blank Lot placeholders now remain typed Lots rather than requirement noise. |
| CDC-DEV-006 | 0 | 3/3 | 0 | 0/6 | — | — | Arabic الفصل headings recovered as Article nodes. |
| CDC-DEV-007 | 2 | 4/4 | 14 | 3/5 | 1/3 | 3/3 | Partie I/II recovered as typed top-level sections; Lots separate. |
| CDC-DEV-009 | 0 | Unscored | 0 | Unscored | — | — | Draft scan; full 37-page OCR run, 1,192 elements. |
| CDC-DEV-011 | 0 | 2/2 | 0 | 1/1 | 0/1 | 1/1 | Arabic الفصل headings recovered. |
| CDC-DEV-017 | 2 | 6/6 | 7 | 4/5 | 1/4 | 4/4 | Partie I/II recovered as typed sections. |
| CDC-DEV-022 | 0 | 4/4 | 0 | 1/4 | 0/1 | 1/1 | Arabic الفصل headings recovered. |

Unreviewed article, annex, section, and requirement detections are not counted as false positives. In particular, the table above does not turn the unreviewed output counts into precision claims.

## Root cause and failure patterns

The measured V1 structural failures shared a small number of deterministic causes:

1. **Arabic article labeling and Unicode numbering (`ARTICLE_NUMBERING`, `LANGUAGE`)**: the heading detector recognized English `Article`/`Art` but had no Arabic `الفصل` cue. Native PDF Arabic rows also arrived in source order that differed from visual right-to-left order. V2 recognizes corpus-evidenced Arabic labels, normalizes decimal and ordinal number forms, and composes structural rows from word parts while retaining their original evidence and provenance. Selected article examples moved from 0/7 to 7/7 across CDC-DEV-006, 011, and 022.
2. **Partie and Lot conflation (`SECTION_BOUNDARY`, `NESTED_STRUCTURE`)**: the generic Roman-number section pattern accepted headings such as `II – Lot 2`, while `Partie I/II` was not a semantic heading type. V2 identifies Partie as a typed top-level section, distinguishes Lots into a separate `lots` collection, and nests article headings under the active part. The two complete reviewed section lists now match exactly.
3. **Requirement/value extraction remains a separate limitation (`REQUIREMENT_MISSED`, `VALUE_NORMALIZATION`)**: among the 26 positive facts, 12 remain undetected. Of 14 detected examples, seven values still fail the benchmark comparison. Examples include Arabic deadline/duration/penalty/warranty/payment facts that have no aliased requirement candidate, French date candidates with `normalized_value=null`, penalty candidates without normalized rates/caps, and a provisional guarantee candidate without a normalized amount. These failures span multiple types and languages; no common safe value-parser change is supported by this structural task, so they are retained for a separately measured V2.1 investigation.
4. **Annex/BOQ and page evidence (`ANNEX_DETECTION`, `BOQ_DETECTION`, `PAGE_PROVENANCE`)**: no reviewed regression was observed: 27/27 annex examples, all three BOQ-positive documents and page overlaps, and 14/14 matched requirement page attributions remain intact.
5. **Scanned Arabic remains an OCR investigation (`OCR_FAILURE`, `SCANNED_DOCUMENT`)**: CDC-DEV-009 produced 1,192 PaddleOCR elements over all 37 pages, but the saved OCR text contains no recognized Arabic chapter/part cues and consists largely of noisy Latin-like transliterations. Since the labels remain DRAFT, zero headings are not scored and cannot be attributed to the analyzer independently of OCR quality.

## Requirement mismatch audit

The 19 incorrect or missing positive facts are not nine value-normalizer failures: 12 of 26 are not detected at all, and seven of 14 detected facts fail exact normalized-value comparison. Specific detected-value mismatches are:

- CDC-DEV-007: penalty rate (p. 8) and penalty cap (p. 9).
- CDC-DEV-011: submission deadline (p. 1; deadline candidate has no normalized date).
- CDC-DEV-017: provisional guarantee (p. 3; candidate has no normalized amount), penalty rate (p. 6), and penalty cap (p. 7).
- CDC-DEV-022: submission deadline (p. 1; deadline candidate has no normalized date).

The 12 misses include six annotated Arabic facts in CDC-DEV-006, annual duration and payment schedule facts in CDC-DEV-007, one payment deadline in CDC-DEV-017, and three CDC-DEV-022 production facts. Notably the CDC-DEV-022 production facts have mixed review status, including a source-ambiguous quantity explicitly marked `HUMAN_REVIEW_REQUIRED`; these remain benchmark facts and are not newly adjudicated here. The scorer's fixed 26-example denominator is retained.

## Regression tests and environment

- Benchmark artifact tests: 4 passed.
- CDC Analyzer plus BOQ integration: 34 passed.
- Document Intelligence excluding the two live Tesseract fallback parametrizations: 40 passed, 1 skipped, 2 deselected.
- At the time of the original V2 branch run, the full suite had 222 passed, 2 skipped, and 2 Tesseract fallback failures because `pytesseract` was missing from that environment. The release environment now has the pinned `pytesseract==0.3.13`; the validated release-candidate full-suite result is recorded in `docs/RELEASE_V1.md`. No OCR behavior or test skip was changed to hide the original environment setup issue.
- `git diff --check` was run on the release candidate; see `docs/RELEASE_V1.md`.

The earlier baseline report remains historical; V1's checked-in `metrics.json`, predictions, annotations, and failure observations are unchanged. The V2 outputs are separate files. No raw PDF is part of the V2 artifact set. The local development corpus is now used to guide analyzer work and must not be presented as an unseen final V2 test set; obtain a new held-out corpus for final evaluation.

## Decision

**Enough verified evidence to design CDC Analyzer V2: YES.** Six documents have verified labels, five are useful tender documents plus one reusable template, PDF processing ran end to end, multiple French and Arabic structures were represented, and the benchmark provides measurable same-scope scores plus repeated page-grounded failure patterns. This supports the targeted V2 changes above. It does not establish broad corpus accuracy: only three documents have complete major-section lists, article and requirement annotations are examples, and the scanned document is unscored.
