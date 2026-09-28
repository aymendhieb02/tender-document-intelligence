from __future__ import annotations

from app.cdc_analysis.schema import Evidence, Requirement, TenderDocument
from app.tender_intelligence_v2 import compose_tender_modules
from app.tender_summary import build_tender_summary
from app.tender_summary.models import FactState


def _candidate(document_id: str, element_id: str, text: str, *, page: int = 1) -> Requirement:
    evidence = Evidence(document_id=document_id, page=page, element_id=element_id, raw_text=text)
    return Requirement(
        id=f"candidate-{element_id}", type="candidate_only", text=text, source_page=page,
        source_evidence=[evidence],
    )


def test_composer_links_normalized_facts_and_projects_structured_summary():
    document_id = "contract-test"
    text = "Le candidat doit fournir une offre valable 60 jours."
    document = TenderDocument(
        document_id=document_id,
        requirements=[_candidate(document_id, "line-1", text)],
    )

    result = compose_tender_modules(document, document_result={"document_id": document_id}, filename="CDC.pdf")

    assert len(result["requirements"]) == 1
    requirement = result["requirements"][0]
    assert requirement.review_status.value == "NEEDS_REVIEW"
    assert requirement.related_value_refs == (result["financial_facts"][0].id,)
    fact = result["financial_facts"][0]
    assert fact.fact.category == "offer_validity"
    assert fact.fact.normalized == {"value": 60, "unit": "DAY"}
    assert fact.evidence_scope == "matched_source_element"
    assert fact.evidence[0].element_id == "line-1"

    summary = result["summary"]
    assert summary.dates["offer_validity"].state is FactState.PRESENT
    assert summary.dates["offer_validity"].value == {"value": "60", "unit": "DAY"}
    assert summary.dates["offer_validity"].candidate_ids == [fact.id]
    assert summary.requirements.by_category[requirement.category.value] == 1
    assert summary.requirements.review_required == 1
    assert summary.review_items[0].code == "requirement_needs_review"

    assert result["dossier"]["documents"][0]["role"] == "CDC"
    assert result["dossier"]["grouping"]["status"] == "review"
    assert result["dossier_reason"] == "single_document_dossier_grouping_not_evaluated"


def test_conflicting_submission_dates_remain_visible_and_reviewable():
    document_id = "conflicting-deadlines"
    first = "La date limite de réception des offres est le 30 juin 2026."
    second = "Nouvelle date limite de réception des offres le 15 juillet 2026."
    document = TenderDocument(
        document_id=document_id,
        requirements=[
            _candidate(document_id, "deadline-1", first),
            _candidate(document_id, "deadline-2", second, page=2),
        ],
    )

    result = compose_tender_modules(document, document_result={"document_id": document_id}, filename="CDC.pdf")

    facts = [fact for fact in result["financial_facts"] if fact.fact.category == "submission_deadline"]
    assert {fact.fact.status for fact in facts} == {"conflict"}
    assert len({fact.fact.conflict_group for fact in facts}) == 1
    summary_fact = result["summary"].dates["submission_deadline"]
    assert summary_fact.state is FactState.AMBIGUOUS
    assert len(summary_fact.candidate_ids) == 2
    dossier_conflict = result["dossier"]["conflicts"]
    assert len(dossier_conflict) == 1
    assert dossier_conflict[0]["fact_key"] == "submission_deadline"
    assert {item["page"] for item in dossier_conflict[0]["observations"]} == {1, 2}


def test_summary_keeps_penalty_rate_and_cap_as_complementary_facts():
    evidence = {
        "document_id": "penalties", "page": 1, "element_id": "e1", "raw_text": "Article 22",
    }
    summary = build_tender_summary(
        TenderDocument(document_id="penalties"),
        classified_requirements=[],
        financial_deadline_facts=[
            {"id": "rate", "category": "penalty_rate", "raw": "2/1000 per day",
             "normalized": {"value": "0.002", "unit": "DECIMAL_RATE"}, "status": "normalized",
             "evidence": [evidence]},
            {"id": "cap", "category": "penalty_cap", "raw": "5% maximum",
             "normalized": {"value": "5", "unit": "PERCENT"}, "status": "normalized",
             "evidence": [evidence]},
        ],
    )
    penalties = summary.financial["penalties"]
    assert penalties.state is FactState.PRESENT
    assert [item["id"] for item in penalties.value] == ["rate", "cap"]
