# CDC deterministic baseline report

## Reference and status

**ENGINEERING BASELINE:** REAL DOCUMENT VALIDATED (`CDC_ANALYZER_BASELINE_V1`)

**GROUND TRUTH:** HUMAN REVIEW REQUIRED (`human_review_required`)

**BENCHMARK:** NOT YET MEASURABLE

The first real structural fixture is [the Tunisian maintenance tender PDF](../dataset/cdc/raw/MM_Cahier-des-charges-type-Entretien.pdf), SHA-256 `f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d`. The CDC consumer used the actual generic Document Intelligence result at `dataset/cdc/document_results/`; no OCR or PDF extraction code was changed for this analysis. The producer result contains 30 pages and 10,451 word elements, with native text on all pages, no OCR fallback, no replacement characters and no missing geometry.

Ground-truth manifest: **human_review_required**. It was drafted independently and the full PDF was visually inspected for source structure, but it is not marked human-verified or scored. The benchmark gate therefore correctly reports **NOT YET MEASURABLE**. Exact-row comparisons in the accompanying JSON are review aids only.

## Structural reconstruction

The prediction identifies document title and sections A–E. Physical page ranges: A 3–9 (27 articles), B 10–11 (9 articles), C 12–19 (4 parent technical topics with 8, 3, 5 and 4 decimal children), D 20–28, and E 29. Annexes 01–05 occupy pages 21–25; annex 06 occupies pages 26–28 and includes three numbered forms (6.1–6.3). Page 20 supplies the Annex 06 index title and evidence. Page 30 is detected as contact/back-cover material. The printed TOC/body titles for section D differ and are retained as a diagnostic; page ranges use physical source pages and are not hardcoded.

Annex 05 is the BOQ handoff: page 25, source node `annex-5`, `boq_agent`. This is a location/type handoff only; no BOQ rows or cells were extracted.

## Requirements and limits

The analyzer emits evidence-linked candidates, with numeric normalization limited to explicit patterns. Review candidates include 60-day offer validity, 3% final guarantee, 10% retention, 2/1000 daily delay penalty with 5% cap, one-year guarantee period, and 20% order-volume variation. Missing execution deadline and provisional guarantee remain null. All candidates require legal/business review; they are not adjudicated interpretations.

This adapter consumes the public DocumentResult contract and its upstream geometry rows, preserving opaque word IDs, raw text, rendered-page bboxes, source type, and nullable confidence in source evidence. It does not run OCR, extract PDF text, infer table contents or rely on this document's exact page numbers as general rules. Dense untagged TOCs, ambiguous headings and requirement semantics remain review-sensitive.

## Validation

`python -m pytest tests/cdc_analysis -q`: **28 passed**. The real-document integration checks section/article counts and ranges, technical hierarchy, annexes and subforms, BOQ handoff, evidence, selected normalized requirements and deterministic prediction parity. The benchmark remains gated pending an authorized human label review.
