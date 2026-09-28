# MALE Municipal Maintenance BOQ V1

Status: first specialized family; reference inspected from the neighboring `cahier_de_charge/data/MM_Cahier-des-charges-type-Entretien.pdf` (same named template; filename omits `(1)`).

## Source and target

The requested reference is `MM_Cahier-des-charges-type-Entretien(1).pdf`; the available same-template file `MM_Cahier-des-charges-type-Entretien.pdf` is preserved in `datasets/boq/male_municipal_maintenance_v1/reference/`. Its Annexe 05 is printed page 25 (PDF page 25), A4 portrait, 595.2 × 841.92 PDF points. The page visibly reads “BORDERAU DES PRIX – DEVIS ESTIMATIF” (source misspells *Bordereau* with one `r`). The table spans approximately x=70.82–503.47 pt and y=213.67–600.17 pt.

## Identification

Family ID: `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1`. Matching requires all five independent normalized anchors: Annexe 05; Bordereau des prix; Devis estimatif; Prix HTVA; Prix TTC. The detector returns each anchor, missing anchors, matched text evidence and a count. The count is a rule diagnostic, not a probability. A lone financial term cannot match.

## Expected structure

The page has the consultation/A.O reference and work title above the table, then lot number; a two-tier header; five article bands 01–05; three totals rows; amount-in-words and signature/date fields. Logical columns are Article (x=70.82–115.01), Désignation (115.01–297.96), Quantité (297.96–333.48), HTVA unit (333.48–375.98), HTVA total (375.98–418.49), TTC unit (418.49–460.97), and TTC total (460.97–503.47), all in PDF points. Main horizontal rules are y=213.67, 228.79, 243.91, 303.22, 362.26, 421.32, 480.38, 554.33, 569.45, 584.57 and 599.69 pt. Thus the five body-row bands are [243.91,303.22), [303.22,362.26), [362.26,421.32), [421.32,480.38), and [480.38,554.33). Each row has a second line “L’unité : … DT” inside the designation cell. The instructions elsewhere in this Cahier des Charges say unit prices are written in letters and figures; this is therefore likely the unit-price-in-words entry, not unit of measure. It is retained as ancillary evidence because the exact semantic field is not in the canonical schema.

Header aliases normalize accents, case and punctuation. The detector accepts the template's printed misspelling “BORDERAU DES PRIX”, `Qté` / `Qte`, `Désignation` / `Designation`, totals and common OCR confusions conservatively.

The measured relative x bands are centralized in `app/boq/extractor.py`; extraction maps coordinates in the source page's rendered-pixel coordinate space by page-width proportions. “L'unité” is preserved separately as ancillary evidence and is not assigned to canonical UOM.

## Values and validation

Raw text is retained separately from normalized values. Numeric parsing returns `Decimal`, missing values remain null, and ambiguous notation is not guessed. The arithmetic tolerance defaults to 0.010 TND and can be overridden. Missing optional values are `NOT_CHECKABLE`, not invalid. Row checks cover quantity × HT/TTC unit price; document checks cover sums and HT + VAT = TTC. OCR confidence is retained as evidence and is independent of arithmetic status.

Detection reports anchor presence and a deterministic signal count, never a probability. Per-cell OCR confidence is copied from the source when present; native PDF text has no fabricated OCR confidence. The evaluator reports template/table detection, header mapping, row count, raw-cell exactness, normalized-number exactness, arithmetic status, review rate, and processing time separately. Reference and synthetic measurements are development checks. Real measurements remain **NOT YET MEASURABLE**.

## Known and unproven

Known: the structure and geometry above, French/Tunisian terminology, five displayed article numbers, three document totals, and the fact that the reference is an empty template. It defines geometry/terminology but cannot measure extraction accuracy.

Unproven: whether the `(1)` file is byte-identical to the available same-template reference, field variability, real-world accuracy, acceptable arithmetic tolerances for actual tenders, and how close variants behave. The synthetic fixtures are development checks only. Real evaluation remains **NOT YET MEASURABLE** until completed BOQs with independent ground truth are collected.

## Failure cases and review

Reject pages without the full anchor combination, including other annexes with tables. Missing or contradictory geometry, incomplete anchors, unparseable or ambiguous values, absent cells, and arithmetic mismatches require review. Every cell value carries source page, union bbox where available, raw text, OCR confidence, source and element IDs. Geometry-free evidence is still retained but cannot support spatial reconstruction.
