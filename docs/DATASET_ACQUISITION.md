# Tunisian tender dataset acquisition

This package collects a small, reproducible corpus of public Tunisian tender documents for later human curation. It does not create benchmark ground truth and does not modify the production analysis workflows. `review_status` remains `PENDING` until a human approves a record.

## Public data policy

Only public pages and documents are eligible. The crawler observes `robots.txt`, uses a descriptive research User-Agent, waits between requests, bounds pages and depth, and does not authenticate, bypass CAPTCHAs, or evade access controls. A robots block is recorded as `ACCESS_RESTRICTED`. TUNEPS is listed disabled because public notice access does not establish that dossier downloads are openly available; do not automate certificate or account workflows. Public source availability does not imply a reuse license; each record retains a source access note.

## Sources

`data/acquisition/sources.csv` is authoritative. URLs were checked on 2026-09-28 against the respective public institutional pages: Government Presidency ([cahier listing](https://pm.gov.tn/fr/cahier-de-charge)), MTC ([tender notices](https://www.mtc.gov.tn/index.php?L=50&id=28)), HAICOP ([tender listing](https://www.marchespublics.gov.tn/fr/appels-doffres)), and Equipment Ministry ([official site](https://www.mehat.gov.tn/fr/)). TUNEPS ([training/public information portal](https://formation.tuneps.tn/)) is registered but disabled pending public document access review. The source notes contain verification dates and limitations.

## Run

From the repository root with Python dependencies installed (`requests`, `beautifulsoup4`, `PyMuPDF`):

```powershell
python -m tools.tender_scraper sources validate
python -m tools.tender_scraper discover --source PM_TN --limit 20
python -m tools.tender_scraper download --dry-run --limit 5
python -m tools.tender_scraper download --limit 5
python -m tools.tender_scraper validate
python -m tools.tender_scraper report
python -m tools.tender_scraper run --limit 100
```

`discover` is read-only except for the candidate registry. `--dry-run` lists queued downloads without fetching document bodies. Discovery follows only same-domain links in tender-related paths and is capped by configured depth/pages. Adapters share the interface in `tools/tender_scraper/adapters/base.py`; `generic_official` uses conservative HTML link extraction. Add an adapter when a public source has a stable, documented structure, and keep access restrictions explicit.

## Records and storage

- `data/acquisition/sources.csv`: trusted-source registry.
- `candidates.csv`: discovered links and state, one row per URL. Transient failures can be retried; permanent HTTP 404 and access-restricted 403 are not looped.
- `manifest.csv`: accepted records with provenance, relative path, SHA-256, profile, score, and `review_status`.
- `rejected.csv`: reserved for rejected record export (rejection reasons are presently retained on candidate rows).
- `state.json`: reserved for explicit state snapshots; candidate download statuses are currently the resumability source of truth.
- `seed_inventory.csv`: inventory of the user-provided extracted seed directory. Its original files are never moved or changed. The stated `data.rar` was not present; the supplied directory contained 26 PDFs, all readable, with one exact duplicate.
- `datasets/cdc_real/raw/`: downloaded PDFs (ignored by Git).
- `datasets/cdc_real/metadata/`: JSON provenance sidecars.

Exact duplicate SHA-256 values are rejected. Different hashes are not removed as near-duplicates; implement or add human similarity review before accepting that feature. A successful HTTP transfer must start with `%PDF-` and open with PyMuPDF. HTML error pages and oversized documents are rejected. Only small text samples are extracted, without OCR.

## Classification and quality

Deterministic lexical signals classify likely CDC vs related tender documents; this is a triage aid, never a ground-truth label. The transparent score is 20 points for official source, up to 30 for CDC likelihood (15 for related tender), up to 15 for a document with at least five pages (5 for any pages), 15 for native text or 8 for likely scanned, 10 for a title hint, and 10 for table cues; exact duplicates lose 50 points. Score is clamped to 0–100: HIGH ≥75, MEDIUM ≥50, otherwise LOW. Scanned PDFs are eligible. The current implementation admits likely CDCs to the manifest and leaves uncertain candidates in `REVIEW`.

The report groups the manifest by organization, organization type, procurement type, document type, language, and score tier. It warns when fewer than three organizations are represented. It does not randomly split a corpus; later benchmark selection should preserve source provenance and be based on inspected diversity.

## Limits

The initial pilot is intended to cover only a few sources and documents. Some portal pages are JavaScript-rendered, some dossier links may be access-controlled, and some official source pages contain notices rather than the underlying cahier itself. The generic adapter may miss these; it must not be expanded to whole-site crawling. Review the pilot manifest, duplicates, metadata, and diversity before a larger run.
