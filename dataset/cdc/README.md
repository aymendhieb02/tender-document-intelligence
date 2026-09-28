# CDC dataset

- `raw/`: source PDF plus the synthetic consumer-contract fixture. The real first fixture is `MM_Cahier-des-charges-type-Entretien.pdf` (SHA-256 recorded in its ground-truth manifest).
- `document_results/`: actual generic Document Intelligence producer JSON for the reference PDF. Reproduce using the existing producer workflow; CDC analysis consumes this interface and does not run OCR/PDF extraction.
- `ground_truth/`: independently drafted source annotations, currently `human_review_required`. Human review and reviewer/date are required before benchmark scoring.
- `predictions/`: deterministic analyzer output and review aids, never ground truth. Run `.venv/Scripts/python.exe -m app.cdc_analysis dataset/cdc/document_results/MM_Cahier-des-charges-type-Entretien.document_result.json --output dataset/cdc/predictions/MM_Cahier-des-charges-type-Entretien.prediction.json`.

The source spans 30 pages. The prediction reconstructs sections A–E, numbered articles, technical decimal hierarchy, six annexes including nested Annex 06 forms, and a BOQ location handoff for Annex 05. It does not parse BOQ rows. Exact-row comparison files are annotation-review aids and are not accuracy scores until labels are human-verified.
