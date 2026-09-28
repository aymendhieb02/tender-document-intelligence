# CDC_ANALYZER_BASELINE_V1 contract

`CDC_ANALYZER_BASELINE_V1` freezes the deterministic CDC consumer behavior and its public output shape. It consumes the public Document Intelligence `DocumentResult` or a JSON serialization of that result through the CDC adapter. It does not read PDFs, invoke OCR, import PaddleOCR or invoice extraction code, or call a language model. Physical pages are 1-based; public bounding boxes remain in rendered-page pixel coordinates.

## Frozen behavior

- The DocumentResult consumer boundary and evidence mapping, including source page, opaque original source element IDs, raw text, bounding boxes, source type and confidence when available. Null native-PDF confidence is preserved as null.
- The canonical tender structure: title, sections and nested subsections, articles and clauses, annexes, ranges, diagnostics and source evidence.
- Deterministic structural detection and candidate requirements, with absent values left absent.
- The CDC to BOQ handoff: classify and locate a BOQ annex, then pass its node/evidence reference to `boq_agent`.
- Separation of `document_results/`, `ground_truth/` and `predictions/`; prediction output is rejected if it targets the ground-truth directory.

## Requirement values and review

`normalized_value` is an `EXTRACTED_VALUE` produced by deterministic matching; it is not a business conclusion. Each candidate retains raw `text`, `type` (category), page, source evidence with original element IDs/text/bbox, `extraction_status`, and `review_status`. `reviewed_business_interpretation` remains null until a human review process supplies one. Values and interpretations must not be silently promoted. Current candidates use `needs_review`.

## Experimental or explicitly out of scope

Semantic/legal interpretation, LLM analysis, RAG, generalized benchmark/accuracy claims, model-based heading detection, and business approval are not frozen capabilities. Human-verified ground truth is required before reporting benchmark scores. The real reference manifest remains `human_review_required`; current benchmark status is `NOT YET MEASURABLE`.

The real 30-page Tunisian tender is a regression fixture. Its expected counts and pages belong only in tests/labels. They are not production rules. Deterministic parity means repeatable output for the same DocumentResult, not extraction accuracy.
