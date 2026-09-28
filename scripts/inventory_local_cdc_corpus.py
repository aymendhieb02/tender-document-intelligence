"""Hash and reconcile a local tender PDF tree without copying or editing source files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import fitz


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="Local folder containing source PDFs")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/cdc_real_v1"))
    parser.add_argument("--seed-inventory", type=Path, default=Path("data/acquisition/seed_inventory.csv"))
    args = parser.parse_args()
    corpus = args.corpus.resolve(strict=True)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    with args.seed_inventory.open(encoding="utf-8-sig", newline="") as stream:
        seed_rows = list(csv.DictReader(stream))
    seed_hashes = {row["sha256"] for row in seed_rows}

    rows = []
    bad = []
    hashes: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(corpus.rglob("*")):
        if not path.is_file() or path.suffix.casefold() != ".pdf":
            continue
        rel = path.relative_to(corpus).as_posix()
        sha = digest(path)
        item = {"relative_path": rel, "filename": path.name, "sha256": sha, "size_bytes": path.stat().st_size}
        try:
            with fitz.open(path) as pdf:
                if pdf.needs_pass or len(pdf) < 1:
                    raise ValueError("encrypted or empty PDF")
                page_text = [page.get_text().strip() for page in pdf]
                text_pages = sum(bool(text) for text in page_text)
                item.update({
                    "valid_pdf": True,
                    "page_count": len(pdf),
                    "text_pages": text_pages,
                    "native_text_availability": "native" if text_pages == len(pdf) else "mixed" if text_pages else "scanned",
                    "title_page_text": page_text[0][:1200] if page_text else "",
                    "page_2_text": page_text[1][:1200] if len(page_text) > 1 else "",
                    "last_page_text": page_text[-1][:1200] if page_text else "",
                })
        except Exception as exc:
            item.update({"valid_pdf": False, "page_count": None, "text_pages": None,
                         "native_text_availability": "unknown", "validation_error": type(exc).__name__})
            bad.append(item)
        rows.append(item)
        hashes[sha].append(item)

    unique_groups = {sha: group for sha, group in hashes.items() if all(x["valid_pdf"] for x in group)}
    ids = {sha: f"CDC-DEV-{n:03d}" for n, sha in enumerate(
        sorted(unique_groups, key=lambda value: (value != "f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d", value)), 1)}
    fields = ["document_id", "sha256", "filename", "relative_path", "size_bytes", "page_count",
              "native_text_availability", "text_pages", "agent6_reconciliation", "review_status",
              "document_role", "role_evidence", "organization", "procurement_type", "language",
              "tender_reference", "year", "dossier_id", "notes"]
    with (out / "corpus_manifest.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for sha, group in sorted(unique_groups.items(), key=lambda pair: ids[pair[0]]):
            item = group[0]
            match = sha in seed_hashes
            writer.writerow({
                "document_id": ids[sha], "sha256": sha, "filename": item["filename"],
                "relative_path": item["relative_path"], "size_bytes": item["size_bytes"],
                "page_count": item["page_count"], "native_text_availability": item["native_text_availability"],
                "text_pages": item["text_pages"],
                "agent6_reconciliation": "MATCHED_AGENT6" if match else "NEW_LOCAL_DOCUMENT",
                "review_status": "DRAFT_CONTENT_REVIEW_REQUIRED", "document_role": "UNKNOWN",
                "role_evidence": "", "organization": "", "procurement_type": "", "language": "",
                "tender_reference": "", "year": "", "dossier_id": "",
                "notes": "Acquisition hints intentionally not promoted to curated labels.",
            })

    duplicate_groups = [{"sha256": sha, "kept_document_id": ids[sha],
                        "files": [item["relative_path"] for item in group]}
                       for sha, group in sorted(hashes.items()) if len(group) > 1]
    missing = sorted(seed_hashes - set(hashes))
    report = {
        "corpus": "CDC_DEVELOPMENT_CORPUS_V1",
        "files_found": len(rows), "valid_pdfs": sum(item["valid_pdf"] for item in rows),
        "unique_valid_pdfs": len(unique_groups),
        "exact_duplicate_files": sum(len(group) - 1 for group in hashes.values() if len(group) > 1),
        "invalid_pdfs": len(bad),
        "matched_agent6_unique": sum(sha in seed_hashes for sha in unique_groups),
        "new_local_unique": sum(sha not in seed_hashes for sha in unique_groups),
        "missing_from_agent6_local": len(missing),
        "missing_agent6_hashes": missing,
        "duplicates": duplicate_groups,
        "invalid_files": bad,
        "seed_inventory_rows": len(seed_rows),
        "note": "File paths are relative to the user-provided corpus root. Role and language fields await content review.",
    }
    (out / "reconciliation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "files_found", "valid_pdfs", "unique_valid_pdfs", "exact_duplicate_files", "invalid_pdfs",
        "matched_agent6_unique", "new_local_unique", "missing_from_agent6_local")}, indent=2))


if __name__ == "__main__":
    main()
