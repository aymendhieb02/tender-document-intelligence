# Future general BOQ extractor

The future general extractor will handle unknown geometry, headers, column counts, currencies, HT/TTC patterns and eventually multi-page tables. It may use semantic header mapping and layout/table models only after a benchmark against the deterministic baseline on the same independently labeled ground truth. The specialized detector, `DocumentPage` adapter, canonical `BOQDocument`/`BOQRow`, `ParsedValue`, provenance, Decimal normalization, validation checks and evaluation harness are reusable interfaces. General extraction is not implemented in this phase.
