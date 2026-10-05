# BOQ evaluation framework

Date: 2026-10-05. `app/boq/evaluation_v2.py` accepts version 1 case dictionaries with `cohort`, `expected`, and an extracted `BOQDocument`. Supported cohorts are `real_completed`, `real_empty_template`, and `synthetic`; each has its own counts. There is no combined accuracy number.

Ground truth should be reviewed and versioned alongside its source checksum, page numbers, table family, and labeling notes. The `expected` object records presence (`detected`), `candidate_page`, and rows. Each row can label article/reference, designation, unit, quantity, unit price, and total fields. Omitted fields are unscored; explicit `null` means the source truly has no value. `evaluate_cases` reports exact counts for presence, candidate page, row count, and each labeled cell, with numeric comparison via Decimal. It does not silently score unlabeled cells or turn absent samples into zero accuracy.

Current repository evidence:

| Cohort | Samples | What can be checked |
| --- | ---: | --- |
| Real completed BOQ | 0 | No real value accuracy can be measured. |
| Real empty template | 1 | The 30-page Ministry reference detects page 25 and five structural row slots; blank quantity/monetary cells remain blank. |
| Synthetic | Several fixtures and focused tests | Controlled parsing, arithmetic, missingness, header/wrap behavior, and pricing calculations. |

On the real empty reference, the new evaluator measured presence 1/1, candidate page 1/1, row count 1/1, and five article labels plus 25 explicitly blank quantity/monetary cells correct. Article slots are template structure, not priced tender values. Those counts **do not** establish extraction accuracy on completed offers. The synthetic test of the evaluation framework passes, but its values are not mixed into the real cohort.

Next collection: obtain consented completed BOQs from distinct issuers and scans, preserve source PDFs, independently label each field and source page, then run the same cohort report. Record OCR mode and review disagreements. Do not publish a general accuracy rate before that set exists.
