# Document Intelligence — producer contract

Public contract version: **1.0**, exported as
`document_intelligence_contract_version`. The existing wire shape is unchanged.
See [the consumer guide](DOCUMENT_INTELLIGENCE_CONSUMER_GUIDE.md) for the frozen
schema, shared integration specimen, identity rules and consumer obligations.

This is the domain-neutral, local evidence producer. It supports multi-page PDF
and multi-frame images. The newer OCR-owner request supersedes the initial BOQ
audit's proposed single-page processor. Any single-page BOQ restriction belongs
in its consumer. The historical invoice UI/API remains unchanged.

## Setup: Windows x64, Python 3.11.9

Do not activate the copied virtual environment. During migration it was moved
to `.cache/environment-before-document-intelligence` for reference only, and
`.venv` was created afresh. Never execute that archived environment.

From this repository, when `.venv` does not already exist:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip check
$env:PADDLE_PDX_CACHE_HOME = Join-Path (Get-Location) '.cache/paddlex'
python scripts/smoke_document_ocr.py --compare
```

`requirements.txt` pins the core packages; `constraints-ocr-baseline.txt` pins
transitive packages recovered from baseline metadata. For the complete tested
Windows development environment use `python -m pip install -r
requirements-lock-win-py311.txt` instead. Python itself is not installed by pip.
The lock is for Windows/Python 3.11; Linux/Docker installation was not verified.
Do not install multiple OpenCV wheel distributions into one environment: PaddleX
uses `opencv-contrib-python`, which provides the existing `cv2` import.

If the shell intentionally sets `PIP_NO_INDEX=1`, use an approved local wheelhouse
or enable the package index for the installation. Do not confuse an offline
resolver failure with an unavailable PaddleOCR release.

Models: keep `optimized_mobile_v4`, `PP-OCRv4_mobile_det` and
`en_PP-OCRv4_mobile_rec`, CPU threads 4, MKLDNN off, existing preprocessing profile
`current`, input max side 1600. Existing model initialization may fetch those
weights on first use. For offline provisioning place the verified model folders
under `$env:PADDLE_PDX_CACHE_HOME/official_models/`. The migration reused local
weights; `ocr_model_manifest.json` records their SHA-256 hashes. Package and model
versions both matter. No document content is sent to an external inference API.

Optional Tesseract fallback also requires the Tesseract executable on PATH with
`fra` and `eng` trained data. The real Paddle smoke test disables fallback; its
success cannot be satisfied by Tesseract. Tesseract executable provisioning is
separate from installing `pytesseract`.

## Python and CLI usage

```python
from app.document_intelligence import DocumentProcessor

result = DocumentProcessor().process("document.pdf")
payload = result.model_dump(mode="json")

# Uncached evidence, with failures surfaced instead of Tesseract fallback:
result = DocumentProcessor(mode="ocr", use_cache=False, allow_fallback=False).process("scan.png")
```

```powershell
python scripts/process_document.py document.pdf --mode auto --no-cache --output outputs/document.json
$env:RUN_REAL_OCR = '1'
python -m pytest tests/document_intelligence -q
Remove-Item Env:RUN_REAL_OCR
```

Without `RUN_REAL_OCR=1`, the one real integration test is explicitly skipped.
The smoke script creates an ASCII controlled **synthetic** price-table fixture,
then performs real inference. `--compare` compares text/confidence with the
legacy recognizer and writes generic evidence to `outputs/document-intelligence-smoke`.
This is an environment/contract test, not a BOQ extraction benchmark.

## Architecture

```text
DocumentProcessor.process(path)
  -> load/hash input; iterate physical pages
  -> native word evidence + explicit per-page path decision
  -> render only pages requiring OCR
  -> OCRRecognizer + FullPageRegionPolicy
     -> existing model initialization / prediction / Paddle result adapters
     -> existing preprocessing with its affine transform exposed
     -> optional Tesseract data fallback
  -> deterministic reading order + generic alignment evidence
  -> DocumentResult (Pydantic, JSON serializable)
