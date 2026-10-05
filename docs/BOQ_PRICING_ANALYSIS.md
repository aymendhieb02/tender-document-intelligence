# BOQ pricing structure analysis

Date: 2026-10-05. Evidence categories are kept separate below.

## Real document inspected

`datasets/boq/male_municipal_maintenance_v1/reference/MM_Cahier-des-charges-type-Entretien.pdf` is a 30-page searchable PDF and an **empty tender template**, not a completed priced offer. PDF page 25, Annexe 05, was inspected visually and through native text; pages 6 and 24 were read for pricing instructions and the submission form.

| Location | Observed structure | Classification |
| --- | --- | --- |
| Page 6, Article 12 | The bidder fills unit prices in words and figures and multiplies by indicated quantities to obtain the total offer. | REAL DOCUMENT |
| Page 6, Article 13 | Prices are in Tunisian dinars; HT prices, TVA rate, and TTC prices must be indicated separately. | REAL DOCUMENT |
| Page 24, Annexe 04 | Submission form has a total amount in DT TTC, blank in this template. | REAL DOCUMENT |
| Page 25, Annexe 05 | Rows 01–05 show Article, Désignation, Qté, Prix HTVA (DT) Unité/Total, Prix TTC (DT) Unité/Total. | REAL DOCUMENT |
| Page 25, bottom | Total HTVA, TVA (blank `...%` rate and blank amount), Total TTC, and total TTC in words. | REAL DOCUMENT |

The printed “L’unité : ... DT” line lies inside the designation column. It appears to request a unit price in words; it is **not** evidence of a physical unit of measure. The existing specialized extractor retains it as ancillary evidence.

## Supplied, bidder-entered, and calculated values

The template supplies five article labels and the field structure. It does **not** supply designations, physical units, quantities, unit prices, row totals, tax rate, tax amount, or document totals. A completed tender could supply quantity and designation, but this reference does not demonstrate that case.

The bidder is instructed to fill unit prices. The form has both HTVA and TTC unit-price columns and a blank TVA-rate field. A pricing draft can therefore accept HTVA and TTC unit prices separately; it may calculate TTC from HTVA only when a source or deliberately configured tax rate is explicit. A blank rate is **UNKNOWN**, never zero. User-entered prices and tax configuration must be labeled as such.

Article 12 supports `quantity × unit price = row amount` when both inputs are available. The table structure suggests sums of HTVA/TTC row totals for document totals, and the labels support `total HTVA + TVA = total TTC` when an explicit rate and taxable base are available. The exact rounding convention is **not stated** in this empty reference; the pricing engine should keep exact `Decimal` values and avoid hidden rounding. Source and calculated totals must remain distinct if they disagree.

## Other evidence and limits

`datasets/boq/male_municipal_maintenance_v1/synthetic/fixture_a_clean.pdf` has two filled rows, HTVA/TTC unit and total values, and an explicit `TVA (19%)`; it is **SYNTHETIC** and useful for regression only. Existing synthetic fixtures also cover missing quantity, shifted geometry, OCR errors, and arithmetic error. `tests/test_platform_api.py` includes a separate synthetic generic BOQ with Article, Désignation, Unité, Quantité, Prix unitaire, Montant; that test has HT-style columns but no tax information.

No completed real BOQ is present in the repository's `real/` dataset folder. No real-world value-extraction or pricing accuracy can be inferred from the synthetic fixtures. A source-specific pricing profile is therefore limited to observed column semantics, and any tax rate used for calculation must be explicit in the extracted source or entered by the employee.
