"""Build audit records for the Agent 7 seed corpus without promoting heuristics."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "cdc_real_v1"
SOURCE = ROOT / "data" / "acquisition" / "seed_inventory.csv"
AVAILABLE = ROOT / "dataset" / "cdc" / "raw" / "MM_Cahier-des-charges-type-Entretien.pdf"
DOC_ID = "f3b99c74d7d1fad9cd438869be1aa8e19d2329d99e28900c444cc3f0b3b8545d"


def main() -> None:
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        unique.setdefault(row["sha256"], row)
    ordered = sorted(unique.items(), key=lambda item: (item[0] != DOC_ID, item[0]))

    columns = [
        "document_id", "filename", "sha256", "page_count", "organization", "language",
        "text_profile", "document_role", "document_role_evidence", "procurement_type",
        "year", "tender_reference", "dossier_id", "review_status", "available_locally", "notes",
    ]
    manifest = []
    for index, (sha, row) in enumerate(ordered, start=1):
        present = sha == DOC_ID and AVAILABLE.is_file()
        manifest.append({
            "document_id": f"CDC-DEV-{index:03d}",
            "filename": row["filename"],
            "sha256": sha,
            "page_count": row["page_count"] if present else "",
            "organization": "" if row["organization"] == "UNKNOWN" else row["organization"],
            "language": row["language_hint"] if present else "UNKNOWN",
            "text_profile": ("native" if row["native_text_available"] == "True" else "scanned") if present else "UNKNOWN",
            "document_role": "CDC" if present else "UNKNOWN",
            "document_role_evidence": "Title page: Cahiers de charge type; visual review pending" if present else "",
            "procurement_type": row["procurement_type"] if present else "UNKNOWN",
            "year": row["year_hint"] if present and row["year_hint"] != "UNKNOWN" else "",
            "tender_reference": "",
            "dossier_id": "",
            "review_status": "HUMAN_REVIEW_REQUIRED" if present else "UNAVAILABLE_PENDING_REVIEW",
            "available_locally": str(present).lower(),
            "notes": f"Acquisition hint only; unverified: role={row['document_role']}, language={row['language_hint']}, procurement={row['procurement_type']}, organization={row['organization']}. {row['notes']}",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "corpus_manifest.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(manifest)

    prediction_path = OUT / "predictions" / "MM_Cahier-des-charges-type-Entretien.prediction.json"
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    result = {
        "corpus": "CDC_DEVELOPMENT_CORPUS_V1",
        "baseline": "CDC_ANALYZER_REAL_BASELINE_V1",
        "tested_commit": "a0f4e31f04540a7901ba0c956fbc5919faf4ab5e",
        "execution_scope": "CDC Analyzer on existing DocumentResult sidecar; PDF-to-Document-Intelligence was not rerun",
        "documents": [{
            "document_id": "CDC-DEV-001",
            "sha256": DOC_ID,
            "prediction_file": "predictions/MM_Cahier-des-charges-type-Entretien.prediction.json",
            "ground_truth_status": "HUMAN_REVIEW_REQUIRED",
            "scored": False,
            "prediction_counts": {
                "top_level_sections": len(prediction.get("sections", [])),
                "top_level_articles": len(prediction.get("articles", [])),
                "annexes": len(prediction.get("annexes", [])),
                "requirements": len(prediction.get("requirements", [])),
                "detected_special_documents": len(prediction.get("detected_special_documents", [])),
            },
        }],
        "gate_result": "NOT YET MEASURABLE: Human-verified source-linked labels required",
    }
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics = {
        "status": "NOT_MEASURABLE",
        "reason": "No source-linked ground truth has passed human visual verification; do not treat pending labels as negatives.",
        "section_precision": None, "section_recall": None,
        "article_precision": None, "article_recall": None,
        "annex_precision": None, "annex_recall": None,
        "requirement_precision": None, "requirement_recall": None,
        "normalized_value_correctness": None,
        "page_provenance_accuracy": None,
        "boq_detection": None,
        "native_performance": None, "scanned_performance": None,
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    failures = {
        "status": "NO_VERIFIED_FAILURES_ASSERTED",
        "reason": "The pending labels cannot establish correct or incorrect analyzer behavior.",
        "failures": [],
        "evaluation_blockers": [
            {"category": "MISSING_SOURCE_CORPUS", "detail": "24 of 25 unique seed PDFs are unavailable in this checkout."},
            {"category": "HUMAN_REVIEW_REQUIRED", "detail": "Available structure annotation requires page-by-page visual verification."},
            {"category": "INCOMPLETE_PIPELINE_RUN", "detail": "Document Intelligence/OCR was not rerun from source PDF."},
        ],
    }
    (OUT / "failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    print(f"seed_rows={len(rows)} unique_seed_files={len(unique)} available_seed_pdfs={sum(r['available_locally'] == 'true' for r in manifest)}")


if __name__ == "__main__":
    main()
