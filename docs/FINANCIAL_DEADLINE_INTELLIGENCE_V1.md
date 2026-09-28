# Financial & Deadline Intelligence V1

## Scope

`app.cdc_analysis.financial_deadline.normalize_financial_deadlines(text)` is a deterministic normalization layer for values already present in source text. It does not run OCR, infer document hierarchy, assign general requirement taxonomy, extract BOQ rows, or use an LLM, embeddings, or model downloads.

Every `Fact` carries the exact matched `raw` text separately from `normalized` fields. Monetary amounts and rates use `Decimal` in Python. `Fact.as_dict()` converts decimals to decimal strings for JSON-safe output. The function returns every supported candidate; callers retain competing candidates and must resolve `status="conflict"` or `status="ambiguous"` explicitly.

Normalized fields currently include:

- Money: `amount`, ISO currency (`TND` for Tunisian dinars), and `tax_basis` (`HT`, `TTC`, or null).
- Percentages, penalties, and explicit VAT rates: decimal `value`, `unit` (`PERCENT`, `PER_MILLE`, or `DECIMAL_RATE`), optional period and basis. Penalty rate and cap are separate facts.
- Guarantees: amount facts are tagged provisional when the source says provisional; the raw amount wording remains available.
- Dates: ISO `date`, and `time` when explicit. Named French and corpus-evidenced Arabic month forms are recognized. Submission, clarification, and site-visit deadlines have distinct categories. Numeric dates with two plausible day/month orders remain ambiguous.
- Durations: numeric or supported written French quantities with `DAY`, `WEEK`, `MONTH`, or `YEAR`; context can classify validity, execution, warranty, and payment deadlines.
- Payment terms: payment components, retention, and schedule frequency are separate facts. Quarterly schedules preserve “à terme échu” as `IN_ARREARS`.

The layer does not convert percentages into money, infer a tax basis, calculate a penalty amount, add renewal periods into a contract term, or select between conflicting dates. It does not infer a missing amount when only a guarantee heading is present.

## Development benchmark

The checked-in development ground-truth labels were read without modification. `scripts/evaluate_financial_deadline.py` writes the separate artifact `benchmarks/cdc_real_v1/financial_deadline_v1.json`.

On the 18 verified development labels in this module's scope, the new normalizer exactly normalized 17/18. A row-level replay of the former V2 normalization predicates on those same labeled raw spans scored 5/18: **12 additional exact values, zero regressions**. The remaining miss is an Arabic payment deadline whose source wording does not provide sufficient payment context in the isolated labeled span.

The prior end-to-end benchmark reported 7/14 exact normalized values among detected requirement examples. Those denominators and evaluation paths differ: the report here evaluates fixed verified labeled raw spans directly, and does not score detection, OCR, requirement taxonomy, or evidence localization. The 17/18 result must not be presented as an end-to-end improvement or as evidence of generalization. The development corpus is not held out.

## Tests

Focused unit coverage is in `tests/cdc_analysis/test_financial_deadline.py`. It covers decimal values, French number/parenthesis combinations, corpus-evidenced Arabic dates and currency forms, per-mille and formula penalties, caps, DT/TND, durations, named and ambiguous dates, payment/retention splits, guarantees, missing values, and conflicting deadlines.

## Known limitations

- Written French number composition is intentionally limited; unrecognized constructions remain missing rather than guessed.
- Arabic temporal support is limited to observed month names, numeric values, common day units, and selected explicit time phrases. Broader dialect and spellings need additional corpus evidence.
- Arabic currency phrases are normalized to TND only when a Tunisian dinar wording is present or the supported `DT`/`TND` abbreviations occur. Other currencies are not yet mapped.
- Tax basis is detected only when an explicit nearby `HT`/`TTC` cue appears.
- Context windows are local deterministic heuristics. Chopped OCR snippets may omit the words needed to classify a value, as seen in the remaining benchmark miss.
- `payment_component` and `retention` values are percentages of payment amount only when nearby payment wording supports that interpretation; no balancing arithmetic is applied.
- The module exposes normalized candidates but is not wired into OCR, structural analysis, UI, or a downstream consumer. Integration should preserve candidate status and source evidence.
- Evaluation covers one development corpus and has no held-out benchmark, precision/recall inventory, or language-by-language reliability claim.
