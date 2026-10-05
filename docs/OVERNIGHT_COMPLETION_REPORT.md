# UDGroup autonomous overnight completion report

Date: 2026-10-05. Overall: **READY WITH LIMITATIONS** for a supervised local demo, not production procurement submission. Start SHA: `f0d6f483ab8bdee5dc86a33b98bdce555df7e160`. Official remote: `https://github.com/aymendhieb02/tender-document-intelligence.git`.

## 1. Baseline

`main` matched remote at start. `pytest -q -rs`: 290 passed, 1 skipped, 1 warning in 33.03 s. The two pre-existing untracked `.rar` and `.zip` archives were preserved and excluded from commits. Historical tags were not moved.

## 2. Pricing structure discovered

The only real BOQ reference is the 30-page Ministry empty template. Page 25 has five article slots, HTVA/TTC unit and total columns, blank TVA rate and totals; pages 6 and 24 give bidder instructions and a blank TTC offer form. It supplies no completed quantity, price, tax, or amount. Article 12 supports quantity × unit price when the inputs exist; no rounding rule is stated. Synthetic fixtures contain filled numbers and an explicit test VAT, but do not establish real accuracy. Full evidence classification is in [BOQ pricing analysis](BOQ_PRICING_ANALYSIS.md).

## 3. BOQ pricing workflow

Separate persistent draft, stable ID, source fingerprint, source/user/computed origins, Decimal arithmetic, debounced autosave, partial/complete/review statuses, source mismatch detection, restart recovery, and separate formula-safe CSV: **PASS**. Controlled browser quantity 1000 × entered 12.500 gave 12500.000 HT. An explicitly entered **synthetic** 19% rate gave tax 2375.000 and TTC 14875.00000. A second disposable priced record reopened with those values after a real Uvicorn process restart. Tax is unknown for the real template; missing source quantity and price remain null. Original analysis and source export remained unchanged. No PDF form filling was attempted.

## 4. Generic BOQ V2

Synthetic regression covers a two-line header, wrapped designation with both evidences, repeated header, and TTC-only field mapping. Existing semantic column ordering, total-row skipping, and negative detection remain. HT/TTC/unknown basis is recorded only from observed header words. Multi-page continuation without a fresh header, complex subtotals, merged cells, and arbitrary OCR fragments are not yet supported reliably. Specialized Ministry regression remains green. Generic real accuracy is not measurable.

## 5. Evaluation

`evaluation_v2.py` reports presence, candidate page, row count, and per-field exact counts by separate real completed / real empty / synthetic cohorts. Real completed: 0. Real empty: 1, with presence 1/1, page 1/1, row count 1/1, five template article slots and 25 explicitly blank monetary/quantity cells checked. Those counts prove empty-template handling only. The synthetic evaluator regression passes. See [evaluation framework](EVALUATION_FRAMEWORK.md).

## 6. CDC

Audited title, reference, issuer, submission, duration, offer validity, guarantees, payment, penalties, requirements, eligibility, lots, annexes, and BOQ presence on the real reference. Title/reference/issuer and a concrete submission date remain missing because the template leaves them blank. The source has 157 requirement candidates and six annexes in the saved V2 response. A normalization offset bug caused accented text to yield wrong raw financial spans; source-offset mapping now preserves exact displayed spans. The real reference no longer shows the observed broken fragments. Financial facts remain candidates for human review, not approved legal facts.

## 7. Ask Tender

Added procurement aliases for location/method, final guarantee, validity, technical/administrative requirements, eligibility, payment, penalties, lots, BOQ, annexes, criteria, and contact. Duplicate citations from the same source element are suppressed. On seven reviewed **synthetic** questions, expected page reached top 1, top 3, and top 7 in 7/7 each. The earlier four-question set remains green. Browser citation selection navigated to the page 1 evidence inspector; local generation was unavailable, and the UI said so. No cloud AI was used.

