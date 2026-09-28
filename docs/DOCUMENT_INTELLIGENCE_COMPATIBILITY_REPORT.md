# Document Intelligence V1 compatibility report

Date: 2026-09-28. Owner: Agent 1. Scope: contract stabilization only.

## CONTRACT VERSION

`document_intelligence_contract_version = "1.0"`, exported from the schema module
and package. It is deliberately out-of-band: existing `DocumentResult` JSON has
no additional field and no consumer payload migration is required. The frozen
JSON Schema records the full current public structure, including inherited types.

## PRODUCER TESTS

`python -m pytest tests/document_intelligence -q -p no:cacheprovider --tb=short`,
with `RUN_REAL_OCR=1`: **43 passed, 1 warning in 13.96 seconds**.

This includes 10 new contract tests and 33 existing producer tests. Contract tests
guard version/schema, fixture round-trip, physical page boundaries (including
empty pages), deterministic source IDs, repeated text, page-scoped group references,
box representation/transforms, source vocabulary and null/zero confidence.

The shared specimen has 2 pages and 9 elements. It is synthetic typed evidence,
not a real OCR result or a ground-truth accuracy dataset. Its metadata says so.

## REAL OCR

**PASS.** The existing real Paddle test ran against the controlled image and
mixed native/scanned/native PDF, with evidence cache and fallback disabled.
The model cache was `.cache/paddlex`; no new models were introduced. The only
producer warning says Paddle ignores `lang`/`ocr_version` when explicit model
names are supplied; this is unchanged from V1 verification.

## BOQ FAILURES

All three named tests now **PASS**. Historical failures are classified below;
they were not reproduced as failures in the current shared checkout. The earlier
captured test log supplied the failing assertions. Exact former consumer source
revisions were not committed, so this report does not invent a precise historical
band change or claim to have fixed the consumer.

| Test in `tests/boq/test_specialized_boq.py` | Classification | Historical observation and ownership evidence |
|---|---|---|
| `test_filled_rows_decimal_validation_and_provenance` | CONSUMER_BUG | Quantity was null instead of `2`. `filled()` constructs a consumer `DocumentPage` from synthetic boxes and calls the specialized extractor directly. No DocumentProcessor/OCR is invoked. Assigning those boxes to numeric fields is the consumer's responsibility. |
| `test_missing_cell_is_not_fabricated_and_arithmetic_error_is_detected` | CONSUMER_BUG | The bad-total case returned NOT_CHECKABLE instead of INVALID. Missing/misassigned numeric operands prevented consumer arithmetic validation; both field assignment and this status are downstream of the producer. |
| `test_ocr_aliases_and_shifted_geometry` | CONSUMER_BUG | Unit price contained quantity text `2` instead of `125,250`. This directly demonstrates consumer column-role assignment, not recognition or coordinate-transform loss; inputs are already supplied by its own fixture. |

Current inspection: the extractor computes center x divided by page width and
maps it through template-specific `column_bands`. For the current width-1000
fixture, x=530 belongs to quantity, x=596 to unit price HT, and x=668 to total HT.
Those are consumer format assumptions. Producer geometry columns do not carry
these semantic roles or promise that a particular band ordering is correct.

## CDC FAILURE

`tests/cdc_analysis/test_analysis.py::test_real_producer_schema_adapter_without_running_ocr`:
**CONSUMER_BUG** (historical source-reference/derived-ID mismatch); currently **PASS**.

Historical expectation: `source_evidence[0].element_id == "original-id"`, but CDC
returned `p1-row-0000`. The supplied producer element retained `original-id`; the
CDC adapter assigned a new ID when building a derived line, retaining original
parts separately. Thus the producer did not lose or mutate an ID.

In the current shared checkout the CDC assertion checks
`source_evidence[0].source_element_ids == ["original-id"]`, and the consumer pipeline
populates those IDs from the preserved parts. That distinction between derived
identity and source identity is compatible with V1. These consumer code/test
changes were made outside this task; Agent 1 did not alter their expectations.

## PRODUCER CHANGES REQUIRED

**No behavioral producer change demonstrated or required.** Only a public version
constant/export was added. No changes to DocumentResult fields, recognition,
preprocessing, model parameters, cache behavior, page selection or geometry
algorithms were made in this stabilization task. Runtime strictness was not
changed: the existing Pydantic schema remains structurally permissive where V1
was permissive, and regression tests document producer invariants separately.

