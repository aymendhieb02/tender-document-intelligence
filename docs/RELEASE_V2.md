# Tender Intelligence V2 — Structured Tender Intelligence

V2 adds a deterministic intelligence layer to the V1 Document Intelligence and CDC foundation. The V1 release tag remains immutable at `838e2d5af55d974a93bf31506eb757e44ca3e4cd`.

## Integrated flow

`DocumentProcessor` extracts a PDF/image once into a `DocumentResult`. `CDCAnalyzer` turns that evidence into a `TenderDocument`. Requirements Intelligence classifies CDC candidates; Financial/Deadline Intelligence normalizes only text already attached to CDC evidence; Tender Summary projects the structured outputs; Tender Dossier retains the processed document and analyzer outputs. API V2 serializes these modules without a second extraction pass. BOQ remains a separate specialized handoff.

Requirements retain source evidence and remain `NEEDS_REVIEW` until a human accepts or rejects them. Financial facts keep raw spans distinct from normalized values, stable IDs, and page/element evidence references. Decimal values are serialized as strings. Requirement `related_value_refs` are populated only when source element IDs match a normalized fact's evidence; unmatched references stay empty. Summary does not read or parse PDFs. Missing fields remain null, and ambiguous or conflicting values remain reviewable.

The current upload endpoints accept one document at a time. The dossier producer can aggregate multiple processed documents, but this API request cannot establish cross-document membership; V2 returns a partial singleton dossier with grouping marked for review. No legal truth is inferred. Compliance and retrieval/Ask Tender are not part of Wave 1; Compliance is reported unavailable.

The core modules are deterministic and do not use an LLM, embeddings, or network calls. OCR remains owned by Document Intelligence. The supported BOQ extractor is template-specific and leaves blank template values null.

## API V2 availability

`/api/v2/cdc/analyze` returns CDC structure, summary, requirements, financial/deadline facts, compact evidence references, and a partial single-document dossier. `/api/v2/cdc/male/analyze` also reports BOQ availability and results from the supported BOQ workflow. A module can return an empty data list after running; `partial`, `unavailable`, and `not_run` distinguish constrained or unexecuted work. Compliance remains `unavailable` with reason `not_in_wave_1`.

V1 routes and payloads are preserved. V2 does not expose copied OCR text inside compact evidence references; raw financial spans remain in their owning financial facts and link to source elements.

## Benchmark scope and results

All benchmark results below are development-corpus measurements, not held-out generalization or overall accuracy.

- **Structural CDC, expanded CDC-DEV-001:** the exhaustive reviewed article inventory matched 36/36 articles (36 TP, 0 FP, 0 FN). Reviewed negative controls produced no false major sections for 8 Lot headings, no false annex headings for 6 in-text annex references, and no guarantee/penalty match for 1 volume-variation decoy.
- **Requirements:** the stored V2 development result records 14/26 positive requirement examples matched (53.8%), with 14/14 page attributions correct. Labels are sampled positives, so requirement precision and exhaustive recall are not measurable. Wave 1 requirement classifications themselves remain human-review candidates; their count is not an accuracy score.
- **Financial/deadline, end-to-end subset:** on CDC-DEV-001, 10/14 scoped nonblank facts had a type/article candidate, all 10 located candidates had correct pages, and 9/10 located candidates had the reviewed normalized value (9/14 exact within-scope recall). One blank template field is unresolved and unscored.
- **Financial/deadline, rule-level:** the separate verified-span evaluation scored 17/18 exact against the same labeled spans, compared with 5/18 for the replayed legacy predicates; 12 examples improved and none regressed. This is not end-to-end accuracy.
- **Provenance:** the stored V2 development evaluation reports 14/14 correct page attributions for matched requirement examples. The expanded single-document scorer reports 10/10 correct pages among its located financial candidates. These scopes are distinct.
- **BOQ:** the development set reports detection/page overlap on 3/3 verified BOQ-positive documents. There is no source-reviewed negative BOQ set, so specificity is not measured. The empty-template API fixture verifies null amounts and does not establish real-world extraction accuracy.
- **Scanned Arabic:** CDC-DEV-009 remains `DRAFT` and unscored; no scanned-Arabic accuracy claim is made.

The local benchmark prediction used for expansion scoring is generated under the ignored `benchmarks/cdc_real_v1/predictions_v2/` directory. Generated predictions are not committed. Structural, requirement, financial, provenance, and BOQ results remain separate; they are not combined into one score.

## Validation environment

On Python 3.11.9 with `pytesseract==0.3.13` and Tesseract 5.4.0, `compileall` succeeded and the complete local suite passed **267 tests, with 1 existing opt-in PaddleOCR test skipped**. The only warning was the existing Starlette/httpx test-client deprecation. GitHub Actions remains the release gate for the pushed main commit.

## Known limitations and provenance

- Requirement and financial rules are deterministic candidates, not accepted procurement advice; human review is required.
- Financial rule coverage is incomplete. Ambiguous and conflicting facts are retained; some contextual matches use candidate-level evidence where an exact source element cannot be isolated.
- The development corpus is small and was used during iteration. A separately acquired and independently reviewed held-out corpus is required for final generalization evaluation.
- The 30-page MALE works-specification template at `dataset/cdc/raw/MM_Cahier-des-charges-type-Entretien.pdf` is retained unchanged as benchmark source material. A byte-identical copy is also retained as the BOQ reference fixture. Its redistribution/license provenance is unresolved and has not been verified; both copies remain unchanged pending human review.
- Multi-document dossier matching and conflict aggregation are available in the domain module but are not exposed as a multi-upload V2 endpoint.
- Compliance and Ask Tender/retrieval require later waves.

The pre-Wave 1 cleanup removed the generated 3.8 MB CDC prediction snapshot from the current tracked tree in a post-V1 commit. The immutable V1 tree and history still contain that historical file; the regression test now uses the committed `DocumentResult` input and direct structural assertions without requiring the generated snapshot.
