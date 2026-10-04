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
