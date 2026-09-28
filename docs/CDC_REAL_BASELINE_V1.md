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
- Prediction: generated locally at `benchmarks/cdc_real_v1/predictions/MM_Cahier-des-charges-type-Entretien.prediction.json`; large prediction files are not committed in the release tree.
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

## LOCAL CORPUS BASELINE — continuation on `agent/cdc-benchmark`

This section supersedes the old availability blocker for the continued run above. The earlier one-document consumer-only pilot remains preserved in the history above; the figures below are from the user-provided local corpus and a new PDF-to-Document Intelligence-to-Analyzer run. Raw files remain outside the repository.

### Inventory, reconciliation, and curation

Recursive inventory found 26 PDF files: all 26 are valid, representing 25 unique SHA-256 hashes, with one exact duplicate and no invalid PDFs. All 25 unique hashes match Agent 6's seed inventory; there are zero new local unique documents and zero missing seed hashes. Classification was based on source content and reviewed evidence, not Agent 6's role hints. Curation counts over 25 unique documents: DAO 14, NOTICE 5, CDC 3, OTHER 1, UNKNOWN 2; CCAP, CCTP, REGLEMENT, BOQ, DEVIS_ESTIMATIF, SOUMISSION, and ANNEX do not occur as primary curated document roles. Some DAO PDFs contain annexes and BOQ content. These roles are mutually exclusive primary document labels, not an inventory of embedded components.

The inventory profiles are 20 native-text PDFs, 4 scanned PDFs, and 1 mixed PDF. Language counts: French 11, bilingual 10, Arabic 2, unknown 2. Issuing-organization evidence is concentrated: Presidency of the Government 20, Al Karama Holding 1, Ministry of Communication Technologies 1, unknown 2, and one template with no issuing organization asserted. One cross-file group is evidenced: `DOSSIER-10-2025` contains the standalone CDC and a composite notice-plus-CDC DAO for tender 10/2025. Other dossier links remain null unless source evidence supports them. See `benchmarks/cdc_real_v1/corpus_manifest.csv` and `reconciliation.json` for file-level audit fields and counts.

### Pilot, frozen pipeline, and annotation coverage

Seven documents were selected: CDC-DEV-001, 006, 007, 009, 011, 017, and 022. They cover 18–51 pages, French/Arabic/bilingual content, native and scanned inputs, works/goods/IT/services, and generic template plus live-dossier structures. Organization diversity is limited; five selected documents are from the Presidency of the Government, one is from the Ministry of Communication Technologies, and the reusable template has no asserted issuer. Six selected documents have VERIFIED source-grounded annotations; CDC-DEV-009 has useful cover/scan notes but remains DRAFT and is excluded from scoring. The seven selected documents provide 26 source-verified requirement examples, 19 selected article-heading examples, three complete major-section inventories, three complete annex inventories (27 annexes), and three verified BOQ-positive documents. Article and requirement annotations are samples, not exhaustive inventories. Each fact includes source text and 1-based physical page evidence.

The frozen baseline is tested commit `cc6e4566d62954f0bc4d0820f833dbd39e9b5994`, Document Intelligence contract `1.0`, and `CDC_ANALYZER_BASELINE_V1`. The production analyzer was not changed. Native inputs were run with `DocumentProcessor(mode=auto,use_cache=False,allow_fallback=True)`. The scanned CDC-DEV-009 was processed end-to-end through the existing Document Intelligence pipeline for all 37 pages (37 OCR pages, 0 fallback pages, 1,192 evidence elements); that fresh `DocumentResult` from the full source-PDF run was then passed into the Analyzer. Its evidence source was PaddleOCR. Other pilot documents used native PDF text only, except CDC-DEV-007 and CDC-DEV-017, which include PaddleOCR evidence on one page each. No old sidecar was used as a substitute for PDF processing. Per-document evidence sources, prediction metadata, and run metadata are in `results.json`; full predictions and local ignored `document_results/` can be regenerated locally.

| Document | Pages / OCR pages | Predicted sections / top-level articles / annexes / requirements | Label status |
|---|---:|---:|---|
| CDC-DEV-001 | 30 / 0 | 5 / 0 / 6 / 62 | VERIFIED |
| CDC-DEV-006 | 51 / 0 | 3 / 0 / 0 / 0 | VERIFIED |
| CDC-DEV-007 | 48 / 1 | 2 / 22 / 14 / 87 | VERIFIED |
| CDC-DEV-009 | 37 / 37 | 0 / 0 / 0 / 5 | DRAFT; not scored |
| CDC-DEV-011 | 21 / 0 | 0 / 0 / 0 / 6 | VERIFIED |
| CDC-DEV-017 | 30 / 1 | 0 / 24 / 7 / 45 | VERIFIED |
| CDC-DEV-022 | 18 / 0 | 0 / 0 / 0 / 1 | VERIFIED |

