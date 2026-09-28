"""Score the deterministic financial/deadline layer on unchanged V1 labels."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.cdc_analysis.financial_deadline import normalize_financial_deadlines

SCOPE = {
    "offer_validity", "annual_contract_duration", "penalty_rate", "penalty_cap",
    "payment_schedule", "submission_deadline", "provisional_guarantee", "payment_deadline",
}


def _value(fact: dict) -> object:
    norm = fact.get("normalized") or {}
    if fact["category"] in ("provisional_guarantee", "guarantee_amount", "money"):
        return Decimal(norm["amount"])
    if fact["category"] in ("penalty_rate", "penalty_cap", "offer_validity", "duration", "execution_period", "payment_deadline"):
        return Decimal(norm["value"])
    if fact["category"] in ("submission_deadline", "date"):
        day = norm.get("date")
        return f"{day} {norm['time']}" if day and norm.get("time") else day
    return norm


def _matches_type(requirement_type: str, fact: dict) -> bool:
    category = fact["category"]
    return {
        "offer_validity": {"offer_validity"},
        "annual_contract_duration": {"duration", "execution_period"},
        "penalty_rate": {"penalty_rate"},
        "penalty_cap": {"penalty_cap"},
        "payment_schedule": {"payment_schedule"},
        "submission_deadline": {"submission_deadline"},
        "provisional_guarantee": {"provisional_guarantee"},
        "payment_deadline": {"payment_deadline"},
    }[requirement_type].__contains__(category)


def _legacy_v2_match(requirement_type: str, raw: str, expected: object) -> bool:
    """Replay only the former normalizer predicates on each labeled raw span."""
    if requirement_type == "offer_validity":
        m = re.search(r"\b(\d{1,3})\s*(?:jours?|days?)\b", raw, re.I)
        return bool(m and Decimal(m.group(1)) == Decimal(str(expected)))
    if requirement_type == "penalty_rate":
        m = re.search(r"\b(\d+)\s*/\s*(\d+)\b", raw)
        return bool(m and Decimal(m.group(1))/Decimal(m.group(2)) == Decimal(str(expected)))
    if requirement_type == "penalty_cap":
        m = re.search(r"plafonn\w*.{0,80}?\b(\d+(?:[,.]\d+)?)\s*%", raw, re.I)
        return bool(m and Decimal(m.group(1).replace(",", ".")) == Decimal(str(expected)))
    if requirement_type == "payment_deadline":
        return bool(re.search(r"45\s*jours", raw, re.I) and Decimal(str(expected)) == Decimal(45))
    return False


def _score(expected: dict, predictions: list[dict]) -> tuple[bool, object, dict | None]:
    choices = [p for p in predictions if _matches_type(expected["requirement_type"], p)]
    if expected.get("normalized_value") is None:
        # For qualitative schedule labels, evidence and a structured schedule
        # are the expected signal even though the benchmark leaves value null.
        return bool(choices), choices[0]["normalized"] if choices else None, choices[0] if choices else None
    target = expected["normalized_value"]
    for choice in choices:
        value = _value(choice)
        if expected["requirement_type"] in ("submission_deadline",):
            if value == target:
                return True, value, choice
        elif isinstance(target, (int, float)):
            if value == Decimal(str(target)):
                return True, value, choice
    return False, _value(choices[0]) if choices else None, choices[0] if choices else None


def evaluate() -> dict:
    rows=[]
    for path in sorted((ROOT / "benchmarks/cdc_real_v1/ground_truth").glob("CDC-DEV-*.json")):
        gt=json.loads(path.read_text(encoding="utf-8"))
        if gt.get("status") != "VERIFIED":
            continue
        for expected in gt.get("important_requirements", []):
            if expected["requirement_type"] not in SCOPE:
                continue
            facts=[fact.as_dict() for fact in normalize_financial_deadlines(expected["raw_text"])]
            correct,predicted,chosen=_score(expected,facts)
            old=_legacy_v2_match(expected["requirement_type"],expected["raw_text"],expected.get("normalized_value"))
            rows.append({"document_id":gt["corpus_document_id"],"requirement_type":expected["requirement_type"],
                "raw_text":expected["raw_text"],"expected_value":expected.get("normalized_value"),
                "predicted_value":str(predicted) if isinstance(predicted,Decimal) else predicted,"correct":correct,"legacy_v2_correct":old,
                "status":chosen["status"] if chosen else "missing","facts":facts})
    return {"artifact_version":"financial_deadline_eval_v1","corpus":"CDC_DEVELOPMENT_CORPUS_V1",
        "label_files_unchanged":True,"scope":"Verified labeled raw spans for financial and temporal requirement types; excludes non-owned production quantities and draft documents.",
        "baseline_method":"Replay of legacy V2 normalization predicates on the same raw labeled spans; this is a rule-level slice, not the published end-to-end 7/14 metric.",
        "examples":len(rows),"legacy_v2_exact":sum(r["legacy_v2_correct"] for r in rows),
        "new_exact":sum(r["correct"] for r in rows),"delta_exact":sum(r["correct"] for r in rows)-sum(r["legacy_v2_correct"] for r in rows),
        "improvements":[r["requirement_type"]+" @ "+r["document_id"] for r in rows if r["correct"] and not r["legacy_v2_correct"]],
        "regressions":[r["requirement_type"]+" @ "+r["document_id"] for r in rows if r["legacy_v2_correct"] and not r["correct"]],
        "rows":rows}


if __name__ == "__main__":
    output=evaluate()
    path=ROOT/"benchmarks/cdc_real_v1/financial_deadline_v1.json"
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:output[key] for key in ("examples","legacy_v2_exact","new_exact","delta_exact","improvements","regressions")},ensure_ascii=False,indent=2))
    print(path.relative_to(ROOT))
