# BOQ MVP

## Supported behavior

The MVP specializes in `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1`. A match requires the five existing independent family anchors. A recognized page exposes five measured article slots and the canonical `BOQDocument` / `BOQRow` models. Annex 05 is handed from the CDC analysis to this extractor on the physical page referenced by the handoff.

The blank reference template is expected to have no quantity or price entries. Such commercial fields remain null in JSON and blank in CSV. Article numbers may be marked `TEMPLATE_INFERRED` because the verified template defines those five structural slots. Inferred articles carry no OCR evidence. No amount is defaulted to zero.

Each row keeps its physical source page, aggregate source bounding box, and field evidence when the source provides it. Evidence retains original text, element IDs, source label, and confidence where available. The extractor does not fabricate page, box, element, or confidence data.

## Review and validation

Validation reports the expected five slots and duplicate item numbers for a detected V1 document. A populated row is flagged for review when designation, quantity, HT/TTC unit price, or HT/TTC total is missing. The physical unit is not marked missing because this family does not yet have a validated physical-unit column mapping. Arithmetic checks compare quantity × unit price with line total only when all three values were parsed; document arithmetic also remains not checkable when required operands are absent. Values are never filled to make a check pass.

Blank structural rows with no row content are not reported as extraction failures. Their arithmetic checks remain `NOT_CHECKABLE`. A populated row with missing required data receives `NEEDS_REVIEW`; arithmetic mismatches are `INVALID`. Document-level review status summarizes those checks. The status is deterministic guidance for human review, not a claim of extraction accuracy.

The model's `unit` field remains distinct from unit price in words. The current family extractor preserves the reference's ambiguous “L’unité … DT” text as ancillary evidence and does not map it to physical unit or invent a `unit_price_in_words` value. This field distinction should be added to the domain contract only with a validated source mapping.

## CSV export

`export_boq_csv()` in `app.boq.export` creates a standard UTF-8-compatible CSV string. The additive `POST /api/cdc/male/export.csv` endpoint accepts the same tender upload as the analysis endpoint and downloads recognized rows as `boq-export.csv`.

Columns are `item_number`, `designation`, `unit`, `quantity`, `unit_price_ht`, `total_ht`, `unit_price_ttc`, `total_ttc`, `status`, and `page`. Null or unavailable values become empty fields; monetary and quantity nulls are never converted to zero. French and Arabic Unicode text is preserved by the CSV writer. There is no separate JSON export because the analysis API already exposes the structured JSON result.

## Limitations and next work

Only the measured Male municipal maintenance template is supported. The extraction geometry is specialized to its reference page; other BOQ families, changed column layouts, multi-page tables, and completed-tender variation are not generalized. The physical `unit` and `unit_price_in_words` distinction has no verified source mapping in this family yet. Real-world field accuracy remains unmeasured because the available reference is a blank template and the synthetic fixtures are development checks.

BOQ V2 work should start with access-approved completed examples and independent ground truth from multiple tender families. It should generalize header and column mapping, currencies, table layouts, page continuation, value origin, and evidence mapping against a measured baseline before any broader extractor is treated as supported. The existing specialized family and its fixtures remain useful as a regression baseline.
