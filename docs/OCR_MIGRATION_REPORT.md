# OCR migration report

Date: 2026-09-28. Scope: generic Document Intelligence only.

## Baseline and environment

Read `BOQ_REFACTOR_AUDIT.md` completely before implementation. The historical
repository/tag was not modified. The revised request explicitly requires a
multi-page producer; no BOQ single-page restriction was added to OCR.

The copied `.venv` was archived inside this copy at
`.cache/environment-before-document-intelligence`; its metadata was read without
executing its interpreter. Fresh `.venv/pyvenv.cfg` points to this repository and
system Python 3.11.9, with system-site-packages disabled.

Verified installed versions:

| Component | Version |
|---|---|
| Python | 3.11.9, Windows x64 |
| PaddleOCR / PaddlePaddle / PaddleX | 3.7.0 / 3.3.1 / 3.7.1 |
| OpenCV distribution | opencv-contrib-python 4.10.0.84 |
| NumPy | 2.3.5 |
| PyMuPDF | 1.27.2.3 |
| Pillow / pytesseract | 12.2.0 / 0.3.13 |
| FastAPI / Pydantic / pydantic-settings | 0.137.2 / 2.13.4 / 2.14.2 |

The initial pip invocation was blocked by `PIP_NO_INDEX=1`, not by missing wheel
compatibility. Index-enabled installation succeeded. Baseline transitive
constraints were then applied and incidental packages from the unconstrained
first resolution removed. `pip check` passed. Only one `cv2` wheel is installed;
the copied environment had competing OpenCV distributions. The complete tested
development set is in `requirements-lock-win-py311.txt`. Requirements include
the baseline constraints; Docker COPY statements include that file, but Docker
and non-Windows reproduction have not been tested. No Torch/Table Transformer/
DocLayout model was installed for this task.

## Real OCR evidence (not mocked)

`scripts/smoke_document_ocr.py` generates a synthetic native PDF and rendered image:
`BORDEREAU DES PRIX`, header text, and `001 / Test article / 10 / 25,500`.
Using the existing model initializer/predictor, `OCREngine(mode="fast",
use_disk_cache=False)._run_paddle` returned **9 elements**, all with text,
positive boxes, confidence and page 1. No fallback was possible in that call.
The fixture is ASCII by design and does not measure accented-language accuracy.

The generic producer subsequently returned the **same nine texts and confidence
values exactly** on this image, while adding dimensions, explicit source and
coordinate transformations. It preserves OCR errors rather than correcting
them: the recognizer adds punctuation in `Prix Unitaire.` and `Test article.`.
This is evidence of working inference and behavior preservation, not perfect OCR.

The real integration test also built an actual image-only PDF page between native
pages. It selected native/OCR/native and attributed scanned-page evidence to page
2. Models were existing local PP-OCRv4 weights, copied into the project's ignored
PaddleX cache; model hashes are recorded in `ocr_model_manifest.json`. No cached
OCR evidence was accepted by these tests.

Commands:

```powershell
$env:PADDLE_PDX_CACHE_HOME = Join-Path (Get-Location) '.cache/paddlex'
python scripts/smoke_document_ocr.py --compare
$env:RUN_REAL_OCR = '1'
python -m pytest tests/document_intelligence -q
```

## Changes and evidence for them

| Change | Reproducible reason | Verification |
|---|---|---|
| Add multipage `DocumentProcessor` | Old loader flattened native text and OCRed all rendered pages | Native/scan/mixed fixtures, empty pages, mode tests, physical attribution |
| Separate `FullPageRegionPolicy` / legacy `InvoiceRegionPolicy` | Old regions included parties/totals/customs | Generic policy test fails if invoice region builder is called; legacy modes retain original selection |
| Expose preprocessing affine transform | Old box remapper handled resize/offset but not the existing deskew rotation | Forced 5° deskew test, affine corner tests, real PDF rotated/cropped ink checks |
| Map fallback geometry | Existing Tesseract data path already returns word-union boxes, but old orchestration leaves them in processed-image coordinates | Actual data-helper fixture plus generic fallback coordinate test; text-only path remains null |
| Preserve repeated evidence | Legacy text-only deduplication could collapse repeated text, including across pages | Two same-text OCR boxes remain separate; repeated pages remain separate |
| Isolate generic cache | Invoice cache/configuration must not contaminate new evidence | Separate schema/namespace; content/page/version invalidation; corrupt-cache and disabled-cache tests |

