# Tender Summary V1

## Purpose and boundary

`app.tender_summary.build_tender_summary(tender_document)` creates a deterministic
executive summary from the structured CDC `TenderDocument` contract. It does not
open files, parse tender wording, invoke OCR, use an LLM, or change any producer
contract. It is a consumer projection intended for later backend integration.

```python
from app.tender_summary import build_tender_summary

summary = build_tender_summary(tender_document)
payload = summary.model_dump(mode="json")
```

The same JSON mapping accepted by `TenderDocument` can be passed directly. Output
has no timestamps or random identifiers; equivalent inputs produce equal output.

## Contract

- Identity includes title, reference, contracting organization, procurement type,
  language, and document identity. CDC `title` and title evidence take precedence;
  other identity facts are read from matching structured metadata keys.
- Publication, submission, clarification, execution-duration, and offer-validity
  fields are exposed under `dates`. Publication/submission/clarification values
  are metadata-only in V1; execution and offer validity use CDC requirement types.
- Financial facts map existing requirement categories: provisional guarantee,
  final/performance guarantee, retention, penalties, and payment terms.
- Structure reports section (including nested subsections), article, and annex counts.
  BOQ detection uses CDC `detected_special_documents` and classified annexes;
  detected page ranges are expanded into physical page numbers.
- Requirement counts are grouped by the exact source category. `review_required`
  counts requirements whose `review_status` is `needs_review`.
- Source coverage reports unique evidence references and the physical pages they
  cite. Total pages and ratio remain null unless page count is supplied in metadata.

Every fact has a state from `PRESENT`, `MISSING`, `AMBIGUOUS`,
`NOT_APPLICABLE`, or `NEEDS_REVIEW`. A value is null when no single usable value
exists. In particular, missing BOQ detection has state `MISSING` and null value;
it is not serialized as false. Observed structural counts may be zero because
they are counts of the supplied CDC nodes.

For requirement facts, candidate-only values and extracted values still marked
`needs_review` remain `NEEDS_REVIEW`. Conflicting values for a single fact become
`AMBIGUOUS`, with all candidate IDs and evidence retained. Evidence references
include document ID, physical page, opaque producer element ID(s), raw wording,
coordinate space, and nullable bounding box. A UI can use `(document_id, page,
element_id)` to resolve the original source.

`missing_or_ambiguous`, `uncertain_fields`, `review_items`, and `source_coverage`
are deterministic diagnostics. They do not make legal or business judgments.

## Metadata mapping

Accepted aliases are explicit in `app/tender_summary/builder.py`. Metadata values
may be plain structured values, or objects with `value`, optional `state`,
`raw_text`, `reason`, and an `evidence` list following the CDC Evidence contract.
No free text is searched for a date, organization, or reference. Unknown metadata
keys are ignored.

## Limitations

- CDC V1 does not currently carry a tender type or language as dedicated fields;
  absent metadata remains missing.
- The CDC pipeline does not expose total source page count on `TenderDocument`.
  Coverage ratio is therefore unavailable unless the consumer supplies a count
  in metadata (`total_pages`, `page_count`, or `pages_count`) or producer page
  geometry metadata.
- Requirement parsing is intentionally outside this module and currently
  incomplete. The summary preserves candidates and review states; it does not
  promote candidate interpretations into approved business facts.
- CDC tables are not treated as BOQs unless a classified BOQ/price-schedule annex
  or special document is present.
- This module does not perform persistence, HTTP/API integration, rendering, or
  frontend navigation.

## Tests

Run the focused contract tests with:

```powershell
python -m pytest tests/tender_summary
```
