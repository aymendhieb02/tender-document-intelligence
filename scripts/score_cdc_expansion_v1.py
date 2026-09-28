"""Score the newly exhaustive, source-reviewed CDC-DEV-001 annotation subsets."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cdc_analysis.benchmark import structural_records
from app.cdc_analysis.schema import TenderDocument

OUT = ROOT / "benchmarks" / "cdc_real_v1"


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def number(value):
    if isinstance(value, dict):
        if "numerator" in value and "denominator" in value:
            return (value["numerator"], value["denominator"])
        if "value" in value:
            return value["value"]
    return value


def main():
    gt = json.loads((OUT / "ground_truth" / "CDC-DEV-001.json").read_text(encoding="utf-8"))
    prediction = TenderDocument.model_validate_json(
        (OUT / "predictions_v2" / "CDC-DEV-001.prediction.json").read_text(encoding="utf-8"))
    records = structural_records(prediction)

    expected = gt["complete_article_inventory"]["expected_articles"]
    actual = records["articles"]
    ec = Counter((norm(x["number"]), x["physical_page"]) for x in expected)
    ac = Counter((norm(x["number"]), x["source_page"]) for x in actual)
    tp = sum((ec & ac).values())
    article = {"status": "EXHAUSTIVE_SOURCE_REVIEWED_INVENTORY", "expected": len(expected),
               "predicted": len(actual), "tp": tp, "fp": len(actual) - tp, "fn": len(expected) - tp,
               "precision": tp / len(actual) if actual else None,
               "recall": tp / len(expected) if expected else None}

    negatives = gt["reviewed_negative_candidates"]
    lots = [x for x in negatives if x["candidate_type"] == "major_section"]
    lot_hits = [x for x in lots if any(norm(s.number) == norm(re.search(r"Lot\s+(\d+)", x["raw_text"], re.I).group(1))
                                             and s.start_page == x["physical_page"]
                                             for s in prediction.sections)]
    refs = [x for x in negatives if x["candidate_type"] == "annex_heading"]
    annex_hits = [x for x in refs if any(a.get("start") == x["physical_page"] for a in records["annexes"])]
    decoys = [x for x in negatives if x["candidate_type"] == "guarantee_or_penalty_fact"]
    bad_fact_types = {"guarantee", "final_guarantee", "retention", "retention_guarantee",
                      "provisional_guarantee", "penalty", "delay_penalty", "delay_penalty_cap",
                      "penalty_rate", "penalty_cap", "deadline", "payment_term", "execution_deadline"}
    decoy_hits = [x for x in decoys if any(r.type in bad_fact_types and r.source_page == x["physical_page"]
                                             for r in prediction.requirements)]
    negative_metrics = {
        "status": "REVIEWED_CANDIDATE_NEGATIVES_ONLY",
        "lot_as_major_section": {"reviewed_negatives": len(lots), "incorrect_major_section_matches": len(lot_hits),
                                  "candidate_rejection_rate": (len(lots) - len(lot_hits)) / len(lots) if lots else None},
        "annex_reference_as_heading": {"reviewed_negatives": len(refs), "incorrect_heading_matches": len(annex_hits),
                                        "candidate_rejection_rate": (len(refs) - len(annex_hits)) / len(refs) if refs else None},
        "volume_variation_as_guarantee_or_penalty": {"reviewed_negatives": len(decoys), "incorrect_fact_matches": len(decoy_hits),
                                                      "candidate_rejection_rate": (len(decoys) - len(decoy_hits)) / len(decoys) if decoys else None}}

    facts = [x for x in gt["financial_deadline_subset"]["facts"] if x.get("normalized_value") is not None]
    aliases = {
        "offer_validity": {"offer_validity"}, "award_notification_deadline": {"deadline"},
        "final_guarantee_submission_deadline": {"deadline"}, "final_guarantee": {"final_guarantee", "guarantee"},
        "payment_schedule": {"payment_term", "payment_schedule"}, "retention_guarantee": {"retention_guarantee", "retention"},
        "retention_release_deadline": {"deadline", "retention"}, "payment_deadline": {"payment_term", "payment_deadline"},
        "penalty_rate": {"delay_penalty", "penalty_rate", "penalty"}, "penalty_cap": {"delay_penalty_cap", "penalty_cap", "penalty"},
        "remediation_deadline": {"deadline"}, "warranty_period": {"guarantee_period", "warranty", "guarantee"},
        "order_volume_variation": {"order_volume_variation"}, "variation_notice_deadline": {"deadline"}}
    detected = pages_correct = values_correct = exact_facts = 0
    for fact in facts:
        expected_article = f"article-{fact['article']}"
        candidates = [r for r in prediction.requirements if r.type in aliases[fact["fact_type"]]
                      and r.source_article == expected_article]
        if candidates:
            detected += 1
            on_page = [r for r in candidates if r.source_page == fact["physical_page"]]
            pages_correct += bool(on_page)
            value_hit = any(number(r.normalized_value) == number(fact["normalized_value"]) for r in on_page)
            values_correct += bool(on_page) and value_hit
            exact_facts += value_hit
    requirement_metrics = {"status": "EXHAUSTIVE_WITHIN_DECLARED_FACT_SCOPE; NOT A CORPUS_WIDE_REQUIREMENT_SCORE",
                          "scope": gt["financial_deadline_subset"]["scope"], "expected_nonblank_facts": len(facts),
                          "unresolved_blank_template_facts": sum(x.get("normalized_value") is None for x in gt["financial_deadline_subset"]["facts"]),
                          "facts_with_type_and_article_candidate": detected,
                          "candidate_coverage_within_scope": detected / len(facts) if facts else None,
                          "candidate_page_provenance_correct": pages_correct / detected if detected else None,
                          "normalized_value_correct_on_located_candidates": values_correct / pages_correct if pages_correct else None,
                          "exact_normalized_fact_recall_within_scope": exact_facts / len(facts) if facts else None}

    result = {"schema_version": "cdc_benchmark_expansion_metrics_v1", "source_document": "CDC-DEV-001",
              "prediction": "predictions_v2/CDC-DEV-001.prediction.json", "article_inventory": article,
              "negative_candidate_measurements": negative_metrics, "financial_deadline_subset": requirement_metrics,
              "boq_negative_examples": {"status": "NOT_MEASURED", "reason": "No locally available source-reviewed document without a BOQ was identified."},
              "scanned_arabic": {"document_id": "CDC-DEV-009", "ground_truth_status": "DRAFT", "scored": False}}
    (OUT / "metrics_expansion_v1.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
