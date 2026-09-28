"""Apply explicit source-reviewed metadata to a hash inventory; omit unknowns."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "cdc_real_v1"


def main() -> None:
    review = json.loads((OUT / "curation_review.json").read_text(encoding="utf-8"))
    path = OUT / "corpus_manifest.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
        fields = list(rows[0])
    for row in rows:
        details = review["documents"].get(row["document_id"])
        if not details:
            continue
        for key in ("document_role", "organization", "procurement_type", "language", "tender_reference", "year", "dossier_id", "review_status"):
            row[key] = "" if details.get(key) is None else str(details.get(key, ""))
        if row["document_id"] == "CDC-DEV-005":
            row["tender_reference"], row["year"] = "18/2025", "2025"
        if row["document_id"] == "CDC-DEV-001":
            row["organization"] = ""
        row["role_evidence"] = " | ".join(
            f"p{item['physical_page']}: {item['raw_text']}" for item in details.get("role_evidence", []))
        row["notes"] = details.get("notes", "")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    role_counts = {}
    for row in rows:
        role = row["document_role"] or "UNKNOWN"
        role_counts[role] = role_counts.get(role, 0) + 1
    summary = json.loads((OUT / "reconciliation.json").read_text(encoding="utf-8"))
    summary["curated_role_counts"] = role_counts
    summary["review_status_counts"] = {
        status: sum(r["review_status"] == status for r in rows)
        for status in sorted({r["review_status"] for r in rows})
    }
    (OUT / "reconciliation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"curated_role_counts": role_counts, "review_status_counts": summary["review_status_counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
