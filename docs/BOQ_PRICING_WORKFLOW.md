# BOQ pricing workflow

Date: 2026-10-05. This is a local, separate bidder draft over an immutable extracted BOQ. The source analysis and source CSV never acquire user prices.

## Use

Upload a tender, open **Bordereau**, then **Chiffrer le bordereau**. Source article, designation, unit, quantity, and page are read only. Enter unit prices in the columns supported by the detected table. The UI calculates line and document amounts without reprocessing the PDF. It saves after a short pause, shows its persistence state, and restores the inputs after refresh or restart. **Exporter le chiffrage** downloads a separate UTF-8 CSV; **Exporter le bordereau extrait** retains the source export.

`GET/PUT /api/v2/cdc/{storage_id}/boq/{index}/pricing` load and save the draft; `GET .../pricing.csv` exports it. The draft is `outputs/tender_workspace/<storage_id>/pricing-<index>.json`, separate from `analysis.json`, with a stable draft ID and source fingerprint. A changed source fingerprint returns 409 for review. Invalid row indices return 422. The source remains immutable. The API recomputes amounts from saved input every time; stored client amounts are never trusted.

## Origin and calculation

Source fields keep their extracted parsed state and evidence. Entered unit prices and optional tax rate are user inputs. Amounts have `computed` origin. Missing quantity or price leaves the amount null. Numeric inputs use dot or comma as the decimal separator, without thousands separators or exponent notation. Negative values are rejected. Zero quantity is allowed only when explicitly present in the source. `Decimal` preserves all input digits; no document rounding convention was found, so no hidden quantization occurs.

The specialized Ministry table has HTVA and TTC price columns. A generic table uses observed header wording: HT, TTC, or unknown. An unqualified generic price yields an unqualified amount, never a mislabeled HT value. HT line amounts are quantity × HT unit price. TTC can come from an explicit TTC unit price, or from HT with an explicit source or employee-configured tax rate. The rate is never defaulted. Differences between source totals and computed totals are reported, while both remain separate.

Status is deterministic: non commencé, en cours, complet, or à vérifier. Complete requires all source quantities and required prices for the profile, valid inputs, and no detected inconsistency. Partial drafts save normally. The CSV preserves nulls as empty fields and neutralizes formula-like text. Source PDF filling is deferred: the real template has complex table layout and no verified completed sample or rounding convention.

## Verification and limits

Unit tests cover exact decimals, missing/invalid inputs, zero, tax, source mismatch, statuses, CSV injection, and generic/specialized profiles. API tests cover store reload, original response immutability, and no repeat DocumentProcessor call. A synthetic browser fixture with quantity 1000 showed `12.500 → 12500.000`, explicit test rate `19 → tax 2375.000`, and TTC `14875.00000`, then persisted through refresh. A second disposable priced record retained those values after an actual Uvicorn process restart. The 19% figure is **synthetic test input**, not a default or assertion about the real tender.

No real completed BOQ or approved tax/rounding rules were available. Pricing a live offer still requires human checking of source quantities, tax applicability, and final submission format.
