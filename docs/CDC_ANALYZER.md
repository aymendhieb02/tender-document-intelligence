# CDC Analyzer

The deterministic baseline is frozen as `CDC_ANALYZER_BASELINE_V1`. See [the V1 contract](CDC_ANALYZER_V1_CONTRACT.md), [the CDC→BOQ handoff](CDC_BOQ_HANDOFF.md), and [the real baseline report](CDC_BASELINE_REPORT.md).

The deterministic CDC domain reconstructs an entire tender's structure from already extracted document evidence. It does not open PDFs, run OCR, alter PaddleOCR, parse BOQ rows or contact external models.

## Run

```python
from app.cdc_analysis import CDCAnalyzer, DocumentInput

tender = CDCAnalyzer().analyze(document_result)  # producer model or its JSON dictionary
payload = tender.model_dump(mode="json")
# Internal fixtures also work: CDCAnalyzer().analyze(DocumentInput.model_validate(fixture_json))
# For a different producer schema: CDCAnalyzer(adapter=MyDocumentResultAdapter()).analyze(result)
```

```powershell
.venv/Scripts/python.exe -m app.cdc_analysis dataset/cdc/raw/tunisian_structure_synthetic.json --output dataset/cdc/predictions/tunisian_structure_synthetic.json --ground-truth dataset/cdc/ground_truth/tunisian_reference_manifest.json
.venv/Scripts/python.exe -m pytest tests/cdc_analysis -q
```

The CLI consumes JSON matching the producer DocumentResult or the internal fixture contract. `IntelligenceDocumentAdapter` handles the newly added producer schema without importing its OCR runtime. There is no HTTP/UI integration in this baseline.

## Input and output

`DocumentInput` contains document ID, source metadata and ordered pages. Pages carry physical 1-based numbers, optional dimensions/coordinate space and ordered elements. Elements contain ID, Unicode text, optional bbox, kind, heading level, bold/font size and table ID. The current producer supplies word elements and geometric rows. Its adapter builds line candidates from upstream row IDs while retaining each source word ID, raw text and bbox. Page transforms/layout counts stay in metadata; geometry is not treated as semantic table candidates. The real producer JSON preserved accented French text and reported no missing geometry.

`TenderDocument` contains metadata, detected title/evidence, sections/subsections, articles, annexes, paragraphs, requirements, table references, special documents, diagnostics, TOC/furniture evidence, source order and review overlays. Content before any section is preserved at document level. Articles outside sections remain document-level articles. Annexes reference their section and may contain articles. IDs are deterministic within one prediction and document-scoped; they are not guaranteed stable after an upstream segmentation change.

All structural nodes expose physical page ranges. Evidence stores document ID, source page/element ID, original element text, optional bbox and coordinate system, page dimensions, and line index for multiline elements. A UI can resolve `document_id + page + bbox` or element ID. `source_order` retains allocation order of structural/content/requirement nodes; nested arrays preserve source order. TOC and furniture remain separate evidence collections.

## Detection and hierarchy

`LanguagePack` centralizes replaceable article, section, decimal subsection, clause, annex, title, TOC, special-document and requirement patterns. Default patterns focus on French with selected English equivalents; an Arabic pattern injection is tested. This is not a claim of full Arabic or English corpus coverage. No A/B/C/D titles or physical page numbers are hardcoded in the detector.

Heading kinds/levels from layout supplement numbering. Unnumbered layout headings remain probable sections with null numbers. A short bold or layout heading may complete a preceding number-only section/article/annex title. Decimal headings inside articles become clauses. Missing hierarchy levels attach to the nearest known ancestor and generate a diagnostic. Inline article references receive a conservative sentence guard; ambiguous OCR text can still require review. Source order, not page position sorting, controls the state machine.

An article extends over successive body pages until another article, section or annex. Parents extend with their descendants; same-page boundaries can legitimately overlap. An empty page extends an active range. Trailing furniture-only pages do not extend it. Paragraphs are source-line fragments; unnumbered continuations are retained but are not merged into semantic paragraphs across pages.

Explicit headers/footers and text repeated on at least three distinct pages in the same top/bottom 10% margin are excluded from structural detection. Evidence remains available. Repeated body text is not suppressed. Font size is accepted for future use; the baseline uses explicit heading levels/kinds and bold signals, not inferred font-size thresholds.

## TOC, tables and BOQ

TOC rows and dot-leader candidates supply evidence, never standalone sections. Body headings establish boundaries. Missing confirmations and different page numbers produce diagnostics; printed/physical page offsets are not guessed. TOC mode ends at the next physical page or explicit body heading. Untagged multi-page TOCs and dense tables with leader-like text remain limitations; producer TOC tagging improves these cases.

Tables stay upstream references with source evidence. Annex context or caption patterns classify known types; absent evidence stays `unknown`. No cell, quantity, price or total parsing occurs. BOQ and other special documents expose node ID and page range; BOQ entries carry `handoff="boq_agent"`. Page overlap is possible, so downstream consumers should also use node evidence. Special types are extensible via the language pack, including price schedules, submission/guarantee forms, declarations and technical sheets/specifications.

## Requirements, uncertainty and review

After structural assignment, conservative lexical rules emit candidate requirements from body lines with original wording and section/article/annex evidence. They include deadline, documents, execution/validity, guarantee, retention, penalty, payment, eligibility, technical conditions, VAT, evaluation, submission, buyer, reference, subject and lot. Absent categories produce no entry. Explicit numeric patterns may populate `normalized_value` and `unit`; these are `extracted_value` candidates, not legal interpretation. `reviewed_business_interpretation` remains null and `review_status` remains `needs_review` until human review. Headings alone do not create requirements. BOQ/price annex body lines and table contents do not enter requirement extraction.

Evidence states are `detected`, `probable`, `ambiguous`, `needs_review`; no fake confidence probabilities. Review overlays retain target ID, field, machine and reviewed values, reviewer and timestamp. Original nodes/evidence are not mutated automatically; review application/UI persistence is future work.

## Benchmark and future experiments

`benchmark.evaluate` requires a source-linked human verification manifest. Otherwise it returns `NOT YET MEASURABLE`. The real manifest is still `human_review_required`. Available metrics are exact multiset record precision/recall by category, including numbering, titles, parent path, range, type or source page. These strict metrics penalize hierarchy/range errors together; separate tolerant detection, boundary and classification diagnostics can be added once verified real labels exist. Synthetic unit tests are not corpus accuracy measurements.

`SemanticAnalyzer` is an optional evidence-only protocol over `TenderDocument`. A later model experiment can compare deterministic output against semantic assistance using the same independently verified dataset. No mandatory LLM, embeddings, vector database or RAG is included.