```

The generic path never calls the legacy invoice pipeline, document classifier,
party resolver, family-specific regional retries, field candidates, validators or
ERP mappers. Legacy `OCREngine` defaults to `InvoiceRegionPolicy`, retaining its
existing full-page/region behavior. `FullPageRegionPolicy` has no fixed supplier,
totals, customs or table zones. The generic recognizer reuses the low-level
Paddle adapters rather than replacing the recognizer. These are currently
private helpers in `ocr_engine.py`; this small compatibility boundary is tested.

## Per-page selection

| Mode | Behavior |
|---|---|
| `auto` | Use native words when at least 12 non-whitespace text characters exist, at least 95% are printable/non-replacement, and every box has positive area. Otherwise OCR this page. |
| `native` | Native words only; an empty/unusable page stays present with a diagnostic. Image input is rejected. |
| `ocr` | Raster recognition only; do not concatenate native words. |
| `hybrid` | Preserve native and OCR evidence separately, with distinct IDs and sources. No fusion or cross-source deduplication; emit `hybrid_unmerged_evidence`. |

The rule is a heuristic, not a quality classifier. Sparse valid native pages may
be OCRed. A readable title above a scanned body or a stale hidden OCR text layer
can make `auto` choose native evidence prematurely. Select `ocr` or `hybrid` for
these documents. Empty pages retain their physical 1-based page number.

## Evidence contract

`DocumentResult` contains a SHA-256 content `document_id`, `source_type` (`pdf` or
`image`), mode, pages and document diagnostics. It has no business fields.

Each page contains physical `page_number`, rendered `width`/`height`, elements,
geometry, diagnostics, and PDF transform/rotation where applicable. Each element
extends the existing `OCRLine`, reusing `BoundingBox`:

- `id`: deterministic page-local identifier, unique within the result; unchanged
  for the same source path/algorithm/configuration. Combine with `document_id` for
  cross-document identity. These are not promises of stable IDs across algorithm changes.
- `text`: source adapter text, not business-normalized or parsed; repeated text
  is retained, including identical evidence on different pages.
- `bbox`, `page_number`, page dimensions and `coordinate_space`.
- `source`: `native_pdf`, `paddleocr` or `tesseract`.
- `confidence`: original recognizer value when available; native text is null.
  Existing Tesseract helper averages available word confidences per line. No
  confidence is generated from arithmetic, semantics or layout.
- `source_bbox`, `source_coordinate_space`, `source_to_page`: original engine
  geometry and the transform used to produce the public box.
- `native_order`: PyMuPDF block/line/word IDs for native words; OCR keeps its
  original `line_index`. Element array order is deterministic page/y/x order.

Native elements are words; Paddle/Tesseract elements are usually recognized
lines. Consumers can use `native_order` or geometry row membership to reconstruct
lines, preserving source IDs. No font-based heading classification is provided.

## Coordinate contract

All public `bbox` values use **rendered_page_pixels**, top-left origin, x right,
y down, matching page width/height. They are not normalized 0–1 coordinates.

| Source | Original box space | Conversion |
|---|---|---|
| Native PDF | `pdf_unrotated_points`, PyMuPDF's unrotated crop-relative coordinates, 72 points/inch | Page rotation matrix, render scale (default 2), then raster-origin offset. Stored as `pdf_to_page` and per-element `source_to_page`. |
| OCR | `ocr_inference_pixels`, after resizing/deskew | Inverse of the exact preprocessing affine matrix; source/rendered image pixels are the target. |
| Image input | Original decoded frame dimensions | Same inverse preprocessing mapping; no PDF points. |

Transforms are 3×3 matrices multiplying homogeneous **column vectors** `[x,y,1]`.
Transform all four box corners; the public box is their axis-aligned envelope.
For rotated boxes the envelope is not perfectly invertible; preserve the source
box/matrix for accurate polygons. Boxes are not clipped after inverse deskew:
consumers may intersect them with the page for display without changing evidence.
PDF rotation/crop mappings are tested against rendered ink at 0/90/180/270°.
Image EXIF orientation is not applied automatically: coordinates refer to the
decoded frame, so previews must use the same orientation.

`preprocess_image_with_transform` executes the existing operations and parameters;
it also exposes resize/deskew transforms. The legacy `preprocess_image` returns
the same pixels. Unknown boxes remain null with `missing_geometry`, never a
fabricated rectangle. Tesseract data boxes are mapped from inference pixels;
its text-only fallback has no box and no invented confidence.

## Generic geometry

`page.geometry` exposes visual rows, element-level cell candidates, repeated-left-
edge column groups and an aligned region candidate. Every group contains a bbox
and source element IDs. Row boxes/IDs serve as row anchors; original elements are
the fragments. This is conservative generic evidence, not a semantic table
reconstruction. A cell candidate may be a word or an OCR line, not a true table
cell. Alignment can include ordinary prose. No headers are guessed and no
invoice `LineItem` is produced. Existing richer invoice table structures remain
untouched for legacy consumers. Table/header semantics must not be inferred merely
from the presence of a geometric group.

## Diagnostics, timing and cache

Page diagnostics: native availability/usability, selected path, OCR/fallback used,
missing geometry count, cache hit, warnings and processing milliseconds. Document
diagnostics aggregate OCR/fallback pages, geometry loss, cache configuration and
`PipelineTimer` stages: load, render, native extraction, preprocessing, OCR,
layout, total. Model initialization is included in OCR. A cached OCR call has
preprocessing/cache overhead but no fresh inference stage; missing stages are zero.
Stage measurements are nested and should not be added to total a second time.

Generic OCR evidence uses a separate `.cache/document_intelligence` namespace and
schema. Identity includes source/processed image hashes, shape, physical page,
OCR package versions, model/configuration names, preprocessing version/profile
and relevant OCR parameters. It never reads invoice cache entries. A model file
replacement under the same name requires cache invalidation; compare the recorded
model manifest. No failed-Paddle/fallback result is cached. `use_cache=False`
disables evidence reads and writes, including in-memory result caching; loaded
recognizer weights may still be reused. Corrupt/incompatible cache files are misses.

Local documents stay local. The library accepts a local path deliberately; it is
not an HTTP upload endpoint. Consumers must authorize/sanitize paths themselves.
Defaults limit input to 100 MiB, 500 pages/frames and 40 million pixels per page.
PDF encrypted input is rejected. Pages are processed sequentially, without
retaining all raster images in the result. Evidence JSON/cache still contains
document text: manage retention and access to these local files. No public
preview or invoice persistence is invoked.

## Limits

No business extraction, semantic headings, automatic document family routing,
merged-cell model, table accuracy claim, LLM, RAG or training. Geometry grouping
is quadratic in dense pages and not a multi-column reading-order model. Hybrid
evidence is intentionally unmerged. The strict generic fallback propagates
unrecoverable engine errors rather than returning fabricated success. Thread-safe
parallel inference on the shared Paddle instance is not established; process
sequentially. See the migration report for actual test counts and remaining
legacy failures.
