"""Small field-wise evaluator; deliberately reports no aggregate accuracy score."""
from __future__ import annotations

from collections import defaultdict
from time import perf_counter

from .extractor import extract_male_municipal_v1


def evaluate(pairs: list[tuple[object, dict]]) -> dict:
    buckets = defaultdict(lambda: {"documents": 0, "detection_correct": 0, "table_detected": 0,
                                   "header_mapping_correct": 0, "header_mapping_total": 0, "expected_rows": 0,
                                   "row_count_correct": 0, "cells_total": 0, "cells_exact": 0,
                                   "normalized_numeric_total": 0, "normalized_numeric_exact": 0,
                                   "review_documents": 0, "not_checkable_documents": 0, "processing_ms": []})
    for page, truth in pairs:
        source = truth.get("source_type", "unknown")
        metrics = buckets[source]
        started = perf_counter()
        result = extract_male_municipal_v1(page, document_id=truth.get("document_id"))
        metrics["processing_ms"].append((perf_counter()-started)*1000)
        metrics["documents"] += 1
        metrics["detection_correct"] += int(result.detected == truth.get("template_detected", True))
        expected_table = truth.get("table_detected", result.detected)
        metrics["table_detected"] += int((result.table_bbox is not None and result.detected) == expected_table)
        expected_mapping = truth.get("column_mapping", result.column_mapping)
        metrics["header_mapping_total"] += len(expected_mapping)
        metrics["header_mapping_correct"] += sum(result.column_mapping.get(k) == v for k, v in expected_mapping.items())
        expected_rows = truth.get("rows", [])
        metrics["expected_rows"] += len(expected_rows)
        metrics["row_count_correct"] += int(len(result.rows) == len(expected_rows))
        metrics["review_documents"] += int(result.review_status == "NEEDS_REVIEW")
        metrics["not_checkable_documents"] += int(result.review_status == "NOT_CHECKABLE")
        expected_validation = truth.get("expected_validation")
        if expected_validation:
            metrics.setdefault("validation_documents", 0)
            metrics.setdefault("validation_correct", 0)
            metrics["validation_documents"] += 1
            metrics["validation_correct"] += int(any(check.status == expected_validation for check in result.validation) or any(row.validation_status == expected_validation for row in result.rows))
        for row_index, expected in enumerate(expected_rows):
            actual = result.rows[row_index] if row_index < len(result.rows) else None
            for key, expected_value in expected.items():
                if key.endswith("_normalized"):
                    metrics["normalized_numeric_total"] += 1
                    actual_value = getattr(actual, key.removesuffix("_normalized")).normalized_value if actual else None
                    metrics["normalized_numeric_exact"] += int(str(actual_value) == str(expected_value))
                elif key.endswith("_raw"):
                    metrics["cells_total"] += 1
                    actual_value = getattr(actual, key.removesuffix("_raw")).raw_value if actual else None
                    metrics["cells_exact"] += int(actual_value == expected_value)
    report = {}
    for source, metrics in buckets.items():
        report[source] = dict(metrics)
        report[source]["template_detection_rate"] = metrics["detection_correct"] / metrics["documents"] if metrics["documents"] else None
        report[source]["table_detection_rate"] = metrics["table_detected"] / metrics["documents"] if metrics["documents"] else None
        report[source]["header_mapping_rate"] = metrics["header_mapping_correct"] / metrics["header_mapping_total"] if metrics["header_mapping_total"] else None
        report[source]["row_count_rate"] = metrics["row_count_correct"] / metrics["documents"] if metrics["documents"] else None
        report[source]["cell_exact_rate"] = metrics["cells_exact"] / metrics["cells_total"] if metrics["cells_total"] else None
        report[source]["normalized_numeric_exact_rate"] = metrics["normalized_numeric_exact"] / metrics["normalized_numeric_total"] if metrics["normalized_numeric_total"] else None
        report[source]["arithmetic_validation_accuracy"] = metrics.get("validation_correct", 0) / metrics.get("validation_documents", 1) if metrics.get("validation_documents") else None
        report[source]["mean_processing_ms"] = sum(metrics["processing_ms"]) / len(metrics["processing_ms"]) if metrics["processing_ms"] else None
        report[source]["review_rate"] = (metrics["review_documents"]+metrics["not_checkable_documents"]) / metrics["documents"] if metrics["documents"] else None
    report.setdefault("real", {"status": "NOT YET MEASURABLE"})
    report.setdefault("reference", {"status": "NOT MEASURED"})
    report.setdefault("synthetic", {"status": "NOT MEASURED"})
    return report
