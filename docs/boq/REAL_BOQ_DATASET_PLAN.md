# Real BOQ dataset collection plan

Real-world extraction performance is **NOT YET MEASURABLE**. The empty reference template and controlled synthetic cases do not measure accuracy.

## Documents and useful minimum

Collect completed Annexe 05 BOQs from multiple consultations, municipalities and scan conditions, including native PDFs and scanned/rasterized PDFs. A useful first evaluation set is at least 30 distinct completed BOQs from at least 5 tenders; split by tender/document source so duplicate pages and near-identical revisions cannot cross train/development/test partitions. This is a collection target, not a claim of statistical sufficiency.

## Variation to capture

Record original versus scanned PDF, resolution/skew, handwriting/stamps, filled versus blank template, number of populated rows, wrapped designations, missing cells, decimal/grouping conventions, VAT rate, lot and consultation variants, template revisions, and municipality/issuer. Keep non-Annexe pages as negative examples, especially Annexes 03/04/06 and technical pages.

## Ground truth process

Two reviewers independently transcribe raw cell text and mark page/bbox; adjudicate disagreements before freezing labels. Store raw and normalized values separately, using Decimal and explicit ambiguous/unreadable states. Record source document hash, page, template family/version, source type, split, reviewer/adjudication metadata and notes. Never derive expected labels by running the extractor.

## Privacy and handling

Obtain permission and document provenance before collection. Minimize personal/contact details, redact unrelated sensitive identifiers in a derivative while preserving an access-controlled original where retention is authorized, and document redactions. Keep documents in approved storage, restrict access, avoid sending them to external services, and define retention/deletion with the data owner.

## Versions and leakage

Classify each item as `reference`, `synthetic`, or `real`; annotate template revision and similarity cluster. Group the same tender, duplicate scan, corrected resubmission and near-identical copies into one split. Freeze a held-out real test set before tuning. Publish metrics separately for reference, synthetic and real and do not call synthetic results production accuracy.
