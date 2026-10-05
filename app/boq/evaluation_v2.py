"""Versioned field-wise BOQ evaluation; cohorts never share an aggregate score."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .models import BOQDocument

FIELDS = ("article", "designation", "unit", "quantity", "unit_price_ht", "total_ht",
          "unit_price_ttc", "total_ttc")
COHORTS = {"real_completed", "real_empty_template", "synthetic"}


def _equal(actual, expected) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    try:
        return Decimal(str(actual)) == Decimal(str(expected))
    except (InvalidOperation, ValueError):
        return " ".join(str(actual).casefold().split()) == " ".join(str(expected).casefold().split())


def evaluate_cases(cases: list[dict]) -> dict:
    """Each case supplies schema_version, cohort, expected, and extracted BOQDocument."""
    report = {name: {"documents": 0, "presence": {"correct": 0, "total": 0},
                     "candidate_page": {"correct": 0, "total": 0},
                     "row_count": {"correct": 0, "total": 0},
                     "fields": {field: {"correct": 0, "total": 0} for field in FIELDS}}
              for name in sorted(COHORTS)}
    for case in cases:
        if case.get("schema_version") != 1 or case.get("cohort") not in COHORTS:
            raise ValueError("Unknown BOQ evaluation schema or cohort")
        result = BOQDocument.model_validate(case["actual"])
        expected = case["expected"]
        bucket = report[case["cohort"]]
        bucket["documents"] += 1
        bucket["presence"]["total"] += 1
        bucket["presence"]["correct"] += int(result.detected == expected["detected"])
        if "candidate_page" in expected:
            bucket["candidate_page"]["total"] += 1
            bucket["candidate_page"]["correct"] += int(result.detection.get("header_page") == expected["candidate_page"] or
                                                      (result.rows and result.rows[0].source_page == expected["candidate_page"]))
        if "rows" in expected:
            bucket["row_count"]["total"] += 1
            bucket["row_count"]["correct"] += int(len(result.rows) == len(expected["rows"]))
            for index, row_truth in enumerate(expected["rows"]):
                actual = result.rows[index] if index < len(result.rows) else None
                for field in FIELDS:
                    if field not in row_truth:
                        continue
                    cell = bucket["fields"][field]
                    cell["total"] += 1
                    value = getattr(actual, field).normalized_value if actual is not None else None
                    cell["correct"] += int(_equal(value, row_truth[field]))
    return {"schema_version": 1, "cohorts": report}