## 8. Human review

Financial facts have a browser control for `unreviewed`, `approved`, or `corrected`; an explicit corrected value is required for corrected status. API also addresses present identity facts. Separate `review.json` preserves machine value, source evidence, correction, status, and timestamp through store reload. No reviewer identity is invented; no authentication exists. API regression verifies persistence and original response immutability.

## 9. Document library

Filename/ID search, reopen, pricing status, and explicit-confirmation delete control are implemented. Server deletion validates a 32-character storage ID and refuses linked or nested directory entries. A disposable API regression deletes only its test record; the controlled browser fixture was likewise removed through the local API after checking its filename. Historical records and archives were preserved.

## 10. OCR

Real Paddle execution: **NO** this run. `paddleocr` is not installed in the current Python environment, and `.cache/paddlex` did not contain provisioned models. The test requires `RUN_REAL_OCR=1`; setup and model instructions are in `DOCUMENT_INTELLIGENCE.md`. Native PDF extraction, OCR fallback contracts, and deterministic fixtures passed. No scanned-tender OCR accuracy claim is made.

## 11. Performance

One warm final-code 30-page native reference run: DI 530.0 ms; CDC 270.6 ms; all-page BOQ scan 248.5 ms; V2 composition 611.6 ms; Ask retrieval 1037.6 ms; five-row pricing 1.478 ms; pricing CSV 0.096 ms; 3.53 MB JSON write 54.2 ms; reload/parse 34.1 ms. Saved Ask/pricing/export/reopen paths use persisted data; regression stubs fail if DocumentProcessor reruns on restored pricing. These one-run timings are not service guarantees.

## 12. Browser end to end

**PASS:** local upload of a synthetic 1000-quantity BOQ, workspace, extracted source BOQ, pricing, live HT/tax/TTC calculation, visible save, refresh/reload, actual server restart and priced-record reopen, invalid and cleared price, repricing, Ask citation, library search and reopen. The UI reported pricing CSV downloaded; the browser automation download event did not expose a file path, while API CSV content was verified by tests. **API verified, browser control not exercised:** deletion, due to computer-use confirmation rules for permanent deletion. Both disposable browser and restart records were deleted through guarded local API calls and verified absent.

## 13. Test suite

Final verification before documentation checkpoint: `pytest -q -rs` → **305 passed, 0 failed, 1 skipped, 1 warning in 34.71 s**. Skip: opt-in real Paddle model test. Warning: existing Starlette/httpx TestClient deprecation. JavaScript syntax checks and `git diff --check` passed.

## 14. GitHub

Code checkpoint `705e81c` (`feat: complete local tender pricing and review workflows`) was pushed to official `origin/main`. Documentation checkpoint and final SHA are recorded in the final task response and Git history. No force push, tag operation, or change to the neighboring invoice repository was made.

## 15. Limitations

P0 for production: authentication, access control, backup/recovery, and representative real completed BOQ validation. P1: scanned/mixed OCR evaluation, multi-page generic tables, source-specific tax/rounding approval, and full browser download verification. P2: filled original PDF or XLSX export and richer review audit history. The local product is usable for a supervised demonstration, not an unattended binding bid.

## 16. Scores (engineering judgment, not measured accuracy)

Architecture 8/10; Document Intelligence 8/10; CDC 7/10; specialized BOQ 8/10; generic BOQ 5/10; BOQ pricing 8/10; Ask Tender 7/10; human review 6/10; evidence 8/10; persistence 8/10; UX 7/10; evaluation maturity 4/10; testing 8/10; security 5/10; maintainability 7/10; production readiness 4/10.

## 17. Verdict

**YES WITH CAVEATS** for a local UDGroup demo tomorrow. The biggest remaining weakness is the lack of labeled, real completed BOQs; the highest-value next task is to collect and independently label a diverse set, including scans, then score row/value extraction and pricing semantics by cohort.