## CONSUMER CHANGES REQUIRED

No edits were made to consumer code. The current four tests are green, so no new
fix is prescribed merely from their old failures. Maintain these obligations:

- BOQ: verify template column bands/fixtures against the same public page pixels,
  infer semantic roles in the consumer and retain contributing source IDs for
  every normalized numeric value. Geometry candidates alone do not identify prices.
- CDC: distinguish derived row/section IDs from original source IDs, retain all
  contributors for merged text, and cite singleton source IDs unchanged.
- Both: use the shared V1 specimen in integration tests; preserve nulls, zero
  confidence, source values and explicit coordinate spaces. Do not depend on
  recognizer internals or parse opaque IDs for semantics.

## CONTRACT AMBIGUITIES

Resolved through documentation, not behavioral changes:

1. “Visual rows” means `page.geometry.rows`, not a new field or a semantic table.
2. Element IDs identify original evidence; group/consumer-derived IDs identify
   derived objects. Source provenance must carry the original IDs separately.
3. Cell candidates can be words or OCR lines; column groups describe repeated
   left edges, not quantity/price roles. A visual row can cross text columns.
4. Public bbox is already in rendered page pixels; source transforms apply only
   to `source_bbox`. Missing boxes are null, not zeros or fabricated rectangles.
5. Native confidence is null; OCR zero is distinct from null. Scores are evidence,
   not field correctness, calibrated accuracy or an arithmetic validation result.
6. Contract version is public metadata outside the unchanged payload, not the
   internal cache schema. Timing values and inference outputs are not frozen bytes.

None of these ambiguities demonstrates a producer bug in the four supplied cases.
The guide explicitly distinguishes structural model validation from invariants
guaranteed by the built-in producer, especially for externally injected data.

## COMPLETE SUITE

With `RUN_REAL_OCR=1`, `python -m pytest -q --tb=short -p no:cacheprovider`:
**650 passed, 13 failed, 2 warnings in 32.07 seconds**. The four requested
consumer cases passed both in isolation (**4 passed in 0.38 seconds**) and in the
full run. All producer tests passed.

Remaining failures: the same 12 historical invoice/optional-model tests plus
`tests/cdc_analysis/test_analysis.py::test_synthetic_fixture_and_benchmark_gate`.
That additional consumer benchmark test is outside the four requested diagnoses
and was not modified. The full suite is not green. Other agents are developing
consumer modules in this shared checkout, so counts are a snapshot, not an
assertion that all changes belong to this task. `git diff --check` passed.

Reproduction from the pinned environment:

```powershell
$env:PADDLE_PDX_CACHE_HOME = Join-Path (Get-Location) '.cache/paddlex'
$env:RUN_REAL_OCR = '1'
python -m pytest tests/document_intelligence -q -p no:cacheprovider --tb=short
python -m pytest tests/boq/test_specialized_boq.py::test_filled_rows_decimal_validation_and_provenance tests/boq/test_specialized_boq.py::test_missing_cell_is_not_fabricated_and_arithmetic_error_is_detected tests/boq/test_specialized_boq.py::test_ocr_aliases_and_shifted_geometry tests/cdc_analysis/test_analysis.py::test_real_producer_schema_adapter_without_running_ocr -q --tb=short -p no:cacheprovider
python -m pytest -q --tb=short -p no:cacheprovider
```

## FILES CHANGED

Files changed/created **in this stabilization task only**:

- `app/document_intelligence/schemas.py` — version constant only.
- `app/document_intelligence/__init__.py` — public version export only.
- `tests/document_intelligence/test_contract_v1.py` — 10 contract tests.
- `tests/document_intelligence/fixtures/document_result_v1.json` — shared typed specimen.
- `tests/document_intelligence/fixtures/document_result_v1.meta.json` — synthetic provenance/version.
- `tests/document_intelligence/fixtures/document_result_v1.schema.json` — frozen wire schema.
- `docs/DOCUMENT_INTELLIGENCE_CONSUMER_GUIDE.md` — consumer contract and integration usage.
- `docs/DOCUMENT_INTELLIGENCE_COMPATIBILITY_REPORT.md` — this report.
- `docs/DOCUMENT_INTELLIGENCE.md` — version and consumer-guide link.

Existing uncommitted OCR/environment work and independently added BOQ/CDC files
were preserved. No consumer source or consumer test file was edited by Agent 1.
