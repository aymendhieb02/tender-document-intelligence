# Tunisian tender acquisition and seed curation

The scraper produces a public-source raw tender corpus for later human review. A `LIKELY_CDC` is a deterministic screening label, not ground truth or benchmark approval. The production analyzer is not run or changed by this package.

## Public collection policy

Only public pages and downloadable public files are eligible. Discovery is restricted to configured official source pages, same-host links, tender-related paths, configured page/depth limits, and `robots.txt`. Requests use a research User-Agent, bounded retries, timeouts, and a per-domain delay. A robots response that cannot be fetched (other than 404/410) causes the URL to be skipped. The collector never authenticates, solves CAPTCHAs, or accesses protected dossiers. TUNEPS remains disabled for document downloads; public metadata access and public file access are tracked separately in the source registry.

## Source registry and verification

`data/acquisition/sources.csv` is the source of truth. Each entry includes verification date, evidence/listing URL, public metadata status, document-download status, and limitations. Sixteen institutional sources were checked against their own public tender/publications pages on 2026-09-28. Fifteen are enabled; TUNEPS is disabled pending public dossier-download verification. Some enabled sources publish notices only or route documents through TUNEPS. Availability is recorded per row; a source's listing page does not imply every underlying dossier is public.

Public source evidence includes the Presidency [cahier listing](https://pm.gov.tn/fr/cahier-de-charge), MTC [tender notices](https://www.mtc.gov.tn/index.php?L=562&id=28), HAICOP [tender listing](https://www.marchespublics.gov.tn/fr/appels-doffres), Equipment Ministry [official portal](https://www.mehat.gov.tn/fr/), Tourism Ministry [tenders](https://www.tourisme.gov.tn/fr/categorie/appels-doffres/), SONEDE [public tenders](https://www.sonede.com.tn/mediatheque/marches-publics/), STEG [tender listings](https://www.steg.com.tn/fr/all-tenders), Social Affairs Ministry [tenders](https://www.social.gov.tn/fr/appels-doffres), ANCS [tenders and consultations](https://www.ancs.tn/fr/appels-doffres-et-consultations), OEP [official site](https://www.oep.tn/fr/), Tunis municipality [public operations](https://www.commune-tunis.gov.tn/operations-publiques.aspx), IGPPP [official portal](https://igppp.tn/fr), SNCFT [tenders](https://www.sncft.com.tn/category/appels-doffres/), OCT [tenders](https://www.oct.gov.tn/fr/avis-dappels-doffres), and ISGIS [tender page](https://isgis.rnu.tn/fr/appels-d-offres). Source-specific limitations are in the CSV.

The initial adapter classes preserve the shared interface. They delegate to the bounded generic HTML extractor; there are no claimed site-specific parsers without a reviewed local HTML fixture. The generic extractor follows only same-host tender-section paths and explicit pagination links, within `max_pages_per_source` and `max_depth`.

## Seed corpus curation

The user-provided extracted seed folder is read in place and is never modified. Generate/update its inventory and report with:

```powershell
python scripts/curate_seed_inventory.py --seed-dir "<extracted seed folder>"
```

Outputs are `seed_inventory.csv`, `seed_corpus_report.md`, and seed rejection rows in `rejected.csv`. Inventory paths are relative to the supplied folder; no absolute local path is recorded. The report counts unique PDFs after exact SHA-256 deduplication and separately retains duplicate history. Filename hints alone never promote a native-text file to `LIKELY_CDC`; the classifier samples native text on the first five pages plus middle/last pages, checks tender terminology, notice covers, repeated article structure, document length, and role-specific terms. A 97-page notice without sufficient article structure remains a notice/review. Native-text availability is a sample heuristic. No seed OCR is run; low/empty text is marked `REVIEW_NEEDS_OCR`, and its content SimHash is null.

Current seed findings are in the report. Organization/source provenance URLs were not supplied for the seed files; the directory label is only an organization grouping hint, not a verified source URL.

## Install and run

Python dependencies used here are `requests`, `beautifulsoup4`, and `PyMuPDF` (already present in the project dependency environment).

```powershell
python -m tools.tender_scraper sources validate
python -m tools.tender_scraper discover --source PM_TN --limit 20
python -m tools.tender_scraper download --dry-run --limit 5
python -m tools.tender_scraper download --limit 5
python -m tools.tender_scraper validate
python -m tools.tender_scraper report
```

`discover` records candidates and does not fetch document bodies. `download --dry-run` lists queued documents without downloading. `run --limit N` is intended for a small reviewed pilot; do not start the 100-document run until the pilot report has been inspected.

## Classification, duplicate handling, and records

A downloaded candidate is profiled with a small native-text sample; OCR is not run. A valid PDF must have a PDF signature and open with PyMuPDF. HTML error pages, oversized content, corrupt files, and exact duplicates are rejected with explicit reason codes. SimHash is computed only when normalized sampled text has at least 80 characters and 15 tokens; otherwise it is null and `near_duplicate_status=NOT_COMPARABLE`. Near matches remain for human review and are never silently deleted.

- `sources.csv`: verified source registry.
- `candidates.csv`: the authoritative resumability state. Stable candidate IDs derive from URL hashes; reruns preserve prior statuses and only add unseen URLs. There is no parallel `state.json`.
- `manifest.csv`: accepted likely-CDC documents only, with source/page/download URLs, SHA-256, relative file path, dossier ID, role, and pending review status.
- `rejected.csv`: durable rejection history (`candidate_id`, `source_id`, `url`, `reason_code`, `reason_detail`, timestamp); seed and crawler records remain in their original inventory/candidate files.
- `seed_inventory.csv` and `seed_corpus_report.md`: seed fingerprinting and curation profile.
- `corpus_stats.json` and `corpus_report.md`: accepted-corpus distributions and concentration warnings.
- `datasets/cdc_real/raw/`: downloadable PDFs, ignored by Git.
- `datasets/cdc_real/metadata/`: one provenance sidecar per accepted record.

The original stated `data.rar` was not present under the supplied folder; 26 extracted PDFs were inventoried there. Exact duplicates retain one canonical seed record, with duplicate rows linked by `exact_duplicate_of`.

## Quality measures

The old combined score is replaced by two transparent heuristics:

**Acquisition quality (0–100):** official source 25, valid PDF 30, complete source-page and download provenance 20, readable page count 20, and at least two pages 5. These measure traceability and file usability.

**Benchmark value (0–100, subjective triage only):** CDC likelihood 55, related-tender relevance 20, review/scan-needed 8, rejected 0; useful length 5–10; table cue 10; CDC-family structure 10; and text accessibility or a genuine scanned profile 5. Values are capped at 100. Relevance dominates length: a long notice cannot win just from its page count. This is not a claim of objective benchmark value. Humans must inspect accepted candidates and document-family fit.

## Diversity and pilot gate

Corpus statistics report source/organization, procurement family, document family, year, language, and native/scanned status. Any category above 60% is surfaced as a warning, not automatically rejected. Seed folder grouping currently shows heavy Presidency concentration and incomplete source provenance. Do not randomly split the corpus yet.

The prior pilot attempt was blocked by outbound proxy connectivity. Repeat it only after connectivity works. Target 5–10 accepted documents from at least three organizations and inspect candidates, manifest, rejection history, sidecars, and diversity before scaling. TUNEPS login/certificate workflows remain out of scope.