No recognizer model, thresholds, confidence arithmetic or preprocessing image
parameters were changed. Before modifying the preprocessing wrapper, SHA-256
hashes were recorded for 3 images × 5 profiles. After exposing the transform,
**15/15 image outputs were byte-identical**. Existing `deskew` and
`preprocess_image` signatures remain compatible. The mathematical addition is
metadata; the existing image operations execute unchanged.

The initial audit's fallback statement was incomplete: `_build_tesseract_line`
alone has no bbox, but `_tesseract_data_lines` already uses the bbox-preserving
wrapper. The new work reuses that adapter and fixes its coordinate interpretation
only in the generic layer. The legacy invoice fallback behavior is unchanged.

## Validation record

- Historical audit/system interpreter: **568 passed, 12 failed, 1 skipped**.
- Fresh pinned environment, before generic code changes: **569 passed, 12 failed**.
  One previously skipped environment-dependent test became available. The same
  twelve legacy failure IDs remained.
- Initial generic suite including real Paddle integration: **31 passed** (before
  two additional geometry/fallback tests were added).
- Current deterministic generic suite: **32 passed, 1 explicitly skipped real test**.
- Final isolated producer run with real OCR: **33 passed, 1 Paddle parameter
  warning in 13.31 seconds**.
- Final repository-wide run, real OCR enabled and a fresh bytecode-cache prefix:
  **636 passed, 16 failed, 2 warnings in 39.37 seconds**. All **33 producer tests**
  passed, including real Paddle. The failures comprise the same 12 legacy IDs
  and 4 concurrent consumer failures, listed below. This is not a green full-suite claim.

Concurrent consumer failures observed in that snapshot:

- `tests/boq/test_specialized_boq.py::test_filled_rows_decimal_validation_and_provenance`
- `tests/boq/test_specialized_boq.py::test_missing_cell_is_not_fabricated_and_arithmetic_error_is_detected`
- `tests/boq/test_specialized_boq.py::test_ocr_aliases_and_shifted_geometry`
- `tests/cdc_analysis/test_analysis.py::test_real_producer_schema_adapter_without_running_ocr`

The BOQ assertions concern numeric-column assignment; the CDC assertion concerns
consumer replacement of a source element ID. They were inspected for producer
contract impact but their code/tests were not edited. These files were still
being developed independently during verification.

The CLI native extraction smoke produced 1 page/13 native word elements. Final
`pip check` reported no broken requirements and `git diff --check` passed.
`ocr_smoke_evidence.json` retains the synthetic recognition comparison and
component versions. The final full run used:

```powershell
$env:PADDLE_PDX_CACHE_HOME = Join-Path (Get-Location) '.cache/paddlex'
$env:RUN_REAL_OCR = '1'
$env:PYTHONPYCACHEPREFIX = Join-Path (Get-Location) '.cache/document-intelligence-pycache'
python -m pytest -q -p no:cacheprovider --tb=short
```

Legacy failure groups remain: 4 document-layout text fallbacks, 1 exact README
disclaimer expectation, 1 party-comparison None/False expectation, 1 geometric
table reconstruction, 2 graph candidate provenance assertions, 1 text-only table
reconstruction, and 2 optional Table Transformer tests requiring Torch. No
unrelated invoice tests were repaired, suppressed or rewritten.

Other agents added CDC/BOQ files while this task ran. They are outside this task's
ownership; aggregate repository counts may include their tests. The producer
test directory and legacy failure-ID comparison are the attribution boundaries.

## Remaining limitations

Auto native selection is a transparent heuristic, not a page coverage/hidden-text
quality detector. Hybrid retains both sources without fusion. Native evidence is
word-level, OCR typically line-level. Table geometry is candidate alignment only:
headers/merged cells and business rows are not inferred. No tender/BOQ accuracy
is claimed. Real Tesseract executable inference and non-Windows installation were
not measured; fallback geometry is verified with deterministic data-adapter tests.
See `DOCUMENT_INTELLIGENCE.md` for coordinates, limits, timing, cache controls and
consumer examples.
