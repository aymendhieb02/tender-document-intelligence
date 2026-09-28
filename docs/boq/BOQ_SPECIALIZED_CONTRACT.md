# Specialized BOQ extractor contract

This contract freezes the output and behavior of `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1` only. It does not specify a general BOQ API, semantic table reconstruction, routing policy, or OCR implementation.

## Input boundary

The public entry point `extract_male_municipal_from_document(document, page_number=...)` accepts the frozen Document Intelligence Contract 1.0 `DocumentResult`, selects exactly one requested `PageResult`, and reads its public `EvidenceElement` values. A missing or duplicate page number raises `ValueError`. The BOQ package does not read OCR-engine internals. `extract_male_municipal_v1` also accepts a single public `PageResult` when the caller already selected the page.

Evidence is carried forward from each source element: page number, bounding box, raw text, confidence, source label, and element ID. Document ID is passed from `DocumentResult`. Coordinates are the coordinates supplied by the public page evidence; this specialized extractor does not reinterpret source transforms.

## Family scope and detection

The only supported family is the Male municipal maintenance schedule described in `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1`. Detection requires all five independent anchor groups: Annex 05, the price schedule title, estimated quotation, HTVA price, and TTC price. Family-only OCR header normalization handles the known `H7VA`/`HTVA` and `TotaI`/`Total` confusions. Generic header normalization remains limited to Unicode accent, case, and punctuation normalization. Detector results retain score, found/missing anchors, and matching evidence on `BOQDocument.detection`.

Nonmatching pages return `detected=false` and no rows. Page routing and multi-page document decisions are outside this contract.

## Output semantics

- `BOQDocument` contains family/version identity, metadata fields, currency, measured table bounds, the fixed column mapping, five row slots when the family matches, totals, checks, source evidence, review status, detector diagnostics, and extraction diagnostics.
- Each `BOQRow` represents one measured article band. Its fields are `ParsedValue` instances. Quantities and monetary values use `Decimal`; ambiguous or invalid strings remain unnormalized and are reported for review.
- `SourceEvidence` retains observed text and source provenance. The aggregate source bbox encloses the contributing elements; confidence is the minimum available confidence for those elements.
- UOM is left `MISSING`: the phrase “L’unité : … DT” in the reference has unverified semantics and is preserved as ancillary evidence instead of being assigned to a unit cell.
- Arithmetic checks are `VALID`, `INVALID`, or `NOT_CHECKABLE`; missing inputs are never treated as zero. `review_status` reflects these results.

## Value origin

`ParsedValue.value_origin` distinguishes how a value entered the result:

- `OBSERVED`: raw text came from supplied evidence, including text that could not be parsed or a visible placeholder.
- `TEMPLATE_INFERRED`: the blank verified template provides a structural article slot, but no article label was observed. Such a value has no raw text and no evidence IDs.
- `DERIVED`: reserved for values computed from observed or inferred inputs; this version does not emit derived BOQ field values.
- `MISSING`: no value is available. It has no normalized value and must not be silently substituted.

On a recognized blank template, article slots 01–05 may therefore have `normalized_value` set with `value_origin=TEMPLATE_INFERRED`, `raw_value=null`, and empty evidence. When article labels are present, their raw text and provenance are `OBSERVED`. The blank-template rule is disabled when numeric body values are present or article anchors exist; missing row labels in populated schedules remain missing and trigger review.

## Validation and limits

The French numeric parser accepts unambiguous decimal/grouping forms and preserves uncertain separators as `AMBIGUOUS`. Calculations use Decimal arithmetic and a 0.010 tolerance. This release supports only the measured page-25 geometry and listed template anchors. Real-world accuracy is unmeasured because the available reference is one template page, not a labeled set of completed tenders. Synthetic fixtures exercise the stated variants but are not real accuracy evidence.
