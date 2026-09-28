import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "cdc_real_v1"


def test_expansion_adds_complete_article_and_scoped_fact_inventories():
    gt = json.loads((BENCHMARK / "ground_truth" / "CDC-DEV-001.json").read_text(encoding="utf-8"))
    inventory = gt["complete_article_inventory"]
    assert inventory["status"] == "VERIFIED"
    assert inventory["count"] == len(inventory["expected_articles"]) == 36
    assert sum(x["section"] == "A" for x in inventory["expected_articles"]) == 27
    assert sum(x["section"] == "B" for x in inventory["expected_articles"]) == 9
    assert gt["financial_deadline_subset"]["status"] == "VERIFIED"
    assert sum(x.get("normalized_value") is None for x in gt["financial_deadline_subset"]["facts"]) == 1


def test_expansion_metrics_are_scoped_and_keep_arabic_scan_draft():
    metrics = json.loads((BENCHMARK / "metrics_expansion_v1.json").read_text(encoding="utf-8"))
    assert metrics["article_inventory"]["tp"] == 36
    assert metrics["article_inventory"]["fp"] == 0
    assert metrics["article_inventory"]["fn"] == 0
    assert metrics["financial_deadline_subset"]["expected_nonblank_facts"] == 14
    assert metrics["financial_deadline_subset"]["exact_normalized_fact_recall_within_scope"] == 9 / 14
    assert metrics["negative_candidate_measurements"]["lot_as_major_section"]["reviewed_negatives"] == 8
    assert metrics["negative_candidate_measurements"]["annex_reference_as_heading"]["reviewed_negatives"] == 6
    assert metrics["boq_negative_examples"]["status"] == "NOT_MEASURED"
    assert metrics["scanned_arabic"]["ground_truth_status"] == "DRAFT"
    assert metrics["scanned_arabic"]["scored"] is False
