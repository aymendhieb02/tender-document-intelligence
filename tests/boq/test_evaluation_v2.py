from app.boq.evaluation_v2 import evaluate_cases
from app.boq.models import BOQDocument, BOQRow, ParsedValue


def observed(value):
    return ParsedValue(raw_value=str(value), normalized_value=value, parse_status="PARSED", value_origin="OBSERVED")


def test_evaluation_v2_keeps_real_empty_and_synthetic_separate():
    empty = BOQDocument(extractor_family="test", detected=True, rows=[BOQRow(article=observed("01"), source_page=25)])
    synthetic = BOQDocument(extractor_family="test", detected=True, rows=[BOQRow(
        article=observed("01"), quantity=observed("1000"), unit_price_ht=observed("12.500"), source_page=1)])
    report = evaluate_cases([
        {"schema_version": 1, "cohort": "real_empty_template", "actual": empty,
         "expected": {"detected": True, "candidate_page": 25, "rows": [{"article": "01", "quantity": None}]}},
        {"schema_version": 1, "cohort": "synthetic", "actual": synthetic,
         "expected": {"detected": True, "candidate_page": 1,
                      "rows": [{"article": "01", "quantity": "1000", "unit_price_ht": "12.500"}]}},
    ])
    assert report["cohorts"]["real_completed"]["documents"] == 0
    assert report["cohorts"]["real_empty_template"]["fields"]["quantity"] == {"correct": 1, "total": 1}
    assert report["cohorts"]["synthetic"]["fields"]["unit_price_ht"] == {"correct": 1, "total": 1}
