# BOQ completion report

Date: 2026-10-04

## What exists

`app/boq` separates candidate detection, family-specific row parsing, normalization, validation, and CSV output. CDC special-document detection hands candidate physical pages to the BOQ adapter. The current implementation recognizes one hard-coded geometry family, `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1` (shown to users as Ministère des Affaires Locales). It is not a general table reconstruction engine.

The parser preserves raw and normalized values, missing/ambiguous states, source pages, geometry and evidence. Arithmetic checks return NOT_CHECKABLE when values are absent. The CSV exporter leaves null values blank; this pass also prefixes formula-like text fields to prevent spreadsheet formula execution while leaving numeric values numeric.

## Reference tender result

Fixture: `datasets/boq/male_municipal_maintenance_v1/reference/MM_Cahier-des-charges-type-Entretien.pdf`, PDF page 25 / Annexe 05. Its metadata explicitly calls it an empty geometry and terminology template, not an accuracy sample.

- Specialized candidate detected: yes
- Rows: 5 structural slots, article labels 01–05
- Designations, quantities, prices and totals: absent in source and remain null
- Row and document monetary checks: NOT_CHECKABLE
- Row-slot and duplicate-number checks: VALID
- Accuracy: not measurable from this fixture

The five structural rows are useful evidence of page-family detection and geometry reconstruction only. They are not completed BOQ extraction results. Synthetic fixtures exercise controlled errors and arithmetic, but are not evidence of real-tender accuracy.

## Changes and verification

- Persisted v2 BOQ analysis as part of the reusable tender response.
- Added a saved-result CSV route so a refreshed workspace exports existing BOQ data without another upload/analysis pass.
- Protected formula-like exported cells without converting missing numbers to zero.
- Added regression coverage for a restart-like store reload, saved CSV/UI wiring, formula neutralization and null preservation.

Focused BOQ, API and UI tests passed after the changes; final counts are in `PRODUCT_COMPLETION_REPORT.md`.

## Limitations and next work

The extractor remains template-specific and depends on stable anchors and coordinates. It does not reconstruct arbitrary table grids or generalize semantic columns across unrelated tenders. The next valuable step is to obtain completed BOQs from multiple procurement formats, label each source row/cell independently, then build and score a generic table candidate/row pipeline beside—not in place of—the proven specialized adapter.
