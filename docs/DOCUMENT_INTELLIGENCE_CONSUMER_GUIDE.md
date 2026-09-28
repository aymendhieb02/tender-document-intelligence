# Document Intelligence consumer guide — contract 1.0

The public types are `DocumentResult`, `PageResult`, `EvidenceElement` and
`GeometryGroup` in `app.document_intelligence.schemas`. The public version is:

```python
from app.document_intelligence import document_intelligence_contract_version
assert document_intelligence_contract_version == "1.0"
```

Version 1.0 freezes the existing payload shape. The version is an exported constant,
**not a new field in DocumentResult**. Persist it alongside serialized evidence,
for example in consumer job metadata. The cache schema version is unrelated.
Changing names, null semantics, coordinates, identity rules or source vocabulary
requires an explicit compatibility review and contract-version decision. Do not
regenerate the frozen schema/fixture just to make a failing test pass.

## Read and reference evidence

```python
from pathlib import Path
from app.document_intelligence.schemas import DocumentResult

fixture = Path("tests/document_intelligence/fixtures/document_result_v1.json")
document = DocumentResult.model_validate_json(fixture.read_text(encoding="utf-8"))
for page in document.pages:
    elements_by_id = {element.id: element for element in page.elements}
    for visual_row in page.geometry.rows:
        original_elements = [elements_by_id[key] for key in visual_row.element_ids]
        source_reference = (document.document_id, page.page_number, visual_row.element_ids)
```

Use the model or its `model_dump(mode="json")` output. Do not import OCR engines,
cache helpers, preprocessing functions, region policies, or private methods in
consumer adapters. Retain the document ID when passing a single page downstream.

| Public evidence | Required interpretation |
|---|---|
| `document_id` | Real producer outputs use SHA-256 of input bytes. Combine it with physical page and element ID for durable source references. |
| `pages[].page_number` | Physical, 1-based, ascending; empty pages remain present. It is not a printed page label or native line ordinal. |
| `element.id` | Opaque source identifier. Preserve it; do not replace it with a consumer row ID, text hash, array position, or article number. Repeated text has distinct IDs. |
| `GeometryGroup.element_ids` | References to elements on **that same page**, not OCR line numbers. Resolve by ID; never use as array indices. |
| `GeometryGroup.id` | Page-local derived group ID. `row-0` can occur on every page and is not an element/source ID. |
| `bbox` | Nullable object `{x1, y1, x2, y2}` using top-left/bottom-right coordinates. Not `[x,y,width,height]`, PDF points or normalized fractions. Missing means unknown, not zero. |
| `page.geometry.rows` | Visual y-overlap groups, with left-to-right member IDs. There is no `visual_rows` field. A group can span unrelated columns; it is not a semantic sentence, heading or business row. |
| `page.geometry.cells` | One candidate per positioned element. Native words and OCR lines have different granularity; these are not guaranteed table cells. |
| `page.geometry.columns` | Repeated left-edge alignment groups. No semantic names, column-role order or quantity/price mapping is promised. Infer roles in the consumer using its supported layout/header rules. |
| `page.geometry.regions` | Alignment candidates, not confirmed tables. Do not promote ordinary text alignment to a semantic table automatically. |
| `source` | Exactly `native_pdf`, `paddleocr`, or `tesseract`; describes provenance, not document family or field correctness. |
| `confidence` | Nullable recognizer evidence, with native text always null. OCR zero is a real value, not missing. Preserve it; do not turn native/null into 1.0. Tesseract may expose an average over line words. Not arithmetic validity or calibrated extraction accuracy. |
| `coordinate_space` | Public element/page/geometry boxes use `rendered_page_pixels`, top-left origin, x right/y down, matching page width/height. |

Native evidence is word-level; OCR evidence is typically line-level. `text` is
original adapter evidence, not a domain-normalized value. `native_order` retains
PDF block/line/word positions; `line_index` retains the source index. Array order
is geometric (y then x, missing boxes last, ID tie-break), not semantic reading
order for multi-column text. Do not infer identity from that order.

Current built-in ID spellings are `pN-native-000000` / `pN-ocr-000000`, using
source extraction indices before reading-order sorting. Consumers must not parse
them. They are deterministic for identical input, settings and engine evidence;
they are not promised stable across model/configuration changes. Blank filtered
items can leave index gaps. Fallback OCR shares the `ocr` ID namespace and its
`source` value distinguishes the engine. Injected recognizers must supply valid
unique IDs themselves. Group IDs are not globally unique.

## Coordinates and derived consumer values

The public box is already mapped to the rendered page. **Do not apply
`source_to_page` to `bbox` again.** The transform maps `source_bbox` only:

- Native `source_bbox`: `pdf_unrotated_points`, crop-relative PyMuPDF coordinates.
- OCR `source_bbox`: `ocr_inference_pixels`, after resize/deskew.
- `source_to_page`: 3×3 affine matrix multiplying column vectors `[x,y,1]`.
  Transform all four corners; the public bbox is their axis-aligned envelope.

Page `pdf_to_page` maps PDF coordinates, not OCR coordinates. For a resized UI
preview, apply a separate display scale to public page pixels. Inverse deskew
boxes may extend beyond the raster; clip only for display, retaining evidence.

CDC: a derived line/heading may have its own consumer ID, but retain every
original source ID and text part separately. A singleton must still cite its
original element. Join a visual row only after checking the consumer's column/
layout context. Do not replace word-level provenance with the row-group ID.

BOQ: map original positioned evidence into business columns using a verified
template/header mapping. If using relative x, compute it from public bbox and
the matching page width, e.g. `(x1+x2)/(2*page.width)`. Preserve all contributing
source IDs, raw text, page, boxes and individual confidences for each value.
Consumer aggregates must be labeled as such; an aggregate is not an original OCR
score. Missing or uncertain values must remain reviewable. The producer does not
promise semantic columns or validate arithmetic.

Hybrid mode retains both sources without fusion, with distinct IDs. Consumers
must explicitly choose or reconcile evidence; do not sum or concatenate duplicates
blindly. No heading levels, business fields or confidence calibration are implied.

## Shared typed fixture and guard tests

- `tests/document_intelligence/fixtures/document_result_v1.json`: a direct
  `DocumentResult` specimen with one native page and one OCR page, repeated text,
  two columns, visual groups, source boxes/transforms, null/zero confidence and
  one unpositioned element.
- `document_result_v1.meta.json`: version and synthetic provenance. Its ID is a
  digest of a specimen label; timings/scores are controlled values, not measured
  OCR output or ground truth.
- `document_result_v1.schema.json`: frozen Pydantic JSON Schema of the public
  payload, including existing inherited `OCRLine` fields and nullability.
- `tests/document_intelligence/test_contract_v1.py`: wire-schema snapshot,
  fixture round-trip, identity/reference, coordinate, confidence and real producer
  boundary tests. No model downloads are needed for these contract tests.

The current Pydantic schema is structurally permissive in some places: parsing
alone does not prove page continuity, unique IDs, matrix shape or semantic
consistency. The producer guarantees are guarded by tests; foreign/injected data
must respect them. No new runtime validators were added during stabilization.

See [compatibility report](DOCUMENT_INTELLIGENCE_COMPATIBILITY_REPORT.md) for
the four consumer diagnoses and recorded verification results, and
[producer documentation](DOCUMENT_INTELLIGENCE.md) for modes and operational limits.
