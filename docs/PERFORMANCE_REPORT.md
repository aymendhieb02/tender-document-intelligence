# Performance report

Date: 2026-10-04. Measurements are local single-run observations, not service-level guarantees.

## Reference document

Input: `datasets/boq/male_municipal_maintenance_v1/reference/MM_Cahier-des-charges-type-Entretien.pdf` (30 pages).

Measured with `DocumentProcessor`, then `CDCAnalyzer`, then the specialized BOQ extractor on detected handoff pages. Warm local environment, native text available on every page.

| Stage | Measured |
| --- | ---: |
| Document Intelligence wall time | 583 ms (reported pipeline 583 ms) |
| PDF load | 6 ms |
| Native extraction | 431 ms |
| Layout | 123 ms |
| OCR / render / preprocessing | 0 ms |
| CDC analysis | 296 ms |
| Specialized BOQ pages | 6 ms |
| DI + CDC + BOQ total | 885 ms |
| Ask Tender evidence retrieval | 568 ms |
| Optional Ollama generation attempt | 2,030 ms; unavailable |
| Ask Tender total wall time | 2,598 ms |

The per-stage sums are rounded. A separate run measured total DI/CDC/BOQ as 885 ms. The file contains 10,451 native evidence elements, 30 physical pages, 0 OCR pages and 0 fallback pages. Specialized BOQ status was detected, 5 empty structural rows, all NOT_CHECKABLE for monetary checks.

Ask Tender now logs retrieval and local generation separately (`app.ask_tender.service`). Analysis requests log Document Intelligence, CDC, BOQ and response stages. Persisted result retrieval reads compact JSON and does not invoke PDF parsing/OCR.

## Interpretation

This is a digital, searchable reference template, so the measurement says little about scanned 30–100 page tenders. OCR model startup/cache state, image complexity, page size and local hardware can dominate scanned-document time. Ollama latency is independent of deterministic retrieval and varies by model/host; the measured local service was unavailable after about two seconds.

## Bottlenecks and next measurements

1. Collect scanned and mixed native/scanned tender fixtures and measure cold/warm OCR separately.
2. Measure CDC structure and Ask retrieval against longer real tenders, including citation coverage and relevance review.
3. Track persistence serialization/restore at larger evidence volumes before increasing document limits.
4. Evaluate local Ollama only with controlled prompts, model/version recording and answer-grounding review.

## 2026-10-05 warm local remeasurement

One sequential final-code run of the same 30-page native PDF measured Document Intelligence 530.0 ms, CDC 270.6 ms, BOQ candidate scan 248.5 ms across all 30 pages, V2 composition 611.6 ms, and Ask evidence retrieval 1037.6 ms for six passages. A five-row pricing calculation took 1.478 ms; pricing CSV assembly took 0.096 ms; JSON serialization plus temporary write of the 3.53 MB response took 54.2 ms and reload/parse 34.1 ms. These are one-run observations on this host, not latency guarantees. This broader BOQ scan includes generic candidate checks on all pages, so it is not directly comparable with the earlier 6 ms specialized-page-only figure.

The persisted API paths for Ask, pricing GET/PUT, pricing CSV, and library reopen operate on saved analysis; API tests replace `DocumentProcessor` with a failing stub on reload to detect duplicate processing. Browser refresh and library reopen restored the pricing draft. Scanned/OCR performance remains unmeasured here.
