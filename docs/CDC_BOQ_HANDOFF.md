# CDC to BOQ handoff contract

The CDC analyzer owns whole-document structure and annex classification. When it detects a BOQ/price-schedule annex, it emits a `SpecialDocument` handoff with document ID (in the containing `TenderDocument`), source annex ID, title and annex page range, source node ID, classification (`document_type="boq"`), source evidence, and `handoff="boq_agent"`.

The handoff is evidence-linked and uses the detected annex's actual page range. It does not assume a fixed page number or annex number across tenders. For the current regression document, this happens to locate Annex 05 on physical page 25; that value is fixture evidence, never a general rule.

The CDC analyzer does not emit BOQ article rows, quantities, prices, totals, reconstructed cells, or row-level financial interpretations. Agent 3/`boq_agent` owns those operations after resolving the source node and evidence against the DocumentResult.

The downstream consumer should treat page ranges and evidence as pointers into the same document ID, retain uncertainty for ambiguous classifications, and report a contract mismatch if required producer evidence is unavailable. The CDC layer must not reach into OCR or PDF extraction internals to fill a gap.
