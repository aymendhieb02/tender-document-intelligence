"""Score only source-reviewed annotation categories; pending labels stay unscored."""
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


def ratio(correct: int, denominator: int) -> float | None:
    return correct / denominator if denominator else None


def norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold()).strip()


def number(value):
    if isinstance(value, dict):
        for key in ("value", "numerator"):
            if key in value:
                return number(value[key])
    if isinstance(value, (int, float)):
        return value
    return value


ALIASES = {
    "offer_validity": {"offer_validity", "deadline"},
    "final_guarantee": {"final_guarantee", "guarantee"},
    "retention_guarantee": {"retention_guarantee", "retention"},
    "payment_deadline": {"payment_term", "payment_deadline"},
    "payment_schedule": {"payment_term", "payment_schedule"},
    "penalty_cap": {"delay_penalty_cap", "penalty_cap", "penalty"},
    "penalty_rate": {"delay_penalty", "penalty_rate", "penalty"},
    "late_penalty_rate": {"delay_penalty", "penalty_rate", "penalty"},
    "provisional_guarantee": {"provisional_guarantee", "guarantee"},
    "submission_deadline": {"deadline", "submission_deadline"},
    "delivery_deadline": {"execution_deadline", "deadline"},
    "warranty": {"guarantee_period", "warranty", "guarantee"},
    "production_quantity": {"quantity", "production_quantity", "technical_requirement"},
    "print_run": {"quantity", "production_quantity", "technical_requirement"},
    "page_count": {"quantity", "technical_requirement"},
}


