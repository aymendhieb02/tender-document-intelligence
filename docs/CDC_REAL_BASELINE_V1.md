# CDC_ANALYZER_REAL_BASELINE_V1 — corpus-limited pilot

**Status: incomplete; no accuracy scores are claimable.** The analyzer was run on one locally available real tender specification template. The requested seed corpus PDFs were not present, the pilot is below target size, and available structure labels have not passed human visual verification. This report preserves the run and documents the blockers instead of treating acquisition heuristics as labels.

## Corpus and inventory

Agent 6's `data/acquisition/seed_inventory.csv` contains 26 rows: 26 valid-PDF claims, one exact duplicate, hence 25 unique seed documents. Its report says 12 likely CDC, 5 related tender documents, 6 notices, and several review items, but explicitly characterizes these as screening hints. Those counts are not curated ground truth.

There are no raw acquisition PDFs in `data/acquisition/` or `datasets/cdc_real/raw/` in this checkout. Of the 25 unique seed rows, only `MM_Cahier-des-charges-type-Entretien.pdf` is locally available elsewhere in the repo. It is 30 pages, native text, French, and SHA-256 `f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d`. Its title page explicitly says “Cahiers de charge type” and describes a simplified consultation/AO for civil engineering, road and utility maintenance. Curator classification: **CDC template**, not a simple notice and not a live tender dossier. Organization is left null in this inventory because the seed metadata does not establish the issuing organization; contextual MALE wording alone is insufficient to fill it.

The 24 unavailable rows have no content-verified role. The canonical manifest uses UNKNOWN/null and records acquisition hints as unverified notes. It reports counts across the **seed inventory**, and separately identifies one available PDF; it does not pretend to classify missing files. Dossier grouping cannot be done from folder hints without files or source provenance. No scanned seed document could be inspected.

| Measure | Seed inventory | Files available here |
|---|---:|---:|
| Total PDF rows / unique PDFs | 26 / 25 | 1 |
| CDC / CCAP / CCTP / DAO / NOTICE / BOQ / ANNEX / OTHER / UNKNOWN | Not human-curated; heuristic report says CDC 12, NOTICE 6, related tender 5 | CDC 1 template; other roles 0 observed; 24 unavailable/unclassified |
| Dossiers | Unknown | 0 established |
| Native / scanned / mixed | Acquisition report hints 21 / 4 / 0 among 25 | 1 / 0 / 0 available |
| French / Arabic / bilingual | Acquisition report hints 12 / 1 / 8 among 25 | French 1 available |

Acquisition profile numbers above are hints, not verified classifications. There is no defensible corpus-level role or diversity distribution until the missing PDFs are restored and reviewed.

## Pilot selection and ground truth

Selected: `CDC-DEV-001`, the available 30-page French native-text generic maintenance specification template. This offers useful template structure but only one organization/category/length/profile. It does not meet the requested 5–8-document diversity pilot. Draft annotation: `docs/ground_truth/documents/CDC-DEV-001.json`. The title-page evidence supports a draft role label, but labels remain `HUMAN_REVIEW_REQUIRED` pending visual page review. No sections, articles, annexes, requirements, or BOQ facts have been promoted to verified ground truth. Each requirement, when added, must carry physical page, raw evidence, section/article where identifiable, and explicit mandatory status when stated.

Existing `dataset/cdc/ground_truth/MM_Cahier-des-charges-type-Entretien.structure.json` is itself marked `human_review_required`; it explicitly says page-by-page visual verification is still needed. It is not ground truth for scoring. No LLM judged correctness.

## Frozen system and run

- Repository: official `tender-document-intelligence`, branch `agent/cdc-benchmark`.
- Commit tested: `a0f4e31f04540a7901ba0c956fbc5919faf4ab5e`.
- Document Intelligence contract: v1 (`DocumentResult` consumer contract; producer sidecar was used as supplied).
- CDC Analyzer: `CDC_ANALYZER_BASELINE_V1`, current source at the tested commit.
- BOQ: current repository version at the tested commit; no independent BOQ evaluation was possible.
- Execution: `python -m app.cdc_analysis <DocumentResult JSON> --output <prediction> --ground-truth <pending structure annotation>`.
- Scope: analyzer consumer run only. Document Intelligence/OCR was **not rerun from the PDF**, so this is not an end-to-end PDF baseline.
- Prediction: `benchmarks/cdc_real_v1/predictions/MM_Cahier-des-charges-type-Entretien.prediction.json`.
- CLI ground-truth gate returned `NOT YET MEASURABLE — Human-verified source-linked labels required`.

## Results

All precision, recall, normalized-value correctness, page provenance accuracy, native/scanned accuracy, and BOQ detection accuracy are **not measurable**. This is a label verification gate, not zero performance. The run's record counts are captured in `results.json` for audit only; they are not accuracy. Requirement metrics have no verified expected requirement records. No confidence intervals or statistical significance are claimed.

## Failure taxonomy and examples

No correctness failures can be established without verified expected labels. Therefore `failures.json` contains no asserted analyzer failures. The observed evaluation blocker is **HUMAN_REVIEW_REQUIRED / missing source corpus**, not an analyzer defect. No OCR, article numbering, annex, requirement, table, or page-attribution failure examples are asserted from unverified sidecars.

## What works and what remains unknown

The CLI accepts the stored DocumentResult, emits a structured prediction, and enforces the human-verification gate rather than scoring pending labels. This confirms execution and guard behavior only. The run does not establish whether the analyzer reliably detects sections, articles, annexes, requirements, BOQ, or page provenance. Missing PDFs also prevent scanned-document evaluation and dossier grouping.

## V2 and completion recommendations

1. Restore Agent 6's 25 unique raw seed PDFs (including the scanned examples) without modifying them; verify hashes and deduplicate by SHA-256.
2. Review document contents and source provenance, then curate role/evidence, dossier membership, organization, language, modality, and procurement type. Keep notices separate from specifications.
3. Select 5–8 genuinely diverse CDC-oriented documents and manually verify a manageable set of sections, articles, annexes, requirement facts, and BOQ pages against physical pages.
4. Re-run the frozen PDF → Document Intelligence → CDC Analyzer pipeline without code changes; retain raw outputs and score category-specific exact and detection metrics only after the verification gate passes.
5. Record root-cause examples with page and raw evidence. Only then use this development corpus to guide V2; acquire new documents for a held-out final evaluation.

The corpus is explicitly a **development corpus**. After failure-driven iteration it must never be described as an unseen final test set or representative of all Tunisian tenders.

## Checks

- CDC Analyzer tests: 28 passed.
- Full project suite: 214 passed, 2 skipped, 2 failed. Both failures are `tests/document_intelligence/test_recognizer.py::test_tesseract_fallback_maps_geometry_or_reports_missing` variants; the environment lacks the `pytesseract` Python package. No test was changed to mask this environment issue.
- `git diff --check`: clean before staging; staged diff check repeated before commit.
- Source PDFs are not added or modified by this change. The only PDF inspected was read-only.
