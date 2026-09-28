"""Guard the source-reviewed scope and draft-label gate of the real CDC baseline."""
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "cdc_real_v1"


def test_local_inventory_reconciles_hashes_without_inflating_unique_count():
    reconciliation = json.loads((BENCHMARK / "reconciliation.json").read_text(encoding="utf-8"))
    assert reconciliation["files_found"] == 26
    assert reconciliation["valid_pdfs"] == 26
    assert reconciliation["unique_valid_pdfs"] == 25
    assert reconciliation["exact_duplicate_files"] == 1
    assert reconciliation["invalid_pdfs"] == 0
    assert reconciliation["matched_agent6_unique"] == 25
    assert reconciliation["new_local_unique"] == 0
    assert reconciliation["missing_from_agent6_local"] == 0


def test_scores_do_not_promote_positive_samples_or_draft_scan_to_full_metrics():
    metrics = json.loads((BENCHMARK / "metrics.json").read_text(encoding="utf-8"))
    results = json.loads((BENCHMARK / "results.json").read_text(encoding="utf-8"))
    assert metrics["article_precision"] is None
    assert metrics["article_recall"] is None
    assert metrics["requirement_precision"] is None
    assert metrics["scanned_performance"].startswith("1 full 37-page exploratory run")
    scan = next(doc for doc in results["documents"] if doc["document_id"] == "CDC-DEV-009")
    assert scan["ground_truth_status"] == "DRAFT"
    assert scan["scored"] is False
    assert scan["evidence_sources"] == ["paddleocr"]
    assert results["ground_truth"]["verified_documents"] == 6


def test_manifest_uses_relative_source_paths_and_curated_roles():
    with (BENCHMARK / "corpus_manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 25
    assert sum(row["document_role"] == "DAO" for row in rows) == 14
    assert sum(row["document_role"] == "NOTICE" for row in rows) == 5
    assert all(not Path(row["relative_path"]).is_absolute() for row in rows)


def test_failure_examples_have_source_evidence_and_draft_scan_is_disclaimed():
    failures = json.loads((BENCHMARK / "failures.json").read_text(encoding="utf-8"))
    assert failures["status"] == "VERIFIED_SUBSET_FAILURES"
    assert len(failures["recurring_patterns"]) >= 2
    assert all(example["source_evidence"] for example in failures["failures"])
    scan = next(example for example in failures["failures"] if example["document_id"] == "CDC-DEV-009")
    assert scan["label_status"] == "DRAFT_EXPLORATORY_NOT_SCORED"