def main() -> None:
    gt_paths = sorted((OUT / "ground_truth").glob("CDC-DEV-*.json"))
    verified = []
    predictions = {}
    for path in gt_paths:
        gt = json.loads(path.read_text(encoding="utf-8"))
        if gt.get("status") != "VERIFIED":
            continue
        verified.append(gt)
        prediction_path = OUT / "predictions" / f"{gt['corpus_document_id']}.prediction.json"
        if prediction_path.exists():
            predictions[gt["corpus_document_id"]] = TenderDocument.model_validate_json(
                prediction_path.read_text(encoding="utf-8"))

    # Major sections are scored only for documents whose complete major-section list was reviewed.
    section_counts = Counter()
    section_documents = []
    for gt in verified:
        expected = gt.get("expected_major_sections") or []
        if not expected:
            continue
        doc_id = gt["corpus_document_id"]
        prediction = predictions.get(doc_id)
        if prediction is None:
            continue
        actual = [{"number": x.number, "start": x.start_page} for x in prediction.sections]
        exp = [{"number": x["number"], "start": x["physical_page_start"]} for x in expected]
        ec = Counter((norm(x["number"]), x["start"]) for x in exp)
        ac = Counter((norm(x["number"]), x["start"]) for x in actual)
        tp = sum((ec & ac).values())
        fp, fn = len(actual) - tp, len(exp) - tp
        section_counts.update(tp=tp, fp=fp, fn=fn)
        section_documents.append({"document_id": doc_id, "tp": tp, "fp": fp, "fn": fn,
                                  "expected": len(exp), "predicted": len(actual)})

    # Annex labels are complete for the three manually reviewed BOQ/form-bearing PDFs.
    annex_counts = Counter()
    annex_documents = []
    for gt in verified:
        expected = gt.get("expected_annexes") or []
        if not expected:
            continue
        doc_id = gt["corpus_document_id"]
        prediction = predictions.get(doc_id)
        if prediction is None:
            continue
        actual = structural_records(prediction)["annexes"]
        # This fully reviewed annotation set closes annex identity and start-page labels;
        # page-range ends remain descriptive evidence, not part of this score.
        ec = Counter((norm(x["number"]), x.get("physical_page_start")) for x in expected)
        ac = Counter((norm(x.get("number")), x.get("start")) for x in actual)
        tp = sum((ec & ac).values())
        fp, fn = len(actual) - tp, len(expected) - tp
        annex_counts.update(tp=tp, fp=fp, fn=fn)
        annex_documents.append({"document_id": doc_id, "tp": tp, "fp": fp, "fn": fn,
                                "expected": len(expected), "predicted": len(actual)})

    # The article annotations are deliberately examples, not a complete negative set.
    article_examples = Counter()
    article_example_documents = []
    for gt in verified:
        examples = gt.get("article_heading_examples") or []
        if not examples:
            continue
        doc_id = gt["corpus_document_id"]
        prediction = predictions.get(doc_id)
        if prediction is None:
            continue
        actual = structural_records(prediction)["articles"]
        ac = Counter((norm(x.get("number")), x.get("source_page")) for x in actual)
        ec = Counter((norm(x.get("number")), x.get("physical_page")) for x in examples)
        matched = sum((ec & ac).values())
        article_examples.update(matched=matched, expected=len(examples))
        article_example_documents.append({"document_id": doc_id, "matched_examples": matched,
                                          "expected_examples": len(examples)})

    requirement_counts = Counter()
    requirement_documents = []
    for gt in verified:
        facts = gt.get("important_requirements") or []
        if not facts:
            continue
        doc_id = gt["corpus_document_id"]
        prediction = predictions.get(doc_id)
        if prediction is None:
            continue
        rows = prediction.requirements
        matched = value_correct = page_correct = 0
        for fact in facts:
            aliases = ALIASES.get(fact["requirement_type"], {fact["requirement_type"]})
            candidates = [x for x in rows if x.type in aliases]
            expected_value = number(fact.get("normalized_value"))
            if candidates:
                matched += 1
                page_candidates = [x for x in candidates if x.source_page == fact["physical_page"]]
                if page_candidates:
                    page_correct += 1
                if expected_value is None or any(number(x.normalized_value) == expected_value for x in page_candidates):
                    value_correct += 1
        requirement_counts.update(detected=matched, expected=len(facts), values_correct=value_correct,
                                  pages_correct=page_correct)
        requirement_documents.append({"document_id": doc_id, "detected": matched,
            "expected": len(facts), "normalized_values_correct": value_correct,
            "page_attributions_correct": page_correct})

    boq_counts = Counter()
    boq_documents = []
    for gt in verified:
        boq = gt.get("boq", {})
        if boq.get("boq_present") is not True:
            continue
        doc_id = gt["corpus_document_id"]
        prediction = predictions.get(doc_id)
        if prediction is None:
            continue
        actual = [x for x in structural_records(prediction)["annexes"]
                  if x.get("annex_type") in {"boq", "price_schedule"}]
        expected_pages = set(boq.get("pages", []))
        actual_pages = {page for item in actual for page in range(item["start"], item["end"] + 1)}
        present = bool(actual)
        page_hit = bool(expected_pages & actual_pages)
        boq_counts.update(tp=int(present), fn=int(not present), page_hit=int(page_hit), evaluated=1)
        boq_documents.append({"document_id": doc_id, "expected_present": True,
                              "predicted_present": present, "page_overlap": page_hit,
                              "expected_pages": sorted(expected_pages), "predicted_pages": sorted(actual_pages)})

    metrics = {
        "status": "MEASURED_ON_VERIFIED_SUBSETS",
        "coverage_note": "Section/annex metrics use only categories with complete source-reviewed labels. Article and requirement records are curated positive examples, so precision is not measurable; their recall/sample hit rate is reported only as an evidence count.",
        "section_precision": ratio(section_counts["tp"], section_counts["tp"] + section_counts["fp"]),
        "section_recall": ratio(section_counts["tp"], section_counts["tp"] + section_counts["fn"]),
        "section_counts": dict(section_counts),
        "article_precision": None,
        "article_recall": None,
        "article_heading_sample_recall": ratio(article_examples["matched"], article_examples["expected"]),
        "article_heading_sample_counts": dict(article_examples),
        "annex_precision": ratio(annex_counts["tp"], annex_counts["tp"] + annex_counts["fp"]),
        "annex_recall": ratio(annex_counts["tp"], annex_counts["tp"] + annex_counts["fn"]),
        "annex_counts": dict(annex_counts),
        "requirement_precision": None,
        "requirement_recall_on_verified_fact_samples": ratio(requirement_counts["detected"], requirement_counts["expected"]),
        "requirement_counts": dict(requirement_counts),
        "normalized_value_correctness_on_detected": ratio(requirement_counts["values_correct"], requirement_counts["detected"]),
        "page_provenance_accuracy_on_detected": ratio(requirement_counts["pages_correct"], requirement_counts["detected"]),
        "boq_presence_recall": ratio(boq_counts["tp"], boq_counts["evaluated"]),
        "boq_page_detection_recall": ratio(boq_counts["page_hit"], boq_counts["evaluated"]),
        "native_performance": "reported via per-document source profile; no aggregate modality accuracy claim",
        "scanned_performance": "1 full 37-page exploratory run; ground truth remains draft, so accuracy is not measurable",
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    old = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    old["ground_truth"] = {"verified_documents": len(verified),
                           "draft_documents": sum(json.loads(p.read_text(encoding="utf-8")).get("status") == "DRAFT" for p in gt_paths),
                           "section_documents_scored": section_documents,
                           "annex_documents_scored": annex_documents,
                           "article_heading_examples": article_example_documents,
                           "requirement_fact_samples": requirement_documents,
                           "boq_documents_scored": boq_documents}
    for row in old.get("documents", []):
        gt_file = OUT / "ground_truth" / f"{row['document_id']}.json"
        if gt_file.exists():
            label = json.loads(gt_file.read_text(encoding="utf-8"))
            row["ground_truth_status"] = label.get("status", "DRAFT")
            row["scored"] = label.get("status") == "VERIFIED"
    old["gate_result"] = "PARTIALLY MEASURABLE: section, annex and targeted fact-sample scores only; full article/requirement accuracy not claimed."
    (OUT / "results.json").write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