### Baseline scores

These are category-specific subset measurements, not an overall accuracy score. Section and annex precision/recall use complete manually reviewed inventories only (sections: three documents; annexes: three documents). Article labels are selected positives, so article precision/recall are **not measurable**; the source-verified example hit rate is 12/19 (63.2%). Requirement labels are also positive examples, so precision and exhaustive recall are **not measurable**; 14/26 reviewed facts were matched (53.8% sample hit rate). Of the 14 matched facts, 5 normalized values were correct (35.7%) and all 14 predicted physical-page attributions matched source pages (100%). BOQ presence was found for all three verified BOQ-positive documents (3/3); the prediction page ranges overlapped source pages in all three (3/3). This small positive-only sample does not estimate BOQ specificity.

| Metric | Result | Scope |
|---|---:|---|
| Section precision / recall | 71.4% / 55.6% (TP 5, FP 2, FN 4) | 3 complete section inventories |
| Article precision / recall | Not measurable | Selected positive examples only |
| Article heading sample hit rate | 63.2% (12/19) | 6 source-reviewed documents |
| Annex precision / recall | 100% / 100% (TP 27, FP 0, FN 0) | 3 complete annex inventories |
| Requirement precision / exhaustive recall | Not measurable | Positive facts only |
| Requirement fact sample hit rate | 53.8% (14/26) | 6 verified documents |
| Normalized-value correctness | 35.7% (5/14) | Matched fact examples with a value comparison |
| Physical-page provenance | 100% (14/14) | Matched fact examples |
| BOQ presence / page detection | 100% / 100% (3/3 / 3/3) | Verified BOQ-positive docs; page metric is overlap |
| Scanned-document accuracy | Not measurable | 1 processed scan, labels DRAFT |

Per-document TP/FP/FN and sample-level results are captured in `results.json`; the canonical aggregate is `metrics.json`. A prediction count is not a score. Null metrics mean unavailable due annotation scope, not zero analyzer performance.

### Failure evidence and V2 decision

The source-linked cases in `failures.json` identify two repeated signals: Arabic `الفصل` article headings were absent from predictions in three source-reviewed documents (006, 011, 022), and top-level `Partie I/II` boundaries were missed or replaced by lot headings in two complete section inventories (007 and 017). These are repeated in this sample, not proof of corpus-wide systematic behavior. The 37-page scanned Arabic document also produced no sections/articles after OCR, but remains an unscored investigation lead because its labels are DRAFT. **Decision gate: YES, there is enough verified failure evidence to design a targeted CDC Analyzer V2 investigation.** Five selected documents are real tender dossiers with verified source annotations and end-to-end predictions; the reusable CDC template provides a sixth verified structure. The repeated, page-grounded Arabic article-heading failures across three tender documents and the two section-boundary failures provide concrete engineering targets. This is a design signal only: article/requirement labels are samples, only three documents have complete major-section/annex inventories, and scanned structure labels remain draft. Do not use these partial scores as broad V2 acceptance criteria; expand structural annotation and use a separate held-out corpus for final evaluation. The development corpus must not later be represented as an unseen V2 test set.

### OCR dependency and verification

`pytesseract==0.3.13` is pinned in `requirements.txt`, so it is a required Python project dependency for the Tesseract fallback path. The fallback also requires the external Tesseract executable and language data. The project virtual environment imports pytesseract 0.3.13 and the Tesseract executable is installed; the module's default executable lookup is `tesseract`, so the test environment PATH must expose that executable. No OCR production behavior or skip policy was changed for this baseline.

Raw PDFs from `CDC_DEVELOPMENT_CORPUS_V1` and generated prediction payloads are not in the release tree. The separate pre-existing backend reference PDF remains versioned for regression tests. `document_results/` and `predictions/` are ignored local outputs; tracked benchmark artifacts are hashes, relative filenames, reviewed metadata/evidence, compact metrics/results, and reports. The source corpus may guide future V2 development, but a newly acquired held-out corpus is required for final evaluation.

Continuation verification: benchmark artifact tests **4 passed**; CDC Analyzer tests **28 passed**; Document Intelligence tests **42 passed, 1 skipped**; full project suite **221 passed, 1 skipped**. The full suite emitted one upstream Starlette deprecation warning. `pytesseract` 0.3.13 imported from the project virtual environment; the Tesseract executable was added to PATH for these runs. No OCR-related test failed or was changed. `git diff --check` was run before commit.
